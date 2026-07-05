# samagra/pratham/store.py
"""I/O over the durable, SEPARATE config.PRATHAM_DB (students + sessions).

Independent of governance.store: its own connection + self-initializing schema.
All bearer secrets (enrollment codes, session tokens) are stored ONLY as sha256
(the caller hashes via identity.hash_secret) — plaintext never persists here.
"""
from __future__ import annotations

import sqlite3

from .. import config

SCHEMA_VERSION = 2

DDL = """
CREATE TABLE IF NOT EXISTS students (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  code_hash TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  created_at TEXT NOT NULL,
  last_login_at TEXT
);
CREATE TABLE IF NOT EXISTS sessions (
  id_hash TEXT PRIMARY KEY,
  student_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_students_code_hash ON students(code_hash);
CREATE INDEX IF NOT EXISTS idx_sessions_student ON sessions(student_id);
CREATE TABLE IF NOT EXISTS progress (
  student_id TEXT NOT NULL,
  chapter    TEXT NOT NULL,
  lane       TEXT NOT NULL,
  status     TEXT NOT NULL DEFAULT 'done',
  marked_at  TEXT NOT NULL,
  PRIMARY KEY (student_id, chapter, lane)
);
CREATE INDEX IF NOT EXISTS idx_progress_student ON progress(student_id);
"""

# Memoize schema init once per DB path (re-inits if the file was deleted), mirroring
# governance.store. Tests clear this when they repoint config.PRATHAM_DB.
_INITIALIZED: set[str] = set()


def connect() -> sqlite3.Connection:
    config.PRATHAM_DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(config.PRATHAM_DB)
    con.row_factory = sqlite3.Row
    return con


def init_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(DDL)
    conn.execute(f"PRAGMA user_version = {int(SCHEMA_VERSION)}")
    conn.commit()


def ensure_tables() -> None:
    key = str(config.PRATHAM_DB)
    if key in _INITIALIZED and config.PRATHAM_DB.exists():
        return
    conn = connect()
    try:
        init_tables(conn)
    finally:
        conn.close()
    _INITIALIZED.add(key)


def _exec(sql: str, params: tuple = ()) -> None:
    ensure_tables()
    conn = connect()
    try:
        conn.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


def _query_one(sql: str, params: tuple = ()) -> dict | None:
    ensure_tables()
    conn = connect()
    try:
        row = conn.execute(sql, params).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def _query_all(sql: str, params: tuple = ()) -> list[dict]:
    ensure_tables()
    conn = connect()
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


# --- students ----------------------------------------------------------
def create_student(student_id: str, name: str, code_hash: str, created_at: str) -> None:
    _exec("INSERT INTO students (id, name, code_hash, status, created_at) "
          "VALUES (?, ?, ?, 'active', ?)", (student_id, name, code_hash, created_at))


def find_student_by_code_hash(code_hash: str) -> dict | None:
    return _query_one("SELECT * FROM students WHERE code_hash = ?", (code_hash,))


def get_student(student_id: str) -> dict | None:
    return _query_one("SELECT * FROM students WHERE id = ?", (student_id,))


def set_status(student_id: str, status: str) -> None:
    _exec("UPDATE students SET status = ? WHERE id = ?", (status, student_id))


def touch_login(student_id: str, at: str) -> None:
    _exec("UPDATE students SET last_login_at = ? WHERE id = ?", (at, student_id))


def list_students() -> list[dict]:
    return _query_all("SELECT * FROM students ORDER BY created_at, id")


# --- sessions ----------------------------------------------------------
def create_session(id_hash: str, student_id: str, created_at: str, expires_at: str) -> None:
    _exec("INSERT OR REPLACE INTO sessions (id_hash, student_id, created_at, expires_at) "
          "VALUES (?, ?, ?, ?)", (id_hash, student_id, created_at, expires_at))


def find_session(id_hash: str) -> dict | None:
    return _query_one("SELECT * FROM sessions WHERE id_hash = ?", (id_hash,))


def delete_session(id_hash: str) -> None:
    _exec("DELETE FROM sessions WHERE id_hash = ?", (id_hash,))


def delete_sessions_for_student(student_id: str) -> None:
    _exec("DELETE FROM sessions WHERE student_id = ?", (student_id,))


# --- progress (G4) ----------------------------------------------------
def mark_progress(student_id: str, chapter: str, lane: str, marked_at: str) -> None:
    """Idempotent 'done' upsert — the PK makes a re-mark update marked_at, never
    duplicate. v1 only ever writes status='done' (the column is the F-G4-3
    escape hatch: a future 'again' is a value, not a migration)."""
    _exec("INSERT INTO progress (student_id, chapter, lane, status, marked_at) "
          "VALUES (?, ?, ?, 'done', ?) "
          "ON CONFLICT(student_id, chapter, lane) "
          "DO UPDATE SET status = 'done', marked_at = excluded.marked_at",
          (student_id, chapter, lane, marked_at))


def list_progress(student_id: str) -> list[dict]:
    return _query_all("SELECT * FROM progress WHERE student_id = ? ORDER BY chapter, lane",
                      (student_id,))
