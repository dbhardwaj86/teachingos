# tests/test_api_learn.py
from fastapi.testclient import TestClient

from samagra import config
from samagra.api import app as api_app
from samagra.api import origin_auth


def _client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PRATHAM_DB", tmp_path / "pratham.db")
    from samagra.pratham import store
    store._INITIALIZED.clear()
    return TestClient(api_app.app)


def test_learn_endpoints_are_public_not_gated():
    # /learn surface stays PUBLIC (DEC-11) — not in the protected tables.
    assert origin_auth.is_protected("POST", "/api/learn/login") is False
    assert origin_auth.is_protected("POST", "/api/learn/logout") is False
    assert origin_auth.is_protected("GET", "/api/learn/me") is False


def test_login_sets_cookie_and_me_returns_student(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    from samagra.pratham import service
    code = service.enroll("Asha")["code"]
    r = c.post("/api/learn/login", json={"code": code})
    assert r.status_code == 200 and r.json()["student"]["name"] == "Asha"
    assert "pratham_session" in r.cookies
    me = c.get("/api/learn/me")            # TestClient persists the cookie
    assert me.json()["student"]["name"] == "Asha"


def test_login_cookie_flags_httponly_samesite(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    from samagra.pratham import service
    code = service.enroll("Asha")["code"]
    r = c.post("/api/learn/login", json={"code": code})
    set_cookie = r.headers["set-cookie"].lower()
    assert "httponly" in set_cookie and "samesite=lax" in set_cookie
    assert "max-age=" in set_cookie


def test_login_wrong_code_is_401(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.post("/api/learn/login", json={"code": "nope"})
    assert r.status_code == 401


def test_login_missing_code_is_400(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    assert c.post("/api/learn/login", json={}).status_code == 400


def test_me_without_cookie_is_null(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    assert c.get("/api/learn/me").json() == {"student": None}


def test_logout_clears_session(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    from samagra.pratham import service
    code = service.enroll("Asha")["code"]
    c.post("/api/learn/login", json={"code": code})
    c.post("/api/learn/logout")
    assert c.get("/api/learn/me").json() == {"student": None}


def test_login_rate_limited_returns_401_even_for_valid_code(tmp_path, monkeypatch):
    # No-oracle at the HTTP layer: a rate-limited caller gets the SAME 401 as a bad
    # code, even when the code is valid.
    c = _client(tmp_path, monkeypatch)
    from samagra.pratham import identity, service
    monkeypatch.setattr(service, "_LIMITER", identity.RateLimiter(max_attempts=1, window_seconds=60))
    code = service.enroll("Asha")["code"]
    assert c.post("/api/learn/login", json={"code": code}).status_code == 200  # 1st allowed
    assert c.post("/api/learn/login", json={"code": code}).status_code == 401  # 2nd rate-limited
