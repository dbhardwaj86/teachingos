from samagra.factory.coverage import next_best

_PUB = [
    {"chapter": "circular-motion", "title": "Circular Motion", "lanes": ["revision", "deck"]},
    {"chapter": "gravitation", "title": "Gravitation", "lanes": ["revision"]},
]


def test_empty_world_is_empty():
    assert next_best.rank_next([], {}, set()) == []


def test_done_pairs_are_subtracted():
    q = next_best.rank_next(_PUB, {}, {("circular-motion", "revision")})
    assert ("circular-motion", "revision") not in {(g["chapter"], g["lane"]) for g in q}
    assert len(q) == 2


def test_demand_ranks_chapters_and_reason_reflects_it():
    q = next_best.rank_next(_PUB, {"gravitation": 900}, set())
    assert (q[0]["chapter"], q[0]["reason"], q[0]["score"]) == ("gravitation", "high-demand", 900)
    assert q[-1]["reason"] == "new"                    # unscored chapters rank after


def test_lane_priority_breaks_ties_saar_first():
    q = next_best.rank_next([_PUB[0]], {}, set())
    assert [g["lane"] for g in q] == ["revision", "deck"]   # mirrors LANE_ORDER


def test_queue_caps_and_ranks():
    pub = [{"chapter": f"c{i:02d}", "title": f"C{i}", "lanes": ["revision", "deck"]}
           for i in range(10)]
    q = next_best.rank_next(pub, {}, set())
    assert len(q) == next_best._QUEUE_SIZE
    assert [g["rank"] for g in q] == list(range(1, next_best._QUEUE_SIZE + 1))


def test_deterministic():
    a = next_best.rank_next(_PUB, {"gravitation": 5}, {("circular-motion", "deck")})
    b = next_best.rank_next(_PUB, {"gravitation": 5}, {("circular-motion", "deck")})
    assert a == b
