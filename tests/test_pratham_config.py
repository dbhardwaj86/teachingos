# tests/test_pratham_config.py
from samagra import config
import samagra.config as _config

_DEFAULT_PRATHAM_DB = _config.PRATHAM_DB  # captured at import, before the autouse fixture repoints it
_DEFAULT_PRATHAM_COOKIE_SECURE = _config.PRATHAM_COOKIE_SECURE  # captured at import, before the autouse fixture flips it


def test_pratham_db_is_a_sibling_durable_store():
    # Durable identity store, SEPARATE from the inward governance ledger.
    assert _DEFAULT_PRATHAM_DB.name == "pratham.db"
    assert _DEFAULT_PRATHAM_DB.parent == _config.REPO_ROOT
    assert _DEFAULT_PRATHAM_DB != _config.GOVERNANCE_DB


def test_pratham_cookie_secure_defaults_true():
    # Prod is behind the HTTPS tunnel; Secure on by default, dev-overridable.
    assert _DEFAULT_PRATHAM_COOKIE_SECURE is True


def test_pratham_session_ttl_is_a_positive_int():
    assert isinstance(config.PRATHAM_SESSION_TTL_DAYS, int)
    assert config.PRATHAM_SESSION_TTL_DAYS > 0
