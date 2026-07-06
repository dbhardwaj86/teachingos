"""The paper lane engine: assemble an answer-safe question paper / drill from QX.

Deterministic given QX's response — NO LLM. Reads the combinedDBQues question
engine's (a QX fork, :8790) read-only /api/qsearch, whose per-result HTML is
question-only (passage / stem / options / matrix, with KaTeX data-tex spans +
figure <img>s). QX's search route NEVER renders rj["answer"] — answers live only
in QX's authoring views — so this lane is answer-free by construction; the build
boundary's _assert_no_answer_leak re-asserts that (defense in depth, dispatch.py).

Two variants share one engine: `paper` = the full first page of QX hits; `drill` =
a smaller focused subset (the first _DRILL_SIZE). Writes <slug>-<variant>.json (the
question list) + <slug>-<variant>.html (a printable, KaTeX-enabled paper) under
config.EXPORT_DIR/<slug>/. There is deliberately NO external/network WRITE here —
QX is read-only and the only writes are local files (no new prod write path).

If QX is unreachable, build_paper raises ValueError BEFORE writing any file, so the
guarded build() refuses cleanly with no partial artifact (mirrors the bridge's
munshi-down posture, review 22 M2).
"""
from __future__ import annotations

import html as _html
import json

from .. import config, questions_proxy
from ..clients import QxClient
from . import chapter_map

# A drill is a smaller, focused subset of the chapter's questions (the first N of
# QX's stable exact-search order — deterministic, no LLM).
_DRILL_SIZE = 8

# Card/question layout + QX's standalone-math classes (.mwrap/.ktx/.eq-hidden) so
# the KaTeX spans render and the hidden image fallback stays hidden until needed.
# NOTE: this CSS must never name an `.answer`/`.solution` class — that would self-
# trip the answer-leak guard in dispatch.py.
_PAGE_CSS = """
.paper{max-width:820px}
.qpaper-item{border:1px solid #e3e3e6;border-radius:10px;padding:14px 18px;margin:12px 0;background:#fff}
.qpaper-n{color:#8a8f98;font-weight:700;margin-right:6px}
.qpaper-meta{color:#8a8f98;font-size:12px;margin-bottom:6px}
.stem{margin:2px 0 8px}
.passage{background:#f8fafc;border-left:3px solid #c7ccd4;padding:8px 12px;margin:0 0 8px;border-radius:0 8px 8px 0}
.ptag{display:inline-block;font-weight:700;color:#647084;margin-right:6px}
.options{display:grid;gap:4px;margin-top:6px}
.opt-label{font-weight:600;color:#1f2328;margin-right:4px}
.matrix-table{border-collapse:collapse;margin-top:6px}
.matrix-table td,.matrix-table th{border:1px solid #e3e3e6;padding:4px 8px;text-align:left}
.mwrap{display:inline}
.ktx .katex{font-size:1.05em}
.eq-hidden,.ktx-hidden{display:none}
img.fig{max-width:100%;height:auto}
@media print{.qpaper-item{break-inside:avoid}}
"""

# Self-contained printable. KaTeX (CDN) renders the .ktx[data-tex] spans QX emits
# under math='standalone'; on KaTeX failure/offline each span falls back to QX's
# hidden equation image (un-hidden) — mirrors QX's renderAllMath
# (gpt-extract-ques/gui/qx_browser.py:571). Doubled braces survive str.format.
_PAGE_TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
<style>
body{{font-family:Inter,system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;color:#1f2933;margin:0;padding:32px;background:#fff;line-height:1.5}}
.kicker{{text-transform:uppercase;letter-spacing:.08em;font-size:12px;color:#647084;font-weight:700}}
h1{{font-size:24px;margin:4px 0 2px}}
.sub{{color:#647084;margin:0 0 14px}}
{css}
</style></head>
<body>
<div class="kicker">{kicker}</div>
<h1>{title}</h1>
<p class="sub">{subtitle}</p>
<section class="paper">
{body}
</section>
<script>
window.addEventListener('DOMContentLoaded', function () {{
  var nodes = document.querySelectorAll('.ktx[data-tex]');
  var haveKatex = (typeof katex !== 'undefined');
  nodes.forEach(function (el) {{
    var ok = false;
    if (haveKatex) {{
      try {{
        katex.render(el.getAttribute('data-tex') || '', el,
                     {{throwOnError: true, strict: 'ignore', displayMode: false}});
        ok = true;
      }} catch (e) {{ ok = false; }}
    }}
    if (!ok) {{
      var wrap = el.closest('.mwrap');
      el.classList.add('ktx-hidden');
      if (wrap) {{ var img = wrap.querySelector('img.eq'); if (img) img.classList.remove('eq-hidden'); }}
    }}
  }});
}});
</script>
</body></html>
"""


def _assemble_items_html(results: list[dict]) -> str:
    """Wrap each QX question-only render in a numbered item. The body is QX's HTML
    verbatim (already answer-free) — we add only a number + metadata chrome."""
    parts: list[str] = []
    for i, r in enumerate(results, 1):
        meta = " · ".join(x for x in (r.get("q_type"), r.get("subject"),
                                      r.get("chapter")) if x)
        body = r.get("html") or ""
        parts.append(
            f'<article class="qpaper-item">'
            f'<div class="qpaper-meta"><span class="qpaper-n">Q{i}.</span>{_html.escape(meta)}</div>'
            f'{body}'
            f'</article>'
        )
    return "\n".join(parts)


def _retrieve(slug: str, client) -> tuple[dict, dict]:
    """Chapter-scoped listing when the slug is mapped (empty q + the chapter
    display-name facet — /api/qsearch filters on the display string, verified
    live 2026-07-06); fall back to the legacy de-hyphenated text query when
    unmapped or the chapter listing returns 0 hits. Returns (payload, meta)
    where meta = {"query", "chapter"} is recorded into the artifact JSON."""
    entry = chapter_map.load().get(slug)
    if entry:
        payload = client.search(q="", mode="exact", chapter=entry["chapter"], page=1)
        if payload.get("results"):
            return payload, {"query": "", "chapter": entry["chapter"]}
    query = slug.replace("-", " ").strip()
    return client.search(q=query, mode="exact", page=1), {"query": query, "chapter": None}


def build_paper(slug: str, *, variant: str) -> dict:
    """Build an answer-safe question paper (variant='paper', the full page) or drill
    set (variant='drill', the first _DRILL_SIZE) for a chapter slug, from QX. Writes
    <slug>-<variant>.json + <slug>-<variant>.html under config.EXPORT_DIR/<slug>/ and
    returns the factory result dict {variant, html, json, questions}. Raises
    ValueError (BEFORE writing anything) if QX is unreachable."""
    client = QxClient()
    try:
        payload, meta = _retrieve(slug, client)
    except Exception as exc:   # noqa: BLE001 — engine down / bad URL / timeout / bad JSON
        raise ValueError(
            f"question engine unreachable — cannot build {variant!r} for {slug!r}: {exc}. "
            f"Is combinedDBQues serving on :8790? (see its RUNBOOK; no artifact written)"
        ) from exc

    results = list(payload.get("results") or [])
    if variant == "drill":
        results = results[:_DRILL_SIZE]
    # Rewrite QX's relative /asset URLs (figures + equation-image fallbacks) to
    # absolute QX-server URLs so they load when the printable is opened elsewhere.
    questions_proxy.absolutize_assets({"results": results}, client.base_url)

    out = config.EXPORT_DIR / slug
    out.mkdir(parents=True, exist_ok=True)

    label = "Question paper" if variant == "paper" else "Drill set"
    title = slug.replace("-", " ").title()

    data = {
        "slug": slug, "variant": variant, "query": meta["query"], "chapter": meta["chapter"],
        "questions": [{"q_uid": r.get("q_uid"), "q_type": r.get("q_type"),
                       "html": r.get("html")} for r in results],
    }
    json_path = out / f"{slug}-{variant}.json"
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    html_doc = _PAGE_TEMPLATE.format(
        title=_html.escape(title),
        subtitle=_html.escape(f"{label} · {len(results)} question(s) · questions only"),
        kicker=_html.escape(label),
        css=_PAGE_CSS,
        body=_assemble_items_html(results),
    )
    html_path = out / f"{slug}-{variant}.html"
    html_path.write_text(html_doc, encoding="utf-8")

    return {"variant": variant, "html": str(html_path),
            "json": str(json_path), "questions": len(results)}
