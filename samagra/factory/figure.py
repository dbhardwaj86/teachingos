"""The figure lane engine (Phase F1 — the first image-generation lane).

One textbook chapter (seed 'textbook:<slug>') -> rendered PNG figures for its
author-written `image-need` briefs: select targets (deterministic, document order,
capped) -> generate a PNG per brief -> an adversarial vision reviewer anchored ONLY
to the chapter ground truth (the brief + section text + the image; NEVER the
StyleSeed) -> write <slug>-figures/ PNGs + <slug>-figures.json + a self-contained
data-URI gallery <slug>-figures.html under EXPORT_DIR/<slug>/.

The prompt is DETERMINISTIC: a frozen style preamble + chapter/section frame + the
brief verbatim. No StyleSeed enters the figure prompt (E: minimal), so the DEC-8
reviewer firewall is trivially structural — there is no StyleSeed anywhere near
this lane. The publish gate is untouched: this writes LOCAL artifacts only;
capturing is build()'s job, and F1 defaults conservative (SAMAGRA_FIGURE_AUTOCAPTURE
off -> every build routes to `changes`).
"""
from __future__ import annotations

import hashlib
import html as _html
import json
import os

from .. import config
from ..clients import image_client, llm_client
from ..clients import image_client as _image_client_mod   # alias: the build_figures
from ..lectures import render                              # PARAMETER shadows the module

_FIGURE_CAP = int(os.environ.get("SAMAGRA_FIGURE_CAP", "6"))

# Frozen module constant — changing it is a reviewed commit. No StyleSeed (E).
_STYLE_PREAMBLE = (
    "A clean, labelled physics diagram for a JEE/NEET textbook. Neutral line-art "
    "on a transparent/white background, one accent colour, legible labels. No "
    "photorealism."
)


def _targets(content: dict) -> list[dict]:
    """PURE: every `image-need` block in document order, capped at _FIGURE_CAP.
    Each target = {idx (1-based doc order), section, brief, prompt}. The prompt is
    the frozen preamble + a chapter/section frame + the brief verbatim (no LLM in
    the prompt-build step, no StyleSeed)."""
    if _FIGURE_CAP <= 0:
        return []
    title = str(content.get("title", "") or "")
    targets: list[dict] = []
    idx = 0
    for section in content.get("sections", []) or []:
        sec_title = str(section.get("title", "") or "")
        for block in section.get("blocks", []) or []:
            if block.get("type") != "image-need":
                continue
            idx += 1
            brief = str(block.get("brief", "") or "")
            prompt = (
                f"{_STYLE_PREAMBLE}\n"
                f"Chapter: {title}.  Section: {sec_title}.\n"
                f"Figure brief: {brief}"
            )
            targets.append({"idx": idx, "section": sec_title,
                            "brief": brief, "prompt": prompt})
            if len(targets) >= _FIGURE_CAP:
                return targets
    return targets


# The gallery is a SELF-CONTAINED single file: every PNG is embedded as a data URI
# and there are NO external references (no CDN font/script, no <img src="fig-...">),
# so the published .html renders standalone in the reader's sandboxed iframe. We do
# NOT reuse render.DOC_TEMPLATE here — it pulls in Google Fonts + a CDN MathJax
# script, which would break self-containment (figures need no MathJax).
_GALLERY_CSS = """
*{box-sizing:border-box}
body{margin:0;background:#fafafa;color:#1f2328;
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  line-height:1.6}
.wrap{max-width:860px;margin:0 auto;padding:32px 20px}
header.doc{margin-bottom:20px}
.kicker{color:#8a8f98;font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.04em}
h1{font-size:26px;margin:6px 0 2px}
.sub{color:#8a8f98}
.figs{display:flex;flex-direction:column;gap:22px;margin-top:8px}
.fig-item{border:1px solid #e3e3e6;border-radius:10px;padding:14px 16px;background:#fff}
.fig-item img{max-width:100%;height:auto;border:1px solid #ececed;border-radius:6px}
.fig-sec{color:#8a8f98;font-weight:600;font-size:12px;margin-bottom:6px}
.fig-brief{margin:8px 0;color:#1f2328}
.fig-verdict{font-size:12px;font-weight:600;margin-top:6px}
.v-ok{color:#1a6f3c}.v-error{color:#9a2a2a}
@media print{.fig-item{break-inside:avoid}}
"""

_GALLERY_DOC = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>{css}</style></head>
<body><div class="wrap">
<header class="doc"><div class="kicker">{kicker}</div><h1>{title}</h1>
<div class="sub">{subtitle}</div></header>
{body}
</div></body></html>
"""


def preflight(slug: str) -> None:
    """Anti-wedge pre-check (called by build() BEFORE recording intent): the
    chapter exists, the image client is configured, and the vision (llm) client is
    configured. NO StyleSeed requirement (E: the figure prompt uses no StyleSeed).
    Raises FileNotFoundError / RuntimeError without writing anything."""
    render.load_chapter(slug)                       # FileNotFoundError if absent
    if not image_client.configured():
        try:
            key_var = image_client.required_key_var()
        except RuntimeError:
            key_var = "the image API key"
        raise RuntimeError(
            f"{key_var} is not set — refusing an image build without a key")
    if not llm_client.configured():
        try:
            key_var = llm_client.required_key_var()
        except RuntimeError:
            key_var = "the LLM API key"
        raise RuntimeError(
            f"{key_var} is not set — refusing a figure vision review without a key")


def _section_text(content: dict, section_title: str) -> str:
    """The plain-ish text of the named section, as ground truth for the reviewer."""
    for s in content.get("sections", []) or []:
        if str(s.get("title", "")) == section_title:
            return " ".join(
                str(b.get("html") or b.get("tex") or b.get("brief") or "")
                for b in s.get("blocks", []) or [])
    return ""


def _gallery_html(content: dict, figures: list[dict]) -> str:
    """Self-contained gallery: each PNG embedded as a data URI (no external image
    ref); the brief + rationale HTML-escaped at the boundary (the C1 lesson)."""
    parts = ['<section class="figs">']
    for f in figures:
        section = _html.escape(str(f.get("section", "")))
        brief = _html.escape(str(f.get("brief", "")))
        verdict = f.get("verdict", "ok")
        vcls = "v-error" if verdict == "error" else "v-ok"
        rationale = _html.escape(str(f.get("rationale", "")))
        data_uri = f"data:image/png;base64,{f['png_b64']}"
        parts.append(
            f'<article class="fig-item">'
            f'<div class="fig-sec">{f.get("idx")}. {section}</div>'
            f'<img alt="{brief}" src="{data_uri}">'
            f'<div class="fig-brief">{brief}</div>'
            f'<div class="fig-verdict {vcls}">reviewer: {_html.escape(str(verdict))}'
            f'{(" — " + rationale) if rationale else ""}</div>'
            f'</article>')
    parts.append("</section>")
    return _GALLERY_DOC.format(
        title=_html.escape(str(content.get("title", "Figures"))),
        subtitle=_html.escape(str(content.get("subtitle", ""))),
        kicker=_html.escape("Generated figures (Figure lane)"),
        css=_GALLERY_CSS,
        body="\n".join(parts))


def build_figures(slug, *, image_client=None, vision_client=None) -> dict:
    """Generate, vision-review (fail-closed), and write the figure gallery. Raises
    FileNotFoundError (no chapter) BEFORE any write; raises (no partial result) if
    ANY image call fails — build() rolls that back retryably. Clears stale
    fig-*.png before writing the new set so a shorter rebuild leaves no orphans."""
    import base64 as _b64

    content = render.load_chapter(slug)             # ground truth (raises if absent)
    targets = _targets(content)
    # NOTE: the `image_client` param shadows the imported module in this scope, so
    # the real-client default is constructed via the module ALIAS `_image_client_mod`.
    img = image_client or _image_client_mod.ImageClient()
    vis = vision_client or llm_client.LLMClient()

    figdir = config.EXPORT_DIR / slug / f"{slug}-figures"
    figdir.mkdir(parents=True, exist_ok=True)
    for stale in figdir.glob("fig-*.png"):          # clear stale before writing (retry-safe)
        stale.unlink()

    figures: list[dict] = []
    verdicts: list[dict] = []
    for t in targets:
        png = img.generate(t["prompt"])             # a raise here raises the whole build
        name = f"fig-{t['idx']:02d}.png"
        (figdir / name).write_bytes(png)
        section_text = _section_text(content, t["section"])
        vres = vis.review_figure(png, t["brief"], section_text)
        vlist = vres.get("verdicts", []) if isinstance(vres, dict) else []
        v = next((x for x in vlist if x.get("idx") == t["idx"] - 1), None)
        # FAIL-CLOSED: an unreviewed / non-ok figure counts as an error (mirrors
        # samadhan) so a partial-coverage reviewer can never let one reach capture.
        if v is None:
            v = {"verdict": "error", "rationale": "no reviewer verdict for this figure"}
        verdict = "ok" if v.get("verdict") == "ok" else "error"
        rationale = str(v.get("rationale", ""))
        verdicts.append({"idx": t["idx"] - 1, "verdict": verdict, "rationale": rationale})
        figures.append({
            "idx": t["idx"], "png": name, "brief": t["brief"], "section": t["section"],
            "verdict": verdict, "rationale": rationale,
            "sha256": hashlib.sha256(png).hexdigest(),
            "png_b64": _b64.b64encode(png).decode("ascii")})

    errors = sum(1 for f in figures if f["verdict"] == "error")
    capped = len([1 for s in content.get("sections", []) or []
                  for b in s.get("blocks", []) or []
                  if b.get("type") == "image-need"]) > len(targets)

    out = config.EXPORT_DIR / slug
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / f"{slug}-figures.json"
    json_path.write_text(json.dumps(
        {"slug": slug, "title": content.get("title", slug),
         "figures": figures, "items": len(targets), "errors": errors,
         "capped": capped}, ensure_ascii=False, indent=2), encoding="utf-8")
    html_path = out / f"{slug}-figures.html"
    html_path.write_text(_gallery_html(content, figures), encoding="utf-8")

    return {"variant": "figure", "html": str(html_path), "json": str(json_path),
            "figures": figures, "items": len(targets), "errors": errors,
            "verdicts": verdicts, "capped": capped}
