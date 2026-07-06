"""Phase F1 wiring: the figure Line, run_line routing, validate_product binary
branch, the lane-dispatched build() preflight, and the SAMAGRA_FIGURE_AUTOCAPTURE
capture gate. Offline: fake image + fake vision clients, isolated governance.db."""
from __future__ import annotations

from pathlib import Path

import pytest

from samagra import config
from samagra.factory import dispatch, figure, run
from samagra.factory.lines import LINES, classify
from samagra.governance import store


# ---------- lane registration ----------

def test_figure_line_registered_llm_optin_textbook():
    spec = LINES["figure"]
    assert spec.kind == "llm"
    assert spec.auto_fan is False                    # opt-in (F-D4 analogue)
    assert spec.source_prefixes == ("textbook:",)


def test_classify_textbook_excludes_figure():
    # figure is opt-in: NOT in the default textbook fan-out (like samadhan).
    assert "figure" not in classify("textbook:circular-motion")


def test_plan_lane_figure_proposes_only_that_lane():
    props = run.plan("textbook:circular-motion", dry=True, lane="figure")
    assert [p["line"] for p in props] == ["figure"]


# ---------- run_line routing ----------

class _FakeImg:
    def generate(self, prompt):
        return b"\x89PNG\r\n\x1a\nX"


class _FakeVis:
    def review_figure(self, png, brief, section):
        return {"verdicts": [{"idx": 0, "verdict": "ok", "rationale": "ok"}]}


# The genuine build_figures, captured at import BEFORE any monkeypatch replaces
# the module attribute — so a helper that fakes the clients never accidentally
# recurses into a prior fake (e.g. the boom->retry sequence in the rollback test).
_REAL_BUILD_FIGURES = figure.build_figures


def test_run_line_routes_figure_to_build_figures(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "EXPORT_DIR", tmp_path / "lectures")
    from samagra.lectures import render
    monkeypatch.setattr(render, "load_chapter", lambda slug: {
        "title": "T", "sections": [{"title": "S", "blocks": [
            {"type": "image-need", "brief": "b"}]}]})
    called = {}
    real = figure.build_figures
    def spy(slug, **kw):
        called["slug"] = slug
        return real(slug, image_client=_FakeImg(), vision_client=_FakeVis())
    monkeypatch.setattr(figure, "build_figures", spy)
    res = dispatch.run_line("figure", "circular-motion")
    assert called["slug"] == "circular-motion"
    assert res["variant"] == "figure"


# ---------- validate_product binary branch ----------

def test_validate_product_requires_a_png(tmp_path):
    # A gallery html present but ZERO png files on disk -> ValueError.
    html = tmp_path / "x-figures.html"
    html.write_text("<html>gallery</html>", encoding="utf-8")
    result = {"variant": "figure", "html": str(html), "json": None,
              "items": 1, "errors": 0, "verdicts": [{"idx": 0, "verdict": "ok"}],
              "figures": [{"idx": 1, "png": "fig-01.png"}]}
    with pytest.raises(ValueError):
        dispatch.validate_product("figure", result)


def test_validate_product_passes_with_a_png(tmp_path):
    figdir = tmp_path / "x-figures"
    figdir.mkdir()
    (figdir / "fig-01.png").write_bytes(b"\x89PNG\r\n\x1a\nX")
    html = tmp_path / "x-figures.html"
    html.write_text("<html>gallery</html>", encoding="utf-8")
    result = {"variant": "figure", "html": str(html), "json": None,
              "items": 1, "errors": 0, "verdicts": [{"idx": 0, "verdict": "ok"}],
              "figures": [{"idx": 1, "png": "fig-01.png"}]}
    dispatch.validate_product("figure", result)      # no raise


# ---------- build() capture gate + preflight + retryable ----------

@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "GOVERNANCE_DB", tmp_path / "governance.db")
    monkeypatch.setattr(config, "DATA_DB", tmp_path / "samagra.db")
    monkeypatch.setattr(config, "EXPORT_DIR", tmp_path / "lectures")
    store._INITIALIZED.clear()
    store.ensure_tables()
    monkeypatch.chdir(tmp_path)
    from samagra.lectures import render
    monkeypatch.setattr(render, "load_chapter", lambda slug: {
        "title": "Circular Motion", "sections": [{"title": "S", "blocks": [
            {"type": "image-need", "brief": "a spinning disc"}]}]})
    # figure preflight sees both clients configured.
    monkeypatch.setattr(figure.image_client, "configured", lambda: True)
    monkeypatch.setattr(figure.llm_client, "configured", lambda: True)
    yield tmp_path
    store._INITIALIZED.clear()


def _fake_build_figures_ok(monkeypatch):
    def fake(slug, **kw):
        return _REAL_BUILD_FIGURES(slug, image_client=_FakeImg(), vision_client=_FakeVis())
    monkeypatch.setattr(figure, "build_figures", fake)


def _approve_and_build(seed_ref):
    props = run.plan(seed_ref, dry=False, lane="figure")
    run.approve_seed(seed_ref)
    return run.build(props[0]["assignment_id"])


def test_autocapture_off_default_routes_to_changes(env, monkeypatch):
    monkeypatch.delenv("SAMAGRA_FIGURE_AUTOCAPTURE", raising=False)
    _fake_build_figures_ok(monkeypatch)
    res = _approve_and_build("textbook:circular-motion")
    assert res["status"] == "changes"                # conservative default (C3-equivalent)
    c = store.connect()
    try:
        verbs = [e["verb"] for e in store.list_events_for_assignment(c, res["assignment_id"])]
    finally:
        c.close()
    assert "product_created" in verbs                # the artifact WAS produced + recorded


def test_autocapture_on_clean_build_is_captured(env, monkeypatch):
    monkeypatch.setenv("SAMAGRA_FIGURE_AUTOCAPTURE", "1")
    _fake_build_figures_ok(monkeypatch)
    res = _approve_and_build("textbook:circular-motion")
    assert res["status"] == "captured"


def test_autocapture_on_error_verdict_routes_to_changes(env, monkeypatch):
    monkeypatch.setenv("SAMAGRA_FIGURE_AUTOCAPTURE", "1")
    class _ErrVis:
        def review_figure(self, png, brief, section):
            return {"verdicts": [{"idx": 0, "verdict": "error", "rationale": "wrong"}]}
    def fake(slug, **kw):
        return _REAL_BUILD_FIGURES(slug, image_client=_FakeImg(), vision_client=_ErrVis())
    monkeypatch.setattr(figure, "build_figures", fake)
    res = _approve_and_build("textbook:circular-motion")
    assert res["status"] == "changes"                # error -> changes even with autocapture on


def test_figure_preflight_refuses_before_intent_no_wedge(env, monkeypatch):
    monkeypatch.setattr(figure.image_client, "configured", lambda: False)
    props = run.plan("textbook:circular-motion", dry=False, lane="figure")
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


def test_figure_image_failure_rolls_back_and_is_retryable(env, monkeypatch):
    monkeypatch.setenv("SAMAGRA_FIGURE_AUTOCAPTURE", "1")
    class _BoomImg:
        def generate(self, prompt):
            raise RuntimeError("transient image-API 500")
    def boom(slug, **kw):
        return _REAL_BUILD_FIGURES(slug, image_client=_BoomImg(), vision_client=_FakeVis())
    monkeypatch.setattr(figure, "build_figures", boom)
    props = run.plan("textbook:circular-motion", dry=False, lane="figure")
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
    _fake_build_figures_ok(monkeypatch)
    assert run.build(aid)["status"] == "captured"


def test_empty_image_need_build_routes_to_changes_not_a_raise(env, monkeypatch):
    """A chapter with ZERO image-need blocks is a legitimate empty build (items=0,
    errors=0 — the Task 3 contract test_build_figures_empty_when_no_image_need pins)
    and must flow through validate_product to build()'s needs_review gate -> the
    terminal 'changes' status, never a validate_product ValueError + rollback.
    Mirrors the samadhan empty-brief -> changes precedent.

    Path choice: figure.preflight requires only chapter + configured clients (NOT
    >=1 brief), so the REAL path is exercised honestly with an empty-brief chapter
    fixture — no SAMAGRA_FIGURE_CAP=0 workaround needed."""
    monkeypatch.delenv("SAMAGRA_FIGURE_AUTOCAPTURE", raising=False)
    from samagra.lectures import render
    monkeypatch.setattr(render, "load_chapter", lambda slug: {
        "title": "Gauss Law", "sections": [
            {"title": "S", "blocks": [{"type": "prose", "html": "<p>x</p>"}]}]})
    _fake_build_figures_ok(monkeypatch)
    res = _approve_and_build("textbook:gauss-law")   # must NOT raise
    assert res["status"] == "changes"
    c = store.connect()
    try:
        verbs = [e["verb"] for e in store.list_events_for_assignment(c, res["assignment_id"])]
        a = [x for x in store.list_assignments(c) if x["id"] == res["assignment_id"]][0]
    finally:
        c.close()
    assert a["status"] == "changes"
    assert "product_created" in verbs                # the empty gallery WAS recorded
    assert "product_build_failed" not in verbs       # never the rollback path


def test_samadhan_preflight_unchanged(env, monkeypatch):
    # Regression pin: the samadhan lane still routes to samadhan.preflight, not
    # figure.preflight (the lane-dispatch must not break the D2 lane). build() calls
    # its own `samadhan` binding (run.py line: `from . import ... samadhan`), and
    # dispatch.run_line calls its own `samadhan` binding — both point at the one
    # module object, so patching the module attribute covers every call site.
    from samagra.factory import samadhan
    calls = {"preflight": 0}
    def spy_preflight(slug):
        calls["preflight"] += 1
        return None                                  # skip StyleSeed/key checks for the pin
    monkeypatch.setattr(samadhan, "preflight", spy_preflight)
    # Stub the produce step so we prove ONLY the preflight dispatch, not the D2 lane.
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
    assert calls["preflight"] == 1                   # samadhan.preflight WAS called
