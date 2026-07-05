# tests/test_g4_golden.py
"""Phase G4 golden threads (spec §7): the adaptive loop, write-path isolation,
anonymous invariance. Mirrors tests/test_g3_golden.py's style."""
import hashlib

from fastapi.testclient import TestClient

from samagra import config
from samagra.api import app as api_app
from samagra.factory.publish import read
from samagra.governance import store as gstore
from samagra.pratham import service

_MAN = {"chapters": {
    "circular-motion": {"title": "Circular Motion",
                        "artifacts": [{"lane": "revision"}, {"lane": "deck"}]},
}}


def _gov_bytes() -> bytes:
    gstore.ensure_tables()
    return config.GOVERNANCE_DB.read_bytes()


def test_golden_adaptive_loop_and_isolation(monkeypatch, tmp_path):
    monkeypatch.setattr(read, "published_manifest", lambda: _MAN)
    monkeypatch.setattr(config, "CONCEPT_GRAPH_DB", tmp_path / "absent.db", raising=False)
    gov_before = hashlib.sha256(_gov_bytes()).hexdigest()

    c = TestClient(api_app.app)
    code = service.enroll("Asha")["code"]
    assert c.post("/api/learn/login", json={"code": code}).status_code == 200

    q1 = c.get("/api/learn/next").json()
    assert ("circular-motion", "revision") in {(g["chapter"], g["lane"]) for g in q1["queue"]}

    assert c.post("/api/learn/progress",
                  json={"chapter": "circular-motion", "lane": "revision"}).json() == {"ok": True}

    q2 = c.get("/api/learn/next").json()
    assert ("circular-motion", "revision") not in {(g["chapter"], g["lane"]) for g in q2["queue"]}
    assert [(d["chapter"], d["lane"]) for d in q2["done"]] == [("circular-motion", "revision")]

    # Write-path isolation: the whole loop left governance.db BYTE-unchanged.
    assert hashlib.sha256(_gov_bytes()).hexdigest() == gov_before


def test_golden_anonymous_invariance(monkeypatch):
    monkeypatch.setattr(read, "published_manifest", lambda: _MAN)
    c = TestClient(api_app.app)
    assert c.get("/api/learn/next").status_code == 401
    assert c.post("/api/learn/progress",
                  json={"chapter": "circular-motion", "lane": "revision"}).status_code == 401
    # The public read surface is untouched by G4.
    assert c.get("/api/published").status_code == 200
