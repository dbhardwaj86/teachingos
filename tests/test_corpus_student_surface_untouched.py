# tests/test_corpus_student_surface_untouched.py
"""T2.8 (F3) — slice-wide golden: exercising the entire corpus slice leaves the
student surface (/learn, /api/published*, /api/learn/*) BYTE-untouched, and no
corpus code path references governance.db / pratham.db."""
from __future__ import annotations

import inspect

from fastapi.testclient import TestClient

from samagra import config
from samagra.api.app import app

_STUDENT_READS = (
    "/learn",
    "/api/published",
    "/api/published/circular-motion/revision",
    "/api/learn/me",
    "/api/learn/next",
)


def _snapshot(client):
    out = {}
    for path in _STUDENT_READS:
        r = client.get(path)
        out[path] = (r.status_code, r.content)
    return out


def test_student_surface_byte_untouched_by_corpus_slice(tmp_path, monkeypatch):
    # isolate the durable stores so the golden runs on ephemeral state
    monkeypatch.setattr(config, "PUBLISHED_DIR", tmp_path / "published")
    monkeypatch.setattr(config, "PRATHAM_DB", tmp_path / "pratham.db")
    # corpus stores absent AND daemon transport failing — worst case
    monkeypatch.setattr(config, "GNOCR_BRAIN_DB", tmp_path / "a.db")
    monkeypatch.setattr(config, "ONEDPULL_BRAIN_DB", tmp_path / "b.db")
    monkeypatch.setattr(config, "LECTUREPDF_BRAIN", tmp_path / "brain")
    # freeze the manifest timestamp so /api/published is byte-comparable
    from samagra.factory.publish import store as pub_store
    monkeypatch.setattr(pub_store, "now", lambda: "2026-01-01T00:00:00Z")

    client = TestClient(app)
    baseline = _snapshot(client)

    # exercise the whole corpus surface: listings + serve (daemon down) +
    # hostile paths + an excluded answer family
    for name in ("gnocr", "onedpull", "lecturepdf"):
        client.get(f"/api/corpus/{name}")
        client.get(f"/api/corpus/{name}/serve/")
        client.get(f"/api/corpus/{name}/serve/api/stats")
        client.get(f"/api/corpus/{name}/serve/../../etc/passwd")
    client.get("/api/corpus/onedpull/serve/api/question/5")

    after = _snapshot(client)
    assert after == baseline  # response bytes + status identical


def test_corpus_code_paths_reference_no_governance_or_pratham():
    import re

    from samagra.adapters import gnocr, lecturepdf, onedpull
    from samagra.api import corpus_proxy

    import_re = re.compile(r"^\s*(from|import)\s+\S*(governance|pratham)",
                           re.MULTILINE)
    for mod in (corpus_proxy, gnocr, onedpull, lecturepdf):
        src = inspect.getsource(mod)
        assert not import_re.search(src), mod.__name__
        assert "GOVERNANCE_DB" not in src and "PRATHAM_DB" not in src, mod.__name__
