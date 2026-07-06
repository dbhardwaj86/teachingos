# tests/test_api_factory_approve_seed.py
import threading

import pytest
from fastapi.testclient import TestClient

from samagra import config
from samagra.api import app as api_app
from samagra.api import origin_auth
from samagra.governance import store as gov


@pytest.fixture
def gate_on(monkeypatch):
    monkeypatch.setattr(config, "DISABLE_ORIGIN_AUTH", False)
    monkeypatch.setattr(config, "ACCESS_AUD", None)
    monkeypatch.setattr(config, "ACCESS_TEAM_DOMAIN", None)
    monkeypatch.setattr(config, "OWNER_EMAIL", None)
    return monkeypatch


def _fresh_world(tmp_path, monkeypatch):
    """Mirrors tests/test_g5_golden.py's _fresh_world: a real temp governance.db +
    a faked lecture exporter so real factory_run.plan()/approve() rows can be used
    instead of a mocked run.approve_seed (the new HTTP contract no longer calls it)."""
    monkeypatch.setattr(config, "GOVERNANCE_DB", tmp_path / "governance.db")
    monkeypatch.setattr(config, "DATA_DB", tmp_path / "samagra.db")
    monkeypatch.setattr(config, "EXPORT_DIR", tmp_path / "exports")
    monkeypatch.setattr(config, "PUBLISHED_DIR", tmp_path / "published")
    gov._INITIALIZED.clear()
    gov.ensure_tables()
    monkeypatch.chdir(tmp_path)

    def fake_export_one(slug, variant, **kw):
        out = tmp_path / f"{slug}-{variant}.html"
        out.write_text(f"<h1>{slug} {variant}</h1>", encoding="utf-8")
        return {"variant": variant, "html": str(out), "docx": None, "gdoc": None}
    monkeypatch.setattr("samagra.lectures.export.export_one", fake_export_one)


def test_remote_approve_seed_without_identity_is_403(gate_on):
    gate_on.setattr(origin_auth, "_client_host", lambda req: "203.0.113.9")
    c = TestClient(api_app.app)
    r = c.post("/api/factory/approve-seed", json={"seed_ref": "textbook:circular-motion"})
    assert r.status_code == 403


def test_approve_seed_route_is_in_protected_posts():
    assert origin_auth.is_protected("POST", "/api/factory/approve-seed") is True


def test_missing_or_non_textbook_seed_ref_is_400():
    c = TestClient(api_app.app)
    assert c.post("/api/factory/approve-seed", json={}).status_code == 400
    assert c.post("/api/factory/approve-seed",
                  json={"seed_ref": "munshi:52"}).status_code == 400


def test_approve_seed_calls_run_approve_per_kept_child(tmp_path, monkeypatch):
    """New contract: the endpoint no longer delegates to run.approve_seed (which
    would flip EVERY in-review child, including a CLI-only llm/mcd row) — it reads
    the seed's in-review children itself, filters to deterministic (non llm/mcd)
    lanes, and calls run.approve(aid) per kept child. Mock run.approve to prove the
    per-assignment call shape while still exercising the real read-only lookup."""
    _fresh_world(tmp_path, monkeypatch)
    from samagra.factory import run as factory_run
    seed_ref = "textbook:circular-motion"
    proposals = factory_run.plan(seed_ref, dry=False)
    rev = next(p for p in proposals if p["line"] == "revision")

    calls = []

    def fake_approve(aid):
        calls.append(aid)
        return {"assignment_id": aid, "status": "approved"}
    monkeypatch.setattr("samagra.factory.run.approve", fake_approve)
    c = TestClient(api_app.app)
    r = c.post("/api/factory/approve-seed", json={"seed_ref": seed_ref})
    assert r.status_code == 200
    body = r.json()
    assert body["seed_ref"] == seed_ref
    assert set(body["approved"]) == set(calls)
    assert rev["assignment_id"] in calls
    assert len(calls) == 5   # revision/lecture/deck/paper/drill — every deterministic lane


def test_approve_seed_noop_for_no_in_review_children(tmp_path, monkeypatch):
    _fresh_world(tmp_path, monkeypatch)
    c = TestClient(api_app.app)
    r = c.post("/api/factory/approve-seed", json={"seed_ref": "textbook:no-such-plan"})
    assert r.status_code == 200 and r.json()["approved"] == []


def test_approve_seed_skips_llm_and_mcd_children_leaving_them_in_review(tmp_path, monkeypatch):
    """The review MED, closed: a GUI approve-seed click must NOT rubber-stamp a
    CLI-only samadhan (llm) brief a `factory plan --lane samadhan` created earlier
    for the same chapter, NOR a mcd `seed` row (a hypothetical/corrupt row —
    the real seed lane keys off a munshi: seed_ref, so a textbook: seed_ref would
    never occur from `factory plan --lane seed` in practice; planted directly here
    to prove the kind filter is defense-in-depth, not merely a seed_ref-prefix
    coincidence). Real rows, real run.approve — no mocking of run at all."""
    _fresh_world(tmp_path, monkeypatch)
    from samagra.factory import run as factory_run
    seed_ref = "textbook:circular-motion"
    proposals = factory_run.plan(seed_ref, dry=False)
    deterministic_ids = {p["assignment_id"] for p in proposals}
    samadhan_proposal = factory_run.plan(seed_ref, dry=False, lane="samadhan")[0]
    samadhan_id = samadhan_proposal["assignment_id"]

    conn = gov.connect()
    try:
        gov.add_assignment(conn, id="mcd-corrupt-1", agent="khanak", outbox_path="x",
                            pipeline="seed", seed_ref=seed_ref,
                            expected_output="x", review_by="khanak")
        gov.set_assignment_status(conn, "mcd-corrupt-1", "in-review")
    finally:
        conn.close()
    mcd_id = "mcd-corrupt-1"

    c = TestClient(api_app.app)
    r = c.post("/api/factory/approve-seed", json={"seed_ref": seed_ref})
    assert r.status_code == 200
    approved = set(r.json()["approved"])
    assert approved == deterministic_ids
    assert samadhan_id not in approved
    assert mcd_id not in approved

    conn = gov.connect_ro()
    try:
        rows = {a["id"]: a["status"] for a in gov.list_assignments(conn)}
    finally:
        conn.close()
    assert rows[samadhan_id] == "in-review"          # untouched — CLI-only through approve too
    assert rows[mcd_id] == "in-review"               # untouched — mcd stays CLI-only too
    for aid in deterministic_ids:
        assert rows[aid] == "approved"


def test_concurrent_double_post_does_not_409(tmp_path, monkeypatch):
    """Codex-30 addendum LOW: the endpoint used to scan+filter the seed's
    in-review children BEFORE acquiring _FACTORY_RUN_LOCK. Two concurrent
    duplicate POSTs could both capture the same 5 in-review ids from the
    pre-lock scan; the loser then entered the lock with STALE ids and its first
    run.approve(aid) saw status "approved" (the winner already flipped it) ->
    ValueError -> 409, instead of the intended idempotent-safe empty batch.

    Real rows, real run.approve, real lock — no mocking of run at all. Two
    threads barrier-synchronized on the SAME seed's 5 deterministic children;
    after the fix (scan moved inside the lock), the serialized loser re-reads
    current state and finds nothing left in-review, so it returns 200 with an
    empty "approved" list rather than 409."""
    _fresh_world(tmp_path, monkeypatch)
    from samagra.factory import run as factory_run
    seed_ref = "textbook:circular-motion"
    proposals = factory_run.plan(seed_ref, dry=False)
    deterministic_ids = {p["assignment_id"] for p in proposals}
    assert len(deterministic_ids) == 5

    barrier = threading.Barrier(2)
    results: list[tuple[int, list[str]] | None] = [None, None]

    def hit(j: int) -> None:
        c = TestClient(api_app.app)          # one client per thread
        barrier.wait()                       # maximize the collision window
        r = c.post("/api/factory/approve-seed", json={"seed_ref": seed_ref})
        body = r.json() if r.status_code == 200 else {}
        results[j] = (r.status_code, body.get("approved", []))

    threads = [threading.Thread(target=hit, args=(j,)) for j in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    statuses = [res[0] for res in results]     # type: ignore[index]
    assert all(s == 200 for s in statuses), (
        f"expected both concurrent approve-seed POSTs to return 200 (the "
        f"loser re-reading an empty in-review set), got {statuses}")

    union_approved: set[str] = set()
    for _, approved in results:                # type: ignore[misc]
        union_approved.update(approved)
    assert union_approved == deterministic_ids, (
        f"expected the union of both responses' approved ids to equal the "
        f"5 deterministic ids exactly once each, got {union_approved} vs "
        f"{deterministic_ids}")

    conn = gov.connect_ro()
    try:
        rows = {a["id"]: a["status"] for a in gov.list_assignments(conn)}
    finally:
        conn.close()
    for aid in deterministic_ids:
        assert rows[aid] == "approved"
