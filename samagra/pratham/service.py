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
