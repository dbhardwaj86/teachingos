"""claude-GN-OCR adapter — the GN Brain handwritten-notes corpus. READ-ONLY,
never writes. Reads `_brain/catalog.db` via sqlite `mode=ro` (plain ro, NO
`immutable=1` — the brain is a live WAL corpus; the Slice-R lesson)."""
from __future__ import annotations

import sqlite3
from typing import Iterator

from .. import config
from .base import Adapter, Artifact


def _ro(path) -> sqlite3.Connection:
    # mode=ro WITHOUT immutable=1: live WAL corpus — immutable would skip the
    # WAL and serve stale/torn reads; plain ro still refuses writes.
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


class GnocrAdapter(Adapter):
    name = "gnocr"
    label = "GN Brain (Handwritten)"

    def available(self) -> bool:
        return config.GNOCR_BRAIN_DB.exists()

    def summary(self) -> dict:
        if not self.available():
            return {}
        try:
            con = _ro(config.GNOCR_BRAIN_DB)
            try:
                docs = con.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
                topics = con.execute("SELECT COUNT(*) FROM topics").fetchone()[0]
                chunks = con.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
            finally:
                con.close()
            return {"documents": docs, "topics": topics, "chunks": chunks}
        except sqlite3.Error:  # missing/locked/foreign schema — never raise
            return {}

    def artifacts(self) -> Iterator[Artifact]:
        if not self.available():
            return
        try:
            con = _ro(config.GNOCR_BRAIN_DB)
            try:
                rows = con.execute(
                    "SELECT d.id, d.title, d.page_count, "
                    "(SELECT t.name FROM doc_topics dt JOIN topics t ON t.id = dt.topic_id "
                    " WHERE dt.doc_id = d.id ORDER BY t.id LIMIT 1) AS topic "
                    "FROM documents d ORDER BY d.id").fetchall()
            finally:
                con.close()
        except sqlite3.Error:
            return
        for doc_id, title, page_count, topic in rows:
            yield Artifact(
                uid=f"gnocr:{doc_id}", source=self.name, kind="chapter",
                title=title or f"doc {doc_id}", subject="physics", chapter=topic,
                meta={"page_count": page_count, "topic": topic},
            )
