"""Shared pytest fixtures for the SAMAGRA test suite.

S-01 (F-14): test isolation. ``catalog.connect()`` reads ``config.DATA_DB`` and
``governance.store.connect()`` reads ``config.GOVERNANCE_DB`` at call time, so
redirecting BOTH to per-test temp paths before any test runs guarantees the
suite never reads or overwrites the real ``samagra.db`` (rebuildable catalog) or
``governance.db`` (durable governance store — runbook D6).
"""
from __future__ import annotations

import pytest

from samagra import config


@pytest.fixture(autouse=True)
def isolate_data_db(monkeypatch, tmp_path):
    """Repoint the catalog AND governance DBs at per-test temp files.

    Function-scoped + autouse, so every test in the suite is isolated from both
    real DBs without having to opt in. ``monkeypatch`` restores the originals
    automatically at teardown.
    """
    monkeypatch.setattr(config, "DATA_DB", tmp_path / "samagra.db")
    monkeypatch.setattr(config, "GOVERNANCE_DB", tmp_path / "governance.db")
    # W1.1: the suite runs as 'local dev' — disable the origin fail-closed gate by
    # default so existing API tests reach their handlers. tests/test_origin_auth.py
    # flips this back OFF to exercise the real gate.
    monkeypatch.setattr(config, "DISABLE_ORIGIN_AUTH", True, raising=False)
    # G3: isolate the PRATHAM identity store too, so no test ever touches a real
    # pratham.db (mirrors the DATA_DB/GOVERNANCE_DB isolation). The store memoizes
    # schema-init by path; a fresh tmp path per test is already isolated, but clear
    # the memo + repoint to be safe.
    monkeypatch.setattr(config, "PRATHAM_DB", tmp_path / "pratham.db", raising=False)
    try:
        from samagra.pratham import store as _pratham_store
        _pratham_store._INITIALIZED.clear()
    except Exception:  # noqa: BLE001 — package may not exist mid-build
        pass
