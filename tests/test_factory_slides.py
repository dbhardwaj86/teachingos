"""Phase F2 slides lane — pure source-text projection + data-URI wrapper HTML.
Offline; a frozen in-memory fixture chapter + fake PDF bytes, no live corpus, no
nlm."""
import base64

import pytest

from samagra.factory import slides


_CHAPTER = {
    "title": "Circular Motion",
    "subtitle": "Uniform & non-uniform",
    "sections": [
        {"title": "Uniform circular motion",
         "blocks": [
             {"type": "prose", "html": "<p>The speed is constant.</p>"},
             {"type": "equation", "tex": "a = v^2/r"},
         ]},
        {"title": "Coriolis force",
         "blocks": [
             {"type": "callout", "html": "<div>Rotating frames add fictitious forces.</div>"},
         ]},
    ],
}


# ---------- source-text projection ----------

def test_source_text_carries_title_headings_and_body():
    txt = slides._source_text(_CHAPTER)
    assert "Circular Motion" in txt
    assert "Uniform circular motion" in txt
    assert "Coriolis force" in txt
    assert "The speed is constant." in txt        # prose html stripped to text
    assert "a = v^2/r" in txt                       # equation tex carried
    assert "Rotating frames add fictitious forces." in txt


def test_source_text_strips_html_tags():
    txt = slides._source_text(_CHAPTER)
    assert "<p>" not in txt and "<div>" not in txt


def test_source_text_empty_chapter_is_nonempty_title_only():
    txt = slides._source_text({"title": "Gauss Law", "sections": []})
    assert "Gauss Law" in txt


def test_source_text_truncates_to_bounded_prefix(monkeypatch):
    monkeypatch.setattr(slides, "_SOURCE_MAX_CHARS", 40)
    big = {"title": "Big", "sections": [
        {"title": "S", "blocks": [{"type": "prose", "html": "x" * 500}]}]}
    txt, truncated = slides._source_text_bounded(big)
    assert len(txt) <= 40
    assert truncated is True


def test_source_text_bounded_not_truncated_when_small():
    txt, truncated = slides._source_text_bounded(_CHAPTER)
    assert truncated is False


def test_source_max_chars_stays_windows_cmdline_safe():
    # The bounded source is passed to `nlm source add --text <text>` as ONE argv
    # element; Windows caps the whole command line at 32767 chars (CreateProcess).
    # Pin the cap so a max-size chapter can never overflow the live subprocess call
    # (the Task-1 concern) — for ANY content, not just prose. list2cmdline's absolute
    # worst-case expansion is 2x (every char a literal `"` -> `\"`), so we prove BOTH
    # the adversarial all-quotes bound AND a realistic LaTeX-dense sample stay under
    # 32767 at the max cap length.
    import subprocess
    assert slides._SOURCE_MAX_CHARS <= 16000
    adversarial = '"' * slides._SOURCE_MAX_CHARS   # 2x-expansion worst case
    realistic = ("The field \\vec{E} = \\frac{kq}{r^2} points radially. " * 1000)[
        :slides._SOURCE_MAX_CHARS]
    for text in (adversarial, realistic):
        argv = ["nlm", "source", "add", "nb_0000000000", "--text", text,
                "--wait", "--wait-timeout", "900"]
        assert len(subprocess.list2cmdline(argv)) < 32767


# ---------- data-URI wrapper HTML ----------

_PDF = b"%PDF-1.4\nfake-deck-bytes\n%%EOF"


def test_wrapper_embeds_pdf_data_uri_and_download_link():
    html = slides._wrapper_html("Circular Motion", _PDF, deck_format="pdf",
                                embed_max=8 * 1024 * 1024)
    b64 = base64.b64encode(_PDF).decode("ascii")
    assert f"data:application/pdf;base64,{b64}" in html
    assert "<embed" in html and 'type="application/pdf"' in html
    assert "download" in html                        # a same-page download link
    # self-contained: no external references.
    assert "http://" not in html and "https://" not in html
    assert 'src="deck' not in html


def test_wrapper_escapes_untrusted_title():
    html = slides._wrapper_html("Gauss & Fields <cube>", _PDF, deck_format="pdf",
                                embed_max=8 * 1024 * 1024)
    assert "Gauss & Fields <cube>" not in html
    assert "Gauss &amp; Fields &lt;cube&gt;" in html


def test_wrapper_oversize_deck_degrades_to_download_only_card():
    # A deck larger than embed_max wraps as a download-only card (no <embed>), still
    # self-contained.
    html = slides._wrapper_html("Big Deck", _PDF, deck_format="pdf", embed_max=4)
    b64 = base64.b64encode(_PDF).decode("ascii")
    assert "<embed" not in html                      # no inline embed above the cap
    assert f"data:application/pdf;base64,{b64}" in html   # download link still self-contained
    assert "download" in html


def test_wrapper_pptx_is_download_card_not_embed():
    pptx = b"PK\x03\x04 fake pptx"
    html = slides._wrapper_html("Deck", pptx, deck_format="pptx",
                                embed_max=8 * 1024 * 1024)
    assert "<embed" not in html                      # pptx is not browser-renderable inline
    b64 = base64.b64encode(pptx).decode("ascii")
    assert (f"data:application/vnd.openxmlformats-officedocument."
            f"presentationml.presentation;base64,{b64}") in html
    assert "download" in html
