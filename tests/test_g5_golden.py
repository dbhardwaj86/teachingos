# tests/test_g5_golden.py
"""Phase G5 golden threads (spec §7): the HTTP recipe matches the CLI's own
result, llm/mcd stay structurally unreachable over HTTP, origin gating holds,
and the student surface is untouched. Mirrors tests/test_g3_golden.py's /
tests/test_g4_golden.py's style: a monkeypatched-temp world, real factory code,
faked-only-at-the-edges (the lecture export writer)."""

from fastapi.testclient import TestClient

from samagra import config
from samagra.api import app as api_app
from samagra.api import origin_auth
from samagra.governance import store as gov


def _fresh_world(tmp_path, monkeypatch):
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


def _stub_deck(monkeypatch, tmp_path):
    # Mirrors tests/test_factory_run.py's _stub_deck: the deck engine is stubbed at
    # its own module boundary (samagra.factory.deck.build_deck), not the lecture
    # exporter, so the deck lane can build in this temp world too.
    def fake_build_deck(slug):
        out = tmp_path / f"{slug}-deck.html"
        out.write_text(f"<h1>{slug} deck</h1>", encoding="utf-8")
        return {"variant": "deck", "html": str(out),
                "json": str(tmp_path / f"{slug}-deck.json"), "cards": 4}
    monkeypatch.setattr("samagra.factory.deck.build_deck", fake_build_deck)


def _stub_paper(monkeypatch, tmp_path):
    # Mirrors tests/test_factory_run.py's _stub_paper: the QX-backed paper/drill
    # engine is stubbed at samagra.factory.paper.build_paper (both lanes share this
    # one function, dispatched by variant), writing an answer-free html + json pair
    # so dispatch.validate_product's answer-leak scan passes for real.
    def fake_build_paper(slug, *, variant):
        out = tmp_path / f"{slug}-{variant}.html"
        out.write_text(f'<h1>{slug} {variant}</h1><div class="stem">q</div>', encoding="utf-8")
        js = tmp_path / f"{slug}-{variant}.json"
        js.write_text(f'{{"variant":"{variant}","questions":[{{"html":"<div class=\\"stem\\">q</div>"}}]}}',
                      encoding="utf-8")
        return {"variant": variant, "html": str(out), "json": str(js), "questions": 3}
    monkeypatch.setattr("samagra.factory.paper.build_paper", fake_build_paper)


def test_golden_http_recipe_matches_deterministic_lane_build(tmp_path, monkeypatch):
    """Spec §7 thread 1's actual promise: plan -> approve-seed -> build ONCE PER
    PROPOSED ASSIGNMENT -> publish, matching the CLI end to end. The single-lane
    (revision) assertions below prove the double-approve/double-build idempotency;
    the extension after them builds every remaining proposed lane (deck/paper/drill
    stubbed at their own engine boundary, mirroring tests/test_factory_run.py) and
    publishes via the G3 HTTP endpoint, then verifies /api/published lists the
    chapter with all 5 built lanes — the golden proof of the WHOLE recipe, not just
    its first step."""
    _fresh_world(tmp_path, monkeypatch)
    _stub_deck(monkeypatch, tmp_path)
    _stub_paper(monkeypatch, tmp_path)
    c = TestClient(api_app.app)
    seed_ref = "textbook:circular-motion"

    plan_resp = c.post("/api/factory/plan", json={"seed_ref": seed_ref})
    assert plan_resp.status_code == 200
    proposals = plan_resp.json()["proposals"]
    rev = next(p for p in proposals if p["line"] == "revision")
    assert rev["assignment_id"]

    appr_resp = c.post("/api/factory/approve-seed", json={"seed_ref": seed_ref})
    assert appr_resp.status_code == 200
    assert rev["assignment_id"] in appr_resp.json()["approved"]

    # Double-click idempotency (Task 3 review): a second approve finds nothing
    # left in-review and truthfully reports an empty batch — the REAL
    # run.approve_seed, not a mock. (No concurrency regression test here:
    # approve's loop is naturally idempotent — a re-run finds no in-review rows
    # — unlike plan's dedup check-then-insert window, which has its own test.)
    again = c.post("/api/factory/approve-seed", json={"seed_ref": seed_ref})
    assert again.status_code == 200
    assert again.json()["approved"] == []

    build_resp = c.post("/api/factory/build", json={"assignment_id": rev["assignment_id"]})
    assert build_resp.status_code == 200
    assert build_resp.json()["line"] == "revision"
    assert build_resp.json()["artifact_ref"]

    # A second build of the SAME assignment is refused (guard 2, unchanged) -> 409,
    # never a silent double-build or a 500.
    again = c.post("/api/factory/build", json={"assignment_id": rev["assignment_id"]})
    assert again.status_code == 409

    # ---- thread 1 extension (review MED): build every remaining proposed lane,
    # then publish over HTTP (the G3 endpoint) and verify the corpus is readable. ----
    remaining = [p for p in proposals if p["line"] != "revision"]
    assert {p["line"] for p in remaining} == {"lecture", "deck", "paper", "drill"}
    built_lines = {"revision"}
    for p in remaining:
        r = c.post("/api/factory/build", json={"assignment_id": p["assignment_id"]})
        assert r.status_code == 200, (p["line"], r.json())
        assert r.json()["line"] == p["line"]
        assert r.json()["artifact_ref"]
        built_lines.add(p["line"])
    assert built_lines == {"revision", "lecture", "deck", "paper", "drill"}   # all 5

    pub_resp = c.post("/api/factory/publish", json={"chapter": "circular-motion"})
    assert pub_resp.status_code == 200
    published = set(pub_resp.json()["result"]["published"])
    assert published == built_lines

    manifest = c.get("/api/published").json()
    assert "circular-motion" in manifest["chapters"]


def test_golden_llm_and_mcd_unreachable_over_http(tmp_path, monkeypatch):
    _fresh_world(tmp_path, monkeypatch)
    c = TestClient(api_app.app)
    # Plan the opt-in samadhan lane the way the CLI would (--lane samadhan) —
    # the GUI's own plan endpoint never does this (v1 scope guard), but the
    # BUILD refusal must hold regardless of how the assignment came to exist.
    from samagra.factory import run as factory_run
    proposals = factory_run.plan("textbook:circular-motion", dry=False, lane="samadhan")
    aid = proposals[0]["assignment_id"]
    factory_run.approve(aid)

    called = {"hit": False}
    monkeypatch.setattr("samagra.factory.run.build",
                        lambda a: called.__setitem__("hit", True) or {})
    r = c.post("/api/factory/build", json={"assignment_id": aid})
    assert r.status_code == 403
    assert called["hit"] is False

    # The golden proof of the WHOLE-lifecycle CLI-only invariant (review MED): a
    # fresh seed with a samadhan (llm) row alongside its deterministic rows, run
    # through the REAL HTTP approve-seed endpoint (no mocking of run at all) —
    # the samadhan row must stay in-review, never silently approved by the GUI's
    # per-seed batch click.
    seed_ref = "textbook:projectile-motion"
    det_proposals = factory_run.plan(seed_ref, dry=False)
    det_ids = {p["assignment_id"] for p in det_proposals}
    samadhan_aid = factory_run.plan(seed_ref, dry=False, lane="samadhan")[0]["assignment_id"]

    appr = c.post("/api/factory/approve-seed", json={"seed_ref": seed_ref})
    assert appr.status_code == 200
    approved = set(appr.json()["approved"])
    assert approved == det_ids
    assert samadhan_aid not in approved

    conn = gov.connect_ro()
    try:
        rows = {a["id"]: a["status"] for a in gov.list_assignments(conn)}
    finally:
        conn.close()
    assert rows[samadhan_aid] == "in-review"   # CLI-only through approve too, not just build


def test_golden_origin_gating_holds(monkeypatch):
    monkeypatch.setattr(config, "DISABLE_ORIGIN_AUTH", False)
    monkeypatch.setattr(config, "ACCESS_AUD", None)
    monkeypatch.setattr(config, "ACCESS_TEAM_DOMAIN", None)
    monkeypatch.setattr(config, "OWNER_EMAIL", None)
    monkeypatch.setattr(origin_auth, "_client_host", lambda req: "203.0.113.9")
    c = TestClient(api_app.app)
    for path, body in [("/api/factory/plan", {"seed_ref": "textbook:x"}),
                       ("/api/factory/approve-seed", {"seed_ref": "textbook:x"}),
                       ("/api/factory/build", {"assignment_id": "x"})]:
        assert c.post(path, json=body).status_code == 403


def _stable(manifest: dict) -> dict:
    # generated_at is a second-resolution live timestamp recomputed per GET —
    # legitimately differs across the recipe's wall-clock; everything else must
    # be byte-stable through the whole factory run.
    return {k: v for k, v in manifest.items() if k != "generated_at"}


def test_golden_student_surface_untouched(tmp_path, monkeypatch):
    _fresh_world(tmp_path, monkeypatch)
    monkeypatch.setattr(config, "PRATHAM_DB", tmp_path / "pratham.db")
    from samagra.pratham import store as pratham_store
    pratham_store._INITIALIZED.clear()

    c = TestClient(api_app.app)
    before_published = c.get("/api/published").json()
    before_me = c.get("/api/learn/me").json()

    seed_ref = "textbook:circular-motion"
    plan_resp = c.post("/api/factory/plan", json={"seed_ref": seed_ref})
    proposals = plan_resp.json()["proposals"]
    rev = next(p for p in proposals if p["line"] == "revision")
    c.post("/api/factory/approve-seed", json={"seed_ref": seed_ref})
    c.post("/api/factory/build", json={"assignment_id": rev["assignment_id"]})

    assert _stable(c.get("/api/published").json()) == _stable(before_published)
    assert c.get("/api/learn/me").json() == before_me   # exact: no timestamp field
    assert c.get("/api/learn/next").status_code == 401   # unchanged: session-gated
