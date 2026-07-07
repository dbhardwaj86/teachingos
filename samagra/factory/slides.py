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
import os
import re

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
