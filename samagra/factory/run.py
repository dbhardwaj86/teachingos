"""The outward active loop: one seed -> N content artifacts.

Mirrors samagra/bridge/run.py shape (plan~scan, build~submit) but fans a seed to
many LANES instead of one mcd write, and writes only LOCAL artifacts in Phase 1.
Governance writes use store.connect() (durable governance.db, D6). Dedup is per
(seed_ref, line): a seed is bridged once PER lane.
"""
from __future__ import annotations

import json
import uuid

from ..adapters.munshi import MunshiAdapter
from ..bridge.classify import classify_item
from ..bridge.pointers import resolve_pointers
from ..bridge.text import item_text
from . import outbox
from ..governance import store
from .. import config
from . import dispatch, figure, samadhan, slides
from .lines import LINES, classify
from .seed_payload import build_seed_payload, validate_seed_payload

_AGENT = "khanak"  # COO/CTO — production lane owner


def _existing_assignment_for(conn, seed_ref: str, line: str) -> dict | None:
    """ANY prior assignment for this (seed_ref, line), status-blind (incl. terminal
    'captured') — one seed is fanned to a given lane at most once."""
    for a in store.list_assignments(conn):
        if a.get("seed_ref") == seed_ref and a.get("pipeline") == line:
            return a
    return None


def _item_from_artifact(art) -> dict:
    """Reconstruct the munshi item dict from an Artifact's meta envelope."""
    meta = getattr(art, "meta", None) or {}
    return {
        "id": art.uid.split(":", 1)[-1], "uid": art.uid, "kind": art.kind,
        "status": art.status, "payload": meta.get("payload") or {},
        "tags": meta.get("tags"), "person": meta.get("person"),
        "due": meta.get("due"), "ts": art.updated_at,
    }


def _munshi_item_for(seed_ref: str) -> dict | None:
    """Read-only: the single munshi item whose uid == seed_ref, else None (munshi
    unavailable / down / item absent). Linear over the library — fine for the
    single-operator console."""
    adapter = MunshiAdapter()
    if not adapter.available():
        return None
    try:
        arts = list(adapter.artifacts())
    except Exception:  # noqa: BLE001
        return None
    for art in arts:
        if art.uid == seed_ref:
            return _item_from_artifact(art)
    return None


def _record_seed_proposal(conn, item: dict, *, dry: bool) -> dict | None:
    """Propose the mcd `seed` lane for ONE munshi content item: build the flat
    create_seed payload (reused build_seed_payload) + corpus pointers, dedup per
    (seed_ref, 'seed'), and record an in-review assignment + a product_proposed
    event whose note carries the PAYLOAD (build() loads it at write time). Returns
    None if the item is not content-classified. dry=True builds the proposal but
    writes nothing (conn may be None)."""
    if classify_item(item) != "content":
        return None
    seed_ref = item.get("uid") or f"munshi:{item.get('id')}"
    pointers = resolve_pointers(item_text(item), limit=5)
    payload = build_seed_payload(item, pointers)
    proposal = {"seed_ref": seed_ref, "line": "seed",
                "expected_output": LINES["seed"].expected_output,
                "classification": "content", "pointers": pointers, "payload": payload}
    if dry:
        return proposal
    existing = _existing_assignment_for(conn, seed_ref, "seed")
    if existing is not None:
        proposal["assignment_id"] = existing["id"]
        proposal["reused"] = True
        return proposal
    assignment_id = uuid.uuid4().hex
    outbox_path = outbox.write_outbox_file(
        agent=_AGENT, assignment_id=assignment_id, pipeline="seed",
        seed_ref=seed_ref, expected_output=LINES["seed"].expected_output,
        review_by=_AGENT, payload=payload, pointers=pointers)
    store.add_assignment(
        conn, id=assignment_id, agent=_AGENT, outbox_path=outbox_path,
        pipeline="seed", seed_ref=seed_ref,
        expected_output=LINES["seed"].expected_output, review_by=_AGENT)
    store.set_assignment_status(conn, assignment_id, "in-review")
    store.append_event(
        conn, actor="system", verb="product_proposed", assignment_id=assignment_id,
        subsystem="factory", subsystem_ref=seed_ref,
        note=json.dumps({"line": "seed", "payload": payload, "pointers": pointers},
                        ensure_ascii=False))
    proposal["assignment_id"] = assignment_id
    return proposal


def _load_proposed_payload(conn, assignment_id: str) -> dict | None:
    """Recover the flat create_seed body from this assignment's product_proposed
    event note. Assignment-scoped + unbounded (no newest-N window — strictly
    better than the bridge's 10000-row scan). Returns None if absent/malformed
    (surfaced as a clear refusal, never a silent wrong write)."""
    for ev in store.list_events_for_assignment(conn, assignment_id):
        if ev.get("verb") == "product_proposed":
            try:
                note = json.loads(ev["note"])
            except (TypeError, ValueError):
                return None
            # Only a dict note carrying a DICT payload is usable; anything else is
            # a clean refusal (build() raises "no proposed payload"), never an
            # opaque AttributeError downstream in validate_seed_payload (DEC-7 F1).
            payload = note.get("payload") if isinstance(note, dict) else None
            return payload if isinstance(payload, dict) else None
    return None


def scan(dry: bool = True) -> list[dict]:
    """Discovery: propose the mcd `seed` lane for every content-classified munshi
    item (the folded bridge.scan, F-C2). Read-only over munshi; writes only
    in-review proposals (never a seed). dry=True writes nothing."""
    adapter = MunshiAdapter()
    if not adapter.available():
        return []
    proposals: list[dict] = []
    conn = None if dry else store.connect()
    try:
        try:
            arts = list(adapter.artifacts())
        except Exception:  # noqa: BLE001
            arts = []                       # munshi down mid-stream -> degrade (review 22 M2)
        for art in arts:
            proposal = _record_seed_proposal(conn, _item_from_artifact(art), dry=dry)
            if proposal is not None:
                proposals.append(proposal)
    finally:
        if conn is not None:
            conn.close()
    return proposals


def plan(seed_ref: str, dry: bool = True, lane: str | None = None) -> list[dict]:
    """Classify a seed into product lines; dry=True writes nothing, dry=False
    records ONE in-review child assignment + outbox + 'product_proposed' per line.

    A munshi: seed is the mcd `seed` lane — proposed from its LIVE item (payload),
    not a slug fan-out; routed here to _record_seed_proposal.

    Pass lane=<key> to target a single lane explicitly (the only way to reach an
    opt-in lane like the llm `samadhan` lane, which classify() excludes from the
    default fan-out); the lane must accept this seed's prefix or ValueError raises."""
    seed_ref = (seed_ref or "").strip()   # normalize ONCE (review 24 L2)
    # An explicit lane is validated FIRST: a caller targeting one lane must have the
    # seed prefix that lane accepts, regardless of which branch the seed would
    # otherwise take (e.g. a munshi: seed with lane='samadhan' is a clean refusal,
    # not a silent munshi fan-out).
    if lane is not None:
        spec = LINES.get(lane)
        if spec is None:
            raise ValueError(f"unknown lane {lane!r}")
        if not any(seed_ref.startswith(p) for p in spec.source_prefixes):
            raise ValueError(f"lane {lane!r} does not accept seed {seed_ref!r}")
    # review 27 LOW-10: a munshi seed routes to the seed proposal for BOTH the default
    # (lane is None) and the explicit `--lane seed` invocation — otherwise lane='seed'
    # fell through to the generic loop, hit `if spec.kind == "mcd": continue`, and
    # silently returned an empty plan. (The explicit-lane prefix check above already
    # refused lane='seed' on a non-munshi seed.)
    if seed_ref.startswith("munshi:") and lane in (None, "seed"):
        conn = None if dry else store.connect()
        try:
            item = _munshi_item_for(seed_ref)
            if item is None:
                return []
            proposal = _record_seed_proposal(conn, item, dry=dry)
            return [proposal] if proposal is not None else []
        finally:
            if conn is not None:
                conn.close()
    if lane is not None:
        lines = [lane]
    else:
        lines = classify(seed_ref)        # what we store + validate == what we classify
    pointers = resolve_pointers(seed_ref.split(":", 1)[-1].replace("-", " "), limit=5)
    proposals: list[dict] = []
    conn = None if dry else store.connect()
    try:
        for line in lines:
            spec = LINES[line]
            if spec.kind == "mcd":            # defense in depth: the seed lane is
                continue                       # proposed via scan/munshi-plan, never a
                                               # textbook fan-out (classify excludes it anyway)
            proposal = {"seed_ref": seed_ref, "line": line,
                        "expected_output": spec.expected_output, "pointers": pointers}
            if not dry:
                existing = _existing_assignment_for(conn, seed_ref, line)
                if existing is not None:
                    proposal["assignment_id"] = existing["id"]
                    proposal["reused"] = True
                    proposals.append(proposal)
                    continue
                assignment_id = uuid.uuid4().hex
                outbox_path = outbox.write_outbox_file(
                    agent=_AGENT, assignment_id=assignment_id, pipeline=line,
                    seed_ref=seed_ref, expected_output=spec.expected_output,
                    review_by=_AGENT, payload=proposal, pointers=pointers)
                store.add_assignment(
                    conn, id=assignment_id, agent=_AGENT, outbox_path=outbox_path,
                    pipeline=line, seed_ref=seed_ref,
                    expected_output=spec.expected_output, review_by=_AGENT)
                store.set_assignment_status(conn, assignment_id, "in-review")
                store.append_event(
                    conn, actor="system", verb="product_proposed",
                    assignment_id=assignment_id, subsystem="factory",
                    subsystem_ref=seed_ref,
                    note=json.dumps({"line": line, "pointers": pointers},
                                    ensure_ascii=False))
                proposal["assignment_id"] = assignment_id
            proposals.append(proposal)
    finally:
        if conn is not None:
            conn.close()
    return proposals


def _load_assignment(conn, assignment_id: str) -> dict | None:
    for a in store.list_assignments(conn):
        if a["id"] == assignment_id:
            return a
    return None


def approve(assignment_id: str) -> dict:
    """Board gate: flip one 'in-review' child -> 'approved'. Refuses others."""
    conn = store.connect()
    try:
        a = _load_assignment(conn, assignment_id)
        if a is None:
            raise ValueError(f"unknown assignment: {assignment_id}")
        if a["pipeline"] not in LINES:                                   # workflow firewall
            raise ValueError(
                f"assignment {assignment_id} pipeline {a['pipeline']!r} is not a "
                f"factory lane — approve it via its own workflow (review 24 M1)")
        if a["status"] != "in-review":
            raise ValueError(
                f"assignment {assignment_id} is {a['status']!r}, not 'in-review'")
        store.set_assignment_status(conn, assignment_id, "approved")
        return {"assignment_id": assignment_id, "status": "approved"}
    finally:
        conn.close()


def approve_seed(seed_ref: str) -> dict:
    """PER-SEED BATCH gate (fork 3): flip ALL in-review children of a seed ->
    'approved' in one explicit human action. Never a silent auto-approve."""
    conn = store.connect()
    try:
        approved = []
        for a in store.list_assignments(conn):
            if (a.get("seed_ref") == seed_ref and a["status"] == "in-review"
                    and a.get("pipeline") in LINES):          # workflow firewall (review 25)
                store.set_assignment_status(conn, a["id"], "approved")
                approved.append(a["id"])
        return {"seed_ref": seed_ref, "approved": approved}
    finally:
        conn.close()


def reopen(assignment_id: str) -> dict:
    """Owner regenerate: flip a terminal 'changes' factory assignment back to
    'in-review' so it can be re-approved and rebuilt to a fresh artifact (the D2
    capture/changes gate's missing return path).

    Guarded — refuses everything but an owner-reviewable local-write 'changes' brief:
      - unknown assignment;
      - not a factory lane (pipeline in LINES) — workflow firewall;
      - the mcd `seed` lane (kind=='mcd') — its single prod write is terminal and
        must stay idempotent (DEC-7); refused on KIND grounds so the guarantee is
        structural, not merely a consequence of mcd never reaching 'changes';
      - any status other than 'changes' (an in-review/approved/captured assignment
        is not reopened — a clean capture must never be silently regenerated).

    Appends a 'reopened' event that BOTH audits the owner decision AND reconciles
    guard 2 (the prior product_created is forgiven for exactly one rebuild — see
    _already_built). No event is deleted; the ledger stays append-only (D6). The
    flip is to 'in-review', NOT 'approved', so the board gate is re-crossed
    explicitly before the rebuild (the never-automated publish gate stays intact)."""
    conn = store.connect()
    try:
        a = _load_assignment(conn, assignment_id)
        if a is None:
            raise ValueError(f"unknown assignment: {assignment_id}")
        if a["pipeline"] not in LINES:                                   # workflow firewall
            raise ValueError(
                f"assignment {assignment_id} pipeline {a['pipeline']!r} is not a "
                f"factory lane — refusing via the factory workflow")
        if LINES[a["pipeline"]].kind == "mcd":                           # never the prod-write lane
            raise ValueError(
                f"assignment {assignment_id} is the mcd seed lane — its single prod "
                f"write is terminal and must not be reopened (DEC-7)")
        if a["status"] != "changes":
            raise ValueError(
                f"assignment {assignment_id} is {a['status']!r}, not 'changes' — "
                f"only an owner-review 'changes' brief is reopenable")
        store.append_event(conn, actor=_AGENT, verb="reopened",
                           assignment_id=assignment_id, subsystem="factory",
                           subsystem_ref=a["seed_ref"],
                           note="owner reopened a 'changes' brief for regeneration")
        store.set_assignment_status(conn, assignment_id, "in-review")
        return {"assignment_id": assignment_id, "status": "in-review"}
    finally:
        conn.close()


def _already_built(conn, assignment_id: str) -> bool:
    """Guard 2: a completed build ('product_created') refuses a second build —
    UNLESS a later owner 'reopened' event has forgiven it (an explicit regenerate
    decision). Count-based, never delete-based: each reopen permits EXACTLY ONE
    rebuild, so more product_created than reopened means an un-reopened build
    already exists. The ledger stays append-only (D6) — no event is removed."""
    created = reopened = 0
    for e in store.list_events_for_assignment(conn, assignment_id):
        v = e.get("verb")
        if v == "product_created":
            created += 1
        elif v == "reopened":
            reopened += 1
    return created > reopened


def _build_in_flight(conn, assignment_id: str) -> bool:
    """A prior build recorded 'product_building' with neither a matching
    'product_created' (success) nor a 'product_build_failed' (a rolled-back
    local-write failure) — it crashed inside its write window. Refuse rather than
    re-produce (guard 3). A 'product_build_failed' reconciles one 'product_building'
    so a transient LOCAL-write-lane failure (e.g. an LLM 502) is RETRYABLE, not a
    permanent wedge (DEC-7 remediation); the mcd lane never emits it, so its
    fail-safe wedge is unchanged. Assignment-scoped + unbounded (review 24 L1)."""
    building = created = failed = 0
    for e in store.list_events_for_assignment(conn, assignment_id):
        v = e.get("verb")
        if v == "product_building":
            building += 1
        elif v == "product_created":
            created += 1
        elif v == "product_build_failed":
            failed += 1
    return building > created + failed


def build(assignment_id: str) -> dict:
    """The ONE guarded write boundary. Inherits the bridge's five guards; writes a
    LOCAL artifact (Phase 1); on success flips the assignment -> terminal 'captured'."""
    conn = store.connect()
    try:
        a = _load_assignment(conn, assignment_id)
        if a is None:
            raise ValueError(f"unknown assignment: {assignment_id}")
        if a["pipeline"] not in LINES:                                   # workflow firewall
            raise ValueError(
                f"assignment {assignment_id} pipeline {a['pipeline']!r} is not a "
                f"factory lane — refusing via the factory workflow (review 24 M1)")
        if a["status"] != "approved":                                    # guard 1
            raise ValueError(
                f"assignment {assignment_id} is {a['status']!r}, not 'approved'")
        if _already_built(conn, assignment_id):                          # guard 2
            raise ValueError(
                f"assignment {assignment_id} already built — refusing a double build")
        if _build_in_flight(conn, assignment_id):                        # guard 3
            raise ValueError(
                f"assignment {assignment_id} has an in-flight build — a prior build "
                f"may have written an artifact. Reconcile before retrying.")
        line, seed_ref = a["pipeline"], a["seed_ref"]
        dispatch.validate_seed_for_line(line, seed_ref)                  # cheap pre-check
        spec = LINES[line]
        # mcd PRE-WRITE: load + validate the proposed payload BEFORE recording build
        # intent, so a structurally invalid payload refuses WITHOUT wedging the
        # assignment in the in-flight state (no prod write was attempted — nothing
        # to reconcile). Mirrors the bridge's validate-before-intent order (review 22 M1).
        payload = None
        if spec.kind == "mcd":
            payload = _load_proposed_payload(conn, assignment_id)
            if payload is None:
                raise ValueError(
                    f"no proposed payload recorded for assignment {assignment_id}")
            validate_seed_payload(payload)
            # anti-wedge (review 27 MED-1): mcd must be CONFIGURED before we record
            # build intent. An unconfigured client raises inside run_seed AFTER the
            # intent is recorded, and the mcd lane deliberately never rolls intent
            # back (it can't tell "never sent" from "may have committed") -> a
            # permanent wedge. This availability check keeps the validate-before-intent
            # contract so a config error refuses cleanly + retryably. (A configured-
            # but-unreachable failure still wedges by design — the correct fail-safe.)
            if not dispatch.McdClient().available():
                raise RuntimeError(
                    "mycontentdev not configured (mcd-cloud.json adminKey / MCD_API_URL)"
                    " — refusing the seed build before recording intent")
        elif spec.kind == "llm":
            # anti-wedge: preflight BEFORE recording build intent (a missing key /
            # absent chapter refuses without wedging the in-flight state). Both llm
            # lanes are kind=="llm"; the lane KEY disambiguates which preflight runs
            # (figure requires no StyleSeed; samadhan's path is unchanged).
            _slug = seed_ref.split(":", 1)[-1]
            if line == "figure":
                figure.preflight(_slug)
            elif line == "slides":
                slides.preflight(_slug)
            else:
                samadhan.preflight(_slug)
        # Record intent BEFORE producing (crash-window safe; mirrors bridge submit).
        store.append_event(conn, actor=_AGENT, verb="product_building",
                           assignment_id=assignment_id, subsystem="factory",
                           subsystem_ref=seed_ref, note="build intent before produce")
        # Produce + validate (KIND-AWARE — the five guards above are identical for
        # every kind; only this produce/validate step differs):
        try:
            if spec.kind == "mcd":
                result = dispatch.run_seed(payload)          # the ONE mcd prod write (+ id-check)
                artifact_ref = result["artifact_ref"]        # "mcd:<seed_id>"
                subsystem_ref = result["seed_id"]
            else:
                result = dispatch.run_line(line, seed_ref.split(":", 1)[-1])
                dispatch.validate_product(line, result)      # guard 4: exists/non-empty (+answer-leak/review)
                artifact_ref = result["html"]
                subsystem_ref = artifact_ref
        except Exception:
            # A LOCAL-write lane (local/qx/llm) commits NO external state in its
            # produce step (only a local file, safe to overwrite on retry), so a
            # transient produce failure ROLLS BACK the in-flight intent -> the
            # assignment is retryable, not permanently wedged (DEC-7 D2 HIGH). The
            # mcd lane is the deliberate exception: its produce is the ONE external
            # prod write, which MAY have committed before a crash, so it KEEPS the
            # fail-safe in-flight wedge (manual reconcile) — we do NOT roll it back.
            if spec.kind != "mcd":
                store.append_event(
                    conn, actor=_AGENT, verb="product_build_failed",
                    assignment_id=assignment_id, subsystem="factory",
                    subsystem_ref=seed_ref,
                    note="produce failed before product_created; in-flight intent rolled back")
            raise
        store.append_event(conn, actor=_AGENT, verb="product_created",
                           assignment_id=assignment_id, subsystem="factory",
                           subsystem_ref=subsystem_ref,
                           note=json.dumps({"line": line, "artifact": result},
                                           ensure_ascii=False))
        # Terminal status (guard 5, single write): an llm brief with an unresolved
        # reviewer error OR a degenerate empty brief (no items) lands in 'changes'
        # (owner review) — never a silent capture; every deterministic/mcd lane and a
        # clean, non-empty brief -> terminal 'captured'.
        # llm capture/changes gate (verbatim): a reviewer error OR an empty brief
        # routes to `changes`. F1 default posture: a figure build ALSO routes to
        # `changes` whenever SAMAGRA_FIGURE_AUTOCAPTURE is off, so a generated
        # diagram is always owner-reviewed until the owner trusts the corpus's
        # failure rate. The reviewer's real error count stays truthful in the
        # artifact — this clause only affects the terminal status, not the ledger.
        needs_review = spec.kind == "llm" and (
            result.get("errors", 0) > 0 or result.get("items", 0) == 0)
        if line == "figure" and not config._env_bool("SAMAGRA_FIGURE_AUTOCAPTURE", False):
            needs_review = True
        if line == "slides" and not config._env_bool("SAMAGRA_SLIDES_AUTOCAPTURE", False):
            needs_review = True
        status = "changes" if needs_review else "captured"
        store.set_assignment_status(conn, assignment_id, status)
        return {"assignment_id": assignment_id, "line": line,
                "artifact_ref": artifact_ref, "status": status}
    finally:
        conn.close()
