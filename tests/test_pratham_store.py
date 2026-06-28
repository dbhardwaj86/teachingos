# tests/test_pratham_store.py
from samagra import config
from samagra.pratham import store


def test_create_and_find_student_by_code_hash(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PRATHAM_DB", tmp_path / "pratham.db")
    store._INITIALIZED.clear()
    store.create_student("stu_1", "Asha", "codehashAAA", "2026-06-28T00:00:00Z")
    row = store.find_student_by_code_hash("codehashAAA")
    assert row["id"] == "stu_1" and row["name"] == "Asha" and row["status"] == "active"
    assert store.find_student_by_code_hash("nope") is None


def test_get_student_set_status_and_touch_login(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PRATHAM_DB", tmp_path / "pratham.db")
    store._INITIALIZED.clear()
    store.create_student("stu_1", "Asha", "h", "2026-06-28T00:00:00Z")
    store.touch_login("stu_1", "2026-06-28T09:00:00Z")
    assert store.get_student("stu_1")["last_login_at"] == "2026-06-28T09:00:00Z"
    store.set_status("stu_1", "revoked")
    assert store.get_student("stu_1")["status"] == "revoked"


def test_session_create_find_delete(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PRATHAM_DB", tmp_path / "pratham.db")
    store._INITIALIZED.clear()
    store.create_student("stu_1", "Asha", "h", "t")
    store.create_session("sesshash", "stu_1", "t", "2026-07-28T00:00:00Z")
    s = store.find_session("sesshash")
    assert s["student_id"] == "stu_1" and s["expires_at"] == "2026-07-28T00:00:00Z"
    store.delete_session("sesshash")
    assert store.find_session("sesshash") is None


def test_delete_sessions_for_student(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PRATHAM_DB", tmp_path / "pratham.db")
    store._INITIALIZED.clear()
    store.create_student("stu_1", "Asha", "h", "t")
    store.create_session("s1", "stu_1", "t", "z")
    store.create_session("s2", "stu_1", "t", "z")
    store.delete_sessions_for_student("stu_1")
    assert store.find_session("s1") is None and store.find_session("s2") is None


def test_list_students(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PRATHAM_DB", tmp_path / "pratham.db")
    store._INITIALIZED.clear()
    store.create_student("stu_1", "Asha", "h1", "t")
    store.create_student("stu_2", "Ben", "h2", "t")
    names = {r["name"] for r in store.list_students()}
    assert names == {"Asha", "Ben"}


def test_db_file_is_separate_from_governance(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PRATHAM_DB", tmp_path / "pratham.db")
    monkeypatch.setattr(config, "GOVERNANCE_DB", tmp_path / "governance.db")
    store._INITIALIZED.clear()
    store.create_student("stu_1", "Asha", "h", "t")
    assert (tmp_path / "pratham.db").exists()
    assert not (tmp_path / "governance.db").exists()  # identity never touches governance
