# tests/test_corpus_api.py
"""T2.7 — the /api/corpus/* endpoint family: gated listing + serve/proxy.
All upstream transports are injected fakes (monkeypatched get_proxy fetch) —
the daemons may be DOWN while this suite runs."""
from __future__ import annotations

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from samagra import config
from samagra.api import corpus_proxy, origin_auth
from samagra.api.app import app


# ---------- helpers ------------------------------------------------------
def _fake_fetch(status=200, ctype="application/json", body=b"{}"):
    def fetch(url, timeout, cap):
        return status, ctype, body
    return fetch


def _patch_fetch(monkeypatch, fetch):
    """Route the endpoint's proxy construction through an injected transport."""
    real = corpus_proxy.get_proxy

    def patched(name, **kw):
        kw["fetch"] = fetch
        return real(name, **kw)

    monkeypatch.setattr("samagra.api.app.corpus_proxy.get_proxy", patched)


def _gnocr_fixture(tmp_path, monkeypatch):
    db = tmp_path / "_brain" / "catalog.db"
    db.parent.mkdir(parents=True)
    c = sqlite3.connect(db)
    c.executescript(
        """
        CREATE TABLE documents (id INTEGER PRIMARY KEY, file_id INTEGER,
                                title TEXT, page_count INTEGER);
        CREATE TABLE topics (id INTEGER PRIMARY KEY, parent_id INTEGER,
                             name TEXT, ncert_ref TEXT);
        CREATE TABLE doc_topics (doc_id INTEGER, topic_id INTEGER);
        CREATE TABLE chunks (id INTEGER PRIMARY KEY, doc_id INTEGER, text_md TEXT);
        INSERT INTO documents VALUES (1, 1, 'Rotation Notes', 12);
        INSERT INTO topics VALUES (7, NULL, 'Rotation', 'ch7');
        INSERT INTO chunks VALUES (1, 1, 'torque');
        """)
    c.commit()
    c.close()
    monkeypatch.setattr(config, "GNOCR_ROOT", tmp_path)
    monkeypatch.setattr(config, "GNOCR_BRAIN_DB", db)


# ---------- listing ------------------------------------------------------
@pytest.mark.parametrize("name", ["gnocr", "onedpull", "lecturepdf"])
def test_list_empty_graceful(name, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "GNOCR_BRAIN_DB", tmp_path / "a.db")
    monkeypatch.setattr(config, "ONEDPULL_BRAIN_DB", tmp_path / "b.db")
    monkeypatch.setattr(config, "LECTUREPDF_BRAIN", tmp_path / "brain")
    r = TestClient(app).get(f"/api/corpus/{name}")
    assert r.status_code == 200  # never a 500
    body = r.json()
    assert body["available"] is False
    assert body["corpus"] == name
    assert body["artifacts"] == []


def test_list_populated(tmp_path, monkeypatch):
    _gnocr_fixture(tmp_path, monkeypatch)
    r = TestClient(app).get("/api/corpus/gnocr")
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is True
    assert body["summary"] == {"documents": 1, "topics": 1, "chunks": 1}
    assert len(body["artifacts"]) == 1
    assert body["artifacts"][0]["uid"] == "gnocr:1"


def test_list_unknown_corpus_404():
    r = TestClient(app).get("/api/corpus/evilcorp")
    assert r.status_code == 404


# ---------- origin gating (F2) -------------------------------------------
@pytest.mark.parametrize("name", ["gnocr", "onedpull", "lecturepdf"])
def test_endpoints_are_origin_gated(name):
    assert origin_auth.is_protected("GET", f"/api/corpus/{name}") is True
    assert origin_auth.is_protected("GET", f"/api/corpus/{name}/serve/anything") is True


def test_non_loopback_without_identity_403(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DISABLE_ORIGIN_AUTH", False)
    monkeypatch.setattr(config, "ACCESS_AUD", None)
    monkeypatch.setattr(config, "ACCESS_TEAM_DOMAIN", None)
    monkeypatch.setattr(config, "OWNER_EMAIL", None)
    monkeypatch.setattr(origin_auth, "_client_host", lambda req: "10.0.0.9")
    r = TestClient(app).get("/api/corpus/gnocr")
    assert r.status_code == 403
    r = TestClient(app).get("/api/corpus/gnocr/serve/api/stats")
    assert r.status_code == 403


# ---------- serve/proxy ---------------------------------------------------
def test_gnocr_serve_index_headers(monkeypatch):
    _patch_fetch(monkeypatch, _fake_fetch(
        ctype="text/html", body=b"<html><head></head><body>GN</body></html>"))
    r = TestClient(app).get("/api/corpus/gnocr/serve/")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["referrer-policy"] == "no-referrer"
    # F1: NO opaque-origin CSP on the same-origin trusted app
    assert "content-security-policy" not in r.headers
    assert b'<base href="/api/corpus/gnocr/serve/">' in r.content


def test_gnocr_serve_traversal_blocked(monkeypatch):
    _patch_fetch(monkeypatch, _fake_fetch())
    client = TestClient(app)
    for path in ("api/../stats", "%2e%2e/secrets", "api%5C..%5Cstats"):
        r = client.get(f"/api/corpus/gnocr/serve/{path}")
        assert r.status_code in (403, 404), path


def test_gnocr_serve_daemon_down_graceful(monkeypatch):
    def down(url, timeout, cap):
        raise ConnectionError("refused")

    _patch_fetch(monkeypatch, down)
    r = TestClient(app).get("/api/corpus/gnocr/serve/api/stats")
    assert r.status_code == 503  # graceful, never a 500 wedge
    assert "offline" in r.json()["hint"]


def test_onedpull_serve_answer_path_refused(monkeypatch):
    _patch_fetch(monkeypatch, _fake_fetch())
    r = TestClient(app).get("/api/corpus/onedpull/serve/api/question/5")
    assert r.status_code in (403, 404)


def test_lecturepdf_serve_read_apis_pass(monkeypatch):
    _patch_fetch(monkeypatch, _fake_fetch(body=b'{"ok": true}'))
    client = TestClient(app)
    for path in ("static/js/app.js", "api/stats", "api/lectures",
                 "api/query_lexical", "api/diagrams/png/r/d/n.png"):
        r = client.get(f"/api/corpus/lecturepdf/serve/{path}")
        assert r.status_code == 200, path


def test_lecturepdf_serve_write_apis_refused(monkeypatch):
    _patch_fetch(monkeypatch, _fake_fetch())
    client = TestClient(app)
    for path in ("api/compositions", "api/prep_pack", "api/reveal",
                 "api/excalidraw/open", "api/synthesize",
                 "api/questions/generate", "api/query"):
        r = client.get(f"/api/corpus/lecturepdf/serve/{path}")
        assert r.status_code in (403, 404), path
    # and POST is structurally unroutable on the GET-only route
    r = client.post("/api/corpus/lecturepdf/serve/api/compositions")
    assert r.status_code in (403, 405)


def test_media_type_js_css_png_over_endpoint(monkeypatch):
    _patch_fetch(monkeypatch, _fake_fetch(ctype="application/octet-stream",
                                          body=b"data"))
    client = TestClient(app)
    cases = {
        "static/js/app.js": "application/javascript",
        "static/css/app.css": "text/css",
        "api/diagrams/png/r/d/f.png": "image/png",
    }
    for path, want in cases.items():
        r = client.get(f"/api/corpus/lecturepdf/serve/{path}")
        assert r.headers["content-type"].split(";")[0] == want, path


def test_serve_unknown_corpus_404(monkeypatch):
    _patch_fetch(monkeypatch, _fake_fetch())
    r = TestClient(app).get("/api/corpus/evilcorp/serve/api/stats")
    assert r.status_code == 404
