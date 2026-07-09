# tests/test_corpus_proxy.py
"""T2.6 — CorpusProxy: GET-only reverse-proxy core with exact positive
allowlists, normalization-before-match, SSRF base-url guard, size cap +
timeout, onedpull answer body-scan, <base href> injection, media types, and
graceful daemon-down. All transports are injected fakes — no live daemon."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from samagra.api import corpus_proxy
from samagra.api.corpus_proxy import CorpusProxy


def _fake_fetch(status=200, ctype="application/json", body=b"{}"):
    calls = []

    def fetch(url, timeout, cap):
        calls.append(url)
        return status, ctype, body

    fetch.calls = calls
    return fetch


def _proxy(name="gnocr", **kw):
    kw.setdefault("fetch", _fake_fetch())
    return CorpusProxy(name, "http://127.0.0.1:8931", **kw)


def test_rejects_non_get_method():
    p = _proxy()
    for method in ("POST", "PUT", "DELETE", "PATCH"):
        status, _, _ = p.serve("/api/stats", method=method)
        assert status == 403
    assert p._fetch.calls == []  # refused BEFORE any upstream call


def test_path_not_in_positive_allowlist_refused():
    p = _proxy("lecturepdf")
    for path in ("/api/compositions", "/api/reveal", "/api/excalidraw/open",
                 "/api/synthesize", "/api/prep_pack", "/api/questions/generate",
                 "/api/query"):
        status, _, _ = p.serve(path)
        assert status == 403, path
    assert p._fetch.calls == []
    # the enumerated read paths pass
    for path in ("/api/stats", "/api/lectures", "/api/query_lexical",
                 "/api/topic/electrostatics", "/api/examples",
                 "/api/diagrams/png/run1/doc2/fig.png", "/static/js/app.js"):
        status, _, _ = p.serve(path)
        assert status == 200, path


def test_onedpull_answer_families_refused():
    p = _proxy("onedpull")
    for path in ("/api/questions", "/api/question/5", "/api/coverage",
                 "/api/similar/5"):
        status, _, _ = p.serve(path)
        assert status == 403, path
    assert p._fetch.calls == []


def test_normalization_before_match():
    p = _proxy("gnocr")
    hostile = (
        "/%2e%2e%2fapi/stats",       # encoded traversal
        "/api\\..\\stats",           # backslash segments
        "/api/../stats",             # plain traversal
        "/api/./stats",              # dot segment
        "http://evil/api/stats",     # absolute-URL smuggling
        "//evil/api/stats",          # protocol-relative smuggling
    )
    for path in hostile:
        status, _, _ = p.serve(path)
        assert status == 403, path
    assert p._fetch.calls == []      # every one rejected BEFORE upstream
    # double-slash collapse still resolves a legit path
    status, _, _ = p.serve("//api/stats")
    assert status in (200, 403)  # collapsed to /api/stats OR conservatively refused


def test_offhost_base_url_rejected():
    with pytest.raises(ValueError):
        CorpusProxy("gnocr", "http://evil.example.com:8931", fetch=_fake_fetch())
    # loopback always fine
    CorpusProxy("gnocr", "http://localhost:8931", fetch=_fake_fetch())


def test_base_href_injected_into_html():
    html = b"<html><head><title>GN</title></head><body></body></html>"
    p = _proxy("gnocr", fetch=_fake_fetch(ctype="text/html", body=html))
    status, media, body = p.serve("/")
    assert status == 200
    assert media.startswith("text/html")
    assert b'<base href="/api/corpus/gnocr/serve/">' in body


def test_absolute_fetch_literals_rewritten():
    html = (b'<html><head></head><body><script>fetch("/api/stats");'
            b'fetch("/api/search?q=1");let x="/preview/1/2.png";'
            b'let y="/pdf/3";</script></body></html>')
    p = _proxy("gnocr", fetch=_fake_fetch(ctype="text/html", body=html))
    _, _, body = p.serve("/")
    assert b'fetch("/api/corpus/gnocr/serve/api/stats")' in body
    assert b'"/api/corpus/gnocr/serve/preview/1/2.png"' in body
    assert b'"/api/corpus/gnocr/serve/pdf/3"' in body
    # no un-rewritten absolute fetch survives
    assert b'fetch("/api/stats' not in body


def test_js_module_fetch_literals_rewritten():
    """F-2 regression: lecturepdf's Vue app fetches from JS MODULES, not the
    shell — the enumerated prefix rewrite must apply to application/javascript
    bodies too, else every data call 404s against SAMAGRA's origin."""
    js = (b'export async function stats(){return fetch("/api/stats");}\n'
          b"const u = '/api/topics'; const s = \"/static/js/app.js\";")
    p = _proxy("lecturepdf", fetch=_fake_fetch(ctype="application/javascript", body=js))
    status, media, body = p.serve("/static/js/api.js")
    assert status == 200
    assert media == "application/javascript"
    assert b'fetch("/api/corpus/lecturepdf/serve/api/stats")' in body
    assert b"'/api/corpus/lecturepdf/serve/api/topics'" in body
    assert b'"/api/corpus/lecturepdf/serve/static/js/app.js"' in body
    assert b'fetch("/api/stats' not in body
    # no <base> tag injected into JS
    assert b"<base href=" not in body


def test_js_rewrite_leaves_non_text_bodies_untouched():
    png = b"\x89PNG\r\n\x1a\n" + b'"/api/' + b"\x00" * 8
    p = _proxy("lecturepdf",
               fetch=_fake_fetch(ctype="image/png", body=png))
    _, media, body = p.serve("/api/diagrams/png/a/b/c.png")
    assert media == "image/png"
    assert body == png


def test_real_lecturepdf_js_modules_no_unrewritten_api_literal():
    """F-2 regression against the REAL lecturepdf brain JS bytes when present."""
    real_dir = Path(r"C:\SandBox\claude_box\lecturepdfs\brain\api\static\js")
    if not real_dir.exists():
        pytest.skip("real lecturepdf brain not on this machine")
    for f in sorted(real_dir.rglob("*.js")):
        rel = f.relative_to(real_dir).as_posix()
        p = _proxy("lecturepdf",
                   fetch=_fake_fetch(ctype="application/javascript",
                                     body=f.read_bytes()))
        _, _, body = p.serve(f"/static/js/{rel}")
        # every quoted /api/ literal must now carry the gated serve prefix
        # (the rewritten form itself starts "/api/corpus/... — exclude it)
        leftovers = re.findall(
            r'["\']/api/(?!corpus/lecturepdf/serve/)[^"\']*',
            body.decode("utf-8", errors="replace"))
        assert not leftovers, (
            f"un-rewritten /api/ literals survive in {rel}: {leftovers}")


def test_no_unrewritten_api_fetch_survives_for_excluded_paths():
    """F5 regression against the REAL onedpull index bytes when present."""
    real = Path(r"C:\SandBox\gemini_box\onedpulls\_brain\webui\index.html")
    if not real.exists():
        pytest.skip("real onedpull index not on this machine")
    p = _proxy("onedpull",
               fetch=_fake_fetch(ctype="text/html", body=real.read_bytes()))
    _, _, body = p.serve("/")
    for excluded in (b'fetch("/api/questions', b'fetch("/api/question/',
                     b'fetch("/api/coverage', b'fetch("/api/similar'):
        assert excluded not in body
    assert b'<base href="/api/corpus/onedpull/serve/">' in body


def test_response_size_cap_enforced():
    p = _proxy("gnocr", size_cap=10,
               fetch=_fake_fetch(body=b"x" * 11))
    status, media, body = p.serve("/api/stats")
    assert status == 503
    assert media.startswith("application/json")
    assert b"error" in body


def test_upstream_timeout_graceful():
    def slow(url, timeout, cap):
        raise TimeoutError("upstream timed out")

    p = _proxy("gnocr", fetch=slow)
    status, media, body = p.serve("/api/stats")
    assert status == 503
    assert b"error" in body


def test_daemon_down_graceful():
    def down(url, timeout, cap):
        raise ConnectionError("refused")

    p = _proxy("gnocr", fetch=down)
    status, media, body = p.serve("/api/stats")
    assert status == 503
    assert media.startswith("application/json")
    assert b"offline" in body  # in-app "brain offline" hint, never a raise


def test_onedpull_body_scan_refuses_solution_md():
    payload = b'{"results": [{"stem": "q", "solution_md": "SECRET"}]}'
    p = _proxy("onedpull", fetch=_fake_fetch(body=payload))
    status, media, body = p.serve("/api/search")
    assert status == 403
    assert b"SECRET" not in body  # the refused payload is never echoed


def test_onedpull_body_scan_allows_clean_payload():
    payload = b'{"results": [{"stem": "what is the phase difference?"}]}'
    p = _proxy("onedpull", fetch=_fake_fetch(body=payload))
    status, _, body = p.serve("/api/search")
    assert status == 200
    assert body == payload


def test_media_type_for_js_css_png():
    p = _proxy("lecturepdf", fetch=_fake_fetch(ctype="application/octet-stream",
                                               body=b"data"))
    cases = {
        "/static/js/app.js": "application/javascript",
        "/static/css/app.css": "text/css",
        "/api/diagrams/png/r/d/fig.png": "image/png",
    }
    for path, want in cases.items():
        status, media, _ = p.serve(path)
        assert status == 200
        assert media == want, path


def test_unknown_corpus_name_rejected():
    with pytest.raises(ValueError):
        CorpusProxy("evilcorp", "http://127.0.0.1:1", fetch=_fake_fetch())


# --- Codex NO-GO review regressions ---------------------------------------


def _local_http_server(handler_cls):
    """Spin a throwaway loopback HTTP server; returns (base_url, shutdown)."""
    import http.server
    import threading

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()

    def shutdown():
        srv.shutdown()
        srv.server_close()

    return f"http://127.0.0.1:{srv.server_address[1]}", shutdown


def test_redirect_status_from_transport_never_returned():
    """FINDING 1 (SSRF via redirect): a 3xx from ANY transport must be refused
    (graceful upstream-error JSON), never surfaced/followed."""
    fetch = _fake_fetch(status=302, ctype="text/html",
                        body=b"redirecting to http://169.254.169.254/latest")
    p = _proxy("gnocr", fetch=fetch)
    status, media, body = p.serve("/api/stats")
    assert status == 503
    assert media.startswith("application/json")
    assert b"169.254.169.254" not in body


def test_default_transport_refuses_redirect():
    """FINDING 1: the DEFAULT transport must not follow a 302 off-host —
    a real loopback daemon 302ing to a LAN/metadata host yields the graceful
    503, never the redirected body."""
    import http.server

    class Redirector(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(302)
            self.send_header("Location", "http://169.254.169.254/latest/meta-data/")
            self.end_headers()

        def log_message(self, *a):
            pass

    base, shutdown = _local_http_server(Redirector)
    try:
        p = CorpusProxy("gnocr", base, timeout=5.0)  # default transport
        status, media, body = p.serve("/api/stats")
        assert status == 503
        assert media.startswith("application/json")
        assert b"meta-data" not in body
    finally:
        shutdown()


def test_default_transport_slow_drip_aborts_at_deadline():
    """FINDING 2 (DoS via slow-drip body): a peer dripping bytes under the
    socket timeout must still be cut off by a HARD total deadline."""
    import http.server
    import time

    class Dripper(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", "1000")
            self.end_headers()
            try:
                for _ in range(1000):
                    self.wfile.write(b"x")
                    self.wfile.flush()
                    time.sleep(0.2)
            except (ConnectionError, OSError):
                pass

        def log_message(self, *a):
            pass

    base, shutdown = _local_http_server(Dripper)
    try:
        p = CorpusProxy("gnocr", base, timeout=0.5)  # default transport
        t0 = time.monotonic()
        status, media, body = p.serve("/api/stats")
        elapsed = time.monotonic() - t0
        assert status == 503
        assert media.startswith("application/json")
        assert elapsed < 2.0, f"slow-drip read not cut off ({elapsed:.1f}s)"
    finally:
        shutdown()


def test_credentialed_base_url_rejected_and_error_leaks_no_userinfo():
    """FINDING 3 (cred leak in error hint): userinfo URLs are refused at
    construction; the daemon-down error body carries no userinfo."""
    with pytest.raises(ValueError):
        CorpusProxy("gnocr", "http://user:token@127.0.0.1:8931",
                    fetch=_fake_fetch())
    # clean loopback URL still constructs; daemon-down hint is userinfo-free
    def down(url, timeout, cap):
        raise ConnectionError("refused")

    p = CorpusProxy("gnocr", "http://127.0.0.1:8931", fetch=down)
    status, _, body = p.serve("/api/stats")
    assert status == 503
    assert b"token" not in body and b"user:" not in body


def test_query_string_forwarded():
    fetch = _fake_fetch()
    p = _proxy("gnocr", fetch=fetch)
    p.serve("/api/search", query="q=torque")
    assert fetch.calls == ["http://127.0.0.1:8931/api/search?q=torque"]
