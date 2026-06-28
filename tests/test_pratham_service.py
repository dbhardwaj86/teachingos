# tests/test_pratham_service.py
from samagra import config
from samagra.pratham import identity, service, store


def _fresh(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PRATHAM_DB", tmp_path / "pratham.db")
    store._INITIALIZED.clear()
    service._LIMITER._hits.clear()


def test_enroll_mints_a_code_and_persists_the_student(tmp_path, monkeypatch):
    _fresh(tmp_path, monkeypatch)
    res = service.enroll("Asha")
    assert res["name"] == "Asha" and res["id"].startswith("stu_")
    assert len(res["code"]) >= 11
    # the code is stored only as a hash
    row = store.get_student(res["id"])
    assert row["code_hash"] == identity.hash_secret(res["code"])
    assert "code" not in row


def test_enroll_rejects_blank_name(tmp_path, monkeypatch):
    _fresh(tmp_path, monkeypatch)
    import pytest
    with pytest.raises(ValueError):
        service.enroll("   ")


def test_login_valid_code_creates_a_session(tmp_path, monkeypatch):
    _fresh(tmp_path, monkeypatch)
    code = service.enroll("Asha")["code"]
    out = service.login(code, client_key="ip1")
    assert out["name"] == "Asha"
    token = out["_session_token"]
    assert store.find_session(identity.hash_secret(token)) is not None


def test_login_wrong_or_revoked_code_returns_none(tmp_path, monkeypatch):
    _fresh(tmp_path, monkeypatch)
    res = service.enroll("Asha")
    assert service.login("not-the-code", client_key="ip1") is None
    service.revoke(res["id"])
    assert service.login(res["code"], client_key="ip1") is None


def test_login_rate_limited_returns_none(tmp_path, monkeypatch):
    _fresh(tmp_path, monkeypatch)
    monkeypatch.setattr(service, "_LIMITER", identity.RateLimiter(max_attempts=1, window_seconds=60))
    service.enroll("Asha")
    assert service.login("x", client_key="ip1") is None     # 1st attempt allowed (bad code -> None)
    assert service.login("y", client_key="ip1") is None     # 2nd blocked by limiter -> None


def test_current_student_valid_expired_and_revoked(tmp_path, monkeypatch):
    _fresh(tmp_path, monkeypatch)
    code = service.enroll("Asha")["code"]
    token = service.login(code, client_key="ip1")["_session_token"]
    assert service.current_student(token)["name"] == "Asha"
    assert service.current_student(None) is None
    assert service.current_student("garbage") is None
    # far-future "now" -> the 30-day session is expired
    import time
    assert service.current_student(token, now_epoch=time.time() + 40 * 86400) is None


def test_logout_invalidates_the_session(tmp_path, monkeypatch):
    _fresh(tmp_path, monkeypatch)
    code = service.enroll("Asha")["code"]
    token = service.login(code, client_key="ip1")["_session_token"]
    service.logout(token)
    assert service.current_student(token) is None
    service.logout(None)  # idempotent / no-op


def test_revoke_invalidates_existing_sessions(tmp_path, monkeypatch):
    _fresh(tmp_path, monkeypatch)
    res = service.enroll("Asha")
    token = service.login(res["code"], client_key="ip1")["_session_token"]
    service.revoke(res["id"])
    assert service.current_student(token) is None
