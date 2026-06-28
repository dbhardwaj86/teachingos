"""W1.1 — origin fail-closed gate (defence-in-depth behind Cloudflare Access).

The public deploy fronts a `cloudflared` tunnel with Cloudflare Access, but the
FastAPI origin itself had no auth — Access was the *sole* gate over five mutating
POSTs (`/api/refresh`, `/api/tick`, `/api/gate/{pipeline}/{decision}`,
`/api/munshi/capture`, `/api/mcd/seeds`) plus two admin-keyed live reads
(`GET /api/munshi/library`, `GET /api/mcd/seeds`). The origin holds prod creds
server-side, so anyone who reaches `:8799` directly (a 0.0.0.0 bind, a LAN /
internet exposure, a second tunnel) needed no credential.

This module adds middleware that gates ONLY those routes and fails closed:

  * loopback (127.0.0.1/::1/localhost) always passes — that is BOTH the local dev
    path AND the cloudflared-origin path (cloudflared connects to localhost:8799,
    so legitimate Access traffic arrives from loopback). The defence this adds is
    therefore against requests whose TCP peer is *not* loopback (the misconfig /
    direct-exposure threat), which is exactly the HIGH.
  * the `SAMAGRA_DISABLE_ORIGIN_AUTH` flag is a dev escape hatch.
  * a remote request must carry a verified Cloudflare Access identity: a
    cryptographically valid `Cf-Access-Jwt-Assertion` (when SAMAGRA_ACCESS_AUD +
    SAMAGRA_ACCESS_TEAM_DOMAIN are configured), else — only as a documented,
    weaker interim — `Cf-Access-Authenticated-User-Email` == SAMAGRA_OWNER_EMAIL.
  * everything else is 403.

The interim email header is spoofable by anyone who can reach the origin, so it
is NOT honoured once real JWT validation is configured; it exists only so the
gate provides *some* value before the owner wires the Access AUD + team domain.
"""
from __future__ import annotations

import base64
import json
import time
from typing import Callable

from fastapi.responses import JSONResponse

from .. import config

# --- protected route table ---------------------------------------------
_PROTECTED_POSTS = frozenset({
    "/api/refresh", "/api/tick", "/api/munshi/capture", "/api/mcd/seeds",
    # G3: the owner publish write path — the GUI/network sibling of the G1 CLI
    # publish. Owner-gated (never-automated); delegates to the reviewed publish.run.
    "/api/factory/publish", "/api/factory/unpublish",
})
# review 27 MED-3: /api/search and /api/assignments serve the CACHED equivalents of
# the admin-keyed live reads (munshi payloads via the catalog; governance proposal
# notes), so they carry the same sensitive data and must be gated for consistency.
# Loopback (the cloudflared-origin path) always passes, so legit access is unaffected
# — this only blocks a direct non-loopback caller (the exposure threat model).
_PROTECTED_GETS = frozenset({
    "/api/munshi/library", "/api/mcd/seeds", "/api/search", "/api/assignments",
})


def is_protected(method: str, path: str) -> bool:
    """True for the five mutating POSTs + the admin-keyed live + cached reads."""
    method = (method or "").upper()
    if method == "POST":
        return path in _PROTECTED_POSTS or path.startswith("/api/gate/")
    if method == "GET":
        return path in _PROTECTED_GETS
    return False


_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


def is_loopback_host(host: str | None) -> bool:
    return host in _LOOPBACK_HOSTS


def _client_host(request) -> str | None:
    """The TCP peer host. Overridable in tests. Deliberately NOT derived from
    X-Forwarded-For / Cf-Connecting-Ip — those are caller-controlled headers and
    must never widen the loopback bypass."""
    return request.client.host if request.client else None


# --- Cloudflare Access JWT verification (full RS256 / JWKS path) --------
_JWKS_CACHE: dict[str, tuple[float, dict]] = {}
_JWKS_TTL = 3600  # seconds


def _b64url_decode(seg: str) -> bytes:
    pad = "=" * (-len(seg) % 4)
    return base64.urlsafe_b64decode(seg + pad)


def _decode_segment(seg: str) -> dict:
    return json.loads(_b64url_decode(seg))


def _jwk_to_public_key(jwk: dict):
    """Build an RSA public key from a JWK's base64url `n`/`e` (RS256 only)."""
    from cryptography.hazmat.primitives.asymmetric import rsa

    n = int.from_bytes(_b64url_decode(jwk["n"]), "big")
    e = int.from_bytes(_b64url_decode(jwk["e"]), "big")
    return rsa.RSAPublicNumbers(e, n).public_key()


def _load_jwks(team_domain: str) -> dict:
    """Fetch + cache the Access team JWKS as {kid: RSAPublicKey}.

    Network-backed; monkeypatched in tests. A fetch failure yields {} so the
    verifier fails closed (no key -> no valid token) rather than raising.
    """
    now = time.time()
    hit = _JWKS_CACHE.get(team_domain)
    if hit and now - hit[0] < _JWKS_TTL:
        return hit[1]
    keys: dict = {}
    try:
        import requests

        url = f"https://{team_domain}/cdn-cgi/access/certs"
        data = requests.get(url, timeout=10).json()
        for jwk in data.get("keys", []):
            kid = jwk.get("kid")
            if kid and jwk.get("kty") == "RSA":
                try:
                    keys[kid] = _jwk_to_public_key(jwk)
                except Exception:  # noqa: BLE001 — skip a malformed key
                    continue
    except Exception:  # noqa: BLE001 — network/parse failure -> fail closed
        keys = {}
    _JWKS_CACHE[team_domain] = (now, keys)
    return keys


def verify_access_jwt(token: str, *, aud: str, team_domain: str,
                      now: float | None = None, jwks: dict | None = None) -> bool:
    """Validate a Cloudflare Access JWT: RS256 signature against the team JWKS,
    audience == `aud`, issuer == https://<team_domain>, and not expired.

    Returns a plain bool and never raises — any malformed/forged token is False.
    """
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding

    if not token or token.count(".") != 2:
        return False
    try:
        h_seg, p_seg, s_seg = token.split(".")
        header = _decode_segment(h_seg)
        payload = _decode_segment(p_seg)
    except Exception:  # noqa: BLE001
        return False

    if header.get("alg") != "RS256":  # block 'none'/HS256 downgrade
        return False
    if jwks is None:
        jwks = _load_jwks(team_domain)
    pub = jwks.get(header.get("kid"))
    if pub is None:
        return False

    try:
        sig = _b64url_decode(s_seg)
        pub.verify(sig, f"{h_seg}.{p_seg}".encode(),
                   padding.PKCS1v15(), hashes.SHA256())
    except Exception:  # noqa: BLE001 — InvalidSignature or malformed segment
        return False

    aud_claim = payload.get("aud")
    auds = aud_claim if isinstance(aud_claim, list) else [aud_claim]
    if aud not in auds:
        return False
    if payload.get("iss") != f"https://{team_domain}":
        return False
    exp = payload.get("exp")
    if not isinstance(exp, (int, float)) or exp <= (now if now is not None else time.time()):
        return False
    return True


# --- policy -------------------------------------------------------------
def has_valid_identity(request) -> bool:
    """A remote request carries a verified Access identity.

    Prefers full JWT validation when configured; falls back to the (weaker,
    documented) owner-email header only when JWT validation is NOT configured.
    """
    aud = config.ACCESS_AUD
    team = config.ACCESS_TEAM_DOMAIN
    if aud and team:
        token = request.headers.get("Cf-Access-Jwt-Assertion", "")
        return verify_access_jwt(token, aud=aud, team_domain=team)
    owner = config.OWNER_EMAIL
    if owner:
        email = request.headers.get("Cf-Access-Authenticated-User-Email", "")
        return bool(email) and email == owner
    return False


def allow_request(request) -> bool:
    if not is_protected(request.method, request.url.path):
        return True
    if config.DISABLE_ORIGIN_AUTH:
        return True
    if is_loopback_host(_client_host(request)):
        return True
    return has_valid_identity(request)


async def enforce(request, call_next: Callable):
    if allow_request(request):
        return await call_next(request)
    return JSONResponse({"detail": "origin authentication required"}, status_code=403)
