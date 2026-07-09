"""lecturepdfs adapter — the Lecture Brain (distilled lecture corpus).
READ-ONLY, never writes. Reads `brain/data/corpus.jsonl` + `data/examples.json`
directly from the filesystem — no daemon, no vector store, no key (the no-key
path only; semantic search stays in the daemon's own UI)."""
from __future__ import annotations

import json
import re
from pathlib import PurePosixPath
from typing import Iterator

from .. import config
from .base import Adapter, Artifact

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slug(text: str) -> str:
    return _SLUG_RE.sub("-", (text or "").lower()).strip("-")


def _batch_dir(source_path: str) -> str:
    """The batch directory name for a corpus row's source file: the nearest
    ancestor dir that looks like a batch (contains '(' or 'batch'), else the
    immediate parent dir."""
    parts = PurePosixPath(source_path.replace("\\", "/")).parts
    dirs = list(parts[:-1])
    for name in reversed(dirs):
        low = name.lower()
        if "(" in name or "batch" in low:
            return name
    return dirs[-1] if dirs else ""


def _corpus_jsonl():
    return config.LECTUREPDF_BRAIN / "data" / "corpus.jsonl"


class LecturepdfAdapter(Adapter):
    name = "lecturepdf"
    label = "Lecture Brain"

    def available(self) -> bool:
        return _corpus_jsonl().exists()

    def _rows(self):
        try:
            with _corpus_jsonl().open(encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        yield json.loads(line)
                    except ValueError:
                        continue
        except OSError:
            return

    def _examples_count(self) -> int:
        path = config.LECTUREPDF_BRAIN / "data" / "examples.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return len(data) if hasattr(data, "__len__") else 0
        except (OSError, ValueError):
            return 0

    def _lectures(self) -> tuple[dict, int, set]:
        """Group corpus rows into lectures keyed (batch, topic, lecture_no, date).

        The key MUST match the uid construction in artifacts(), so uids are
        unique by construction (grouping on source_path once produced colliding
        uids that catalog's `insert or replace` on the uid PK silently dropped).
        What is MERGED: same-date rows sharing the triple — multi-part lectures
        (part-1/part-2 source PDFs) plus the rare same-date different-teacher
        residual. What is SPLIT: rows sharing the triple on DIFFERENT dates —
        genuinely distinct lectures (e.g. different course runs) that a
        date-blind key collapsed first-write-wins (~69 live lectures)."""
        lectures: dict[tuple, dict] = {}
        chunks = 0
        topics: set[str] = set()
        for row in self._rows():
            chunks += 1
            topic = row.get("topic") or ""
            if topic:
                topics.add(topic)
            key = (_batch_dir(row.get("source_path") or ""), topic,
                   str(row.get("lecture_no") or ""),
                   str(row.get("date") or ""))
            if key not in lectures:
                lectures[key] = row
        return lectures, chunks, topics

    def summary(self) -> dict:
        if not self.available():
            return {}
        lectures, chunks, topics = self._lectures()
        return {"lectures": len(lectures), "topics": len(topics),
                "examples": self._examples_count(), "chunks": chunks}

    def artifacts(self) -> Iterator[Artifact]:
        if not self.available():
            return
        lectures, _, _ = self._lectures()
        for (batch, topic, lecture_no, date), row in lectures.items():
            source_path = row.get("source_path") or ""
            # uid derives from EXACTLY the group key, so uids are unique by
            # construction (no last-write-wins drop at the catalog uid PK).
            # Dateless rows keep the legacy uid shape (no trailing dash).
            tail = f"-{date}" if date else ""
            yield Artifact(
                uid=f"lecturepdf:{_slug(batch)}/{_slug(topic)}-{lecture_no}{tail}",
                source=self.name, kind="chapter",
                title=row.get("topic_display") or topic or source_path,
                subject="physics", chapter=topic, path=source_path or None,
                updated_at=row.get("date"),
                meta={"batch": batch, "topic": topic,
                      "lecture_no": lecture_no, "date": row.get("date")},
            )
