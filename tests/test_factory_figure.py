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
