"""PURE student what's-next ranker (G4) — the student-facing sibling of gaps.rank_gaps.

Ranks the published (chapter, lane) inventory a student has NOT yet marked done, by
the chapter's summed concept demand. Deterministic Tier-1 (no LLM, no I/O — this
module never imports sqlite3; the API-layer glue feeds it plain dicts/sets).
"""
from __future__ import annotations

_QUEUE_SIZE = 8

# Saar-led study order — deliberately mirrors LANE_ORDER in
# frontend/src/lib/published/manifest.ts (a TS<->Python duplication; keep in sync).
_LANE_PRIORITY = {lane: i for i, lane in enumerate(
    ["revision", "lecture", "deck", "paper", "drill", "samadhan"])}


def rank_next(published: list[dict], chapter_demand: dict[str, int],
              done_pairs: set[tuple[str, str]], *, top: int = _QUEUE_SIZE) -> list[dict]:
    """published: [{chapter, title, lanes: [str]}] (from the manifest, via the glue).
    chapter_demand: {chapter_slug: summed concept demand} ({} when the graph is unbuilt).
    done_pairs: this student's marked (chapter, lane) set (empty for a new student)."""
    items: list[dict] = []
    for ch in published:
        slug = ch.get("chapter") or ""
        for lane in ch.get("lanes", []):
            if not slug or not lane or (slug, lane) in done_pairs:
                continue
            score = int(chapter_demand.get(slug, 0))
            items.append({
                "chapter": slug, "title": ch.get("title") or slug, "lane": lane,
                "score": score, "reason": "high-demand" if score > 0 else "new",
            })
    items.sort(key=lambda g: (-g["score"], _LANE_PRIORITY.get(g["lane"], 99), g["chapter"]))
    del items[top:]
    for i, g in enumerate(items, 1):
        g["rank"] = i
    return items
