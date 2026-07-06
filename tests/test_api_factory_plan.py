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
