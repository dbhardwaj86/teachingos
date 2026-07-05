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
