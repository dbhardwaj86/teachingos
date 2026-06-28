# tests/test_pratham_cli.py
from samagra import config
from samagra.__main__ import build_parser
from samagra.pratham import service, store


def _args(argv):
    return build_parser().parse_args(argv)


def test_enroll_prints_code_and_persists(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(config, "PRATHAM_DB", tmp_path / "pratham.db")
    store._INITIALIZED.clear()
    args = _args(["pratham", "enroll", "Asha"])
    args.func(args)
    out = capsys.readouterr().out
    assert "Asha" in out and "code" in out.lower()
    assert len(store.list_students()) == 1


def test_students_lists_enrolled(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(config, "PRATHAM_DB", tmp_path / "pratham.db")
    store._INITIALIZED.clear()
    service.enroll("Asha")
    args = _args(["pratham", "students"])
    args.func(args)
    assert "Asha" in capsys.readouterr().out


def test_revoke_marks_revoked(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(config, "PRATHAM_DB", tmp_path / "pratham.db")
    store._INITIALIZED.clear()
    sid = service.enroll("Asha")["id"]
    args = _args(["pratham", "revoke", sid])
    args.func(args)
    assert store.get_student(sid)["status"] == "revoked"
