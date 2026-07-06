"""Regression: adapter reads must see LIVE writes (combinedDBQues is a WAL corpus
mutated in place by their validation pipeline). immutable=1 makes sqlite ignore
the WAL and serve stale/torn reads — the adapter must open plain mode=ro."""
import sqlite3

from samagra.adapters import qx as qx_adapter


def test_ro_connection_sees_rows_committed_after_open(tmp_path):
    db = tmp_path / "live.sqlite"
    rw = sqlite3.connect(db)
    rw.execute("PRAGMA journal_mode=WAL")
    rw.execute("CREATE TABLE t (x)")
    rw.execute("INSERT INTO t VALUES (1)")
    rw.commit()

    ro = qx_adapter._ro(db)
    assert ro.execute("SELECT count(*) FROM t").fetchone()[0] == 1

    rw.execute("INSERT INTO t VALUES (2)")     # live write AFTER the ro open
    rw.commit()
    assert ro.execute("SELECT count(*) FROM t").fetchone()[0] == 2   # visible
    ro.close(); rw.close()


def test_ro_connection_refuses_writes(tmp_path):
    db = tmp_path / "live.sqlite"
    sqlite3.connect(db).execute("CREATE TABLE t (x)").connection.commit()
    ro = qx_adapter._ro(db)
    try:
        import pytest
        with pytest.raises(sqlite3.OperationalError):
            ro.execute("INSERT INTO t VALUES (9)")
    finally:
        ro.close()
