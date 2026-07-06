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

import os

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
