"""Adapter tests for mycontentdev + munshi.

The HTTP clients are replaced with hand-rolled fakes that return canned JSON,
so artifacts() is exercised over known data with NO network access. We assert
exact Artifact field values against the SHARED CONTRACTS.
"""
from __future__ import annotations

from samagra.adapters import ALL_ADAPTERS, get_adapter
from samagra.adapters.mcd import McdAdapter
from samagra.adapters.munshi import MunshiAdapter


class FakeMcdClient:
    def __init__(self, api_url="https://mcd.example.dev", rows=None, avail=True):
        self.api_url = api_url
        self._rows = rows or []
        self._avail = avail
        self.last_sql = None

    def available(self):
        return self._avail

    def query(self, sql):
        self.last_sql = sql
        return self._rows


class FakeMunshiClient:
    def __init__(self, library=None, avail=True):
        self._library = library or {"people": [], "total": 0, "items": []}
        self._avail = avail

    def available(self):
        return self._avail

    def library(self):
        return self._library


# ---------------- McdAdapter ----------------

def test_mcd_adapter_identity():
    ad = McdAdapter()
    assert ad.name == "mycontentdev"
    assert ad.label == "Editorial (mycontentdev)"


def test_mcd_adapter_available_delegates_to_client():
    assert McdAdapter(client=FakeMcdClient(avail=True)).available() is True
    assert McdAdapter(client=FakeMcdClient(avail=False)).available() is False


def test_mcd_adapter_query_excludes_archived():
    fake = FakeMcdClient(rows=[])
    list(McdAdapter(client=fake).artifacts())
    assert fake.last_sql == (
        "SELECT id,type,title,status,created_at,updated_at "
        "FROM seeds WHERE status != 'archived'"
    )


def test_mcd_adapter_maps_row_to_artifact():
    rows = [{
        "id": "abc123",
        "type": "concept",
        "title": "Gauss's law flux",
        "status": "draft_ready",
        "created_at": "2026-06-10T00:00:00Z",
        "updated_at": "2026-06-15T09:00:00Z",
    }]
    ad = McdAdapter(client=FakeMcdClient(api_url="https://mcd.example.dev", rows=rows))
    arts = list(ad.artifacts())
    assert len(arts) == 1
    a = arts[0]
    assert a.uid == "mcd:abc123"
    assert a.source == "mycontentdev"
    assert a.kind == "concept"
    assert a.title == "Gauss's law flux"
    assert a.subject == "physics"
    assert a.unit is None
    assert a.chapter is None
    assert a.status == "draft_ready"
    assert a.path is None
    assert a.url == "https://mcd.example.dev/seed/abc123"
    assert a.updated_at == "2026-06-15T09:00:00Z"
    assert a.meta == {"seedId": "abc123"}


# ---------------- MunshiAdapter ----------------

def test_munshi_adapter_identity():
    ad = MunshiAdapter()
    assert ad.name == "munshi"
    assert ad.label == "Front Desk (munshi)"


def test_munshi_adapter_available_delegates_to_client():
    assert MunshiAdapter(client=FakeMunshiClient(avail=True)).available() is True
    assert MunshiAdapter(client=FakeMunshiClient(avail=False)).available() is False


def test_munshi_adapter_skips_dismissed():
    lib = {"people": [], "total": 2, "items": [
        {"id": 1, "kind": "note", "status": "dismissed",
         "ts": "2026-06-01T00:00:00Z", "payload": {"issue": "ignore me"}},
        {"id": 2, "kind": "note", "status": "open",
         "ts": "2026-06-02T00:00:00Z", "payload": {"issue": "keep me"}},
    ]}
    arts = list(MunshiAdapter(client=FakeMunshiClient(library=lib)).artifacts())
    assert [a.uid for a in arts] == ["munshi:2"]


def test_munshi_adapter_maps_item_to_artifact():
    # Uses the REAL live munshi 'todo' payload schema (myProd/src/tools.ts:150 ->
    # insertItem(sql, "todo", {task})); the title comes from payload.task.
    lib = {"people": [], "total": 1, "items": [{
        "id": 7,
        "kind": "todo",
        "status": "open",
        "ts": "2026-06-12T11:00:00Z",
        "payload": {"task": "Draft a Gauss's law worksheet"},
        "tags": ["physics", "worksheet"],
        "person": "Khanak",
        "due": "2026-06-20",
    }]}
    arts = list(MunshiAdapter(client=FakeMunshiClient(library=lib)).artifacts())
    assert len(arts) == 1
    a = arts[0]
    assert a.uid == "munshi:7"
    assert a.source == "munshi"
    assert a.kind == "todo"
    assert a.title == "Draft a Gauss's law worksheet"
    assert a.subject == "physics"
    assert a.unit is None
    assert a.chapter is None
    assert a.status == "open"
    assert a.path is None
    assert a.url is None
    assert a.updated_at == "2026-06-12T11:00:00Z"
    assert a.meta == {
        "payload": {"task": "Draft a Gauss's law worksheet"},
        "tags": ["physics", "worksheet"],
        "person": "Khanak",
        "due": "2026-06-20",
    }


def test_munshi_adapter_title_per_kind():
    # Each live munshi kind stores its title under a kind-specific payload key
    # (myProd/src/tools.ts). Lock the per-kind mapping so a future schema drift
    # is caught instead of silently collapsing titles to the bare kind (MUN-01).
    t = "2026-06-12T11:00:00Z"
    lib = {"people": [], "total": 5, "items": [
        {"id": 1, "kind": "note", "status": "open", "ts": t,
         "payload": {"topic": "rotation", "issue": "why does torque vanish?",
                     "action": "revise"}},
        {"id": 2, "kind": "todo", "status": "open", "ts": t,
         "payload": {"task": "Make a worksheet"}},
        {"id": 3, "kind": "issue", "status": "open", "ts": t,
         "payload": {"summary": "Projector broken", "source": "lab"}},
        {"id": 4, "kind": "question", "status": "open", "ts": t,
         "payload": {"stem": "A block slides down...", "options": ["a", "b"]}},
        {"id": 5, "kind": "followup", "status": "open", "ts": t,
         "payload": {"note": "Khanak: call parent"}},
    ]}
    arts = list(MunshiAdapter(client=FakeMunshiClient(library=lib)).artifacts())
    titles = {a.kind: a.title for a in arts}
    assert titles["note"] == "why does torque vanish?"   # issue, not topic
    assert titles["todo"] == "Make a worksheet"
    assert titles["issue"] == "Projector broken"
    assert titles["question"] == "A block slides down..."
    assert titles["followup"] == "Khanak: call parent"


def test_munshi_adapter_title_fallbacks():
    # note with an empty issue falls back to topic; an unknown kind falls back
    # across the generic keys (body); a raw string payload is used verbatim;
    # an empty dict payload falls back to the kind.
    t = "2026-06-12T11:00:00Z"
    lib = {"people": [], "total": 4, "items": [
        {"id": 1, "kind": "note", "status": "open", "ts": t,
         "payload": {"topic": "optics", "issue": ""}},
        {"id": 2, "kind": "mystery", "status": "open", "ts": t,
         "payload": {"body": "from body"}},
        {"id": 3, "kind": "note", "status": "open", "ts": t,
         "payload": "raw string note"},
        {"id": 4, "kind": "issue", "status": "open", "ts": t, "payload": {}},
    ]}
    arts = list(MunshiAdapter(client=FakeMunshiClient(library=lib)).artifacts())
    by_uid = {a.uid: a.title for a in arts}
    assert by_uid["munshi:1"] == "optics"            # empty issue -> topic
    assert by_uid["munshi:2"] == "from body"         # unknown kind -> body
    assert by_uid["munshi:3"] == "raw string note"   # string payload verbatim
    assert by_uid["munshi:4"] == "issue"             # empty dict -> kind


def test_munshi_adapter_title_falls_back_to_kind():
    lib = {"people": [], "total": 1, "items": [{
        "id": 8, "kind": "issue", "status": "open",
        "ts": "2026-06-12T11:00:00Z", "payload": {},
    }]}
    a = list(MunshiAdapter(client=FakeMunshiClient(library=lib)).artifacts())[0]
    assert a.title == "issue"
    assert a.meta["tags"] is None and a.meta["person"] is None and a.meta["due"] is None


# ---------------- registration ----------------

def test_subsystem_adapters_registered():
    names = {a.name for a in ALL_ADAPTERS}
    assert {"mycontentdev", "munshi"} <= names
    assert isinstance(get_adapter("mycontentdev"), McdAdapter)
    assert isinstance(get_adapter("munshi"), MunshiAdapter)


# ---------------- Corpus adapters (T2.2-T2.5: gnocr / onedpull / lecturepdf) ----------------
import json as _json
import sqlite3 as _sqlite3

import pytest as _pytest

from samagra import config as _config
from samagra.adapters.gnocr import GnocrAdapter
from samagra.adapters.lecturepdf import LecturepdfAdapter
from samagra.adapters.onedpull import OnedpullAdapter


@_pytest.fixture
def gnocr_db(tmp_path, monkeypatch):
    db = tmp_path / "_brain" / "catalog.db"
    db.parent.mkdir(parents=True)
    c = _sqlite3.connect(db)
    c.executescript(
        """
        CREATE TABLE documents (id INTEGER PRIMARY KEY, file_id INTEGER, title TEXT,
                                page_count INTEGER);
        CREATE TABLE topics (id INTEGER PRIMARY KEY, parent_id INTEGER, name TEXT,
                             ncert_ref TEXT);
        CREATE TABLE doc_topics (doc_id INTEGER, topic_id INTEGER);
        CREATE TABLE chunks (id INTEGER PRIMARY KEY, doc_id INTEGER, text_md TEXT);
        INSERT INTO documents VALUES (1, 1, 'Rotation Notes', 12), (2, 2, 'Optics Sheet', 5);
        INSERT INTO topics VALUES (7, NULL, 'Rotational Motion', 'ch7');
        INSERT INTO doc_topics VALUES (1, 7);
        INSERT INTO chunks VALUES (1, 1, 'torque'), (2, 1, 'inertia'), (3, 2, 'lens');
        """)
    c.commit()
    c.close()
    monkeypatch.setattr(_config, "GNOCR_ROOT", tmp_path)
    monkeypatch.setattr(_config, "GNOCR_BRAIN_DB", db)
    return db


def test_gnocr_adapter_identity():
    ad = GnocrAdapter()
    assert ad.name == "gnocr"
    assert ad.label == "GN Brain (Handwritten)"


def test_gnocr_available_true_when_db_exists(gnocr_db):
    assert GnocrAdapter().available() is True


def test_gnocr_available_false_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(_config, "GNOCR_BRAIN_DB", tmp_path / "nope" / "catalog.db")
    assert GnocrAdapter().available() is False


def test_gnocr_summary_counts(gnocr_db):
    assert GnocrAdapter().summary() == {"documents": 2, "topics": 1, "chunks": 3}


def test_gnocr_artifacts_field_by_field(gnocr_db):
    arts = sorted(GnocrAdapter().artifacts(), key=lambda a: a.uid)
    assert len(arts) == 2
    a = arts[0]
    assert a.uid == "gnocr:1"
    assert a.source == "gnocr"
    assert a.kind == "chapter"
    assert a.title == "Rotation Notes"
    assert a.subject == "physics"
    assert a.meta == {"page_count": 12, "topic": "Rotational Motion"}
    b = arts[1]
    assert b.uid == "gnocr:2"
    assert b.meta == {"page_count": 5, "topic": None}
    # coarse altitude only: no answer/solution fields anywhere
    dump = _json.dumps([x.row() for x in arts])
    assert "answer" not in dump and "solution" not in dump


def test_gnocr_registered():
    assert "gnocr" in {a.name for a in ALL_ADAPTERS}
    assert isinstance(get_adapter("gnocr"), GnocrAdapter)


def test_gnocr_reads_readonly(gnocr_db, monkeypatch):
    from samagra.adapters import gnocr as mod
    seen = []
    real = mod.sqlite3.connect

    def spy(database, *a, **kw):
        seen.append((database, kw))
        return real(database, *a, **kw)

    monkeypatch.setattr(mod.sqlite3, "connect", spy)
    GnocrAdapter().summary()
    assert seen, "expected a sqlite connect"
    uri, kw = seen[0]
    assert "mode=ro" in uri and kw.get("uri") is True
    assert "immutable" not in uri  # WAL corpus - the Slice-R lesson


@_pytest.fixture
def onedpull_db(tmp_path, monkeypatch):
    db = tmp_path / "_brain" / "catalog.db"
    db.parent.mkdir(parents=True)
    c = _sqlite3.connect(db)
    c.executescript(
        """
        CREATE TABLE documents (id INTEGER PRIMARY KEY, file_id INTEGER, kind TEXT,
                                title TEXT, exam TEXT, year TEXT, pages INTEGER);
        CREATE TABLE topics (id INTEGER PRIMARY KEY, parent_id INTEGER, name TEXT,
                             ncert_ref TEXT);
        CREATE TABLE questions (id INTEGER PRIMARY KEY, doc_id INTEGER, answer TEXT,
                                solution_md TEXT);
        INSERT INTO documents VALUES
          (10, 1, 'test_paper', 'JEE Mock 3', 'JEE', '2025', 8),
          (11, 2, 'notes', 'Waves Notes', NULL, NULL, 20),
          (12, 3, 'book', 'HCV Vol 1', NULL, '1999', 300);
        INSERT INTO topics VALUES (1, NULL, 'Waves', 'ch15'), (2, NULL, 'Optics', 'ch9');
        INSERT INTO questions VALUES
          (100, 10, 'SECRET_ANS_B', 'SECRET_SOLUTION_MD'),
          (101, 10, 'SECRET_ANS_C', 'SECRET_SOLUTION_MD2');
        """)
    c.commit()
    c.close()
    monkeypatch.setattr(_config, "ONEDPULL_ROOT", tmp_path)
    monkeypatch.setattr(_config, "ONEDPULL_BRAIN_DB", db)
    return db


def test_onedpull_adapter_identity():
    ad = OnedpullAdapter()
    assert ad.name == "onedpull"
    assert ad.label == "Corpus Brain (onedpulls)"


def test_onedpull_available_true_when_db_exists(onedpull_db):
    assert OnedpullAdapter().available() is True


def test_onedpull_available_false_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(_config, "ONEDPULL_BRAIN_DB", tmp_path / "nope.db")
    assert OnedpullAdapter().available() is False


def test_onedpull_summary_counts(onedpull_db):
    # counts ONLY - no question stems/answers ever enter the catalog
    assert OnedpullAdapter().summary() == {"documents": 3, "questions": 2, "topics": 2}


def test_onedpull_artifacts_field_by_field(onedpull_db):
    arts = sorted(OnedpullAdapter().artifacts(), key=lambda a: a.uid)
    assert len(arts) == 3
    a = arts[0]
    assert a.uid == "onedpull:doc:10"
    assert a.source == "onedpull"
    assert a.kind == "paper"           # test_paper -> paper
    assert a.title == "JEE Mock 3"
    assert a.subject == "physics"
    assert a.meta == {"kind": "test_paper", "exam": "JEE", "year": "2025", "pages": 8}
    assert arts[1].kind == "chapter"   # notes -> chapter
    assert arts[2].kind == "booklet"   # book -> booklet
    # catalog-boundary answer-leak firewall: no answer/solution content anywhere
    dump = _json.dumps([x.row() for x in arts])
    assert "SECRET_ANS" not in dump and "SECRET_SOLUTION" not in dump
    assert "solution_md" not in dump


def test_onedpull_registered():
    assert "onedpull" in {a.name for a in ALL_ADAPTERS}
    assert isinstance(get_adapter("onedpull"), OnedpullAdapter)


@_pytest.fixture
def lecturepdf_brain(tmp_path, monkeypatch):
    data = tmp_path / "brain" / "data"
    data.mkdir(parents=True)
    src1 = "C:/X/Batch A (2026-27)/Physics/Electro/Electro, lec-01 (18-06-26)._Extracted.docx"
    src2 = "C:/X/Batch A (2026-27)/Physics/Electro/Electro, lec-02 (19-06-26)._Extracted.docx"
    rows = [
        {"id": "e__l1__s0", "topic": "electrostatics", "lecture_no": "1",
         "date": "2026-06-18", "type": "concept", "source_path": src1, "text": "t1"},
        {"id": "e__l1__s1", "topic": "electrostatics", "lecture_no": "1",
         "date": "2026-06-18", "type": "example", "source_path": src1, "text": "t2"},
        {"id": "e__l2__s0", "topic": "electrostatics", "lecture_no": "2",
         "date": "2026-06-19", "type": "concept", "source_path": src2, "text": "t3"},
    ]
    with (data / "corpus.jsonl").open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(_json.dumps(r) + "\n")
    (data / "examples.json").write_text(_json.dumps([{"id": 1}, {"id": 2}]), encoding="utf-8")
    monkeypatch.setattr(_config, "LECTUREPDF_ROOT", tmp_path)
    monkeypatch.setattr(_config, "LECTUREPDF_BRAIN", tmp_path / "brain")
    return tmp_path / "brain"


def test_lecturepdf_adapter_identity():
    ad = LecturepdfAdapter()
    assert ad.name == "lecturepdf"
    assert ad.label == "Lecture Brain"


def test_lecturepdf_available_true_when_corpus_jsonl_exists(lecturepdf_brain):
    assert LecturepdfAdapter().available() is True


def test_lecturepdf_available_false_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(_config, "LECTUREPDF_BRAIN", tmp_path / "nope")
    assert LecturepdfAdapter().available() is False


def test_lecturepdf_summary_counts(lecturepdf_brain):
    assert LecturepdfAdapter().summary() == {
        "lectures": 2, "topics": 1, "examples": 2, "chunks": 3}


def test_lecturepdf_artifacts(lecturepdf_brain):
    arts = sorted(LecturepdfAdapter().artifacts(), key=lambda a: a.uid)
    assert len(arts) == 2
    a = arts[0]
    assert a.uid == "lecturepdf:batch-a-2026-27/electrostatics-1-2026-06-18"
    assert a.source == "lecturepdf"
    assert a.kind == "chapter"
    assert a.subject == "physics"
    assert a.meta == {"batch": "Batch A (2026-27)", "topic": "electrostatics",
                      "lecture_no": "1", "date": "2026-06-18"}
    assert arts[1].uid == "lecturepdf:batch-a-2026-27/electrostatics-2-2026-06-19"


def test_lecturepdf_part_files_same_lecture_merge_to_one_uid(tmp_path, monkeypatch):
    """Two source PDFs for the SAME (batch, topic, lecture_no) — a lecture split
    into part 1 / part 2 — must NOT collapse into colliding uids (the review-MED:
    91 live lectures silently last-write-wins dropped by catalog's uid PK)."""
    data = tmp_path / "brain" / "data"
    data.mkdir(parents=True)
    p1 = "C:/X/Batch A (2026-27)/Physics/Cap/Capacitance, Lec - 05 Part 1._Extracted.docx"
    p2 = "C:/X/Batch A (2026-27)/Physics/Cap/Capacitance lec-05 part-2._Extracted.docx"
    rows = [
        {"id": "c__l5__s0", "topic": "capacitance", "lecture_no": "5",
         "date": "2026-06-18", "type": "concept", "source_path": p1, "text": "t1"},
        {"id": "c__l5b__s0", "topic": "capacitance", "lecture_no": "5",
         "date": "2026-06-18", "type": "concept", "source_path": p2, "text": "t2"},
    ]
    with (data / "corpus.jsonl").open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(_json.dumps(r) + "\n")
    monkeypatch.setattr(_config, "LECTUREPDF_BRAIN", tmp_path / "brain")
    arts = list(LecturepdfAdapter().artifacts())
    uids = [a.uid for a in arts]
    assert len(uids) == len(set(uids)), f"colliding uids: {uids}"
    # the two part-files are ONE lecture — merged into a single artifact
    assert uids == ["lecturepdf:batch-a-2026-27/capacitance-5-2026-06-18"]
    assert LecturepdfAdapter().summary()["lectures"] == 1


def test_lecturepdf_same_triple_different_dates_are_distinct_lectures(tmp_path, monkeypatch):
    """Two rows with the SAME (batch, topic, lecture_no) but DIFFERENT dates are
    genuinely distinct lectures (different course runs) — must yield 2 artifacts
    with distinct uids, not first-write-wins collapse (review F-1)."""
    data = tmp_path / "brain" / "data"
    data.mkdir(parents=True)
    p1 = "C:/X/Batch A (2026-27)/Physics/Grav/Gravitation lec-03 (10-05-26)._Extracted.docx"
    p2 = "C:/X/Batch A (2026-27)/Physics/Grav/Gravitation lec-03 (12-06-26)._Extracted.docx"
    rows = [
        {"id": "g__l3a__s0", "topic": "gravitation", "lecture_no": "3",
         "date": "2026-05-10", "type": "concept", "source_path": p1, "text": "t1"},
        {"id": "g__l3b__s0", "topic": "gravitation", "lecture_no": "3",
         "date": "2026-06-12", "type": "concept", "source_path": p2, "text": "t2"},
    ]
    with (data / "corpus.jsonl").open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(_json.dumps(r) + "\n")
    monkeypatch.setattr(_config, "LECTUREPDF_BRAIN", tmp_path / "brain")
    arts = sorted(LecturepdfAdapter().artifacts(), key=lambda a: a.uid)
    uids = [a.uid for a in arts]
    assert len(uids) == 2 and len(set(uids)) == 2, f"collapsed: {uids}"
    assert uids == [
        "lecturepdf:batch-a-2026-27/gravitation-3-2026-05-10",
        "lecturepdf:batch-a-2026-27/gravitation-3-2026-06-12",
    ]
    assert LecturepdfAdapter().summary()["lectures"] == 2


def test_lecturepdf_empty_date_keeps_legacy_uid_shape(lecturepdf_brain):
    """Rows with no date keep the historical uid shape (no trailing dash)."""
    data = lecturepdf_brain / "data"
    rows = [
        {"id": "m__l7__s0", "topic": "magnetism", "lecture_no": "7",
         "source_path": "C:/X/Batch A (2026-27)/Physics/Mag/Mag lec-07._Extracted.docx",
         "text": "t"},
    ]
    with (data / "corpus.jsonl").open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(_json.dumps(r) + "\n")
    uids = [a.uid for a in LecturepdfAdapter().artifacts()]
    assert uids == ["lecturepdf:batch-a-2026-27/magnetism-7"]


def test_lecturepdf_live_corpus_uids_unique():
    """Against the REAL brain (skipped if absent): every artifact uid is unique,
    so catalog's `insert or replace` on the uid PK cannot silently drop rows."""
    ad = LecturepdfAdapter()
    if not ad.available():
        _pytest.skip("real lecturepdf brain not present")
    uids = [a.uid for a in ad.artifacts()]
    assert len(uids) == len(set(uids))


def test_lecturepdf_reads_no_lancedb_no_key():
    import inspect

    from samagra.adapters import lecturepdf as mod
    src = inspect.getsource(mod)
    assert "lancedb" not in src.lower()
    assert "OPENAI" not in src and "API_KEY" not in src


def test_lecturepdf_registered():
    assert "lecturepdf" in {a.name for a in ALL_ADAPTERS}
    assert isinstance(get_adapter("lecturepdf"), LecturepdfAdapter)


def test_all_three_corpora_registered():
    names = {a.name for a in ALL_ADAPTERS}
    assert {"gnocr", "onedpull", "lecturepdf"} <= names
    assert isinstance(get_adapter("gnocr"), GnocrAdapter)
    assert isinstance(get_adapter("onedpull"), OnedpullAdapter)
    assert isinstance(get_adapter("lecturepdf"), LecturepdfAdapter)
