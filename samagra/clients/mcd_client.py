"""Admin-API client for mycontentdev (editorial subsystem).

Mirrors mycontentdev/scripts/_cloud.mjs: config from mcd-cloud.json
{apiUrl,adminKey} at the mycontentdev repo root, or env MCD_API_URL /
MCD_ADMIN_KEY / MCD_APP_KEY. Trailing slashes on the URL are trimmed.

SAFETY: this client NEVER logs or reprs a key value. Reads (query / pending /
available) plus the owner-initiated capture write create_seed (POST /api/seeds,
form-encoded, authorized by the adminKey via the x-mcd-admin header) are
supported. The write was added under the 2026-06-21 DEC-3 amendment
(owner-initiated capture in-scope; the human publish gate stays never-automated).
"""
from __future__ import annotations

import json
import os

import requests

from .. import config

_TIMEOUT = 30
# mycontentdev repo root — env-overridable via SAMAGRA_MCD_ROOT (config.MCD_ROOT).
# Repointed 2026-07-08 to claude_khanak_box\mycontentdev; supplies mcd-cloud.json
# creds only (actual data hits apiUrl, the deployed worker).
_MCD_ROOT = config.MCD_ROOT


def _load_cloud_json() -> dict:
    p = _MCD_ROOT / "mcd-cloud.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return {}
    return {}


class McdClient:
    def __init__(self, api_url=None, admin_key=None, app_key=None):
        file = _load_cloud_json()
        url = api_url or os.environ.get("MCD_API_URL") or file.get("apiUrl") or ""
        self.api_url = url.rstrip("/")
        self._admin_key = admin_key or os.environ.get("MCD_ADMIN_KEY") or file.get("adminKey") or ""
        self._app_key = app_key or os.environ.get("MCD_APP_KEY") or file.get("appKey") or ""

    def available(self) -> bool:
        return bool(self.api_url and self._admin_key)

    def query(self, sql: str) -> list[dict]:
        r = requests.post(
            f"{self.api_url}/api/admin/query",
            headers={"x-mcd-admin": self._admin_key, "content-type": "application/json"},
            json={"sql": sql},
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        return r.json()

    def create_seed(self, fields: dict) -> dict:
        # Owner-initiated capture. The deployed worker parses multipart/form-data
        # (request.formData()), so send form-encoded — NOT json. The existing
        # adminKey authorizes /api/seeds (middleware accepts adminOk). Never logs keys.
        r = requests.post(
            f"{self.api_url}/api/seeds",
            headers={"x-mcd-admin": self._admin_key},
            data=fields,
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        return r.json()

    def pending(self) -> list[dict]:
        r = requests.get(
            f"{self.api_url}/api/admin/pending",
            headers={"x-mcd-admin": self._admin_key},
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        return r.json()

    def __repr__(self) -> str:  # never leak key values
        return f"McdClient(api_url={self.api_url!r}, admin_key=<set:{bool(self._admin_key)}>)"
