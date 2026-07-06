"""OPT-IN live smoke: one real Samadhan end-to-end against the configured LLM provider.

Gated on an EXPLICIT opt-in flag (SAMAGRA_LIVE_LLM_SMOKE), NOT merely on the key:
config.py auto-loads the gitignored .env, so once the owner configures a provider
key a key-only gate would fire this on every `pytest` run — billing tokens + hitting
the network during the standing gate. Requiring a separate flag keeps the standing
CI gate strictly offline. Run it manually to validate the real generation boundary
(provider-aware: anthropic default, or SAMAGRA_LLM_PROVIDER=openai):
  SAMAGRA_LIVE_LLM_SMOKE=1 ANTHROPIC_API_KEY=… python -m pytest tests/test_samadhan_live_smoke.py -v
  SAMAGRA_LIVE_LLM_SMOKE=1 SAMAGRA_LLM_PROVIDER=openai OPENAI_API_KEY=… python -m pytest tests/test_samadhan_live_smoke.py -v
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from samagra import config
from samagra.clients import llm_client
from samagra.factory import samadhan
from samagra.factory.style import profile as P


def _truthy(name):
    return (os.environ.get(name) or "").strip().lower() in {"1", "true", "yes", "on"}


pytestmark = pytest.mark.skipif(
    not (_truthy("SAMAGRA_LIVE_LLM_SMOKE") and llm_client.configured()),
    reason="opt-in live smoke: set SAMAGRA_LIVE_LLM_SMOKE=1 + a configured provider key")


def test_live_samadhan_circular_motion(tmp_path, monkeypatch):
    if P.load_current() is None:
        pytest.skip("no committed StyleSeed (run `factory style-extract`)")
    try:
        from samagra.lectures import render
        render.load_chapter("circular-motion")
    except FileNotFoundError:
        pytest.skip("circular-motion chapter not present in this checkout")
    monkeypatch.setattr(config, "EXPORT_DIR", tmp_path / "lectures")
    res = samadhan.build_samadhan("circular-motion")
    assert res["items"] >= 1
    assert isinstance(res["errors"], int)
    assert Path(res["html"]).is_file() and Path(res["json"]).is_file()
