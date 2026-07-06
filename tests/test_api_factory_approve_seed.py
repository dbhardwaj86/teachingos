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


def test_approve_seed_route_is_in_protected_posts():
    assert origin_auth.is_protected("POST", "/api/factory/approve-seed") is True


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
