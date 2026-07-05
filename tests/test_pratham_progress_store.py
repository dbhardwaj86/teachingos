import sqlite3

from samagra import config
from samagra.pratham import store


def test_list_progress_empty():
    assert store.list_progress("stu_nobody") == []


def test_mark_and_list_roundtrip():
    store.mark_progress("stu_a", "circular-motion", "revision", "2026-07-05T10:00:00Z")
    rows = store.list_progress("stu_a")
    assert len(rows) == 1
    r = rows[0]
    assert (r["chapter"], r["lane"], r["status"]) == ("circular-motion", "revision", "done")
    assert r["marked_at"] == "2026-07-05T10:00:00Z"
    assert store.list_progress("stu_b") == []          # never another student's rows


def test_mark_progress_is_idempotent_upsert():
    store.mark_progress("stu_a", "circular-motion", "revision", "2026-07-05T10:00:00Z")
    store.mark_progress("stu_a", "circular-motion", "revision", "2026-07-05T11:00:00Z")
    rows = store.list_progress("stu_a")
    assert len(rows) == 1                              # PK prevents duplicates
    assert rows[0]["marked_at"] == "2026-07-05T11:00:00Z"


_V1_DDL = """
CREATE TABLE IF NOT EXISTS students (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, code_hash TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active', created_at TEXT NOT NULL, last_login_at TEXT);
CREATE TABLE IF NOT EXISTS sessions (
  id_hash TEXT PRIMARY KEY, student_id TEXT NOT NULL,
  created_at TEXT NOT NULL, expires_at TEXT NOT NULL);
"""


def test_existing_v1_db_gains_progress_table_and_keeps_rows():
    # Build a REAL schema-v1 pratham.db (as G3 shipped it), then prove the additive
    # upgrade: ensure_tables() adds `progress` without touching existing rows.
    con = sqlite3.connect(config.PRATHAM_DB)
    con.executescript(_V1_DDL)
    con.execute("INSERT INTO students (id, name, code_hash, status, created_at) "
                "VALUES ('stu_old', 'Asha', 'h', 'active', '2026-06-28T00:00:00Z')")
    con.execute("PRAGMA user_version = 1")
    con.commit(); con.close()
    store._INITIALIZED.clear()

    store.mark_progress("stu_old", "gravitation", "deck", "2026-07-05T10:00:00Z")

    assert store.get_student("stu_old")["name"] == "Asha"     # old rows survive
    assert store.list_progress("stu_old")[0]["chapter"] == "gravitation"
    con = sqlite3.connect(config.PRATHAM_DB)
    assert con.execute("PRAGMA user_version").fetchone()[0] == 2
    con.close()
