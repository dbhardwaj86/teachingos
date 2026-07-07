"""Phase F2 golden threads: the plan->approve->build->(changes/capture) loop, the
no-migration invariant, and the publish-compatibility of the wrapper html (the deck
embedded as a data URI reaches /learn via the G1/G2 pipeline with ZERO code change).
Offline: a fake nlm client, isolated stores. Mirrors tests/test_figure_golden.py's
governance-schema discipline."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from samagra import config
from samagra.factory import run, slides
from samagra.factory.publish import read as pub_read, run as pub_run
from samagra.governance import store


class _FakeNLM:
    def create_notebook(self, title):
        return "nb_g"
    def add_text_source(self, nb, text, *, wait_timeout):
        pass
    def create_slides(self, nb):
        pass
    def studio_status(self, nb):
        return {"artifacts": [{"type": "slide_deck", "status": "completed", "id": "a1"}]}
    def download_slide_deck(self, nb, artifact_id, out_path):
        Path(out_path).write_bytes(b"%PDF-1.4 golden-deck-bytes %%EOF")
        return out_path
    def delete_notebook(self, nb):
        pass
    _dl_format = "pdf"


# Capture the genuine engine once at import time, before any monkeypatch, so the
# fixture's replacement can still reach the real build_slides with the fake injected.
_REAL_BUILD_SLIDES = slides.build_slides


def _real_build(slug):
    return _REAL_BUILD_SLIDES(slug, nlm=_FakeNLM())


@pytest.fixture()
def envfx(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "GOVERNANCE_DB", tmp_path / "governance.db")
    monkeypatch.setattr(config, "DATA_DB", tmp_path / "samagra.db")
    monkeypatch.setattr(config, "EXPORT_DIR", tmp_path / "lectures")
    monkeypatch.setattr(config, "PUBLISHED_DIR", tmp_path / "published")
    monkeypatch.setattr(slides, "_sleep", lambda s: None)
    store._INITIALIZED.clear()
    store.ensure_tables()
    monkeypatch.chdir(tmp_path)
    from samagra.lectures import render
    monkeypatch.setattr(render, "load_chapter", lambda slug: {
        "title": "Circular Motion", "sections": [{"title": "S", "blocks": [
            {"type": "prose", "html": "<p>the chapter</p>"}]}]})
    monkeypatch.setattr(slides.notebooklm_client, "configured", lambda: True)
    # build() calls dispatch.run_line("slides", slug) -> slides.build_slides(slug)
    # with NO injected client, so replace build_slides with a version that injects
    # the offline fake (the real production path, just with the fake swapped in).
    monkeypatch.setattr(slides, "build_slides", lambda slug, **kw: _real_build(slug))
    yield tmp_path
    store._INITIALIZED.clear()


def test_golden_default_routes_to_changes_governance_schema_stable(envfx, monkeypatch):
    monkeypatch.delenv("SAMAGRA_SLIDES_AUTOCAPTURE", raising=False)
    # schema version BEFORE (no migration expected across the whole loop).
    ver_before = store.connect().execute("PRAGMA user_version").fetchone()[0]
    props = run.plan("textbook:circular-motion", dry=False, lane="slides")
    run.approve_seed("textbook:circular-motion")
    res = run.build(props[0]["assignment_id"])
    assert res["status"] == "changes"                 # conservative default
    ver_after = store.connect().execute("PRAGMA user_version").fetchone()[0]
    assert ver_after == ver_before                    # NO migration / schema bump


def test_golden_no_new_governance_table(envfx, monkeypatch):
    monkeypatch.delenv("SAMAGRA_SLIDES_AUTOCAPTURE", raising=False)
    c = store.connect()
    try:
        before = {r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    finally:
        c.close()
    props = run.plan("textbook:circular-motion", dry=False, lane="slides")
    run.approve_seed("textbook:circular-motion")
    run.build(props[0]["assignment_id"])
    c = store.connect()
    try:
        after = {r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    finally:
        c.close()
    assert after == before                            # slides adds NO governance table


def test_golden_publish_compat_on_wrapper_html(envfx, monkeypatch):
    # With autocapture ON the build captures; publish --lanes slides copies the
    # wrapper html + json; the G2 read surface serves it sha-verified with the PDF
    # data-URI embedded. (The `envfx` fixture already routes build_slides through the
    # offline fake.)
    monkeypatch.setenv("SAMAGRA_SLIDES_AUTOCAPTURE", "1")
    props = run.plan("textbook:circular-motion", dry=False, lane="slides")
    run.approve_seed("textbook:circular-motion")
    assert run.build(props[0]["assignment_id"])["status"] == "captured"

    pub = pub_run.publish("circular-motion", lanes=["slides"])
    assert pub["chapter"] == "circular-motion"        # publish succeeded

    art = pub_read.resolve_artifact("circular-motion", "slides", "html")
    assert art is not None
    assert art["media_type"].startswith("text/html")
    # sha-verified serving: the resolver re-hashes the bytes against the manifest.
    assert art["sha256"] == hashlib.sha256(art["bytes"]).hexdigest()
    # the published wrapper is self-contained (data-URI PDF embedded).
    assert b"data:application/pdf;base64," in art["bytes"]
