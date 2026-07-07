"""The slides lane engine (Phase F2 — the second, final Phase-F lane, and SAMAGRA's
first subprocess/external-CLI generation boundary).

One textbook chapter (seed 'textbook:<slug>') -> a NotebookLM-generated slide deck:
render the chapter to plain text -> create an EPHEMERAL notebook via the `nlm` CLI
-> add the text source -> kick off async slide generation -> SYNCHRONOUSLY poll
`nlm studio status` until the deck is ready (bounded by SAMAGRA_SLIDES_TIMEOUT) ->
download the PDF -> wrap it in a self-contained data-URI HTML (the only shape G1/G2
can publish) -> DELETE the ephemeral notebook in a `finally` -> return a
factory-compatible result dict under EXPORT_DIR/<slug>/.

NO StyleSeed (NotebookLM composes the deck from the source; there is no SAMAGRA
prompt to condition), so the DEC-8 reviewer firewall is trivially structural. NO
model review — the default posture (SAMAGRA_SLIDES_AUTOCAPTURE off) routes every
deck build to `changes` for owner eyes. NO AUDIO — the client exposes no audio verb.
"""
from __future__ import annotations

import base64
import html as _html
import json
import os
import re
import time
import uuid

from .. import config
from ..clients import notebooklm_client
from ..lectures import render

_MEDIA_TYPES = {
    "pdf": "application/pdf",
    "pptx": ("application/vnd.openxmlformats-officedocument."
             "presentationml.presentation"),
}

# Bound the source text fed to `nlm source add --text`; a chapter longer than this
# is truncated to a prefix (manifest records source_truncated=True). This is ALSO a
# HARD, content-independent Windows-safety rail: `--text <chapter>` is one argv
# element, and Windows caps the WHOLE command line at 32767 chars (CreateProcess).
# subprocess.list2cmdline's ABSOLUTE worst-case expansion is 2x (every char a literal
# `"` -> `\"`), so a 16000-char cap can never exceed 32002 for the text arg even
# adversarially — under the limit for ANY content (not just prose that lacks quote
# storms). A slide deck is an owner-reviewed summary artifact, so a ~2600-word prefix
# is an ample seed; if the owner's live smoke shows truncation hurts deck quality,
# the localized upgrade is to write the text to a temp file and switch add_text_source
# to `nlm source add --file <tmp>` (the method signature already takes text, not argv,
# so the swap is internal). Rarely hit — most chapters project well under 16000.
_SOURCE_MAX_CHARS = 16000

# Decks larger than this (bytes) wrap as a download-only card (no inline <embed>),
# still self-contained. Overridable via SAMAGRA_SLIDES_EMBED_MAX (default 8MB).
_DEFAULT_EMBED_MAX = 8 * 1024 * 1024

_TAG_RE = re.compile(r"<[^>]+>")


def _embed_max() -> int:
    raw = os.environ.get("SAMAGRA_SLIDES_EMBED_MAX")
    try:
        return int(raw) if raw not in (None, "") else _DEFAULT_EMBED_MAX
    except ValueError:
        return _DEFAULT_EMBED_MAX


def _strip_html(s: str) -> str:
    return _TAG_RE.sub(" ", str(s or "")).strip()


def _block_text(block: dict) -> str:
    """The plain-ish text of one block (prose/callout html stripped; equation tex
    carried; image-need briefs included as context)."""
    return _strip_html(block.get("html") or block.get("tex") or block.get("brief") or "")


def _source_text(content: dict) -> str:
    """PURE: a clean text document for the whole chapter (title + section headings +
    stripped block text). The whole-chapter generalization of figure._section_text.
    Deterministic; no LLM, no StyleSeed."""
    parts: list[str] = []
    title = str(content.get("title", "") or "")
    if title:
        parts.append(title)
    subtitle = str(content.get("subtitle", "") or "")
    if subtitle:
        parts.append(subtitle)
    for section in content.get("sections", []) or []:
        sec_title = str(section.get("title", "") or "")
        if sec_title:
            parts.append("")
            parts.append(sec_title)
        for block in section.get("blocks", []) or []:
            t = _block_text(block)
            if t:
                parts.append(t)
    return "\n".join(parts).strip()


def _source_text_bounded(content: dict) -> tuple[str, bool]:
    """The source text truncated to _SOURCE_MAX_CHARS. Returns (text, truncated)."""
    txt = _source_text(content)
    if len(txt) > _SOURCE_MAX_CHARS:
        return txt[:_SOURCE_MAX_CHARS], True
    return txt, False


# The wrapper is a SELF-CONTAINED single file: the deck is embedded as a data URI
# and there are NO external references, so the published .html renders standalone in
# the G2 reader's sandboxed iframe (CSP `sandbox allow-scripts`; a data-URI <embed>
# needs no script and no external host).
_WRAPPER_CSS = """
*{box-sizing:border-box}
body{margin:0;background:#fafafa;color:#1f2328;
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  line-height:1.6}
.wrap{max-width:960px;margin:0 auto;padding:32px 20px}
header.doc{margin-bottom:16px}
.kicker{color:#8a8f98;font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.04em}
h1{font-size:26px;margin:6px 0 2px}
.deck{width:100%;height:70vh;min-height:480px;border:1px solid #e3e3e6;border-radius:10px;background:#fff}
.dl{display:inline-block;margin-top:14px;padding:8px 14px;border:1px solid #d0d3d8;
  border-radius:8px;background:#fff;color:#1f2328;text-decoration:none;font-weight:600}
.note{color:#8a8f98;margin-top:10px;font-size:13px}
"""

_WRAPPER_DOC = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>{css}</style></head>
<body><div class="wrap">
<header class="doc"><div class="kicker">{kicker}</div><h1>{title}</h1></header>
{body}
</div></body></html>
"""


def _wrapper_html(title: str, deck_bytes: bytes, *, deck_format: str,
                  embed_max: int) -> str:
    """Self-contained wrapper: the deck embedded as a data URI (no external ref);
    the title HTML-escaped at the boundary (the C1 lesson). A PDF within embed_max
    renders inline via <embed> + a same-page download link; a PDF over embed_max, or
    any PPTX, degrades to a download-only card (still self-contained)."""
    media = _MEDIA_TYPES.get(deck_format, "application/octet-stream")
    b64 = base64.b64encode(deck_bytes).decode("ascii")
    data_uri = f"data:{media};base64,{b64}"
    esc_title = _html.escape(str(title))
    dl = (f'<a class="dl" download="{esc_title} slides.{deck_format}" '
          f'href="{data_uri}">Download the deck ({deck_format.upper()})</a>')
    inline = (deck_format == "pdf" and len(deck_bytes) <= embed_max)
    if inline:
        body = (f'<embed class="deck" type="application/pdf" src="{data_uri}">'
                f'<div>{dl}</div>')
    else:
        reason = ("deck too large to preview inline"
                  if deck_format == "pdf" else "PPTX is not previewable in-browser")
        body = (f'<div class="note">{_html.escape(reason)} — use the download link.</div>'
                f'<div>{dl}</div>')
    return _WRAPPER_DOC.format(
        title=esc_title, kicker=_html.escape("NotebookLM slide deck (Slides lane)"),
        css=_WRAPPER_CSS, body=body)


_POLL_TERMINAL_OK = "completed"
_POLL_TERMINAL_BAD = ("failed", "error")


def _timeout() -> int:
    raw = os.environ.get("SAMAGRA_SLIDES_TIMEOUT")
    try:
        return int(raw) if raw not in (None, "") else 900
    except ValueError:
        return 900


def _poll_interval() -> float:
    raw = os.environ.get("SAMAGRA_SLIDES_POLL_INTERVAL")
    try:
        val = float(raw) if raw not in (None, "") else 15.0
    except ValueError:
        val = 15.0
    return max(1.0, val)   # floor: a 0/tiny interval would busy-loop the real poll


def _sleep(seconds: float) -> None:
    """Indirection so tests can no-op the poll wait (monkeypatched). Never called
    with a real interval in the standing gate."""
    time.sleep(seconds)


def preflight(slug: str) -> None:
    """Anti-wedge pre-check (called by build() BEFORE recording intent): the chapter
    exists, `nlm` is present + authed, and the deck-format env knobs are valid. NO
    StyleSeed requirement, NO API key (nlm owns the Google creds). Raises
    FileNotFoundError / RuntimeError without writing anything."""
    render.load_chapter(slug)                           # FileNotFoundError if absent
    if not notebooklm_client.configured():
        raise RuntimeError(
            "nlm is not present or not authenticated (run `nlm login`) — refusing a "
            "slides build without an authed NotebookLM CLI")
    # Validate the deck-format env knobs BEFORE any intent is recorded (a bogus
    # SAMAGRA_SLIDES_FORMAT/LENGTH/DOWNLOAD_FORMAT must refuse here, not mid-build).
    # NotebookLMClient.__init__ validates them and is side-effect-free (no subprocess).
    notebooklm_client.NotebookLMClient()


def _slide_deck_artifact(status: dict) -> dict | None:
    """The slide-deck artifact record from a `studio status --json` payload, or None
    if not present yet. Tolerant of the artifact-list shape."""
    arts = status.get("artifacts") if isinstance(status, dict) else None
    for a in arts or []:
        t = str(a.get("type", "")).lower()
        if "slide" in t or "deck" in t:
            return a
    return None


def _poll_until_ready(nlm, nb: str, *, deadline: float) -> str:
    """SYNCHRONOUS S1 poll: studio_status until the slide deck is `completed` (return
    its artifact id), an explicit `failed`/`error` (RuntimeError), or the SHARED build
    `deadline` (an absolute time.monotonic() value) elapses (TimeoutError). The deadline
    is shared with the source-add stage so total build wall-clock stays within one
    SAMAGRA_SLIDES_TIMEOUT — not a fresh full budget per stage. The interval sleep goes
    through _sleep so tests never wait for real."""
    interval = _poll_interval()
    while True:
        art = _slide_deck_artifact(nlm.studio_status(nb))
        st = str((art or {}).get("status", "")).lower()
        if st == _POLL_TERMINAL_OK:
            aid = (art or {}).get("id")
            if not aid:
                raise RuntimeError("slide deck completed but carried no artifact id")
            return str(aid)
        if st in _POLL_TERMINAL_BAD:
            raise RuntimeError("NotebookLM slide generation reported a failed status")
        if time.monotonic() >= deadline:
            raise TimeoutError(
                f"slide generation did not complete within {_timeout()}s")
        _sleep(interval)


def build_slides(slug, *, nlm=None) -> dict:
    """Create an ephemeral NotebookLM notebook, generate + download a slide deck,
    wrap it into a self-contained data-URI HTML, and write the artifacts. The
    ephemeral notebook is deleted in a `finally` (a delete failure is logged and
    does NOT mask the primary outcome, nor convert a success into a rollback). Any
    step failure or a timeout raises the whole build (no partial RESULT) — build()
    rolls it back retryably. Clears the stale working dir before writing."""
    content = render.load_chapter(slug)                 # ground truth (raises if absent)
    client = nlm or notebooklm_client.NotebookLMClient()
    source_text, truncated = _source_text_bounded(content)

    out = config.EXPORT_DIR / slug
    out.mkdir(parents=True, exist_ok=True)
    workdir = out / f"{slug}-slides"
    for stale in workdir.glob("deck.*"):                # clear stale before writing (retry-safe)
        stale.unlink()
    workdir.mkdir(parents=True, exist_ok=True)

    title = str(content.get("title", slug) or slug)
    nb = None
    try:
        nb = client.create_notebook(f"SAMAGRA slides: {slug} {uuid.uuid4().hex[:8]}")
        # ONE shared wall-clock budget for the two blocking stages (source ingest +
        # generation poll) so the total honors SAMAGRA_SLIDES_TIMEOUT, not 2x it.
        deadline = time.monotonic() + _timeout()
        source_wait = max(1, int(deadline - time.monotonic()))
        client.add_text_source(nb, source_text, wait_timeout=source_wait)
        client.create_slides(nb)
        artifact_id = _poll_until_ready(client, nb, deadline=deadline)
        dl_format = getattr(client, "_dl_format", "pdf")
        if dl_format not in ("pdf", "pptx"):       # path-forming value — clamp at the write boundary
            dl_format = "pdf"
        deck_path = workdir / f"deck.{dl_format}"
        client.download_slide_deck(nb, artifact_id, deck_path)
        deck_bytes = deck_path.read_bytes()
        if not deck_bytes:
            raise RuntimeError("downloaded slide deck is empty")
    finally:
        if nb is not None:
            try:
                client.delete_notebook(nb)
            except Exception:  # noqa: BLE001 - a delete failure must NEVER mask the
                # primary outcome nor convert a success to a rollback. The ephemeral
                # notebook (titled `SAMAGRA slides:`) is harmless owner-pruneable
                # state. Deliberately swallowed; a concise log names the orphan id
                # WITHOUT echoing any nlm stderr / notebook content.
                import logging
                logging.getLogger(__name__).warning(
                    "slides: failed to delete ephemeral notebook %s (owner-pruneable)", nb)

    # The synthetic owner-review verdict (D2 3.4): items=1, errors=0, and a single
    # `changes` verdict so _assert_review_clean passes structurally, while the
    # conservative default clause routes to `changes` regardless.
    verdicts = [{"idx": 0, "verdict": "changes",
                 "rationale": "NotebookLM deck — owner review required"}]
    deck_b64 = base64.b64encode(deck_bytes).decode("ascii")
    embed_max = _embed_max()

    json_path = out / f"{slug}-slides.json"
    json_path.write_text(json.dumps({
        "slug": slug, "title": title, "deck_format": dl_format,
        "artifact_id": artifact_id, "deck_bytes": len(deck_bytes),
        "deck_b64": deck_b64, "source_truncated": truncated,
        "items": 1, "errors": 0, "verdicts": verdicts,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    html_path = out / f"{slug}-slides.html"
    html_path.write_text(
        _wrapper_html(title, deck_bytes, deck_format=dl_format, embed_max=embed_max),
        encoding="utf-8")

    return {"variant": "slides", "html": str(html_path), "json": str(json_path),
            "deck": str(deck_path), "deck_format": dl_format,
            "artifact_id": artifact_id, "source_truncated": truncated,
            "items": 1, "errors": 0, "verdicts": verdicts}
