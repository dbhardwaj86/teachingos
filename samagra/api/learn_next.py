# samagra/api/learn_next.py
"""GLUE for GET /api/learn/next (G4) — the ONE module that joins the three read-only
sources. Lives in the API layer on purpose: samagra/pratham/ must never import
samagra/factory/ (the DEC-12/13 isolation firewall), and the pure ranker never does
I/O. concept_graph.db is opened strictly via the existing read-only connect_ro; an
absent/unbuilt graph degrades to an unranked queue (score 0), never an error."""
from __future__ import annotations

import sqlite3

from ..factory.coverage import next_best
from ..factory.coverage import store as coverage_store
from ..factory.publish import read
from ..pratham import service


def _published_inventory() -> list[dict]:
    man = read.published_manifest() or {}
    out: list[dict] = []
    for slug, ch in sorted((man.get("chapters") or {}).items()):
        lanes = sorted({a.get("lane") for a in (ch.get("artifacts") or []) if a.get("lane")})
        if lanes:
            out.append({"chapter": slug, "title": (ch.get("title") or slug), "lanes": lanes})
    return out


def _chapter_demand() -> dict[str, int]:
    # Absent OR corrupt/mid-rebuild graph degrades to an unranked queue (score 0) —
    # the ranker treats {} as "no demand data"; never a 500 on the student surface.
    try:
        conn = coverage_store.connect_ro()
    except FileNotFoundError:
        return {}
    try:
        rows = conn.execute(
            "SELECT cc.chapter_slug AS slug, SUM(c.demand_size) AS demand "
            "FROM concept_chapter cc JOIN concept c ON c.concept_id = cc.concept_id "
            "GROUP BY cc.chapter_slug").fetchall()
        return {r["slug"]: int(r["demand"] or 0) for r in rows}
    except sqlite3.Error:
        return {}
    finally:
        conn.close()


def next_payload(student_id: str) -> dict:
    """{queue: ranked not-done published pairs, done: the student's own rows} —
    `done` rides along so the reader learns button state in one round trip."""
    done = service.progress_for(student_id)
    done_pairs = {(d["chapter"], d["lane"]) for d in done}
    queue = next_best.rank_next(_published_inventory(), _chapter_demand(), done_pairs)
    return {"queue": queue, "done": done}
