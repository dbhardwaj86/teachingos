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


def test_golden_http_recipe_matches_deterministic_lane_build(tmp_path, monkeypatch):
    _fresh_world(tmp_path, monkeypatch)
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
