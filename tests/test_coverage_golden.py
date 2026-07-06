import hashlib
import pytest
from samagra import config
from samagra.factory import coverage
from samagra.factory.coverage import store


def _sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


@pytest.mark.skipif(not config.QX_BUILDER_DB.exists(), reason="QX builder.sqlite absent")
@pytest.mark.skipif(not config.TEXTBOOK_CHAPTERS.exists(), reason="textbook corpus absent")
def test_golden_thread_real_sources(tmp_path):
    graph = tmp_path / "concept_graph.db"

    # R5 (spec §12/§13): a coverage rebuild must leave the durable governance.db
    # byte-unchanged — it is read read-only, never written.
    gov = config.GOVERNANCE_DB
    gov_before = _sha(gov) if gov.exists() else None

    summary = coverage.build_concept_graph(graph_db=graph)   # real QX + corpus + governance

    if gov_before is not None:
        assert _sha(gov) == gov_before

    # Slice R: QX_BUILDER_DB now points at the live combinedDBQues sidecar, whose
    # concept count is that project's own scope (128 at rewire time), not the old
    # QX engine's 86 — assert the shape (a real, positive count), not a stale
    # hardcoded value tied to the previous engine's corpus.
    assert summary["concepts"] > 0
    assert summary["gaps"] > 0

    conn = store.connect_ro(graph)
    try:
        payload = store.coverage_payload(conn)
    finally:
        conn.close()

    states = {c["state"] for c in payload["cells"]}
    assert states <= {"produced", "base", "gap"}   # only the three valid states
    assert "gap" in states                          # samadhan everywhere is a gap
    # R4: `state == produced` iff a captured factory artifact was counted. The real,
    # cleaned-up governance.db carries no captured `textbook:` artifacts, so a real
    # `produced` cell is EXPECTED to be absent here (the produced code path is covered
    # by the synthetic tests/test_coverage_build.py::test_full_build_writes_a_queryable_graph).
    # We assert the true invariant rather than a stale "≥1 produced" claim.
    assert all((c["state"] == "produced") == (c["produced_n"] > 0) for c in payload["cells"])

    # the top gap is a high-demand concept and is pointer-pre-loaded
    top = payload["gaps"][0]
    assert top["plan_command"].startswith("samagra factory plan textbook:")
    assert top["deficit_score"] >= payload["gaps"][-1]["deficit_score"]
