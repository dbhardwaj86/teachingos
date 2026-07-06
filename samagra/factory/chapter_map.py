"""Load the git-committed textbook-slug -> combinedDBQues chapter mapping.

chapter_map.json (repo root, config.CHAPTER_MAP) is the owner-curated crosswalk
from the 59 textbook chapter slugs to the 30 canonical NCERT chapters — the same
review pattern as concept_aliases.json. Each row carries chapter_id (dotted, for
validation/coverage) + chapter (the display name /api/qsearch filters on).
PURE: no HTTP, no sqlite. Missing/invalid file -> {} (callers fall back to the
free-text query path, so a curation gap degrades quality, never safety)."""
from __future__ import annotations

import json

from .. import config


def load() -> dict[str, dict]:
    """Parse + shape-validate the committed map. Malformed rows are DROPPED
    (never raise on curation errors); a valid row is
    slug -> {"chapter_id": str, "chapter": str}."""
    try:
        raw = json.loads(config.CHAPTER_MAP.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict] = {}
    for slug, entry in raw.items():
        if (isinstance(slug, str) and isinstance(entry, dict)
                and isinstance(entry.get("chapter_id"), str)
                and isinstance(entry.get("chapter"), str)):
            out[slug] = {"chapter_id": entry["chapter_id"],
                         "chapter": entry["chapter"]}
    return out
