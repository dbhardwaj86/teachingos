# tests/test_publish_run.py
import json
import pytest
from samagra import config
from samagra.governance import store
from samagra.factory.publish import run


@pytest.fixture
def publish_env(tmp_path, monkeypatch):
    """Isolate governance + export + published trees into tmp (mirrors
    tests/test_factory_run.py::factory_env, plus PUBLISHED_DIR)."""
    monkeypatch.setattr(config, "GOVERNANCE_DB", tmp_path / "governance.db")
    monkeypatch.setattr(config, "DATA_DB", tmp_path / "samagra.db")
    monkeypatch.setattr(config, "EXPORT_DIR", tmp_path / "exports")
    monkeypatch.setattr(config, "PUBLISHED_DIR", tmp_path / "published")
    store._INITIALIZED.clear()
    store.ensure_tables()
    monkeypatch.chdir(tmp_path)
    yield tmp_path
    store._INITIALIZED.clear()


def test_publishable_excludes_the_mcd_seed_lane():
    assert "seed" not in run.PUBLISHABLE
    assert {"revision", "lecture", "deck", "paper", "drill", "samadhan",
            "figure", "slides"} == run.PUBLISHABLE


def test_norm_lanes_validates_against_publishable():
    assert run._norm_lanes(None) is None
    assert run._norm_lanes("revision,deck") == {"revision", "deck"}
    with pytest.raises(ValueError):
        run._norm_lanes("seed")                       # not publishable
    with pytest.raises(ValueError):
        run._norm_lanes("bogus")


def test_titleize():
    assert run._titleize("circular-motion") == "Circular Motion"


def test_last_product_created_recovers_the_artifact_dict():
    events = [
        {"verb": "product_building", "note": "x"},
        {"verb": "product_created",
         "note": json.dumps({"line": "revision", "artifact": {"html": "/p/a.html"}})},
    ]
    assert run._last_product_created(events) == {"html": "/p/a.html"}


def test_last_product_created_returns_none_without_a_created_event():
    assert run._last_product_created([{"verb": "product_building", "note": "x"}]) is None


def test_last_product_created_returns_last_on_rebuild():
    events = [
        {"verb": "product_created",
         "note": json.dumps({"line": "revision", "artifact": {"html": "/a.html"}})},
        {"verb": "product_created",
         "note": json.dumps({"line": "revision", "artifact": {"html": "/b.html"}})},
    ]
    assert run._last_product_created(events) == {"html": "/b.html"}


def test_last_product_created_tolerates_malformed_notes():
    events = [
        {"verb": "product_created", "note": "not-json"},
        {"verb": "product_created",
         "note": json.dumps({"line": "revision", "artifact": "not-a-dict"})},
        {"verb": "product_created",
         "note": json.dumps({"line": "revision", "artifact": {"html": "/ok.html"}})},
    ]
    assert run._last_product_created(events) == {"html": "/ok.html"}


def test_norm_lanes_edges():
    assert run._norm_lanes("revision") == {"revision"}
    assert run._norm_lanes(["revision", "deck"]) == {"revision", "deck"}
    assert run._norm_lanes(" revision , deck ") == {"revision", "deck"}
    with pytest.raises(ValueError):
        run._norm_lanes("")
    with pytest.raises(ValueError):
        run._norm_lanes([])


def _captured_revision_assignment(conn, aid, html_path):
    """A minimal captured 'revision' assignment for textbook:cm with a
    product_created note pointing at html_path."""
    store.add_assignment(conn, id=aid, agent="khanak", outbox_path="o",
                         pipeline="revision", seed_ref="textbook:cm")
    store.append_event(conn, actor="khanak", verb="product_created",
                       assignment_id=aid, subsystem="factory",
                       note=json.dumps({"line": "revision",
                                        "artifact": {"html": str(html_path), "docx": None}}))
    store.set_assignment_status(conn, aid, "captured")


def test_captured_publishable_happy_path(publish_env):
    f = publish_env / "cm-thin.html"
    f.write_text("<h1>x</h1>", encoding="utf-8")
    conn = store.connect()
    try:
        _captured_revision_assignment(conn, "x3", f)
        out = run._captured_publishable(conn, "cm", None)
        assert len(out) == 1
        assert out[0]["lane"] == "revision"
        assert out[0]["source_files"] == [str(f)]
        assert out[0]["assignment_id"] == "x3"
    finally:
        conn.close()


def test_captured_publishable_refuses_missing_product_created(publish_env):
    conn = store.connect()
    try:
        store.add_assignment(conn, id="x1", agent="khanak", outbox_path="o",
                             pipeline="revision", seed_ref="textbook:cm")
        store.set_assignment_status(conn, "x1", "captured")
        with pytest.raises(ValueError, match="no recoverable artifact"):
            run._captured_publishable(conn, "cm", None)
    finally:
        conn.close()


def test_captured_publishable_refuses_missing_file(publish_env):
    conn = store.connect()
    try:
        _captured_revision_assignment(conn, "x2", "/no/such/file.html")
        with pytest.raises(ValueError, match="file missing on disk"):
            run._captured_publishable(conn, "cm", None)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Task 7: run.publish — the owner release gate
# ---------------------------------------------------------------------------

from samagra.factory import run as factory


def _stub_export(monkeypatch, tmp_path):
    def fake_export_one(slug, variant, **kw):
        out = tmp_path / f"{slug}-{variant}.html"
        out.write_text(f"<h1>{slug} {variant}</h1>", encoding="utf-8")
        return {"variant": variant, "html": str(out), "docx": None, "gdoc": None}
    monkeypatch.setattr("samagra.lectures.export.export_one", fake_export_one)


def _capture_revision(publish_env, monkeypatch, chapter="circular-motion"):
    """plan -> approve -> build the revision lane => one captured artifact."""
    _stub_export(monkeypatch, publish_env)
    proposals = factory.plan(f"textbook:{chapter}", dry=False)
    rev = next(p for p in proposals if p["line"] == "revision")
    factory.approve(rev["assignment_id"])
    factory.build(rev["assignment_id"])
    return rev["assignment_id"]


def test_publish_golden_revision_saar_sheet(publish_env, monkeypatch):
    aid = _capture_revision(publish_env, monkeypatch)
    res = run.publish("circular-motion", lanes=["revision"])
    assert res["published"] == ["revision"]
    m = run.list_published()
    art = m["chapters"]["circular-motion"]["artifacts"][0]
    assert art["uid"] == "published:circular-motion:revision"
    assert art["assignment_id"] == aid
    # the frozen copy exists under published/<chapter>/ and matches the manifest sha
    rel = art["files"][0]["rel"]
    data = (publish_env / "published" / rel).read_bytes()
    from samagra.factory.publish import manifest as M
    assert M.sha256_bytes(data) == art["files"][0]["sha256"]
    # a `published` audit event was appended, linked to the lane's assignment
    conn = store.connect()
    try:
        ev = [e for e in store.list_events(conn) if e["verb"] == "published"]
        assert len(ev) == 1 and ev[0]["assignment_id"] == aid
    finally:
        conn.close()


def test_publish_is_idempotent_noop(publish_env, monkeypatch):
    _capture_revision(publish_env, monkeypatch)
    run.publish("circular-motion", lanes=["revision"])
    res = run.publish("circular-motion", lanes=["revision"])
    assert res.get("noop") is True
    assert res["published"] == []
    assert res["skipped_unchanged"] == ["revision"]
    from samagra.factory.publish import store as pubstore
    assert len(pubstore.read_publications()) == 1     # second publish wrote no record


def test_publish_refuses_chapter_with_no_captured_artifacts(publish_env):
    with pytest.raises(ValueError):
        run.publish("circular-motion")


def test_publish_refuses_non_publishable_lane_filter(publish_env, monkeypatch):
    _capture_revision(publish_env, monkeypatch)
    with pytest.raises(ValueError):
        run.publish("circular-motion", lanes=["seed"])


def test_publish_skips_in_review_artifacts(publish_env, monkeypatch):
    _stub_export(monkeypatch, publish_env)
    factory.plan("textbook:circular-motion", dry=False)   # in-review, never built
    with pytest.raises(ValueError):                        # nothing captured yet
        run.publish("circular-motion", lanes=["revision"])


def test_publish_retry_after_lost_manifest_is_noop_no_duplicate_event(publish_env, monkeypatch):
    """I1 regression: if manifest.json is lost but the immutable record persists
    (a mid-publish crash), a retry derives 'current' from the records, sees the
    lane unchanged, and is a clean no-op — no duplicate `published` event."""
    _capture_revision(publish_env, monkeypatch)
    run.publish("circular-motion", lanes=["revision"])
    (config.PUBLISHED_DIR / "manifest.json").unlink()      # simulate the lost cache
    conn = store.connect()
    try:
        before = sum(1 for e in store.list_events(conn) if e["verb"] == "published")
    finally:
        conn.close()
    res = run.publish("circular-motion", lanes=["revision"])
    assert res.get("noop") is True
    conn = store.connect()
    try:
        after = sum(1 for e in store.list_events(conn) if e["verb"] == "published")
    finally:
        conn.close()
    assert after == before          # no duplicate published event on retry
    # the no-op retry also self-heals the lost export contract on disk
    assert (config.PUBLISHED_DIR / "manifest.json").is_file()
    assert "circular-motion" in run.list_published()["chapters"]


# ---------------------------------------------------------------------------
# Task 8: run.unpublish + run.list_published
# ---------------------------------------------------------------------------


def test_list_published_empty_when_nothing_published(publish_env):
    m = run.list_published()
    assert m["chapters"] == {} and m["schema"] == "samagra.published.v1"


def test_unpublish_drops_from_manifest_but_keeps_history(publish_env, monkeypatch):
    _capture_revision(publish_env, monkeypatch)
    run.publish("circular-motion", lanes=["revision"])
    res = run.unpublish("circular-motion", lanes=["revision"])
    assert res["unpublished"] == ["revision"]
    assert run.list_published()["chapters"] == {}          # gone from current view
    from samagra.factory.publish import store as pubstore
    recs = pubstore.read_publications()
    assert [r["action"] for r in recs] == ["publish", "unpublish"]   # history retained
    conn = store.connect()
    try:
        verbs = [e["verb"] for e in store.list_events(conn)]
        assert "unpublished" in verbs
    finally:
        conn.close()


def test_unpublish_refuses_unpublished_chapter(publish_env):
    with pytest.raises(ValueError):
        run.unpublish("circular-motion")


# ---------------------------------------------------------------------------
# Task 9: Package re-exports + governance-byte-unchanged invariant + golden e2e
# ---------------------------------------------------------------------------


def test_package_reexports_the_public_api():
    from samagra.factory import publish as pub_pkg
    assert callable(pub_pkg.publish)
    assert callable(pub_pkg.unpublish)
    assert callable(pub_pkg.list_published)


def test_publish_leaves_assignments_table_byte_unchanged(publish_env, monkeypatch):
    """The publish boundary is additive: it appends `published` events and writes
    published/ — it must NOT alter the assignment rows (no state-machine change)."""
    _capture_revision(publish_env, monkeypatch)
    conn = store.connect()
    try:
        before = store.list_assignments(conn)
    finally:
        conn.close()
    run.publish("circular-motion", lanes=["revision"])
    conn = store.connect()
    try:
        after = store.list_assignments(conn)
        assert after == before                         # assignments untouched
        verbs = [e["verb"] for e in store.list_events(conn)]
        assert verbs.count("published") == 1           # only an event was appended
        # The published assignment must still be 'captured' — no status-machine change
        assert any(a["status"] == "captured" for a in after)
    finally:
        conn.close()


def test_golden_thread_publish_then_unpublish_roundtrip(publish_env, monkeypatch):
    _capture_revision(publish_env, monkeypatch)
    run.publish("circular-motion", lanes=["revision"])
    assert "circular-motion" in run.list_published()["chapters"]
    run.unpublish("circular-motion")
    assert run.list_published()["chapters"] == {}
    # the frozen file + both publication records persist on disk (append-only)
    from samagra.factory.publish import store as pubstore
    assert len(pubstore.read_publications()) == 2
    assert (publish_env / "published" / "circular-motion"
            / "circular-motion-thin.html").is_file()


# ---------------------------------------------------------------------------
# M2 extra test (deferred from Tasks 7–8 review): partial unpublish
# ---------------------------------------------------------------------------


def _stub_deck(monkeypatch, tmp_path):
    def fake_build_deck(slug):
        out = tmp_path / f"{slug}-deck.html"
        out.write_text(f"<h1>{slug} deck</h1>", encoding="utf-8")
        return {"variant": "deck", "html": str(out),
                "json": str(tmp_path / f"{slug}-deck.json"), "cards": 4}
    monkeypatch.setattr("samagra.factory.deck.build_deck", fake_build_deck)


def test_partial_unpublish_keeps_other_lanes(publish_env, monkeypatch):
    _stub_export(monkeypatch, publish_env)
    _stub_deck(monkeypatch, publish_env)
    proposals = factory.plan("textbook:circular-motion", dry=False)
    for lane in ("revision", "deck"):
        p = next(x for x in proposals if x["line"] == lane)
        factory.approve(p["assignment_id"])
        factory.build(p["assignment_id"])
    run.publish("circular-motion")            # all CAPTURED publishable -> revision + deck
    pubd = run.list_published()["chapters"]["circular-motion"]["artifacts"]
    assert sorted(a["lane"] for a in pubd) == ["deck", "revision"]
    run.unpublish("circular-motion", lanes=["deck"])
    remaining = run.list_published()["chapters"]["circular-motion"]["artifacts"]
    assert [a["lane"] for a in remaining] == ["revision"]      # deck withdrawn, revision stays


# ---------------------------------------------------------------------------
# Adversarial review (2 MED crash-consistency findings) + spec republish path
# ---------------------------------------------------------------------------


def test_publish_event_failure_leaves_no_orphan_record(publish_env, monkeypatch):
    """MED#1: events are appended BEFORE the record, so if the `published` event
    append fails (a crash), NO publication record is left behind — clean + retryable,
    never a record-without-its-event silent audit gap."""
    _capture_revision(publish_env, monkeypatch)
    real_append = run.gov.append_event
    def failing_append(conn, **kw):
        if kw.get("verb") == "published":
            raise RuntimeError("simulated crash during published-event append")
        return real_append(conn, **kw)
    monkeypatch.setattr("samagra.factory.publish.run.gov.append_event", failing_append)
    with pytest.raises(RuntimeError):
        run.publish("circular-motion", lanes=["revision"])
    from samagra.factory.publish import store as pubstore
    assert pubstore.read_publications() == []          # no orphan record


def test_unpublish_crash_is_idempotent_and_list_reflects_records(publish_env, monkeypatch):
    """MED#2: a crash mid-unpublish (record written, manifest not re-derived) ->
    list_published reflects the records (chapter gone, not the stale cache), and a
    retry cleanly refuses (no duplicate unpublish record)."""
    _capture_revision(publish_env, monkeypatch)
    run.publish("circular-motion", lanes=["revision"])
    real_wm = run.pub.write_manifest
    def crash_wm(m):
        raise RuntimeError("simulated crash before unpublish manifest re-derive")
    monkeypatch.setattr("samagra.factory.publish.run.pub.write_manifest", crash_wm)
    with pytest.raises(RuntimeError):
        run.unpublish("circular-motion")
    monkeypatch.setattr("samagra.factory.publish.run.pub.write_manifest", real_wm)
    from samagra.factory.publish import store as pubstore
    assert [r["action"] for r in pubstore.read_publications()] == ["publish", "unpublish"]
    assert run.list_published()["chapters"] == {}      # derives from records, not stale cache
    with pytest.raises(ValueError):                    # already withdrawn -> clean refusal
        run.unpublish("circular-motion")
    assert [r["action"] for r in pubstore.read_publications()] == ["publish", "unpublish"]  # no dup


def test_republish_after_content_change_supersedes(publish_env, monkeypatch):
    """Spec §6/§11 load-bearing path (review NIT coverage): a captured artifact whose
    bytes changed (a rebuild) re-publishes to a NEW publication record + event; the
    manifest shows the new content (last-write-wins); the old record is retained."""
    _capture_revision(publish_env, monkeypatch)
    run.publish("circular-motion", lanes=["revision"])
    html = publish_env / "circular-motion-thin.html"      # the stubbed captured artifact
    html.write_text("<h1>circular-motion thin v2</h1>", encoding="utf-8")
    res = run.publish("circular-motion", lanes=["revision"])
    assert res["published"] == ["revision"] and not res.get("noop")
    from samagra.factory.publish import store as pubstore
    assert len([r for r in pubstore.read_publications() if r["action"] == "publish"]) == 2
    art = run.list_published()["chapters"]["circular-motion"]["artifacts"][0]
    assert (publish_env / "published" / art["files"][0]["rel"]).read_text(
        encoding="utf-8") == "<h1>circular-motion thin v2</h1>"
    conn = store.connect()
    try:
        assert sum(1 for e in store.list_events(conn) if e["verb"] == "published") == 2
    finally:
        conn.close()


def test_unpublish_event_failure_leaves_no_orphan_record(publish_env, monkeypatch):
    """MED#1 class on the retract path: `unpublished` events are appended BEFORE the
    record, so an event-append crash leaves NO orphan unpublish record — the lane
    stays published (clean + retryable), never a silent retract."""
    _capture_revision(publish_env, monkeypatch)
    run.publish("circular-motion", lanes=["revision"])
    real_append = run.gov.append_event
    def failing_append(conn, **kw):
        if kw.get("verb") == "unpublished":
            raise RuntimeError("simulated crash during unpublished-event append")
        return real_append(conn, **kw)
    monkeypatch.setattr("samagra.factory.publish.run.gov.append_event", failing_append)
    with pytest.raises(RuntimeError):
        run.unpublish("circular-motion")
    from samagra.factory.publish import store as pubstore
    assert [r["action"] for r in pubstore.read_publications()] == ["publish"]   # no orphan
    assert "circular-motion" in run.list_published()["chapters"]                # still published
