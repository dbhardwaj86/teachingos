# tests/test_config_corpus_roots.py
"""T2.1 — config roots + server URLs for the 3 read-only corpora
(GN-OCR, onedpulls, lecturepdfs). Mirrors the MCD_ROOT precedent."""
from __future__ import annotations

import importlib
from pathlib import Path

from samagra import config


def _reload():
    return importlib.reload(config)


def test_corpus_roots_are_env_overridable(monkeypatch, tmp_path):
    monkeypatch.setenv("SAMAGRA_GNOCR_ROOT", str(tmp_path / "gn"))
    monkeypatch.setenv("SAMAGRA_ONEDPULL_ROOT", str(tmp_path / "od"))
    monkeypatch.setenv("SAMAGRA_LECTUREPDF_ROOT", str(tmp_path / "lp"))
    try:
        cfg = _reload()
        assert cfg.GNOCR_ROOT == tmp_path / "gn"
        assert cfg.ONEDPULL_ROOT == tmp_path / "od"
        assert cfg.LECTUREPDF_ROOT == tmp_path / "lp"
        # derived paths follow the overridden roots
        assert cfg.GNOCR_BRAIN_DB == tmp_path / "gn" / "_brain" / "catalog.db"
        assert cfg.ONEDPULL_BRAIN_DB == tmp_path / "od" / "_brain" / "catalog.db"
        assert cfg.LECTUREPDF_BRAIN == tmp_path / "lp" / "brain"
    finally:
        monkeypatch.delenv("SAMAGRA_GNOCR_ROOT")
        monkeypatch.delenv("SAMAGRA_ONEDPULL_ROOT")
        monkeypatch.delenv("SAMAGRA_LECTUREPDF_ROOT")
        _reload()


def test_corpus_roots_have_sane_defaults():
    assert config.GNOCR_ROOT == Path(r"C:\SandBox\claude_box\claude-GN-OCR")
    assert config.ONEDPULL_ROOT == Path(r"C:\SandBox\gemini_box\onedpulls")
    assert config.LECTUREPDF_ROOT == Path(r"C:\SandBox\claude_box\lecturepdfs")
    assert config.GNOCR_BRAIN_DB == config.GNOCR_ROOT / "_brain" / "catalog.db"
    assert config.ONEDPULL_BRAIN_DB == config.ONEDPULL_ROOT / "_brain" / "catalog.db"
    assert config.LECTUREPDF_BRAIN == config.LECTUREPDF_ROOT / "brain"


def test_corpus_server_urls_default_to_local_ports():
    assert config.GNOCR_SERVER_URL == "http://127.0.0.1:8931"
    assert config.ONEDPULL_SERVER_URL == "http://127.0.0.1:8137"
    assert config.LECTUREPDF_SERVER_URL == "http://127.0.0.1:8000"
    # allowed-hosts siblings exist and default empty (loopback always allowed)
    assert config.GNOCR_SERVER_ALLOWED_HOSTS == ""
    assert config.ONEDPULL_SERVER_ALLOWED_HOSTS == ""
    assert config.LECTUREPDF_SERVER_ALLOWED_HOSTS == ""
