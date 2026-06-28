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
