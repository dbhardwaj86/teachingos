# SAMAGRA Content Factory — Phase G3 (multi-tenant identity + outward publish write path) Implementation Plan

> **✅ COMPLETE (2026-07-05).** Tasks 1–12 all executed; merged to `main` fast-forward and pushed.
> Review gate: dedicated DEC-7 Codex pre-merge review **28 GO-WITH-CAVEATS → both caveats
> (Publish-GUI `/api/assignments` shape crash; `pratham_session` cookie `path="/"`) remediated TDD →
> effectively GO** (`docs/codex-reviews/28-g3-identity-publish-write-premerge.report.md`); 4-lens
> adversarial final review = 0 HIGH/MED (firewall: nothing; spec-fidelity: PASS; 3 security LOWs
> accepted as documented best-effort/owner-config items). DEC-12 ratified in `HANDOFF.md`.
> Final gate: 608 pytest passed + 1 skip (opt-in live-LLM smoke), 604 vitest (72 files), tsc + build
> green. Per project convention the step checkboxes below are left unchecked — completion is recorded
> here and in the CLAUDE.md / HANDOFF.md / STATUS.html banners.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give SAMAGRA its first inbound write paths — an owner-gated `POST /api/factory/publish|unpublish` (the GUI/network sibling of G1's CLI publish) and a lightweight multi-tenant student identity (owner-minted enrollment codes → opaque, revocable, server-side sessions in a *separate* durable `pratham.db`) — while keeping `/learn` public and every standing invariant intact.

**Architecture:** Two physically isolated write boundaries. (1) Publish is a thin HTTP adapter over the already-reviewed `factory.publish.run.publish/unpublish` (G1) — adds the two endpoints to `origin_auth._PROTECTED_POSTS` so they inherit the existing Cloudflare-Access owner gate; never-automated. (2) Identity is a new `samagra/pratham/` package (`identity.py` pure, `store.py` over a new `pratham.db`, `service.py` orchestration) exposed by *public* `POST /api/learn/login|logout` + `GET /api/learn/me` with an opaque `HttpOnly`/`SameSite=Lax` cookie. `/learn` stays public-by-design (DEC-11); the student-login write touches only `pratham.db`, so it cannot reach `governance.db`, the inward `build()`, or the 7 subsystems. No `governance.db` migration, no catalog change, no assignment-state-machine change.

**Tech Stack:** Python 3.11, FastAPI, SQLite (`sqlite3`, stdlib `secrets`/`hashlib`), pytest + FastAPI `TestClient`; React + TypeScript + Vite, vitest + @testing-library/react.

**Spec:** `docs/superpowers/specs/2026-06-28-samagra-content-factory-phase-g3-identity-and-publish-write-design.md`
**Branch:** `feature/content-factory-phase-g3` (already created; the spec is committed there).
**Baseline gate:** 562 pytest (1 skipped live-LLM smoke; lone red = pre-existing env `test_gdocs`) + 583 vitest, all green.

---

## File Structure

**Backend (new):**
- `samagra/pratham/__init__.py` — package marker.
- `samagra/pratham/identity.py` — PURE: code/session-token mint, sha256 hashing, expiry math, redeem verdict, `RateLimiter`. No I/O.
- `samagra/pratham/store.py` — I/O over `config.PRATHAM_DB`: `students` + `sessions` tables; CRUD; secrets hashed at rest. Self-initializing schema (independent of `governance.db`).
- `samagra/pratham/service.py` — orchestration: `enroll`, `login`, `current_student`, `logout`, `revoke`; the process-wide `_LIMITER`.

**Backend (modified):**
- `samagra/config.py` — add `PRATHAM_DB`, `PRATHAM_COOKIE_SECURE`, `PRATHAM_SESSION_TTL_DAYS`.
- `samagra/api/origin_auth.py` — add `/api/factory/publish` + `/api/factory/unpublish` to `_PROTECTED_POSTS`.
- `samagra/api/app.py` — add the 2 owner publish POSTs + 3 public learn endpoints; import `Request`, `JSONResponse`.
- `samagra/__main__.py` — add `samagra pratham enroll|students|revoke`.
- `tests/conftest.py` — isolate `PRATHAM_DB` + reset the rate limiter per test.
- `.env.example` — document the new G3 vars. (`.gitignore` already ignores `pratham.db` via `*.db`.)

**Frontend (new):**
- `frontend/src/lib/pratham/session.ts` — thin `loginRequest`/`logoutRequest`/`meRequest` fetch wrappers.
- `frontend/src/lib/publishctl/rows.ts` — PURE merge of captured assignments × published manifest → publish rows.
- `frontend/src/apps/Publish/index.tsx` — the minimal operator Publish control.

**Frontend (modified):**
- `frontend/src/types/contracts.ts` — add `Student`; add `"publish"` to `AppId`.
- `frontend/src/apps/Pratham/index.tsx` — additive sign-in/out (anonymous reading unchanged).
- `frontend/src/registry.ts` — register the `publish` app + `ORDER`.
- `frontend/src/registry.test.ts` — update count 18→19, `ORDER`, add a Publish registration test.
- `frontend/src/App.tsx` — add `publish: "Publish"` to `APP_DIR`.
- `frontend/src/components/icons-data.ts` — add the `publish` icon (ICONS is a total `Record<AppId,…>`).

> **Total-record note (frontend):** `AppId` feeds three total records — `APPS` (registry.ts), `APP_DIR` (App.tsx), `ICONS` (icons-data.ts). Adding `"publish"` to `AppId` REQUIRES an entry in all three or the TS build fails. If the build complains about another `Record<AppId,…>`, grep `Record<AppId` and add the missing key.

---

## Task 1: Config + .env.example for the identity store

**Files:**
- Modify: `samagra/config.py` (after the `PUBLISHED_DIR` block, ~line 114)
- Modify: `.env.example`
- Test: `tests/test_pratham_config.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pratham_config.py
from samagra import config


def test_pratham_db_is_a_sibling_durable_store():
    # Durable identity store, SEPARATE from the inward governance ledger.
    assert config.PRATHAM_DB.name == "pratham.db"
    assert config.PRATHAM_DB.parent == config.REPO_ROOT
    assert config.PRATHAM_DB != config.GOVERNANCE_DB


def test_pratham_cookie_secure_defaults_true():
    # Prod is behind the HTTPS tunnel; Secure on by default, dev-overridable.
    assert config.PRATHAM_COOKIE_SECURE is True


def test_pratham_session_ttl_is_a_positive_int():
    assert isinstance(config.PRATHAM_SESSION_TTL_DAYS, int)
    assert config.PRATHAM_SESSION_TTL_DAYS > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pratham_config.py -v`
Expected: FAIL — `AttributeError: module 'samagra.config' has no attribute 'PRATHAM_DB'`.

- [ ] **Step 3: Add the config block**

In `samagra/config.py`, immediately after the `PUBLISHED_DIR = REPO_ROOT / "published"` line:

```python
# Phase G3: PRATHAM multi-tenant student identity. DURABLE (student accounts +
# sessions) and gitignored like GOVERNANCE_DB (covered by the `*.db` rule) — never
# reset. DELIBERATELY SEPARATE from governance.db so the PUBLIC student-login write
# path is physically isolated from the inward governance ledger and the 7 subsystems.
PRATHAM_DB = REPO_ROOT / "pratham.db"
# The session cookie's Secure flag: True by default (prod is served over HTTPS
# behind the cloudflared tunnel). Set SAMAGRA_PRATHAM_COOKIE_SECURE=0 only for
# local plain-http dev (alongside SAMAGRA_DISABLE_ORIGIN_AUTH).
PRATHAM_COOKIE_SECURE = _env_bool("SAMAGRA_PRATHAM_COOKIE_SECURE", True)
# Student session lifetime (fixed expiry; re-login via the enrollment code).
PRATHAM_SESSION_TTL_DAYS = int(os.environ.get("SAMAGRA_PRATHAM_SESSION_TTL_DAYS", "30"))
```

Then append to `.env.example` (after the LLM block):

```bash

# --- PRATHAM student identity (Phase G3) ---
# Session cookie Secure flag: 1 (default) for the HTTPS tunnel; 0 for local http dev.
SAMAGRA_PRATHAM_COOKIE_SECURE=1
SAMAGRA_PRATHAM_SESSION_TTL_DAYS=30
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pratham_config.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add samagra/config.py .env.example tests/test_pratham_config.py
git commit -m "feat(g3): config for the durable, separate PRATHAM identity store"
```

---

## Task 2: `pratham/identity.py` (PURE)

**Files:**
- Create: `samagra/pratham/__init__.py`
- Create: `samagra/pratham/identity.py`
- Test: `tests/test_pratham_identity.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pratham_identity.py
import calendar
import time

from samagra.pratham import identity


def test_new_code_is_high_entropy_and_unique():
    a, b = identity.new_code(), identity.new_code()
    assert a != b
    assert len(a) >= 11  # token_urlsafe(9) -> ~12 chars


def test_new_session_token_is_unique_and_long():
    a, b = identity.new_session_token(), identity.new_session_token()
    assert a != b
    assert len(a) >= 40  # token_urlsafe(32) -> ~43 chars


def test_hash_secret_is_stable_sha256_hex_and_hides_input():
    h = identity.hash_secret("hunter2")
    assert h == identity.hash_secret("hunter2")
    assert len(h) == 64 and "hunter2" not in h


def test_session_expiry_and_is_expired_boundaries():
    now = calendar.timegm(time.strptime("2026-06-28T00:00:00Z", "%Y-%m-%dT%H:%M:%SZ"))
    exp = identity.session_expiry(now, ttl_days=2)
    assert exp == "2026-06-30T00:00:00Z"
    assert identity.is_expired(exp, now) is False
    assert identity.is_expired(exp, now + 2 * 86400) is True       # exactly at expiry -> expired
    assert identity.is_expired("not-a-date", now) is True          # malformed -> treat as expired


def test_redeem_verdict():
    assert identity.redeem_verdict(None) == "invalid"
    assert identity.redeem_verdict({"status": "revoked"}) == "revoked"
    assert identity.redeem_verdict({"status": "active"}) == "ok"


def test_rate_limiter_blocks_after_threshold_then_window_resets():
    rl = identity.RateLimiter(max_attempts=2, window_seconds=60)
    assert rl.allow("ip1", 1000.0) is True
    assert rl.allow("ip1", 1001.0) is True
    assert rl.allow("ip1", 1002.0) is False        # 3rd within window -> blocked
    assert rl.allow("ip2", 1002.0) is True         # other key unaffected
    assert rl.allow("ip1", 1002.0 + 61) is True     # window slid past -> allowed again
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pratham_identity.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'samagra.pratham'`.

- [ ] **Step 3: Write the implementation**

```python
# samagra/pratham/__init__.py
"""PRATHAM — the A6 downstream student entity (Phase G3): multi-tenant identity."""
```

```python
# samagra/pratham/identity.py
"""PURE identity helpers — no DB, no network, no I/O (fully unit-testable).

Owner-minted enrollment codes are high-entropy bearer credentials; sessions are
opaque high-entropy tokens. Both are stored ONLY as sha256 (see store.py); this
module mints them, hashes them, computes session expiry, and decides the redeem
verdict. A small in-process RateLimiter blunts login volume (best-effort — the
real brute-force defense is the code entropy).
"""
from __future__ import annotations

import calendar
import hashlib
import secrets
import time

_CODE_BYTES = 9     # secrets.token_urlsafe(9) -> ~12 chars, ~72 bits of entropy
_TOKEN_BYTES = 32   # session token -> ~43 chars, ~256 bits
_ISO = "%Y-%m-%dT%H:%M:%SZ"


def new_code() -> str:
    return secrets.token_urlsafe(_CODE_BYTES)


def new_session_token() -> str:
    return secrets.token_urlsafe(_TOKEN_BYTES)


def hash_secret(s: str) -> str:
    """sha256 hex of a bearer secret — the at-rest form (a DB leak exposes no code)."""
    return hashlib.sha256((s or "").encode("utf-8")).hexdigest()


def now_iso() -> str:
    return time.strftime(_ISO, time.gmtime())


def session_expiry(now_epoch: float, ttl_days: int) -> str:
    return time.strftime(_ISO, time.gmtime(now_epoch + ttl_days * 86400))


def is_expired(expires_at_iso: str, now_epoch: float) -> bool:
    """True if now >= expiry. A malformed/empty timestamp is treated as expired."""
    try:
        exp = calendar.timegm(time.strptime(expires_at_iso, _ISO))
    except (TypeError, ValueError):
        return True
    return now_epoch >= exp


def redeem_verdict(student_row, now_epoch: float | None = None) -> str:
    """'invalid' (no such student) | 'revoked' | 'ok' for a looked-up student row."""
    if not student_row:
        return "invalid"
    if student_row.get("status") != "active":
        return "revoked"
    return "ok"


class RateLimiter:
    """In-process sliding-window limiter. Best-effort (resets on restart; behind the
    tunnel the key is a caller-supplied Cf-Connecting-IP — usable only to BLUNT
    volume, never to widen trust). Not a security boundary on its own."""

    def __init__(self, max_attempts: int = 20, window_seconds: int = 60) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._hits: dict[str, list[float]] = {}

    def allow(self, key: str, now_epoch: float) -> bool:
        hits = [t for t in self._hits.get(key, []) if now_epoch - t < self.window_seconds]
        if len(hits) >= self.max_attempts:
            self._hits[key] = hits
            return False
        hits.append(now_epoch)
        self._hits[key] = hits
        return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pratham_identity.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add samagra/pratham/__init__.py samagra/pratham/identity.py tests/test_pratham_identity.py
git commit -m "feat(g3): pure identity helpers (code/session mint, hashing, expiry, rate limiter)"
```

---

## Task 3: `pratham/store.py` (I/O) + test isolation

**Files:**
- Create: `samagra/pratham/store.py`
- Modify: `tests/conftest.py`
- Test: `tests/test_pratham_store.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pratham_store.py
from samagra import config
from samagra.pratham import store


def test_create_and_find_student_by_code_hash(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PRATHAM_DB", tmp_path / "pratham.db")
    store._INITIALIZED.clear()
    store.create_student("stu_1", "Asha", "codehashAAA", "2026-06-28T00:00:00Z")
    row = store.find_student_by_code_hash("codehashAAA")
    assert row["id"] == "stu_1" and row["name"] == "Asha" and row["status"] == "active"
    assert store.find_student_by_code_hash("nope") is None


def test_get_student_set_status_and_touch_login(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PRATHAM_DB", tmp_path / "pratham.db")
    store._INITIALIZED.clear()
    store.create_student("stu_1", "Asha", "h", "2026-06-28T00:00:00Z")
    store.touch_login("stu_1", "2026-06-28T09:00:00Z")
    assert store.get_student("stu_1")["last_login_at"] == "2026-06-28T09:00:00Z"
    store.set_status("stu_1", "revoked")
    assert store.get_student("stu_1")["status"] == "revoked"


def test_session_create_find_delete(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PRATHAM_DB", tmp_path / "pratham.db")
    store._INITIALIZED.clear()
    store.create_student("stu_1", "Asha", "h", "t")
    store.create_session("sesshash", "stu_1", "t", "2026-07-28T00:00:00Z")
    s = store.find_session("sesshash")
    assert s["student_id"] == "stu_1" and s["expires_at"] == "2026-07-28T00:00:00Z"
    store.delete_session("sesshash")
    assert store.find_session("sesshash") is None


def test_delete_sessions_for_student(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PRATHAM_DB", tmp_path / "pratham.db")
    store._INITIALIZED.clear()
    store.create_student("stu_1", "Asha", "h", "t")
    store.create_session("s1", "stu_1", "t", "z")
    store.create_session("s2", "stu_1", "t", "z")
    store.delete_sessions_for_student("stu_1")
    assert store.find_session("s1") is None and store.find_session("s2") is None


def test_list_students(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PRATHAM_DB", tmp_path / "pratham.db")
    store._INITIALIZED.clear()
    store.create_student("stu_1", "Asha", "h1", "t")
    store.create_student("stu_2", "Ben", "h2", "t")
    names = {r["name"] for r in store.list_students()}
    assert names == {"Asha", "Ben"}


def test_db_file_is_separate_from_governance(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PRATHAM_DB", tmp_path / "pratham.db")
    monkeypatch.setattr(config, "GOVERNANCE_DB", tmp_path / "governance.db")
    store._INITIALIZED.clear()
    store.create_student("stu_1", "Asha", "h", "t")
    assert (tmp_path / "pratham.db").exists()
    assert not (tmp_path / "governance.db").exists()  # identity never touches governance
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pratham_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'samagra.pratham.store'`.

- [ ] **Step 3: Write the implementation**

```python
# samagra/pratham/store.py
"""I/O over the durable, SEPARATE config.PRATHAM_DB (students + sessions).

Independent of governance.store: its own connection + self-initializing schema.
All bearer secrets (enrollment codes, session tokens) are stored ONLY as sha256
(the caller hashes via identity.hash_secret) — plaintext never persists here.
"""
from __future__ import annotations

import sqlite3

from .. import config

SCHEMA_VERSION = 1

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pratham_store.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Add test isolation to conftest**

In `tests/conftest.py`, inside the `isolate_data_db` fixture, after the `GOVERNANCE_DB` line, add:

```python
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
```

- [ ] **Step 6: Run the broader suite to verify no regression**

Run: `python -m pytest tests/test_pratham_store.py tests/test_governance.py -q`
Expected: PASS (no regressions; governance unaffected).

- [ ] **Step 7: Commit**

```bash
git add samagra/pratham/store.py tests/test_pratham_store.py tests/conftest.py
git commit -m "feat(g3): pratham.db store (students + sessions, hashed at rest) + test isolation"
```

---

## Task 4: `pratham/service.py` (orchestration)

**Files:**
- Create: `samagra/pratham/service.py`
- Test: `tests/test_pratham_service.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pratham_service.py
from samagra import config
from samagra.pratham import identity, service, store


def _fresh(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PRATHAM_DB", tmp_path / "pratham.db")
    store._INITIALIZED.clear()
    service._LIMITER._hits.clear()


def test_enroll_mints_a_code_and_persists_the_student(tmp_path, monkeypatch):
    _fresh(tmp_path, monkeypatch)
    res = service.enroll("Asha")
    assert res["name"] == "Asha" and res["id"].startswith("stu_")
    assert len(res["code"]) >= 11
    # the code is stored only as a hash
    row = store.get_student(res["id"])
    assert row["code_hash"] == identity.hash_secret(res["code"])
    assert "code" not in row


def test_enroll_rejects_blank_name(tmp_path, monkeypatch):
    _fresh(tmp_path, monkeypatch)
    import pytest
    with pytest.raises(ValueError):
        service.enroll("   ")


def test_login_valid_code_creates_a_session(tmp_path, monkeypatch):
    _fresh(tmp_path, monkeypatch)
    code = service.enroll("Asha")["code"]
    out = service.login(code, client_key="ip1")
    assert out["name"] == "Asha"
    token = out["_session_token"]
    assert store.find_session(identity.hash_secret(token)) is not None


def test_login_wrong_or_revoked_code_returns_none(tmp_path, monkeypatch):
    _fresh(tmp_path, monkeypatch)
    res = service.enroll("Asha")
    assert service.login("not-the-code", client_key="ip1") is None
    service.revoke(res["id"])
    assert service.login(res["code"], client_key="ip1") is None


def test_login_rate_limited_returns_none(tmp_path, monkeypatch):
    _fresh(tmp_path, monkeypatch)
    monkeypatch.setattr(service, "_LIMITER", identity.RateLimiter(max_attempts=1, window_seconds=60))
    service.enroll("Asha")
    assert service.login("x", client_key="ip1") is None     # 1st attempt allowed (bad code -> None)
    assert service.login("y", client_key="ip1") is None     # 2nd blocked by limiter -> None


def test_current_student_valid_expired_and_revoked(tmp_path, monkeypatch):
    _fresh(tmp_path, monkeypatch)
    code = service.enroll("Asha")["code"]
    token = service.login(code, client_key="ip1")["_session_token"]
    assert service.current_student(token)["name"] == "Asha"
    assert service.current_student(None) is None
    assert service.current_student("garbage") is None
    # far-future "now" -> the 30-day session is expired
    import time
    assert service.current_student(token, now_epoch=time.time() + 40 * 86400) is None


def test_logout_invalidates_the_session(tmp_path, monkeypatch):
    _fresh(tmp_path, monkeypatch)
    code = service.enroll("Asha")["code"]
    token = service.login(code, client_key="ip1")["_session_token"]
    service.logout(token)
    assert service.current_student(token) is None
    service.logout(None)  # idempotent / no-op


def test_revoke_invalidates_existing_sessions(tmp_path, monkeypatch):
    _fresh(tmp_path, monkeypatch)
    res = service.enroll("Asha")
    token = service.login(res["code"], client_key="ip1")["_session_token"]
    service.revoke(res["id"])
    assert service.current_student(token) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pratham_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'samagra.pratham.service'`.

- [ ] **Step 3: Write the implementation**

```python
# samagra/pratham/service.py
"""Orchestration over identity (pure) + store (I/O): enroll, login, session lookup,
logout, revoke. Keeps the FastAPI handlers trivial and the logic unit-testable.

The process-wide _LIMITER blunts login volume; tests inject their own.
"""
from __future__ import annotations

import time
import uuid

from .. import config
from . import identity, store

_LIMITER = identity.RateLimiter()


def enroll(name: str) -> dict:
    """Owner action (CLI): mint a code, create the student. Returns the plaintext
    code ONCE (the only place it ever appears un-hashed) for the owner to hand over."""
    name = (name or "").strip()
    if not name:
        raise ValueError("name is required")
    code = identity.new_code()
    student_id = "stu_" + uuid.uuid4().hex[:12]
    store.create_student(student_id, name, identity.hash_secret(code), identity.now_iso())
    return {"id": student_id, "name": name, "code": code}


def login(code: str, *, client_key: str, now_epoch: float | None = None) -> dict | None:
    """Redeem an enrollment code -> a new session. Returns {id, name, _session_token}
    or None for a bad/revoked code OR a rate-limited caller (an identical None — no
    oracle). _session_token is the RAW token the caller sets as the cookie."""
    now_epoch = time.time() if now_epoch is None else now_epoch
    if not _LIMITER.allow(client_key, now_epoch):
        return None
    code = (code or "").strip()
    row = store.find_student_by_code_hash(identity.hash_secret(code))
    if identity.redeem_verdict(row, now_epoch) != "ok":
        return None
    token = identity.new_session_token()
    created = identity.now_iso()
    expires = identity.session_expiry(now_epoch, config.PRATHAM_SESSION_TTL_DAYS)
    store.create_session(identity.hash_secret(token), row["id"], created, expires)
    store.touch_login(row["id"], created)
    return {"id": row["id"], "name": row["name"], "_session_token": token}


def current_student(token: str | None, *, now_epoch: float | None = None) -> dict | None:
    """The student for a session cookie, or None (absent/expired/revoked)."""
    if not token:
        return None
    now_epoch = time.time() if now_epoch is None else now_epoch
    sess = store.find_session(identity.hash_secret(token))
    if not sess or identity.is_expired(sess["expires_at"], now_epoch):
        return None
    row = store.get_student(sess["student_id"])
    if not row or row.get("status") != "active":
        return None
    return {"id": row["id"], "name": row["name"]}


def logout(token: str | None) -> None:
    if token:
        store.delete_session(identity.hash_secret(token))


def revoke(student_id: str) -> None:
    """Owner action (CLI): revoke a student + invalidate ALL their sessions."""
    store.set_status(student_id, "revoked")
    store.delete_sessions_for_student(student_id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pratham_service.py -v`
Expected: PASS (8 passed).

- [ ] **Step 5: Commit**

```bash
git add samagra/pratham/service.py tests/test_pratham_service.py
git commit -m "feat(g3): pratham identity service (enroll/login/session/logout/revoke)"
```

---

## Task 5: Owner publish endpoints + origin gate

**Files:**
- Modify: `samagra/api/origin_auth.py:41-43` (`_PROTECTED_POSTS`)
- Modify: `samagra/api/app.py` (after the G2 published GETs, ~line 247)
- Test: `tests/test_api_factory_publish.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_api_factory_publish.py
import pytest
from fastapi.testclient import TestClient

from samagra import config
from samagra.api import app as api_app
from samagra.api import origin_auth


def test_publish_endpoints_are_in_protected_posts():
    assert origin_auth.is_protected("POST", "/api/factory/publish") is True
    assert origin_auth.is_protected("POST", "/api/factory/unpublish") is True


@pytest.fixture
def gate_on(monkeypatch):
    monkeypatch.setattr(config, "DISABLE_ORIGIN_AUTH", False)
    monkeypatch.setattr(config, "ACCESS_AUD", None)
    monkeypatch.setattr(config, "ACCESS_TEAM_DOMAIN", None)
    monkeypatch.setattr(config, "OWNER_EMAIL", None)
    return monkeypatch


def test_remote_publish_without_identity_is_403(gate_on):
    gate_on.setattr(origin_auth, "_client_host", lambda req: "203.0.113.9")
    c = TestClient(api_app.app)
    r = c.post("/api/factory/publish", json={"chapter": "circular-motion"})
    assert r.status_code == 403  # gate blocks before the handler


def test_loopback_publish_bad_body_is_400(gate_on):
    gate_on.setattr(origin_auth, "_client_host", lambda req: "127.0.0.1")
    c = TestClient(api_app.app)
    r = c.post("/api/factory/publish", json={})       # reached handler -> 400, not 403
    assert r.status_code == 400


def test_publish_unknown_chapter_is_409(tmp_path, monkeypatch):
    # conftest disables the gate (local dev), so this reaches the handler on loopback.
    monkeypatch.setattr(config, "GOVERNANCE_DB", tmp_path / "governance.db")
    monkeypatch.setattr(config, "PUBLISHED_DIR", tmp_path / "published")
    from samagra.governance import store as gov
    gov._INITIALIZED.clear(); gov.ensure_tables()
    c = TestClient(api_app.app)
    r = c.post("/api/factory/publish", json={"chapter": "no-such-chapter"})
    assert r.status_code == 409
    gov._INITIALIZED.clear()


def test_publish_delegates_to_run(monkeypatch):
    captured = {}

    def fake_publish(chapter, *, lanes=None, actor="owner"):
        captured.update(chapter=chapter, lanes=lanes, actor=actor)
        return {"chapter": chapter, "publication_id": "pub_x", "published": ["revision"]}
    monkeypatch.setattr("samagra.factory.publish.run.publish", fake_publish)
    c = TestClient(api_app.app)
    r = c.post("/api/factory/publish", json={"chapter": "cm", "lanes": ["revision"]})
    assert r.status_code == 200
    assert r.json()["result"]["publication_id"] == "pub_x"
    assert captured == {"chapter": "cm", "lanes": ["revision"], "actor": "owner"}


def test_unpublish_delegates_to_run(monkeypatch):
    def fake_unpublish(chapter, *, lanes=None, actor="owner"):
        return {"chapter": chapter, "publication_id": "pub_y", "unpublished": ["revision"]}
    monkeypatch.setattr("samagra.factory.publish.run.unpublish", fake_unpublish)
    c = TestClient(api_app.app)
    r = c.post("/api/factory/unpublish", json={"chapter": "cm"})
    assert r.status_code == 200 and r.json()["result"]["publication_id"] == "pub_y"


def test_publish_bad_lanes_type_is_400():
    c = TestClient(api_app.app)
    r = c.post("/api/factory/publish", json={"chapter": "cm", "lanes": "revision"})
    assert r.status_code == 400  # lanes must be a list
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_api_factory_publish.py -v`
Expected: FAIL — `is_protected(...) is True` assertion fails (not yet protected); the POSTs 404 (not defined).

- [ ] **Step 3a: Add the two POSTs to `_PROTECTED_POSTS`**

In `samagra/api/origin_auth.py`, replace the `_PROTECTED_POSTS` frozenset:

```python
_PROTECTED_POSTS = frozenset({
    "/api/refresh", "/api/tick", "/api/munshi/capture", "/api/mcd/seeds",
    # G3: the owner publish write path — the GUI/network sibling of the G1 CLI
    # publish. Owner-gated (never-automated); delegates to the reviewed publish.run.
    "/api/factory/publish", "/api/factory/unpublish",
})
```

- [ ] **Step 3b: Add the endpoints to `app.py`**

In `samagra/api/app.py`, add a body-parse helper + the two handlers immediately after the `api_published_artifact` function (before `@app.post("/api/refresh")`):

```python
# -- G3 owner publish write path (owner-gated via origin_auth._PROTECTED_POSTS) --
def _parse_publish_body(payload: dict):
    """Validate {chapter, lanes?}. chapter required (non-empty str); lanes optional
    (list[str]) — the network sibling of the G1 CLI's `--lanes`."""
    chapter = (payload or {}).get("chapter")
    if not isinstance(chapter, str) or not chapter.strip():
        raise HTTPException(400, "chapter is required")
    lanes = (payload or {}).get("lanes")
    if lanes is not None and not (isinstance(lanes, list)
                                  and all(isinstance(x, str) for x in lanes)):
        raise HTTPException(400, "lanes must be a list of strings")
    return chapter.strip(), lanes


@app.post("/api/factory/publish")
def api_factory_publish(payload: dict):
    # The owner release gate over HTTP. NEVER-AUTOMATED: an explicit per-call
    # {chapter, lanes?} from an authenticated owner (the gate above) — no schedule,
    # no auto-approve. A thin delegate to the already-reviewed G1 publish.run; adds
    # no new write mechanism (published/ frozen copies + append-only gov events only).
    chapter, lanes = _parse_publish_body(payload)
    from ..factory.publish import run as publish_run
    try:
        return {"ok": True, "result": publish_run.publish(chapter, lanes=lanes, actor="owner")}
    except (ValueError, FileNotFoundError) as e:
        # G1's clean refusals (unknown chapter / nothing captured / mcd lane /
        # non-textbook seed / missing artifact) -> 409 conflict, never a 500.
        raise HTTPException(409, str(e))


@app.post("/api/factory/unpublish")
def api_factory_unpublish(payload: dict):
    chapter, lanes = _parse_publish_body(payload)
    from ..factory.publish import run as publish_run
    try:
        return {"ok": True, "result": publish_run.unpublish(chapter, lanes=lanes, actor="owner")}
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(409, str(e))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_api_factory_publish.py tests/test_origin_auth.py -v`
Expected: PASS (new file all pass; `test_origin_auth.py` still green).

- [ ] **Step 5: Commit**

```bash
git add samagra/api/origin_auth.py samagra/api/app.py tests/test_api_factory_publish.py
git commit -m "feat(g3): owner-gated POST /api/factory/publish|unpublish (delegate to G1 publish.run)"
```

---

## Task 6: Public student endpoints (login/logout/me)

**Files:**
- Modify: `samagra/api/app.py:14-15` (imports) + add the 3 endpoints
- Modify: `tests/conftest.py` (reset the rate limiter per test)
- Test: `tests/test_api_learn.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_api_learn.py
from fastapi.testclient import TestClient

from samagra import config
from samagra.api import app as api_app
from samagra.api import origin_auth


def _client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PRATHAM_DB", tmp_path / "pratham.db")
    from samagra.pratham import store
    store._INITIALIZED.clear()
    return TestClient(api_app.app)


def test_learn_endpoints_are_public_not_gated():
    # /learn surface stays PUBLIC (DEC-11) — not in the protected tables.
    assert origin_auth.is_protected("POST", "/api/learn/login") is False
    assert origin_auth.is_protected("POST", "/api/learn/logout") is False
    assert origin_auth.is_protected("GET", "/api/learn/me") is False


def test_login_sets_cookie_and_me_returns_student(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    from samagra.pratham import service
    code = service.enroll("Asha")["code"]
    r = c.post("/api/learn/login", json={"code": code})
    assert r.status_code == 200 and r.json()["student"]["name"] == "Asha"
    assert "pratham_session" in r.cookies
    me = c.get("/api/learn/me")            # TestClient persists the cookie
    assert me.json()["student"]["name"] == "Asha"


def test_login_cookie_flags_httponly_samesite(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    from samagra.pratham import service
    code = service.enroll("Asha")["code"]
    r = c.post("/api/learn/login", json={"code": code})
    set_cookie = r.headers["set-cookie"].lower()
    assert "httponly" in set_cookie and "samesite=lax" in set_cookie


def test_login_wrong_code_is_401(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.post("/api/learn/login", json={"code": "nope"})
    assert r.status_code == 401


def test_login_missing_code_is_400(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    assert c.post("/api/learn/login", json={}).status_code == 400


def test_me_without_cookie_is_null(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    assert c.get("/api/learn/me").json() == {"student": None}


def test_logout_clears_session(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    from samagra.pratham import service
    code = service.enroll("Asha")["code"]
    c.post("/api/learn/login", json={"code": code})
    c.post("/api/learn/logout")
    assert c.get("/api/learn/me").json() == {"student": None}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_api_learn.py -v`
Expected: FAIL — the login/logout/me routes 404 (not defined).

- [ ] **Step 3a: Extend the app imports**

In `samagra/api/app.py`, change line 14:

```python
from fastapi import FastAPI, HTTPException, Request
```

and line 15:

```python
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
```

- [ ] **Step 3b: Add the three public endpoints**

In `samagra/api/app.py`, after the two factory-publish handlers (Task 5), add:

```python
# -- G3 PRATHAM student identity (PUBLIC — deliberately NOT in _PROTECTED_*) ------
# /learn stays public-by-design (DEC-11); the session cookie is the only credential.
# The login write touches ONLY pratham.db (physically isolated from governance.db,
# the inward build(), and the 7 subsystems).
_PRATHAM_COOKIE = "pratham_session"


def _rate_key(request: Request) -> str:
    # Best-effort key for the login rate limiter. Behind cloudflared the TCP peer is
    # loopback, so prefer Cf-Connecting-Ip when present — a CALLER-CONTROLLED header,
    # used ONLY to blunt volume, NEVER to widen trust (the real brute-force defense is
    # the code's entropy). Falls back to the TCP peer host.
    return (request.headers.get("Cf-Connecting-Ip")
            or (request.client.host if request.client else "unknown"))


@app.post("/api/learn/login")
def api_learn_login(payload: dict, request: Request):
    code = (payload or {}).get("code")
    if not isinstance(code, str) or not code.strip():
        raise HTTPException(400, "code required")
    from ..pratham import service
    student = service.login(code.strip(), client_key=_rate_key(request))
    if student is None:        # bad / revoked code OR rate-limited -> identical 401
        raise HTTPException(401, "invalid code")
    resp = JSONResponse({"student": {"id": student["id"], "name": student["name"]}})
    resp.set_cookie(_PRATHAM_COOKIE, student["_session_token"], httponly=True,
                    samesite="lax", secure=config.PRATHAM_COOKIE_SECURE, path="/",
                    max_age=config.PRATHAM_SESSION_TTL_DAYS * 86400)
    return resp


@app.post("/api/learn/logout")
def api_learn_logout(request: Request):
    from ..pratham import service
    service.logout(request.cookies.get(_PRATHAM_COOKIE))
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(_PRATHAM_COOKIE, path="/")
    return resp


@app.get("/api/learn/me")
def api_learn_me(request: Request):
    from ..pratham import service
    return {"student": service.current_student(request.cookies.get(_PRATHAM_COOKIE))}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_api_learn.py -v`
Expected: PASS (7 passed).

- [ ] **Step 5: Reset the rate limiter per test (conftest)**

In `tests/conftest.py`, extend the `try/except` block added in Task 3 so the process-wide limiter never leaks state between tests:

```python
    try:
        from samagra.pratham import store as _pratham_store
        _pratham_store._INITIALIZED.clear()
        from samagra.pratham import service as _pratham_service
        _pratham_service._LIMITER._hits.clear()
    except Exception:  # noqa: BLE001 — package may not exist mid-build
        pass
```

- [ ] **Step 6: Run the full API test slice to verify no regression**

Run: `python -m pytest tests/test_api_learn.py tests/test_origin_auth.py tests/test_published_api.py -q`
Expected: PASS (no regressions).

- [ ] **Step 7: Commit**

```bash
git add samagra/api/app.py tests/test_api_learn.py tests/conftest.py
git commit -m "feat(g3): public POST /api/learn/login|logout + GET /api/learn/me (opaque session cookie)"
```

---

## Task 7: CLI `samagra pratham enroll|students|revoke`

**Files:**
- Modify: `samagra/__main__.py` (add `cmd_pratham` + subparser)
- Test: `tests/test_pratham_cli.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pratham_cli.py
from samagra import config
from samagra.__main__ import build_parser
from samagra.pratham import service, store


def _args(argv):
    return build_parser().parse_args(argv)


def test_enroll_prints_code_and_persists(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(config, "PRATHAM_DB", tmp_path / "pratham.db")
    store._INITIALIZED.clear()
    args = _args(["pratham", "enroll", "Asha"])
    args.func(args)
    out = capsys.readouterr().out
    assert "Asha" in out and "code" in out.lower()
    assert len(store.list_students()) == 1


def test_students_lists_enrolled(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(config, "PRATHAM_DB", tmp_path / "pratham.db")
    store._INITIALIZED.clear()
    service.enroll("Asha")
    args = _args(["pratham", "students"])
    args.func(args)
    assert "Asha" in capsys.readouterr().out


def test_revoke_marks_revoked(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(config, "PRATHAM_DB", tmp_path / "pratham.db")
    store._INITIALIZED.clear()
    sid = service.enroll("Asha")["id"]
    args = _args(["pratham", "revoke", sid])
    args.func(args)
    assert store.get_student(sid)["status"] == "revoked"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pratham_cli.py -v`
Expected: FAIL — `argparse` errors on the unknown `pratham` subcommand (SystemExit).

- [ ] **Step 3a: Add `cmd_pratham`**

In `samagra/__main__.py`, after `cmd_bridge` (before `build_parser`), add:

```python
def cmd_pratham(args) -> None:
    from .pratham import service, store

    if args.action == "enroll":
        res = service.enroll(args.name)
        print(f"pratham enroll: {res['name']} -> {res['id']}")
        print(f"  code (give to the student; shown ONCE): {res['code']}")
    elif args.action == "students":
        rows = store.list_students()
        if not rows:
            print('pratham students: none enrolled yet (`pratham enroll "<name>"`).')
        for r in rows:
            print(f"  [{r['id']}] {r['status']:8} {r['name']}  "
                  f"(last login {r['last_login_at'] or '-'})")
    elif args.action == "revoke":
        service.revoke(args.student_id)
        print(f"pratham revoke: {args.student_id} revoked (sessions invalidated)")
```

- [ ] **Step 3b: Wire the subparser**

In `build_parser()`, after the `factory` subparser block (`ft.set_defaults(func=cmd_factory)`) and before `return p`, add:

```python
    pr = sub.add_parser("pratham",
                        help="student identity (Phase G3): enroll / students / revoke")
    pr_sub = pr.add_subparsers(dest="action", required=True)
    pr_en = pr_sub.add_parser("enroll",
                              help="enroll a student (mints + prints a one-time code)")
    pr_en.add_argument("name")
    pr_sub.add_parser("students", help="list enrolled students")
    pr_rv = pr_sub.add_parser("revoke",
                              help="revoke a student (invalidates their sessions)")
    pr_rv.add_argument("student_id")
    pr.set_defaults(func=cmd_pratham)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pratham_cli.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add samagra/__main__.py tests/test_pratham_cli.py
git commit -m "feat(g3): samagra pratham enroll|students|revoke CLI"
```

---

## Task 8: Backend golden threads + isolation proof

**Files:**
- Test: `tests/test_g3_golden.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_g3_golden.py
"""G3 acceptance golden threads (spec §9):
1. publish over HTTP — gated, delegates, 409 on unknown;
2. enroll -> login -> me -> revoke;
3. identity never touches governance.db (physical isolation).
"""
from fastapi.testclient import TestClient

from samagra import config
from samagra.api import app as api_app


def test_golden_publish_over_http(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "GOVERNANCE_DB", tmp_path / "governance.db")
    monkeypatch.setattr(config, "DATA_DB", tmp_path / "samagra.db")
    monkeypatch.setattr(config, "EXPORT_DIR", tmp_path / "exports")
    monkeypatch.setattr(config, "PUBLISHED_DIR", tmp_path / "published")
    from samagra.governance import store as gov
    gov._INITIALIZED.clear(); gov.ensure_tables()
    monkeypatch.chdir(tmp_path)

    def fake_export_one(slug, variant, **kw):
        out = tmp_path / f"{slug}-{variant}.html"
        out.write_text(f"<h1>{slug} {variant}</h1>", encoding="utf-8")
        return {"variant": variant, "html": str(out), "docx": None, "gdoc": None}
    monkeypatch.setattr("samagra.lectures.export.export_one", fake_export_one)

    from samagra.factory import run as factory
    proposals = factory.plan("textbook:circular-motion", dry=False)
    rev = next(p for p in proposals if p["line"] == "revision")
    factory.approve(rev["assignment_id"])
    factory.build(rev["assignment_id"])

    c = TestClient(api_app.app)
    # publish over HTTP (gate disabled in tests -> reaches handler on loopback)
    r = c.post("/api/factory/publish", json={"chapter": "circular-motion", "lanes": ["revision"]})
    assert r.status_code == 200
    assert "revision" in r.json()["result"]["published"]
    # the corpus is now readable via the G2 public surface
    assert "circular-motion" in c.get("/api/published").json()["chapters"]
    # unknown chapter -> 409
    assert c.post("/api/factory/publish", json={"chapter": "nope"}).status_code == 409
    gov._INITIALIZED.clear()


def test_golden_enroll_login_me_revoke(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PRATHAM_DB", tmp_path / "pratham.db")
    from samagra.pratham import store, service
    store._INITIALIZED.clear()
    res = service.enroll("Asha")
    c = TestClient(api_app.app)
    assert c.post("/api/learn/login", json={"code": res["code"]}).json()["student"]["name"] == "Asha"
    assert c.get("/api/learn/me").json()["student"]["name"] == "Asha"
    # a wrong code is an identical 401
    assert c.post("/api/learn/login", json={"code": "wrong"}).status_code == 401
    service.revoke(res["id"])
    assert c.get("/api/learn/me").json() == {"student": None}  # session invalidated
    store._INITIALIZED.clear()


def test_identity_never_touches_governance_db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PRATHAM_DB", tmp_path / "pratham.db")
    monkeypatch.setattr(config, "GOVERNANCE_DB", tmp_path / "governance.db")
    from samagra.governance import store as gov
    from samagra.pratham import store as pstore, service
    gov._INITIALIZED.clear(); pstore._INITIALIZED.clear()
    gov.ensure_tables()
    before = (tmp_path / "governance.db").read_bytes()
    res = service.enroll("Asha")
    service.login(res["code"], client_key="ip1")
    service.revoke(res["id"])
    after = (tmp_path / "governance.db").read_bytes()
    assert before == after  # all identity writes land in pratham.db only
    gov._INITIALIZED.clear()
```

- [ ] **Step 2: Run test to verify it fails (or passes)**

Run: `python -m pytest tests/test_g3_golden.py -v`
Expected: PASS — every component already exists (Tasks 1-7). This task is the integration proof; if any assertion fails, fix the relevant module before continuing.

- [ ] **Step 3: Commit**

```bash
git add tests/test_g3_golden.py
git commit -m "test(g3): golden threads — publish over HTTP, enroll/login/me/revoke, gov isolation"
```

---

## Task 9: Frontend — `lib/pratham/session.ts` + `Student` type

**Files:**
- Modify: `frontend/src/types/contracts.ts:1-7` (add `Student`)
- Create: `frontend/src/lib/pratham/session.ts`
- Test: `frontend/src/lib/pratham/session.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// frontend/src/lib/pratham/session.test.ts
import { afterEach, describe, expect, it, vi } from "vitest";
import { loginRequest, logoutRequest, meRequest } from "./session";

afterEach(() => vi.restoreAllMocks());

function mockFetch(ok: boolean, body: unknown) {
  return vi.fn(async () => ({ ok, json: async () => body })) as unknown as typeof fetch;
}

describe("pratham session wrappers", () => {
  it("loginRequest posts the code and returns the student", async () => {
    const f = mockFetch(true, { student: { id: "stu_1", name: "Asha" } });
    vi.stubGlobal("fetch", f);
    const r = await loginRequest("abc");
    expect(r.student.name).toBe("Asha");
    const [url, opts] = (f as unknown as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe("/api/learn/login");
    expect(JSON.parse((opts as RequestInit).body as string)).toEqual({ code: "abc" });
  });

  it("loginRequest throws on a non-2xx (so the caller can show an error)", async () => {
    vi.stubGlobal("fetch", mockFetch(false, { detail: "invalid code" }));
    await expect(loginRequest("bad")).rejects.toThrow();
  });

  it("meRequest returns the student when present", async () => {
    vi.stubGlobal("fetch", mockFetch(true, { student: { id: "stu_1", name: "Asha" } }));
    expect(await meRequest()).toEqual({ id: "stu_1", name: "Asha" });
  });

  it("meRequest returns null when not authenticated / on error", async () => {
    vi.stubGlobal("fetch", mockFetch(true, { student: null }));
    expect(await meRequest()).toBeNull();
    vi.stubGlobal("fetch", mockFetch(false, {}));
    expect(await meRequest()).toBeNull();
  });

  it("logoutRequest posts to the logout endpoint", async () => {
    const f = mockFetch(true, { ok: true });
    vi.stubGlobal("fetch", f);
    await logoutRequest();
    expect((f as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0]).toBe("/api/learn/logout");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/lib/pratham/session.test.ts`
Expected: FAIL — cannot resolve `./session`.

- [ ] **Step 3a: Add the `Student` type**

In `frontend/src/types/contracts.ts`, after the `AppId` type (before/around `AppMeta`), add:

```ts
// G3: a PRATHAM student identity (the /api/learn/me + login shape).
export interface Student { id: string; name: string; }
```

- [ ] **Step 3b: Write the session wrappers**

```ts
// frontend/src/lib/pratham/session.ts
// Thin fetch wrappers for the PUBLIC /api/learn/* identity endpoints (Phase G3).
// The reader manages signed-in state from these; anonymous reading needs none.
import type { Student } from "../../types/contracts";

export interface MeResponse { student: Student | null; }
export interface LoginResponse { student: Student; }

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(path, {
    method: "POST",
    headers: { "content-type": "application/json", accept: "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return (await res.json()) as T;
}

export function loginRequest(code: string): Promise<LoginResponse> {
  return postJson<LoginResponse>("/api/learn/login", { code });
}

export function logoutRequest(): Promise<{ ok: true }> {
  return postJson<{ ok: true }>("/api/learn/logout", {});
}

export async function meRequest(): Promise<Student | null> {
  try {
    const res = await fetch("/api/learn/me", { headers: { accept: "application/json" } });
    if (!res.ok) return null;
    const j = (await res.json()) as MeResponse;
    return j.student ?? null;
  } catch {
    return null;
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/lib/pratham/session.test.ts`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/contracts.ts frontend/src/lib/pratham/session.ts frontend/src/lib/pratham/session.test.ts
git commit -m "feat(g3): frontend pratham session wrappers + Student type"
```

---

## Task 10: Frontend — additive sign-in/out in the `/learn` reader

**Files:**
- Modify: `frontend/src/apps/Pratham/index.tsx`
- Test: `frontend/src/apps/Pratham/signin.test.tsx` (create — keeps the existing G2 Pratham test untouched)

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/apps/Pratham/signin.test.tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import Pratham from "./index";

// The corpus fetch is irrelevant here — return an empty manifest so the reader
// mounts; we only exercise the additive sign-in affordance.
vi.mock("../../hooks/useApi", () => ({
  useApi: () => ({ data: { schema: "samagra.published.v1", chapters: {} }, loading: false, error: null }),
}));
vi.mock("../../lib/pratham/session", () => ({
  meRequest: vi.fn(),
  loginRequest: vi.fn(),
  logoutRequest: vi.fn(),
}));
import { loginRequest, logoutRequest, meRequest } from "../../lib/pratham/session";

afterEach(() => vi.clearAllMocks());

describe("Pratham sign-in (G3)", () => {
  it("shows a Sign in control when anonymous", async () => {
    (meRequest as ReturnType<typeof vi.fn>).mockResolvedValue(null);
    render(<Pratham />);
    expect(await screen.findByTestId("pratham-signin")).toBeTruthy();
  });

  it("signs in with a code and shows the student name", async () => {
    (meRequest as ReturnType<typeof vi.fn>).mockResolvedValue(null);
    (loginRequest as ReturnType<typeof vi.fn>).mockResolvedValue({ student: { id: "s1", name: "Asha" } });
    render(<Pratham />);
    fireEvent.click(await screen.findByTestId("pratham-signin"));
    fireEvent.change(screen.getByTestId("pratham-signin-input"), { target: { value: "abc" } });
    fireEvent.click(screen.getByTestId("pratham-signin-submit"));
    await waitFor(() => expect(screen.getByTestId("pratham-user").textContent).toContain("Asha"));
    expect(loginRequest).toHaveBeenCalledWith("abc");
  });

  it("hydrates an already-signed-in student on mount", async () => {
    (meRequest as ReturnType<typeof vi.fn>).mockResolvedValue({ id: "s1", name: "Ben" });
    render(<Pratham />);
    await waitFor(() => expect(screen.getByTestId("pratham-user").textContent).toContain("Ben"));
  });

  it("signs out", async () => {
    (meRequest as ReturnType<typeof vi.fn>).mockResolvedValue({ id: "s1", name: "Ben" });
    (logoutRequest as ReturnType<typeof vi.fn>).mockResolvedValue({ ok: true });
    render(<Pratham />);
    fireEvent.click(await screen.findByTestId("pratham-signout"));
    await waitFor(() => expect(screen.getByTestId("pratham-signin")).toBeTruthy());
  });

  it("shows an error on a bad code (login rejects)", async () => {
    (meRequest as ReturnType<typeof vi.fn>).mockResolvedValue(null);
    (loginRequest as ReturnType<typeof vi.fn>).mockRejectedValue(new Error("HTTP 401"));
    render(<Pratham />);
    fireEvent.click(await screen.findByTestId("pratham-signin"));
    fireEvent.change(screen.getByTestId("pratham-signin-input"), { target: { value: "bad" } });
    fireEvent.click(screen.getByTestId("pratham-signin-submit"));
    expect(await screen.findByTestId("pratham-signin-error")).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/apps/Pratham/signin.test.tsx`
Expected: FAIL — no `pratham-signin` testid (sign-in not built yet).

- [ ] **Step 3: Add the sign-in affordance to the reader**

In `frontend/src/apps/Pratham/index.tsx`:

(a) extend the imports at the top:

```tsx
import { useEffect, useState } from "react";
import type { Student } from "../../types/contracts";
import { loginRequest, logoutRequest, meRequest } from "../../lib/pratham/session";
```

(b) inside `export default function Pratham()`, after the existing `const [sel, setSel] = useState(...)` line, add the identity state + handlers:

```tsx
  // G3: additive student identity. Anonymous reading is unchanged; a signed-in
  // student gets a small shell header (their name + sign out). The corpus renders
  // regardless of session.
  const [student, setStudent] = useState<Student | null>(null);
  const [signinOpen, setSigninOpen] = useState(false);
  const [code, setCode] = useState("");
  const [authErr, setAuthErr] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    meRequest().then((s) => { if (alive) setStudent(s); });
    return () => { alive = false; };
  }, []);

  async function doLogin() {
    setAuthErr(null);
    try {
      const r = await loginRequest(code.trim());
      setStudent(r.student);
      setSigninOpen(false);
      setCode("");
    } catch {
      setAuthErr("That code didn't work. Check it and try again.");
    }
  }

  async function doLogout() {
    try { await logoutRequest(); } finally { setStudent(null); }
  }
```

(c) in the `<header>` element, after the existing `<span>…Published revision corpus</span>`, add an auth control pushed to the right (insert just before the header's closing `</header>`):

```tsx
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8 }}>
          {student ? (
            <>
              <span data-testid="pratham-user" style={{ fontSize: 13, color: C.muted }}>
                Signed in as {student.name}
              </span>
              <button data-testid="pratham-signout" onClick={doLogout}
                style={{ border: `1px solid ${C.line}`, background: C.card, color: C.text,
                  font: "inherit", padding: "5px 10px", borderRadius: 8, cursor: "pointer" }}>
                Sign out
              </button>
            </>
          ) : signinOpen ? (
            <>
              <input data-testid="pratham-signin-input" value={code}
                onChange={(e) => setCode(e.target.value)} placeholder="Enter your code"
                aria-label="enrollment code"
                style={{ font: "inherit", padding: "5px 8px", borderRadius: 8,
                  border: `1px solid ${C.line}` }} />
              <button data-testid="pratham-signin-submit" onClick={doLogin}
                style={{ border: 0, background: C.accent, color: "#fff", font: "inherit",
                  padding: "6px 12px", borderRadius: 8, cursor: "pointer" }}>
                Go
              </button>
              {authErr ? (
                <span data-testid="pratham-signin-error" role="alert"
                  style={{ fontSize: 12, color: "#b91c1c" }}>{authErr}</span>
              ) : null}
            </>
          ) : (
            <button data-testid="pratham-signin" onClick={() => setSigninOpen(true)}
              style={{ border: `1px solid ${C.line}`, background: C.card, color: C.text,
                font: "inherit", padding: "5px 10px", borderRadius: 8, cursor: "pointer" }}>
              Sign in
            </button>
          )}
        </div>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/apps/Pratham/signin.test.tsx src/apps/Pratham/index.test.tsx`
Expected: PASS — the new sign-in tests pass AND the existing G2 Pratham test still passes (anonymous reading unchanged).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/apps/Pratham/index.tsx frontend/src/apps/Pratham/signin.test.tsx
git commit -m "feat(g3): additive student sign-in/out in the /learn reader"
```

---

## Task 11: Frontend — the operator Publish control

**Files:**
- Create: `frontend/src/lib/publishctl/rows.ts`
- Test: `frontend/src/lib/publishctl/rows.test.ts`
- Create: `frontend/src/apps/Publish/index.tsx`
- Test: `frontend/src/apps/Publish/index.test.tsx`
- Modify: `frontend/src/types/contracts.ts` (`AppId` += `"publish"`)
- Modify: `frontend/src/registry.ts` (`APPS` + `ORDER`)
- Modify: `frontend/src/registry.test.ts` (count 18→19, ORDER, registration test)
- Modify: `frontend/src/App.tsx:60-79` (`APP_DIR`)
- Modify: `frontend/src/components/icons-data.ts` (`ICONS.publish`)

- [ ] **Step 1: Write the failing pure-lib test**

```ts
// frontend/src/lib/publishctl/rows.test.ts
import { describe, expect, it } from "vitest";
import { publishRows } from "./rows";

const manifest = {
  chapters: {
    "circular-motion": {
      chapter: "circular-motion", title: "Circular Motion",
      artifacts: [{ lane: "revision" }],
    },
  },
};

const assignments = [
  { seed_ref: "textbook:circular-motion", pipeline: "revision", status: "captured" },
  { seed_ref: "textbook:circular-motion", pipeline: "deck", status: "captured" },
  { seed_ref: "textbook:gravitation", pipeline: "revision", status: "captured" },
  { seed_ref: "textbook:gravitation", pipeline: "revision", status: "in-review" }, // not captured
  { seed_ref: "munshi:52", pipeline: "seed", status: "captured" },                 // not textbook
];

describe("publishRows", () => {
  it("merges captured textbook lanes with the published manifest", () => {
    const rows = publishRows(assignments, manifest);
    const cm = rows.find((r) => r.chapter === "circular-motion")!;
    expect(cm.title).toBe("Circular Motion");
    expect(cm.capturedLanes.sort()).toEqual(["deck", "revision"]);
    expect(cm.publishedLanes).toEqual(["revision"]);
  });

  it("includes captured chapters with nothing published yet", () => {
    const rows = publishRows(assignments, manifest);
    const grav = rows.find((r) => r.chapter === "gravitation")!;
    expect(grav.capturedLanes).toEqual(["revision"]);   // the in-review one is excluded
    expect(grav.publishedLanes).toEqual([]);
  });

  it("ignores non-textbook seeds and sorts by chapter", () => {
    const rows = publishRows(assignments, manifest);
    expect(rows.map((r) => r.chapter)).toEqual(["circular-motion", "gravitation"]);
  });

  it("is defensive against null inputs", () => {
    expect(publishRows(null, null)).toEqual([]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/lib/publishctl/rows.test.ts`
Expected: FAIL — cannot resolve `./rows`.

- [ ] **Step 3: Write the pure merge lib**

```ts
// frontend/src/lib/publishctl/rows.ts
// PURE merge of captured factory assignments x the published manifest -> the rows
// the operator Publish control renders. No fetch, no React (headless-tested).

export interface AssignmentLike { seed_ref?: string; pipeline?: string; status?: string; }
export interface PublishedManifestLike {
  chapters?: Record<string, { chapter?: string; title?: string;
    artifacts?: Array<{ lane?: string }> }>;
}
export interface PublishRow {
  chapter: string;
  title: string;
  capturedLanes: string[];   // lanes captured-and-publishable (textbook seeds)
  publishedLanes: string[];  // lanes currently in the published manifest
}

const _TEXTBOOK = "textbook:";

export function publishRows(
  assignments: AssignmentLike[] | null | undefined,
  manifest: PublishedManifestLike | null | undefined,
): PublishRow[] {
  const captured = new Map<string, Set<string>>();
  for (const a of assignments ?? []) {
    if (a?.status !== "captured") continue;
    const ref = a?.seed_ref ?? "";
    if (!ref.startsWith(_TEXTBOOK)) continue;
    const chapter = ref.slice(_TEXTBOOK.length);
    const lane = a?.pipeline;
    if (!chapter || !lane) continue;
    (captured.get(chapter) ?? captured.set(chapter, new Set()).get(chapter)!).add(lane);
  }
  const chapters = manifest?.chapters ?? {};
  const rows: PublishRow[] = [];
  for (const [chapter, lanes] of captured) {
    const m = chapters[chapter];
    const publishedLanes = (m?.artifacts ?? [])
      .map((x) => x?.lane).filter((l): l is string => !!l).sort();
    rows.push({
      chapter,
      title: m?.title ?? chapter,
      capturedLanes: [...lanes].sort(),
      publishedLanes,
    });
  }
  rows.sort((a, b) => a.chapter.localeCompare(b.chapter));
  return rows;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/lib/publishctl/rows.test.ts`
Expected: PASS (4 passed).

- [ ] **Step 5: Write the failing Publish-app test**

```tsx
// frontend/src/apps/Publish/index.test.tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import Publish from "./index";

vi.mock("../../hooks/useApi", () => ({
  useApi: (path: string) =>
    path.startsWith("/api/assignments")
      ? { data: [{ seed_ref: "textbook:circular-motion", pipeline: "revision", status: "captured" }],
          loading: false, error: null }
      : { data: { chapters: {} }, loading: false, error: null },
}));
const post = vi.fn().mockResolvedValue({ ok: true, result: { published: ["revision"] } });
vi.mock("../../hooks/useApiPost", () => ({ useApiPost: () => ({ post, loading: false, error: null }) }));

afterEach(() => vi.clearAllMocks());

describe("Publish operator control (G3)", () => {
  it("lists captured chapters with a publish action", async () => {
    render(<Publish />);
    expect(await screen.findByText(/circular-motion/i)).toBeTruthy();
  });

  it("publishes a chapter via POST /api/factory/publish", async () => {
    render(<Publish />);
    fireEvent.click(await screen.findByTestId("publish-circular-motion"));
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/api/factory/publish", { chapter: "circular-motion" }));
  });
});
```

- [ ] **Step 6: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/apps/Publish/index.test.tsx`
Expected: FAIL — cannot resolve `./index`.

- [ ] **Step 7: Write the Publish app**

```tsx
// frontend/src/apps/Publish/index.tsx
// G3 minimal operator Publish control: list captured textbook chapters (with which
// lanes are captured + which are already published) and publish / unpublish each
// through the OWNER-GATED POST /api/factory/publish|unpublish. The CLI remains the
// power path; this is the thin GUI sibling.
import { useState } from "react";
import { useApi } from "../../hooks/useApi";
import { useApiPost } from "../../hooks/useApiPost";
import { publishRows, type AssignmentLike, type PublishedManifestLike } from "../../lib/publishctl/rows";

export default function Publish() {
  const [nonce, setNonce] = useState(0);
  // useApi refetches when the path changes -> a cache-busting nonce reloads both
  // sources after a publish/unpublish.
  const asg = useApi<AssignmentLike[]>(`/api/assignments?_=${nonce}`);
  const man = useApi<PublishedManifestLike>(`/api/published?_=${nonce}`);
  const { post, error } = useApiPost<{ ok: boolean }>();
  const rows = publishRows(asg.data, man.data);

  async function act(path: string, chapter: string) {
    const r = await post(path, { chapter });
    if (r) setNonce((n) => n + 1);
  }

  return (
    <div style={{ padding: 16, font: "14px 'Inter', system-ui, sans-serif", color: "#1c1c28" }}>
      <h2 style={{ margin: "0 0 4px" }}>Publish</h2>
      <p style={{ color: "#6b7280", marginTop: 0 }}>
        Release captured chapters to the public <code>/learn</code> corpus. Owner-gated; never automated.
      </p>
      {error ? <p role="alert" style={{ color: "#b91c1c" }}>{error}</p> : null}
      {rows.length === 0 ? (
        <p data-testid="publish-empty" style={{ color: "#6b7280" }}>
          No captured chapters yet — build a chapter through the factory first.
        </p>
      ) : (
        <table style={{ borderCollapse: "collapse", width: "100%" }}>
          <thead>
            <tr style={{ textAlign: "left", borderBottom: "1px solid #e6e6ef" }}>
              <th style={{ padding: "6px 8px" }}>Chapter</th>
              <th style={{ padding: "6px 8px" }}>Captured</th>
              <th style={{ padding: "6px 8px" }}>Published</th>
              <th style={{ padding: "6px 8px" }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.chapter} style={{ borderBottom: "1px solid #f1f1f6" }}>
                <td style={{ padding: "6px 8px" }}>{r.title}</td>
                <td style={{ padding: "6px 8px", color: "#6b7280" }}>{r.capturedLanes.join(", ")}</td>
                <td style={{ padding: "6px 8px", color: "#16a34a" }}>
                  {r.publishedLanes.length ? r.publishedLanes.join(", ") : "—"}
                </td>
                <td style={{ padding: "6px 8px", display: "flex", gap: 6 }}>
                  <button data-testid={`publish-${r.chapter}`}
                    onClick={() => act("/api/factory/publish", r.chapter)}
                    style={{ border: 0, background: "#16a34a", color: "#fff", borderRadius: 6,
                      padding: "5px 10px", cursor: "pointer" }}>
                    Publish all captured
                  </button>
                  {r.publishedLanes.length ? (
                    <button data-testid={`unpublish-${r.chapter}`}
                      onClick={() => act("/api/factory/unpublish", r.chapter)}
                      style={{ border: "1px solid #e6e6ef", background: "#fff", color: "#1c1c28",
                        borderRadius: 6, padding: "5px 10px", cursor: "pointer" }}>
                      Unpublish
                    </button>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
```

- [ ] **Step 8: Wire the app into the registry**

(a) `frontend/src/types/contracts.ts` — extend the `AppId` union (the last member is `"atlas"`):

```ts
  | "settings" | "terminal" | "clock" | "notes" | "snake" | "atlas" | "publish";
```

(b) `frontend/src/registry.ts` — add to `APPS` (after the `atlas` entry):

```ts
  publish: { id: "publish", name: "Publish", accent: "#16a34a", w: 900, h: 600 },
```

and append `"publish"` to the end of the `ORDER` array:

```ts
export const ORDER: AppId[] = [
  "dashboard", "pipelines", "assignments", "org", "questions", "lectures", "booklets",
  "insp", "sims", "mycontentdev", "munshi", "notes", "clock", "terminal", "snake",
  "activity", "settings", "atlas", "publish",
];
```

(c) `frontend/src/App.tsx` — add to `APP_DIR` (after `atlas: "Atlas",`):

```ts
  publish: "Publish",
```

(d) `frontend/src/components/icons-data.ts` — add a `publish` entry to `ICONS` (after the `atlas` entry; an upload-to-tray glyph in the existing pipe-delimited path format):

```ts
  publish:
    "M12 3v11|M8 7l4-4 4 4|M5 15v4a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-4",
```

- [ ] **Step 9: Update `registry.test.ts` for the new app**

In `frontend/src/registry.test.ts`:

- change `expect(Object.keys(APPS)).toHaveLength(18);` to `toHaveLength(19);`
- change the `ORDER` expectation to include `"publish"` at the end:

```ts
    expect(ORDER).toEqual([
      "dashboard", "pipelines", "assignments", "org", "questions", "lectures", "booklets",
      "insp", "sims", "mycontentdev", "munshi", "notes", "clock", "terminal", "snake",
      "activity", "settings", "atlas", "publish",
    ]);
```

- add a registration test after the Atlas one:

```ts
describe("Publish registration", () => {
  it("registers the publish app and includes it in ORDER", () => {
    expect(APPS.publish).toMatchObject({ id: "publish", name: "Publish" });
    expect(ORDER).toContain("publish");
  });
});
```

- [ ] **Step 10: Run the tests to verify they pass**

Run: `cd frontend && npx vitest run src/apps/Publish/index.test.tsx src/lib/publishctl/rows.test.ts src/registry.test.ts`
Expected: PASS. Then `cd frontend && npx tsc --noEmit` — expect no type errors (every total `Record<AppId,…>` now has a `publish` key). If `tsc` reports another missing `Record<AppId,…>` key, grep `Record<AppId` and add it.

- [ ] **Step 11: Commit**

```bash
git add frontend/src/lib/publishctl frontend/src/apps/Publish frontend/src/types/contracts.ts frontend/src/registry.ts frontend/src/registry.test.ts frontend/src/App.tsx frontend/src/components/icons-data.ts
git commit -m "feat(g3): minimal operator Publish control + registry wiring"
```

---

## Task 12: Full verification gate + docs/trackers

**Files:**
- Modify: `STATUS.html`, `HANDOFF.md`, `SUMMARY.html` (the live trackers — NOT the superseded `SAMAGRA-HANDOFF.md`), `CLAUDE.md` G-status block — end-of-slice updates.

- [ ] **Step 1: Run the full backend suite**

Run: `python -m pytest -q`
Expected: all green except the lone pre-existing env `test_gdocs` red and the opt-in live-LLM-smoke skip (≈+35 over the 562 baseline). If any NEW failure, fix before proceeding.

- [ ] **Step 2: Run the full frontend suite + typecheck + build**

Run: `cd frontend && npx vitest run` then `npx tsc --noEmit` then `npm run build`
Expected: vitest green (≈+20 over the 583 baseline), no type errors, build succeeds.

- [ ] **Step 3: Update the project status docs**

Update `STATUS.html` (the global-doc-preference single-file format) and the trackers with the G3 entry: what shipped (the two write boundaries), the proposed DEC-12, the test deltas, and the ⚠ owner follow-ups: (a) `pratham.db` is gitignored — created on first `samagra pratham enroll`; (b) set `SAMAGRA_PRATHAM_COOKIE_SECURE=0` for local http dev; (c) public exposure of `/learn` + `/api/learn/*` is still the separate owner deploy step from G2; (d) the DEC-7-style Codex pre-merge review of both write boundaries is still owed (see review gate).

- [ ] **Step 4: Commit**

```bash
git add STATUS.html SAMAGRA-HANDOFF.md CLAUDE.md
git commit -m "docs(g3): status + trackers for the identity + publish-write slice"
```

- [ ] **Step 5: Review gate (do NOT merge before these)**

Per spec §10, before merging `feature/content-factory-phase-g3` to `main`:
1. A **dedicated DEC-7-style Codex pre-merge review** of BOTH write boundaries (owner publish + public student login) — the first inbound write + first public write. Save the report under `docs/codex-reviews/`.
2. An **adversarial multi-lens final review** (Workflow, 4 lenses × independent verify) — firewall (store isolation; no inward reach from the public path), security (no code/session leak; cookie flags; rate-limit honesty; publish stays owner-only + never-automated), spec-fidelity, separate-entity boundary.
3. Remediate findings TDD; re-run the full gate (Steps 1-2); then merge `--ff-only` and push.

---

## Self-Review

**1. Spec coverage** — every spec section maps to a task:
- §2 forks (scope/posture/auth/store/state-scope/surface) → Tasks 1-11 collectively (identity-optional reader Task 10; enrollment-codes Tasks 2-4,7; pratham.db Task 3; endpoint+UI Tasks 5,11).
- §5.1 store → Task 3; §5.2 identity → Task 2; §5.3 endpoints (publish owner-gated → Task 5; learn public → Task 6); §5.4 config → Task 1; §5.5 CLI → Task 7.
- §6.1 reader sign-in → Tasks 9-10; §6.2 operator control → Task 11.
- §8 security model → enforced/asserted across Tasks 2 (rate limiter, hashing), 3 (hashed at rest), 5 (owner gate, never-automated), 6 (public + identical 401 + cookie flags + rate key), 8 (isolation).
- §9 invariants & acceptance (DEC-12 + 3 golden threads) → Task 8 + the `is_protected`/public assertions in Tasks 5-6.
- §10 review gate → Task 12 Step 5. §11 testing strategy → the per-task tests. §12 non-goals — nothing in the plan introduces learning state, open registration, passwords, gating of `/learn`, JWT/signing secret, or governance migration (confirmed: Task 3 stamps its OWN `user_version` on `pratham.db`; no `_MIGRATIONS` edit to governance.store).

**2. Placeholder scan** — no TBD/TODO; every code step shows complete code; every command has an expected result. The only "fill-in" is Task 12 Step 3 (status-doc prose), which is documentation, not code.

**3. Type consistency** — checked across tasks: `service.enroll` returns `{id,name,code}` (Task 4) consumed by the CLI (Task 7) and tests; `service.login` returns `{id,name,_session_token}` consumed by `api_learn_login` (Task 6); `store` function names (`create_student`, `find_student_by_code_hash`, `get_student`, `set_status`, `touch_login`, `list_students`, `create_session`, `find_session`, `delete_session`, `delete_sessions_for_student`) are identical in Task 3's impl, Task 4's service, and the tests; `identity.hash_secret`/`new_code`/`new_session_token`/`session_expiry`/`is_expired`/`redeem_verdict`/`RateLimiter` names match across Tasks 2/4; frontend `Student` (Task 9) is imported by `session.ts` and the reader (Task 10); `publishRows`/`PublishRow`/`AssignmentLike`/`PublishedManifestLike` names match across Task 11's lib + app + tests; the cookie name `pratham_session` is identical in the endpoint (Task 6) and its test. `run.publish(chapter, *, lanes, actor)` matches the real G1 signature read from `factory/publish/run.py`.
