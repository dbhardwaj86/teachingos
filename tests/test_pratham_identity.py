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
