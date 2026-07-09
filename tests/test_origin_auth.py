"""W1.1 — the FastAPI origin must fail closed (defence-in-depth behind Access).

The deploy puts Cloudflare Access in front of the tunnel, but the origin itself
had no auth: any caller reaching :8799 directly (a 0.0.0.0 bind, a LAN/internet
exposure, a second tunnel) could drive the five mutating POSTs + the two
admin-keyed live reads with no credential. This adds middleware that:

  * gates ONLY the protected routes (the 5 mutating POSTs + 2 admin reads),
  * always passes genuine loopback (the local dev + cloudflared-origin path) and
    a SAMAGRA_DISABLE_ORIGIN_AUTH dev escape hatch,
  * for remote requests, requires a verified Cloudflare Access identity — a
    cryptographically valid `Cf-Access-Jwt-Assertion` (when the Access AUD + team
    domain are configured) or, as the documented interim, the
    `Cf-Access-Authenticated-User-Email` header equal to the owner email,
  * 403s everything else.

The suite-wide conftest sets SAMAGRA_DISABLE_ORIGIN_AUTH (tests run as local
dev), so these tests flip it back OFF to exercise the real gate.
"""
from __future__ import annotations

import base64
import json
import time

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from fastapi.testclient import TestClient

from samagra import config
from samagra.api import app as api_app
from samagra.api import origin_auth


# --- pure helpers -------------------------------------------------------
def test_is_loopback_host_recognizes_local():
    assert origin_auth.is_loopback_host("127.0.0.1") is True
    assert origin_auth.is_loopback_host("::1") is True
    assert origin_auth.is_loopback_host("localhost") is True


def test_is_loopback_host_rejects_remote_and_unknown():
    assert origin_auth.is_loopback_host("10.0.0.5") is False
    assert origin_auth.is_loopback_host("0.0.0.0") is False
    assert origin_auth.is_loopback_host("testclient") is False
    assert origin_auth.is_loopback_host(None) is False


def test_is_protected_covers_five_posts_and_two_admin_reads():
    assert origin_auth.is_protected("POST", "/api/refresh") is True
    assert origin_auth.is_protected("POST", "/api/tick") is True
    assert origin_auth.is_protected("POST", "/api/gate/textbook/approve") is True
    assert origin_auth.is_protected("POST", "/api/munshi/capture") is True
    assert origin_auth.is_protected("POST", "/api/mcd/seeds") is True
    assert origin_auth.is_protected("GET", "/api/munshi/library") is True
    assert origin_auth.is_protected("GET", "/api/mcd/seeds") is True


def test_is_protected_covers_sensitive_cache_reads():
    # review 27 MED-3: the cached equivalents of the admin-keyed live reads carry the
    # same sensitive data — munshi payloads via /api/search, governance proposal
    # notes via /api/assignments — so the origin gate must cover them too. (Legit
    # traffic arrives via the loopback tunnel and always passes; this only blocks a
    # direct non-loopback caller.)
    assert origin_auth.is_protected("GET", "/api/search") is True
    assert origin_auth.is_protected("GET", "/api/assignments") is True


def test_is_protected_leaves_reads_and_spa_open():
    assert origin_auth.is_protected("GET", "/api/overview") is False
    assert origin_auth.is_protected("GET", "/api/questions") is False
    assert origin_auth.is_protected("GET", "/api/sims") is False
    assert origin_auth.is_protected("GET", "/") is False
    # a read on a write-path verb-mismatch is not protected
    assert origin_auth.is_protected("GET", "/api/refresh") is False


# --- JWT verification (full RS256 / JWKS path) --------------------------
def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _mint(payload: dict, key, *, kid: str = "k1", alg: str = "RS256") -> str:
    header = {"alg": alg, "kid": kid, "typ": "JWT"}
    h = _b64url(json.dumps(header).encode())
    p = _b64url(json.dumps(payload).encode())
    sig = key.sign(f"{h}.{p}".encode(), padding.PKCS1v15(), hashes.SHA256())
    return f"{h}.{p}.{_b64url(sig)}"


@pytest.fixture
def rsa_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _good_payload(team="acme.cloudflareaccess.com", aud="AUD123"):
    return {"aud": aud, "iss": f"https://{team}", "exp": int(time.time()) + 300,
            "email": "owner@example.com"}


def test_verify_access_jwt_accepts_valid_token(rsa_key):
    jwks = {"k1": rsa_key.public_key()}
    token = _mint(_good_payload(), rsa_key)
    assert origin_auth.verify_access_jwt(
        token, aud="AUD123", team_domain="acme.cloudflareaccess.com", jwks=jwks) is True


def test_verify_access_jwt_rejects_wrong_audience(rsa_key):
    jwks = {"k1": rsa_key.public_key()}
    token = _mint(_good_payload(aud="OTHER"), rsa_key)
    assert origin_auth.verify_access_jwt(
        token, aud="AUD123", team_domain="acme.cloudflareaccess.com", jwks=jwks) is False


def test_verify_access_jwt_rejects_expired(rsa_key):
    jwks = {"k1": rsa_key.public_key()}
    payload = _good_payload()
    payload["exp"] = int(time.time()) - 5
    token = _mint(payload, rsa_key)
    assert origin_auth.verify_access_jwt(
        token, aud="AUD123", team_domain="acme.cloudflareaccess.com", jwks=jwks) is False


def test_verify_access_jwt_rejects_bad_signature(rsa_key):
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwks = {"k1": other.public_key()}  # verify with the WRONG public key
    token = _mint(_good_payload(), rsa_key)
    assert origin_auth.verify_access_jwt(
        token, aud="AUD123", team_domain="acme.cloudflareaccess.com", jwks=jwks) is False


def test_verify_access_jwt_rejects_unknown_kid(rsa_key):
    jwks = {"other-kid": rsa_key.public_key()}
    token = _mint(_good_payload(), rsa_key, kid="k1")
    assert origin_auth.verify_access_jwt(
        token, aud="AUD123", team_domain="acme.cloudflareaccess.com", jwks=jwks) is False


def test_verify_access_jwt_rejects_non_rs256_alg(rsa_key):
    # 'none'/HS256 downgrade attempts must not pass the RS256 verifier.
    jwks = {"k1": rsa_key.public_key()}
    token = _mint(_good_payload(), rsa_key, alg="none")
    assert origin_auth.verify_access_jwt(
        token, aud="AUD123", team_domain="acme.cloudflareaccess.com", jwks=jwks) is False


# --- middleware policy (integration) ------------------------------------
@pytest.fixture
def gate_on(monkeypatch):
    """Turn the origin gate ON (conftest disables it suite-wide as 'local dev')."""
    monkeypatch.setattr(config, "DISABLE_ORIGIN_AUTH", False)
    monkeypatch.setattr(config, "ACCESS_AUD", None)
    monkeypatch.setattr(config, "ACCESS_TEAM_DOMAIN", None)
    monkeypatch.setattr(config, "OWNER_EMAIL", None)
    return monkeypatch


def _remote(monkeypatch, host="203.0.113.9"):
    monkeypatch.setattr(origin_auth, "_client_host", lambda req: host)


def _loopback(monkeypatch):
    monkeypatch.setattr(origin_auth, "_client_host", lambda req: "127.0.0.1")


def test_remote_protected_post_without_identity_is_403(gate_on):
    _remote(gate_on)
    c = TestClient(api_app.app)
    # bad body would be a 400 from the handler; a 403 proves the gate blocked first.
    r = c.post("/api/munshi/capture", json={"kind": "todo"})
    assert r.status_code == 403


def test_remote_protected_get_without_identity_is_403(gate_on):
    _remote(gate_on)
    c = TestClient(api_app.app)
    r = c.get("/api/munshi/library")
    assert r.status_code == 403


def test_loopback_protected_request_passes_gate(gate_on):
    _loopback(gate_on)
    c = TestClient(api_app.app)
    # reaches the handler -> 400 (bad kind), NOT a 403 from the gate.
    r = c.post("/api/munshi/capture", json={"kind": "todo"})
    assert r.status_code == 400


def test_remote_with_owner_email_header_passes_interim(gate_on):
    gate_on.setattr(config, "OWNER_EMAIL", "owner@example.com")
    _remote(gate_on)
    c = TestClient(api_app.app)
    r = c.post("/api/munshi/capture", json={"kind": "todo"},
               headers={"Cf-Access-Authenticated-User-Email": "owner@example.com"})
    assert r.status_code == 400  # reached the handler


def test_remote_with_wrong_email_header_is_403(gate_on):
    gate_on.setattr(config, "OWNER_EMAIL", "owner@example.com")
    _remote(gate_on)
    c = TestClient(api_app.app)
    r = c.post("/api/munshi/capture", json={"kind": "todo"},
               headers={"Cf-Access-Authenticated-User-Email": "attacker@evil.com"})
    assert r.status_code == 403


def test_remote_unprotected_read_is_always_open(gate_on):
    _remote(gate_on)
    c = TestClient(api_app.app)
    # /api/overview is a public read — the gate must not touch it.
    assert c.get("/api/overview").status_code == 200


def test_disable_flag_bypasses_gate_for_remote(gate_on):
    gate_on.setattr(config, "DISABLE_ORIGIN_AUTH", True)
    _remote(gate_on)
    c = TestClient(api_app.app)
    r = c.post("/api/munshi/capture", json={"kind": "todo"})
    assert r.status_code == 400  # gate disabled -> reaches handler


def test_remote_with_valid_jwt_passes(gate_on, rsa_key):
    gate_on.setattr(config, "ACCESS_AUD", "AUD123")
    gate_on.setattr(config, "ACCESS_TEAM_DOMAIN", "acme.cloudflareaccess.com")
    gate_on.setattr(origin_auth, "_load_jwks", lambda team: {"k1": rsa_key.public_key()})
    _remote(gate_on)
    token = _mint(_good_payload(), rsa_key)
    c = TestClient(api_app.app)
    r = c.post("/api/munshi/capture", json={"kind": "todo"},
               headers={"Cf-Access-Jwt-Assertion": token})
    assert r.status_code == 400  # reached the handler


def test_remote_with_invalid_jwt_is_403(gate_on, rsa_key):
    gate_on.setattr(config, "ACCESS_AUD", "AUD123")
    gate_on.setattr(config, "ACCESS_TEAM_DOMAIN", "acme.cloudflareaccess.com")
    gate_on.setattr(origin_auth, "_load_jwks", lambda team: {"k1": rsa_key.public_key()})
    _remote(gate_on)
    # a token signed by a different key must be rejected even with the right kid.
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = _mint(_good_payload(), other)
    c = TestClient(api_app.app)
    r = c.post("/api/munshi/capture", json={"kind": "todo"},
               headers={"Cf-Access-Jwt-Assertion": token})
    assert r.status_code == 403


def test_jwt_config_present_ignores_spoofable_email_header(gate_on, rsa_key):
    # When real JWT validation is configured, the cheap email header is NOT a
    # fallback — a spoofed email with no valid JWT must still 403.
    gate_on.setattr(config, "ACCESS_AUD", "AUD123")
    gate_on.setattr(config, "ACCESS_TEAM_DOMAIN", "acme.cloudflareaccess.com")
    gate_on.setattr(config, "OWNER_EMAIL", "owner@example.com")
    gate_on.setattr(origin_auth, "_load_jwks", lambda team: {"k1": rsa_key.public_key()})
    _remote(gate_on)
    c = TestClient(api_app.app)
    r = c.post("/api/munshi/capture", json={"kind": "todo"},
               headers={"Cf-Access-Authenticated-User-Email": "owner@example.com"})
    assert r.status_code == 403


# --- G5: the factory-run HTTP recipe (plan/approve-seed/build) ----------
def test_factory_run_endpoints_are_in_protected_posts():
    assert origin_auth.is_protected("POST", "/api/factory/plan") is True
    assert origin_auth.is_protected("POST", "/api/factory/approve-seed") is True
    assert origin_auth.is_protected("POST", "/api/factory/build") is True


def test_protected_posts_count_is_nine():
    # Documents the growth 6 -> 9 this slice makes (spec §4); a future slice bumping
    # this further should update the count deliberately, not by accident.
    assert len(origin_auth._PROTECTED_POSTS) == 9


# --- /api/corpus/ GET prefix branch (F2, desktop-icons-corpus-apps slice) ---
def test_is_protected_gets_corpus_prefix_branch():
    # the whole /api/corpus/ namespace is gated by ONE startswith branch
    assert origin_auth.is_protected("GET", "/api/corpus/x") is True
    assert origin_auth.is_protected("GET", "/api/corpus/gnocr") is True
    assert origin_auth.is_protected("GET", "/api/corpus/onedpull/serve/api/stats") is True
    # no regression to the existing exact-match set / public reads
    assert origin_auth.is_protected("GET", "/api/coverage") is False
    assert origin_auth.is_protected("GET", "/api/published") is False
    assert origin_auth.is_protected("GET", "/api/corpusless") is False  # prefix, not substring
