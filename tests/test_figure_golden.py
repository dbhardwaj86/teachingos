"""Phase F1 golden threads: the plan->approve->build->(changes/capture) loop, the
publish-compatibility of the gallery html, and governance-byte consistency (no
migration). Offline: fake image + fake vision clients, isolated stores. Mirrors
tests/test_g4_golden.py's governance-byte discipline."""
from __future__ import annotations

import base64
import hashlib
from pathlib import Path

import pytest

from samagra import config
from samagra.factory import figure, run
from samagra.factory.publish import read as pub_read, run as pub_run
from samagra.governance import store


_FAKE_PNG_BYTES = b"\x89PNG\r\n\x1a\nGOLDEN"


class _FakeImg:
    def generate(self, prompt):
        return _FAKE_PNG_BYTES


class _FakeVis:
    def review_figure(self, png, brief, section):
        return {"verdicts": [{"idx": 0, "verdict": "ok", "rationale": "ok"}]}


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "GOVERNANCE_DB", tmp_path / "governance.db")
    monkeypatch.setattr(config, "DATA_DB", tmp_path / "samagra.db")
    monkeypatch.setattr(config, "EXPORT_DIR", tmp_path / "lectures")
    monkeypatch.setattr(config, "PUBLISHED_DIR", tmp_path / "published")
    store._INITIALIZED.clear()
    store.ensure_tables()
    monkeypatch.chdir(tmp_path)
    from samagra.lectures import render
    monkeypatch.setattr(render, "load_chapter", lambda slug: {
        "title": "Circular Motion", "sections": [{"title": "S", "blocks": [
            {"type": "image-need", "brief": "a spinning disc"}]}]})
    monkeypatch.setattr(figure.image_client, "configured", lambda: True)
    monkeypatch.setattr(figure.llm_client, "configured", lambda: True)
    # build() calls dispatch.run_line("figure", slug) -> figure.build_figures(slug)
    # with NO injected clients, so replace build_figures with a version that injects
    # the offline fakes (the real production path, just with fakes swapped in).
    monkeypatch.setattr(figure, "build_figures", lambda slug, **kw: _real_build(slug))
    yield tmp_path
    store._INITIALIZED.clear()


# Capture the genuine engine once at import time, before any monkeypatch, so the
# fixture's replacement can still reach the real build_figures with fakes injected.
_REAL_BUILD_FIGURES = figure.build_figures


def _real_build(slug):
    return _REAL_BUILD_FIGURES(slug, image_client=_FakeImg(), vision_client=_FakeVis())


def test_golden_default_routes_to_changes_governance_schema_stable(env, monkeypatch):
    monkeypatch.delenv("SAMAGRA_FIGURE_AUTOCAPTURE", raising=False)
    # schema version BEFORE (no migration expected across the whole loop).
    ver_before = store.connect().execute("PRAGMA user_version").fetchone()[0]
    props = run.plan("textbook:circular-motion", dry=False, lane="figure")
    run.approve_seed("textbook:circular-motion")
    res = run.build(props[0]["assignment_id"])
    assert res["status"] == "changes"                 # conservative default
    ver_after = store.connect().execute("PRAGMA user_version").fetchone()[0]
    assert ver_after == ver_before                    # NO migration / schema bump


def test_golden_publish_compat_on_gallery_html(env, monkeypatch):
    # With autocapture ON the build captures; publish --lanes figure copies the
    # gallery html + json; the G2 read surface serves it sha-verified. (The `env`
    # fixture already routes figure.build_figures through the offline fakes.)
    monkeypatch.setenv("SAMAGRA_FIGURE_AUTOCAPTURE", "1")
    props = run.plan("textbook:circular-motion", dry=False, lane="figure")
    run.approve_seed("textbook:circular-motion")
    assert run.build(props[0]["assignment_id"])["status"] == "captured"

    pub = pub_run.publish("circular-motion", lanes=["figure"])
    assert pub["chapter"] == "circular-motion"       # publish succeeded

    art = pub_read.resolve_artifact("circular-motion", "figure", "html")
    assert art is not None
    assert art["media_type"].startswith("text/html")
    # sha-verified serving: the resolver re-hashes the bytes against the manifest.
    assert art["sha256"] == hashlib.sha256(art["bytes"]).hexdigest()
    # The published gallery is self-contained (data-URI PNG embedded) AND the
    # ACTUAL fake PNG bytes round-tripped end-to-end: the data-URI payload is the
    # base64 of the exact bytes the (fake) image API returned — not merely the
    # template's hardcoded "data:image/png;base64," prefix.
    assert b"data:image/png;base64," in art["bytes"]
    assert base64.b64encode(_FAKE_PNG_BYTES) in art["bytes"]
