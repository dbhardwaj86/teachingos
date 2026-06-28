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
    assert "Asha" in out and "shown ONCE" in out
    # the printed code must be a real, non-empty token on the code line
    code_line = next(l for l in out.splitlines() if "shown ONCE" in l)
    printed_code = code_line.split(":")[-1].strip()
    assert len(printed_code) >= 11
    assert len(store.list_students()) == 1


def test_students_lists_enrolled(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(config, "PRATHAM_DB", tmp_path / "pratham.db")
    store._INITIALIZED.clear()
    service.enroll("Asha")
    args = _args(["pratham", "students"])
    args.func(args)
    out = capsys.readouterr().out
    assert "Asha" in out
    # secrecy: the listing must never leak the stored code hash
    assert store.list_students()[0]["code_hash"] not in out


def test_revoke_marks_revoked(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(config, "PRATHAM_DB", tmp_path / "pratham.db")
    store._INITIALIZED.clear()
    sid = service.enroll("Asha")["id"]
    args = _args(["pratham", "revoke", sid])
    args.func(args)
    assert store.get_student(sid)["status"] == "revoked"
