"""OPT-IN live smoke: one real slides build end-to-end against live NotebookLM via
the `nlm` CLI. Gated on an EXPLICIT flag (SAMAGRA_LIVE_SLIDES_SMOKE) AND
notebooklm_client.configured() (both required — interactive Google auth may be
absent in headless/subagent/CI, and generation is slow/flaky, so the standing gate
stays 100% offline and this NEVER runs by default). Run it manually to validate the
real NotebookLM subprocess boundary (the FIRST live validation, and the confirming
check of the exact download format):
  SAMAGRA_LIVE_SLIDES_SMOKE=1 python -m pytest tests/test_slides_live_smoke.py -v
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from samagra import config
from samagra.clients import notebooklm_client
from samagra.factory import slides


def _truthy(name):
    return (os.environ.get(name) or "").strip().lower() in {"1", "true", "yes", "on"}


pytestmark = pytest.mark.skipif(
    not (_truthy("SAMAGRA_LIVE_SLIDES_SMOKE") and notebooklm_client.configured()),
    reason="opt-in live smoke: set SAMAGRA_LIVE_SLIDES_SMOKE=1 + an authed `nlm` (nlm login)")


def test_live_slides_build_circular_motion(tmp_path, monkeypatch):
    try:
        from samagra.lectures import render
        render.load_chapter("circular-motion")
    except FileNotFoundError:
        pytest.skip("circular-motion chapter not present in this checkout")
    monkeypatch.setattr(config, "EXPORT_DIR", tmp_path / "lectures")
    res = slides.build_slides("circular-motion")      # real nlm client, live NotebookLM
    assert res["variant"] == "slides"
    assert res["items"] == 1
    assert Path(res["html"]).is_file() and Path(res["json"]).is_file()
    deck = Path(res["deck"])
    assert deck.is_file() and deck.stat().st_size > 0   # a real deck was downloaded
    html = Path(res["html"]).read_text(encoding="utf-8")
    assert "data:application/pdf;base64," in html or "data:application/" in html
