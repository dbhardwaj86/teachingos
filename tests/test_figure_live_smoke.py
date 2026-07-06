"""OPT-IN live smoke: one real figure build end-to-end against the configured image
provider + a real vision review. Gated on an EXPLICIT flag (SAMAGRA_LIVE_IMAGE_SMOKE),
NOT merely on the key: config.py auto-loads the gitignored .env, so a key-only gate
would fire this on every `pytest` run — billing tokens + hitting the network during
the standing gate. Requiring a separate flag keeps the standing CI gate strictly
offline. Run it manually to validate the real image boundary:
  SAMAGRA_LIVE_IMAGE_SMOKE=1 OPENAI_API_KEY=… python -m pytest tests/test_figure_live_smoke.py -v
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from samagra import config
from samagra.clients import image_client, llm_client
from samagra.factory import figure


def _truthy(name):
    return (os.environ.get(name) or "").strip().lower() in {"1", "true", "yes", "on"}


pytestmark = pytest.mark.skipif(
    not (_truthy("SAMAGRA_LIVE_IMAGE_SMOKE")
         and image_client.configured() and llm_client.configured()),
    reason="opt-in live smoke: set SAMAGRA_LIVE_IMAGE_SMOKE=1 + a configured image+vision key")


def test_live_figure_build_circular_motion(tmp_path, monkeypatch):
    try:
        from samagra.lectures import render
        content = render.load_chapter("circular-motion")
    except FileNotFoundError:
        pytest.skip("circular-motion chapter not present in this checkout")
    if not figure._targets(content):
        pytest.skip("circular-motion has no image-need briefs in this checkout")
    monkeypatch.setattr(config, "EXPORT_DIR", tmp_path / "lectures")
    # COST BOUND: caps the live smoke at 2 generation + 2 vision calls max. The env
    # var alone won't work here — _FIGURE_CAP is read at module import — so patch
    # the module attribute directly.
    monkeypatch.setattr(figure, "_FIGURE_CAP", 2)
    res = figure.build_figures("circular-motion")     # real image + real vision clients
    assert res["items"] >= 1
    assert isinstance(res["errors"], int)
    assert Path(res["html"]).is_file() and Path(res["json"]).is_file()
    figdir = config.EXPORT_DIR / "circular-motion" / "circular-motion-figures"
    assert any(figdir.glob("fig-*.png"))              # >=1 real PNG written
    assert len(res["verdicts"]) == res["items"]       # a real vision verdict per figure
