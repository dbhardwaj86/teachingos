"""Phase F2 wiring: the slides Line, run_line routing, validate_product slides
branch, the lane-dispatched build() preflight, and the SAMAGRA_SLIDES_AUTOCAPTURE
capture gate. Offline: a fake nlm client, isolated governance.db."""
from __future__ import annotations

from pathlib import Path

import pytest

from samagra import config
from samagra.factory import dispatch, run, slides
from samagra.factory.lines import LINES, classify
from samagra.governance import store


# ---------- lane registration ----------

def test_slides_line_registered_llm_optin_textbook():
    spec = LINES["slides"]
    assert spec.kind == "llm"
    assert spec.auto_fan is False                    # opt-in (F-D4 analogue)
    assert spec.source_prefixes == ("textbook:",)


def test_classify_textbook_excludes_slides():
    # slides is opt-in: NOT in the default textbook fan-out (like samadhan/figure).
    assert "slides" not in classify("textbook:circular-motion")
    # regression pin: the default fan-out is UNCHANGED.
    assert classify("textbook:circular-motion") == [
        "revision", "lecture", "deck", "paper", "drill"]


def test_plan_lane_slides_proposes_only_that_lane():
    props = run.plan("textbook:circular-motion", dry=True, lane="slides")
    assert [p["line"] for p in props] == ["slides"]


# ---------- run_line routing ----------

class _FakeNLM:
    def __init__(self):
        self.calls = []
    def create_notebook(self, title):
        self.calls.append("create"); return "nb_1"
    def add_text_source(self, nb, text, *, wait_timeout):
        self.calls.append("source")
    def create_slides(self, nb):
        self.calls.append("slides")
    def studio_status(self, nb):
        return {"artifacts": [{"type": "slide_deck", "status": "completed", "id": "a1"}]}
    def download_slide_deck(self, nb, artifact_id, out_path):
        Path(out_path).write_bytes(b"%PDF-1.4 fake"); return out_path
    def delete_notebook(self, nb):
        self.calls.append("delete")
    _dl_format = "pdf"


# The genuine build_slides, captured at import BEFORE any monkeypatch replaces the
# module attribute — so a helper that injects the fake nlm client never accidentally
# recurses into a prior fake (the boom->retry sequence in the rollback test would
# otherwise recurse until RecursionError). Mirrors F1's _REAL_BUILD_FIGURES.
_REAL_BUILD_SLIDES = slides.build_slides


def test_run_line_routes_slides_to_build_slides(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "EXPORT_DIR", tmp_path / "lectures")
    monkeypatch.setattr(slides, "_sleep", lambda s: None)
    from samagra.lectures import render
    monkeypatch.setattr(render, "load_chapter", lambda slug: {
        "title": "T", "sections": [{"title": "S", "blocks": [
            {"type": "prose", "html": "<p>x</p>"}]}]})
    called = {}
    real = slides.build_slides
    def spy(slug, **kw):
        called["slug"] = slug
        return real(slug, nlm=_FakeNLM())
    monkeypatch.setattr(slides, "build_slides", spy)
    res = dispatch.run_line("slides", "circular-motion")
    assert called["slug"] == "circular-motion"
    assert res["variant"] == "slides"


# ---------- validate_product slides branch ----------

def test_validate_product_requires_the_deck_file(tmp_path):
    # A wrapper html present but the working deck file MISSING -> ValueError.
    html = tmp_path / "x-slides.html"
    html.write_text("<html>wrapper</html>", encoding="utf-8")
    result = {"variant": "slides", "html": str(html), "json": None,
              "deck": str(tmp_path / "x-slides" / "deck.pdf"),
              "items": 1, "errors": 0, "verdicts": [{"idx": 0, "verdict": "changes"}]}
    with pytest.raises(ValueError):
        dispatch.validate_product("slides", result)


def test_validate_product_passes_with_deck(tmp_path):
    workdir = tmp_path / "x-slides"
    workdir.mkdir()
    (workdir / "deck.pdf").write_bytes(b"%PDF-1.4 fake")
    html = tmp_path / "x-slides.html"
    html.write_text("<html>wrapper</html>", encoding="utf-8")
    result = {"variant": "slides", "html": str(html), "json": None,
              "deck": str(workdir / "deck.pdf"),
              "items": 1, "errors": 0, "verdicts": [{"idx": 0, "verdict": "changes"}]}
    dispatch.validate_product("slides", result)      # no raise


# ---------- build() capture gate + preflight + retryable ----------

@pytest.fixture()
def envfx(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "GOVERNANCE_DB", tmp_path / "governance.db")
    monkeypatch.setattr(config, "DATA_DB", tmp_path / "samagra.db")
    monkeypatch.setattr(config, "EXPORT_DIR", tmp_path / "lectures")
    monkeypatch.setattr(slides, "_sleep", lambda s: None)
    store._INITIALIZED.clear()
    store.ensure_tables()
    monkeypatch.chdir(tmp_path)
    from samagra.lectures import render
    monkeypatch.setattr(render, "load_chapter", lambda slug: {
        "title": "Circular Motion", "sections": [{"title": "S", "blocks": [
            {"type": "prose", "html": "<p>the chapter</p>"}]}]})
    monkeypatch.setattr(slides.notebooklm_client, "configured", lambda: True)
    yield tmp_path
    store._INITIALIZED.clear()


def _fake_build_slides_ok(monkeypatch):
    def fake(slug, **kw):
        return _REAL_BUILD_SLIDES(slug, nlm=_FakeNLM())    # captured real, NOT the patched attr
    monkeypatch.setattr(slides, "build_slides", fake)


def _approve_and_build(seed_ref):
    props = run.plan(seed_ref, dry=False, lane="slides")
    run.approve_seed(seed_ref)
    return run.build(props[0]["assignment_id"])


def test_autocapture_off_default_routes_to_changes(envfx, monkeypatch):
    monkeypatch.delenv("SAMAGRA_SLIDES_AUTOCAPTURE", raising=False)
    _fake_build_slides_ok(monkeypatch)
    res = _approve_and_build("textbook:circular-motion")
    assert res["status"] == "changes"                # conservative default
    c = store.connect()
    try:
        verbs = [e["verb"] for e in store.list_events_for_assignment(c, res["assignment_id"])]
    finally:
        c.close()
    assert "product_created" in verbs                # the artifact WAS produced + recorded


def test_autocapture_on_clean_build_is_captured(envfx, monkeypatch):
    monkeypatch.setenv("SAMAGRA_SLIDES_AUTOCAPTURE", "1")
    _fake_build_slides_ok(monkeypatch)
    res = _approve_and_build("textbook:circular-motion")
    assert res["status"] == "captured"


def test_slides_preflight_refuses_before_intent_no_wedge(envfx, monkeypatch):
    monkeypatch.setattr(slides.notebooklm_client, "configured", lambda: False)
    props = run.plan("textbook:circular-motion", dry=False, lane="slides")
    run.approve_seed("textbook:circular-motion")
    aid = props[0]["assignment_id"]
    with pytest.raises(RuntimeError):
        run.build(aid)
    c = store.connect()
    try:
        verbs = [e["verb"] for e in store.list_events_for_assignment(c, aid)]
        a = [x for x in store.list_assignments(c) if x["id"] == aid][0]
    finally:
        c.close()
    assert "product_building" not in verbs and a["status"] == "approved"   # not wedged


def test_slides_failure_rolls_back_and_is_retryable(envfx, monkeypatch):
    monkeypatch.setenv("SAMAGRA_SLIDES_AUTOCAPTURE", "1")
    class _BoomNLM(_FakeNLM):
        def create_slides(self, nb):
            raise RuntimeError("nlm slides create failed")
    def boom(slug, **kw):
        return _REAL_BUILD_SLIDES(slug, nlm=_BoomNLM())    # captured real, NOT the patched attr
    monkeypatch.setattr(slides, "build_slides", boom)
    props = run.plan("textbook:circular-motion", dry=False, lane="slides")
    run.approve_seed("textbook:circular-motion")
    aid = props[0]["assignment_id"]
    with pytest.raises(RuntimeError):
        run.build(aid)
    c = store.connect()
    try:
        a = [x for x in store.list_assignments(c) if x["id"] == aid][0]
        verbs = [e["verb"] for e in store.list_events_for_assignment(c, aid)]
    finally:
        c.close()
    assert a["status"] == "approved"                 # not wedged (local-write lane rollback)
    assert "product_build_failed" in verbs and "product_created" not in verbs
    # retry with a working client -> succeeds and captures.
    _fake_build_slides_ok(monkeypatch)
    assert run.build(aid)["status"] == "captured"


def test_samadhan_and_figure_preflight_unchanged(envfx, monkeypatch):
    # Regression pin: the samadhan + figure lanes still route to THEIR own preflight,
    # not slides.preflight (the lane-dispatch must not break the D2/F1 lanes).
    from samagra.factory import samadhan, figure
    calls = {"samadhan": 0}
    def spy_preflight(slug):
        calls["samadhan"] += 1
        return None                                  # skip StyleSeed/key checks for the pin
    monkeypatch.setattr(samadhan, "preflight", spy_preflight)
    (config.EXPORT_DIR).mkdir(parents=True, exist_ok=True)
    (config.EXPORT_DIR / "s.html").write_text("<h1>s</h1>", encoding="utf-8")
    monkeypatch.setattr(
        samadhan, "build_samadhan",
        lambda slug: {"variant": "samadhan",
                      "html": str(config.EXPORT_DIR / "s.html"),
                      "json": None, "items": 1, "errors": 0,
                      "verdicts": [{"idx": 0, "verdict": "ok"}]})
    props = run.plan("textbook:circular-motion", dry=False, lane="samadhan")
    run.approve_seed("textbook:circular-motion")
    run.build(props[0]["assignment_id"])
    assert calls["samadhan"] == 1                     # samadhan.preflight WAS called
    # figure.preflight is a distinct callable and is untouched by the slides arm.
    assert figure.preflight is not slides.preflight
