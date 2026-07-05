# Phase G4 Pre-Merge Review

## Verdict

GO-WITH-CAVEATS. I found no concrete HIGH/MED/LOW correctness or security findings in the reviewed G4 code path; the caveat is verification-only: targeted pytest execution could not start in this read-only sandbox because pytest had no usable temp directory.

## Findings

No HIGH/MED/LOW findings.

## Invariant Checks

1. PASS — Student writes touch ONLY `pratham.db`; `samagra/pratham/` imports no factory/governance module.  
Evidence: `samagra/pratham/store.py:12` imports only config, `samagra/pratham/store.py:49-53` connects to `config.PRATHAM_DB`, and `samagra/pratham/store.py:148-156` is the only new progress upsert. `samagra/pratham/service.py:12-13` imports only config plus local identity/store; `samagra/pratham/service.py:80-89` delegates to `store.mark_progress`. The API layer performs the manifest check before entering pratham at `samagra/api/app.py:346-364`.

2. PASS — Student identity is server-derived only.  
Evidence: `POST /api/learn/progress` has no student path parameter at `samagra/api/app.py:340-341`; it derives the student from `_PRATHAM_COOKIE` at `samagra/api/app.py:348`, reads only `chapter` and `lane` from the body at `samagra/api/app.py:351-356`, and writes with `student["id"]` at `samagra/api/app.py:363`. `GET /api/learn/next` similarly derives the student from the cookie at `samagra/api/app.py:368-377`. The frontend posts only `{chapter, lane}` at `frontend/src/lib/pratham/plan.ts:20-26`.

3. PASS — 404-before-write prevents unpublished progress rows.  
Evidence: `samagra/api/app.py:357-362` loads the live published manifest and raises 404 when the requested lane is not present, before `service.mark_done` is called at `samagra/api/app.py:363`. The regression test asserts both unpublished lane and chapter return 404 and leave progress empty at `tests/test_api_learn_progress.py:40-47`.

4. PASS — Deterministic recommender, no LLM/network/key.  
Evidence: `samagra/factory/coverage/next_best.py:1-5` states and implements the ranker as pure/no I/O; the actual ranking is a deterministic sort/cap/rank at `samagra/factory/coverage/next_best.py:17-37`. The glue reads the manifest and concept graph only at `samagra/api/learn_next.py:17-43`, using `coverage_store.connect_ro()`, whose SQLite URI is opened with `mode=ro` at `samagra/factory/coverage/store.py:53-59`.

5. PASS — CSRF acceptance is scoped.  
Evidence: the PRATHAM cookie is `HttpOnly`, `SameSite=Lax`, and scoped to `path="/api/learn"` at `samagra/api/app.py:317-319`; deletion mirrors that path at `samagra/api/app.py:329-330`. The progress endpoint is session-gated, not origin-gated, and only writes the authenticated student's own row at `samagra/api/app.py:342-364`. The body cannot express status or another student in the implemented write path.

6. PASS — Anonymous `/learn`, governance, publish gate, build guards, and source subsystems remain untouched.  
Evidence: anonymous adaptive UI is gated behind `student` at `frontend/src/apps/Pratham/index.tsx:70-78`, `frontend/src/apps/Pratham/index.tsx:203-217`, and `frontend/src/apps/Pratham/index.tsx:226-244`; the anonymous regression asserts no adaptive UI and no `/api/learn/next` call at `frontend/src/apps/Pratham/adaptive.test.tsx:38-45`. Governance schema remains at `SCHEMA_VERSION = 2` with only the prior `style_events` migration at `samagra/governance/store.py:24-50`. The owner publish gate remains a thin delegate at `samagra/api/app.py:263-285`; the factory build guards remain in `samagra/factory/run.py:355-420` and `samagra/factory/run.py:431-450`. Diff inspection showed no G4 changes under governance, factory run/dispatch/publish run, lectures, bridge, clients, adapters, catalog, scheduler, or state.

## Test Gap Assessment

Covered: progress auth/body/404/idempotency/rate-limit tests at `tests/test_api_learn_progress.py:21-65`; next auth/empty queue tests at `tests/test_api_learn_next.py:12-34`; store/service progress tests at `tests/test_pratham_progress_store.py:7-56` and `tests/test_pratham_progress_service.py:4-22`; pure ranker determinism/ranking tests at `tests/test_next_best.py:9-41`; glue tests for unbuilt/corrupt graph and done subtraction at `tests/test_learn_next_glue.py:14-52`; golden loop/governance-byte-isolation/anonymous checks at `tests/test_g4_golden.py:25-55`; frontend anonymous and signed-in adaptive tests at `frontend/src/apps/Pratham/adaptive.test.tsx:38-86`.

Missing or weak: no explicit test posts an extra `student_id` or `status` field to prove it is ignored/rejected; current code is still IDOR-safe because it never reads those fields, but a stricter contract test would pin the "no id in body" rule. I also could not execute the focused test set here: system Python lacked pytest, and the repo `.venv` pytest failed before collection with `FileNotFoundError: No usable temporary directory found`.
