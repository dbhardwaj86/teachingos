"""Central configuration.

All paths/secrets come from environment variables (optionally loaded from a .env
file at the repo root). Machine-specific Python overrides may live in config.local.py
(gitignored). Nothing here hardcodes secrets — see .env.example.
"""
from __future__ import annotations

import os
from pathlib import Path

# Optional .env loading (python-dotenv is only required once you install deps).
try:  # pragma: no cover - convenience only
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except Exception:  # noqa: BLE001
    pass

REPO_ROOT = Path(__file__).resolve().parents[1]


def _env_path(name: str, default: Path) -> Path:
    val = os.environ.get(name)
    return Path(val) if val else default


# --- source workspace roots ---
GPT_BOX = _env_path("SAMAGRA_GPT_BOX", Path(r"C:\SandBox\gpt_box"))
CLAUDE_BOX = _env_path("SAMAGRA_CLAUDE_BOX", Path(r"C:\SandBox\claude_box"))

# --- QX (question engine) ---
QX_ROOT = _env_path("SAMAGRA_QX_ROOT", GPT_BOX / "gpt-extract-ques")
QX_CONTENT_DB = QX_ROOT / "qx" / "qx_content.sqlite"
QX_BUILDER_DB = QX_ROOT / "qx" / "builder.sqlite"

# --- physics-textbook (lecture/notes engine) ---
TEXTBOOK_ROOT = _env_path("SAMAGRA_TEXTBOOK_ROOT", GPT_BOX / "physics-textbook")
TEXTBOOK_QUEUE = TEXTBOOK_ROOT / "textbook" / "queue.json"
TEXTBOOK_CHAPTERS = TEXTBOOK_ROOT / "textbook" / "chapters"
TEXTBOOK_THEME = TEXTBOOK_ROOT / "textbook" / "theme"
TEXTBOOK_LOCK = TEXTBOOK_ROOT / "textbook" / ".routine.lock"

# --- booklets / INSP / sims ---
BOOKLETS_ROOT = _env_path("SAMAGRA_BOOKLETS_ROOT", CLAUDE_BOX / "claude-booklet-proofer")
INSP_ROOT = _env_path("SAMAGRA_INSP_ROOT", CLAUDE_BOX / "claude-INSP-extract")
SIMS_ROOT = _env_path("SAMAGRA_SIMS_ROOT", CLAUDE_BOX / "pratyaksh-May-deploy")

# --- online target ---
QUESTIONDB_URL = os.environ.get(
    "SAMAGRA_QUESTIONDB_URL", "https://dbhardwaj86-questiondb.hf.space"
)

# --- QX live server (the question engine, run locally as a sidecar) ---
# `python gui/qx_browser.py` -> :8783 exposes GET /api/qsearch (exact + semantic
# search with rendered maths + figures). SAMAGRA's /api/questions proxies it.
# W1.3: the QX base URL is the target of BOTH the backend fetch and the figure
# asset URLs the browser loads, so it must point only at a trusted local host —
# validated by api.qx_guard when QxClient is constructed (an off-host URL is
# rejected unless SAMAGRA_QX_SERVER_ALLOWED_HOSTS opts it in).
QX_SERVER_URL = os.environ.get("SAMAGRA_QX_SERVER_URL", "http://127.0.0.1:8783")
# Comma-separated extra hostnames allowed for QX_SERVER_URL beyond loopback
# (e.g. a trusted LAN sidecar). Loopback is always allowed.
QX_SERVER_ALLOWED_HOSTS = os.environ.get("SAMAGRA_QX_SERVER_ALLOWED_HOSTS", "")


def _env_bool(name: str, default: bool = False) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


# --- origin fail-closed gate (W1.1) ---
# Defence-in-depth behind Cloudflare Access. The gate covers the 5 mutating POSTs
# + the 2 admin-keyed live reads; loopback (local dev + the cloudflared origin)
# always passes. For remote requests it requires a verified Access identity:
#   * full path  — SAMAGRA_ACCESS_AUD + SAMAGRA_ACCESS_TEAM_DOMAIN configured ->
#     cryptographically validate the Cf-Access-Jwt-Assertion against the team JWKS.
#   * interim    — only when JWT validation is NOT configured: require
#     Cf-Access-Authenticated-User-Email == SAMAGRA_OWNER_EMAIL (spoofable; weaker).
# SAMAGRA_DISABLE_ORIGIN_AUTH is a dev escape hatch.
DISABLE_ORIGIN_AUTH = _env_bool("SAMAGRA_DISABLE_ORIGIN_AUTH", False)
ACCESS_AUD = os.environ.get("SAMAGRA_ACCESS_AUD") or None
ACCESS_TEAM_DOMAIN = os.environ.get("SAMAGRA_ACCESS_TEAM_DOMAIN") or None
OWNER_EMAIL = os.environ.get("SAMAGRA_OWNER_EMAIL") or None

# --- SAMAGRA-owned data (all gitignored) ---
# DATA_DB is the REBUILDABLE catalog (FTS5 index over the subsystems); it may be
# deleted and rebuilt at will. GOVERNANCE_DB is the DURABLE governance store
# (assignments / events ledger / review overlay) and must NEVER be deleted as a
# "catalog reset" — runbook D6 splits the two so irreplaceable governance state
# never shares a file with the throwaway index.
DATA_DB = REPO_ROOT / "samagra.db"
GOVERNANCE_DB = REPO_ROOT / "governance.db"
STATE_DIR = REPO_ROOT / "state"
BUILD_DIR = REPO_ROOT / "build"
EXPORT_DIR = BUILD_DIR / "lectures"
# StyleSeed (Phase D): durable, owner-curated, git-COMMITTED style profile(s).
# Unlike state/ (rebuildable) this is version-controlled — git is the review/
# approval surface (fork F-D3). One file per version: styleseed-v<N>.json.
STYLESEED_DIR = REPO_ROOT / "styleseed"
# Coverage graph (Phase E): REBUILDABLE derived DB, a sibling of DATA_DB and
# gitignored — it may be deleted and rebuilt at will (never a governance reset).
CONCEPT_GRAPH_DB = REPO_ROOT / "concept_graph.db"
# The curated chapter<->concept normalization overlay — git-COMMITTED (the human
# review surface, like styleseed/). Deltas merged onto the deterministic FTS base.
CONCEPT_ALIASES = REPO_ROOT / "concept_aliases.json"
# Published corpus (Phase G1): the owner-gated export snapshot a downstream
# consumer (PRATHAM) reads INSTEAD of the inward stores. DURABLE — never reset
# (frozen artifact copies + immutable per-publication records); gitignored like
# GOVERNANCE_DB (durable != git-committed). The append-only audit ledger lives
# in governance.db (`published`/`unpublished` events).
PUBLISHED_DIR = REPO_ROOT / "published"
# Phase G3: PRATHAM multi-tenant student identity. DURABLE (student accounts +
# sessions) and gitignored like GOVERNANCE_DB (covered by the `*.db` rule) — never
# reset. DELIBERATELY SEPARATE from governance.db so the PUBLIC student-login write
# path is physically isolated from the inward governance ledger and the 7 subsystems.
PRATHAM_DB = REPO_ROOT / "pratham.db"
# The session cookie's Secure flag: True by default (prod is served over HTTPS
# behind the cloudflared tunnel). Set SAMAGRA_PRATHAM_COOKIE_SECURE=0 only for
# local plain-http dev (alongside SAMAGRA_DISABLE_ORIGIN_AUTH).
PRATHAM_COOKIE_SECURE = _env_bool("SAMAGRA_PRATHAM_COOKIE_SECURE", True)
# Student session lifetime (fixed expiry; re-login via the enrollment code).
PRATHAM_SESSION_TTL_DAYS = int(os.environ.get("SAMAGRA_PRATHAM_SESSION_TTL_DAYS", "30"))

# --- portal ---
HOST = os.environ.get("SAMAGRA_HOST", "127.0.0.1")
PORT = int(os.environ.get("SAMAGRA_PORT", "8799"))

# --- optional python override ---
try:  # pragma: no cover
    import config_local  # type: ignore  # noqa: F401

    globals().update({k: v for k, v in vars(config_local).items() if k.isupper()})
except Exception:  # noqa: BLE001
    pass
