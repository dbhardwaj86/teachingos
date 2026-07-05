# SAMAGRA Content Factory — Phase G5: factory run over HTTP — Design

**Status:** PROPOSED 2026-07-06 by the Chairman ("factory run over HTTP" direction + two
forks ruled). The Chairman may still veto any individual ruling or ratify DEC-14 during
implementation; this spec is the implementer's contract until then.
**Author:** Claude (Fable 5), synthesizing the Chairman's ratified direction.
**Depends on:** G1 publish boundary (`samagra/factory/publish/` + `publish.run`) · G3
owner-gated `POST /api/factory/publish|unpublish` + the origin-auth gate
(`samagra/api/origin_auth.py`) + the operator **Publish** app · the factory dispatch
core (`samagra/factory/run.py` — `plan`/`approve_seed`/`build`) and lane registry
(`samagra/factory/lines.py`).
**Implements:** the Chairman-ratified "factory run over HTTP" slice — putting the
plan → approve-seed → build recipe on the console GUI, on-demand, beside the
already-shipped publish/unpublish GUI controls.

---

## §0 Goal

Give the Chairman a GUI way to run the **entire deterministic content-factory recipe**
for a textbook chapter — `plan → approve-seed → build (× N lanes) → publish` — from the
existing **Publish** app, without leaving the browser and without collapsing any
governance gate into a single click. Today this recipe is CLI-only
(`samagra factory plan|approve-seed|build`, `samagra factory publish`); G5 makes it a
button sequence on the console, reusing the CLI's own reviewed code paths verbatim. The
first real live throughput run (circular-motion, 5 lanes, published, student loop live)
was completed over the CLI earlier today — **G5 GUI-fies exactly that recipe**, no more
and no less.

## §1 Context

Phase G's arc so far: G1 made `published` a durable owner-gated state (CLI only). G2
opened the outward read surface + the `/learn` reader. G3 put the *publish/unpublish*
half of the recipe on the GUI (`POST /api/factory/publish|unpublish` + the **Publish**
app) and gave students identity. G4 closed the adaptive-twin loop. Every phase to date
that reaches *into* the factory — `plan`, `approve_seed`, `build` — has stayed CLI-only;
the Chairman has been running the actual content-production recipe by hand at a
terminal. G5 closes that gap: it does **not** touch `publish`/`unpublish` (G3 already
GUI-fied those) and does **not** touch identity, coverage, or StyleSeed — it is narrowly
the "run the factory" half of the recipe, mirrored onto HTTP with the same one-write-
mechanism, thin-delegate discipline every prior write boundary in this project has used
(Phase 1's `build()`, G1's `publish.run`, G3's `publish` POSTs).

**Why now, why this shape.** The Chairman ratified two forks up front (§2), closing the
open design questions before any code is written — the same discipline as G3's
brainstorming-forks table and G4's judge-directive fork table. The result is three new
origin-gated POSTs, each a thin delegate to already-reviewed `samagra/factory/run.py`
functions, plus a frontend stepper panel appended to the existing Publish app. **No new
app, no new write mechanism, no new prod-write path** — this is the CLI's own contract,
reached over HTTP, exactly as G3's publish endpoints were the CLI's `factory publish`
contract reached over HTTP.

**Phase G sub-slice discipline** (mirroring G1→G2→G3→G4): (G1) the publish boundary ✅,
(G2) the outward read surface + reader ✅, (G3) multi-tenant identity + the outward
publish write path ✅, (G4) the adaptive student twin ✅, **(G5) factory run over
HTTP** ← this spec.

## §2 Forks ruled (Chairman, 2026-07-06)

| # | Fork | Ruling |
|---|------|--------|
| F-G5-1 | GUI placement | **Extend the existing Publish app** with a "Factory run" stepper panel — **not** a new app. The Publish app already owns the operator's release-management surface (chapter list, captured/published lanes, publish/unpublish buttons); the factory-run recipe is the upstream half of the same workflow and belongs beside it, not in a 20th app. |
| F-G5-2 | Gate granularity | **Per-gate buttons.** Each governance gate — Plan, Approve seed, Build (all lanes), Publish — stays its own explicit click. "Build all" is a **client-side convenience loop** over the approved assignments (the frontend calls `POST /api/factory/build` once per assignment_id in sequence; the server has no batch-build endpoint) — it is UX sugar over N single-assignment gates, not a new server-side batch primitive. Approve and Publish **never** collapse into one click with Plan or Build — the never-automated publish gate stays exactly as manual as the CLI, just reachable from a browser. |
| F-G5-3 | Lane reachability over HTTP | (Corollary of F-G5-2, pinned explicitly because it is the boundary's one refusal rule.) `POST /api/factory/build` **structurally refuses** (403) any assignment whose lane `kind` is `"llm"` or `"mcd"`. Samadhan (`kind="llm"`) needs an API key + incurs real generation cost and stays an explicit CLI-only action (`factory plan --lane samadhan` then `factory build`); the `seed` lane (`kind="mcd"`) is the **one production write path** in the whole system (the C3 bridge-fold) and must keep **zero** HTTP triggers — this is a structural invariant, not a policy the frontend merely chooses not to exercise. |

## §3 Architecture

```
Chairman (Publish app, /  console — origin-gated, Cloudflare Access)
   │
   │  1) chapter slug ──────► POST /api/factory/plan       {seed_ref}
   │  2) per-gate clicks ───► POST /api/factory/approve-seed {seed_ref}
   │  3) build-all loop ────► POST /api/factory/build      {assignment_id}  (×N, client sequenced)
   │  4) publish (G3, reused, unchanged) ─► POST /api/factory/publish {chapter, lanes?}
   ▼
samagra/api/app.py  (origin_auth._PROTECTED_POSTS — the existing owner gate, reused)
   │  thin delegates, no new write mechanism
   ▼
samagra/factory/run.py   .plan(seed_ref, dry=False)  →  .approve_seed(seed_ref)  →  .build(assignment_id)
   │  (ALREADY REVIEWED: Phase 1 DEC-7 Codex 24/25, Phase C1-C3, D2 review gates)
   ▼
governance.db (assignments + append-only events)  +  EXPORT_DIR local artifacts
```

- The **write path never gains a new mechanism.** `plan`/`approve_seed`/`build` are the
  exact functions the CLI (`samagra/__main__.py:cmd_factory`) already calls; the three
  new endpoints are argument-parsing + error-mapping wrappers, the same shape as G3's
  `api_factory_publish`/`api_factory_unpublish`.
- The **frontend never talks to governance.db or the factory directly.** It only calls
  the three new POSTs plus the existing `GET /api/assignments` (already origin-gated,
  already read by the Publish app) to derive stepper state.
- The **llm/mcd refusal lives in the endpoint**, keyed off `samagra/factory/lines.LINES[
  assignment.pipeline].kind` — not in the frontend. A frontend bug, a stale build, or a
  hand-crafted request all hit the same 403; the frontend's own button-disabling is
  belt-and-suspenders UX, never the actual boundary.

## §4 Backend — three new endpoints in `samagra/api/app.py`

All three are added to `origin_auth._PROTECTED_POSTS` (currently 6 entries — `/api/refresh`,
`/api/tick`, `/api/munshi/capture`, `/api/mcd/seeds`, `/api/factory/publish`,
`/api/factory/unpublish` — growing to 9) and therefore inherit `origin_auth.enforce`
verbatim: loopback (the cloudflared-origin path) passes; a remote caller needs a
verified Cloudflare Access identity; everything else is 403. No new auth code.

### §4.1 `POST /api/factory/plan`

- **Body:** `{seed_ref: str}`.
- **v1 scope guard:** `seed_ref` must start with `"textbook:"` — **400** otherwise. This
  is deliberate: `munshi:`-prefixed seeds (the mcd `scan`/`plan` path) and any explicit
  `--lane samadhan`/`--lane seed` targeting stay CLI-only in v1 (see §12 non-goals); the
  GUI only ever drives the deterministic 5-lane textbook fan-out
  (`revision/lecture/deck/paper/drill` — `classify()`'s default auto-fan set, per
  `samagra/factory/lines.py:45`).
- **Delegates:** `run.plan(seed_ref, dry=False)` (verified signature:
  `run.plan(seed_ref: str, dry: bool = True, lane: str | None = None) -> list[dict]`,
  `samagra/factory/run.py:147`) — `dry=False` so it actually records the in-review child
  assignments + outbox files + `product_proposed` events (the CLI's live-mode
  behaviour); `lane` is omitted (`None`), so `classify()` drives the default fan-out —
  the GUI never targets a single lane.
- **Response:** `{"proposals": [...]}`, the list `run.plan` returns verbatim — dicts
  shaped `{seed_ref, line, expected_output, pointers, assignment_id, reused?}` (per the
  CLI's own rendering at `samagra/__main__.py:142-150`, which prints
  `p['assignment_id']`, `p['line']`, `p['expected_output']`, and an optional `reused`
  tag from the identical dicts).
- **Error mapping:** a malformed body (`seed_ref` missing/not a string/empty) → **400**.
  `run.plan` itself does not raise ValueError for a well-formed `textbook:` ref in the
  default (non-lane-targeted) branch (per `run.py:184-227`, the `mcd`-kind lane is
  silently skipped, not raised) — so no 409 branch is expected here for the v1 prefix;
  if a future defensive `ValueError` were added upstream it would still map to 409 for
  consistency with §4.2/§4.3 (see the plan's Task 2 for the exact test matrix).

### §4.2 `POST /api/factory/approve-seed`

- **Body:** `{seed_ref: str}`; same `textbook:` prefix guard → **400** otherwise (v1
  scope; consistent with §4.1 — the GUI drives one recipe end-to-end, not arbitrary
  seed refs).
- **Delegates:** `run.approve_seed(seed_ref)` (verified signature: `run.approve_seed(
  seed_ref: str) -> dict`, `samagra/factory/run.py:257`) — the **per-seed batch gate**
  (fork 3 from Phase 1): flips every `in-review` child of this seed to `approved` in one
  explicit action. This is the CLI's `factory approve-seed` verbatim, matching the
  Chairman's F-G5-2 ruling that Approve stays its own explicit click, distinct from Plan
  and from Build.
- **Response:** the dict `run.approve_seed` returns verbatim —
  `{"seed_ref": ..., "approved": [assignment_id, ...]}` (per `run.py:257-270` and the
  CLI's own rendering at `__main__.py:154-156`, which reads `res['approved']`).
- **Error mapping:** malformed body → **400**. `approve_seed` itself never raises (it
  filters `store.list_assignments` in a loop and is a no-op — `{"approved": []}` — for a
  seed with no in-review children); there is no 409 branch for this endpoint in v1.

### §4.3 `POST /api/factory/build`

- **Body:** `{assignment_id: str}`.
- **Lookup + kind check BEFORE delegating** (the one place this endpoint does more than
  parse-and-delegate, per F-G5-3): load the assignment via
  `samagra.governance.store.list_assignments`/an equivalent lookup, resolve
  `samagra.factory.lines.LINES[assignment["pipeline"]].kind`, and:
  - unknown `assignment_id` → **404**;
  - `pipeline` not a key in `LINES` at all → **404** (the same "not a factory lane"
    condition `run.build` itself would raise as a `ValueError` — surfaced as 404 here
    because there is nothing meaningful to build for an assignment `build()` doesn't
    even recognize as its own; contrast with §4.3's 409 branch below, which is for a
    *recognized* lane in the wrong state);
  - `LINES[pipeline].kind in {"llm", "mcd"}` → **403**, structurally, before `run.build`
    is ever called — Samadhan (key + cost) and the mcd seed lane (the ONE prod write)
    are refused at the HTTP boundary itself, never reaching `dispatch.run_seed` or
    `samadhan.preflight`. This is the load-bearing rule in this spec: **the one
    production-write path (the mcd `seed` lane, C3's bridge-fold) keeps zero HTTP
    triggers**, full stop.
- **Delegates (only past the kind check):** `run.build(assignment_id)` (verified
  signature: `run.build(assignment_id: str) -> dict`, `samagra/factory/run.py:355`) —
  the ONE guarded write boundary, its five crash-safety guards untouched (workflow
  firewall, status=='approved', not-already-built, no in-flight build, kind-aware
  produce/validate). This inherits every guard `run.build` already has; the endpoint
  adds no new safety logic beyond the pre-delegation kind refusal above.
- **Response:** `{"line": ..., "artifact_ref": ...}` — the fields the CLI itself prints
  (`__main__.py:157-159`: `res['line']`, `res['artifact_ref']`); `run.build` also returns
  `assignment_id` and `status`, both passed through unfiltered (the response is the dict
  verbatim, a superset of the two named fields).
- **Error mapping:** `run.build` raises `ValueError` for every one of its five guards
  (unknown assignment, not a factory lane, wrong status, already-built, in-flight
  build) and for a `qx`-kind lane's `validate_seed_for_line` precheck failure — all of
  these map to **409** (a conflict with the assignment's current governance state, never
  a 500); a malformed body (`assignment_id` missing/not a string/empty) → **400**. Note
  the endpoint's own pre-delegation 404 (unknown assignment / unrecognized pipeline) and
  403 (llm/mcd kind) happen **before** `run.build` is called, so those two assignment
  states never reach `run.build`'s own `ValueError`s for "unknown assignment" / "not a
  factory lane" — the endpoint's guard is simply first in line.

### §4.4 GET side — nothing new

The Publish app already fetches `GET /api/assignments` (origin-gated, unchanged) to
derive its captured/published rows; the new stepper panel reuses that same fetch — no
new GET endpoint, no new origin-gated read surface.

## §5 Frontend — the "Factory run" stepper panel

Extends `frontend/src/apps/Publish/` (F-G5-1) — no new app, no registry change, no new
`AppId` entry.

### §5.1 `frontend/src/lib/publishctl/recipe.ts` (new, PURE)

Mirrors the existing `frontend/src/lib/publishctl/rows.ts` convention (pure functions,
headless-tested, no fetch/React inside the derivation logic):

- **`deriveStep(assignmentsForChapter: AssignmentLike[]) -> RecipeStep`** — given the
  subset of `/api/assignments` rows whose `seed_ref === "textbook:<slug>"`, derive which
  single next action is enabled:
  - no rows for this seed_ref at all → `"plan"` (nothing proposed yet).
  - some rows exist and at least one is `status === "in-review"` → `"approve"` (a batch
    is proposed but not yet board-approved).
  - at least one row is `status === "approved"` (none left `"in-review"`) → `"build"`
    (something is approved and awaiting a build click).
  - all rows for the deterministic lane set are terminal `"captured"` (or `"changes"` —
    treated as build-not-applicable, since the GUI only drives the 5 deterministic
    local/qx lanes, which never land in `"changes"` — that status is llm-only) → `
    "publish"` (everything buildable is built; hand off to the existing Publish
    button — this state is a no-op for the NEW stepper panel, since publish is G3's
    already-shipped control).
  - **`"done"`** is not a distinct derived state in v1 — once lanes are captured, control
    passes to the existing per-chapter Publish/Unpublish row (F-G5-1: the two controls
    sit side by side in one panel, not fused).
- **`nextAssignmentToBuild(assignmentsForChapter) -> string | null`** — the first
  `status === "approved"` row's `assignment_id` (deterministic order: sort by
  `pipeline` per the `_ORDER` in `samagra/factory/lines.py:45`, so a re-render always
  proposes the same next build target) — used by the client-side build-all loop.
- **Typed fetch wrappers** (mirroring `rows.ts`'s sibling module boundary — pure
  derivation stays here, wrappers are the thin I/O edge, same file per the existing
  `publishctl` convention of colocating both in one small lib):
  `planRequest(seedRef)`, `approveSeedRequest(seedRef)`, `buildRequest(assignmentId)` —
  each a `useApiPost`-shaped async function returning the parsed JSON or `null`/throwing
  the server's `detail` message on a non-2xx (mirroring `useApiPost`'s existing
  `res.json().detail` unwrap convention, `frontend/src/hooks/useApiPost.ts:14-16`).

### §5.2 Publish app — the new panel

A "Factory run" section, added to `frontend/src/apps/Publish/index.tsx` above or beside
the existing captured/published table (F-G5-1: same app, same file, additive JSX):

- a **chapter-slug text input** (`data-testid="factory-run-slug"`) — the Chairman types
  e.g. `circular-motion` (no `textbook:` prefix in the input; the panel prepends it when
  calling the endpoints, mirroring how the CLI's own `--lane` help text and the Publish
  app's existing `r.chapter` rows both use the bare slug);
- **4 per-gate buttons** (F-G5-2, never collapsed): **Plan** → `POST
  /api/factory/plan {seed_ref: "textbook:"+slug}`; **Approve seed** → `POST
  /api/factory/approve-seed {seed_ref}`; **Build all** → the client-side loop (§5.1's
  `nextAssignmentToBuild`, called repeatedly against a refetched assignment list until it
  returns `null` or a call fails); **Publish** → reuses the **existing** G3
  `act("/api/factory/publish", chapter)` handler already in the Publish app (no new
  publish code — the stepper panel's Publish button is literally the same handler the
  per-row Publish button already calls, just also reachable from the stepper);
  each button **enabled only when `deriveStep` says it is this button's turn** (disabled
  otherwise — belt-and-suspenders; the real guard is server-side per §4);
- **inline per-step result/error lines** (`data-testid="factory-run-result"` /
  `"factory-run-error"`) under the button row — the raw `{proposals: [...]}` /
  `{approved: [...]}` / per-build `{line, artifact_ref}` summarized as short text (e.g.
  `"planned 5 lane(s)"`, `"approved 5"`, `"built 3/5 (paper failed: ...)"` if the build-
  all loop hits a 409/403 partway through — the loop stops on first failure and surfaces
  which assignment failed, it never silently skips);
- a **refetch of `GET /api/assignments`** after every action (the existing `nonce`-bump
  pattern already in the Publish app, `frontend/src/apps/Publish/index.tsx:12-24`) so the
  stepper's derived state and the existing captured/published table both stay live.

## §6 Stepper states (summary table)

| Derived state | Trigger | Button enabled | Server call |
|---|---|---|---|
| `plan` | no assignments for `textbook:<slug>` | **Plan** | `POST /api/factory/plan` |
| `approve` | ≥1 row `in-review` | **Approve seed** | `POST /api/factory/approve-seed` |
| `build` | ≥1 row `approved`, none `in-review` | **Build all** | `POST /api/factory/build` ×N (client loop) |
| `publish` | all deterministic-lane rows `captured` | **Publish** (existing G3 control) | `POST /api/factory/publish` (unchanged) |

Exactly one button is enabled at a time (F-G5-2's per-gate discipline expressed as UI
state) — the stepper never offers two simultaneously-actionable gates, even though a
determined caller could still hit any of the three new endpoints directly (the server-
side state checks in `run.approve_seed`/`run.build` are the real enforcement, not the
disabled attribute).

## §7 Golden threads (acceptance)

1. **HTTP recipe ≡ CLI result.** With a fresh `textbook:circular-motion` seed and a real
   (or realistically monkeypatched) lane engine: `POST /api/factory/plan` →
   `POST /api/factory/approve-seed` → `POST /api/factory/build` (once per proposed
   assignment) → `POST /api/factory/publish` produces the **same** `governance.db`
   assignment/event trail and the **same** `published/` artifacts that the equivalent
   CLI sequence (`factory plan --dry-run=false`, `factory approve-seed`, `factory
   build` ×N, `factory publish`) already produces — proven by a `TestClient`-driven
   golden test that walks the HTTP sequence end to end on a monkeypatched-temp world
   (mirrors `tests/test_g3_golden.py`'s pattern of `monkeypatch`-ing `GOVERNANCE_DB`/
   `EXPORT_DIR`/`PUBLISHED_DIR` to a `tmp_path`).
2. **llm/mcd structurally unreachable.** `POST /api/factory/build` against an assignment
   whose `pipeline == "samadhan"` (kind `llm`) or `"seed"` (kind `mcd`) → **403**, and
   `dispatch.run_seed`/`samadhan.generate_samadhan` are never invoked (asserted via a
   monkeypatch spy that must show zero calls) — pinning F-G5-3 as a structural, not
   merely policy, refusal.
3. **Origin gating holds.** All three new POSTs are members of
   `origin_auth._PROTECTED_POSTS` (`is_protected("POST", "/api/factory/plan") is True`,
   etc. — the exact assertion shape `tests/test_api_factory_publish.py` already uses for
   the G3 pair) and a simulated non-loopback, non-authenticated caller gets **403** on
   all three, mirroring `test_remote_publish_without_identity_is_403`.
4. **Student surface untouched.** `/learn`, `/api/learn/*` (login/logout/me/progress/
   next), and `/api/published*` are byte-identical across a full G5 recipe run — no new
   testid, no new fetch call, no response diff (mirrors G4's frozen anonymous-invariance
   baseline and golden-thread isolation assertions).

## §8 Security model

- **The existing owner gate, reused — no new auth code.** All three POSTs join
  `_PROTECTED_POSTS`; they inherit `origin_auth.enforce` verbatim (loopback passes; a
  remote caller needs a verified Access identity; else 403). This is the identical
  mechanism G3's publish endpoints already use — G5 adds table entries, not gate logic.
- **The never-automated publish gate is unchanged.** Nothing about G5 makes any gate
  fire without an explicit owner click. `build-all` is a *client* loop that still calls
  the single-assignment `POST /api/factory/build` once per approved row — there is no
  server-side "build everything approved for this seed" endpoint, so a future scripted
  caller cannot batch-build with one request; each build is independently gated by
  `run.build`'s five guards and independently audited (`product_building` →
  `product_created` events per assignment, unchanged).
- **The one production-write path keeps zero HTTP triggers.** `POST /api/factory/build`'s
  kind check (§4.3) refuses `kind in {"llm","mcd"}` **before** any factory code runs —
  the mcd `seed` lane (the system's one write to the external mycontentdev system,
  C3's bridge-fold) remains reachable **only** via `samagra factory build` at a terminal,
  exactly as before G5. The llm `samadhan` lane (API key + real generation cost) is the
  same: CLI-only. This refusal is keyed on `LINES[pipeline].kind`, a property of the lane
  registry itself, not a per-request allowlist that could drift — adding a new lane kind
  in a future phase must deliberately widen this check, it cannot silently stay open.
- **No new write mechanism.** Every new endpoint's write is a call into
  `samagra/factory/run.py` functions the CLI, and prior Codex reviews (Phase 1's 24/25,
  the D2/C3 boundary reviews), already exercised and passed. G5 introduces zero new
  logic inside `run.plan`/`run.approve_seed`/`run.build` — only HTTP-shaped call sites.
- **Student surface is untouched by construction.** None of the three new endpoints, nor
  the frontend changes, touch `samagra/pratham/`, `pratham.db`, `/api/learn/*`, or
  `/api/published*`. The Publish app already lives entirely on the operator side of the
  G2/G3 separate-entity boundary; extending it with a stepper panel does not cross that
  boundary.
- **No new secrets, no LLM, no network egress** beyond what `run.build`'s existing `qx`-
  kind lanes already perform (the read-only QX `/api/qsearch` calls, unchanged).

## §9 Invariants — proposed DEC-14

1. **No new write mechanism.** Every one of the three new endpoints is a thin delegate
   to already-reviewed `samagra/factory/run.py` code — `plan`/`approve_seed`/`build`
   gain zero new logic; only HTTP argument-parsing + error-mapping wrappers are added.
2. **The never-automated publish gate is unchanged.** The GUI adds a **second owner
   trigger** beside the CLI (the G3 precedent for publish/unpublish, now extended to
   plan/approve/build) — every governance gate stays an explicit, separately-clicked
   owner action (F-G5-2); `build-all` is client-side UX sugar over N single-assignment
   calls, never a new server-side batch-write primitive.
3. **The llm (`samadhan`) and mcd (`seed`) lanes are structurally unreachable over
   HTTP.** `POST /api/factory/build` refuses `kind in {"llm","mcd"}` with 403 before
   calling `run.build` — the one production-write path (the mcd seed lane) keeps **zero**
   HTTP triggers, full stop. This is enforced by the `LINES` registry's `kind` field, not
   a maintained allowlist.
4. **All three POSTs are origin-gated** (`origin_auth._PROTECTED_POSTS`, inheriting the
   Cloudflare Access + loopback rule verbatim) — never public-prefix, never reachable
   without the same owner identity the publish endpoints already require.
5. **The student surface is untouched.** `/learn`, `/api/learn/*`, and `/api/published*`
   carry zero diffs from this slice — G5 is wholly an operator-side (Publish app)
   change.
6. **No migration, no governance schema change.** `governance.db`'s tables, columns, and
   assignment-state-machine are identical before and after G5; the new endpoints only
   ever call existing `store`/`run` functions that already write to that schema.

## §10 Review gate (before merge)

Per the DEC-7 pattern applied to every prior write boundary (Phase 1, C3, D2, G1, G3,
G4): (1) a **dedicated Codex pre-merge review** of the three new endpoints — particularly
the llm/mcd kind-refusal boundary (§4.3, §8) and the origin-gating additions — report
saved under `docs/codex-reviews/30-g5-factory-run-http-premerge.report.md`; (2) an
**adversarial multi-lens final review** (Workflow, 4 lenses × independent refute-verify):
firewall/write-mechanism (no new logic in `run.py`; llm/mcd structurally unreachable) ·
security (origin gating verbatim; no privilege widening) · spec-fidelity (§2 forks + §7
golden threads) · separate-entity (student surface untouched, Publish-app-only frontend
change); (3) remediate findings TDD, re-run the full gate, `merge --ff-only`, push.

## §11 Testing strategy

TDD throughout (red first, every task), mirroring the G3/G4 discipline. Backend:
endpoint tests for each of the three new POSTs — `is_protected` membership (mirrors
`test_publish_endpoints_are_in_protected_posts`), 403-without-identity (mirrors
`test_remote_publish_without_identity_is_403`), 400 on malformed body, the delegation-
with-monkeypatched-`run`-function pattern (mirrors `test_publish_delegates_to_run`),
409-on-`ValueError`-from-`run` for build, and the dedicated llm/mcd 403 kind-refusal
tests for build (constructing or monkeypatching an assignment with `pipeline in
{"samadhan","seed"}`). The §7 golden thread as its own test module (mirrors
`tests/test_g3_golden.py`/`tests/test_g4_golden.py`), including the `/api/learn/*` +
`/api/published` untouched assertions. Frontend: `recipe.ts` table-driven pure-function
tests (every `deriveStep` transition, `nextAssignmentToBuild` ordering) with a fake
`fetch`; the stepper panel rendered with mocked endpoints, one test per button-enabled
state, one test for the build-all loop (including a mid-loop failure surfacing the right
error text), one regression proving the existing Publish/Unpublish row and its tests are
unaffected. Full gate: pytest + vitest + tsc + build, against the 637 pytest (1 skip) /
613 vitest / tsc+build-green baseline this plan inherits from G4.

## §12 Non-goals (v1)

- **No `scan`/`munshi:` seeds over HTTP.** The mcd-lane discovery loop
  (`samagra factory scan`) and any `munshi:`-prefixed `plan`/`approve-seed` targeting
  stay CLI-only — the `textbook:` prefix guard in §4.1/§4.2 is load-bearing, not
  incidental.
- **No `reopen` over HTTP.** The `changes`→`in-review` regenerate loop
  (`samagra factory reopen <aid>`) is not exposed; a `changes`-status brief (llm-lane
  only, and llm lanes are unreachable via `build` anyway per F-G5-3) stays a CLI-only
  fix-up path.
- **No one-click end-to-end.** There is no server-side "run the whole recipe for this
  chapter" endpoint. Each gate is its own click, per F-G5-2; a future "one-click" mode
  would be a distinct phase with its own decision + review, not a silent upgrade of
  `build-all`'s client loop into a server batch primitive.
- **No new app.** The stepper panel lives inside the existing Publish app (F-G5-1); no
  registry entry, no new `AppId`, no new icon.
- **No enroll/revoke or any `pratham` identity action over HTTP.** Student enrollment
  stays the G3 CLI-only path (`samagra pratham enroll|students|revoke`); G5 does not
  touch `samagra/pratham/`.
- **No change to `LINES`, `classify()`, or any lane engine.** G5 is purely a new way to
  *trigger* the existing recipe, not a new lane or a change to which lanes exist or how
  they render.
- **No coverage-graph or StyleSeed changes.** Phase E and Phase D machinery are
  untouched; the stepper panel does not read `concept_graph.db` or `styleseed/*.json`.

## §13 Open questions (owner)

1. Should the "Build all" client loop stop on the **first** failed build (as specified
   in §5.2) or attempt all remaining approved assignments and report a summary of
   successes/failures? Defaulted to fail-fast (simpler, matches the CLI's own behaviour
   of one command per build) — revisit after the first GUI-driven multi-lane run.
2. Should the chapter-slug input auto-suggest from `GET /api/assignments`'s existing
   `textbook:` seed refs, or stay a free-text field? Defaulted to free-text for v1
   (lowest implementation cost); a datalist/autocomplete is a cosmetic v1.1 follow-up.
3. Whether a future "one-click end-to-end" convenience mode is ever wanted is explicitly
   deferred (§12) — out of scope until the Chairman asks for it, and would need its own
   fork ruling given F-G5-2's "gates never collapse" ruling.
