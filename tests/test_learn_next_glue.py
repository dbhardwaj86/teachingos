from samagra import config
from samagra.api import learn_next
from samagra.factory.coverage import store as cov_store
from samagra.factory.publish import read
from samagra.pratham import service

_MAN = {"chapters": {
    "circular-motion": {"title": "Circular Motion",
                        "artifacts": [{"lane": "revision"}, {"lane": "deck"}]},
    "gravitation": {"title": "Gravitation", "artifacts": [{"lane": "revision"}]},
}}


def test_empty_world_yields_empty_payload(monkeypatch):
    monkeypatch.setattr(read, "published_manifest", lambda: {"chapters": {}})
    assert learn_next.next_payload("stu_a") == {"queue": [], "done": []}


def test_unbuilt_concept_graph_degrades_to_unranked(monkeypatch, tmp_path):
    monkeypatch.setattr(read, "published_manifest", lambda: _MAN)
    monkeypatch.setattr(config, "CONCEPT_GRAPH_DB", tmp_path / "absent.db", raising=False)
    p = learn_next.next_payload("stu_a")
    assert len(p["queue"]) == 3 and all(g["score"] == 0 for g in p["queue"])


def test_built_graph_scores_and_done_subtracts(monkeypatch, tmp_path):
    monkeypatch.setattr(read, "published_manifest", lambda: _MAN)
    db = tmp_path / "graph.db"
    monkeypatch.setattr(config, "CONCEPT_GRAPH_DB", db, raising=False)
    conn = cov_store.connect(db)
    cov_store.init_schema(conn)
    conn.execute("INSERT INTO concept VALUES (1, 'gravitation', 'physics.gravitation', 700, 3)")
    conn.execute("INSERT INTO concept_chapter VALUES (1, 'gravitation', 'fts', 1.0)")
    conn.commit(); conn.close()

    service.mark_done("stu_a", "circular-motion", "revision")
    p = learn_next.next_payload("stu_a")

    pairs = {(g["chapter"], g["lane"]) for g in p["queue"]}
    assert ("circular-motion", "revision") not in pairs          # done subtracted
    assert p["queue"][0]["chapter"] == "gravitation"             # demand-ranked first
    assert p["queue"][0]["score"] == 700
    assert p["done"][0]["chapter"] == "circular-motion"          # done rides along
