"""Reverse-proxy core for the 3 read-only corpus daemons (F4/F5/F7/F3).

`CorpusProxy` proxies the native web UI of a corpus's own localhost daemon
(GN Brain :8931, Corpus Brain :8137, Lecture Brain :8000) behind SAMAGRA's
ORIGIN-GATED `/api/corpus/<name>/serve/{path}` endpoint. It is deliberately
narrow:

  * GET-only — every other verb is refused structurally (the lecturepdf write
    endpoints are unreachable).
  * exact POSITIVE per-corpus allowlist (F4) — no broad `^/api/` prefix-allow;
    the request path is NORMALIZED first (single URL-decode, collapse `//`,
    reject any backslash, reject any post-decode `..`/`.` segment, reject `:`
    absolute-URL smuggling) and only then matched.
  * onedpull answer-bearing endpoint families are OFF the allowlist (F3) AND a
    defense-in-depth body-scan refuses any proxied onedpull response carrying
    an answer/solution marker.
  * SSRF guard: the daemon base URL must be loopback (or an explicitly opted-in
    host) — validated at construction (the qx_guard pattern).
  * response-size cap + timeout (F7); daemon-down/over-cap/timeout return a
    graceful JSON error body, never an unbounded read, a hang, or a 500 wedge.
  * the HTML shell gets `<base href="/api/corpus/<name>/serve/">` injected plus
    an enumerated absolute-prefix rewrite (F5) so the fetch-driven pages
    resolve under the gated same-origin serve prefix.

READ-ONLY by construction: nothing here writes to any corpus root, any SAMAGRA
store, governance, or pratham.
"""
from __future__ import annotations

import json
import re
import time
import urllib.request
from urllib.parse import unquote, urlparse

_SEG = r"[A-Za-z0-9][A-Za-z0-9._-]*"

# Exact positive allowlists (F4) — GET-only upstream paths per corpus. The
# onedpull answer families (/api/questions, /api/question/<id>, /api/coverage,
# /api/similar/<id>) are deliberately ABSENT (F3); the lecturepdf write /
# compositions / key-consuming families are deliberately ABSENT.
_ALLOWLISTS: dict[str, tuple[str, ...]] = {
    "gnocr": (
        r"/", r"/api/stats", r"/api/search", r"/api/topics",
        rf"/preview/\d+/\d+\.png", rf"/gn-assets/\d+(/{_SEG})+",
        rf"/pdf/\d+", rf"/briefs/{_SEG}",
    ),
    "onedpull": (
        r"/", r"/api/stats", r"/api/search", r"/api/topics",
        rf"/preview/\d+/\d+\.png", rf"/pdf/\d+", rf"/extracted(/{_SEG})+",
    ),
    "lecturepdf": (
        r"/", rf"/static(/{_SEG})+", r"/api/health", r"/api/stats",
        r"/api/topics", r"/api/query_lexical", rf"/api/topic/{_SEG}",
        r"/api/examples", r"/api/lectures", r"/api/lecture",
        r"/api/lecture_overlap",
        rf"/api/diagrams/png/{_SEG}/{_SEG}/{_SEG}",
        rf"/api/diagrams/scene/{_SEG}/{_SEG}",
    ),
}

_COMPILED: dict[str, tuple[re.Pattern, ...]] = {
    name: tuple(re.compile(p + r"\Z") for p in pats)
    for name, pats in _ALLOWLISTS.items()
}

# F3 defense-in-depth body-scan markers for proxied onedpull responses. The
# structural set mirrors factory.dispatch._ANSWER_MARKERS + the onedpull JSON
# keys. The HTML shell (path "/") is the daemon's own STATIC app markup — it
# legitimately contains empty class="answer" containers and `x.solution_md`
# property accesses but carries no DATA, so it is scanned only for the
# data-key forms; every non-shell response gets the full set.
_ANSWER_MARKERS_DATA = ('"answer"', '"solution_md"', 'class="answer"',
                        "answer-label", "data-answer", "data-correct",
                        "pq-ans", "pkey")
_ANSWER_MARKERS_SHELL = ('"answer":', '"solution_md":')

_MEDIA_BY_EXT = {
    ".js": "application/javascript",
    ".mjs": "application/javascript",
    ".css": "text/css",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
    ".html": "text/html; charset=utf-8",
    ".htm": "text/html; charset=utf-8",
    ".json": "application/json",
    ".pdf": "application/pdf",
    ".md": "text/plain; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".map": "application/json",
}

# Absolute prefixes the corpus pages reference from JS/markup; rewritten to the
# gated serve prefix on the HTML shell (F5 — enumerated, derived from the real
# index bytes, not guessed).
_REWRITE_PREFIXES = ("/api/", "/preview/", "/pdf/", "/static/", "/gn-assets/",
                     "/briefs/", "/extracted/")

_LOOPBACK = frozenset({"127.0.0.1", "::1", "localhost"})

_DEFAULT_SIZE_CAP = 25 * 1024 * 1024  # 25 MB (F7)
_DEFAULT_TIMEOUT = 15.0               # seconds (F7)


class SizeCapExceeded(Exception):
    pass


def _validate_base_url(url: str, allowed_hosts: str = "") -> str:
    """Loopback-or-allowlist-only daemon base URL (the qx_guard SSRF pattern)."""
    parsed = urlparse(url or "")
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"corpus base URL must be http(s), got {parsed.scheme!r}")
    if parsed.username or parsed.password:
        # Credentialed sidecar URLs are refused outright: _error() echoes the
        # base URL in its hint, so userinfo would leak on daemon-down.
        raise ValueError(
            "corpus base URL must not carry userinfo (user:password@) — "
            "refusing (credential-leak guard)")
    host = (parsed.hostname or "").lower()
    extra = {h.strip().lower() for h in (allowed_hosts or "").split(",") if h.strip()}
    if host not in _LOOPBACK and host not in extra:
        raise ValueError(
            f"corpus base URL host {host!r} is not loopback and not opted in — "
            "refusing (SSRF guard)")
    return url.rstrip("/")


def _normalize(path: str) -> str | None:
    """Single-decode + collapse `//` + reject backslash / dot-segments / `:`.

    Returns the normalized absolute path, or None when the path must be
    refused. Runs BEFORE any allowlist match or upstream call (F4)."""
    if not isinstance(path, str) or "\\" in path:
        return None
    p = unquote(path)  # single decode only — a double-encoded `..` stays inert
    if "\\" in p or ":" in p:  # post-decode backslash / scheme smuggling
        return None
    if not p.startswith("/"):
        p = "/" + p
    while "//" in p:
        p = p.replace("//", "/")
    for seg in p.split("/"):
        if seg in ("..", "."):
            return None
    return p


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """SSRF guard: NEVER follow an upstream redirect. Returning None makes
    urllib raise HTTPError on any 3xx, which serve() maps to the graceful
    503 'brain offline' path — a loopback daemon can't bounce the fetch to
    169.254.169.254 or a LAN host after the base-url check passed."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        return None


_NO_REDIRECT_OPENER = urllib.request.build_opener(_NoRedirect)


def _http_fetch(url: str, timeout: float, cap: int) -> tuple[int, str, bytes]:
    """Default transport: bounded read from the loopback daemon. Tests inject
    fakes; nothing in the standing suite hits the network.

    Redirects are structurally refused (_NoRedirect). The body is read in
    chunks under a HARD wall-clock deadline (the same `timeout` budget) so a
    slow-drip peer that stays under the per-recv socket timeout still can't
    tie the worker up (Codex review: DoS via slow-drip body)."""
    req = urllib.request.Request(url, method="GET")
    deadline = time.monotonic() + timeout
    with _NO_REDIRECT_OPENER.open(req, timeout=timeout) as resp:  # noqa: S310 — loopback-validated
        # Belt-and-suspenders: if a redirect somehow slipped through, the
        # final URL's host must match the one we validated at construction.
        final_host = (urlparse(resp.geturl() or url).hostname or "").lower()
        want_host = (urlparse(url).hostname or "").lower()
        if final_host != want_host:
            raise ValueError(
                f"upstream redirected off-host to {final_host!r} — refused")
        read1 = getattr(resp, "read1", resp.read)
        chunks: list[bytes] = []
        total = 0
        while True:
            if time.monotonic() > deadline:
                raise TimeoutError("upstream body read exceeded total deadline")
            chunk = read1(min(65536, cap + 1 - total))
            if not chunk:
                break
            total += len(chunk)
            if total > cap:
                raise SizeCapExceeded(f"upstream response exceeds {cap} bytes")
            chunks.append(chunk)
        ctype = resp.headers.get("Content-Type", "") or ""
        return resp.status, ctype, b"".join(chunks)


def _error(status: int, message: str, corpus: str, base_url: str) -> tuple[int, str, bytes]:
    body = json.dumps({
        "error": message, "corpus": corpus,
        "hint": f"brain offline? start the {corpus} sidecar at {base_url}",
    }).encode("utf-8")
    return status, "application/json", body


class CorpusProxy:
    """GET-only, allowlisted, size/timeout-bounded reverse proxy (see module
    docstring). `fetch` is the injectable transport seam:
    fetch(url, timeout, cap) -> (status, content_type, body_bytes)."""

    def __init__(self, name: str, base_url: str, *, allowed_hosts: str = "",
                 size_cap: int = _DEFAULT_SIZE_CAP,
                 timeout: float = _DEFAULT_TIMEOUT, fetch=None) -> None:
        if name not in _ALLOWLISTS:
            raise ValueError(f"unknown corpus {name!r}")
        self.name = name
        self.base_url = _validate_base_url(base_url, allowed_hosts)
        self.size_cap = int(size_cap)
        self.timeout = float(timeout)
        self._fetch = fetch

    # -- helpers ----------------------------------------------------------
    def _allowed(self, norm: str) -> bool:
        return any(pat.match(norm) for pat in _COMPILED[self.name])

    def _serve_prefix(self) -> str:
        return f"/api/corpus/{self.name}/serve/"

    def _rewrite_html(self, body: bytes) -> bytes:
        prefix = self._serve_prefix().encode()
        # 1) enumerated absolute-prefix rewrite FIRST (so the injected <base>
        #    tag's own "/api/ is never re-rewritten)
        for quote in (b'"', b"'"):
            for pre in _REWRITE_PREFIXES:
                lit = quote + pre.encode()
                repl = quote + prefix + pre.encode()[1:]
                body = body.replace(lit, repl)
        # 2) inject <base href> right after <head> so every RELATIVE URL the
        #    page issues resolves under the gated serve prefix
        base_tag = b'<base href="' + prefix + b'">'
        low = body.lower()
        i = low.find(b"<head>")
        if i != -1:
            return body[:i + 6] + base_tag + body[i + 6:]
        return base_tag + body

    def _rewrite_js(self, body: bytes) -> bytes:
        """F-2: the corpus SPAs fetch from JS modules, not only the HTML shell —
        apply the SAME enumerated absolute-prefix rewrite to JavaScript bodies
        (no <base> injection; that is HTML-only). Decode utf-8 replace-safe,
        rewrite, re-encode; only ever called on application/javascript media so
        non-text bodies are untouched."""
        prefix = self._serve_prefix()
        text = body.decode("utf-8", errors="replace")
        for quote in ('"', "'"):
            for pre in _REWRITE_PREFIXES:
                text = text.replace(quote + pre, quote + prefix + pre[1:])
        return text.encode("utf-8")

    def _scan_answers(self, norm: str, body: bytes) -> bool:
        """True when a proxied onedpull body carries an answer/solution marker."""
        if self.name != "onedpull":
            return False
        text = body.decode("utf-8", errors="replace").lower()
        markers = _ANSWER_MARKERS_SHELL if norm == "/" else _ANSWER_MARKERS_DATA
        return any(m in text for m in markers)

    def _media_type(self, norm: str, upstream_ctype: str) -> str:
        if norm == "/" or norm.endswith("/"):
            return "text/html; charset=utf-8"
        dot = norm.rfind(".")
        if dot != -1:
            ext = norm[dot:].lower()
            if ext in _MEDIA_BY_EXT:
                return _MEDIA_BY_EXT[ext]
        if upstream_ctype:
            return upstream_ctype
        return "application/json" if norm.startswith("/api/") else "application/octet-stream"

    # -- the one entry point ----------------------------------------------
    def serve(self, path: str, *, method: str = "GET",
              query: str = "") -> tuple[int, str, bytes]:
        """Proxy one request. Returns (status, media_type, body). Never raises
        for daemon-down/timeout/over-cap — a graceful JSON error body instead
        (never a wedge)."""
        if (method or "").upper() != "GET":
            return 403, "application/json", b'{"error": "GET only"}'
        norm = _normalize(path)
        if norm is None or not self._allowed(norm):
            return 403, "application/json", b'{"error": "path not allowed"}'
        url = self.base_url + norm
        if query:
            url += "?" + query
        fetch = self._fetch if self._fetch is not None else _http_fetch
        try:
            status, ctype, body = fetch(url, self.timeout, self.size_cap)
        except SizeCapExceeded:
            return _error(503, "upstream response too large", self.name, self.base_url)
        except Exception:  # noqa: BLE001 — daemon down / timeout / refused
            return _error(503, "corpus daemon offline or unreachable",
                          self.name, self.base_url)
        if 300 <= status < 400:
            # SSRF guard: a redirect from ANY transport is refused — never
            # followed, never surfaced (its Location/body could point off-host).
            return _error(503, "upstream redirect refused", self.name, self.base_url)
        if len(body) > self.size_cap:
            return _error(503, "upstream response too large", self.name, self.base_url)
        if self._scan_answers(norm, body):
            # F3: refuse, and never echo the offending payload
            return 403, "application/json", (
                b'{"error": "response carries an answer/solution marker - refused"}')
        media = self._media_type(norm, ctype)
        if norm == "/" and media.startswith("text/html"):
            body = self._rewrite_html(body)
        elif media.startswith("application/javascript"):
            body = self._rewrite_js(body)
        return status, media, body


def get_proxy(name: str, *, fetch=None) -> CorpusProxy:
    """Build the per-corpus proxy from config (read at call time so tests can
    monkeypatch the *_SERVER_URL values)."""
    from .. import config

    table = {
        "gnocr": (config.GNOCR_SERVER_URL, config.GNOCR_SERVER_ALLOWED_HOSTS),
        "onedpull": (config.ONEDPULL_SERVER_URL, config.ONEDPULL_SERVER_ALLOWED_HOSTS),
        "lecturepdf": (config.LECTUREPDF_SERVER_URL, config.LECTUREPDF_SERVER_ALLOWED_HOSTS),
    }
    if name not in table:
        raise ValueError(f"unknown corpus {name!r}")
    base_url, allowed = table[name]
    return CorpusProxy(name, base_url, allowed_hosts=allowed, fetch=fetch)
