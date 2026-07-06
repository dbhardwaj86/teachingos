"""QxClient — thin client to the always-up local QX server's JSON search route.

QX (gpt-extract-ques) is the question engine, now served by combinedDBQues. It runs
as a local read-only HTTP server (``python gui/qx_browser.py`` -> :8790) exposing
``GET /api/qsearch``: exact + semantic search with per-result rendered HTML (KaTeX
maths + figures) and browse facets. SAMAGRA's ``/api/questions`` proxies this so the
OS Questions app gets the real QX engine instead of a thin LIKE slice over QX's sqlite.

No secret: QX is local and fail-open on localhost (Cloudflare Access only engages
when QX_ACCESS_* env is set). The base URL is configurable via SAMAGRA_QX_SERVER_URL.
"""
from __future__ import annotations

import requests

from .. import config
from ..api import qx_guard

_TIMEOUT = 30


class QxClient:
    def __init__(self, base_url: str | None = None):
        url = (base_url or config.QX_SERVER_URL).rstrip("/")
        # W1.3: refuse an off-host QX URL (SSRF / open asset-host guard).
        qx_guard.validate_qx_url(url)
        self.base_url = url

    def search(self, *, q: str = "", mode: str = "exact", subject: str | None = None,
               chapter: str | None = None, qtype: str | None = None, page: int = 1) -> dict:
        params: dict = {"q": q, "mode": mode, "page": page}
        for key, val in (("subject", subject), ("chapter", chapter), ("qtype", qtype)):
            if val:
                params[key] = val
        r = requests.get(f"{self.base_url}/api/qsearch", params=params, timeout=_TIMEOUT)
        r.raise_for_status()
        return r.json()
