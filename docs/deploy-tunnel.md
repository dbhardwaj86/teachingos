# SAMAGRA OS — Cloudflare tunnel deploy runbook

Expose the **local** SAMAGRA OS stack at a custom HTTPS URL via a `cloudflared`
**named tunnel** (NOT a Workers/Pages edge deploy — the Python + QX + BGE stack
runs locally; the tunnel just fronts it). Only `:8799` is tunnelled; the QX
sidecar on `:8783` stays internal and is reached via the same-origin
`/api/questions` proxy.

> **✅ LIVE as of 2026-06-22** at **https://samagra.bhautikiplusprashnavali.com**
> behind Cloudflare Access. The values below are the as-shipped reality.

- **Custom hostname:** `samagra.bhautikiplusprashnavali.com` (zone `bhautikiplusprashnavali.com`)
- **Tunnel name / id:** `samagra-os` / `9b7a3df8-6fda-4500-b97c-4592c2dd101e`
- **Origin:** `http://localhost:8799` (FastAPI serving `frontend/dist` + `/api`, same-origin)
- **Committed config:** [`deploy/cloudflared/config.samagra.yml`](../deploy/cloudflared/config.samagra.yml)
- **Auth gate:** Cloudflare Access (one-time-PIN to owner email) — **required before any public run**

> ⚠️ **Access before exposure (hard rule).** Never `cloudflared tunnel run` this
> hostname before its Cloudflare Access application exists and is verified. The
> origin exposes **ten mutating POSTs** that must never be reachable
> unauthenticated:
> `POST /api/refresh`, `POST /api/tick`, **`POST /api/gate/{pipeline}/{decision}`
> (advances the human publish gate — `…/textbook/approve`)**,
> `POST /api/munshi/capture`, `POST /api/mcd/seeds`, (since Phase G3)
> **`POST /api/factory/publish`**, **`POST /api/factory/unpublish`** (the outward
> publish gate's HTTP trigger), and (since Phase G5) **`POST /api/factory/plan`**,
> **`POST /api/factory/approve-seed`**, **`POST /api/factory/build`** (the factory-run
> recipe's HTTP trigger; `build` additionally refuses the llm/mcd lane kinds with a
> structural 403 before any factory code runs — the one production-write path, the
> mcd `seed` lane, keeps zero HTTP triggers) — plus the four protected GETs
> (`GET /api/munshi/library`, `GET /api/mcd/seeds`, `GET /api/search`,
> `GET /api/assignments`). The authoritative list is
> `_PROTECTED_POSTS`/`_PROTECTED_GETS` in `samagra/api/origin_auth.py` — keep this
> paragraph in sync with it.
> **Deliberately public (by design, DEC-11/DEC-12):** `GET /api/published*`,
> `/learn`, and the Phase-G3 student session trio `POST /api/learn/login`,
> `POST /api/learn/logout`, `GET /api/learn/me` — these are the outward student
> surface and are *excluded* from the origin gate on purpose; the session cookie
> is their only credential and the login path writes only `pratham.db`.
> As of **W1.1** the origin **also fails closed** (defence-in-depth, §5): remote
> requests to those routes require a verified Access identity. But because
> `cloudflared` connects from loopback, that origin gate only blocks *non-loopback*
> direct exposure — so **Access remains the primary gate** and the §7 smoke-test
> (unauth request must 302 to the Access login) is load-bearing, not optional.
> This mirrors the existing `hermes.bhautikiplusprashnavali.com` tunnel's gate.

> 🔑 **Why `bhautikiplusprashnavali.com` and not `pratyakshsims.com`?** The local
> `cloudflared` `cert.pem` (from a prior `cloudflared tunnel login`) is **scoped to
> the `bhautikiplusprashnavali.com` zone**. Both domains are on the *same* Cloudflare
> account (identical nameservers), but the cert can only write DNS in the zone it was
> issued for — `route dns samagra.pratyakshsims.com` mangled the name to
> `samagra.pratyakshsims.com.bhautikiplusprashnavali.com`. To use `pratyakshsims.com`
> instead, re-run `cloudflared tunnel login` and select that zone (a browser action,
> owner-only), then repeat steps 3–6 with the new hostname + a new Access app.

---

## 0. Prerequisites (one-time)

- `cloudflared` installed (`cloudflared --version`; shipped on 2025.8.1).
- Authenticated to the Cloudflare account that owns the zone:
  `~/.cloudflared/cert.pem` present **and scoped to the zone you route into**
  (here `bhautikiplusprashnavali.com`). If `route dns` mangles the hostname (appends
  another zone), the cert is scoped to the wrong zone — re-run `cloudflared tunnel
  login` and pick the right one (owner-only browser auth).
- The QX sidecar repo present at `C:\SandBox\gpt_box\gpt-extract-ques` (Questions).

## 1. Bring up the local stack

```powershell
# from the repo root (C:\SandBox\claude_box\TeachingOS)
& .\scripts\serve-local.ps1
```

This builds `frontend/dist`, starts FastAPI on `:8799` and the QX sidecar on
`:8783`, is idempotent (reuses healthy servers; `-Restart` forces a clean
relaunch clearing stale listeners), and prints a health summary. Confirm the
summary shows `FastAPI :8799 HEALTHY` before tunnelling. (Run it directly — do
**not** add `-ExecutionPolicy Bypass`; a local script runs fine under the normal
policy and the bypass flag is an unnecessary security-weakening.)

## 2. Create the tunnel (once) — DONE

```bash
cloudflared tunnel create samagra-os
# -> Created tunnel samagra-os with id 9b7a3df8-6fda-4500-b97c-4592c2dd101e
# -> writes credentials to ~/.cloudflared/<id>.json  (KEEP LOCAL, never commit)
cloudflared tunnel list   # confirm samagra-os + its id
```

## 3. Tunnel config (committed, no secrets) — DONE

The committed config at `deploy/cloudflared/config.samagra.yml` carries the real
tunnel id + the `credentials-file` path under `~/.cloudflared/` (OUTSIDE the repo —
the creds JSON and `cert.pem` are gitignored and never committed; a tunnel UUID is
not a secret). Validate it:

```bash
cloudflared tunnel --config deploy/cloudflared/config.samagra.yml ingress validate   # -> OK
```

`ingress` maps `samagra.bhautikiplusprashnavali.com -> http://localhost:8799`, with
a `http_status:404` catch-all so nothing else is served.

## 4. Route DNS (creates the proxied CNAME) — DONE

Always pass `--config` so cloudflared uses the **samagra-os** tunnel (without it, it
loads the default `~/.cloudflared/config.yml` = the hermes tunnel, and routes wrong):

```bash
cloudflared tunnel --config deploy/cloudflared/config.samagra.yml route dns samagra-os samagra.bhautikiplusprashnavali.com
```

Until the tunnel is running this hostname returns Cloudflare Error 1016 (origin
down) — harmless. (To undo: delete the `samagra` CNAME in the zone's DNS.)

> 🧹 **Cleanup owed (D-8):** an initial mis-route (run without `--config`, against the
> pratyakshsims hostname) left a stray CNAME
> `samagra.pratyakshsims.com.bhautikiplusprashnavali.com` → the hermes tunnel. It is
> harmless (nobody resolves that FQDN; it does not affect `hermes.*` or the real
> samagra host) but should be **deleted in the Cloudflare DNS dashboard**
> (`cloudflared` has no `route dns delete`).

## 5. Cloudflare Access — REQUIRED before any public run (owner, dashboard) — DONE

In the **Zero Trust dashboard** (mirrors the existing `hermes.*` gate):

1. **Access → Applications → Add an application → Self-hosted.**
2. Application domain: `samagra.bhautikiplusprashnavali.com`.
3. Add a **policy**: Action **Allow**, Include → **Emails** → the owner's email
   (`dbhardwaj86@gmail.com`); login method **One-time PIN**.
4. Save. Verify (step 7): a logged-out request **302-redirects to the Access
   one-time-PIN login** (not straight to the app).

> **Defence-in-depth — DONE (W1.1).** The FastAPI origin now fails closed: an
> `http` middleware (`samagra/api/origin_auth.py`) gates the five mutating POSTs +
> the two admin-keyed live reads. **Loopback always passes** (local dev + the
> `cloudflared`-origin path, which connects from `127.0.0.1`), so legitimate
> Access traffic is unaffected; the gate blocks **non-loopback** direct hits
> (a `0.0.0.0` bind / LAN / internet exposure). A remote request must carry a
> verified Access identity. Configure it via env (`.env`):
>
> | env var | effect |
> |---|---|
> | `SAMAGRA_ACCESS_AUD` + `SAMAGRA_ACCESS_TEAM_DOMAIN` | **full** path: cryptographically validate `Cf-Access-Jwt-Assertion` (RS256) against the team JWKS (`https://<team>.cloudflareaccess.com/cdn-cgi/access/certs`) — set the Access app's AUD tag + team domain |
> | `SAMAGRA_OWNER_EMAIL` | **interim** (only when JWT vars unset): require `Cf-Access-Authenticated-User-Email == <owner>`. Spoofable by a direct caller, so it is a weaker stopgap — prefer the JWT vars |
> | `SAMAGRA_DISABLE_ORIGIN_AUTH=1` | dev escape hatch (disables the gate) |
>
> Because the legitimate tunnel terminates at loopback, this is **defence-in-depth
> behind Access, not a replacement** — Access stays the primary gate (§7 smoke
> test still load-bearing). Recommended to set the JWT vars in production.

## 6. Run the tunnel (the public step — owner-gated) — RUNNING

Only after step 5 is verified:

```bash
cloudflared tunnel --config deploy/cloudflared/config.samagra.yml run samagra-os
```

Leave it running (foreground / background process), or install as a persistent
service (step 8). A healthy run registers ~4 QUIC edge connections.

## 7. Smoke test (over TLS) — gate VERIFIED

- **Confirm the gate (load-bearing):** an unauthenticated request is blocked by
  Access — verified:

  ```bash
  curl -sS -D - -o /dev/null https://samagra.bhautikiplusprashnavali.com/api/overview
  # -> HTTP/1.1 302 Found
  # -> Location: https://jolly-sound-164b.cloudflareaccess.com/cdn-cgi/access/login/...
  # -> Www-Authenticate: Cloudflare-Access
  ```

  A `200` with API JSON here means the gate is OFF — **stop the tunnel immediately.**
- **Browser (owner):** load `https://samagra.bhautikiplusprashnavali.com` → Access
  OTP login → after auth the SAMAGRA OS desktop loads. Verify a few apps render
  (Dashboard, Questions, Munshi), both devices + a theme switch, and that `/api/*`
  is same-origin (no CORS).

## 8. Persistence + restart — DONE (logon Scheduled Task)

Durability is set up via a **logon Scheduled Task** (chosen over `cloudflared
service install`, which would hijack the hermes default `~/.cloudflared/config.yml`):

```powershell
& .\scripts\install-durable-task.ps1            # register (idempotent) the "SAMAGRA-OS" task
& .\scripts\install-durable-task.ps1 -Remove    # remove it
& .\scripts\serve-durable.ps1                   # bring it all up by hand any time
```

- The task runs **`scripts\serve-durable.ps1`** at logon: it brings the stack up
  (`serve-local.ps1`, reusing healthy servers + the built `dist`, so no npm is
  needed) and starts the `samagra-os` tunnel **detached** (survives the shell),
  idempotent, touching ONLY the samagra `--config`.
- **Scope:** user context, no stored password — so the URL is up **once the owner
  is logged in**, not at the pre-login lock screen. For 24/7 pre-login uptime, run
  cloudflared as a **Windows service** pointed at a copy of `config.samagra.yml`
  (separate from the hermes default service) instead of / in addition to the task.

## 9. Teardown

```bash
# stop the tunnel process (Ctrl-C, or stop the service)
# delete the samagra CNAME in the dashboard (and the D-8 junk record)
cloudflared tunnel delete samagra-os   # removes the tunnel (delete creds JSON after)
```

Also remove the Access application in the Zero Trust dashboard if retiring the host.

---

## Dependencies & notes

- **QX sidecar is a hard dependency for Questions.** It must run on `:8783`
  (`python -X utf8 gui/qx_browser.py` in `C:\SandBox\gpt_box\gpt-extract-ques`).
  If it's down, Questions degrades gracefully (banner) rather than erroring.
  Keep `:8783` internal — only `:8799` is tunnelled.
- **Same-origin in prod:** FastAPI serves `frontend/dist` + `/api` on `:8799`, so
  there is no CORS over the tunnel (the Vite dev proxy is dev-only).
- **Two math stacks (note):** the Questions app typesets with **KaTeX** (bundled),
  but the public `GET /lecture/{slug}` HTML hard-codes a **MathJax 3 CDN**
  (`samagra/lectures/render.py`). Over the tunnel that page loads MathJax from
  `cdn.jsdelivr.net`, so it loses equations **offline** or behind a strict
  `Content-Security-Policy` that disallows the CDN. Bundle MathJax (or render to
  KaTeX) if the lecture preview must work offline/under a tight CSP.
- **Never commit secrets:** `cert.pem`, `~/.cloudflared/<id>.json`, `.env`,
  `mcd-cloud.json` are all gitignored. Only the non-secret `config.samagra.yml`
  (tunnel UUID + ingress) is committed; a tunnel UUID is not a secret.
- **Legacy tunnels:** the account also has `bhautiki-prashnavali` (hermes, live),
  `mycontentdev-api`, `quizrag-demo`. `samagra-os` is independent and uses its own
  `--config`, so it never touches the default `~/.cloudflared/config.yml`.
