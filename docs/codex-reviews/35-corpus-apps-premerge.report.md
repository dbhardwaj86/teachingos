# Codex Review #35 — Corpus Apps HTTP Boundary Pre-Merge Review

**Metadata:**
- Repo path: `C:\SandBox\claude_box\TeachingOS`
- Branch: `feature/desktop-icons-corpus-apps`
- Date: 2026-07-09 (Asia/Calcutta)
- Scope: `samagra/api/corpus_proxy.py`, `samagra/api/app.py`, `samagra/api/origin_auth.py`, `samagra/adapters/{gnocr,onedpull,lecturepdf}.py`, `samagra/config.py`, and the named corpus/origin/student/adapters tests.
- Method: read-only working-tree source review. No files were edited or created.
- Model: gpt-5.5, extra-high reasoning.

## Findings

**1. Severity: MED**
File: `samagra/api/corpus_proxy.py:114-125`, `:151-153`, `:253-258`
Description: The SSRF guard validates only the configured initial `base_url`, but the default transport uses `urllib.request.urlopen()` without disabling redirects or validating the final response URL. `urllib` follows HTTP redirects by default, so a loopback daemon response can move the proxy fetch off loopback after the allowlist and base-host checks have already passed.
Exploit scenario: An allowed request such as `/api/corpus/gnocr/serve/api/search?q=x` reaches `http://127.0.0.1:8931/api/search?q=x`; the daemon, a compromised sidecar, or an attacker-influenced endpoint returns `302 Location: http://169.254.169.254/...` or a LAN admin URL. The proxy follows it and returns the off-host bytes to the authenticated caller.
Fix recommendation: Install a no-redirect opener for this proxy, or reject any redirect unless the resolved `Location` is revalidated against the same loopback/allowed-host policy. Also check `resp.url` before reading the body and add a regression test with a fake redirecting transport or local redirect handler.

**2. Severity: MED**
File: `samagra/api/corpus_proxy.py:151-155`, `:257-265`, `tests/test_corpus_proxy.py:184-191`
Description: The 25MB size cap is enforced by reading `cap + 1`, but the 15s timeout is only passed to `urlopen()`/socket operations. There is no wall-clock deadline around the full body read. A peer that slowly drips bytes can keep the worker occupied far beyond 15 seconds while staying under the idle socket timeout and under the size cap. The test only covers a fake transport that raises `TimeoutError`, not a slow streaming body.
Exploit scenario: A local sidecar endpoint accepts an allowed path and sends one byte every few seconds. The SAMAGRA request can remain tied up for minutes or hours, despite the documented 15s cap, without ever exceeding `size_cap`.
Fix recommendation: Replace the single `resp.read(cap + 1)` with a chunked read loop using `time.monotonic()` and a hard total deadline. Abort once either the size cap or total deadline is exceeded, and add a regression test for a slow reader.

**3. Severity: LOW**
File: `samagra/api/corpus_proxy.py:114-125`, `:160-164`, `samagra/config.py:86-91`
Description: Error JSON includes the full configured `base_url` in the user-facing hint. `_validate_base_url()` preserves URL userinfo, so an env-configured URL like `http://user:token@127.0.0.1:8931` would be echoed on daemon-down or timeout paths. Defaults are clean, but the env-overridable URL surface does not reject or redact credentials.
Exploit scenario: An operator temporarily configures a corpus sidecar URL with basic-auth userinfo. Any caller allowed through the origin gate who triggers daemon-down gets the token in the JSON `hint`.
Fix recommendation: Reject `parsed.username`/`parsed.password` in `_validate_base_url()`, or redact userinfo before storing/returning `base_url`. Keep error bodies generic.

## Invariant Table

| # | Invariant | Result | Evidence |
|---|---|---|---|
| 1 | Read-only firewall | PASS | New corpus routes are `@app.get` only (`app.py:220`, `:237`); proxy refuses non-GET (`corpus_proxy.py:248-249`); adapters use sqlite `mode=ro` or filesystem reads (`gnocr.py:13-16`, `onedpull.py:27-28`, `lecturepdf.py:46-64`). |
| 2 | Origin gating complete | PASS | Middleware registered before routes (`app.py:44-48`); `GET /api/corpus/` protected (`origin_auth.py:69-74`); corpus routes registered as GET (`app.py:220`, `:237`). |
| 3 | Traversal/smuggle resistance | PASS | `_normalize()` single-decodes, rejects backslash/colon/dot segments, collapses `//`, runs before allowlist/upstream (`corpus_proxy.py:128-145`, `:250-253`); anchored positive regexes (`:41-64`). |
| 4 | Answer-leak posture | PASS | Onedpull allowlist omits answer families (`corpus_proxy.py:47-50`); normalized paths checked before fetch (`:250-252`); body scan before return (`:222-228`, `:266-269`). |
| 5 | SSRF | FAIL | Initial base hosts constrained (`corpus_proxy.py:114-125`), but fetch uses redirect-following `urllib.request.urlopen()` with no final URL validation (`:151-153`). |
| 6 | DoS | FAIL | Size cap real (`corpus_proxy.py:153-155`, `:264-265`), but timeout is not a hard total streaming deadline around the body read (`:151-153`). |
| 7 | Student surface + publish gate + governance DB untouched | PASS | Byte-identical student responses tested (`test_corpus_student_surface_untouched.py:31-56`); no governance/pratham imports (`:59-70`); published CSP in separate route (`app.py:264-288`). |
| 8 | No secret handling/leak in error paths | FAIL | Upstream exceptions generic, but `_error()` returns full `base_url` in JSON hint (`corpus_proxy.py:160-164`), env-overridable (`config.py:86-91`). |

## Final Verdict

**NO-GO.**

Caveats to close before merge:
- Block or revalidate redirects in the corpus proxy transport.
- Add a hard wall-clock deadline for the full upstream read, not just socket timeout.
- Redact or reject credential-bearing corpus base URLs before they can appear in error JSON.

---

## Remediation log (orchestrator, 2026-07-09)

All 3 findings remediated TDD (red→green each) in `samagra/api/corpus_proxy.py` + regressions in `tests/test_corpus_proxy.py`:

- **F1 (SSRF via redirect) → RESOLVED.** Default transport now uses a `_NoRedirect(HTTPRedirectHandler)` opener (`redirect_request → None` ⇒ urllib raises on any 3xx → graceful 503); post-open `resp.geturl()` hostname must equal the requested hostname else raise; `serve()` additionally refuses any `300≤status<400` from ANY transport (covers injected fakes). Regressions: injected-302 + real-loopback-302→169.254.169.254.
- **F2 (slow-drip DoS) → RESOLVED (caveat).** `_http_fetch` replaced the single `read(cap+1)` with a chunked `read1()` loop under a hard `time.monotonic()` deadline reusing the timeout budget; over-deadline → `TimeoutError` → 503; over-cap → `SizeCapExceeded`. Regression: real loopback dripper (1 byte/0.2s, timeout 0.5s) aborts <2s. Caveat: the deadline is checked before each `read1()`, so one in-flight read can run to the per-read socket timeout — worst case = deadline + one socket-timeout, bounded (NOT the original unbounded hold). Accepted under the single-operator, origin-gated-owner-only threat model.
- **F3 (cred leak) → RESOLVED.** `_validate_base_url()` now rejects any `parsed.username`/`password` at construction (fail-closed) — credentialed sidecar URLs forbidden outright, so `_error()`'s `base_url` hint can never echo userinfo.

**Codex addendum verdict: GO-WITH-CAVEATS** (all 3 RESOLVED, 0 new findings, 5-invariant regression sanity all PASS; lone caveat = the bounded-not-exact F2 deadline, accepted). Gate 5 (dedicated Codex pre-merge review of the proxy/serve/gate boundary) is CLOSED.

Post-remediation gate: **919 pytest** (915 passed, 4 opt-in live-smoke skips, 0 fail) + **668 vitest** (80 files) + `tsc --noEmit` clean + `npm run build` green.
