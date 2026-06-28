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
