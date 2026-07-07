"""Product-line registry + classify: which content lanes a seed fans out to.

Phase 1 (deterministic, local-write): a textbook-chapter seed (uid 'textbook:<slug>')
fans to a revision sheet (thin) and a full lecture (thick). Pure; no I/O.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Line:
    key: str
    expected_output: str
    variant: str            # the lectures.export variant this lane renders (unused by non-export engines)
    source_prefixes: tuple  # seed_ref prefixes this lane applies to
    kind: str = "local"     # output class: "local" | "qx" | "mcd" | "llm" (Phase-C lane-kind seam).
                            # Default keeps revision/lecture local; consumed by C2 (qx
                            # answer-leak) / C3 (mcd build). In C1 every lane is "local".
    auto_fan: bool = True   # included in the default classify() fan-out? F-D4: the
                            # llm samadhan lane is registered but opt-in (False) — it
                            # is proposed only via `factory plan … --lane samadhan`.


LINES: dict[str, Line] = {
    "revision": Line("revision", "Revision sheet (thin lecture export)",
                     "thin", ("textbook:",)),
    "lecture": Line("lecture", "Full lecture (thick lecture export)",
                    "thick", ("textbook:",)),
    "deck": Line("deck", "Flashcard deck (equation/callout projection)",
                 "deck", ("textbook:",), "local"),
    "paper": Line("paper", "Question paper (answer-safe)",
                  "paper", ("textbook:",), "qx"),
    "drill": Line("drill", "Adaptive drill set (answer-safe)",
                  "drill", ("textbook:",), "qx"),
    # C3: the folded munshi->mcd bridge. variant=None (no slug render — build()
    # runs the mcd path directly from the proposed payload). The ONLY mcd writer.
    "seed": Line("seed", "mycontentdev editorial seed",
                 None, ("munshi:",), "mcd"),
    "samadhan": Line("samadhan", "Misconception brief (Samadhan, LLM)",
                     None, ("textbook:",), "llm", auto_fan=False),
    "figure": Line("figure", "Generated figures (image-gen, LLM-reviewed)",
                   None, ("textbook:",), "llm", auto_fan=False),
    "slides": Line("slides", "Slide deck (NotebookLM-generated)",
                   None, ("textbook:",), "llm", auto_fan=False),
}

# Deterministic lane order so a seed always fans out the same way.
_ORDER = ["revision", "lecture", "deck", "paper", "drill", "seed", "samadhan",
          "figure", "slides"]


def classify(seed_ref: str) -> list[str]:
    """Return the applicable AUTO-FAN product-line keys for a seed_ref, in stable
    order. Opt-in lanes (auto_fan=False, e.g. the llm samadhan lane) are excluded
    from the default fan-out and targeted explicitly via plan(lane=...)."""
    ref = (seed_ref or "").strip()
    if not ref:
        return []
    return [k for k in _ORDER
            if LINES[k].auto_fan
            and any(ref.startswith(p) for p in LINES[k].source_prefixes)]
