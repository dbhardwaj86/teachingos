"""QX (gpt-extract-ques) adapter — the question engine.

Backed by combinedDBQues's unified DBs: `unified_content.sqlite` holds documents +
questions but its subject/chapter columns are NULL; the real, overlay-aware metadata
lives in `unified_builder.sqlite.search_index` (coalesce ov_* over base columns),
same as before. combinedDBQues is a LIVE WAL corpus — their validation pipeline
writes it in place — so we attach both READ-ONLY (plain `mode=ro`, no `immutable`)
so our reads see live commits while still refusing writes ourselves.
"""
from __future__ import annotations

import sqlite3
from collections import Counter
from typing import Iterator

from .. import config
from .base import Adapter, Artifact


def _ro(path) -> sqlite3.Connection:
    # mode=ro WITHOUT immutable=1: combinedDBQues is a LIVE WAL corpus (their
    # validation pipeline writes in place). immutable=1 would make sqlite skip
    # the WAL and serve stale/torn reads; a plain ro connection attaches the WAL
    # like any reader while still refusing writes (the firewall holds).
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


class QXAdapter(Adapter):
    name = "qx"
    label = "Question Bank (QX)"

    def available(self) -> bool:
        return config.QX_CONTENT_DB.exists()

    # -- helpers ---------------------------------------------------------
    def _subject_by_slug(self) -> dict:
        out: dict[str, str] = {}
        if not config.QX_BUILDER_DB.exists():
            return out
        b = _ro(config.QX_BUILDER_DB)
        try:
            rows = b.execute(
                "select slug, coalesce(ov_subject, subject) from search_index"
            ).fetchall()
        finally:
            b.close()
        agg: dict[str, Counter] = {}
        for slug, subj in rows:
            if subj:
                agg.setdefault(slug, Counter())[subj] += 1
        for slug, c in agg.items():
            out[slug] = c.most_common(1)[0][0]
        return out

    # -- contract --------------------------------------------------------
    def summary(self) -> dict:
        c = _ro(config.QX_CONTENT_DB)
        try:
            docs = c.execute("select count(*) from documents").fetchone()[0]
            qs = c.execute("select count(*) from questions").fetchone()[0]
        finally:
            c.close()
        subjects: dict[str, int] = {}
        if config.QX_BUILDER_DB.exists():
            b = _ro(config.QX_BUILDER_DB)
            try:
                for s, n in b.execute(
                    "select coalesce(ov_subject, subject) s, count(*) "
                    "from search_index group by 1 order by 2 desc"
                ):
                    if s:
                        subjects[s] = n
            finally:
                b.close()
        return {"documents": docs, "questions": qs, "subjects": subjects,
                "online": config.QUESTIONDB_URL}

    def artifacts(self) -> Iterator[Artifact]:
        subj_map = self._subject_by_slug()
        c = _ro(config.QX_CONTENT_DB)
        try:
            qcount = dict(c.execute("select slug, count(*) from questions group by slug"))
            for slug, rel, title, exam, year, status, extracted in c.execute(
                "select slug, rel_path, title, exam, year, status, extracted_at "
                "from documents"
            ):
                yield Artifact(
                    uid=f"qx:doc:{slug}", source=self.name, kind="paper",
                    title=title or slug, subject=subj_map.get(slug),
                    status=status, path=rel, updated_at=extracted,
                    meta={"exam": exam, "year": year,
                          "questions": qcount.get(slug, 0)},
                )
        finally:
            c.close()

    # -- live question search for the portal -----------------------------
    def search_questions(self, q="", subject=None, chapter=None, qtype=None, limit=50):
        if not config.QX_BUILDER_DB.exists():
            return []
        b = _ro(config.QX_BUILDER_DB)
        try:
            sql = ("select q_uid, slug, q_type, coalesce(ov_subject,subject), "
                   "coalesce(ov_chapter,chapter), difficulty, text_projection "
                   "from search_index where 1=1")
            args: list = []
            if q:
                sql += " and text_projection like ?"
                args.append(f"%{q}%")
            if subject:
                sql += " and coalesce(ov_subject,subject)=?"
                args.append(subject)
            if chapter:
                sql += " and coalesce(ov_chapter,chapter)=?"
                args.append(chapter)
            if qtype:
                sql += " and q_type=?"
                args.append(qtype)
            sql += " limit ?"
            args.append(limit)
            cols = ["q_uid", "slug", "q_type", "subject", "chapter", "difficulty", "text"]
            return [dict(zip(cols, r)) for r in b.execute(sql, args)]
        finally:
            b.close()
