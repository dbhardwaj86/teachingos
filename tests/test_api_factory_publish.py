# tests/test_api_factory_publish.py
import pytest
from fastapi.testclient import TestClient

from samagra import config
from samagra.api import app as api_app
from samagra.api import origin_auth


def test_publish_endpoints_are_in_protected_posts():
    assert origin_auth.is_protected("POST", "/api/factory/publish") is True
    assert origin_auth.is_protected("POST", "/api/factory/unpublish") is True


@pytest.fixture
def gate_on(monkeypatch):
    monkeypatch.setattr(config, "DISABLE_ORIGIN_AUTH", False)
    monkeypatch.setattr(config, "ACCESS_AUD", None)
    monkeypatch.setattr(config, "ACCESS_TEAM_DOMAIN", None)
    monkeypatch.setattr(config, "OWNER_EMAIL", None)
    return monkeypatch


def test_remote_publish_without_identity_is_403(gate_on):
    gate_on.setattr(origin_auth, "_client_host", lambda req: "203.0.113.9")
    c = TestClient(api_app.app)
    r = c.post("/api/factory/publish", json={"chapter": "circular-motion"})
    assert r.status_code == 403  # gate blocks before the handler


def test_loopback_publish_bad_body_is_400(gate_on):
    gate_on.setattr(origin_auth, "_client_host", lambda req: "127.0.0.1")
    c = TestClient(api_app.app)
    r = c.post("/api/factory/publish", json={})       # reached handler -> 400, not 403
    assert r.status_code == 400


def test_publish_unknown_chapter_is_409(tmp_path, monkeypatch):
    # conftest disables the gate (local dev), so this reaches the handler on loopback.
    monkeypatch.setattr(config, "GOVERNANCE_DB", tmp_path / "governance.db")
    monkeypatch.setattr(config, "PUBLISHED_DIR", tmp_path / "published")
    from samagra.governance import store as gov
    gov._INITIALIZED.clear(); gov.ensure_tables()
    c = TestClient(api_app.app)
    r = c.post("/api/factory/publish", json={"chapter": "no-such-chapter"})
    assert r.status_code == 409
    gov._INITIALIZED.clear()


def test_publish_delegates_to_run(monkeypatch):
    captured = {}

    def fake_publish(chapter, *, lanes=None, actor="owner"):
        captured.update(chapter=chapter, lanes=lanes, actor=actor)
        return {"chapter": chapter, "publication_id": "pub_x", "published": ["revision"]}
    monkeypatch.setattr("samagra.factory.publish.run.publish", fake_publish)
    c = TestClient(api_app.app)
    r = c.post("/api/factory/publish", json={"chapter": "cm", "lanes": ["revision"]})
    assert r.status_code == 200
    assert r.json()["result"]["publication_id"] == "pub_x"
    assert captured == {"chapter": "cm", "lanes": ["revision"], "actor": "owner"}


def test_unpublish_delegates_to_run(monkeypatch):
    def fake_unpublish(chapter, *, lanes=None, actor="owner"):
        return {"chapter": chapter, "publication_id": "pub_y", "unpublished": ["revision"]}
    monkeypatch.setattr("samagra.factory.publish.run.unpublish", fake_unpublish)
    c = TestClient(api_app.app)
    r = c.post("/api/factory/unpublish", json={"chapter": "cm"})
    assert r.status_code == 200 and r.json()["result"]["publication_id"] == "pub_y"


def test_publish_bad_lanes_type_is_400():
    c = TestClient(api_app.app)
    r = c.post("/api/factory/publish", json={"chapter": "cm", "lanes": "revision"})
    assert r.status_code == 400  # lanes must be a list
