# SAMAGRA Content Factory — Phase G3: Multi-tenant identity + the outward publish write path (design)

> **Status:** ratified design (2026-06-28). Continues **Phase G** (PRATHAM / the A6
> downstream student entity), following **G1** (the publish boundary — `samagra/factory/publish/`
> + `samagra factory publish|unpublish|published`) and **G2** (the outward read surface +
> the `/learn` reader). Implements **Plan A–G row G** in full: *"multi-tenant identity +
> the single outward `POST /api/factory/publish`, Saar sheets first, batch-by-chapter
> approval."* Extends the umbrella content-factory spec
> `2026-06-23-samagra-content-factory-design.md` (§3 DOWNSTREAM, DEC-9) and consumes the
> G1 publish contract + the G2 read surface verbatim.
>
> **One-line:** give the system its **first inbound write paths** — an owner-gated
> `POST /api/factory/publish` (the GUI/network sibling of G1's CLI publish, behind the
> existing Cloudflare Access gate, still never-automated) **and** a lightweight
> **multi-tenant student identity** (owner-minted enrollment codes → opaque, revocable,
> server-side sessions in a *separate* durable `pratham.db`) that keeps `/learn` public
> and adds identity as an optional layer — **without** touching the inward factory, the
> seven source subsystems, or `governance.db`'s schema.

---

## 1. Context & goal

Phase G is the **DOWNSTREAM** layer (STEERING / ENGINE / MOAT / SEAM / DOWNSTREAM).
G1 made `published` a real, durable, owner-gated state (a manual CLI that copies captured
artifacts into an immutable `published/` snapshot). G2 opened the first **outward,
read-only, public-by-design** surface over that corpus (`GET /api/published` + the
separate full-page `/learn` reader) and ratified **DEC-11** (the outward read surface is
read-only/additive: no write path, no identity, no session).

**The gap this slice closes.** Two G-row capabilities remain unbuilt, and both were
explicitly deferred *to G3* by the G2 non-goals:
1. **The outward publish *write* path.** Today publishing is the inward manual CLI from
   G1 (`samagra factory publish`). Plan A–G row G names *"the single outward
   `POST /api/factory/publish`."* G2's non-goals: *"No outward `POST /api/factory/publish`
   (write path) → G3."*
2. **Multi-tenant identity.** G2's non-goals: *"No identity, login, session, cookie, or
   per-student state → G3."* A6's *"separate entity"* and DEC-9 (*"no … multi-tenant
   identity until Phase G"*) park the student account model here.

This is the system's **first inbound write surface**. Every phase to date was either
read-only outward (E coverage GET, G2 published GET) or a CLI-only / owner-Access-gated
write (the bridge, the factory `build()`, G1 publish). G3 introduces (a) the first
network-triggered *owner* write and (b) the first *public* (unauthenticated) write
(student login). The design's whole burden is to add those two boundaries **without
weakening any standing invariant** — the never-automated publish gate, the read-only
firewall over the seven subsystems, and the inward `build()` boundary + its five guards.

**Phase G sub-slice discipline** (mirroring 1→C→D→E→G1→G2): (G1) the publish boundary ✅,
(G2) the outward read surface + reader ✅, **(G3) multi-tenant identity + the outward
publish write path** ← this spec, (G4) the adaptive student twin (per-student learning
state).

## 2. Decisions locked (brainstorming forks, 2026-06-28)

| Fork | Decision | Rationale |
|---|---|---|
| Slice scope | **Both** — the owner publish write path **and** multi-tenant student identity in one slice | the owner ratified building row-G in full; the two boundaries are independent and isolatable, so they can ship together behind one boundary review |
| Access posture | **Identity optional — `/learn` stays public** (G2/DEC-11 preserved); login is a purely additive layer | the gate was already crossed at publish time (G2's reasoning); anonymous reading continues; a logged-in student gets a personalized shell that G4's per-student state hangs off. Lowest-friction; no need to protect `/api/published` |
| Auth mechanism | **Owner-minted enrollment codes → opaque server-side session** | lightest mechanism that is still genuinely multi-tenant; owner-driven (no open self-registration — mirrors the owner-gated, never-automated discipline); **no passwords**, no email infra, no third-party OAuth; needs **no new signing secret** (opaque sessions are authoritative + revocable). Cloudflare Access was rejected: it gates a path (can't do the "public overlay" posture) and would conflate owner-tier identity with student-tier |
| Identity store | **Separate durable `pratham.db`** (sibling of `governance.db`, gitignored, never reset) | clean inward(`governance.db`) / outward(`pratham.db`) firewall split; reinforces A6's "separate entity"; physically isolates the public-write path from inward governance; avoids growing the governance schema with downstream concerns |
| Per-student state scope | **Identity only in G3** — the account, the session, the signed-in shell; **no** learning state (progress / bookmarks / annotations / adaptive selection) | matches the phasing: G3 is the identity *substrate*, G4 is the *twin*. Keeps G3 a clean, reviewable identity slice |
| Publish surface | **`POST /api/factory/publish` + `POST /api/factory/unpublish` + a minimal operator-console publish control** | the endpoint's natural client is the owner's authenticated console; a thin GUI affordance completes G1 (CLI → GUI). The G1 CLI remains |

## 3. Architecture — two physically isolated write boundaries

```
  OWNER  (authenticated via Cloudflare Access)            STUDENT  (public /learn surface)
  ───────────────────────────────────────────            ─────────────────────────────────
  POST /api/factory/publish    ┐                          POST /api/learn/login {code} ┐
  POST /api/factory/unpublish  ┤  _PROTECTED_POSTS         POST /api/learn/logout        ┤  PUBLIC
                               │  (existing owner gate,    GET  /api/learn/me            ┘  (rate-limited,
                               │   origin_auth.enforce)                  │                    leak-free)
                               ▼                                         ▼
            samagra.factory.publish.run                      samagra/pratham/  ──▶  pratham.db
              .publish / .unpublish  (G1, reviewed)            (store + identity)     (students · sessions)
                               │                                         │            SEPARATE durable store,
                               ▼                                         ▼            gitignored, never reset
            governance.db events (`published`/`unpublished`)   opaque server-side sessions
            + published/ frozen copies   (G1 contract, UNCHANGED)        (hashed at rest, revocable)
```

**Firewall posture.** The two new write surfaces are **physically isolated by store**:

- **Publish** (`POST /api/factory/publish|unpublish`) is a thin HTTP adapter over the
  *already-shipped, already-Codex-reviewed* `publish.run.publish/unpublish` (G1). It writes
  **only** what G1 writes — `published/` frozen copies + append-only `governance.db`
  `published`/`unpublished` events. It adds **no new write mechanism**; it is the G1 CLI's
  contract reached over HTTP. It is **owner-gated** (added to
  `origin_auth._PROTECTED_POSTS`) and **never-automated** (a human owner action; no
  schedule, no auto-approve).
- **Student login** (`POST /api/learn/login|logout`, `GET /api/learn/me`) writes **only**
  `pratham.db` session rows. Because `pratham.db` is a **separate** durable store, even a
  worst-case bug in the *public* login path cannot touch `governance.db`, the inward
  `build()` boundary, `published/`, `EXPORT_DIR`, or any of the seven source subsystems.

Neither boundary can reach the other's store, the inward factory, or the read-only
subsystems. The inward `build()` boundary + its five crash-safety guards + the
never-automated publish gate are **untouched**. **No `governance.db` migration, no new
governance table, no catalog (`samagra.db`) change, no assignment-state-machine change.**

## 4. Data substrate (real inputs, verified)

| Input | Source (real API / path) | Shape used |
|---|---|---|
| Publish action | the request body `{chapter, lanes?}` → `publish.run.publish(chapter, lanes=lanes, actor="owner")` | returns G1's publish result dict (chapters × lanes × file count) |
| Unpublish action | `{chapter, lanes?}` → `publish.run.unpublish(...)` | G1's unpublish result dict |
| Publishable chapters (for the console control) | existing `GET /api/assignments` (captured `textbook:` seeds) + `GET /api/published` (current manifest) | the union: which chapters are captured-and-publishable, and which lanes are already published |
| Student credential | the request body `{code}` on `POST /api/learn/login` | a high-entropy enrollment code, hashed for lookup; never stored or logged in plaintext |
| Current student | the `pratham_session` cookie on any `/api/learn/*` request | hashed → `sessions` row lookup → student record (or none) |

**No new inward substrate.** The publish endpoints reuse the G1 contract verbatim; the
identity endpoints introduce a brand-new, self-contained store. There is no read of, or
write to, `governance.db`'s schema, the catalog, or the subsystems.

## 5. Backend — `samagra/pratham/` (new package) + endpoints

### 5.1 `samagra/pratham/store.py` (I/O — the `pratham.db` layout)

Opens/creates `config.PRATHAM_DB` and self-initializes its schema on first open (a
private `user_version` pragma + `CREATE TABLE IF NOT EXISTS`, mirroring the governance
store's idempotent open but **wholly independent** of `governance.db`). Two tables:

```sql
students (
  id            TEXT PRIMARY KEY,     -- e.g. stu_<hex>
  name          TEXT NOT NULL,
  code_hash     TEXT NOT NULL,        -- sha256(enrollment code); plaintext code never stored
  status        TEXT NOT NULL,        -- 'active' | 'revoked'
  created_at    TEXT NOT NULL,
  last_login_at TEXT                  -- updated on each successful login
)
sessions (
  id_hash    TEXT PRIMARY KEY,        -- sha256(session token); plaintext token never stored
  student_id TEXT NOT NULL REFERENCES students(id),
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL
)
```

The enrollment code is folded onto the student row (one active code per student) — no
separate enrollments table in G3; code rotation is a later nicety. `store.py` functions:
`create_student(name, code_hash) -> id`; `find_student_by_code_hash(code_hash) -> row|None`;
`set_status(id, status)`; `touch_login(id, at)`; `list_students()`; `create_session(id_hash,
student_id, created_at, expires_at)`; `find_session(id_hash) -> row|None`;
`delete_session(id_hash)`; `delete_sessions_for_student(id)`. **All bearer secrets are
stored hashed; nothing is ever logged or returned in plaintext beyond the one-time code
print at enrollment.**

### 5.2 `samagra/pratham/identity.py` (PURE — no I/O)

The testable core, no DB or network:

| Function | Responsibility |
|---|---|
| `new_code() -> str` | `secrets.token_urlsafe(_CODE_BYTES)` — high entropy (≥64 bits) so online/offline brute-force is infeasible regardless of rate limiting |
| `new_session_token() -> str` | `secrets.token_urlsafe(32)` — the opaque session id |
| `hash_secret(s) -> str` | `sha256` hex — used for both code and session-token hashing (the at-rest form) |
| `session_expiry(now, ttl_days) -> str` | compute `expires_at` |
| `is_expired(expires_at, now) -> bool` | session validity check |
| `redeem(student_row, now) -> "ok"\|"revoked"\|"invalid"` | the pure verdict given a looked-up student row (None → invalid; status revoked → revoked; else ok) |
| `RateLimiter` | a small in-process sliding-window counter keyed by a best-effort client key (see §8); `allow(key, now) -> bool` |

### 5.3 Endpoints in `samagra/api/app.py`

**Owner-gated** (added to `origin_auth._PROTECTED_POSTS` — they then inherit the exact
existing gate: loopback/cloudflared-origin passes, a remote caller needs a verified
Access identity, everything else 403):

```python
@app.post("/api/factory/publish")
def api_factory_publish(payload: dict):
    chapter, lanes = _parse_publish_body(payload)   # 400 on missing/bad chapter or non-str lanes
    from ..factory.publish import run
    try:
        return {"ok": True, "result": run.publish(chapter, lanes=lanes, actor="owner")}
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=409, detail=str(e))   # unknown chapter / nothing captured / mcd lane

@app.post("/api/factory/unpublish")
def api_factory_unpublish(payload: dict):
    chapter, lanes = _parse_publish_body(payload)
    from ..factory.publish import run
    try:
        return {"ok": True, "result": run.unpublish(chapter, lanes=lanes, actor="owner")}
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=409, detail=str(e))
```

**Public student** (deliberately NOT in `_PROTECTED_POSTS` — the `/learn` posture; the
cookie is the only credential):

```python
@app.post("/api/learn/login")
def api_learn_login(payload: dict, request: Request):
    code = (payload or {}).get("code")
    if not isinstance(code, str) or not code.strip():
        raise HTTPException(400, "code required")
    from ..pratham import service
    student = service.login(code.strip(), client_key=_rate_key(request))
    if student is None:                 # bad / revoked code OR rate-limited -> identical 401
        raise HTTPException(401, "invalid code")
    resp = JSONResponse({"student": {"id": student["id"], "name": student["name"]}})
    resp.set_cookie(_COOKIE, student["_session_token"], httponly=True,
                    samesite="lax", secure=config.PRATHAM_COOKIE_SECURE, path="/")
    return resp

@app.post("/api/learn/logout")
def api_learn_logout(request: Request):
    from ..pratham import service
    service.logout(request.cookies.get(_COOKIE))
    resp = JSONResponse({"ok": True}); resp.delete_cookie(_COOKIE, path="/"); return resp

@app.get("/api/learn/me")
def api_learn_me(request: Request):
    from ..pratham import service
    student = service.current_student(request.cookies.get(_COOKIE))
    return {"student": student}         # {id, name} or null
```

A thin `samagra/pratham/service.py` orchestrates `store` + `identity` (login = rate-check →
hash code → lookup → redeem verdict → on ok, mint+store session, `touch_login`, return
student + raw token; current_student = hash cookie → session lookup → expiry + student
status check; logout = delete session). Keeping the SDK-free orchestration in `service.py`
keeps the handlers trivial and the logic unit-testable.

### 5.4 Config additions (`samagra/config.py`)
- `PRATHAM_DB = REPO_ROOT / "pratham.db"` — durable, **gitignored**, documented "never
  reset" (the `GOVERNANCE_DB` precedent).
- `PRATHAM_COOKIE_SECURE: bool` — default `True` (prod behind the HTTPS tunnel); a
  documented dev escape for local http, alongside `SAMAGRA_DISABLE_ORIGIN_AUTH`.
- `PRATHAM_SESSION_TTL_DAYS` (default 30), `_CODE_BYTES`, cookie name — module constants.

### 5.5 CLI (`samagra/__main__.py`, new `samagra pratham …` subcommand)
- `samagra pratham enroll "<name>"` → `service.enroll(name)`: mint a code, create the
  student, **print the code once** (the only plaintext appearance).
- `samagra pratham students` → list (name, id, status, last login). Never prints codes.
- `samagra pratham revoke <id>` → set status revoked + delete the student's sessions.

## 6. Frontend

### 6.1 `/learn` reader — additive sign-in (extends G2's `<Pratham/>`)
- A **"Sign in"** control (enter your code) and, when signed in, a small shell header
  ("Signed in as <name>" + "Sign out"). Anonymous reading is **unchanged** — the corpus
  renders with or without a session.
- New PURE `frontend/src/lib/pratham/session.ts`: `loginRequest(code)`, `logoutRequest()`,
  `meRequest()` thin wrappers over the endpoints (reuse `useApiPost`/`useApi`); a
  `Student` type in `types/contracts.ts`.
- On mount, the reader calls `GET /api/learn/me` to hydrate the signed-in state; login/
  logout update it. No operator-shell imports (the G2 separate-entity boundary holds).

### 6.2 Operator console — a minimal **Publish** control
- A thin affordance (a small `Publish` operator app or a panel) that lists captured
  `textbook:` chapters with their current published lanes (joining `GET /api/assignments`
  + `GET /api/published`) and a **Publish / Unpublish** button per chapter (with an
  optional lane subset, "Saar sheets first") calling the owner-gated endpoints via
  `useApiPost`. Thin by design; the CLI remains the power path. Pure list/merge logic in
  `frontend/src/lib/publishctl/` (headless-tested); the component is a thin view.

## 7. Data flow & error handling

**Publish:** owner (through Access) → `POST /api/factory/publish {chapter, lanes?}` →
`origin_auth` passes (verified identity / loopback) → `run.publish` → `{ok, result}`;
unknown chapter / nothing captured / mcd lane / non-`textbook:` seed → G1's clean refusal
surfaced as **409**; bad body → **400**. The endpoint adds no logic beyond body parse +
delegation, so G1's guarantees (immutability, append-only, idempotent no-op, mcd-lane
exclusion) carry over verbatim.

**Login:** student at `/learn` → `POST /api/learn/login {code}` → rate-check →
hash+lookup+redeem → on ok set the `pratham_session` cookie + return `{student}`; bad/
revoked code **or** rate-limit → an **identical 401** (no oracle distinguishing "no such
code" / "revoked" / "throttled"). `GET /api/learn/me` with no/expired/invalid cookie →
`{student: null}` (never an error). Logout always 200. The public surface never reveals
whether a code exists, never logs a code, and writes nothing but a session row.

## 8. Security model (the heart of the boundary review)

- **Owner publish is the existing gate, reused.** Adding the two POSTs to
  `_PROTECTED_POSTS` means they inherit `origin_auth.enforce` exactly: loopback (the
  cloudflared-origin + local-dev path) passes; a remote caller must carry a verified
  `Cf-Access-Jwt-Assertion` (or, only until JWT is configured, the documented weaker
  owner-email header); else 403. No new auth code for the owner path.
- **The publish gate stays never-automated.** The endpoint requires an explicit per-call
  `{chapter, lanes?}` from an authenticated owner; there is no schedule, no batch-propose,
  no auto-approve. A GUI button pressed by the owner is exactly as manual as the CLI.
- **Codes are bearer credentials, treated as such.** High entropy (≥64 bits) makes
  guessing infeasible; stored only as `sha256` (a `pratham.db` leak exposes no usable
  code); compared by hashed-equality lookup; printed once at enrollment; never logged.
- **Sessions are opaque, revocable, hashed at rest.** A random 256-bit token, stored as
  `sha256`, in a `HttpOnly` + `SameSite=Lax` + `Secure` (prod) cookie scoped by a distinct
  name and honored only on `/api/learn/*`. Revoke (or logout) deletes the row → instant
  invalidation. No JWT, no signing secret to manage or rotate.
- **Rate-limiting is best-effort defense-in-depth, honestly bounded.** Behind cloudflared
  the origin's TCP peer is loopback, so a per-TCP-peer limit cannot distinguish remote
  callers; the limiter therefore keys on a best-effort `Cf-Connecting-IP` (a
  caller-controlled header — usable for *throttling* but, per `origin_auth`'s rule, NEVER
  to widen trust) plus a global ceiling. The **real** protection against code brute-force
  is the code entropy; the limiter only blunts volume. This limitation is documented, not
  hidden.
- **Physical store isolation is the firewall.** The public login write path can reach
  *only* `pratham.db`. It has no import of, or path to, `governance.db`, `publish.run`,
  the inward `build()`, `EXPORT_DIR`, or the seven subsystems. The two boundaries cannot
  cross-contaminate.
- **No new outward read exposure.** `/api/published` stays public + unchanged (DEC-11);
  identity adds no gating and no per-student read endpoint in G3.

## 9. Invariants & acceptance

**Proposed DEC-12 (to ratify in this spec + trackers): the outward write boundary +
multi-tenant identity.** The system gains its first inbound write paths under two
physically isolated, additively-stored boundaries:

- **Publish gate holds.** `POST /api/factory/publish|unpublish` is **owner-gated**
  (`_PROTECTED_POSTS` / Cloudflare Access) and **never-automated**, and delegates to the
  already-reviewed `publish.run` — adding **no new write mechanism** beyond the G1
  contract (`published/` + append-only `governance.db` events).
- **Identity is owner-enrolled, session-based, identity-optional.** No open
  self-registration (codes are owner-minted via CLI); sessions are opaque + revocable;
  `/learn` stays **public** (DEC-11 preserved); there is **no per-student learning state in
  G3** (→ G4).
- **Firewall by physical isolation.** Publish writes only `governance.db` events +
  `published/` (unchanged); student login writes only `pratham.db`. The seven subsystems,
  the inward `build()` + its five guards, the never-automated publish gate, and each
  store remain untouched. The public login write is bounded (redeem a pre-minted
  high-entropy code → one session row), rate-limited (best-effort), and leak-free.
- **`pratham.db` is durable + gitignored** (the `governance.db` precedent); **no
  `governance.db` migration, no new governance table, no catalog change, no
  assignment-state-machine change.**

**Acceptance (golden threads):**
1. **Publish over HTTP.** With a captured `textbook:<slug>` chapter, an authenticated
   (loopback in tests) `POST /api/factory/publish {chapter, lanes:["revision"]}` produces
   the same result as the G1 CLI — `published/<slug>/` gets the frozen Saar sheet, a
   `published` event is appended, the manifest lists it; the same call **unauthenticated
   from a non-loopback peer is 403**; an unknown chapter is **409**; `GET /api/published`
   then shows the chapter.
2. **Enroll → login → me → revoke.** `samagra pratham enroll "Asha"` prints a code and
   creates a student; `POST /api/learn/login {code}` sets the cookie + returns
   `{student:{name:"Asha"}}`; `GET /api/learn/me` with that cookie returns Asha; a wrong
   code returns an **identical 401**; `samagra pratham revoke <id>` then makes the prior
   cookie resolve to `{student:null}` (session invalidated).
3. **Isolation proven.** `governance.db` is **byte-unchanged** by any identity operation
   (all identity writes land in `pratham.db`); `/api/published` is **byte-unchanged** in
   behaviour by G3; the inward `build()` path is untouched.

## 10. Review gate

- **TDD throughout** (the standing discipline) — §11.
- **A dedicated DEC-7-style Codex pre-merge review of BOTH new write boundaries** —
  required: G3 introduces the system's **first inbound write paths** (owner publish) and
  its **first *public* write** (student login), matching the boundary reviews that gated
  Phase 1 (dispatch), C3 (seed-fold), D2 (LLM lane), and G1 (publish). The review
  confirms: publish is owner-gated + never-automated + a pure delegate to the reviewed
  `publish.run`; the student-login write is bounded to one `pratham.db` session row,
  leak-free, rate-limited, and structurally unable to reach `governance.db` / the inward
  factory / the subsystems.
- **An adversarial multi-lens final review** (Workflow, 4 lenses × independent verify), as
  every prior phase — lenses: the firewall (store isolation proven; no inward reach from
  the public path), security (no code/session leak; cookie flags; rate-limit honesty; the
  publish gate stays owner-only + never-automated), spec-fidelity, and the
  separate-entity boundary (no operator-shell leakage into `/learn`).

## 11. Testing strategy (TDD throughout)

- **`pratham/identity.py` (pure):** `new_code`/`new_session_token` entropy + uniqueness;
  `hash_secret` stability; `session_expiry`/`is_expired` boundaries; `redeem` verdicts
  (None→invalid, revoked→revoked, active→ok); `RateLimiter.allow` window behaviour.
- **`pratham/store.py` (I/O, tmp `PRATHAM_DB`):** schema self-init idempotent; create/find
  student by code hash; status set; session create/find/delete; delete-sessions-for-student;
  hashed-at-rest (no plaintext code/token persisted).
- **`pratham/service.py`:** enroll (mints + persists, returns plaintext code once); login
  (valid → session; wrong/revoked → None; rate-limited → None); current_student
  (valid/expired/revoked/absent cookie); logout (idempotent).
- **API (pytest, FastAPI TestClient):**
  - publish/unpublish: happy path (loopback) delegates to `run` + returns its result;
    **403 from a simulated non-loopback peer without identity** (mirrors the existing
    protected-POST tests); 409 on unknown chapter; 400 on bad body; assert they are in
    `_PROTECTED_POSTS`.
  - learn/login: sets a `HttpOnly`+`SameSite=Lax` cookie on a valid code; **identical 401**
    for wrong/revoked code; rate-limit returns 401 after the threshold; **reachable
    WITHOUT origin auth** (public — not gated).
  - learn/me: cookie present → student; absent/expired/revoked → `{student:null}`.
  - learn/logout: clears the cookie + invalidates the session.
  - **`/api/published` unchanged + still public** (regression).
- **`governance.db`-byte-unchanged** assertion across an enroll→login→revoke sequence
  (identity never touches it).
- **Frontend (vitest):** `lib/pratham/session.ts` wrappers; the reader's sign-in/sign-out
  state machine (mock `useApi`/`useApiPost`); anonymous reading still works with no
  session; `lib/publishctl/` list+merge of assignments × published; the Publish control
  view (mock post).
- Gate: **pytest green** (≈+30–40 over the current 562) and **vitest green** (≈+20–30), no
  regressions; the lone pre-existing `test_gdocs` env red and the opt-in live-LLM-smoke
  skip are unrelated.

## 12. Non-goals (Phase G3, YAGNI)

- **No per-student learning state** — progress, bookmarks, annotations, adaptive/
  personalized content selection over the coverage graph → **G4** (the twin).
- **No open self-registration** — students are owner-enrolled via CLI; there is no public
  "create account" write.
- **No passwords, no email/magic-link, no third-party OAuth** — the enrollment-code model
  is the whole auth surface; no SMTP, no Google OAuth client.
- **No gating of `/learn` or `/api/published`** — the public read posture (DEC-11) is
  preserved; identity is optional.
- **No new JWT / signing secret** — sessions are opaque server-side rows.
- **No `governance.db` migration, no new governance table, no catalog (`samagra.db`)
  change, no assignment-state-machine change, no change to the inward `build()` boundary
  or its five guards.**
- **No actual public-hostname / Access-bypass deploy** — code is deploy-ready; exposing
  `/learn` publicly remains the separate owner deploy step from G2.
- **No code rotation / self-serve password reset / roles beyond {owner, student}** — later
  nicety; G3 has exactly two tiers.

## 13. Open questions deferred (to the plan or a later G slice)

- **Session TTL + sliding vs fixed expiry** — defaulted to a fixed 30-day expiry
  (re-login via code); the plan may make it sliding.
- **Operator publish-control placement** — a dedicated small `Publish` app vs a panel in
  an existing app; defaulted to a thin dedicated control, finalized in the plan.
- **Rate-limit thresholds + key** — defaulted to a best-effort `Cf-Connecting-IP` + global
  ceiling (documented limitation behind the tunnel); tuned in the plan.
- **Per-student learning state + the adaptive twin** — **G4**.
- **Code rotation / re-enroll** — a later identity nicety, out of G3 scope.
