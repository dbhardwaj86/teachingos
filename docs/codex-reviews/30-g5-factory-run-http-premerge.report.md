# DEC-7 pre-merge review: Phase G5 factory-run HTTP write boundary

Date: 2026-07-06
Repo: `C:/SandBox/claude_box/TeachingOS`
Branch/head reviewed: `feature/factory-run-http` at `da820c0f6fcc528fbe870536462ad2fc95bd5094`
Base stated by review request: `main` at `5be40ed699fbe8c01b8c347d0ed7fc5c5a6d742f`
Review range: `5be40ed..da820c0` (12 commits)
Scope: Phase G5's new factory-run HTTP write surface: `POST /api/factory/plan`, `POST /api/factory/approve-seed`, `POST /api/factory/build`, their `origin_auth` registration, delegation to `samagra/factory/run.py`, the `samagra/factory/lines.py` lane-kind boundary, relevant governance read paths, focused backend/golden tests, and the Publish app stepper plus `frontend/src/lib/publishctl/recipe.ts`. I also checked the stated spec at `docs/superpowers/specs/2026-07-06-samagra-content-factory-phase-g5-factory-run-http-design.md`.

## Verdict

GO.

I found no HIGH, MEDIUM, or LOW correctness/security findings in the reviewed G5 write boundary. The load-bearing llm/mcd refusal is implemented in `api_factory_build` before `run.build` is imported/called; the three new POSTs are exact members of `_PROTECTED_POSTS`; the handlers add only body parsing, the textbook scope guard, the kind pre-check, a process-local serialization lock, and error mapping around the already-reviewed `samagra/factory/run.py` functions. The frontend stepper calls the same three backend endpoints and reuses the existing G3 publish handler rather than adding a second publish path.

## Scope

Files inspected with line-level evidence:
- `samagra/api/app.py`
- `samagra/api/origin_auth.py`
- `samagra/factory/run.py`
- `samagra/factory/lines.py`
- `samagra/governance/store.py`
- `frontend/src/lib/publishctl/recipe.ts`
- `frontend/src/apps/Publish/index.tsx`
- `frontend/src/lib/publishctl/recipe.test.ts`
- `frontend/src/apps/Publish/index.test.tsx`
- `tests/test_api_factory_plan.py`
- `tests/test_api_factory_approve_seed.py`
- `tests/test_api_factory_build.py`
- `tests/test_g5_golden.py`
- `tests/test_origin_auth.py`
- `docs/superpowers/specs/2026-07-06-samagra-content-factory-phase-g5-factory-run-http-design.md`

Worktree note: before this report, the branch already had unrelated dirty items: `AGENTS.md` modified and untracked `samagra_overhaul.html`. I did not modify them.

## Findings

### HIGH

None.

### MEDIUM

None.

### LOW

None.

## Boundary Review Notes

### llm/mcd kind-refusal boundary

PASS. `api_factory_build` validates `assignment_id` first at `samagra/api/app.py:354-357`, then loads the assignment through governance before any delegate import at `samagra/api/app.py:359-368`. Unknown assignments return 404 at `samagra/api/app.py:369-370`; unrecognized pipelines return 404 at `samagra/api/app.py:371-373`; and `kind in ("llm", "mcd")` returns 403 at `samagra/api/app.py:374-378`. Only after those checks does the handler import `factory_run` and enter `_FACTORY_RUN_LOCK` to call `factory_run.build(assignment_id)` at `samagra/api/app.py:380-384`.

The lane registry maps `seed` to kind `"mcd"` and `samadhan` to kind `"llm"` at `samagra/factory/lines.py:36-41`. The reviewed delegate still supports those kinds for CLI use: `run.build` dispatches mcd through `dispatch.run_seed` at `samagra/factory/run.py:385-415` and llm through `samadhan.preflight` plus the normal local artifact path at `samagra/factory/run.py:402-420`. Because the HTTP check happens before `run.build`, those branches are structurally unreachable over HTTP.

TOCTOU assessment: the kind lookup and delegate call are not in one database transaction, but I did not find a reachable HTTP or normal factory API path that can change an existing assignment's `pipeline` between those two steps. The new HTTP routes can add assignments via `plan`, approve statuses via `approve-seed`, or build by id; none updates `pipeline`. The cross-process CLI race remains the accepted single-operator threat model described in the route comments at `samagra/api/app.py:291-298`.

Coverage: `tests/test_api_factory_build.py:64-81` constructs both `samadhan` and `seed` assignments, monkeypatches `samagra.factory.run.build`, and asserts 403 with zero delegate calls. `tests/test_g5_golden.py:67-83` separately creates a CLI-planned `samadhan` assignment, approves it, and verifies HTTP build returns 403 without calling `run.build`. The focused backend suite passed with these tests.

### Origin-gating coverage

PASS. The three new exact paths are in `_PROTECTED_POSTS` at `samagra/api/origin_auth.py:41-52`. `is_protected` gates POSTs by exact membership or `/api/gate/` prefix at `samagra/api/origin_auth.py:63-71`; `allow_request` applies that decision to `request.url.path` and returns 403 unless dev bypass, loopback, or valid identity applies at `samagra/api/origin_auth.py:205-218`. The middleware is registered before routes at `samagra/api/app.py:44-48`.

Tests pin exact registration and remote unauthenticated denial: `tests/test_origin_auth.py:263-273`, `tests/test_api_factory_plan.py:12-31`, `tests/test_api_factory_approve_seed.py:19-27`, `tests/test_api_factory_build.py:27-35`, and `tests/test_g5_golden.py:86-96`.

Normalization check: the tests do not explicitly cover trailing-slash/case/URL-encoded variants; they cover exact paths only. I manually smoked the routing/auth interaction with a simulated non-loopback unauthenticated caller: `/api/factory/%70lan` returned 403, while `/api/factory/plan/` and `/API/factory/plan` returned 405 and did not reach a mutating route. I did not find a normalization path that lets an unauthenticated remote request execute a protected mutation.

### Thin-delegate claim

PASS. `POST /api/factory/plan` parses/guards `{seed_ref}`, imports `factory_run`, locks, and calls `factory_run.plan(seed_ref, dry=False)` at `samagra/api/app.py:302-330`. It does not expose `lane`, so the default fan-out remains `run.plan` plus `classify()` at `samagra/factory/run.py:147-227` and `samagra/factory/lines.py:48-57`.

`POST /api/factory/approve-seed` parses/guards `{seed_ref}`, imports `factory_run`, locks, and returns `factory_run.approve_seed(seed_ref)` at `samagra/api/app.py:333-342`. The actual per-seed batch gate remains in `samagra/factory/run.py:257-270`.

`POST /api/factory/build` adds the required kind refusal before delegation, then calls `factory_run.build(assignment_id)` at `samagra/api/app.py:345-385`. The five build guards and crash-safety behavior remain in `run.build`: workflow firewall/status/already-built/in-flight/seed precheck at `samagra/factory/run.py:355-379`, kind-aware mcd/llm preflight at `samagra/factory/run.py:380-407`, intent-before-produce at `samagra/factory/run.py:408-410`, produce/validate at `samagra/factory/run.py:413-420`, failure rollback event for non-mcd at `samagra/factory/run.py:423-437`, and terminal status at `samagra/factory/run.py:438-452`.

One precision note: `api_factory_build` calls `gov_store.ensure_tables()` before `connect_ro()` at `samagra/api/app.py:359-362`, and `connect_ro()` itself also calls `ensure_tables()` before opening SQLite `mode=ro` at `samagra/governance/store.py:81-99`. That makes the "read-only lookup" description slightly imprecise at initialization time, but it reuses the existing startup/read-path schema initializer (`samagra/api/app.py:35-40` and `samagra/api/app.py:173-184`) and does not add a new schema or a new content write path.

### Lock correctness

PASS. The module-level `_FACTORY_RUN_LOCK` is a plain `threading.Lock` at `samagra/api/app.py:290-299`. The handlers acquire it only around the delegate calls: plan at `samagra/api/app.py:321-329`, approve-seed at `samagra/api/app.py:340-342`, and build at `samagra/api/app.py:380-385`. There is no nested acquisition in `samagra/factory/run.py`, and the lock is released by context manager even if the delegate raises.

The lock does serialize potentially slow builds behind plan/approve/build requests in this one process. Under the documented single-operator model, I do not consider that a merge blocker: `build-all` is already a sequential client loop, and the UI disables stepper buttons while a step is in flight at `frontend/src/apps/Publish/index.tsx:35-39`, `frontend/src/apps/Publish/index.tsx:53-98`, and `frontend/src/apps/Publish/index.tsx:114-136`. Starvation risk is therefore operational, not a correctness/security boundary failure.

Coverage: the plan double-POST race is pinned by `tests/test_api_factory_plan.py:91-132`, which uses real `run.plan` under two concurrent `TestClient` threads and asserts exactly five rows per seed. Frontend in-flight disabling is pinned by `frontend/src/apps/Publish/index.test.tsx:168-202`.

### Error mapping honesty

PASS. Body validation maps to 400 in `_parse_seed_ref_body` at `samagra/api/app.py:302-311` and build body parsing at `samagra/api/app.py:354-357`. Build's endpoint-local unknown assignment, unknown pipeline, and kind refusal map to 404/404/403 at `samagra/api/app.py:359-378`. `run.build` `ValueError`s map to 409 at `samagra/api/app.py:380-385`; the underlying five guard `ValueError`s are at `samagra/factory/run.py:360-378`, with mcd pre-write payload/config refusals at `samagra/factory/run.py:385-401`.

I did not find a realistic request shape that reaches `run.build` for `llm` or `mcd`. Non-`ValueError` deterministic lane engine failures can still surface as 500 because `run.build` intentionally re-raises produce failures after recording a `product_build_failed` event for non-mcd lanes at `samagra/factory/run.py:423-437`, and the HTTP wrapper catches only `ValueError` at `samagra/api/app.py:382-385`. I treat that as the existing build failure contract rather than a new G5 validation hole.

Coverage: `tests/test_api_factory_build.py:38-62` covers 400/404/404, `tests/test_api_factory_build.py:108-123` covers `ValueError` to 409, and `tests/test_g5_golden.py:61-64` covers a second build returning 409 rather than 500.

### Frontend request paths

PASS. `recipe.ts` posts exactly to `/api/factory/plan`, `/api/factory/approve-seed`, and `/api/factory/build` with the expected body keys at `frontend/src/lib/publishctl/recipe.ts:56-90`. It derives deterministic-lane state using only `revision`, `lecture`, `deck`, `paper`, and `drill` at `frontend/src/lib/publishctl/recipe.ts:20-53`, so same-seed `seed`/`samadhan` rows do not drive GUI build requests.

The Publish app unwraps the real `/api/assignments` envelope at `frontend/src/apps/Publish/index.tsx:19-24`, builds `seedRef` as `textbook:${slug.trim()}` at `frontend/src/apps/Publish/index.tsx:41`, filters rows to deterministic lanes at `frontend/src/apps/Publish/index.tsx:42-50`, and makes one explicit handler per gate at `frontend/src/apps/Publish/index.tsx:53-98`. The stepper Publish button calls the existing G3 `act("/api/factory/publish", slug.trim())` handler at `frontend/src/apps/Publish/index.tsx:26-29` and `frontend/src/apps/Publish/index.tsx:132-136`; there is no second publish implementation.

Coverage: pure wrapper/derivation tests pin request paths and lane filtering at `frontend/src/lib/publishctl/recipe.test.ts:75-129`. Rendered Publish tests pin the true assignments envelope, per-button calls, deterministic build ordering, samadhan-row filtering, existing publish handler reuse, and in-flight disabling at `frontend/src/apps/Publish/index.test.tsx:16-27` and `frontend/src/apps/Publish/index.test.tsx:71-202`.

## Invariant Checks

| # | DEC-14 invariant | Verdict | Evidence |
|---|---|---|---|
| 1 | No new write mechanism; new endpoints delegate to existing factory run code. | PASS | `api_factory_plan` delegates to `factory_run.plan(seed_ref, dry=False)` at `samagra/api/app.py:314-330`; `api_factory_approve_seed` delegates to `factory_run.approve_seed(seed_ref)` at `samagra/api/app.py:333-342`; `api_factory_build` delegates to `factory_run.build(assignment_id)` only after kind check at `samagra/api/app.py:345-385`. The target functions remain in `samagra/factory/run.py:147-227`, `samagra/factory/run.py:257-270`, and `samagra/factory/run.py:355-454`. |
| 2 | Never-automated publish gate unchanged; owner gates stay explicit. | PASS | The G5 backend adds no batch/publish endpoint beyond the existing G3 `api_factory_publish` at `samagra/api/app.py:264-277`. The frontend has separate Plan, Approve seed, Build all, and Publish buttons at `frontend/src/apps/Publish/index.tsx:114-140`; Publish reuses `act("/api/factory/publish", slug.trim())` at `frontend/src/apps/Publish/index.tsx:132-136`. |
| 3 | llm (`samadhan`) and mcd (`seed`) lanes structurally unreachable over HTTP. | PASS | `LINES` marks `seed` as `"mcd"` and `samadhan` as `"llm"` at `samagra/factory/lines.py:36-41`. `api_factory_build` returns 403 for both kinds before `run.build` at `samagra/api/app.py:371-380`. Tests assert no delegate call for both lanes at `tests/test_api_factory_build.py:64-81` and `tests/test_g5_golden.py:67-83`. |
| 4 | All three new POSTs are origin-gated. | PASS | `_PROTECTED_POSTS` includes `/api/factory/plan`, `/api/factory/approve-seed`, and `/api/factory/build` at `samagra/api/origin_auth.py:41-52`; `origin_auth.enforce` is registered globally at `samagra/api/app.py:44-48`; tests assert exact registration and remote 403s at `tests/test_origin_auth.py:263-273` and `tests/test_g5_golden.py:86-96`. |
| 5 | Student surface untouched. | PASS | The new backend routes live in the factory section at `samagra/api/app.py:290-385`, before the unchanged PRATHAM student identity section starting at `samagra/api/app.py:388`. Golden coverage checks `/api/published`, `/api/learn/me`, and `/api/learn/next` invariance across a G5 run at `tests/test_g5_golden.py:106-125`. |
| 6 | No governance migration/schema change. | PASS | Governance schema remains `SCHEMA_VERSION = 2` with the existing `assignments`, `events`, `review_overlay`, and `style_events` migration definitions at `samagra/governance/store.py:22-50`. The G5 diff added no governance migration file/change; `run.plan`, `approve_seed`, and `build` continue using existing assignment/event store calls at `samagra/factory/run.py:211-221`, `samagra/factory/run.py:263-268`, and `samagra/factory/run.py:408-450`. |

## Test Evidence

Code/tests inspected:
- Backend endpoint tests: `tests/test_api_factory_plan.py:12-132`, `tests/test_api_factory_approve_seed.py:19-56`, `tests/test_api_factory_build.py:27-123`.
- Golden tests: `tests/test_g5_golden.py:32-125`.
- Origin tests: `tests/test_origin_auth.py:263-273`, plus the pre-existing gate-policy tests in the same file.
- Frontend pure/render tests: `frontend/src/lib/publishctl/recipe.test.ts:17-129`, `frontend/src/apps/Publish/index.test.tsx:16-202`.

Commands run:
- Initial backend attempt with system Python failed because system Python has no pytest.
- Initial `.venv` pytest attempt failed before execution because pytest could not access `C:/Users/abc/AppData/Local/Temp/pytest-of-abc`; rerunning with `C:/tmp` also failed because this sandbox could not create `C:/tmp/pytest-g5`.
- Successful backend run: `$env:TMP=(Resolve-Path .).Path + '\\tmp'; $env:TEMP=$env:TMP; New-Item -ItemType Directory -Force tmp | Out-Null; .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider --basetemp .\tmp\pytest-g5 tests\test_api_factory_plan.py tests\test_api_factory_approve_seed.py tests\test_api_factory_build.py tests\test_g5_golden.py tests\test_origin_auth.py` -> `48 passed, 1 warning in 6.40s`.
- Successful frontend run: `npm.cmd run test -- src/lib/publishctl/recipe.test.ts src/apps/Publish/index.test.tsx` from `frontend/` -> `2 passed`, `28 passed`.

Test gap assessment:
- Covered strongly: exact protected-post membership, remote unauthenticated 403s, plan body validation/delegation/whitespace, real concurrent plan double-POST dedup, approve-seed body/delegation/no-op behavior, build 400/404/403/409/delegation behavior, llm/mcd no-delegate boundary, golden student-surface isolation, frontend request paths, deterministic lane filtering, per-gate UI enablement, publish-handler reuse, and in-flight disabling.
- Weak but manually checked: no automated test covers route-normalization variants for the three protected POSTs. I manually checked non-loopback unauthenticated requests and found no bypass: encoded `/api/factory/%70lan` returned 403, while trailing-slash `/api/factory/plan/` and case-variant `/API/factory/plan` returned 405 and did not mutate.

GO

## Addendum: remediation delta da820c0..4418b32

Date: 2026-07-06
Repo: `C:/SandBox/claude_box/TeachingOS`
Branch/head reviewed: `feature/factory-run-http` at `4418b32fb9a85d5fd861ac90ba510cf2c749deed`
Delta reviewed: `da820c0..4418b32` (`336d670`, `d2dd43e`, `4418b32`)

This addendum supersedes the original report's description of `POST /api/factory/approve-seed` only. The original report correctly described the `5be40ed..da820c0` implementation, where the endpoint delegated to `run.approve_seed`; commit `336d670` rewrites that endpoint to scan/filter children itself and call `run.approve(aid)` per kept assignment.

### Scope

Reviewed current file contents and the remediation diff for:
- `samagra/api/app.py`
- `samagra/api/origin_auth.py`
- `samagra/factory/run.py`
- `samagra/factory/lines.py`
- `tests/test_api_factory_approve_seed.py`
- `tests/test_g5_golden.py`

Also checked docs/test-only commits in the delta: `d2dd43e` changes status/handoff docs only, and `4418b32` expands the G5 golden test to build all five deterministic lanes and publish through the existing G3 endpoint.

### Findings

#### HIGH

None.

#### MEDIUM

None.

#### LOW

1. LOW - Concurrent duplicate approve-seed POSTs can return 409 instead of the intended idempotent empty batch.

Evidence:
- The endpoint reads the seed's in-review children before acquiring `_FACTORY_RUN_LOCK` at `samagra/api/app.py:351-360`.
- It then enters the lock and calls `factory_run.approve(aid)` for each precomputed id at `samagra/api/app.py:362-374`.
- `run.approve` refuses any assignment whose status is no longer `"in-review"` at `samagra/factory/run.py:237-252`.
- The sequential retry case is covered: the golden test posts approve-seed a second time after the first completed and gets an empty approved list at `tests/test_g5_golden.py:80-91`.
- The approve-seed tests cover route protection, body validation, per-kept-child `run.approve` calls, empty-batch no-op, and llm skip behavior at `tests/test_api_factory_approve_seed.py:39-118`, but they do not cover two concurrent approve-seed POSTs that both scan before either acquires the lock.

Impact:
A GUI/network duplicate POST that arrives concurrently can have both requests capture the same in-review ids. The first request approves them. The second request then enters the lock with stale ids; its first `run.approve(aid)` sees status `"approved"` and raises `ValueError`, which the endpoint maps to 409. This does not approve llm/mcd rows and does not double-approve rows, but it weakens the original "double-click protection" property from safe no-op to avoidable conflict.

Suggested fix:
Move the read-only scan/filter of `children`/`kept` inside `_FACTORY_RUN_LOCK`, immediately before the loop, so each serialized request re-reads the current state. Then the second duplicate request sees no in-review deterministic children and returns `{"approved": []}`.

### Boundary Checks

1. Origin gate: PASS. `/api/factory/approve-seed` remains in `_PROTECTED_POSTS` at `samagra/api/origin_auth.py:41-52`, and `is_protected` still gates exact POST paths at `samagra/api/origin_auth.py:63-71`. Tests pin both exact membership and remote unauthenticated 403 at `tests/test_api_factory_approve_seed.py:39-47`.

2. No new write mechanism: PASS. The endpoint no longer calls `run.approve_seed`, but the write still goes through the already-reviewed single-assignment CLI verb `run.approve`. The HTTP wrapper calls `factory_run.approve(aid)` at `samagra/api/app.py:362-374`; `run.approve` loads one assignment, verifies it is a factory lane and `"in-review"`, and flips it through `store.set_assignment_status` at `samagra/factory/run.py:237-252`.

3. Kind-filter symmetry with build: PASS. Approve-seed keeps only rows whose `LINES[pipeline].kind` is not `"llm"` or `"mcd"` at `samagra/api/app.py:358-360`. Build refuses the same kinds before delegation at `samagra/api/app.py:396-403`. `LINES` defines deterministic local/qx lanes at `samagra/factory/lines.py:25-35`, `seed` as `"mcd"` at `samagra/factory/lines.py:36-39`, and `samadhan` as `"llm"` at `samagra/factory/lines.py:40-41`. The golden test proves a same-seed `samadhan` row stays in-review after HTTP approve-seed at `tests/test_g5_golden.py:143-164`.

4. Retry idempotency: PASS for completed sequential retries; LOW finding for concurrent duplicates. After a completed approve, a retry re-scans and returns an empty `approved` list, pinned at `tests/test_g5_golden.py:84-91`. The pre-lock scan leaves a concurrent duplicate race, described in the LOW finding above.

5. Partial-batch semantics: PASS with explicit caveat. The code documents that a mid-loop `ValueError` leaves a partial batch and maps to 409 at `samagra/api/app.py:364-373`; the already-approved rows are durable assignment-status updates because `run.approve` commits via `store.set_assignment_status` at `samagra/factory/run.py:237-252`. This is not silent: the caller gets 409. The likely normal source of such a mid-loop failure is stale state from the pre-lock scan, addressed by the LOW finding.

6. Lock/loop/response shape: PASS except for the pre-lock scan issue. The lock is held only during the `run.approve` loop at `samagra/api/app.py:362-374`, not during body parsing or the governance read. The response shape remains `{"seed_ref": seed_ref, "approved": approved}` at `samagra/api/app.py:375`; empty batches return the same shape and are tested at `tests/test_api_factory_approve_seed.py:85-89`.

### Verification

Focused command run:

`$env:TMP=(Resolve-Path .).Path + '\\tmp'; $env:TEMP=$env:TMP; New-Item -ItemType Directory -Force tmp | Out-Null; .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider --basetemp .\tmp\pytest-g5-addendum tests\test_api_factory_approve_seed.py tests\test_g5_golden.py tests\test_origin_auth.py`

Result: `33 passed, 1 warning in 7.04s`. The warning is the existing Starlette/httpx deprecation warning from `fastapi.testclient`.

GO

Closure: the addendum's LOW (pre-lock scan) was fixed in commit 83921a1 — scan moved inside _FACTORY_RUN_LOCK + concurrent regression test.
