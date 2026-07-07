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


# --- Task 3: build_slides + preflight + poll (fake nlm client) -----------------
import json
from pathlib import Path

from samagra import config


class FakeNLM:
    """A fake NotebookLMClient scripting the whole slides lifecycle. Records the
    ordered method calls; studio_status returns pending K times then completed;
    download writes a fake PDF. Can be told to raise on a named step, or to fail on
    delete, to exercise the failure/cleanup paths. NEVER shells out."""
    def __init__(self, *, pending=1, raise_on=None, delete_raises=False,
                 status_failed=False, pdf=b"%PDF-1.4 fake"):
        self.calls = []
        self._pending = pending
        self._polls = 0
        self._raise_on = raise_on
        self._delete_raises = delete_raises
        self._status_failed = status_failed
        self._pdf = pdf

    def _maybe_raise(self, step):
        if self._raise_on == step:
            raise RuntimeError(f"nlm {step} failed")

    def create_notebook(self, title):
        self.calls.append("create_notebook")
        self._maybe_raise("create_notebook")
        return "nb_fake"

    def add_text_source(self, nb, text, *, wait_timeout):
        self.calls.append("add_text_source")
        self._maybe_raise("add_text_source")

    def create_slides(self, nb):
        self.calls.append("create_slides")
        self._maybe_raise("create_slides")

    def studio_status(self, nb):
        self.calls.append("studio_status")
        self._maybe_raise("studio_status")
        self._polls += 1
        if self._status_failed:
            return {"artifacts": [{"type": "slide_deck", "status": "failed", "id": "a1"}]}
        status = "completed" if self._polls > self._pending else "pending"
        return {"artifacts": [{"type": "slide_deck", "status": status, "id": "art_9"}]}

    def download_slide_deck(self, nb, artifact_id, out_path):
        self.calls.append("download_slide_deck")
        self._maybe_raise("download_slide_deck")
        Path(out_path).write_bytes(self._pdf)
        return out_path

    def delete_notebook(self, nb):
        self.calls.append("delete_notebook")
        if self._delete_raises:
            raise RuntimeError("nlm notebook delete failed")


@pytest.fixture()
def export(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "EXPORT_DIR", tmp_path / "lectures")
    # zero the poll interval so the bounded loop spins instantly (no real wait).
    monkeypatch.setenv("SAMAGRA_SLIDES_POLL_INTERVAL", "0")
    return tmp_path


@pytest.fixture()
def fake_chapter(monkeypatch):
    from samagra.lectures import render
    monkeypatch.setattr(render, "load_chapter", lambda slug: _CHAPTER)


def test_build_slides_happy_path_writes_wrapper_json_and_deck(export, fake_chapter, monkeypatch):
    monkeypatch.setattr(slides, "_sleep", lambda s: None)     # no real wait in tests
    nlm = FakeNLM(pending=2)
    res = slides.build_slides("circular-motion", nlm=nlm)
    assert res["variant"] == "slides"
    assert res["items"] == 1 and res["errors"] == 0
    # the synthetic owner-review verdict (D2) so _assert_review_clean passes.
    assert res["verdicts"] and res["verdicts"][0]["verdict"] == "changes"
    # ordered lifecycle: create -> source -> slides -> poll(>=1) -> download -> delete.
    assert nlm.calls[0] == "create_notebook"
    assert nlm.calls[1] == "add_text_source"
    assert nlm.calls[2] == "create_slides"
    assert "download_slide_deck" in nlm.calls
    assert nlm.calls[-1] == "delete_notebook"        # cleanup last
    # artifacts on disk.
    out = config.EXPORT_DIR / "circular-motion"
    assert (out / "circular-motion-slides.html").is_file()
    assert (out / "circular-motion-slides.json").is_file()
    assert (out / "circular-motion-slides" / "deck.pdf").stat().st_size > 0
    assert Path(res["html"]).is_file() and Path(res["json"]).is_file()
    data = json.loads(Path(res["json"]).read_text(encoding="utf-8"))
    assert data["deck_format"] == "pdf"
    assert data["deck_bytes"] > 0 and data["artifact_id"] == "art_9"


def test_wrapper_html_is_self_contained_data_uri(export, fake_chapter, monkeypatch):
    monkeypatch.setattr(slides, "_sleep", lambda s: None)
    res = slides.build_slides("circular-motion", nlm=FakeNLM(pending=0))
    html = Path(res["html"]).read_text(encoding="utf-8")
    assert "data:application/pdf;base64," in html
    assert "http://" not in html and "https://" not in html


def test_build_slides_deletes_notebook_in_finally_on_failure(export, fake_chapter, monkeypatch):
    # A download failure AFTER the notebook is created STILL deletes it.
    monkeypatch.setattr(slides, "_sleep", lambda s: None)
    nlm = FakeNLM(pending=0, raise_on="download_slide_deck")
    with pytest.raises(RuntimeError):
        slides.build_slides("circular-motion", nlm=nlm)
    assert "delete_notebook" in nlm.calls             # cleanup ran despite the raise


def test_delete_failure_does_not_mask_success(export, fake_chapter, monkeypatch):
    # The deck downloaded fine; the delete fails -> the SUCCESS is still returned.
    monkeypatch.setattr(slides, "_sleep", lambda s: None)
    nlm = FakeNLM(pending=0, delete_raises=True)
    res = slides.build_slides("circular-motion", nlm=nlm)   # no raise
    assert res["variant"] == "slides" and res["items"] == 1


def test_delete_failure_does_not_convert_failure_to_success(export, fake_chapter, monkeypatch):
    # The download fails AND the delete fails -> the PRIMARY (download) raise wins.
    monkeypatch.setattr(slides, "_sleep", lambda s: None)
    nlm = FakeNLM(pending=0, raise_on="download_slide_deck", delete_raises=True)
    with pytest.raises(RuntimeError) as e:
        slides.build_slides("circular-motion", nlm=nlm)
    assert "download slide-deck" in str(e.value) or "download_slide_deck" in str(e.value)


def test_poll_explicit_failed_status_raises(export, fake_chapter, monkeypatch):
    monkeypatch.setattr(slides, "_sleep", lambda s: None)
    nlm = FakeNLM(status_failed=True)
    with pytest.raises(RuntimeError):
        slides.build_slides("circular-motion", nlm=nlm)
    assert "delete_notebook" in nlm.calls             # still cleans up


def test_poll_timeout_raises_timeouterror(export, fake_chapter, monkeypatch):
    # Never completes within the timeout -> TimeoutError; cleanup still runs.
    monkeypatch.setenv("SAMAGRA_SLIDES_TIMEOUT", "0")     # immediate timeout
    monkeypatch.setattr(slides, "_sleep", lambda s: None)
    nlm = FakeNLM(pending=9999)
    with pytest.raises(TimeoutError):
        slides.build_slides("circular-motion", nlm=nlm)
    assert "delete_notebook" in nlm.calls


def test_source_truncation_flag_recorded(export, monkeypatch):
    monkeypatch.setattr(slides, "_sleep", lambda s: None)
    monkeypatch.setattr(slides, "_SOURCE_MAX_CHARS", 20)
    from samagra.lectures import render
    big = {"title": "Big Chapter Title Here", "sections": [
        {"title": "S", "blocks": [{"type": "prose", "html": "y" * 500}]}]}
    monkeypatch.setattr(render, "load_chapter", lambda slug: big)
    res = slides.build_slides("big", nlm=FakeNLM(pending=0))
    data = json.loads(Path(res["json"]).read_text(encoding="utf-8"))
    assert data["source_truncated"] is True


def test_preflight_ok(export, fake_chapter, monkeypatch):
    monkeypatch.setattr(slides.notebooklm_client, "configured", lambda: True)
    slides.preflight("circular-motion")               # no raise


def test_preflight_missing_chapter_raises(export, monkeypatch):
    from samagra.lectures import render
    def boom(slug):
        raise FileNotFoundError(slug)
    monkeypatch.setattr(render, "load_chapter", boom)
    monkeypatch.setattr(slides.notebooklm_client, "configured", lambda: True)
    with pytest.raises(FileNotFoundError):
        slides.preflight("nope")


def test_preflight_unconfigured_raises(export, fake_chapter, monkeypatch):
    monkeypatch.setattr(slides.notebooklm_client, "configured", lambda: False)
    with pytest.raises(RuntimeError):
        slides.preflight("circular-motion")


def test_preflight_requires_no_styleseed(export, fake_chapter, monkeypatch, tmp_path):
    # Unlike samadhan, the slides preflight does NOT require a committed StyleSeed.
    monkeypatch.setattr(config, "STYLESEED_DIR", tmp_path / "no-styleseed-here")
    monkeypatch.setattr(slides.notebooklm_client, "configured", lambda: True)
    slides.preflight("circular-motion")               # no raise despite absent StyleSeed


def test_build_slides_clamps_hostile_dl_format_to_pdf(export, fake_chapter, monkeypatch):
    # A client carrying a path-traversal _dl_format must NOT form the deck path from
    # it — build_slides clamps an unknown value to pdf at the write boundary.
    monkeypatch.setattr(slides, "_sleep", lambda s: None)
    nlm = FakeNLM(pending=0)
    nlm._dl_format = "../../evil"
    res = slides.build_slides("circular-motion", nlm=nlm)
    assert res["deck_format"] == "pdf"
    assert res["deck"].endswith("deck.pdf")          # path stayed inside the workdir
    data = json.loads(Path(res["json"]).read_text(encoding="utf-8"))
    assert data["deck_format"] == "pdf"
