"""onedpulls adapter — the Corpus Brain (documents + 13k-question bank).
READ-ONLY, never writes. Reads `_brain/catalog.db` via sqlite `mode=ro` (plain
ro, NO `immutable=1` — live WAL corpus).

Answer-leak firewall at the catalog boundary: summary() emits COUNTS only and
artifacts() NEVER selects the `answer`/`solution_md` columns — no question
stem, answer, or solution content ever enters the SAMAGRA catalog (base.py's
coarse-altitude contract)."""
from __future__ import annotations

import sqlite3
from typing import Iterator

from .. import config
from .base import Adapter, Artifact

_KIND_MAP = {
    "test_paper": "paper",
    "solutions": "paper",
    "question_bank": "paper",
    "notes": "chapter",
    "slides": "chapter",
    "book": "booklet",
}


def _ro(path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


class OnedpullAdapter(Adapter):
    name = "onedpull"
    label = "Corpus Brain (onedpulls)"

    def available(self) -> bool:
        return config.ONEDPULL_BRAIN_DB.exists()

    def summary(self) -> dict:
        if not self.available():
            return {}
        try:
            con = _ro(config.ONEDPULL_BRAIN_DB)
            try:
                docs = con.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
                questions = con.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
                topics = con.execute("SELECT COUNT(*) FROM topics").fetchone()[0]
            finally:
                con.close()
            return {"documents": docs, "questions": questions, "topics": topics}
        except sqlite3.Error:
            return {}

    def artifacts(self) -> Iterator[Artifact]:
        if not self.available():
            return
        try:
            con = _ro(config.ONEDPULL_BRAIN_DB)
            try:
                # NEVER select answer / solution_md — catalog answer-leak firewall.
                rows = con.execute(
                    "SELECT id, kind, title, exam, year, pages "
                    "FROM documents ORDER BY id").fetchall()
            finally:
                con.close()
        except sqlite3.Error:
            return
        for doc_id, kind, title, exam, year, pages in rows:
            yield Artifact(
                uid=f"onedpull:doc:{doc_id}", source=self.name,
                kind=_KIND_MAP.get(kind, "paper"),
                title=title or f"doc {doc_id}", subject="physics",
                meta={"kind": kind, "exam": exam, "year": year, "pages": pages},
            )
