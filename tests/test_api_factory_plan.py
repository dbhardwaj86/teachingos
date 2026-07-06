# tests/test_api_factory_plan.py
import threading

import pytest
from fastapi.testclient import TestClient

from samagra import config
from samagra.api import app as api_app
from samagra.api import origin_auth


def test_plan_route_is_in_protected_posts():
    # Mirrors test_api_factory_publish.py: accidental removal from
    # origin_auth._PROTECTED_POSTS must be caught by this file too.
    assert origin_auth.is_protected("POST", "/api/factory/plan") is True


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


@pytest.fixture
def factory_env(tmp_path, monkeypatch):
    """Isolate governance.db + catalog db + outbox/export trees into tmp
    (mirrors tests/test_factory_run.py::factory_env)."""
    from samagra.governance import store as gov
    monkeypatch.setattr(config, "GOVERNANCE_DB", tmp_path / "governance.db")
    monkeypatch.setattr(config, "DATA_DB", tmp_path / "samagra.db")
    monkeypatch.setattr(config, "EXPORT_DIR", tmp_path / "exports")
    gov._INITIALIZED.clear()             # memoized schema cache must not leak across DBs
    gov.ensure_tables()                  # connect() does NOT create tables
    monkeypatch.chdir(tmp_path)          # outbox writes board/<agent>/outbox/ under tmp
    yield tmp_path
    gov._INITIALIZED.clear()


def test_concurrent_double_post_does_not_duplicate_rows(factory_env):
    # Review (Important): the GUI can double-click/fire concurrent POSTs where the
    # CLI was always serial, and run.plan's per-line dedup (read `_existing_
    # assignment_for` then `add_assignment` write) is not atomic — an unserialized
    # endpoint duplicated governance rows (reviewer observed 6-7 instead of 5).
    # Deliberately uses the REAL run.plan (no mock): the unmocked read-then-write
    # window IS the hazard. Pre-fix failure is probabilistic, so the double-POST
    # loops 5x — dedup must hold the row count at exactly 5 across ALL iterations.
    from samagra.governance import store as gov

    seed = "textbook:circular-motion"
    statuses: list[int] = []
    for _ in range(5):
        barrier = threading.Barrier(2)
        results: list[int | None] = [None, None]

        def hit(i: int) -> None:
            c = TestClient(api_app.app)          # one client per thread
            barrier.wait()                       # maximize the collision window
            results[i] = c.post(
                "/api/factory/plan", json={"seed_ref": seed}).status_code

        threads = [threading.Thread(target=hit, args=(i,)) for i in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        statuses.extend(results)                 # type: ignore[arg-type]
        conn = gov.connect()
        try:
            rows = [r for r in gov.list_assignments(conn) if r["seed_ref"] == seed]
        finally:
            conn.close()
        assert len(rows) == 5, (
            f"expected exactly 5 lane rows for {seed!r}, got {len(rows)} "
            f"(concurrent POSTs duplicated governance rows)")
    assert all(s == 200 for s in statuses), f"non-200 among {statuses}"
