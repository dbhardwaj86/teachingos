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


def test_build_route_is_in_protected_posts():
    assert origin_auth.is_protected("POST", "/api/factory/build") is True


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
