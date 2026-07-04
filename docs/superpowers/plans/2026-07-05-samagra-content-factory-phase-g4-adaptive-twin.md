# SAMAGRA Content Factory — Phase G4 (adaptive student twin, v1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give a signed-in `/learn` student per-`(chapter, lane)` "Mark done" progress (SAMAGRA's first authenticated student write, into `pratham.db` ONLY) and a deterministic, demand-ranked session-gated "What's next" queue — while anonymous reading stays byte-identical and every standing invariant holds.

**Architecture:** One new `progress` table in `pratham.db` (PK `(student_id, chapter, lane)`, idempotent upsert). Write path: `POST /api/learn/progress` — session-required, `(chapter, lane)` validated against the LIVE published manifest **before** any write (404-before-write), per-student rate limit, `samagra/pratham/` never imports factory code. Read path: `GET /api/learn/next` — session-required; a PURE ranker `samagra/factory/coverage/next_best.py` (sibling of `gaps.rank_gaps`, no I/O) is fed by an API-layer glue `samagra/api/learn_next.py` that joins the published manifest × chapter demand (`concept_graph.db` via the existing `connect_ro`, `FileNotFoundError` → unranked) × the student's done-set. Reader UI additions are wholly `{student && …}`-gated.

**Tech Stack:** Python 3.11, FastAPI, sqlite3, pytest + TestClient; React + TypeScript + Vite, vitest + @testing-library/react.

**Spec:** `docs/superpowers/specs/2026-07-05-samagra-content-factory-phase-g4-adaptive-twin-design.md` (forks ruled by deliberation run `wf_df1f8da3-4d4`; Chairman veto reverses any ruling).
**Branch:** `feature/content-factory-phase-g4` (create from `main` @ `1f51a04`+).
**Baseline gate:** 608 pytest passed + 1 skip (opt-in live-LLM smoke) · 604 vitest (72 files) · tsc + build green.

---

## File Structure

**Backend (modify):**
- `samagra/pratham/store.py` — `progress` DDL (SCHEMA_VERSION 1→2, additive) + `mark_progress`/`list_progress`.
- `samagra/pratham/service.py` — `_PROGRESS_LIMITER` + `mark_done`/`progress_for`.
- `samagra/api/app.py` — `POST /api/learn/progress` + `GET /api/learn/next` (in the G3 `/api/learn/*` block, after `api_learn_me`).
- `tests/conftest.py` — clear the new limiter in the existing isolation fixture.

**Backend (create):**
- `samagra/factory/coverage/next_best.py` — PURE student-queue ranker (no sqlite import).
- `samagra/api/learn_next.py` — the glue joining manifest × demand × done-set (the ONLY new module importing both worlds).

**Frontend (create):**
- `frontend/src/lib/pratham/plan.ts` — typed fetch wrappers (`nextRequest`, `markDoneRequest`).
- `frontend/src/apps/Pratham/adaptive.test.tsx` — anonymous-invariance regression + signed-in UI tests.

**Frontend (modify):**
- `frontend/src/apps/Pratham/index.tsx` — student-gated "Mark done" + "What's next" strip.

**Tests (create):** `tests/test_pratham_progress_store.py`, `tests/test_pratham_progress_service.py`, `tests/test_next_best.py`, `tests/test_learn_next_glue.py`, `tests/test_api_learn_progress.py`, `tests/test_api_learn_next.py`, `tests/test_g4_golden.py`, `frontend/src/lib/pratham/plan.test.ts`.

**No changes to:** `governance/`, `factory/publish/`, `factory/dispatch|run|lines`, `origin_auth.py` (the new endpoints are deliberately public-prefix, session-gated), `registry.ts`/`App.tsx` (no new app).

---

### Task 0: Branch

- [ ] **Step 1: Create the branch**

```bash
git checkout main && git pull && git checkout -b feature/content-factory-phase-g4
```

- [ ] **Step 2: Commit the spec + this plan** (if not already committed)

```bash
git add docs/superpowers/specs/2026-07-05-samagra-content-factory-phase-g4-adaptive-twin-design.md docs/superpowers/plans/2026-07-05-samagra-content-factory-phase-g4-adaptive-twin.md
git commit -m "docs(g4): Phase G4 adaptive-twin design (proposed) + implementation plan"
```

---

### Task 1: `progress` table in pratham.db

**Files:**
- Modify: `samagra/pratham/store.py` (DDL at ~line 16, `SCHEMA_VERSION` at line 14, new functions after `delete_sessions_for_student`)
- Test: `tests/test_pratham_progress_store.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_pratham_progress_store.py
import sqlite3

from samagra import config
from samagra.pratham import store


def test_list_progress_empty():
    assert store.list_progress("stu_nobody") == []


def test_mark_and_list_roundtrip():
    store.mark_progress("stu_a", "circular-motion", "revision", "2026-07-05T10:00:00Z")
    rows = store.list_progress("stu_a")
    assert len(rows) == 1
    r = rows[0]
    assert (r["chapter"], r["lane"], r["status"]) == ("circular-motion", "revision", "done")
    assert r["marked_at"] == "2026-07-05T10:00:00Z"
    assert store.list_progress("stu_b") == []          # never another student's rows


def test_mark_progress_is_idempotent_upsert():
    store.mark_progress("stu_a", "circular-motion", "revision", "2026-07-05T10:00:00Z")
    store.mark_progress("stu_a", "circular-motion", "revision", "2026-07-05T11:00:00Z")
    rows = store.list_progress("stu_a")
    assert len(rows) == 1                              # PK prevents duplicates
    assert rows[0]["marked_at"] == "2026-07-05T11:00:00Z"


_V1_DDL = """
CREATE TABLE IF NOT EXISTS students (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, code_hash TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active', created_at TEXT NOT NULL, last_login_at TEXT);
CREATE TABLE IF NOT EXISTS sessions (
  id_hash TEXT PRIMARY KEY, student_id TEXT NOT NULL,
  created_at TEXT NOT NULL, expires_at TEXT NOT NULL);
"""


def test_existing_v1_db_gains_progress_table_and_keeps_rows():
    # Build a REAL schema-v1 pratham.db (as G3 shipped it), then prove the additive
    # upgrade: ensure_tables() adds `progress` without touching existing rows.
    con = sqlite3.connect(config.PRATHAM_DB)
    con.executescript(_V1_DDL)
    con.execute("INSERT INTO students (id, name, code_hash, status, created_at) "
                "VALUES ('stu_old', 'Asha', 'h', 'active', '2026-06-28T00:00:00Z')")
    con.execute("PRAGMA user_version = 1")
    con.commit(); con.close()
    store._INITIALIZED.clear()

    store.mark_progress("stu_old", "gravitation", "deck", "2026-07-05T10:00:00Z")

    assert store.get_student("stu_old")["name"] == "Asha"     # old rows survive
    assert store.list_progress("stu_old")[0]["chapter"] == "gravitation"
    con = sqlite3.connect(config.PRATHAM_DB)
    assert con.execute("PRAGMA user_version").fetchone()[0] == 2
    con.close()
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_pratham_progress_store.py -q`
Expected: FAIL — `AttributeError: module ... has no attribute 'list_progress'`.

- [ ] **Step 3: Implement**

In `samagra/pratham/store.py`: change line 14 to `SCHEMA_VERSION = 2`; append to the `DDL` string (before the closing `"""`):

```sql
CREATE TABLE IF NOT EXISTS progress (
  student_id TEXT NOT NULL,
  chapter    TEXT NOT NULL,
  lane       TEXT NOT NULL,
  status     TEXT NOT NULL DEFAULT 'done',
  marked_at  TEXT NOT NULL,
  PRIMARY KEY (student_id, chapter, lane)
);
CREATE INDEX IF NOT EXISTS idx_progress_student ON progress(student_id);
```

Append after `delete_sessions_for_student`:

```python
# --- progress (G4) ----------------------------------------------------
def mark_progress(student_id: str, chapter: str, lane: str, marked_at: str) -> None:
    """Idempotent 'done' upsert — the PK makes a re-mark update marked_at, never
    duplicate. v1 only ever writes status='done' (the column is the F-G4-3
    escape hatch: a future 'again' is a value, not a migration)."""
    _exec("INSERT INTO progress (student_id, chapter, lane, status, marked_at) "
          "VALUES (?, ?, ?, 'done', ?) "
          "ON CONFLICT(student_id, chapter, lane) "
          "DO UPDATE SET status = 'done', marked_at = excluded.marked_at",
          (student_id, chapter, lane, marked_at))


def list_progress(student_id: str) -> list[dict]:
    return _query_all("SELECT * FROM progress WHERE student_id = ? ORDER BY chapter, lane",
                      (student_id,))
```

- [ ] **Step 4: Run to verify pass** — `python -m pytest tests/test_pratham_progress_store.py -q` → 4 passed. Also run `python -m pytest tests/test_pratham_store.py tests/test_pratham_service.py -q` to prove G3 store behavior is untouched.

- [ ] **Step 5: Commit**

```bash
git add samagra/pratham/store.py tests/test_pratham_progress_store.py
git commit -m "feat(g4): progress table in pratham.db — additive schema v2 + idempotent upsert"
```

---

### Task 2: service layer — rate-limited `mark_done`

**Files:**
- Modify: `samagra/pratham/service.py` (after `revoke`), `tests/conftest.py` (~line 42)
- Test: `tests/test_pratham_progress_service.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_pratham_progress_service.py
from samagra.pratham import identity, service, store


def test_mark_done_writes_a_done_row():
    assert service.mark_done("stu_a", "circular-motion", "revision") is True
    rows = store.list_progress("stu_a")
    assert len(rows) == 1 and rows[0]["status"] == "done"
    assert rows[0]["marked_at"]          # stamped via identity.now_iso()


def test_mark_done_rate_limited_returns_false_and_does_not_write(monkeypatch):
    monkeypatch.setattr(service, "_PROGRESS_LIMITER",
                        identity.RateLimiter(max_attempts=1, window_seconds=60))
    assert service.mark_done("stu_a", "c1", "revision", now_epoch=1000.0) is True
    assert service.mark_done("stu_a", "c2", "revision", now_epoch=1001.0) is False
    assert len(store.list_progress("stu_a")) == 1     # the refused mark never wrote


def test_progress_for_delegates_to_store():
    service.mark_done("stu_a", "gravitation", "deck")
    assert service.progress_for("stu_a")[0]["chapter"] == "gravitation"
    assert service.progress_for("stu_b") == []
```

- [ ] **Step 2: Run to verify failure** — `python -m pytest tests/test_pratham_progress_service.py -q` → FAIL (`no attribute 'mark_done'`).

- [ ] **Step 3: Implement**

Append to `samagra/pratham/service.py`:

```python
# G4: progress marks. Keyed on the AUTHENTICATED student_id (non-spoofable, unlike
# login's Cf-Connecting-Ip key) — looser than login's limiter because marking is a
# legitimate high-frequency study action; still bounds a buggy client.
_PROGRESS_LIMITER = identity.RateLimiter(max_attempts=60, window_seconds=60)


def mark_done(student_id: str, chapter: str, lane: str, *,
              now_epoch: float | None = None) -> bool:
    """Upsert a 'done' mark. False when rate-limited (no write). The (chapter, lane)
    pair MUST already be validated against the live published manifest by the caller
    (the API layer) — this module never imports factory code (the isolation firewall)."""
    now_epoch = time.time() if now_epoch is None else now_epoch
    if not _PROGRESS_LIMITER.allow(student_id, now_epoch):
        return False
    store.mark_progress(student_id, chapter, lane, identity.now_iso())
    return True


def progress_for(student_id: str) -> list[dict]:
    return store.list_progress(student_id)
```

In `tests/conftest.py`, after `_pratham_service._LIMITER._hits.clear()` (line 42) add:

```python
        _pratham_service._PROGRESS_LIMITER._hits.clear()
```

- [ ] **Step 4: Run to verify pass** — `python -m pytest tests/test_pratham_progress_service.py -q` → 3 passed.

- [ ] **Step 5: Commit**

```bash
git add samagra/pratham/service.py tests/test_pratham_progress_service.py tests/conftest.py
git commit -m "feat(g4): service.mark_done — per-student rate-limited progress writes"
```

---

### Task 3: PURE ranker `next_best.rank_next`

**Files:**
- Create: `samagra/factory/coverage/next_best.py`
- Test: `tests/test_next_best.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_next_best.py
from samagra.factory.coverage import next_best

_PUB = [
    {"chapter": "circular-motion", "title": "Circular Motion", "lanes": ["revision", "deck"]},
    {"chapter": "gravitation", "title": "Gravitation", "lanes": ["revision"]},
]


def test_empty_world_is_empty():
    assert next_best.rank_next([], {}, set()) == []


def test_done_pairs_are_subtracted():
    q = next_best.rank_next(_PUB, {}, {("circular-motion", "revision")})
    assert ("circular-motion", "revision") not in {(g["chapter"], g["lane"]) for g in q}
    assert len(q) == 2


def test_demand_ranks_chapters_and_reason_reflects_it():
    q = next_best.rank_next(_PUB, {"gravitation": 900}, set())
    assert (q[0]["chapter"], q[0]["reason"], q[0]["score"]) == ("gravitation", "high-demand", 900)
    assert q[-1]["reason"] == "new"                    # unscored chapters rank after


def test_lane_priority_breaks_ties_saar_first():
    q = next_best.rank_next([_PUB[0]], {}, set())
    assert [g["lane"] for g in q] == ["revision", "deck"]   # mirrors LANE_ORDER


def test_queue_caps_and_ranks():
    pub = [{"chapter": f"c{i:02d}", "title": f"C{i}", "lanes": ["revision", "deck"]}
           for i in range(10)]
    q = next_best.rank_next(pub, {}, set())
    assert len(q) == next_best._QUEUE_SIZE
    assert [g["rank"] for g in q] == list(range(1, next_best._QUEUE_SIZE + 1))


def test_deterministic():
    a = next_best.rank_next(_PUB, {"gravitation": 5}, {("circular-motion", "deck")})
    b = next_best.rank_next(_PUB, {"gravitation": 5}, {("circular-motion", "deck")})
    assert a == b
```

- [ ] **Step 2: Run to verify failure** — `python -m pytest tests/test_next_best.py -q` → FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement**

```python
# samagra/factory/coverage/next_best.py
"""PURE student what's-next ranker (G4) — the student-facing sibling of gaps.rank_gaps.

Ranks the published (chapter, lane) inventory a student has NOT yet marked done, by
the chapter's summed concept demand. Deterministic Tier-1 (no LLM, no I/O — this
module never imports sqlite3; the API-layer glue feeds it plain dicts/sets).
"""
from __future__ import annotations

_QUEUE_SIZE = 8

# Saar-led study order — deliberately mirrors LANE_ORDER in
# frontend/src/lib/published/manifest.ts (a TS<->Python duplication; keep in sync).
_LANE_PRIORITY = {lane: i for i, lane in enumerate(
    ["revision", "lecture", "deck", "paper", "drill", "samadhan"])}


def rank_next(published: list[dict], chapter_demand: dict[str, int],
              done_pairs: set[tuple[str, str]], *, top: int = _QUEUE_SIZE) -> list[dict]:
    """published: [{chapter, title, lanes: [str]}] (from the manifest, via the glue).
    chapter_demand: {chapter_slug: summed concept demand} ({} when the graph is unbuilt).
    done_pairs: this student's marked (chapter, lane) set (empty for a new student)."""
    items: list[dict] = []
    for ch in published:
        slug = ch.get("chapter") or ""
        for lane in ch.get("lanes", []):
            if not slug or not lane or (slug, lane) in done_pairs:
                continue
            score = int(chapter_demand.get(slug, 0))
            items.append({
                "chapter": slug, "title": ch.get("title") or slug, "lane": lane,
                "score": score, "reason": "high-demand" if score > 0 else "new",
            })
    items.sort(key=lambda g: (-g["score"], _LANE_PRIORITY.get(g["lane"], 99), g["chapter"]))
    del items[top:]
    for i, g in enumerate(items, 1):
        g["rank"] = i
    return items
```

- [ ] **Step 4: Run to verify pass** — `python -m pytest tests/test_next_best.py -q` → 6 passed.

- [ ] **Step 5: Commit**

```bash
git add samagra/factory/coverage/next_best.py tests/test_next_best.py
git commit -m "feat(g4): pure deterministic what's-next ranker (demand x published minus done)"
```

---

### Task 4: API-layer glue `learn_next.next_payload`

**Files:**
- Create: `samagra/api/learn_next.py`
- Test: `tests/test_learn_next_glue.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_learn_next_glue.py
from samagra import config
from samagra.api import learn_next
from samagra.factory.coverage import store as cov_store
from samagra.factory.publish import read
from samagra.pratham import service

_MAN = {"chapters": {
    "circular-motion": {"title": "Circular Motion",
                        "artifacts": [{"lane": "revision"}, {"lane": "deck"}]},
    "gravitation": {"title": "Gravitation", "artifacts": [{"lane": "revision"}]},
}}


def test_empty_world_yields_empty_payload(monkeypatch):
    monkeypatch.setattr(read, "published_manifest", lambda: {"chapters": {}})
    assert learn_next.next_payload("stu_a") == {"queue": [], "done": []}


def test_unbuilt_concept_graph_degrades_to_unranked(monkeypatch, tmp_path):
    monkeypatch.setattr(read, "published_manifest", lambda: _MAN)
    monkeypatch.setattr(config, "CONCEPT_GRAPH_DB", tmp_path / "absent.db", raising=False)
    p = learn_next.next_payload("stu_a")
    assert len(p["queue"]) == 3 and all(g["score"] == 0 for g in p["queue"])


def test_built_graph_scores_and_done_subtracts(monkeypatch, tmp_path):
    monkeypatch.setattr(read, "published_manifest", lambda: _MAN)
    db = tmp_path / "graph.db"
    monkeypatch.setattr(config, "CONCEPT_GRAPH_DB", db, raising=False)
    conn = cov_store.connect(db)
    cov_store.init_schema(conn)
    conn.execute("INSERT INTO concept VALUES (1, 'gravitation', 'physics.gravitation', 700, 3)")
    conn.execute("INSERT INTO concept_chapter VALUES (1, 'gravitation', 'fts', 1.0)")
    conn.commit(); conn.close()

    service.mark_done("stu_a", "circular-motion", "revision")
    p = learn_next.next_payload("stu_a")

    pairs = {(g["chapter"], g["lane"]) for g in p["queue"]}
    assert ("circular-motion", "revision") not in pairs          # done subtracted
    assert p["queue"][0]["chapter"] == "gravitation"             # demand-ranked first
    assert p["queue"][0]["score"] == 700
    assert p["done"][0]["chapter"] == "circular-motion"          # done rides along
```

- [ ] **Step 2: Run to verify failure** — `python -m pytest tests/test_learn_next_glue.py -q` → FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement**

```python
# samagra/api/learn_next.py
"""GLUE for GET /api/learn/next (G4) — the ONE module that joins the three read-only
sources. Lives in the API layer on purpose: samagra/pratham/ must never import
samagra/factory/ (the DEC-12/13 isolation firewall), and the pure ranker never does
I/O. concept_graph.db is opened strictly via the existing read-only connect_ro; an
absent/unbuilt graph degrades to an unranked queue (score 0), never an error."""
from __future__ import annotations

from ..factory.coverage import next_best
from ..factory.coverage import store as coverage_store
from ..factory.publish import read
from ..pratham import service


def _published_inventory() -> list[dict]:
    man = read.published_manifest() or {}
    out: list[dict] = []
    for slug, ch in sorted((man.get("chapters") or {}).items()):
        lanes = sorted({a.get("lane") for a in (ch.get("artifacts") or []) if a.get("lane")})
        if lanes:
            out.append({"chapter": slug, "title": (ch.get("title") or slug), "lanes": lanes})
    return out


def _chapter_demand() -> dict[str, int]:
    try:
        conn = coverage_store.connect_ro()
    except FileNotFoundError:
        return {}
    try:
        rows = conn.execute(
            "SELECT cc.chapter_slug AS slug, SUM(c.demand_size) AS demand "
            "FROM concept_chapter cc JOIN concept c ON c.concept_id = cc.concept_id "
            "GROUP BY cc.chapter_slug").fetchall()
        return {r["slug"]: int(r["demand"] or 0) for r in rows}
    finally:
        conn.close()


def next_payload(student_id: str) -> dict:
    """{queue: ranked not-done published pairs, done: the student's own rows} —
    `done` rides along so the reader learns button state in one round trip."""
    done = service.progress_for(student_id)
    done_pairs = {(d["chapter"], d["lane"]) for d in done}
    queue = next_best.rank_next(_published_inventory(), _chapter_demand(), done_pairs)
    return {"queue": queue, "done": done}
```

> NOTE: `coverage_store.connect_ro()` reads `config.CONCEPT_GRAPH_DB` at call time when
> called with no argument — verify this against `samagra/factory/coverage/store.py:53`
> (it does: `path = Path(db_path) if db_path is not None else config.CONCEPT_GRAPH_DB`).

- [ ] **Step 4: Run to verify pass** — `python -m pytest tests/test_learn_next_glue.py -q` → 3 passed.

- [ ] **Step 5: Commit**

```bash
git add samagra/api/learn_next.py tests/test_learn_next_glue.py
git commit -m "feat(g4): learn_next glue — manifest x demand x done-set, graceful-empty"
```

---

### Task 5: `POST /api/learn/progress` — the first authenticated student write

**Files:**
- Modify: `samagra/api/app.py` (append to the G3 `/api/learn/*` block, after `api_learn_me` ~line 334)
- Test: `tests/test_api_learn_progress.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_api_learn_progress.py
from fastapi.testclient import TestClient

from samagra import config
from samagra.api import app as api_app
from samagra.api import origin_auth
from samagra.factory.publish import read
from samagra.pratham import identity, service, store

_MAN = {"chapters": {"circular-motion": {"title": "Circular Motion",
                                         "artifacts": [{"lane": "revision"}]}}}


def _signed_in_client(monkeypatch):
    monkeypatch.setattr(read, "published_manifest", lambda: _MAN)
    c = TestClient(api_app.app)
    code = service.enroll("Asha")["code"]
    assert c.post("/api/learn/login", json={"code": code}).status_code == 200
    return c


def test_progress_is_public_prefix_not_origin_gated():
    # Session-gated, NOT origin-gated (student self-service, like /api/learn/me).
    assert origin_auth.is_protected("POST", "/api/learn/progress") is False
    assert origin_auth.is_protected("GET", "/api/learn/next") is False


def test_anonymous_is_401(monkeypatch):
    monkeypatch.setattr(read, "published_manifest", lambda: _MAN)
    c = TestClient(api_app.app)
    r = c.post("/api/learn/progress", json={"chapter": "circular-motion", "lane": "revision"})
    assert r.status_code == 401


def test_bad_body_is_400(monkeypatch):
    c = _signed_in_client(monkeypatch)
    assert c.post("/api/learn/progress", json={}).status_code == 400
    assert c.post("/api/learn/progress", json={"chapter": "x", "lane": 3}).status_code == 400


def test_unpublished_pair_is_404_before_write(monkeypatch):
    c = _signed_in_client(monkeypatch)
    assert c.post("/api/learn/progress",
                  json={"chapter": "circular-motion", "lane": "deck"}).status_code == 404
    assert c.post("/api/learn/progress",
                  json={"chapter": "nope", "lane": "revision"}).status_code == 404
    sid = store.list_students()[0]["id"]
    assert store.list_progress(sid) == []              # nothing was written


def test_mark_done_persists_and_is_idempotent(monkeypatch):
    c = _signed_in_client(monkeypatch)
    body = {"chapter": "circular-motion", "lane": "revision"}
    assert c.post("/api/learn/progress", json=body).json() == {"ok": True}
    assert c.post("/api/learn/progress", json=body).json() == {"ok": True}   # re-mark ok
    sid = store.list_students()[0]["id"]
    assert len(store.list_progress(sid)) == 1


def test_rate_limited_is_429(monkeypatch):
    c = _signed_in_client(monkeypatch)
    monkeypatch.setattr(service, "_PROGRESS_LIMITER",
                        identity.RateLimiter(max_attempts=1, window_seconds=60))
    body = {"chapter": "circular-motion", "lane": "revision"}
    assert c.post("/api/learn/progress", json=body).status_code == 200
    assert c.post("/api/learn/progress", json=body).status_code == 429
```

- [ ] **Step 2: Run to verify failure** — `python -m pytest tests/test_api_learn_progress.py -q` → FAIL (405/404: route absent).

- [ ] **Step 3: Implement**

Append to `samagra/api/app.py` after `api_learn_me` (keep the G3 block comment style):

```python
@app.post("/api/learn/progress")
def api_learn_progress(payload: dict, request: Request):
    # G4: the FIRST authenticated student write. Session-gated (NOT origin-gated);
    # the student id comes ONLY from the session cookie — no id parameter exists
    # anywhere on this surface (structural IDOR prevention, DEC-13). The write
    # touches ONLY pratham.db via service/store.
    from ..factory.publish import read
    from ..pratham import service
    student = service.current_student(request.cookies.get(_PRATHAM_COOKIE))
    if student is None:
        raise HTTPException(401, "sign in required")
    chapter = (payload or {}).get("chapter")
    lane = (payload or {}).get("lane")
    if not isinstance(chapter, str) or not chapter.strip() \
            or not isinstance(lane, str) or not lane.strip():
        raise HTTPException(400, "chapter and lane required")
    chapter, lane = chapter.strip(), lane.strip()
    # 404-before-write (DEC-13): a progress row can never reference content that
    # is not in the LIVE published manifest.
    ch = (read.published_manifest() or {}).get("chapters", {}).get(chapter)
    lanes = {a.get("lane") for a in (ch.get("artifacts") or [])} if ch else set()
    if lane not in lanes:
        raise HTTPException(404, "not published")
    if not service.mark_done(student["id"], chapter, lane):
        raise HTTPException(429, "slow down")
    return {"ok": True}
```

- [ ] **Step 4: Run to verify pass** — `python -m pytest tests/test_api_learn_progress.py -q` → 6 passed. Also `python -m pytest tests/test_api_learn.py -q` (G3 endpoints untouched).

- [ ] **Step 5: Commit**

```bash
git add samagra/api/app.py tests/test_api_learn_progress.py
git commit -m "feat(g4): POST /api/learn/progress — session-gated, 404-before-write, rate-limited"
```

---

### Task 6: `GET /api/learn/next`

**Files:**
- Modify: `samagra/api/app.py` (directly after `api_learn_progress`)
- Test: `tests/test_api_learn_next.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_api_learn_next.py
from fastapi.testclient import TestClient

from samagra import config
from samagra.api import app as api_app
from samagra.factory.publish import read
from samagra.pratham import service

_MAN = {"chapters": {"circular-motion": {"title": "Circular Motion",
                                         "artifacts": [{"lane": "revision"}]}}}


def test_anonymous_is_401():
    assert TestClient(api_app.app).get("/api/learn/next").status_code == 401


def test_signed_in_gets_queue_and_done(monkeypatch, tmp_path):
    monkeypatch.setattr(read, "published_manifest", lambda: _MAN)
    monkeypatch.setattr(config, "CONCEPT_GRAPH_DB", tmp_path / "absent.db", raising=False)
    c = TestClient(api_app.app)
    code = service.enroll("Asha")["code"]
    c.post("/api/learn/login", json={"code": code})
    p = c.get("/api/learn/next").json()
    assert [ (g["chapter"], g["lane"]) for g in p["queue"] ] == [("circular-motion", "revision")]
    assert p["done"] == []


def test_empty_world_is_valid_json(monkeypatch, tmp_path):
    monkeypatch.setattr(read, "published_manifest", lambda: {"chapters": {}})
    monkeypatch.setattr(config, "CONCEPT_GRAPH_DB", tmp_path / "absent.db", raising=False)
    c = TestClient(api_app.app)
    code = service.enroll("Asha")["code"]
    c.post("/api/learn/login", json={"code": code})
    r = c.get("/api/learn/next")
    assert r.status_code == 200 and r.json() == {"queue": [], "done": []}
```

- [ ] **Step 2: Run to verify failure** — `python -m pytest tests/test_api_learn_next.py -q` → FAIL.

- [ ] **Step 3: Implement** — append after `api_learn_progress`:

```python
@app.get("/api/learn/next")
def api_learn_next(request: Request):
    # G4: the deterministic what's-next queue — session-gated (F-G4-4: adaptivity is
    # the reward for signing in; anonymous /learn stays byte-identical). Read-only.
    from ..pratham import service
    from . import learn_next
    student = service.current_student(request.cookies.get(_PRATHAM_COOKIE))
    if student is None:
        raise HTTPException(401, "sign in required")
    return learn_next.next_payload(student["id"])
```

- [ ] **Step 4: Run to verify pass** — `python -m pytest tests/test_api_learn_next.py -q` → 3 passed.

- [ ] **Step 5: Commit**

```bash
git add samagra/api/app.py tests/test_api_learn_next.py
git commit -m "feat(g4): GET /api/learn/next — session-gated deterministic queue + done-set"
```

---

### Task 7: golden threads

**Files:**
- Test: `tests/test_g4_golden.py`

- [ ] **Step 1: Write the failing tests** (thread 1 fails until Tasks 5–6 are merged in the worktree; if executing in order it passes immediately — still write it as its own file, it is the acceptance record)

```python
# tests/test_g4_golden.py
"""Phase G4 golden threads (spec §7): the adaptive loop, write-path isolation,
anonymous invariance. Mirrors tests/test_g3_golden.py's style."""
import hashlib

from fastapi.testclient import TestClient

from samagra import config
from samagra.api import app as api_app
from samagra.factory.publish import read
from samagra.governance import store as gstore
from samagra.pratham import service

_MAN = {"chapters": {
    "circular-motion": {"title": "Circular Motion",
                        "artifacts": [{"lane": "revision"}, {"lane": "deck"}]},
}}


def _gov_bytes() -> bytes:
    gstore.ensure_tables()
    return config.GOVERNANCE_DB.read_bytes()


def test_golden_adaptive_loop_and_isolation(monkeypatch, tmp_path):
    monkeypatch.setattr(read, "published_manifest", lambda: _MAN)
    monkeypatch.setattr(config, "CONCEPT_GRAPH_DB", tmp_path / "absent.db", raising=False)
    gov_before = hashlib.sha256(_gov_bytes()).hexdigest()

    c = TestClient(api_app.app)
    code = service.enroll("Asha")["code"]
    assert c.post("/api/learn/login", json={"code": code}).status_code == 200

    q1 = c.get("/api/learn/next").json()
    assert ("circular-motion", "revision") in {(g["chapter"], g["lane"]) for g in q1["queue"]}

    assert c.post("/api/learn/progress",
                  json={"chapter": "circular-motion", "lane": "revision"}).json() == {"ok": True}

    q2 = c.get("/api/learn/next").json()
    assert ("circular-motion", "revision") not in {(g["chapter"], g["lane"]) for g in q2["queue"]}
    assert [(d["chapter"], d["lane"]) for d in q2["done"]] == [("circular-motion", "revision")]

    # Write-path isolation: the whole loop left governance.db BYTE-unchanged.
    assert hashlib.sha256(_gov_bytes()).hexdigest() == gov_before


def test_golden_anonymous_invariance(monkeypatch):
    monkeypatch.setattr(read, "published_manifest", lambda: _MAN)
    c = TestClient(api_app.app)
    assert c.get("/api/learn/next").status_code == 401
    assert c.post("/api/learn/progress",
                  json={"chapter": "circular-motion", "lane": "revision"}).status_code == 401
    # The public read surface is untouched by G4.
    assert c.get("/api/published").status_code == 200
```

- [ ] **Step 2: Run** — `python -m pytest tests/test_g4_golden.py -q` → 2 passed (or fix forward).

- [ ] **Step 3: Commit**

```bash
git add tests/test_g4_golden.py
git commit -m "test(g4): golden threads — adaptive loop, governance byte-isolation, anon 401s"
```

---

### Task 8: frontend `lib/pratham/plan.ts`

**Files:**
- Create: `frontend/src/lib/pratham/plan.ts`
- Test: `frontend/src/lib/pratham/plan.test.ts`

- [ ] **Step 1: Write the failing tests**

```ts
// frontend/src/lib/pratham/plan.test.ts
import { afterEach, describe, expect, it, vi } from "vitest";
import { markDoneRequest, nextRequest } from "./plan";

const ok = (body: unknown) =>
  Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as Response);
const status = (code: number) =>
  Promise.resolve({ ok: false, status: code, json: () => Promise.resolve({}) } as Response);

afterEach(() => vi.unstubAllGlobals());

describe("plan.ts wrappers (G4)", () => {
  it("nextRequest returns the payload with same-origin credentials", async () => {
    const fetchMock = vi.fn().mockReturnValue(ok({ queue: [], done: [] }));
    vi.stubGlobal("fetch", fetchMock);
    expect(await nextRequest()).toEqual({ queue: [], done: [] });
    expect(fetchMock).toHaveBeenCalledWith("/api/learn/next",
      expect.objectContaining({ credentials: "same-origin" }));
  });

  it("nextRequest swallows 401/network to null (anonymous-safe)", async () => {
    vi.stubGlobal("fetch", vi.fn().mockReturnValue(status(401)));
    expect(await nextRequest()).toBeNull();
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("net")));
    expect(await nextRequest()).toBeNull();
  });

  it("markDoneRequest POSTs the pair and reports ok", async () => {
    const fetchMock = vi.fn().mockReturnValue(ok({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);
    expect(await markDoneRequest("circular-motion", "revision")).toBe(true);
    expect(fetchMock).toHaveBeenCalledWith("/api/learn/progress",
      expect.objectContaining({
        method: "POST", credentials: "same-origin",
        body: JSON.stringify({ chapter: "circular-motion", lane: "revision" }),
      }));
  });

  it("markDoneRequest reports false on failure", async () => {
    vi.stubGlobal("fetch", vi.fn().mockReturnValue(status(429)));
    expect(await markDoneRequest("c", "revision")).toBe(false);
  });
});
```

- [ ] **Step 2: Run to verify failure** — `cd frontend && npx vitest run src/lib/pratham/plan.test.ts` → FAIL (module missing).

- [ ] **Step 3: Implement**

```ts
// frontend/src/lib/pratham/plan.ts
// G4: thin typed wrappers over the session-gated adaptive endpoints (mirrors
// session.ts — same-origin credentials, null/false on any failure so the reader
// degrades to anonymous behavior instead of crashing).
export interface NextItem {
  chapter: string; title: string; lane: string;
  reason: string; score: number; rank: number;
}
export interface ProgressRow { chapter: string; lane: string; status: string; marked_at: string; }
export interface NextResponse { queue: NextItem[]; done: ProgressRow[]; }

export async function nextRequest(): Promise<NextResponse | null> {
  try {
    const r = await fetch("/api/learn/next", { credentials: "same-origin" });
    if (!r.ok) return null;
    return (await r.json()) as NextResponse;
  } catch { return null; }
}

export async function markDoneRequest(chapter: string, lane: string): Promise<boolean> {
  try {
    const r = await fetch("/api/learn/progress", {
      method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chapter, lane }),
    });
    return r.ok;
  } catch { return false; }
}
```

- [ ] **Step 4: Run to verify pass** — `npx vitest run src/lib/pratham/plan.test.ts` → 4 passed.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/pratham/plan.ts frontend/src/lib/pratham/plan.test.ts
git commit -m "feat(g4): frontend plan.ts wrappers for next/progress"
```

---

### Task 9: anonymous-invariance regression (write BEFORE any new JSX)

**Files:**
- Test: `frontend/src/apps/Pratham/adaptive.test.tsx`

- [ ] **Step 1: Write the tests — they must PASS against the current (pre-G4-UI) reader, then keep passing forever**

```tsx
// frontend/src/apps/Pratham/adaptive.test.tsx
// G4 identity-optional invariant: an anonymous reader renders ZERO adaptive UI —
// written BEFORE the new JSX landed (spec §11) and kept green after it.
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import Pratham from "./index";

const MAN = {
  version: "samagra.published.v1",
  chapters: {
    "circular-motion": {
      chapter: "circular-motion", title: "Circular Motion",
      artifacts: [{ lane: "revision", files: [{ ext: "html" }] }],
    },
  },
};

vi.mock("../../hooks/useApi", () => ({
  useApi: () => ({ data: MAN, loading: false, error: null }),
}));

const me = vi.fn();
const next = vi.fn();
vi.mock("../../lib/pratham/session", () => ({
  meRequest: (...a: unknown[]) => me(...a),
  loginRequest: vi.fn(),
  logoutRequest: vi.fn(),
}));
vi.mock("../../lib/pratham/plan", () => ({
  nextRequest: (...a: unknown[]) => next(...a),
  markDoneRequest: vi.fn(),
}));

afterEach(() => vi.clearAllMocks());

describe("anonymous invariance (G4)", () => {
  it("renders no adaptive UI and never calls /api/learn/next when anonymous", async () => {
    me.mockResolvedValue(null);
    render(<Pratham />);
    await waitFor(() => expect(me).toHaveBeenCalled());
    expect(screen.queryByTestId("pratham-mark-done")).toBeNull();
    expect(screen.queryByTestId("pratham-next")).toBeNull();
    expect(screen.queryByTestId("pratham-done-badge")).toBeNull();
    expect(next).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run** — `npx vitest run src/apps/Pratham/adaptive.test.tsx` → 1 passed (it must be green BEFORE the UI task and stay green after — this is the frozen baseline).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/apps/Pratham/adaptive.test.tsx
git commit -m "test(g4): freeze anonymous-invariance baseline before any adaptive JSX"
```

---

### Task 10: signed-in UI tests (red)

**Files:**
- Modify: `frontend/src/apps/Pratham/adaptive.test.tsx` (append a signed-in describe block)

- [ ] **Step 1: Append the failing tests**

```tsx
describe("signed-in adaptive UI (G4)", () => {
  const PAYLOAD = {
    queue: [
      { chapter: "circular-motion", title: "Circular Motion", lane: "revision",
        reason: "high-demand", score: 700, rank: 1 },
    ],
    done: [],
  };

  it("renders the what's-next strip and a mark-done button when signed in", async () => {
    me.mockResolvedValue({ id: "stu_1", name: "Asha" });
    next.mockResolvedValue(PAYLOAD);
    render(<Pratham />);
    expect(await screen.findByTestId("pratham-next")).toBeTruthy();
    expect(await screen.findByTestId("pratham-mark-done")).toBeTruthy();
  });

  it("marking done POSTs the current pair and refetches the queue", async () => {
    const { markDoneRequest } = await import("../../lib/pratham/plan");
    me.mockResolvedValue({ id: "stu_1", name: "Asha" });
    next.mockResolvedValue(PAYLOAD);
    (markDoneRequest as ReturnType<typeof vi.fn>).mockResolvedValue(true);
    render(<Pratham />);
    (await screen.findByTestId("pratham-mark-done")).click();
    await waitFor(() => {
      expect(markDoneRequest).toHaveBeenCalledWith("circular-motion", "revision");
      expect(next.mock.calls.length).toBeGreaterThanOrEqual(2);   // initial + refetch
    });
  });

  it("shows the done badge instead of the button for an already-done pair", async () => {
    me.mockResolvedValue({ id: "stu_1", name: "Asha" });
    next.mockResolvedValue({ queue: [], done: [
      { chapter: "circular-motion", lane: "revision", status: "done",
        marked_at: "2026-07-05T10:00:00Z" }] });
    render(<Pratham />);
    expect(await screen.findByTestId("pratham-done-badge")).toBeTruthy();
    expect(screen.queryByTestId("pratham-mark-done")).toBeNull();
  });
});
```

(For the `markDoneRequest` assertions to work, hoist it: change the plan mock to
`const markDone = vi.fn(); vi.mock("../../lib/pratham/plan", () => ({ nextRequest: (...a: unknown[]) => next(...a), markDoneRequest: (...a: unknown[]) => markDone(...a) }));`
and assert on `markDone` — follow the same closure-safe pattern the file already uses for `me`/`next`.)

- [ ] **Step 2: Run to verify failure** — `npx vitest run src/apps/Pratham/adaptive.test.tsx` → signed-in block FAILS (no such testids), anonymous block still PASSES.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/apps/Pratham/adaptive.test.tsx
git commit -m "test(g4): signed-in adaptive UI expectations (red)"
```

---

### Task 11: implement the reader UI

**Files:**
- Modify: `frontend/src/apps/Pratham/index.tsx`

- [ ] **Step 1: Implement (drive tasks 9+10 green)**

(a) Imports (after the `session` import at line 7):

```tsx
import { markDoneRequest, nextRequest, type NextResponse } from "../../lib/pratham/plan";
```

(b) State + fetch effect (after the `meResolved` ref block, ~line 43):

```tsx
  // G4: the adaptive plan — fetched ONLY for a signed-in student (F-G4-4). An
  // anonymous reader never calls /api/learn/next and renders zero adaptive UI.
  const [plan, setPlan] = useState<NextResponse | null>(null);
  useEffect(() => {
    if (!student) { setPlan(null); return; }
    let alive = true;
    nextRequest().then((p) => { if (alive) setPlan(p); });
    return () => { alive = false; };
  }, [student]);

  async function markDone() {
    if (!chapter || !lane) return;
    if (await markDoneRequest(chapter.chapter, lane)) {
      const p = await nextRequest();          // refetch: the loop closes here
      setPlan(p);
    }
  }
  const doneSet = new Set((plan?.done ?? []).map((d) => `${d.chapter}:${d.lane}`));
```

NOTE: `markDone`/`doneSet` reference `chapter`/`lane`, so place this block AFTER the
existing `const lane = pickLane(...)` line (~line 65), keeping the `useEffect` with the
other effects is fine (it only closes over `student`).

(c) Mark-done control — inside the lane-tab row `<div>`, immediately BEFORE the
`{hasDocx && chapter && lane ? (` block (~line 183):

```tsx
              {student && chapter && lane ? (
                doneSet.has(`${chapter.chapter}:${lane}`) ? (
                  <span data-testid="pratham-done-badge"
                    style={{ fontSize: 13, color: "#15803d", fontWeight: 600 }}>
                    Done
                  </span>
                ) : (
                  <button data-testid="pratham-mark-done" onClick={markDone}
                    style={{ border: `1px solid ${C.line}`, background: C.card,
                      color: C.text, font: "inherit", padding: "6px 12px",
                      borderRadius: 999, cursor: "pointer" }}>
                    Mark done
                  </button>
                )
              ) : null}
```

(d) What's-next strip — immediately AFTER the lane-tab row `</div>` and BEFORE the
`{chapter && lane ? (<iframe …` block (~line 191):

```tsx
            {student && plan && plan.queue.length > 0 ? (
              <div data-testid="pratham-next" style={{
                display: "flex", gap: 6, padding: "8px 14px", flexWrap: "wrap",
                alignItems: "center", borderBottom: `1px solid ${C.line}`,
                fontSize: 13,
              }}>
                <span style={{ color: C.muted }}>What's next:</span>
                {plan.queue.slice(0, 5).map((g) => (
                  <button key={`${g.chapter}:${g.lane}`}
                    data-testid={`pratham-next-${g.chapter}-${g.lane}`}
                    onClick={() => go(g.chapter, g.lane)} title={g.reason}
                    style={{ border: `1px solid ${C.line}`, background: C.card,
                      color: C.text, font: "inherit", padding: "4px 10px",
                      borderRadius: 999, cursor: "pointer" }}>
                    {g.title} · {laneLabel(g.lane).name}
                  </button>
                ))}
              </div>
            ) : null}
```

- [ ] **Step 2: Run to verify pass** — `npx vitest run src/apps/Pratham/` → ALL green (including the pre-existing `index.test.tsx` + `signin.test.tsx` — anonymous behavior byte-identical). Then `npx tsc --noEmit`.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/apps/Pratham/index.tsx frontend/src/apps/Pratham/adaptive.test.tsx
git commit -m "feat(g4): student-gated Mark done + What's-next strip in the /learn reader"
```

---

### Task 12: full verification gate + docs/trackers + DEC-13

- [ ] **Step 1: Full backend suite** — `python -m pytest -q` — expected: baseline 608 + ~27 new, 1 skip, 0 failures.
- [ ] **Step 2: Full frontend gate** — `cd frontend && npx vitest run && npx tsc --noEmit && npm run build` — expected: baseline 604 + ~8 new, tsc + build green.
- [ ] **Step 3: Empty-world smoke** — with a scratch env (fresh `pratham.db`, no `published/`, no `concept_graph.db`): `python -m pytest tests/test_g4_golden.py tests/test_api_learn_next.py -q` (already parameterized to that world) plus a manual `curl -s localhost:8799/api/learn/next` → 401 (anon), never 500.
- [ ] **Step 4: Update trackers** — CLAUDE.md G-status banner + HANDOFF.md (banner + append DEC-13 to the decisions block, text from spec §9) + STATUS.html + SUMMARY.html per the house prepend-banner convention; note the owner follow-ups (queue size/rate-limit tunables; the operator progress view deferred).
- [ ] **Step 5: Commit** — `git add -A docs STATUS.html HANDOFF.md SUMMARY.html CLAUDE.md && git commit -m "docs(g4): status + trackers + DEC-13 for the adaptive-twin slice"`

---

### Task 13: review gate (do NOT merge before these)

Per spec §10 and the DEC-7 pattern for every write boundary:

- [ ] **Step 1:** Dedicated Codex pre-merge review of the student write boundary (`POST /api/learn/progress` + store/service) and the session-gated read surface → save as `docs/codex-reviews/29-g4-adaptive-twin-premerge.report.md`.
- [ ] **Step 2:** Adversarial multi-lens final review (Workflow, 4 lenses × independent refute-verify): firewall/store-isolation (pratham imports no factory code; writes only pratham.db) · security (IDOR-proofness, rate limit, CSRF scope, no oracle) · spec-fidelity (§2 rulings + §7 threads) · identity-optional/separate-entity (anonymous byte-identical).
- [ ] **Step 3:** Remediate findings TDD → re-run the full gate → `git checkout main && git merge --ff-only feature/content-factory-phase-g4 && git push origin main`.

---

## Self-Review

**1. Spec coverage:** §4 schema → Task 1; §5.1 write endpoint (401/400/404/429/idempotent) → Tasks 2+5; §5.2 read endpoint + ranker + glue → Tasks 3+4+6; §6 UI (mark-done, next strip, plan.ts, anonymous gating) → Tasks 8–11; §7 golden threads → Task 7 (threads 1–3) + Task 12 Step 3 (thread 4); §8 security model → asserted across Tasks 2/5/6 tests; §9 DEC-13 → Task 12 Step 4; §10 review gate → Task 13. §12/§13 non-goals introduce no tasks (correct).

**2. Placeholder scan:** every code step shows complete code; every command has an expected result; the only prose-level steps are Task 12 Step 4 (documentation, per convention) and Task 13 (the review gate procedure). One deliberate adaptation note in Task 10 (hoisting the `markDoneRequest` mock) gives the exact pattern to follow.

**3. Type consistency:** `mark_progress(student_id, chapter, lane, marked_at)` (Task 1) matches Task 2's call; `mark_done(student_id, chapter, lane, *, now_epoch=None) -> bool` (Task 2) matches Task 5's call; `rank_next(published, chapter_demand, done_pairs, *, top)` (Task 3) matches Task 4's call; `next_payload(student_id) -> {queue, done}` (Task 4) matches Tasks 6–8's response typing (`NextResponse`); frontend `nextRequest()/markDoneRequest(chapter, lane)` (Task 8) match Tasks 9–11's mocks and calls; testids `pratham-mark-done`/`pratham-next`/`pratham-done-badge` are consistent across Tasks 9–11.
