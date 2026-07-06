"""Phase F1 figure lane — pure target selection + prompt build. Offline; a frozen
in-memory fixture chapter, no live corpus dependency."""
import pytest

from samagra.factory import figure


# A frozen fixture chapter mirroring the REAL schema:
#   chapter.title; section.title; block {"type":"image-need","brief": "..."}.
_CHAPTER = {
    "title": "Circular Motion",
    "sections": [
        {"title": "Uniform circular motion",
         "blocks": [
             {"type": "prose", "html": "<p>text</p>"},
             {"type": "image-need", "brief": "A disc spinning about a vertical axis."},
         ]},
        {"title": "Coriolis force",
         "blocks": [
             {"type": "equation", "tex": "F=ma"},
             {"type": "image-need", "brief": "A rotating frame with the Coriolis vector."},
             {"type": "callout", "html": "<div>note</div>"},
         ]},
    ],
}


def test_targets_selects_only_image_need_in_document_order():
    ts = figure._targets(_CHAPTER)
    assert len(ts) == 2
    assert ts[0]["brief"] == "A disc spinning about a vertical axis."
    assert ts[1]["brief"] == "A rotating frame with the Coriolis vector."
    # idx is 1-based document order; section title carried alongside.
    assert [t["idx"] for t in ts] == [1, 2]
    assert ts[0]["section"] == "Uniform circular motion"
    assert ts[1]["section"] == "Coriolis force"


def test_targets_prompt_is_preamble_plus_frame_plus_brief_verbatim():
    ts = figure._targets(_CHAPTER)
    p = ts[1]["prompt"]
    assert p.startswith(figure._STYLE_PREAMBLE)
    assert "Chapter: Circular Motion." in p
    assert "Section: Coriolis force." in p
    assert "A rotating frame with the Coriolis vector." in p   # brief verbatim


def test_targets_empty_when_no_image_need():
    ch = {"title": "Gauss Law", "sections": [
        {"title": "S1", "blocks": [{"type": "prose", "html": "<p>x</p>"}]}]}
    assert figure._targets(ch) == []


def test_targets_caps_at_figure_cap(monkeypatch):
    monkeypatch.setattr(figure, "_FIGURE_CAP", 2)
    ch = {"title": "Many", "sections": [
        {"title": "S", "blocks": [
            {"type": "image-need", "brief": f"fig {i}"} for i in range(5)]}]}
    ts = figure._targets(ch)
    assert len(ts) == 2
    assert [t["brief"] for t in ts] == ["fig 0", "fig 1"]   # first N in order


def test_figure_cap_default_is_six():
    assert figure._FIGURE_CAP == 6


def test_targets_empty_when_cap_is_zero(monkeypatch):
    monkeypatch.setattr(figure, "_FIGURE_CAP", 0)
    assert figure._targets(_CHAPTER) == []


def test_targets_empty_when_cap_is_negative(monkeypatch):
    monkeypatch.setattr(figure, "_FIGURE_CAP", -1)
    assert figure._targets(_CHAPTER) == []


# --- Task 3: build_figures + preflight (fake image + fake vision clients) ------
import base64
import json
from pathlib import Path

from samagra import config


class FakeImageClient:
    """Returns a fixed tiny PNG per call; records prompts; can be told to raise on
    the K-th call to exercise the whole-build-raise path."""
    _PNG = b"\x89PNG\r\n\x1a\nFAKE-PNG-BYTES"

    def __init__(self, raise_on=None):
        self.prompts = []
        self._raise_on = raise_on

    def generate(self, prompt):
        self.prompts.append(prompt)
        if self._raise_on is not None and len(self.prompts) == self._raise_on:
            raise RuntimeError("transient image-API 500")
        return self._PNG


class FakeVisionClient:
    """Returns a scripted verdict list from review_figure. NEVER accepts a
    StyleSeed (mirrors llm_client.review_figure's real signature)."""
    def __init__(self, verdicts):
        self._verdicts = verdicts
        self.calls = []

    def review_figure(self, png_bytes, brief, section_text):
        self.calls.append((png_bytes, brief, section_text))
        return {"verdicts": self._verdicts}


@pytest.fixture()
def export(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "EXPORT_DIR", tmp_path / "lectures")
    return tmp_path


@pytest.fixture()
def fake_chapter(monkeypatch):
    from samagra.lectures import render
    monkeypatch.setattr(render, "load_chapter", lambda slug: _CHAPTER)


def _ok_verdicts(n):
    return [{"idx": i, "verdict": "ok", "rationale": "matches"} for i in range(n)]


def test_build_figures_happy_path_writes_pngs_gallery_json(export, fake_chapter):
    img = FakeImageClient()
    vis = FakeVisionClient(_ok_verdicts(2))
    res = figure.build_figures("circular-motion", image_client=img, vision_client=vis)
    assert res["variant"] == "figure"
    assert res["items"] == 2 and res["errors"] == 0 and res["capped"] is False
    assert len(res["verdicts"]) == 2
    # Two loose PNGs on disk, non-empty, zero-padded doc-order names.
    figdir = config.EXPORT_DIR / "circular-motion" / "circular-motion-figures"
    assert (figdir / "fig-01.png").stat().st_size > 0
    assert (figdir / "fig-02.png").stat().st_size > 0
    # Gallery html + json sidecar present.
    assert Path(res["html"]).is_file() and Path(res["json"]).is_file()
    data = json.loads(Path(res["json"]).read_text(encoding="utf-8"))
    assert len(data["figures"]) == 2
    assert data["figures"][0]["verdict"] == "ok"


def test_gallery_embeds_data_uris_and_escapes_untrusted_text(export, monkeypatch):
    from samagra.lectures import render
    ch = {"title": "Gauss & Fields", "sections": [
        {"title": "Flux <through> a cube", "blocks": [
            {"type": "image-need", "brief": "A cube with E>0 and label <n̂>"}]}]}
    monkeypatch.setattr(render, "load_chapter", lambda slug: ch)
    img = FakeImageClient()
    vis = FakeVisionClient([{"idx": 0, "verdict": "error", "rationale": "label <wrong>"}])
    res = figure.build_figures("gauss-law", image_client=img, vision_client=vis)
    html = Path(res["html"]).read_text(encoding="utf-8")
    # PNG embedded as a data URI — no external image reference.
    assert "data:image/png;base64," in html
    assert "src=\"fig-" not in html and "http://" not in html and "https://" not in html.replace("fonts.googleapis", "")
    # Untrusted brief + rationale HTML-escaped at the boundary (the C1 lesson).
    assert "E>0" not in html and "E&gt;0" in html
    assert "label <wrong>" not in html and "label &lt;wrong&gt;" in html
    # JSON keeps raw text + raw base64.
    data = json.loads(Path(res["json"]).read_text(encoding="utf-8"))
    assert data["figures"][0]["brief"] == "A cube with E>0 and label <n̂>"
    assert base64.b64decode(data["figures"][0]["png_b64"])   # decodes


def test_build_figures_empty_when_no_image_need(export, monkeypatch):
    from samagra.lectures import render
    monkeypatch.setattr(render, "load_chapter",
                        lambda slug: {"title": "Empty", "sections": []})
    res = figure.build_figures("gauss-law",
                               image_client=FakeImageClient(),
                               vision_client=FakeVisionClient([]))
    assert res["items"] == 0 and res["errors"] == 0
    # No image call, no PNG written — an empty set drives build()'s changes path.
    figdir = config.EXPORT_DIR / "gauss-law" / "gauss-law-figures"
    assert not any(figdir.glob("fig-*.png")) if figdir.exists() else True


def test_missing_verdict_fails_closed(export, fake_chapter):
    # 2 targets but only 1 verdict -> the unreviewed figure counts as an error.
    img = FakeImageClient()
    vis = FakeVisionClient([{"idx": 0, "verdict": "ok", "rationale": "ok"}])
    res = figure.build_figures("circular-motion", image_client=img, vision_client=vis)
    assert res["items"] == 2 and res["errors"] == 1


def test_error_verdict_is_counted(export, fake_chapter):
    img = FakeImageClient()
    vis = FakeVisionClient([{"idx": 0, "verdict": "error", "rationale": "wrong vectors"},
                            {"idx": 1, "verdict": "ok", "rationale": "ok"}])
    res = figure.build_figures("circular-motion", image_client=img, vision_client=vis)
    assert res["errors"] == 1


def test_whole_build_raises_on_image_failure_no_partial_return(export, fake_chapter):
    # Second image call raises -> build_figures raises (no partial result dict).
    img = FakeImageClient(raise_on=2)
    vis = FakeVisionClient(_ok_verdicts(2))
    with pytest.raises(RuntimeError):
        figure.build_figures("circular-motion", image_client=img, vision_client=vis)


def test_stale_figs_cleared_on_rebuild(export, monkeypatch):
    from samagra.lectures import render
    # First build: 2 figures.
    monkeypatch.setattr(render, "load_chapter", lambda slug: _CHAPTER)
    figure.build_figures("circular-motion",
                         image_client=FakeImageClient(),
                         vision_client=FakeVisionClient(_ok_verdicts(2)))
    figdir = config.EXPORT_DIR / "circular-motion" / "circular-motion-figures"
    assert len(list(figdir.glob("fig-*.png"))) == 2
    # Rebuild with a SHORTER set (1 figure) -> no orphan fig-02.png.
    one = {"title": "Circular Motion", "sections": [
        {"title": "S", "blocks": [{"type": "image-need", "brief": "just one"}]}]}
    monkeypatch.setattr(render, "load_chapter", lambda slug: one)
    figure.build_figures("circular-motion",
                         image_client=FakeImageClient(),
                         vision_client=FakeVisionClient(_ok_verdicts(1)))
    assert sorted(p.name for p in figdir.glob("fig-*.png")) == ["fig-01.png"]


def test_preflight_ok(export, fake_chapter, monkeypatch):
    monkeypatch.setattr(figure.image_client, "configured", lambda: True)
    monkeypatch.setattr(figure.llm_client, "configured", lambda: True)
    figure.preflight("circular-motion")   # no raise


def test_preflight_missing_chapter_raises(export, monkeypatch):
    from samagra.lectures import render
    def boom(slug):
        raise FileNotFoundError(slug)
    monkeypatch.setattr(render, "load_chapter", boom)
    monkeypatch.setattr(figure.image_client, "configured", lambda: True)
    monkeypatch.setattr(figure.llm_client, "configured", lambda: True)
    with pytest.raises(FileNotFoundError):
        figure.preflight("nope")


def test_preflight_image_unconfigured_raises(export, fake_chapter, monkeypatch):
    monkeypatch.setattr(figure.image_client, "configured", lambda: False)
    monkeypatch.setattr(figure.llm_client, "configured", lambda: True)
    with pytest.raises(RuntimeError):
        figure.preflight("circular-motion")


def test_preflight_vision_unconfigured_raises(export, fake_chapter, monkeypatch):
    monkeypatch.setattr(figure.image_client, "configured", lambda: True)
    monkeypatch.setattr(figure.llm_client, "configured", lambda: False)
    with pytest.raises(RuntimeError):
        figure.preflight("circular-motion")


def test_preflight_requires_no_styleseed(export, fake_chapter, monkeypatch, tmp_path):
    # Unlike samadhan, the figure preflight does NOT require a committed StyleSeed.
    monkeypatch.setattr(config, "STYLESEED_DIR", tmp_path / "no-styleseed-here")
    monkeypatch.setattr(figure.image_client, "configured", lambda: True)
    monkeypatch.setattr(figure.llm_client, "configured", lambda: True)
    figure.preflight("circular-motion")   # no raise despite absent StyleSeed
