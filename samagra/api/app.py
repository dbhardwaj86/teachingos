"""SAMAGRA OS — FastAPI app.

Serves the Vite-built SAMAGRA OS single-page app (`frontend/dist/`) plus a small
JSON API over the catalog, QX live question search, the pipeline state machine,
and a safe local-file opener constrained to configured source roots.
"""
from __future__ import annotations

import mimetypes
import threading
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

import samagra
from . import origin_auth
from .. import catalog, config, questions_proxy, scheduler, sims_manifest, state
from ..adapters import get_adapter
from ..clients import McdClient, MunshiClient, QxClient
from ..governance import store as gstore
from ..lectures import render as lecture_render
from ..org import ORG  # E2.1 static org chart

# Vite build output (E1.17). Computed from config.REPO_ROOT at import time so the
# serve seam follows config.REPO_ROOT under test (the suite reloads this module
# after monkeypatching REPO_ROOT to a built/unbuilt tmp tree).
FRONTEND_DIST = config.REPO_ROOT / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # W1.4: create the catalog + governance schemas ONCE at startup so the GET
    # read paths never have to run DDL. Both are also memoized, so this is a
    # belt-and-braces eager init (a fresh CLI process initializes lazily).
    catalog.ensure_schema()
    gstore.ensure_tables()
    yield


app = FastAPI(title="SAMAGRA", version=samagra.__version__, lifespan=lifespan)
# W1.1: origin fail-closed gate (defence-in-depth behind Cloudflare Access). Only
# the mutating POSTs + admin-keyed live reads are gated; loopback + the dev flag
# always pass. Registered first so it wraps every route below.
app.middleware("http")(origin_auth.enforce)
# Serve hashed Vite assets only when a build is present; absent before the first
# `npm run build`, so guard the mount to avoid a StaticFiles directory error.
if (FRONTEND_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")),
              name="assets")

# review 27 MED-2: QX_ROOT is deliberately EXCLUDED. The QX source root holds
# answer-bearing audit/QC JSON (codex_jobs/*/reports/*.report.json) + raw question
# data; QX is exposed ONLY through the answer-safe /api/questions proxy, never the
# raw /open file server. (Catalog QX rows carry relative paths that never resolved
# under QX_ROOT anyway, so no working open is removed — only the absolute-path
# answer-audit surface is closed.)
ALLOWED_ROOTS = [
    config.TEXTBOOK_ROOT, config.BOOKLETS_ROOT,
    config.INSP_ROOT, config.SIMS_ROOT, config.EXPORT_DIR,
]

# The frontend's largest page (Booklets/Insp use limit=500). Clamps the
# network-facing /api/search so a negative limit (SQLite's unbounded) can't dump
# the whole catalog in one response (review 27 MED-3).
_MAX_SEARCH_LIMIT = 500


def _under_root(p: Path) -> Path | None:
    """Return p's path RELATIVE to the matched allowed root, else None.

    Resolving first keeps traversal blocked; returning the relative path lets the
    servability check inspect only the artifact path (not the trusted, possibly
    dotted, operator-configured root prefix)."""
    rp = p.resolve()
    for root in ALLOWED_ROOTS:
        try:
            return rp.relative_to(root.resolve())
        except ValueError:
            continue
    return None


def _allowed(p: Path) -> bool:
    return _under_root(p) is not None


# W1.5: even under an allowed root, only serve catalog-shaped artifact files —
# an extension allowlist plus a deny on hidden (dotfile/dir) and secret-looking
# names, so a stray .env / *.pem / token file can't be exfiltrated by path. Only
# the path RELATIVE to the root is inspected (the root itself is trusted).
_OPEN_ALLOWED_EXT = frozenset({
    ".html", ".htm", ".pdf", ".docx", ".png", ".jpg", ".jpeg",
    ".gif", ".svg", ".webp", ".md", ".txt", ".json", ".csv",
})
_OPEN_DENY_SUBSTR = ("secret", "credential", "password", "token",
                     ".env", ".pem", ".key", ".pfx", ".p12")


def _open_servable(rel: Path) -> bool:
    if rel.suffix.lower() not in _OPEN_ALLOWED_EXT:
        return False
    for part in rel.parts:
        low = part.lower()
        if part.startswith("."):  # hidden file or dir
            return False
        # secret-looking name in ANY component (a secret-named dir, not just the file)
        if any(bad in low for bad in _OPEN_DENY_SUBSTR):
            return False
    return True


# -- pages ---------------------------------------------------------------
@app.get("/lecture/{slug}", response_class=HTMLResponse)
def lecture_preview(slug: str):
    try:
        content = lecture_render.load_chapter(slug)
    except FileNotFoundError:
        raise HTTPException(404, f"chapter {slug!r} not found")
    return HTMLResponse(lecture_render.render_chapter_html(content, label="Preview"))


# -- api -----------------------------------------------------------------
@app.get("/api/overview")
def api_overview():
    return catalog.overview()


@app.get("/api/facets")
def api_facets():
    return catalog.facets()


@app.get("/api/search")
def api_search(q: str = "", source: str | None = None,
               kind: str | None = None, limit: int = 200):
    # review 27 MED-3: clamp to a positive bound. A negative limit (e.g. -1) is
    # SQLite's "no limit" and would dump the entire catalog; the CLI calls
    # catalog.search directly and is unaffected by this network-only clamp.
    limit = max(1, min(limit, _MAX_SEARCH_LIMIT))
    return {"results": catalog.search(q, source=source, kind=kind, limit=limit)}


@app.get("/api/questions")
def api_questions(q: str = "", subject: str | None = None,
                  chapter: str | None = None, qtype: str | None = None,
                  mode: str = "exact", page: int = 1):
    # Proxy the always-up QX engine (gui/qx_browser.py :8783) which owns the real
    # exact + semantic search, KaTeX maths and figure rendering. QX renders the
    # question HTML with relative /asset URLs -> absolutize them to the QX server
    # so figures load. QX unreachable -> graceful empty + error (never a 500).
    # W1.3: QxClient() validates QX_SERVER_URL — a poisoned (off-host) URL raises
    # and is caught below, so the proxy never fetches an attacker host (SSRF).
    try:
        client = QxClient()
        payload = client.search(q=q, mode=mode, subject=subject,
                                chapter=chapter, qtype=qtype, page=page)
    except Exception:  # noqa: BLE001 — bad URL / connection refused / timeout / bad JSON
        return {"results": [], "total": 0, "page": page, "page_size": 0,
                "mode": mode, "degraded": False, "facets": {},
                "error": "questions backend unavailable — is the QX server running on :8783?"}
    return questions_proxy.absolutize_assets(payload, client.base_url)


@app.get("/api/pipelines")
def api_pipelines():
    return {"pipelines": state.all_states()}


@app.get("/api/assignments")
def api_assignments():
    # Reads the DURABLE governance DB (governance.db, D6) — separate from the
    # rebuildable catalog. W1.4: the schema is ensured once (memoized + at
    # startup), and the read opens read-only so this GET can't mutate.
    gstore.ensure_tables()
    conn = gstore.connect_ro()
    try:
        return {"assignments": gstore.list_assignments(conn),
                "events": gstore.list_events(conn)}
    finally:
        conn.close()


@app.get("/api/coverage")
def api_coverage():
    # Read-only over the rebuildable concept_graph.db (Phase E). Not built yet ->
    # a graceful empty payload + hint, never a 500 (mirrors /api/questions).
    from ..factory import coverage
    try:
        return coverage.coverage_payload()
    except FileNotFoundError:
        return {"lanes": [], "concepts": [], "cells": [], "gaps": [],
                "meta": {"built": False},
                "error": "coverage graph not built — run `samagra factory coverage-build`"}


@app.get("/api/coverage/concept/{concept_id}")
def api_coverage_concept(concept_id: int):
    from ..factory import coverage
    try:
        dossier = coverage.concept_dossier(concept_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="coverage graph not built")
    if dossier is None:
        raise HTTPException(status_code=404, detail=f"unknown concept {concept_id}")
    return dossier


# -- G2 outward read surface (public, read-only) ------------------------
@app.get("/api/published")
def api_published():
    # Phase G2: the outward read surface. Public-by-design (deliberately NOT in
    # origin_auth._PROTECTED_GETS) — it serves only the corpus the owner already
    # released through the G1 publish gate. Graceful-empty (chapters == {}) when
    # nothing is published; never a 500 (mirrors /api/coverage).
    from ..factory.publish import read
    return read.published_manifest()


@app.get("/api/published/{chapter}/{lane}")
def api_published_artifact(chapter: str, lane: str, kind: str = "html"):
    # One published artifact's bytes, resolved FROM the manifest (never a
    # client-supplied path) and sha-verified. Public read. 404 on unknown
    # chapter/lane/kind; 500 on an integrity breach (a tampered/rebuilt frozen file
    # whose bytes no longer match the manifest sha — surfaced, never served).
    from ..factory.publish import read
    try:
        art = read.resolve_artifact(chapter, lane, kind=kind)
    except ValueError:
        raise HTTPException(status_code=500, detail="artifact integrity check failed")
    if art is None:
        raise HTTPException(status_code=404, detail="not published")
    # Defense-in-depth headers on this PUBLIC byte surface (adversarial review LOW):
    # nosniff stops MIME-confusion on the json/docx kinds; no-referrer keeps the
    # /api/published/<ch>/<lane> path out of the Referer when the artifact loads CDN
    # resources. For html, a CSP `sandbox allow-scripts` forces an opaque origin even
    # on DIRECT navigation (a shared deep-link / the reader's docx href) — closing the
    # gap the in-reader iframe sandbox leaves open — while still letting the artifact's
    # own inline + CDN KaTeX/MathJax run (sandbox isolates the ORIGIN, not resource
    # sources, so no restrictive script-src that would break typesetting).
    headers = {"X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer"}
    if kind == "html":
        headers["Content-Security-Policy"] = "sandbox allow-scripts"
    return Response(content=art["bytes"], media_type=art["media_type"], headers=headers)


# -- G3 owner publish write path (owner-gated via origin_auth._PROTECTED_POSTS) --
def _parse_publish_body(payload: dict):
    """Validate {chapter, lanes?}. chapter required (non-empty str); lanes optional
    (list[str]) — the network sibling of the G1 CLI's `--lanes`."""
    chapter = (payload or {}).get("chapter")
    if not isinstance(chapter, str) or not chapter.strip():
        raise HTTPException(400, "chapter is required")
    lanes = (payload or {}).get("lanes")
    if lanes is not None and not (isinstance(lanes, list)
                                  and all(isinstance(x, str) for x in lanes)):
        raise HTTPException(400, "lanes must be a list of strings")
    return chapter.strip(), lanes


@app.post("/api/factory/publish")
def api_factory_publish(payload: dict):
    # The owner release gate over HTTP. NEVER-AUTOMATED: an explicit per-call
    # {chapter, lanes?} from an authenticated owner (the gate above) — no schedule,
    # no auto-approve. A thin delegate to the already-reviewed G1 publish.run; adds
    # no new write mechanism (published/ frozen copies + append-only gov events only).
    chapter, lanes = _parse_publish_body(payload)
    from ..factory.publish import run as publish_run
    try:
        return {"ok": True, "result": publish_run.publish(chapter, lanes=lanes, actor="owner")}
    except (ValueError, FileNotFoundError) as e:
        # G1's clean refusals (unknown chapter / nothing captured / mcd lane /
        # non-textbook seed / missing artifact) -> 409 conflict, never a 500.
        raise HTTPException(409, str(e))


@app.post("/api/factory/unpublish")
def api_factory_unpublish(payload: dict):
    chapter, lanes = _parse_publish_body(payload)
    from ..factory.publish import run as publish_run
    try:
        return {"ok": True, "result": publish_run.unpublish(chapter, lanes=lanes, actor="owner")}
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(409, str(e))


# -- G5 factory-run write path (owner-gated; thin delegates to samagra/factory/run.py) --
# Serializes the G5 factory-run writes within this (single-process) server: the GUI
# can double-click/fire concurrent POSTs where the CLI was always serial, and
# run.plan's dedup check-then-insert is not atomic. Cross-PROCESS concurrency
# (CLI + HTTP at once) is unchanged and remains accepted under the single-operator
# threat model (the C3 review's H2 precedent). Deliberately NOT fixed with a DB
# unique constraint (governance no-migration invariant) or inside run.py (G5's
# thin-delegate invariant: zero new logic in reviewed factory code). Tasks 3/4
# (approve-seed, build) reuse this same lock.
_FACTORY_RUN_LOCK = threading.Lock()


def _parse_seed_ref_body(payload: dict) -> str:
    """Validate {seed_ref}. Required non-empty str; v1 scope guard restricts to the
    textbook: prefix (spec §4.1/§4.2) — munshi:/other prefixes stay CLI-only."""
    seed_ref = (payload or {}).get("seed_ref")
    if not isinstance(seed_ref, str) or not seed_ref.strip():
        raise HTTPException(400, "seed_ref is required")
    seed_ref = seed_ref.strip()
    if not seed_ref.startswith("textbook:"):
        raise HTTPException(400, "seed_ref must start with 'textbook:' (v1 GUI scope)")
    return seed_ref


@app.post("/api/factory/plan")
def api_factory_plan(payload: dict):
    # The GUI/network sibling of `samagra factory plan`. dry=False so it actually
    # records the in-review child assignments (the CLI's live-mode behaviour);
    # lane is omitted so classify() drives the default 5-lane deterministic fan-out
    # — the GUI never targets a single lane (samadhan/seed stay CLI-only, F-G5-3).
    seed_ref = _parse_seed_ref_body(payload)          # validation OUTSIDE the lock
    from ..factory import run as factory_run
    with _FACTORY_RUN_LOCK:
        try:
            proposals = factory_run.plan(seed_ref, dry=False)
        except ValueError as e:
            # Inert today (run.plan only raises for an explicit lane, never passed
            # here) — kept as future-proofing symmetry with the publish siblings;
            # becomes live only if lane is ever exposed over HTTP.
            raise HTTPException(409, str(e))
    return {"proposals": proposals}


@app.post("/api/factory/approve-seed")
def api_factory_approve_seed(payload: dict):
    # The GUI/network sibling of `samagra factory approve-seed` — the PER-SEED
    # BATCH gate (fork 3, Phase 1), SCOPED to the HTTP-buildable (deterministic)
    # lanes only (review MED, G5 4-lens review): run.approve_seed flips EVERY
    # in-review child of a seed, including a CLI-only samadhan (llm) or seed (mcd)
    # row a `factory plan --lane samadhan`/munshi scan created earlier for the same
    # seed_ref — a GUI click must never silently rubber-stamp a brief the owner
    # never reviewed. So this endpoint does NOT delegate to run.approve_seed; it
    # reads the seed's in-review children itself (the same read-only lookup pattern
    # api_factory_build uses), keeps only the ones whose LINES[pipeline].kind is
    # NOT "llm"/"mcd", and approves each kept child individually via run.approve
    # (the CLI's own single-assignment approve verb). llm/mcd children are left
    # in-review — CLI-only through their WHOLE HTTP lifecycle (approve AND build;
    # mirrors api_factory_build's 403 refusal above).
    #
    # Codex-30 addendum LOW, fixed: the scan+filter of in-review children now
    # happens INSIDE _FACTORY_RUN_LOCK, immediately before the approve loop —
    # not before the lock — so each serialized request re-reads current state.
    # A concurrent duplicate POST then loses the lock race, re-scans, finds
    # nothing left in-review (the winner already flipped it to "approved"), and
    # returns {"approved": []} instead of racing on stale ids and 409ing.
    seed_ref = _parse_seed_ref_body(payload)          # validation OUTSIDE the lock
    from ..factory.lines import LINES
    from ..factory import run as factory_run
    approved = []
    with _FACTORY_RUN_LOCK:
        gstore.ensure_tables()
        conn = gstore.connect_ro()
        try:
            children = [a for a in gstore.list_assignments(conn)
                        if a.get("seed_ref") == seed_ref and a["status"] == "in-review"]
        finally:
            conn.close()
        kept = [a["id"] for a in children
                if (spec := LINES.get(a.get("pipeline"))) is not None
                and spec.kind not in ("llm", "mcd")]
        for aid in kept:
            # run.approve raises ValueError on an unknown/wrong-pipeline/wrong-status
            # assignment; mapped to 409 like its build sibling. A mid-loop raise
            # leaves a partial batch — that matches the CLI's own semantics (each
            # approve is independent + idempotent-safe to re-run; a retried
            # approve-seed simply finds fewer in-review rows next time), so no
            # rollback is engineered here. With the scan now inside the lock, a
            # mid-loop ValueError here means the row changed state some OTHER way
            # between the scan and this specific approve (e.g. same-process CLI
            # use), not a duplicate-POST race — the single-operator threat model.
            try:
                factory_run.approve(aid)
            except ValueError as e:
                raise HTTPException(409, str(e))
            approved.append(aid)
    return {"seed_ref": seed_ref, "approved": approved}


@app.post("/api/factory/build")
def api_factory_build(payload: dict):
    # The GUI/network sibling of `samagra factory build`. Looks up the assignment's
    # lane KIND before delegating (spec §4.3, F-G5-3): a "llm" (samadhan — needs an
    # API key + incurs real generation cost) or "mcd" (seed — the ONE production
    # write path, the C3 bridge-fold) lane is refused with 403 BEFORE run.build is
    # ever called, so dispatch.run_seed / samadhan.generate_samadhan are structurally
    # unreachable over HTTP. This is the one place this endpoint does more than
    # parse-and-delegate.
    assignment_id = (payload or {}).get("assignment_id")
    if not isinstance(assignment_id, str) or not assignment_id.strip():
        raise HTTPException(400, "assignment_id is required")
    assignment_id = assignment_id.strip()

    from ..factory.lines import LINES
    from ..governance import store as gov_store
    gov_store.ensure_tables()
    conn = gov_store.connect_ro()
    try:
        assignment = next(
            (a for a in gov_store.list_assignments(conn) if a["id"] == assignment_id),
            None)
    finally:
        conn.close()
    if assignment is None:
        raise HTTPException(404, "unknown assignment")
    spec = LINES.get(assignment["pipeline"])
    if spec is None:
        raise HTTPException(404, "assignment pipeline is not a recognized factory lane")
    if spec.kind in ("llm", "mcd"):
        raise HTTPException(
            403,
            f"the {spec.kind} lane ({assignment['pipeline']}) is CLI-only — "
            "build it with `samagra factory build " + assignment_id + "` at a terminal")

    from ..factory import run as factory_run
    with _FACTORY_RUN_LOCK:
        try:
            return factory_run.build(assignment_id)
        except ValueError as e:
            raise HTTPException(409, str(e))


# -- G3 PRATHAM student identity (PUBLIC — deliberately NOT in _PROTECTED_*) ------
# /learn stays public-by-design (DEC-11); the session cookie is the only credential.
# The login write touches ONLY pratham.db (physically isolated from governance.db,
# the inward build(), and the 7 subsystems).
_PRATHAM_COOKIE = "pratham_session"


def _rate_key(request: Request) -> str:
    # Best-effort key for the login rate limiter. Behind cloudflared the TCP peer is
    # loopback, so prefer Cf-Connecting-Ip when present — a CALLER-CONTROLLED header,
    # used ONLY to blunt volume, NEVER to widen trust (the real brute-force defense is
    # the code's entropy). Falls back to the TCP peer host.
    return (request.headers.get("Cf-Connecting-Ip")
            or (request.client.host if request.client else "unknown"))


@app.post("/api/learn/login")
def api_learn_login(payload: dict, request: Request):
    code = (payload or {}).get("code")
    if not isinstance(code, str) or not code.strip():
        raise HTTPException(400, "code required")
    from ..pratham import service
    student = service.login(code.strip(), client_key=_rate_key(request))
    if student is None:        # bad / revoked code OR rate-limited -> identical 401
        raise HTTPException(401, "invalid code")
    resp = JSONResponse({"student": {"id": student["id"], "name": student["name"]}})
    # path="/api/learn": the token is honored only by /api/learn/* (spec §5.3/§8),
    # so the browser must not attach it to operator-console or asset requests.
    resp.set_cookie(_PRATHAM_COOKIE, student["_session_token"], httponly=True,
                    samesite="lax", secure=config.PRATHAM_COOKIE_SECURE, path="/api/learn",
                    max_age=config.PRATHAM_SESSION_TTL_DAYS * 86400)
    return resp


@app.post("/api/learn/logout")
def api_learn_logout(request: Request):
    from ..pratham import service
    service.logout(request.cookies.get(_PRATHAM_COOKIE))
    resp = JSONResponse({"ok": True})
    # Deletion only matches a cookie set with the SAME path — mirror /api/learn.
    resp.delete_cookie(_PRATHAM_COOKIE, path="/api/learn",
                       secure=config.PRATHAM_COOKIE_SECURE, httponly=True, samesite="lax")
    return resp


@app.get("/api/learn/me")
def api_learn_me(request: Request):
    from ..pratham import service
    return {"student": service.current_student(request.cookies.get(_PRATHAM_COOKIE))}


@app.post("/api/learn/progress")
def api_learn_progress(payload: dict, request: Request):
    # G4: the FIRST authenticated student write. Session-gated (NOT origin-gated);
    # the student id comes ONLY from the session cookie — no id parameter exists
    # anywhere on this surface (structural IDOR prevention, DEC-13). The write
    # touches ONLY pratham.db via service/store.
    from ..factory.publish import read
    from ..pratham import service
    student = service.current_student(request.cookies.get(_PRATHAM_COOKIE))
    if student is None:
        raise HTTPException(401, "sign in required")
    chapter = (payload or {}).get("chapter")
    lane = (payload or {}).get("lane")
    if not isinstance(chapter, str) or not chapter.strip() \
            or not isinstance(lane, str) or not lane.strip():
        raise HTTPException(400, "chapter and lane required")
    chapter, lane = chapter.strip(), lane.strip()
    # 404-before-write (DEC-13): a progress row can never reference content that
    # is not in the LIVE published manifest.
    ch = (read.published_manifest() or {}).get("chapters", {}).get(chapter)
    lanes = {a.get("lane") for a in (ch.get("artifacts") or [])} if ch else set()
    if lane not in lanes:
        raise HTTPException(404, "not published")
    if not service.mark_done(student["id"], chapter, lane):
        raise HTTPException(429, "slow down")
    return {"ok": True}


@app.get("/api/learn/next")
def api_learn_next(request: Request):
    # G4: the deterministic what's-next queue — session-gated (F-G4-4: adaptivity is
    # the reward for signing in; anonymous /learn stays byte-identical). Read-only.
    from ..pratham import service
    from . import learn_next
    student = service.current_student(request.cookies.get(_PRATHAM_COOKIE))
    if student is None:
        raise HTTPException(401, "sign in required")
    return learn_next.next_payload(student["id"])


@app.post("/api/refresh")
def api_refresh():
    totals = catalog.refresh(verbose=False)
    return {"ok": True, "totals": totals}


@app.post("/api/tick")
def api_tick(dry_run: bool = False):
    return scheduler.tick(dry_run=dry_run)


@app.post("/api/gate/{pipeline}/{decision}")
def api_gate(pipeline: str, decision: str):
    result = scheduler.gate(pipeline, decision)
    # F-02: a refused gate decision (prereqs incomplete, not awaiting_gate, bad
    # decision) is a conflict with current pipeline state — surface it as HTTP
    # 409 instead of a 200 with a silent JSON error body.
    if "error" in result:
        raise HTTPException(status_code=409, detail=result["error"])
    return result


# -- safe local file opener ---------------------------------------------
@app.get("/open")
def open_file(path: str, download: bool = False):
    p = Path(path)
    rel = _under_root(p)
    if rel is None:
        raise HTTPException(403, "path outside allowed source roots")
    if not _open_servable(rel):
        raise HTTPException(403, "file type not servable")
    if not p.exists() or not p.is_file():
        raise HTTPException(404, "file not found")
    media, _ = mimetypes.guess_type(str(p))
    filename = p.name if (download or p.suffix.lower() == ".docx") else None
    return FileResponse(str(p), media_type=media or "application/octet-stream",
                        filename=filename)


@app.get("/api/org")
def api_org():
    return ORG


_MUNSHI_REQUIRED = {
    "todo": ("assignee", "task"),
    "note": ("student", "issue"),
    "followup": ("date", "note"),
}
# Contract passthrough — must mirror the TS buildMunshiCapture OPTIONAL whitelist
# (frontend/src/lib/capture/munshi.ts). The server is the real trust boundary for
# this production write, so it independently whitelists allowed fields.
_MUNSHI_OPTIONAL = {
    "todo": ("due",),
    "note": ("label",),
    "followup": ("person",),
}


@app.post("/api/munshi/capture")
def api_munshi_capture(payload: dict):
    kind = (payload or {}).get("kind")
    if not isinstance(kind, str) or kind not in _MUNSHI_REQUIRED:
        raise HTTPException(400, "kind must be one of: todo, note, followup")
    required = _MUNSHI_REQUIRED[kind]
    allowed = required + _MUNSHI_OPTIONAL[kind]
    # Whitelist + sanitize: only contract-allowed keys with string values are
    # forwarded to the live worker. Unknown keys (status, id, ts, ...) are dropped.
    fields: dict[str, str] = {}
    for k in allowed:
        if k not in payload:
            continue
        v = payload[k]
        if not isinstance(v, str):
            raise HTTPException(400, f"field {k!r} must be a string")
        v = v.strip()
        if v:
            fields[k] = v
    missing = [k for k in required if k not in fields]
    if missing:
        raise HTTPException(400, f"missing required field(s): {', '.join(missing)}")
    client = MunshiClient()
    if not client.available():
        raise HTTPException(503, "munshi not configured — set MUNSHI_API_URL/MUNSHI_SECRET")
    try:
        created = client.create_item(kind, fields)
    except Exception:  # noqa: BLE001 — never surface the upstream/secret details
        raise HTTPException(502, "munshi capture failed")
    return {"ok": True, "item": created}


_SEED_TYPES = {"concept", "question", "snippet", "simulation_idea",
               "experiment", "notebooklm_link", "rough_idea"}


@app.post("/api/mcd/seeds")
def api_mcd_create_seed(payload: dict):
    payload = payload or {}
    typ = payload.get("type")
    # review 27 LOW-13: guard isinstance BEFORE the set-membership test — an
    # unhashable `type` (list/dict) would otherwise raise TypeError (500) here
    # instead of a clean 400. Mirrors the munshi `kind` guard above.
    if not isinstance(typ, str) or typ not in _SEED_TYPES:
        raise HTTPException(400, "type must be one of: " + ", ".join(sorted(_SEED_TYPES)))
    # Symmetric with munshi capture: reject non-string field values rather than
    # silently str()-coercing them into a production write.
    raw_text = payload.get("raw_text")
    if not isinstance(raw_text, str):
        raise HTTPException(400, "raw_text must be a string")
    raw_text = raw_text.strip()
    if not raw_text:
        raise HTTPException(400, "raw_text is required")
    client = McdClient()
    if not client.available():
        raise HTTPException(503, "mycontentdev not configured — set mcd-cloud.json adminKey")
    fields = {"type": typ, "raw_text": raw_text}
    for opt in ("title", "source_ref"):
        if opt not in payload:
            continue
        v = payload[opt]
        if not isinstance(v, str):
            raise HTTPException(400, f"field {opt!r} must be a string")
        v = v.strip()
        if v:
            fields[opt] = v
    try:
        created = client.create_seed(fields)
    except Exception:  # noqa: BLE001
        raise HTTPException(502, "mycontentdev seed create failed")
    return {"ok": True, "seed": created}


@app.get("/api/sims")
def api_sims():
    p = config.SIMS_ROOT / "deployed-sims-by-grade.md"
    if not p.exists():
        return {"sims": [], "total": 0}
    sims = sims_manifest.parse_deployed_sims(p.read_text(encoding="utf-8"))
    return {"sims": sims, "total": len(sims)}


@app.get("/api/questions/facets")
def api_questions_facets():
    # NOTE (provenance, W2): the live Questions UI does NOT consume this endpoint.
    # Its subject/chapter/qtype chips come from the filter-scoped facets in the
    # /api/questions payload (QX search.facet_counts → frontend lib/questions/facets).
    # This route is a separate, question-scoped subject list (qx.summary().subjects)
    # with a non-alpha guard; it is retained as an alternate read but is not what
    # structurally killed the old SIM0xxx leak (that was the UI no longer touching
    # the catalog-wide /api/facets).
    qx = get_adapter("qx")
    if not qx or not qx.available():
        return {"subjects": []}
    subjects = (qx.summary() or {}).get("subjects") or {}
    # Only human-meaningful subject names (must contain a letter). Some QX corpora
    # store numeric subject codes (e.g. {1: 32285}); a bare "1" chip is useless —
    # drop non-alphabetic keys.
    names = [str(s) for s in subjects.keys() if any(ch.isalpha() for ch in str(s))]
    return {"subjects": names}


# -- live subsystem read passthroughs (always-fresh; capture appears immediately)
# These read the LIVE deployed Munshi/mycontentdev via their adapters (not the
# rebuildable catalog), so the capture apps show real data without a catalog
# refresh and a fresh capture is visible on the next refetch. Read-only,
# creds-gated, never leak upstream/secret detail.
@app.get("/api/munshi/library")
def api_munshi_library():
    ad = get_adapter("munshi")
    if not ad or not ad.available():
        return {"results": [], "error": "munshi not configured — set MUNSHI_API_URL/MUNSHI_SECRET"}
    try:
        return {"results": [asdict(a) for a in ad.artifacts()]}
    except Exception:  # noqa: BLE001 — never surface upstream/secret detail
        return {"results": [], "error": "munshi read failed"}


@app.get("/api/mcd/seeds")
def api_mcd_seeds():
    ad = get_adapter("mycontentdev")
    if not ad or not ad.available():
        return {"results": [], "error": "mycontentdev not configured — set mcd-cloud.json adminKey"}
    try:
        return {"results": [asdict(a) for a in ad.artifacts()]}
    except Exception:  # noqa: BLE001 — never surface upstream/secret detail
        return {"results": [], "error": "mycontentdev read failed"}


# -- SPA fallback (MUST be declared LAST) -------------------------------
# Catch-all for client-side routes: serve the Vite-built index.html so the React
# router can take over. Declared last so it never shadows the API, the lecture
# preview, or the file opener above. Explicitly 404s anything under `api/` (an
# unknown API path should be a real 404, not the SPA shell).
@app.get("/{full_path:path}", response_class=HTMLResponse)
def spa(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(404, "unknown API route")
    index_html = FRONTEND_DIST / "index.html"
    if not index_html.is_file():
        raise HTTPException(503, "frontend not built — run `npm run build`")
    return FileResponse(str(index_html))
