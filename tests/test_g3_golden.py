# tests/test_g3_golden.py
"""G3 acceptance golden threads (spec §9):
1. publish over HTTP — gated, delegates, 409 on unknown;
2. enroll -> login -> me -> revoke;
3. identity never touches governance.db (physical isolation).
"""
from fastapi.testclient import TestClient

from samagra import config
from samagra.api import app as api_app


def test_golden_publish_over_http(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "GOVERNANCE_DB", tmp_path / "governance.db")
    monkeypatch.setattr(config, "DATA_DB", tmp_path / "samagra.db")
    monkeypatch.setattr(config, "EXPORT_DIR", tmp_path / "exports")
    monkeypatch.setattr(config, "PUBLISHED_DIR", tmp_path / "published")
    from samagra.governance import store as gov
    gov._INITIALIZED.clear(); gov.ensure_tables()
    monkeypatch.chdir(tmp_path)

    def fake_export_one(slug, variant, **kw):
        out = tmp_path / f"{slug}-{variant}.html"
        out.write_text(f"<h1>{slug} {variant}</h1>", encoding="utf-8")
        return {"variant": variant, "html": str(out), "docx": None, "gdoc": None}
    monkeypatch.setattr("samagra.lectures.export.export_one", fake_export_one)

    from samagra.factory import run as factory
    proposals = factory.plan("textbook:circular-motion", dry=False)
    rev = next(p for p in proposals if p["line"] == "revision")
    factory.approve(rev["assignment_id"])
    factory.build(rev["assignment_id"])

    c = TestClient(api_app.app)
    # publish over HTTP (gate disabled in tests -> reaches handler on loopback)
    r = c.post("/api/factory/publish", json={"chapter": "circular-motion", "lanes": ["revision"]})
    assert r.status_code == 200
    assert "revision" in r.json()["result"]["published"]
    # the corpus is now readable via the G2 public surface
    assert "circular-motion" in c.get("/api/published").json()["chapters"]
    # unknown chapter -> 409
    assert c.post("/api/factory/publish", json={"chapter": "nope"}).status_code == 409
    gov._INITIALIZED.clear()


def test_golden_enroll_login_me_revoke(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PRATHAM_DB", tmp_path / "pratham.db")
    from samagra.pratham import store, service
    store._INITIALIZED.clear()
    res = service.enroll("Asha")
    c = TestClient(api_app.app)
    assert c.post("/api/learn/login", json={"code": res["code"]}).json()["student"]["name"] == "Asha"
    assert c.get("/api/learn/me").json()["student"]["name"] == "Asha"
    # a wrong code is an identical 401
    assert c.post("/api/learn/login", json={"code": "wrong"}).status_code == 401
    service.revoke(res["id"])
    assert c.get("/api/learn/me").json() == {"student": None}  # session invalidated
    store._INITIALIZED.clear()


def test_identity_never_touches_governance_db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PRATHAM_DB", tmp_path / "pratham.db")
    monkeypatch.setattr(config, "GOVERNANCE_DB", tmp_path / "governance.db")
    from samagra.governance import store as gov
    from samagra.pratham import store as pstore, service
    gov._INITIALIZED.clear(); pstore._INITIALIZED.clear()
    gov.ensure_tables()
    before = (tmp_path / "governance.db").read_bytes()
    res = service.enroll("Asha")
    service.login(res["code"], client_key="ip1")
    service.revoke(res["id"])
    after = (tmp_path / "governance.db").read_bytes()
    assert before == after  # all identity writes land in pratham.db only
    gov._INITIALIZED.clear()
