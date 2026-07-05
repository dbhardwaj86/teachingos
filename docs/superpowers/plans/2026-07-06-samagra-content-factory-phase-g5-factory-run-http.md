# SAMAGRA Content Factory — Phase G5 (factory run over HTTP) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Put the deterministic content-factory recipe (plan → approve-seed → build ×N → publish) on the SAMAGRA console GUI so the Chairman can run it on-demand, extending the existing Publish app with a "Factory run" stepper panel — while every governance gate stays its own explicit click and the one production-write path (the mcd `seed` lane) keeps zero HTTP triggers.

**Architecture:** Three new origin-gated POSTs in `samagra/api/app.py` — `POST /api/factory/plan`, `POST /api/factory/approve-seed`, `POST /api/factory/build` — each a thin delegate to the already-reviewed `samagra/factory/run.py` (`plan`/`approve_seed`/`build`), added to `origin_auth._PROTECTED_POSTS` (6 → 9 entries) so they inherit the existing Cloudflare-Access owner gate verbatim. `POST /api/factory/build` structurally refuses (403) any assignment whose lane `kind` is `"llm"` or `"mcd"` (`samagra/factory/lines.LINES[pipeline].kind`), keyed BEFORE calling `run.build` — Samadhan and the mcd seed lane stay CLI-only. Frontend: a new pure lib `frontend/src/lib/publishctl/recipe.ts` derives stepper state from `/api/assignments` rows and wraps the 3 new POSTs; the Publish app (`frontend/src/apps/Publish/index.tsx`) gains a "Factory run" panel with 4 per-gate buttons (Plan / Approve seed / Build all / Publish — Publish reuses the existing G3 handler). No new app, no new write mechanism, no migration.

**Tech Stack:** Python 3.11, FastAPI, pytest + FastAPI `TestClient`; React + TypeScript + Vite, vitest + @testing-library/react.

**Spec:** `docs/superpowers/specs/2026-07-06-samagra-content-factory-phase-g5-factory-run-http-design.md` (forks ratified by the Chairman 2026-07-06: F-G5-1 extend Publish app, F-G5-2 per-gate buttons, F-G5-3 llm/mcd structural 403; proposed DEC-14).
**Branch:** `feature/factory-run-http` (created from `main` @ `5be40ed`).
**Baseline gate:** 637 pytest passed + 1 skip (opt-in live-LLM smoke) · 613 vitest · tsc + build green.

---

## File Structure

**Backend (modify):**
- `samagra/api/origin_auth.py` — 3 new entries in `_PROTECTED_POSTS` (`/api/factory/plan`, `/api/factory/approve-seed`, `/api/factory/build`).
- `samagra/api/app.py` — 3 new endpoints (in the existing G3 `/api/factory/*` block, after `api_factory_unpublish`).
- `docs/deploy-tunnel.md` — endpoint enumeration re-synced (the `_PROTECTED_POSTS` paragraph).

**Backend (create):**
- none — no new Python modules; the endpoints delegate to the existing `samagra/factory/run.py` + `samagra/factory/lines.py`.

**Frontend (create):**
- `frontend/src/lib/publishctl/recipe.ts` — PURE stepper-state derivation + typed fetch wrappers.
- `frontend/src/lib/publishctl/recipe.test.ts` — table-driven tests.

**Frontend (modify):**
- `frontend/src/apps/Publish/index.tsx` — the "Factory run" stepper panel.
- `frontend/src/apps/Publish/index.test.tsx` — new stepper-panel tests (append; file may need creating if it doesn't already exist — verify against reality, adapt the TEST never the module, flag it if the file layout differs).

**Tests (create):** `tests/test_api_factory_plan.py`, `tests/test_api_factory_approve_seed.py`, `tests/test_api_factory_build.py`, `tests/test_g5_golden.py`, `frontend/src/lib/publishctl/recipe.test.ts`.

**No changes to:** `samagra/factory/run.py`, `samagra/factory/lines.py`, `samagra/factory/publish/`, `samagra/pratham/`, `samagra/factory/coverage/`, `samagra/factory/style/`, `governance/store.py` schema, `registry.ts`/`App.tsx` (no new app), any `/api/learn/*` or `/api/published*` code.

---

### Task 0: Branch

- [x] **Step 1: Create the branch**

```bash
git checkout main && git pull && git checkout -b feature/factory-run-http
```

(Already done for this docs-only commit — this step is a no-op re-statement for the implementer picking up the plan; verify `git branch --show-current` reports `feature/factory-run-http` before Task 1.)

- [x] **Step 2: Commit the spec + this plan** (if not already committed)

```bash
git add docs/superpowers/specs/2026-07-06-samagra-content-factory-phase-g5-factory-run-http-design.md docs/superpowers/plans/2026-07-06-samagra-content-factory-phase-g5-factory-run-http.md
git commit -m "docs(g5): Phase G5 factory-run-over-HTTP design (proposed) + implementation plan"
```

---

### Task 1: origin_auth — 3 new protected POSTs + deploy-tunnel.md sync

**Files:**
- Modify: `samagra/api/origin_auth.py:41-46` (`_PROTECTED_POSTS`)
- Modify: `docs/deploy-tunnel.md` (the `_PROTECTED_POSTS`/`_PROTECTED_GETS` enumeration paragraph, ~line 20-30)
- Test: `tests/test_origin_auth.py` (extend — verify this file exists and holds the existing `_PROTECTED_POSTS`/`is_protected` tests; if the assertions live in a differently-named file, adapt the file path, not the test content)

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_origin_auth.py
from samagra.api import origin_auth


def test_factory_run_endpoints_are_in_protected_posts():
    assert origin_auth.is_protected("POST", "/api/factory/plan") is True
    assert origin_auth.is_protected("POST", "/api/factory/approve-seed") is True
    assert origin_auth.is_protected("POST", "/api/factory/build") is True


def test_protected_posts_count_is_nine():
    # Documents the growth 6 -> 9 this slice makes (spec §4); a future slice bumping
    # this further should update the count deliberately, not by accident.
    assert len(origin_auth._PROTECTED_POSTS) == 9
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_origin_auth.py -k factory_run -q`
Expected: FAIL — `is_protected("POST", "/api/factory/plan") is True` assertion fails (not yet in the set); count assertion fails (6, not 9).

- [ ] **Step 3: Implement**

In `samagra/api/origin_auth.py`, replace the `_PROTECTED_POSTS` frozenset (currently
lines 41-46):

```python
_PROTECTED_POSTS = frozenset({
    "/api/refresh", "/api/tick", "/api/munshi/capture", "/api/mcd/seeds",
    # G3: the owner publish write path — the GUI/network sibling of the G1 CLI
    # publish. Owner-gated (never-automated); delegates to the reviewed publish.run.
    "/api/factory/publish", "/api/factory/unpublish",
    # G5: the owner factory-run write path (plan/approve-seed/build over HTTP) —
    # the GUI/network sibling of `samagra factory plan|approve-seed|build`. Each is
    # a thin delegate to the already-reviewed samagra/factory/run.py; build()
    # structurally refuses the llm/mcd lane kinds (see api_factory_build). Owner-
    # gated; never-automated (each gate is its own explicit owner click, F-G5-2).
    "/api/factory/plan", "/api/factory/approve-seed", "/api/factory/build",
})
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_origin_auth.py -q`
Expected: all pass (the 2 new + all pre-existing origin_auth tests green).

- [ ] **Step 5: Re-sync `docs/deploy-tunnel.md`**

In `docs/deploy-tunnel.md`, the `⚠️ Access before exposure (hard rule)` paragraph
(~lines 18-30) currently reads (verify against the live file — the exact line numbers
may have shifted since this plan was written):

```
> `POST /api/munshi/capture`, `POST /api/mcd/seeds`, and (since Phase G3)
> **`POST /api/factory/publish`**, **`POST /api/factory/unpublish`** (the outward
> publish gate's HTTP trigger) — plus the four protected GETs
```

Change to:

```
> `POST /api/munshi/capture`, `POST /api/mcd/seeds`, (since Phase G3)
> **`POST /api/factory/publish`**, **`POST /api/factory/unpublish`** (the outward
> publish gate's HTTP trigger), and (since Phase G5) **`POST /api/factory/plan`**,
> **`POST /api/factory/approve-seed`**, **`POST /api/factory/build`** (the factory-run
> recipe's HTTP trigger; `build` additionally refuses the llm/mcd lane kinds with a
> structural 403 before any factory code runs — the one production-write path, the
> mcd `seed` lane, keeps zero HTTP triggers) — plus the four protected GETs
```

- [ ] **Step 6: Commit**

```bash
git add samagra/api/origin_auth.py tests/test_origin_auth.py docs/deploy-tunnel.md
git commit -m "feat(g5): origin-gate the 3 factory-run POSTs (plan/approve-seed/build)"
```

---

### Task 2: `POST /api/factory/plan`

**Files:**
- Modify: `samagra/api/app.py` (append to the existing G3 factory block, after `api_factory_unpublish`)
- Test: `tests/test_api_factory_plan.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_api_factory_plan.py
import pytest
from fastapi.testclient import TestClient

from samagra import config
from samagra.api import app as api_app
from samagra.api import origin_auth


@pytest.fixture
def gate_on(monkeypatch):
    monkeypatch.setattr(config, "DISABLE_ORIGIN_AUTH", False)
    monkeypatch.setattr(config, "ACCESS_AUD", None)
    monkeypatch.setattr(config, "ACCESS_TEAM_DOMAIN", None)
    monkeypatch.setattr(config, "OWNER_EMAIL", None)
    return monkeypatch


def test_remote_plan_without_identity_is_403(gate_on):
    gate_on.setattr(origin_auth, "_client_host", lambda req: "203.0.113.9")
    c = TestClient(api_app.app)
    r = c.post("/api/factory/plan", json={"seed_ref": "textbook:circular-motion"})
    assert r.status_code == 403


def test_missing_seed_ref_is_400():
    c = TestClient(api_app.app)
    assert c.post("/api/factory/plan", json={}).status_code == 400
    assert c.post("/api/factory/plan", json={"seed_ref": 3}).status_code == 400
    assert c.post("/api/factory/plan", json={"seed_ref": "  "}).status_code == 400


def test_non_textbook_seed_ref_is_400():
    # v1 scope guard (spec §4.1): munshi:/other prefixes stay CLI-only.
    c = TestClient(api_app.app)
    r = c.post("/api/factory/plan", json={"seed_ref": "munshi:52"})
    assert r.status_code == 400


def test_plan_delegates_to_run_dry_false_no_lane(monkeypatch):
    captured = {}

    def fake_plan(seed_ref, dry=True, lane=None):
        captured.update(seed_ref=seed_ref, dry=dry, lane=lane)
        return [{"seed_ref": seed_ref, "line": "revision",
                 "expected_output": "Revision sheet (thin lecture export)",
                 "assignment_id": "a1"}]
    monkeypatch.setattr("samagra.factory.run.plan", fake_plan)
    c = TestClient(api_app.app)
    r = c.post("/api/factory/plan", json={"seed_ref": "textbook:circular-motion"})
    assert r.status_code == 200
    assert r.json() == {"proposals": [
        {"seed_ref": "textbook:circular-motion", "line": "revision",
         "expected_output": "Revision sheet (thin lecture export)",
         "assignment_id": "a1"}]}
    assert captured == {"seed_ref": "textbook:circular-motion", "dry": False, "lane": None}


def test_plan_strips_whitespace(monkeypatch):
    captured = {}
    monkeypatch.setattr("samagra.factory.run.plan",
                        lambda seed_ref, dry=True, lane=None: captured.update(seed_ref=seed_ref) or [])
    c = TestClient(api_app.app)
    c.post("/api/factory/plan", json={"seed_ref": "  textbook:circular-motion  "})
    assert captured["seed_ref"] == "textbook:circular-motion"
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_api_factory_plan.py -q`
Expected: FAIL — route 404 (not yet defined); the 403 test fails too (nothing to gate yet).

- [ ] **Step 3: Implement**

In `samagra/api/app.py`, immediately after `api_factory_unpublish` (Task 5's location
in the G3 plan) and BEFORE the `# -- G3 PRATHAM student identity` comment block, add a
shared body-parse helper + the endpoint:

```python
# -- G5 factory-run write path (owner-gated; thin delegates to samagra/factory/run.py) --
def _parse_seed_ref_body(payload: dict) -> str:
    """Validate {seed_ref}. Required non-empty str; v1 scope guard restricts to the
    textbook: prefix (spec §4.1/§4.2) — munshi:/other prefixes stay CLI-only."""
    seed_ref = (payload or {}).get("seed_ref")
    if not isinstance(seed_ref, str) or not seed_ref.strip():
        raise HTTPException(400, "seed_ref is required")
    seed_ref = seed_ref.strip()
    if not seed_ref.startswith("textbook:"):
        raise HTTPException(400, "seed_ref must start with 'textbook:' (v1 GUI scope)")
    return seed_ref


@app.post("/api/factory/plan")
def api_factory_plan(payload: dict):
    # The GUI/network sibling of `samagra factory plan`. dry=False so it actually
    # records the in-review child assignments (the CLI's live-mode behaviour);
    # lane is omitted so classify() drives the default 5-lane deterministic fan-out
    # — the GUI never targets a single lane (samadhan/seed stay CLI-only, F-G5-3).
    seed_ref = _parse_seed_ref_body(payload)
    from ..factory import run as factory_run
    try:
        proposals = factory_run.plan(seed_ref, dry=False)
    except ValueError as e:
        raise HTTPException(409, str(e))
    return {"proposals": proposals}
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_api_factory_plan.py -q`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add samagra/api/app.py tests/test_api_factory_plan.py
git commit -m "feat(g5): POST /api/factory/plan — owner-gated delegate to run.plan(dry=False)"
```

---

### Task 3: `POST /api/factory/approve-seed`

**Files:**
- Modify: `samagra/api/app.py` (directly after `api_factory_plan`)
- Test: `tests/test_api_factory_approve_seed.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_api_factory_approve_seed.py
import pytest
from fastapi.testclient import TestClient

from samagra import config
from samagra.api import app as api_app
from samagra.api import origin_auth


@pytest.fixture
def gate_on(monkeypatch):
    monkeypatch.setattr(config, "DISABLE_ORIGIN_AUTH", False)
    monkeypatch.setattr(config, "ACCESS_AUD", None)
    monkeypatch.setattr(config, "ACCESS_TEAM_DOMAIN", None)
    monkeypatch.setattr(config, "OWNER_EMAIL", None)
    return monkeypatch


def test_remote_approve_seed_without_identity_is_403(gate_on):
    gate_on.setattr(origin_auth, "_client_host", lambda req: "203.0.113.9")
    c = TestClient(api_app.app)
    r = c.post("/api/factory/approve-seed", json={"seed_ref": "textbook:circular-motion"})
    assert r.status_code == 403


def test_missing_or_non_textbook_seed_ref_is_400():
    c = TestClient(api_app.app)
    assert c.post("/api/factory/approve-seed", json={}).status_code == 400
    assert c.post("/api/factory/approve-seed",
                  json={"seed_ref": "munshi:52"}).status_code == 400


def test_approve_seed_delegates_to_run(monkeypatch):
    captured = {}

    def fake_approve_seed(seed_ref):
        captured["seed_ref"] = seed_ref
        return {"seed_ref": seed_ref, "approved": ["a1", "a2"]}
    monkeypatch.setattr("samagra.factory.run.approve_seed", fake_approve_seed)
    c = TestClient(api_app.app)
    r = c.post("/api/factory/approve-seed", json={"seed_ref": "textbook:circular-motion"})
    assert r.status_code == 200
    assert r.json() == {"seed_ref": "textbook:circular-motion", "approved": ["a1", "a2"]}
    assert captured == {"seed_ref": "textbook:circular-motion"}


def test_approve_seed_noop_for_no_in_review_children(monkeypatch):
    monkeypatch.setattr("samagra.factory.run.approve_seed",
                        lambda seed_ref: {"seed_ref": seed_ref, "approved": []})
    c = TestClient(api_app.app)
    r = c.post("/api/factory/approve-seed", json={"seed_ref": "textbook:no-such-plan"})
    assert r.status_code == 200 and r.json()["approved"] == []
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_api_factory_approve_seed.py -q`
Expected: FAIL — route 404 (not yet defined).

- [ ] **Step 3: Implement**

In `samagra/api/app.py`, immediately after `api_factory_plan`:

```python
@app.post("/api/factory/approve-seed")
def api_factory_approve_seed(payload: dict):
    # The GUI/network sibling of `samagra factory approve-seed` — the PER-SEED
    # BATCH gate (fork 3, Phase 1): flips every in-review child of this seed to
    # approved in one explicit owner click. Never a silent auto-approve; distinct
    # click from Plan and from Build (F-G5-2).
    seed_ref = _parse_seed_ref_body(payload)
    from ..factory import run as factory_run
    return factory_run.approve_seed(seed_ref)
```

> NOTE: `run.approve_seed` never raises in the current implementation (it filters
> `store.list_assignments` in a loop and returns `{"approved": []}` for a seed with no
> in-review children — verified at `samagra/factory/run.py:257-270`), so there is no
> try/except here. If a future change to `run.approve_seed` adds a raise, wrap it the
> same way `api_factory_plan` does (`ValueError` → 409) — flag this as a place to
> re-verify against reality if the signature has changed since this plan was written.

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_api_factory_approve_seed.py -q`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add samagra/api/app.py tests/test_api_factory_approve_seed.py
git commit -m "feat(g5): POST /api/factory/approve-seed — owner-gated per-seed batch approve"
```

---

### Task 4: `POST /api/factory/build` — the kind-refusal boundary

**Files:**
- Modify: `samagra/api/app.py` (directly after `api_factory_approve_seed`)
- Test: `tests/test_api_factory_build.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_api_factory_build.py
import pytest
from fastapi.testclient import TestClient

from samagra import config
from samagra.api import app as api_app
from samagra.api import origin_auth


@pytest.fixture
def gate_on(monkeypatch):
    monkeypatch.setattr(config, "DISABLE_ORIGIN_AUTH", False)
    monkeypatch.setattr(config, "ACCESS_AUD", None)
    monkeypatch.setattr(config, "ACCESS_TEAM_DOMAIN", None)
    monkeypatch.setattr(config, "OWNER_EMAIL", None)
    return monkeypatch


def _gov(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "GOVERNANCE_DB", tmp_path / "governance.db")
    from samagra.governance import store as gov
    gov._INITIALIZED.clear()
    gov.ensure_tables()
    return gov


def test_remote_build_without_identity_is_403(gate_on):
    gate_on.setattr(origin_auth, "_client_host", lambda req: "203.0.113.9")
    c = TestClient(api_app.app)
    r = c.post("/api/factory/build", json={"assignment_id": "a1"})
    assert r.status_code == 403


def test_missing_assignment_id_is_400():
    c = TestClient(api_app.app)
    assert c.post("/api/factory/build", json={}).status_code == 400
    assert c.post("/api/factory/build", json={"assignment_id": 3}).status_code == 400


def test_unknown_assignment_is_404(tmp_path, monkeypatch):
    _gov(tmp_path, monkeypatch)
    c = TestClient(api_app.app)
    r = c.post("/api/factory/build", json={"assignment_id": "no-such-id"})
    assert r.status_code == 404


def test_unrecognized_pipeline_is_404(tmp_path, monkeypatch):
    gov = _gov(tmp_path, monkeypatch)
    conn = gov.connect()
    gov.add_assignment(conn, id="a1", agent="khanak", outbox_path="x",
                       pipeline="not-a-real-lane", seed_ref="textbook:cm",
                       expected_output="x", review_by="khanak")
    gov.set_assignment_status(conn, "a1", "approved")
    conn.close()
    c = TestClient(api_app.app)
    r = c.post("/api/factory/build", json={"assignment_id": "a1"})
    assert r.status_code == 404


@pytest.mark.parametrize("lane", ["samadhan", "seed"])
def test_llm_and_mcd_lanes_are_403_before_run_build_is_called(lane, tmp_path, monkeypatch):
    gov = _gov(tmp_path, monkeypatch)
    conn = gov.connect()
    gov.add_assignment(conn, id="a1", agent="khanak", outbox_path="x",
                       pipeline=lane, seed_ref="textbook:cm" if lane == "samadhan" else "munshi:1",
                       expected_output="x", review_by="khanak")
    gov.set_assignment_status(conn, "a1", "approved")
    conn.close()

    called = {"hit": False}
    monkeypatch.setattr("samagra.factory.run.build",
                        lambda aid: called.__setitem__("hit", True) or {})
    c = TestClient(api_app.app)
    r = c.post("/api/factory/build", json={"assignment_id": "a1"})
    assert r.status_code == 403
    assert called["hit"] is False   # run.build (and therefore dispatch.run_seed /
                                    # samadhan.generate_samadhan) is NEVER invoked


def test_deterministic_lane_delegates_to_run_build(tmp_path, monkeypatch):
    gov = _gov(tmp_path, monkeypatch)
    conn = gov.connect()
    gov.add_assignment(conn, id="a1", agent="khanak", outbox_path="x",
                       pipeline="revision", seed_ref="textbook:cm",
                       expected_output="x", review_by="khanak")
    gov.set_assignment_status(conn, "a1", "approved")
    conn.close()

    captured = {}

    def fake_build(assignment_id):
        captured["assignment_id"] = assignment_id
        return {"assignment_id": assignment_id, "line": "revision",
                "artifact_ref": "/exports/cm-thin.html", "status": "captured"}
    monkeypatch.setattr("samagra.factory.run.build", fake_build)
    c = TestClient(api_app.app)
    r = c.post("/api/factory/build", json={"assignment_id": "a1"})
    assert r.status_code == 200
    assert r.json()["line"] == "revision"
    assert r.json()["artifact_ref"] == "/exports/cm-thin.html"
    assert captured == {"assignment_id": "a1"}


def test_run_build_valueerror_is_409(tmp_path, monkeypatch):
    gov = _gov(tmp_path, monkeypatch)
    conn = gov.connect()
    gov.add_assignment(conn, id="a1", agent="khanak", outbox_path="x",
                       pipeline="revision", seed_ref="textbook:cm",
                       expected_output="x", review_by="khanak")
    # deliberately leave status='in-review' (not 'approved') so run.build's own
    # guard-1 ValueError fires
    conn.close()

    def fake_build(assignment_id):
        raise ValueError(f"assignment {assignment_id} is 'in-review', not 'approved'")
    monkeypatch.setattr("samagra.factory.run.build", fake_build)
    c = TestClient(api_app.app)
    r = c.post("/api/factory/build", json={"assignment_id": "a1"})
    assert r.status_code == 409
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_api_factory_build.py -q`
Expected: FAIL — route 404 (not yet defined). NOTE: verify the exact keyword-argument
names `add_assignment`/`set_assignment_status`/`connect` take against
`samagra/governance/store.py` before running — if any signature differs from what is
written above (e.g. `add_assignment`'s exact kwargs), FIX THE TEST to match the real
`store.py` API, never invent a different `run.build`/`app.py` contract to route around
a test that was wrong about `store.py`.

- [ ] **Step 3: Implement**

In `samagra/api/app.py`, immediately after `api_factory_approve_seed`:

```python
@app.post("/api/factory/build")
def api_factory_build(payload: dict):
    # The GUI/network sibling of `samagra factory build`. Looks up the assignment's
    # lane KIND before delegating (spec §4.3, F-G5-3): a "llm" (samadhan — needs an
    # API key + incurs real generation cost) or "mcd" (seed — the ONE production
    # write path, the C3 bridge-fold) lane is refused with 403 BEFORE run.build is
    # ever called, so dispatch.run_seed / samadhan.generate_samadhan are structurally
    # unreachable over HTTP. This is the one place this endpoint does more than
    # parse-and-delegate.
    assignment_id = (payload or {}).get("assignment_id")
    if not isinstance(assignment_id, str) or not assignment_id.strip():
        raise HTTPException(400, "assignment_id is required")
    assignment_id = assignment_id.strip()

    from ..factory.lines import LINES
    from ..governance import store as gov_store
    gov_store.ensure_tables()
    conn = gov_store.connect_ro()
    try:
        assignment = next(
            (a for a in gov_store.list_assignments(conn) if a["id"] == assignment_id),
            None)
    finally:
        conn.close()
    if assignment is None:
        raise HTTPException(404, "unknown assignment")
    spec = LINES.get(assignment["pipeline"])
    if spec is None:
        raise HTTPException(404, "assignment pipeline is not a recognized factory lane")
    if spec.kind in ("llm", "mcd"):
        raise HTTPException(
            403,
            f"the {spec.kind} lane ({assignment['pipeline']}) is CLI-only — "
            "build it with `samagra factory build " + assignment_id + "` at a terminal")

    from ..factory import run as factory_run
    try:
        return factory_run.build(assignment_id)
    except ValueError as e:
        raise HTTPException(409, str(e))
```

> NOTE: verify `gov_store.connect_ro()` exists and returns a connection whose
> `list_assignments` reads work the same as `connect()` (the read side is used here
> deliberately — this endpoint only ever READS governance state for the kind check;
> the actual write happens inside `factory_run.build`, which opens its own connection).
> If `connect_ro` does not exist on `governance/store.py`, use `gov_store.connect()`
> instead and close it identically — adapt the implementation, not the test's
> observable behaviour (404/403/200/409 outcomes must stay as specified).

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_api_factory_build.py -q`
Expected: 7 passed (2 parametrized cases count as 2).

- [ ] **Step 5: Commit**

```bash
git add samagra/api/app.py tests/test_api_factory_build.py
git commit -m "feat(g5): POST /api/factory/build — kind-refuses llm/mcd (403) before delegating to run.build"
```

---

### Task 5: backend golden threads

**Files:**
- Test: `tests/test_g5_golden.py`

- [ ] **Step 1: Write the tests**

```python
# tests/test_g5_golden.py
"""Phase G5 golden threads (spec §7): the HTTP recipe matches the CLI's own
result, llm/mcd stay structurally unreachable over HTTP, origin gating holds,
and the student surface is untouched. Mirrors tests/test_g3_golden.py's /
tests/test_g4_golden.py's style: a monkeypatched-temp world, real factory code,
faked-only-at-the-edges (the lecture export writer, matching the G3 golden
thread's own precedent for a Phase-1 local-write lane)."""
import hashlib

from fastapi.testclient import TestClient

from samagra import config
from samagra.api import app as api_app
from samagra.api import origin_auth
from samagra.governance import store as gov


def _fresh_world(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "GOVERNANCE_DB", tmp_path / "governance.db")
    monkeypatch.setattr(config, "DATA_DB", tmp_path / "samagra.db")
    monkeypatch.setattr(config, "EXPORT_DIR", tmp_path / "exports")
    monkeypatch.setattr(config, "PUBLISHED_DIR", tmp_path / "published")
    gov._INITIALIZED.clear()
    gov.ensure_tables()
    monkeypatch.chdir(tmp_path)

    def fake_export_one(slug, variant, **kw):
        out = tmp_path / f"{slug}-{variant}.html"
        out.write_text(f"<h1>{slug} {variant}</h1>", encoding="utf-8")
        return {"variant": variant, "html": str(out), "docx": None, "gdoc": None}
    monkeypatch.setattr("samagra.lectures.export.export_one", fake_export_one)


def test_golden_http_recipe_matches_deterministic_lane_build(tmp_path, monkeypatch):
    _fresh_world(tmp_path, monkeypatch)
    c = TestClient(api_app.app)
    seed_ref = "textbook:circular-motion"

    plan_resp = c.post("/api/factory/plan", json={"seed_ref": seed_ref})
    assert plan_resp.status_code == 200
    proposals = plan_resp.json()["proposals"]
    rev = next(p for p in proposals if p["line"] == "revision")
    assert rev["assignment_id"]

    appr_resp = c.post("/api/factory/approve-seed", json={"seed_ref": seed_ref})
    assert appr_resp.status_code == 200
    assert rev["assignment_id"] in appr_resp.json()["approved"]

    build_resp = c.post("/api/factory/build", json={"assignment_id": rev["assignment_id"]})
    assert build_resp.status_code == 200
    assert build_resp.json()["line"] == "revision"
    assert build_resp.json()["artifact_ref"]

    # A second build of the SAME assignment is refused (guard 2, unchanged) -> 409,
    # never a silent double-build or a 500.
    again = c.post("/api/factory/build", json={"assignment_id": rev["assignment_id"]})
    assert again.status_code == 409


def test_golden_llm_and_mcd_unreachable_over_http(tmp_path, monkeypatch):
    _fresh_world(tmp_path, monkeypatch)
    c = TestClient(api_app.app)
    # Plan the opt-in samadhan lane the way the CLI would (--lane samadhan) —
    # the GUI's own plan endpoint never does this (v1 scope guard, Task 2), but the
    # BUILD refusal must hold regardless of how the assignment came to exist.
    from samagra.factory import run as factory_run
    proposals = factory_run.plan("textbook:circular-motion", dry=False, lane="samadhan")
    aid = proposals[0]["assignment_id"]
    factory_run.approve(aid)

    called = {"hit": False}
    monkeypatch.setattr("samagra.factory.run.build",
                        lambda a: called.__setitem__("hit", True) or {})
    r = c.post("/api/factory/build", json={"assignment_id": aid})
    assert r.status_code == 403
    assert called["hit"] is False


def test_golden_origin_gating_holds(monkeypatch):
    monkeypatch.setattr(config, "DISABLE_ORIGIN_AUTH", False)
    monkeypatch.setattr(config, "ACCESS_AUD", None)
    monkeypatch.setattr(config, "ACCESS_TEAM_DOMAIN", None)
    monkeypatch.setattr(config, "OWNER_EMAIL", None)
    monkeypatch.setattr(origin_auth, "_client_host", lambda req: "203.0.113.9")
    c = TestClient(api_app.app)
    for path, body in [("/api/factory/plan", {"seed_ref": "textbook:x"}),
                       ("/api/factory/approve-seed", {"seed_ref": "textbook:x"}),
                       ("/api/factory/build", {"assignment_id": "x"})]:
        assert c.post(path, json=body).status_code == 403


def test_golden_student_surface_untouched(tmp_path, monkeypatch):
    _fresh_world(tmp_path, monkeypatch)
    monkeypatch.setattr(config, "PRATHAM_DB", tmp_path / "pratham.db")
    from samagra.pratham import store as pratham_store
    pratham_store._INITIALIZED.clear()

    c = TestClient(api_app.app)
    before_published = c.get("/api/published").json()
    before_me = c.get("/api/learn/me").json()

    seed_ref = "textbook:circular-motion"
    c.post("/api/factory/plan", json={"seed_ref": seed_ref})
    proposals = factory_run_proposals = c.post(
        "/api/factory/plan", json={"seed_ref": seed_ref}).json()["proposals"]
    rev = next(p for p in proposals if p["line"] == "revision")
    c.post("/api/factory/approve-seed", json={"seed_ref": seed_ref})
    c.post("/api/factory/build", json={"assignment_id": rev["assignment_id"]})

    assert c.get("/api/published").json() == before_published
    assert c.get("/api/learn/me").json() == before_me
    assert c.get("/api/learn/next").status_code == 401   # unchanged: session-gated
```

- [ ] **Step 2: Run**

Run: `python -m pytest tests/test_g5_golden.py -q`
Expected: 4 passed (or fix forward — this is the acceptance record for spec §7; if the
real `run.plan`/`run.approve`/`run.build` signatures or the lecture-export monkeypatch
target have drifted since this plan was written, adapt the TEST's fixture setup to the
real code, never adapt the spec's golden-thread guarantees).

- [ ] **Step 3: Commit**

```bash
git add tests/test_g5_golden.py
git commit -m "test(g5): golden threads — HTTP recipe == CLI result, llm/mcd 403, origin gating, student surface untouched"
```

---

### Task 6: frontend `lib/publishctl/recipe.ts`

**Files:**
- Create: `frontend/src/lib/publishctl/recipe.ts`
- Test: `frontend/src/lib/publishctl/recipe.test.ts`

- [ ] **Step 1: Write the failing tests**

```ts
// frontend/src/lib/publishctl/recipe.test.ts
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  approveSeedRequest, buildRequest, deriveStep, nextAssignmentToBuild, planRequest,
  type AssignmentLike,
} from "./recipe";

const ok = (body: unknown) =>
  Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as Response);
const bad = (code: number, detail = "boom") =>
  Promise.resolve({
    ok: false, status: code, json: () => Promise.resolve({ detail }),
  } as Response);

afterEach(() => vi.unstubAllGlobals());

describe("deriveStep (G5 stepper state)", () => {
  it("is 'plan' when there are no assignments for this seed yet", () => {
    expect(deriveStep([])).toBe("plan");
  });

  it("is 'approve' when any row is in-review", () => {
    const rows: AssignmentLike[] = [
      { id: "a1", pipeline: "revision", status: "in-review" },
      { id: "a2", pipeline: "deck", status: "approved" },
    ];
    expect(deriveStep(rows)).toBe("approve");
  });

  it("is 'build' when nothing is in-review but something is approved", () => {
    const rows: AssignmentLike[] = [
      { id: "a1", pipeline: "revision", status: "approved" },
      { id: "a2", pipeline: "deck", status: "captured" },
    ];
    expect(deriveStep(rows)).toBe("build");
  });

  it("is 'publish' when every row is terminal captured", () => {
    const rows: AssignmentLike[] = [
      { id: "a1", pipeline: "revision", status: "captured" },
      { id: "a2", pipeline: "deck", status: "captured" },
    ];
    expect(deriveStep(rows)).toBe("publish");
  });
});

describe("nextAssignmentToBuild", () => {
  it("returns the first approved row's id in lane order", () => {
    const rows: AssignmentLike[] = [
      { id: "a-deck", pipeline: "deck", status: "approved" },
      { id: "a-rev", pipeline: "revision", status: "approved" },
    ];
    // lane order (samagra/factory/lines.py _ORDER): revision before deck
    expect(nextAssignmentToBuild(rows)).toBe("a-rev");
  });

  it("returns null when nothing is approved", () => {
    expect(nextAssignmentToBuild([{ id: "a1", pipeline: "revision", status: "captured" }]))
      .toBeNull();
  });
});

describe("fetch wrappers", () => {
  it("planRequest posts seed_ref and returns proposals", async () => {
    const fetchMock = vi.fn().mockReturnValue(ok({ proposals: [{ line: "revision" }] }));
    vi.stubGlobal("fetch", fetchMock);
    const res = await planRequest("textbook:circular-motion");
    expect(res).toEqual({ proposals: [{ line: "revision" }] });
    expect(fetchMock).toHaveBeenCalledWith("/api/factory/plan", expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ seed_ref: "textbook:circular-motion" }),
    }));
  });

  it("planRequest throws the server detail on failure", async () => {
    vi.stubGlobal("fetch", vi.fn().mockReturnValue(bad(400, "seed_ref is required")));
    await expect(planRequest("")).rejects.toThrow("seed_ref is required");
  });

  it("approveSeedRequest posts seed_ref and returns the approved list", async () => {
    const fetchMock = vi.fn().mockReturnValue(ok({ seed_ref: "textbook:cm", approved: ["a1"] }));
    vi.stubGlobal("fetch", fetchMock);
    expect(await approveSeedRequest("textbook:cm")).toEqual({ seed_ref: "textbook:cm", approved: ["a1"] });
    expect(fetchMock).toHaveBeenCalledWith("/api/factory/approve-seed", expect.objectContaining({
      method: "POST", body: JSON.stringify({ seed_ref: "textbook:cm" }),
    }));
  });

  it("buildRequest posts assignment_id and returns the build result", async () => {
    const fetchMock = vi.fn().mockReturnValue(ok({ line: "revision", artifact_ref: "/x.html" }));
    vi.stubGlobal("fetch", fetchMock);
    expect(await buildRequest("a1")).toEqual({ line: "revision", artifact_ref: "/x.html" });
    expect(fetchMock).toHaveBeenCalledWith("/api/factory/build", expect.objectContaining({
      method: "POST", body: JSON.stringify({ assignment_id: "a1" }),
    }));
  });

  it("buildRequest throws the server detail (e.g. a kind-refusal 403) on failure", async () => {
    vi.stubGlobal("fetch", vi.fn().mockReturnValue(bad(403, "the mcd lane is CLI-only")));
    await expect(buildRequest("a1")).rejects.toThrow("the mcd lane is CLI-only");
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npx vitest run src/lib/publishctl/recipe.test.ts`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement**

```ts
// frontend/src/lib/publishctl/recipe.ts
// PURE stepper-state derivation for the G5 "Factory run" panel + thin typed fetch
// wrappers over the 3 new owner-gated endpoints. No React (headless-tested),
// mirroring the existing rows.ts convention in this same directory.

export interface AssignmentLike {
  id?: string;
  pipeline?: string;
  status?: string;
}

export type RecipeStep = "plan" | "approve" | "build" | "publish";

// Mirrors samagra/factory/lines.py's _ORDER — a deliberate TS<->Python duplication
// (like next_best.ts's LANE_ORDER precedent) so build-all always proposes the same
// next target across a re-render.
const _LANE_ORDER = ["revision", "lecture", "deck", "paper", "drill"];
const _laneRank = (p: string | undefined) => {
  const i = _LANE_ORDER.indexOf(p ?? "");
  return i === -1 ? 99 : i;
};

export function deriveStep(rows: AssignmentLike[] | null | undefined): RecipeStep {
  const list = Array.isArray(rows) ? rows : [];
  if (list.length === 0) return "plan";
  if (list.some((r) => r.status === "in-review")) return "approve";
  if (list.some((r) => r.status === "approved")) return "build";
  return "publish";
}

export function nextAssignmentToBuild(rows: AssignmentLike[] | null | undefined): string | null {
  const list = Array.isArray(rows) ? rows : [];
  const approved = list.filter((r) => r.status === "approved" && r.id);
  if (approved.length === 0) return null;
  approved.sort((a, b) => _laneRank(a.pipeline) - _laneRank(b.pipeline));
  return approved[0].id as string;
}

async function _postOrThrow<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    let detail = `HTTP ${r.status}`;
    try { const j = await r.json(); if (j?.detail) detail = String(j.detail); } catch { /* keep detail */ }
    throw new Error(detail);
  }
  return (await r.json()) as T;
}

export interface PlanProposal {
  seed_ref: string; line: string; expected_output: string;
  assignment_id?: string; reused?: boolean;
}
export interface PlanResponse { proposals: PlanProposal[]; }
export interface ApproveSeedResponse { seed_ref: string; approved: string[]; }
export interface BuildResponse {
  assignment_id?: string; line: string; artifact_ref: string; status?: string;
}

export function planRequest(seedRef: string): Promise<PlanResponse> {
  return _postOrThrow<PlanResponse>("/api/factory/plan", { seed_ref: seedRef });
}

export function approveSeedRequest(seedRef: string): Promise<ApproveSeedResponse> {
  return _postOrThrow<ApproveSeedResponse>("/api/factory/approve-seed", { seed_ref: seedRef });
}

export function buildRequest(assignmentId: string): Promise<BuildResponse> {
  return _postOrThrow<BuildResponse>("/api/factory/build", { assignment_id: assignmentId });
}
```

- [ ] **Step 4: Run to verify pass**

Run: `cd frontend && npx vitest run src/lib/publishctl/recipe.test.ts`
Expected: 12 passed.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/publishctl/recipe.ts frontend/src/lib/publishctl/recipe.test.ts
git commit -m "feat(g5): recipe.ts — pure stepper-state derivation + factory-run fetch wrappers"
```

---

### Task 7: Publish app — the "Factory run" stepper panel

**Files:**
- Modify: `frontend/src/apps/Publish/index.tsx`
- Test: `frontend/src/apps/Publish/index.test.tsx` (verify this file exists — if the
  Publish app's existing tests live under a different filename, e.g.
  `frontend/src/apps/Publish/Publish.test.tsx`, append there instead; the content below
  is what matters, not the exact path)

- [ ] **Step 1: Write the failing tests** (append to the existing Publish test file)

```tsx
// append to frontend/src/apps/Publish/index.test.tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import Publish from "./index";

const planMock = vi.fn();
const approveMock = vi.fn();
const buildMock = vi.fn();
vi.mock("../../lib/publishctl/recipe", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../lib/publishctl/recipe")>();
  return {
    ...actual,
    planRequest: (...a: unknown[]) => planMock(...a),
    approveSeedRequest: (...a: unknown[]) => approveMock(...a),
    buildRequest: (...a: unknown[]) => buildMock(...a),
  };
});

afterEach(() => vi.clearAllMocks());

describe("Factory run stepper panel (G5)", () => {
  it("renders a chapter-slug input and only the Plan button enabled with an empty slug", () => {
    render(<Publish />);
    expect(screen.getByTestId("factory-run-slug")).toBeTruthy();
    expect(screen.getByTestId("factory-run-plan")).toBeTruthy();
  });

  it("clicking Plan calls planRequest with the textbook:-prefixed slug and shows a result line", async () => {
    planMock.mockResolvedValue({ proposals: [
      { seed_ref: "textbook:circular-motion", line: "revision", expected_output: "x", assignment_id: "a1" },
      { seed_ref: "textbook:circular-motion", line: "deck", expected_output: "x", assignment_id: "a2" },
    ]});
    render(<Publish />);
    fireEvent.change(screen.getByTestId("factory-run-slug"), { target: { value: "circular-motion" } });
    fireEvent.click(screen.getByTestId("factory-run-plan"));
    await waitFor(() => expect(planMock).toHaveBeenCalledWith("textbook:circular-motion"));
    expect(await screen.findByTestId("factory-run-result")).toBeTruthy();
  });

  it("shows an error line when a step fails", async () => {
    planMock.mockRejectedValue(new Error("seed_ref is required"));
    render(<Publish />);
    fireEvent.change(screen.getByTestId("factory-run-slug"), { target: { value: "circular-motion" } });
    fireEvent.click(screen.getByTestId("factory-run-plan"));
    expect(await screen.findByTestId("factory-run-error")).toHaveTextContent("seed_ref is required");
  });

  it("build-all loops buildRequest until nextAssignmentToBuild returns null", async () => {
    // Simulate: after planning, the panel independently refetches /api/assignments
    // via useApi (already mocked at the module boundary by the surrounding test
    // file's existing useApi mock, per this file's established pattern) to derive
    // approved rows; this test only asserts the LOOP mechanics once build is
    // reachable — wire the useApi mock's returned rows to 2 approved assignments
    // and assert buildRequest is called twice, then no more.
    buildMock.mockResolvedValueOnce({ line: "revision", artifact_ref: "/a.html" })
             .mockResolvedValueOnce({ line: "deck", artifact_ref: "/b.html" });
    // NOTE: the exact useApi-mock wiring depends on how this test file already
    // mocks useApi for the existing captured/published table tests (see the top of
    // this file, established by the G3 plan). Reuse that SAME mock and simply vary
    // its returned `assignments` payload per test — do not introduce a second,
    // divergent mocking mechanism.
  });
});
```

> NOTE on the last test: the exact plumbing of `useApi` mocking is file-specific and
> was NOT re-derived here — verify against the real `frontend/src/apps/Publish/
> index.test.tsx` (or wherever the G3 Publish tests live) before writing this test's
> body, and adapt the TEST to that file's existing mock pattern; the ASSERTION that
> matters (buildRequest called once per approved row, in lane order, until none
> remain) must not be weakened.

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npx vitest run src/apps/Publish/`
Expected: the new describe block FAILS (no such testids yet); the pre-existing Publish
tests still PASS (regression baseline).

- [ ] **Step 3: Implement**

In `frontend/src/apps/Publish/index.tsx`:

(a) Imports — add after the existing `rows` import:

```tsx
import { useState } from "react";
import {
  approveSeedRequest, buildRequest, deriveStep, nextAssignmentToBuild, planRequest,
  type AssignmentLike as RecipeAssignmentLike,
} from "../../lib/publishctl/recipe";
```

(NOTE: `useState` is likely already imported at the top of this file per the G3 plan's
Task 11 — do not double-import; merge into the existing `import { useState } from
"react"` line if present.)

(b) State + handlers — inside the `Publish()` component, after the existing
`asg`/`man`/`rows` derivations:

```tsx
  const [slug, setSlug] = useState("");
  const [stepResult, setStepResult] = useState<string | null>(null);
  const [stepError, setStepError] = useState<string | null>(null);

  const seedRef = `textbook:${slug.trim()}`;
  const rowsForSeed: RecipeAssignmentLike[] = (asg.data?.assignments ?? [])
    .filter((a) => (a as { seed_ref?: string }).seed_ref === seedRef)
    .map((a) => ({
      id: (a as { id?: string }).id, pipeline: (a as { pipeline?: string }).pipeline,
      status: (a as { status?: string }).status,
    }));
  const step = slug.trim() ? deriveStep(rowsForSeed) : "plan";

  async function doPlan() {
    setStepError(null); setStepResult(null);
    try {
      const r = await planRequest(seedRef);
      setStepResult(`planned ${r.proposals.length} lane(s)`);
      setNonce((n) => n + 1);           // refetch /api/assignments (existing G3 pattern)
    } catch (e) { setStepError(String((e as Error).message ?? e)); }
  }

  async function doApproveSeed() {
    setStepError(null); setStepResult(null);
    try {
      const r = await approveSeedRequest(seedRef);
      setStepResult(`approved ${r.approved.length}`);
      setNonce((n) => n + 1);
    } catch (e) { setStepError(String((e as Error).message ?? e)); }
  }

  async function doBuildAll() {
    setStepError(null); setStepResult(null);
    let built = 0;
    let current = rowsForSeed;
    let next = nextAssignmentToBuild(current);
    while (next) {
      try {
        await buildRequest(next);
        built += 1;
      } catch (e) {
        setStepError(`built ${built} then failed: ${String((e as Error).message ?? e)}`);
        setNonce((n) => n + 1);
        return;
      }
      // Re-derive from the freshly-known state: mark this id as no longer
      // approved so the loop terminates without waiting on a network refetch
      // mid-loop (the panel still triggers ONE refetch at the end for the
      // captured/published table + stepper to reflect reality).
      current = current.map((r) => (r.id === next ? { ...r, status: "captured" } : r));
      next = nextAssignmentToBuild(current);
    }
    setStepResult(`built ${built}`);
    setNonce((n) => n + 1);
  }
```

(c) The panel JSX — inserted above the existing captured/published `<table>` (after the
existing `<p>` intro paragraph, before the `{rows.length === 0 ? (` block):

```tsx
      <div style={{ border: `1px solid #e6e6ef`, borderRadius: 8, padding: 12, marginBottom: 16 }}>
        <h3 style={{ margin: "0 0 8px", fontSize: 15 }}>Factory run</h3>
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <input data-testid="factory-run-slug" value={slug}
            onChange={(e) => setSlug(e.target.value)}
            placeholder="chapter slug, e.g. circular-motion"
            style={{ padding: "5px 8px", border: "1px solid #e6e6ef", borderRadius: 6, minWidth: 220 }} />
          <button data-testid="factory-run-plan" disabled={!slug.trim() || step !== "plan"}
            onClick={doPlan}
            style={{ border: 0, background: step === "plan" ? "#2563eb" : "#c7d2fe",
              color: "#fff", borderRadius: 6, padding: "5px 10px", cursor: "pointer" }}>
            Plan
          </button>
          <button data-testid="factory-run-approve" disabled={!slug.trim() || step !== "approve"}
            onClick={doApproveSeed}
            style={{ border: 0, background: step === "approve" ? "#2563eb" : "#c7d2fe",
              color: "#fff", borderRadius: 6, padding: "5px 10px", cursor: "pointer" }}>
            Approve seed
          </button>
          <button data-testid="factory-run-build" disabled={!slug.trim() || step !== "build"}
            onClick={doBuildAll}
            style={{ border: 0, background: step === "build" ? "#2563eb" : "#c7d2fe",
              color: "#fff", borderRadius: 6, padding: "5px 10px", cursor: "pointer" }}>
            Build all
          </button>
          <button data-testid="factory-run-publish" disabled={!slug.trim() || step !== "publish"}
            onClick={() => act("/api/factory/publish", slug.trim())}
            style={{ border: 0, background: step === "publish" ? "#16a34a" : "#bbf7d0",
              color: "#fff", borderRadius: 6, padding: "5px 10px", cursor: "pointer" }}>
            Publish
          </button>
        </div>
        {stepResult ? (
          <p data-testid="factory-run-result" style={{ color: "#16a34a", margin: "8px 0 0" }}>{stepResult}</p>
        ) : null}
        {stepError ? (
          <p data-testid="factory-run-error" role="alert" style={{ color: "#b91c1c", margin: "8px 0 0" }}>{stepError}</p>
        ) : null}
      </div>
```

> NOTE: the `Publish` step button deliberately calls the EXISTING `act(...)` handler
> already defined in this file (G3's `act("/api/factory/publish", chapter)`, per-row) —
> it is not a new publish code path, just a second call site for the same function
> (F-G5-1/§5.2: "the stepper panel's Publish button is literally the same handler the
> per-row Publish button already calls"). If `act`'s signature differs from
> `act(path, chapter)` in the real current file, adapt this call site to match — never
> duplicate a second publish implementation.

- [ ] **Step 4: Run to verify pass**

Run: `cd frontend && npx vitest run src/apps/Publish/` — ALL green (new + pre-existing).
Then `cd frontend && npx tsc --noEmit`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/apps/Publish/index.tsx frontend/src/apps/Publish/index.test.tsx
git commit -m "feat(g5): Factory run stepper panel in the Publish app (plan/approve/build-all/publish)"
```

---

### Task 8: full verification gate + docs/trackers + DEC-14

- [ ] **Step 1: Full backend suite** — `python -m pytest -q` — expected: baseline 637 +
  ~26 new (Task 1: 2, Task 2: 6, Task 3: 4, Task 4: 7, Task 5: 4), 1 skip, 0 failures.
- [ ] **Step 2: Full frontend gate** — `cd frontend && npx vitest run && npx tsc --noEmit && npm run build` —
  expected: baseline 613 + ~16 new (Task 6: 12, Task 7: ~4), tsc + build green.
- [ ] **Step 3: Manual smoke** (optional but recommended before the review gate) — with
  the samagra server restarted on this branch, exercise the stepper panel against a
  captured-but-unpublished chapter (or a fresh `textbook:` seed) end to end in a
  browser: Plan → Approve seed → Build all → Publish, confirming `/api/assignments` and
  `/api/published` reflect each step and `/learn` is unaffected.
- [ ] **Step 4: Update trackers** — CLAUDE.md G-status banner + HANDOFF.md (banner +
  append DEC-14 to the decisions block, text from spec §9) + STATUS.html + SUMMARY.html
  per the house prepend-banner convention; note the owner follow-up: the samagra server
  needs a restart post-merge before the 3 new endpoints exist live; the Chairman should
  run the recipe once for real through the GUI (the first GUI-driven throughput run) as
  a smoke test.
- [ ] **Step 5: Commit**

```bash
git add -A docs STATUS.html HANDOFF.md SUMMARY.html CLAUDE.md
git commit -m "docs(g5): status + trackers + DEC-14 for the factory-run-over-HTTP slice"
```

---

### Task 9: review gate (do NOT merge before these)

Per spec §10 and the DEC-7 pattern for every prior write boundary:

- [ ] **Step 1:** Dedicated Codex pre-merge review of the three new endpoints —
  particularly the llm/mcd kind-refusal boundary (`api_factory_build`) and the 3 new
  `_PROTECTED_POSTS` entries — save as
  `docs/codex-reviews/30-g5-factory-run-http-premerge.report.md`.
- [ ] **Step 2:** Adversarial multi-lens final review (Workflow, 4 lenses × independent
  refute-verify): firewall/write-mechanism (no new logic inside `run.py`; llm/mcd
  structurally unreachable, proven by the zero-call spy assertions in Tasks 4-5) ·
  security (origin gating verbatim; no privilege widening; the kind check cannot be
  bypassed by a hand-crafted request) · spec-fidelity (§2 forks F-G5-1/2/3 + §7 golden
  threads) · separate-entity (student surface untouched — Task 5's golden thread +
  a diff review confirming zero changes under `samagra/pratham/` or `/api/learn/*`).
- [ ] **Step 3:** Remediate findings TDD → re-run the full gate → `git checkout main &&
  git merge --ff-only feature/factory-run-http && git push origin main`.

---

## Self-Review

**1. Spec coverage:** §4.1 `POST /api/factory/plan` → Task 2; §4.2
`POST /api/factory/approve-seed` → Task 3; §4.3 `POST /api/factory/build` (kind
refusal + error mapping) → Task 4; §4.4 (no new GET) → correctly introduces no task;
§5.1 `recipe.ts` → Task 6; §5.2 the stepper panel → Task 7; §6 stepper states → encoded
in `deriveStep`'s tests (Task 6) and the panel's button-enabled logic (Task 7); §7
golden threads (1-4) → Task 5; §8 security model → asserted across Tasks 1 (origin
gate), 4 (kind refusal), 5 (student surface); §9 DEC-14 → Task 8 Step 4; §10 review
gate → Task 9. §12/§13 non-goals introduce no tasks (correct — no `scan`/`reopen`/
enroll-over-HTTP task exists; no new app task exists).

**2. Placeholder scan:** every code step shows complete code; every command has an
expected result. Three explicit "verify against reality, adapt the TEST never the
module" notes are called out where this plan could not directly re-read a live file at
write time: Task 4 Step 2 (governance `store.py` kwarg names), Task 4 Step 3
(`connect_ro` existence), and Task 7 Step 1/3 (the exact `useApi` mock plumbing and
`act()` signature already present in the real `Publish/index.tsx`/its test file) — each
names exactly what to re-check and what must NOT be weakened if the real code differs.

**3. Type consistency:** `run.plan(seed_ref, dry=False)` (Task 2) matches the verified
signature `run.plan(seed_ref: str, dry: bool = True, lane: str | None = None) ->
list[dict]` (`samagra/factory/run.py:147`); `run.approve_seed(seed_ref) -> dict` (Task
3) matches `run.py:257`; `run.build(assignment_id) -> dict` (Task 4) matches
`run.py:355`; the response field names `{proposals}` / `{seed_ref, approved}` /
`{line, artifact_ref, ...}` (Tasks 2-4) match the CLI's own field access
(`__main__.py:142-159`) and are consumed identically by `recipe.ts`'s
`PlanResponse`/`ApproveSeedResponse`/`BuildResponse` (Task 6) and the panel's handlers
(Task 7); `LINES[pipeline].kind in {"llm","mcd"}` (Task 4) matches the registry at
`samagra/factory/lines.py:25-42` (`seed`→`mcd`, `samadhan`→`llm`); the lane-order list
in `recipe.ts`'s `_LANE_ORDER` (Task 6) mirrors `samagra/factory/lines.py`'s `_ORDER`
(the deterministic 5 local/qx lanes only — `seed`/`samadhan` deliberately excluded,
since `nextAssignmentToBuild` only ever operates on GUI-planned, hence
deterministic-lane, assignments in practice, though the function itself does not
special-case lane kind — the actual 403 refusal lives server-side per Task 4, so a
stray llm/mcd row in the derived rows would simply rank last (index 99) and, if ever
selected, fail loudly with the 403 `recipe.ts`'s `buildRequest` already surfaces as a
thrown error, per Task 6's own test for that case).
