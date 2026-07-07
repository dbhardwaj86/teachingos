NO-GO → REMEDIATED (both findings fixed TDD post-review — effectively GO; see "Remediation" at end)

# DEC-7 pre-merge review: Phase F2 slides lane NotebookLM subprocess boundary

Date: 2026-07-07
Repo: `C:/SandBox/claude_box/TeachingOS`
Branch/head reviewed: `feature/content-factory-phase-f2-slides` at `9ac6726`
Base reviewed: `main` at `db4bfe0`
Review range: `db4bfe0..HEAD`
Scope: Phase F2 `slides` lane: the first SAMAGRA subprocess/external-CLI generation boundary, `nlm` client, synchronous NotebookLM deck orchestration, factory wiring, HTTP reachability, publish compatibility, cleanup, and path safety. Ground truth checked against `docs/superpowers/specs/2026-07-07-samagra-content-factory-phase-f2-slides-lane-design.md` section 3 and section 4.

## Verdict

NO-GO.

No HIGH findings were found, but two review-focus invariants do not fully hold:

1. Slides output paths are formed from a raw `slug`, so a hostile absolute or traversal slug can move the working deck, JSON, and HTML outside `EXPORT_DIR`.
2. Invalid `SAMAGRA_SLIDES_*` deck-format env values are validated only when `NotebookLMClient()` is constructed inside `build_slides()`, after `run.build()` has already recorded `product_building`; the ratified spec says those env failures refuse during `slides.preflight()` before build intent.

The subprocess boundary itself is otherwise shaped correctly: `nlm` invocations use argv lists, no `shell=True` was found in the reviewed surface, `configured()` parses stdout rather than exit code, `nlm` stderr/chapter text is not echoed in raised errors, cleanup runs in `finally`, the default autocapture posture is conservative, and HTTP build/approve-seed remain CLI-only for `kind="llm"`.

Worktree note before this report: the branch already had dirty/untracked items outside the reviewed F2 source surface (`AGENTS.md`, `CLAUDE.md`, `.playwright-mcp/`, `samagra_overhaul.html`, `tmp/`). I did not modify source files; this review creates only this report file. The targeted pytest run used workspace-local temp paths under `tmp/`.

## Scope

Files inspected with line-level evidence:
- `docs/codex-reviews/33-f1-figure-lane-premerge.report.md`
- `docs/superpowers/specs/2026-07-07-samagra-content-factory-phase-f2-slides-lane-design.md`
- `docs/superpowers/plans/2026-07-07-samagra-content-factory-phase-f2-slides-lane.md`
- `.env.example`
- `requirements.txt`
- `samagra/clients/notebooklm_client.py`
- `samagra/factory/slides.py`
- `samagra/factory/dispatch.py`
- `samagra/factory/lines.py`
- `samagra/factory/run.py`
- `samagra/api/app.py`
- `samagra/lectures/render.py`
- `samagra/config.py`
- `samagra/factory/publish/run.py`
- `samagra/factory/publish/store.py`
- `samagra/factory/publish/read.py`
- `tests/test_notebooklm_client.py`
- `tests/test_factory_slides.py`
- `tests/test_factory_slides_wiring.py`
- `tests/test_slides_golden.py`
- `tests/test_slides_invariants.py`
- `tests/test_slides_live_smoke.py`
- `tests/test_factory_lines.py`
- `tests/test_publish_run.py`

Diff scope checked: `git diff --name-status main...HEAD` lists only `.env.example`, the F2 spec/plan docs, `requirements.txt`, the new NotebookLM client and slides engine, the small factory wiring edits, and F2 tests. There is no committed diff under governance, coverage, Pratham, adapters, org, or the question proxy.

## Findings

| Severity | File:line | Issue | Suggested fix |
|---|---|---|---|
| MED | `samagra/factory/slides.py:249` | Slides artifacts are not guaranteed to stay under `EXPORT_DIR`. `build_slides()` uses the raw `slug` in `out = config.EXPORT_DIR / slug`, `workdir = out / f"{slug}-slides"`, and the final filenames at `samagra/factory/slides.py:249-266` and `samagra/factory/slides.py:292-300`. The upstream seed guard only checks prefix and non-empty slug at `samagra/factory/dispatch.py:24-33`, and the chapter loader also joins the raw slug at `samagra/lectures/render.py:59-63`. Failure scenario: a CLI build for `textbook:C:\tmp\f2-owned` where `C:\tmp\f2-owned\content.json` exists can write `C:\tmp\f2-owned-slides.html`, `C:\tmp\f2-owned-slides.json`, and `C:\tmp\f2-owned-slides\deck.pdf` outside `EXPORT_DIR`; `..\` segments have the same class of escape. | Reject unsafe slugs before any path use, ideally centrally in `dispatch.validate_seed_for_line()` or a shared slug helper: require a single safe segment such as `[A-Za-z0-9][A-Za-z0-9._-]*`, reject absolute paths, separators, drive letters, and `..`, and resolve/assert every F2 output path remains under `config.EXPORT_DIR.resolve()` before `mkdir()` or writes. |
| LOW | `samagra/factory/slides.py:190` | `slides.preflight()` does not validate the deck-format env knobs before `product_building`. The spec says `slides.preflight()` checks chapter existence, `notebooklm_client.configured()`, and valid deck env before intent (`docs/superpowers/specs/2026-07-07-samagra-content-factory-phase-f2-slides-lane-design.md:178-180`, `docs/superpowers/specs/2026-07-07-samagra-content-factory-phase-f2-slides-lane-design.md:273-276`). Actual preflight only loads the chapter and checks `configured()` at `samagra/factory/slides.py:190-200`; invalid `SAMAGRA_SLIDES_FORMAT`, `SAMAGRA_SLIDES_LENGTH`, or `SAMAGRA_SLIDES_DOWNLOAD_FORMAT` raises later in `NotebookLMClient.__init__()` at `samagra/clients/notebooklm_client.py:71-83`, reached by `build_slides()` at `samagra/factory/slides.py:245-247` after `run.build()` has appended `product_building` at `samagra/factory/run.py:403-418`. Failure scenario: `SAMAGRA_SLIDES_FORMAT=fancy_deck` records `product_building` and then `product_build_failed` instead of cleanly refusing before intent. | Add a no-side-effect config validation call inside `slides.preflight()` before it returns, for example constructing `NotebookLMClient()` only to validate env knobs, or factoring a `notebooklm_client.validate_config()` helper and testing that bad env leaves no `product_building` event. |

## Invariants

| # | Review focus item | Verdict | Evidence |
|---|---|---|---|
| 1 | No new prod write path. | FAIL | No protected-store diffs were found, and `nlm` is outbound through the client, but F2 local artifact writes are not guaranteed to be under `EXPORT_DIR` because raw `slug` reaches `config.EXPORT_DIR / slug` at `samagra/factory/slides.py:249`; see MED finding. |
| 2 | Subprocess safety. | PASS | The real runner calls `subprocess.run(list(args), ...)` at `samagra/clients/notebooklm_client.py:40-47`; `configured()` uses a list at `samagra/clients/notebooklm_client.py:58`; typed methods pin list argv at `samagra/clients/notebooklm_client.py:103-141`. The 16000-char source cap is enforced at `samagra/factory/slides.py:37-49` and tested against `subprocess.list2cmdline()` at `tests/test_factory_slides.py:64-80`. |
| 3 | Secret non-leak. | PASS | There is no SAMAGRA Google secret; `.env.example` states `nlm` owns OAuth at `.env.example:64-78`. Client errors wrap missing executable, timeout, unexpected runner errors, nonzero exits, and unparseable status without raw stderr/source text at `samagra/clients/notebooklm_client.py:86-100` and `samagra/clients/notebooklm_client.py:124-130`; delete-failure logging names only the notebook id at `samagra/factory/slides.py:271-282`. |
| 4 | Never-automated publish gate. | PASS | `SAMAGRA_SLIDES_AUTOCAPTURE` defaults false via `config._env_bool(..., False)` at `samagra/factory/run.py:461-466`, so successful slides builds route to `changes` unless explicitly opted in; tests pin default `changes` and opt-in `captured` at `tests/test_factory_slides_wiring.py:140-157`. |
| 5 | The 5 `build()` crash-safety guards. | FAIL | The guard block is otherwise unchanged (`samagra/factory/run.py:361-379`), the F2 diff adds only `slides.preflight()` and the autocapture clause, and rollback appends `product_build_failed` for non-`mcd` failures at `samagra/factory/run.py:431-445`. However, bad deck env values are not preflighted before `product_building`; see LOW finding. |
| 6 | No migration. | PASS | There is no committed diff under `samagra/governance` or coverage store code; governance schema creation remains in `samagra/governance/store.py:27-40`. Golden tests pin unchanged `PRAGMA user_version` and no new governance table at `tests/test_slides_golden.py:68-97`. |
| 7 | DEC-8 reviewer firewall. | PASS | The slides engine imports only config, `notebooklm_client`, and lecture render at `samagra/factory/slides.py:27-29`, states no StyleSeed/model review at `samagra/factory/slides.py:12-15`, and uses a synthetic owner-review verdict rather than a model-review call at `samagra/factory/slides.py:284-288`. |
| 8 | HTTP-403. | PASS | `slides` is registered as `kind="llm"` and `auto_fan=False` at `samagra/factory/lines.py:44-45`; POST `/api/factory/build` rejects `llm`/`mcd` before `run.build()` at `samagra/api/app.py:414-421`, and approve-seed filters out `llm`/`mcd` children at `samagra/api/app.py:367-369`. Tests pin both at `tests/test_slides_invariants.py:157-187`. |
| 9 | Cleanup correctness. | PASS | `build_slides()` deletes the ephemeral notebook in `finally` at `samagra/factory/slides.py:258-282`, swallows delete failures without masking the primary outcome at `samagra/factory/slides.py:271-282`, and writes JSON/HTML only after `download_slide_deck()`, `read_bytes()`, and the non-empty deck check at `samagra/factory/slides.py:263-270` and `samagra/factory/slides.py:292-300`. Tests cover failure cleanup and delete-failure behavior at `tests/test_factory_slides.py:235-258`. |
| 10 | Path safety. | FAIL | `dl_format` is clamped before forming `deck_path` at `samagra/factory/slides.py:263-266`, and notebook-id parsing fails closed at `samagra/clients/notebooklm_client.py:148-159`, but raw `slug` still controls `EXPORT_DIR` joins and filenames at `samagra/factory/slides.py:249-266` and `samagra/factory/slides.py:292-300`; see MED finding. |

## Boundary Checks

### NotebookLM client

`configured()` is correctly stdout-based. It runs `[_nlm_bin(), "login", "--check"]` at `samagra/clients/notebooklm_client.py:56-64`, returns false on `"Authentication Error"`, and returns true only when the authenticated marker is present. Tests pin authenticated, expired-exit-zero, expired-exit-one, missing binary, and runner-error cases at `tests/test_notebooklm_client.py:55-91` and the fail-closed both-markers case at `tests/test_notebooklm_client.py:312-317`.

The subprocess boundary is list-argv based. `_default_runner()` calls `subprocess.run(list(args), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=...)` at `samagra/clients/notebooklm_client.py:40-47`; `_run()` passes `list(args)` into the injected runner at `samagra/clients/notebooklm_client.py:86-101`. The typed methods expose only notebook create/delete, source add, slides create, studio status, and slide-deck download at `samagra/clients/notebooklm_client.py:103-141`. Tests assert exact argv shapes and list semantics at `tests/test_notebooklm_client.py:126-219` and `tests/test_notebooklm_client.py:260-267`.

Errors are concise and do not echo raw `nlm` stderr, source text, or status payloads. `_run()` wraps failures at `samagra/clients/notebooklm_client.py:90-100`; `studio_status()` reports only unparseable JSON length at `samagra/clients/notebooklm_client.py:124-130`. Tests cover stderr, chapter text, parse, and unexpected-runner leak cases at `tests/test_notebooklm_client.py:222-245` and `tests/test_notebooklm_client.py:293-309`.

### Slides engine

The source text projection is deterministic and bounded. `_source_text_bounded()` truncates at `_SOURCE_MAX_CHARS` at `samagra/factory/slides.py:99-104`; `_SOURCE_MAX_CHARS = 16000` is documented as a Windows command-line rail at `samagra/factory/slides.py:37-49`, and the test proves adversarial all-quote and realistic LaTeX text remain below `32767` once passed to `subprocess.list2cmdline()` at `tests/test_factory_slides.py:64-80`.

The wrapper HTML is self-contained and title-escaped. `_wrapper_html()` base64-embeds the deck in a `data:` URI at `samagra/factory/slides.py:138-161`, escapes the title at `samagra/factory/slides.py:147-160`, and switches oversize/PPTX decks to download-only while keeping the same data URI at `samagra/factory/slides.py:150-158`. Tests cover PDF embed, no external refs, title escaping, oversize fallback, and PPTX download card at `tests/test_factory_slides.py:88-125`.

The cleanup path does not mask primary success/failure. The external lifecycle is inside the `try/finally` at `samagra/factory/slides.py:258-282`; delete failures are caught and logged with only `nb` at `samagra/factory/slides.py:271-282`. The local JSON/HTML writes occur only after non-empty deck bytes are confirmed at `samagra/factory/slides.py:263-270` and `samagra/factory/slides.py:292-300`.

The remaining slides-engine defect is path containment: `slug` is never normalized to a single safe path segment before it is used in path joins and filenames. This is the source of the MED finding and causes invariant 1/10 failure.

### Factory wiring and HTTP reachability

`slides` is a `kind="llm"`, opt-in `textbook:` lane at `samagra/factory/lines.py:44-45`, while default fan-out still includes only auto-fan lines at `samagra/factory/lines.py:53-62`. `dispatch.run_line()` special-cases slides before the generic `kind=="llm"` samadhan branch at `samagra/factory/dispatch.py:36-61`; `validate_product()` adds `_assert_slides_present()` at `samagra/factory/dispatch.py:83-96`, and the slides branch requires a non-empty working deck at `samagra/factory/dispatch.py:197-207`.

`run.build()` keeps the established guard and rollback envelope. The existing assignment, workflow, approved-status, already-built, in-flight, and seed-prefix checks remain at `samagra/factory/run.py:361-379`. The F2 committed diff adds the `slides.preflight()` branch at `samagra/factory/run.py:403-414` and the conservative `SAMAGRA_SLIDES_AUTOCAPTURE` clause at `samagra/factory/run.py:461-466`; `product_build_failed` rollback for non-`mcd` lanes remains at `samagra/factory/run.py:431-445`.

HTTP stays CLI-only for slides. The HTTP plan endpoint omits lane targeting and uses default classify at `samagra/api/app.py:314-330`, so opt-in slides is not planned there. HTTP approve-seed skips `llm`/`mcd` at `samagra/api/app.py:367-369`, and HTTP build rejects `llm`/`mcd` with 403 before calling `factory_run.build()` at `samagra/api/app.py:414-421`.

### Publish story

Slides publish compatibility uses the existing captured-artifact contract. `publish.PUBLISHABLE` is every non-`mcd` lane at `samagra/factory/publish/run.py:24`; `_captured_publishable()` copies only existing `html`, `json`, and `docx` source files at `samagra/factory/publish/run.py:68-99`. `publish()` stages bytes and writes frozen files through `write_published_file()` at `samagra/factory/publish/run.py:116-177`. The publish store validates `chapter` and `basename` as safe segments before writing under `PUBLISHED_DIR` at `samagra/factory/publish/store.py:101-107`, and the read resolver re-validates manifest rel paths and containment at `samagra/factory/publish/read.py:33-70`.

The publish boundary is therefore not the path-containment defect. The defect is earlier: a slides build can produce its local captured artifact outside `EXPORT_DIR` before publish is involved.

## Verification

- `git diff --name-status main...HEAD` confirmed the committed F2 diff surface: env/docs/comments, `samagra/clients/notebooklm_client.py`, `samagra/factory/slides.py`, factory wiring, and F2 tests.
- `git diff --check main...HEAD` exited 0.
- Static subprocess scan over the F2 client/engine/wiring/tests found `subprocess.run` only in `samagra/clients/notebooklm_client.py:44` and found no `shell=True` / `shell=` / `Popen` / `os.system` in the reviewed F2 runtime surface.
- Targeted offline pytest command:

```powershell
$env:PYTHONIOENCODING='utf-8'
$env:TEMP='C:\SandBox\claude_box\TeachingOS\tmp\pytest-temp'
$env:TMP='C:\SandBox\claude_box\TeachingOS\tmp\pytest-temp'
.\.venv\Scripts\python.exe -m pytest tests/test_notebooklm_client.py tests/test_factory_slides.py tests/test_factory_slides_wiring.py tests/test_slides_golden.py tests/test_slides_invariants.py tests/test_factory_lines.py tests/test_publish_run.py -q --basetemp tmp\pytest-f2-review-34
```

Result: exit 0, all selected tests passed. Warnings were limited to a Starlette `TestClient` deprecation warning and a pytest cache write warning for `.pytest_cache` access denial.

- I did not run the opt-in live NotebookLM smoke; it is explicitly gated by `SAMAGRA_LIVE_SLIDES_SMOKE` and `notebooklm_client.configured()` at `tests/test_slides_live_smoke.py:26-45`.

## Remediation (post-review, 2026-07-07 — orchestrator)

Both findings were remediated TDD on `feature/content-factory-phase-f2-slides` (the orchestrator drove the fixes; each shipped with regressions and the full 848-test gate stayed green with 0 failures). The NO-GO is thereby closed to **effectively GO**.

- **MED (slug path-containment) — FIXED (`a4d66e2`).** Added `_SAFE_SLUG_RE = ^[A-Za-z0-9][A-Za-z0-9._-]*$` + `_assert_safe_slug()` (rejects absolute paths, separators, drive letters, and `..`) as the FIRST statement of BOTH `slides.preflight()` and `slides.build_slides()`, before any path is formed or `render.load_chapter` is called — defense-in-depth at the F2 write boundary, mirroring `publish/store.py`'s segment guard and the existing `dl_format` clamp. Regressions: `test_safe_slug_accepts_real_chapter_slugs`, `test_build_slides_rejects_unsafe_slug` (`../evil`, `..\evil`, `a/b`, `C:\tmp\x`, `/etc/x`, `a..b`, ``), `test_preflight_rejects_unsafe_slug`. Invariants 1 + 10 (the two that FAILED on this finding) now hold for the F2 lane. NOTE: the raw-slug pattern is factory-wide (also `render.load_chapter` + the other lanes + the `dispatch` seed guard) — F2 hardened its own boundary; the broader central guard (Codex's preferred `dispatch.validate_seed_for_line()`/shared-helper site) is tracked as a separate hardening slice, since F2 did not introduce the pattern.
- **LOW (preflight deck-format knob drift) — FIXED (`0146e94`).** `slides.preflight()` now constructs a throwaway `NotebookLMClient()` (its `__init__` is side-effect-free — validates `SAMAGRA_SLIDES_FORMAT/LENGTH/DOWNLOAD_FORMAT` against their enums, no subprocess) so a bogus deck-format env value refuses BEFORE `run.build()` records the `product_building` intent — the true anti-wedge the spec §3.6.2 promises. Invariant 5 (which FAILED only on this) now holds. Regression: `test_preflight_bad_deck_format_refuses_before_intent`.

Two additional 4-lens-adversarial findings (independent of this Codex pass) were remediated in the same window: a MED (source-add + poll each budgeted the full `SAMAGRA_SLIDES_TIMEOUT` ⇒ ~2× total wall-clock) fixed via a SHARED absolute deadline threaded through both stages (`0146e94`), and a NIT (`_poll_interval()` unbounded ⇒ `SAMAGRA_SLIDES_POLL_INTERVAL=0` busy-loop) floored to 1.0s (`0146e94`). Full gate after all remediation: **848 pytest, 0 failures, 0 errors, 4 skipped** (opt-in live smokes).

NO-GO (original) → effectively GO (remediated)
