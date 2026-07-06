"""The samadhan lane engine (Phase D2 — the first generative lane).

One textbook chapter (seed 'textbook:<slug>') -> a misconception brief in the
owner's StyleSeed voice: condition on the StyleSeed -> generate items -> an
adversarial reviewer anchored ONLY to the chapter ground truth -> an advisory
style-fit score -> write <slug>-samadhan.{json,html} under EXPORT_DIR/<slug>/.

The publish gate is untouched: this writes a LOCAL artifact only; capturing it
is build()'s job (a clean review -> captured; any reviewer error -> changes).
"""
from __future__ import annotations

import html as _html
import json

from .. import config
from ..clients import llm_client
from ..lectures import render
from .style import condition, profile as style_profile, score

_SAMADHAN_CSS = """
.sam{display:flex;flex-direction:column;gap:14px;margin-top:8px}
.sam-item{border:1px solid #e3e3e6;border-radius:10px;padding:14px 16px;background:#fff}
.sam-concept{font-weight:600;color:#1f2328;margin-bottom:6px}
.sam-row{margin:4px 0}.sam-k{color:#8a8f98;font-weight:600;margin-right:6px}
.sam-bad{color:#9a2a2a}.sam-good{color:#1a6f3c}
.sam-verdict{font-size:12px;font-weight:600;margin-top:6px}
.v-ok{color:#1a6f3c}.v-error{color:#9a2a2a}
@media print{.sam-item{break-inside:avoid}}
"""


def _require_styleseed():
    seed = style_profile.load_current()
    if seed is None:
        raise RuntimeError(
            "no committed StyleSeed — run `factory style-extract` and commit v0 "
            "before generating a samadhan brief")
    return seed


def preflight(slug: str) -> None:
    """Anti-wedge pre-check (called by build() BEFORE recording intent): the
    chapter exists, a StyleSeed is committed, and the LLM is configured. Raises
    FileNotFoundError / RuntimeError without writing anything."""
    render.load_chapter(slug)                  # FileNotFoundError if absent
    _require_styleseed()
    if not llm_client.configured():
        try:
            key_var = llm_client.required_key_var()
        except RuntimeError:
            key_var = "the LLM API key"         # unknown provider — configured() already fail-closed
        raise RuntimeError(
            f"{key_var} is not set — refusing an LLM build without a key")


def _prose(item: dict) -> str:
    return " ".join(str(item.get(k, "")) for k in ("misconception", "correction", "why"))


def _html_doc(content: dict, scored: list[dict]) -> str:
    parts = ['<section class="sam">']
    for i, it in enumerate(scored, 1):
        concept = _html.escape(str(it.get("concept", "")))
        misc = _html.escape(str(it.get("misconception", "")))
        corr = _html.escape(str(it.get("correction", "")))
        why = _html.escape(str(it.get("why", "")))
        verdict = it.get("verdict", "ok")
        vcls = "v-error" if verdict == "error" else "v-ok"
        rationale = _html.escape(str(it.get("rationale", "")))
        parts.append(
            f'<article class="sam-item">'
            f'<div class="sam-concept"><span class="sam-k">{i}.</span> {concept}</div>'
            f'<div class="sam-row"><span class="sam-k">Misconception</span>'
            f'<span class="sam-bad">{misc}</span></div>'
            f'<div class="sam-row"><span class="sam-k">Correction</span>'
            f'<span class="sam-good">{corr}</span></div>'
            f'<div class="sam-row"><span class="sam-k">Why</span>{why}</div>'
            f'<div class="sam-verdict {vcls}">reviewer: {_html.escape(verdict)}'
            f'{(" — " + rationale) if rationale else ""}</div>'
            f'</article>')
    parts.append("</section>")
    return render.DOC_TEMPLATE.format(
        title=_html.escape(content.get("title", "Samadhan")),
        subtitle=_html.escape(content.get("subtitle", "")),
        kicker=_html.escape("Misconception brief (Samadhan)"),
        css=render.DOC_CSS + _SAMADHAN_CSS,
        body="\n".join(parts))


def build_samadhan(slug: str, *, client=None) -> dict:
    """Generate, adversarially review, advisory-score, and write the brief. Raises
    FileNotFoundError (no chapter) / RuntimeError (no StyleSeed) BEFORE any write."""
    content = render.load_chapter(slug)             # ground truth (raises if absent)
    seed = _require_styleseed()
    system = condition.to_system_prompt(seed)
    client = client or llm_client.LLMClient()       # constructs real client (key check)

    gen = client.generate_samadhan(content, system=system)
    items = list(gen.get("items", []))
    verdicts = client.review_samadhan(items, content).get("verdicts", [])
    by_idx = {v.get("idx"): v for v in verdicts}

    scored = []
    for i, it in enumerate(items):
        # FAIL-CLOSED (DEC-7 remediation): an item the reviewer did not explicitly
        # clear (missing idx, or a verdict that isn't "ok") counts as an error, so a
        # partial-coverage reviewer can never let an unreviewed item reach `captured`.
        v = by_idx.get(i)
        if v is None:
            v = {"verdict": "error", "rationale": "no reviewer verdict for this item"}
        verdict = "ok" if v.get("verdict") == "ok" else "error"
        scored.append({**it, "verdict": verdict, "rationale": v.get("rationale", "")})
    errors = sum(1 for s in scored if s.get("verdict") == "error")

    prose = "\n".join(_prose(it) for it in items)
    style_score = score.style_fit(prose, seed) if items else {"overall": 0.0, "facets": {}}

    out = config.EXPORT_DIR / slug
    out.mkdir(parents=True, exist_ok=True)
    payload = {"slug": slug, "title": content.get("title", slug),
               "model": getattr(client, "_model", None),
               "style_seed_version": seed.version, "style_score": style_score,
               "items": scored, "errors": errors}
    json_path = out / f"{slug}-samadhan.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    html_path = out / f"{slug}-samadhan.html"
    html_path.write_text(_html_doc(content, scored), encoding="utf-8")

    return {"variant": "samadhan", "html": str(html_path), "json": str(json_path),
            "items": len(items), "errors": errors, "verdicts": verdicts,
            "style_score": style_score, "style_seed_version": seed.version}
