# tests/test_qx_live_smoke.py
"""OPT-IN live smoke: paper + drill against the REAL combinedDBQues server (:8790).

Gated on an explicit flag so the standing pytest gate never needs the sidecar:
  SAMAGRA_LIVE_QX_SMOKE=1 python -m pytest tests/test_qx_live_smoke.py -v
Writes only under a tmp EXPORT_DIR; touches no governance store.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from samagra import config
from samagra.factory import paper


def _truthy(name):
    return (os.environ.get(name) or "").strip().lower() in {"1", "true", "yes", "on"}


pytestmark = pytest.mark.skipif(
    not _truthy("SAMAGRA_LIVE_QX_SMOKE"),
    reason="opt-in live smoke: set SAMAGRA_LIVE_QX_SMOKE=1 with combinedDBQues on :8790")


@pytest.fixture
def export_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "EXPORT_DIR", tmp_path / "exports")
    return tmp_path / "exports"


def test_gauss_law_paper_and_drill_live(export_dir):
    res_paper = paper.build_paper("gauss-law", variant="paper")
    res_drill = paper.build_paper("gauss-law", variant="drill")

    # Chapter-scoped listing beats the old 2-hit text search by construction.
    assert res_paper["questions"] > 2
    assert res_drill["questions"] == paper._DRILL_SIZE

    data = json.loads(Path(res_paper["json"]).read_text(encoding="utf-8"))
    assert data["chapter"] == "Electric Charges and Fields"

    # Zero duplicate projections survive (the run-evidence bug this slice fixes).
    projs = [" ".join(paper._TAG_RE.sub(" ", q["html"] or "").split()).lower()
             for q in data["questions"]]
    long_projs = [p for p in projs if len(p) >= paper._DEDUPE_MIN_CHARS]
    assert len(long_projs) == len(set(long_projs))

    html = Path(res_paper["html"]).read_text(encoding="utf-8")
    low = html.lower()
    for marker in ('class="answer"', "answer-label", "data-answer",
                   'class="solution"', "pq-ans", "pkey"):
        assert marker not in low                       # answer-free held live
    assert "data-tex=" in html                         # KaTeX spans present
    base = config.QX_SERVER_URL.rstrip("/")
    assert 'src="/asset?' not in html                  # assets absolutized
    if "/asset?" in html:
        assert f'src="{base}/asset?' in html
