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
