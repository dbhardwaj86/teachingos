import json
from pathlib import Path

import pytest

from samagra import config
from samagra.factory import paper


def _q(uid, body):
    """A QX result row carrying QX's question-only render (answer-free)."""
    return {"q_uid": uid, "slug": "circular-motion", "q_type": "mcq_single",
            "subject": "physics", "chapter": "Circular Motion", "difficulty": None,
            "snippet": body, "html": body}


class _FakeQx:
    """Stub of QxClient: returns a fixed answer-free payload, records the query."""
    base_url = "http://127.0.0.1:8783"
    last_kw = None

    def __init__(self, *a, **k):
        pass

    def search(self, **kw):
        _FakeQx.last_kw = kw
        return {
            "results": [
                _q("q1", '<div class="stem">A wheel spins. '
                         '<span class="mwrap"><span class="ktx" data-tex="v=\\\\omega R"></span>'
                         '<img class="eq eq-hidden" src="/asset?slug=circular-motion&amp;id=eq1"></span></div>'
                         '<div class="options"><div class="opt"><span class="opt-label">(A)</span> two</div></div>'),
                _q("q2", '<div class="stem">A car turns. '
                         '<img class="fig" src="/asset?slug=circular-motion&amp;id=f1"></div>'),
            ],
            "total": 2, "page": 1, "page_size": 25, "mode": "exact", "degraded": False,
            "facets": {},
        }


class _ManyQx(_FakeQx):
    def search(self, **kw):
        return {"results": [_q(f"q{i}", f'<div class="stem">Q{i}</div>') for i in range(12)],
                "total": 12, "page": 1, "page_size": 25, "mode": "exact",
                "degraded": False, "facets": {}}


class _DownQx:
    base_url = "http://127.0.0.1:8783"

    def __init__(self, *a, **k):
        pass

    def search(self, **kw):
        raise RuntimeError("connection refused")


@pytest.fixture
def export_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "EXPORT_DIR", tmp_path / "exports")
    return tmp_path / "exports"


def _deck_json(export_dir, name):
    return json.loads((export_dir / "circular-motion" / name).read_text(encoding="utf-8"))


def _map(monkeypatch, tmp_path, rows):
    """Point config.CHAPTER_MAP at a throwaway map for retrieval-branch tests."""
    p = tmp_path / "chapter_map.json"
    p.write_text(json.dumps(rows), encoding="utf-8")
    monkeypatch.setattr(config, "CHAPTER_MAP", p)


def _rows(n, prefix="q", text="Unique question body number"):
    """n distinct, long-enough (>= _DEDUPE_MIN_CHARS) rows."""
    return [_q(f"{prefix}{i}", f'<div class="stem">{text} {i} with enough '
                               f'length to clear the dedupe threshold easily.</div>')
            for i in range(n)]


class _TieredQx(_FakeQx):
    """Records every search() call's kwargs; returns a caller-supplied
    per-mode/per-chapter result table (default: empty everywhere)."""
    calls: list = []
    table: dict = {}  # (mode, chapter) -> results list; missing -> []

    def __init__(self, *a, **k):
        pass

    def search(self, **kw):
        type(self).calls.append(dict(kw))
        results = type(self).table.get((kw.get("mode"), kw.get("chapter")), [])
        return {"results": results, "total": len(results), "page": 1, "page_size": 25,
                "mode": kw.get("mode"), "degraded": False, "facets": {}}


def _fresh_tiered(table):
    cls = type("_TieredQxCase", (_TieredQx,), {"calls": [], "table": table})
    return cls


def test_tier1_exact_chapter_hit_is_a_single_call(export_dir, tmp_path, monkeypatch):
    _map(monkeypatch, tmp_path, {"circular-motion": {
        "chapter_id": "physics.c11.laws_of_motion", "chapter": "Laws of Motion"}})
    cls = _fresh_tiered({("exact", "Laws of Motion"): _rows(8)})
    monkeypatch.setattr(paper, "QxClient", cls)
    res = paper.build_paper("circular-motion", variant="paper")
    assert len(cls.calls) == 1
    assert cls.calls[0]["q"] == "circular motion"
    assert cls.calls[0]["mode"] == "exact"
    assert cls.calls[0]["chapter"] == "Laws of Motion"
    data = _deck_json(export_dir, "circular-motion-paper.json")
    assert data["mode"] == "exact"
    assert res["questions"] == 8


def test_tier2_semantic_floor_when_exact_chapter_is_thin(export_dir, tmp_path, monkeypatch):
    _map(monkeypatch, tmp_path, {"circular-motion": {
        "chapter_id": "physics.c11.laws_of_motion", "chapter": "Laws of Motion"}})
    cls = _fresh_tiered({
        ("exact", "Laws of Motion"): _rows(2, prefix="e"),          # < _DRILL_SIZE(8)
        ("semantic", "Laws of Motion"): _rows(8, prefix="s"),
    })
    monkeypatch.setattr(paper, "QxClient", cls)
    res = paper.build_paper("circular-motion", variant="paper")
    assert len(cls.calls) == 2
    assert cls.calls[1]["mode"] == "semantic"
    assert cls.calls[1]["q"] == cls.calls[0]["q"]
    assert cls.calls[1]["chapter"] == cls.calls[0]["chapter"] == "Laws of Motion"
    data = _deck_json(export_dir, "circular-motion-paper.json")
    assert data["mode"] == "semantic"
    assert res["questions"] == 8


def test_tier3_legacy_fallback_when_both_chapter_tiers_empty(export_dir, tmp_path, monkeypatch):
    _map(monkeypatch, tmp_path, {"circular-motion": {
        "chapter_id": "physics.c11.laws_of_motion", "chapter": "Laws of Motion"}})
    cls = _fresh_tiered({("exact", None): _rows(2, prefix="l")})   # legacy hits
    monkeypatch.setattr(paper, "QxClient", cls)
    res = paper.build_paper("circular-motion", variant="paper")
    assert len(cls.calls) == 3
    assert "chapter" not in cls.calls[2] or cls.calls[2]["chapter"] is None
    assert cls.calls[2]["q"] == "circular motion"
    data = _deck_json(export_dir, "circular-motion-paper.json")
    assert data["chapter"] is None
    assert data["mode"] == "exact"
    assert res["questions"] == 2


def test_unmapped_slug_falls_back_to_dehyphenated_text_query(export_dir, tmp_path, monkeypatch):
    _map(monkeypatch, tmp_path, {})                         # empty map
    monkeypatch.setattr(paper, "QxClient", _FakeQx)
    paper.build_paper("circular-motion", variant="paper")
    assert _FakeQx.last_kw["q"] == "circular motion"
    assert "chapter" not in _FakeQx.last_kw or _FakeQx.last_kw["chapter"] is None


def test_unmapped_slug_is_a_single_call(export_dir, tmp_path, monkeypatch):
    _map(monkeypatch, tmp_path, {})
    cls = _fresh_tiered({("exact", None): _rows(2)})
    monkeypatch.setattr(paper, "QxClient", cls)
    paper.build_paper("circular-motion", variant="paper")
    assert len(cls.calls) == 1
    assert "chapter" not in cls.calls[0] or cls.calls[0]["chapter"] is None


def test_artifact_json_records_chapter_query_and_mode(export_dir, tmp_path, monkeypatch):
    _map(monkeypatch, tmp_path, {"circular-motion": {
        "chapter_id": "physics.c11.laws_of_motion", "chapter": "Laws of Motion"}})
    cls = _fresh_tiered({("exact", "Laws of Motion"): _rows(8)})
    monkeypatch.setattr(paper, "QxClient", cls)
    paper.build_paper("circular-motion", variant="paper")
    data = _deck_json(export_dir, "circular-motion-paper.json")
    assert data["chapter"] == "Laws of Motion"
    assert data["query"] == "circular motion"
    assert data["mode"] == "exact"


def test_same_chapter_slugs_get_different_queries_regression(export_dir, monkeypatch):
    """Pins the HIGH: circular-motion and constraints-and-spring both map to
    'Laws of Motion' in the real committed chapter_map.json, but must send
    DIFFERENT text queries (and therefore no longer collide chapter-wide)."""
    cls = _fresh_tiered({})   # everything empty -> tier 3 for both, still proves per-slug q
    monkeypatch.setattr(paper, "QxClient", cls)
    paper.build_paper("circular-motion", variant="drill")
    paper.build_paper("constraints-and-spring", variant="drill")
    qs = [c["q"] for c in cls.calls]
    assert "circular motion" in qs
    assert "constraints and spring" in qs
    assert len(set(qs)) >= 2


def test_build_paper_writes_nonempty_katex_html_with_question_bodies(export_dir, monkeypatch):
    monkeypatch.setattr(paper, "QxClient", _FakeQx)
    res = paper.build_paper("circular-motion", variant="paper")
    html_path = Path(res["html"])
    assert html_path.is_file() and html_path.stat().st_size > 0
    html = html_path.read_text(encoding="utf-8")
    assert "katex" in html.lower()              # KaTeX loaded for the data-tex spans
    assert 'data-tex="v=\\\\omega R"' in html   # QX's math markup carried through
    assert "A wheel spins." in html and "A car turns." in html
    assert res["html"].endswith("circular-motion-paper.html")
    assert res["json"].endswith("circular-motion-paper.json")


def test_build_paper_absolutizes_asset_urls(export_dir, monkeypatch):
    monkeypatch.setattr(paper, "QxClient", _FakeQx)
    res = paper.build_paper("circular-motion", variant="paper")
    html = Path(res["html"]).read_text(encoding="utf-8")
    assert 'src="http://127.0.0.1:8783/asset?slug=circular-motion&amp;id=f1"' in html
    assert 'src="/asset?' not in html           # no relative asset URL survives


def test_build_paper_is_answer_free(export_dir, monkeypatch):
    monkeypatch.setattr(paper, "QxClient", _FakeQx)
    res = paper.build_paper("circular-motion", variant="paper")
    html = Path(res["html"]).read_text(encoding="utf-8").lower()
    for marker in ('class="answer"', "answer-label", "data-answer", 'class="solution"'):
        assert marker not in html


def test_drill_is_a_smaller_subset_than_paper(export_dir, monkeypatch):
    monkeypatch.setattr(paper, "QxClient", _ManyQx)
    full = paper.build_paper("circular-motion", variant="paper")
    drill = paper.build_paper("circular-motion", variant="drill")
    assert full["questions"] == 12
    assert drill["questions"] == paper._DRILL_SIZE     # capped to the focused size
    assert drill["questions"] < full["questions"]


def test_drill_keeps_all_when_fewer_than_cap(export_dir, monkeypatch):
    monkeypatch.setattr(paper, "QxClient", _FakeQx)   # only 2 results
    drill = paper.build_paper("circular-motion", variant="drill")
    assert drill["questions"] == 2


def test_drill_cap_propagates_to_the_on_disk_artifact(export_dir, monkeypatch):
    # The persisted artifact is the published product — assert the cap reaches the
    # written JSON, not only the returned count (a bug that capped the return but
    # wrote the full list would otherwise pass).
    monkeypatch.setattr(paper, "QxClient", _ManyQx)   # 12 results
    paper.build_paper("circular-motion", variant="drill")
    data = _deck_json(export_dir, "circular-motion-drill.json")
    assert data["variant"] == "drill"
    assert len(data["questions"]) == paper._DRILL_SIZE   # exactly 8 on disk, not 12


def test_build_paper_json_lists_questions(export_dir, monkeypatch):
    monkeypatch.setattr(paper, "QxClient", _FakeQx)
    paper.build_paper("circular-motion", variant="paper")
    data = _deck_json(export_dir, "circular-motion-paper.json")
    assert data["variant"] == "paper" and len(data["questions"]) == 2
    assert [q["q_uid"] for q in data["questions"]] == ["q1", "q2"]


def test_build_paper_raises_and_writes_nothing_when_qx_unreachable(export_dir, monkeypatch):
    monkeypatch.setattr(paper, "QxClient", _DownQx)
    with pytest.raises(ValueError):
        paper.build_paper("circular-motion", variant="paper")
    assert not (export_dir / "circular-motion" / "circular-motion-paper.html").exists()


def test_build_paper_result_is_json_serializable(export_dir, monkeypatch):
    monkeypatch.setattr(paper, "QxClient", _FakeQx)
    res = paper.build_paper("circular-motion", variant="paper")
    json.dumps(res)   # build() json.dumps the result into the event note — must not raise
    assert all(isinstance(v, (str, int)) for v in res.values())


_LONG_A = ('<div class="stem">A 100 N force is applied to the centre of a rope; '
           'find the tension in the rope at its midpoint.</div>')
_LONG_B = ('<div class="stem">A block slides down a frictionless incline of angle '
           'thirty degrees; find its acceleration.</div>')


class _DupQx(_FakeQx):
    def search(self, **kw):
        return {"results": [
                    _q("q1", _LONG_A),
                    _q("q2", _LONG_A),                                  # exact dup of q1
                    _q("q3", '<div class="stem">  a 100 n force is applied to the '
                             'centre of a rope; find the tension in the rope at its '
                             'midpoint.  </div>'),                       # dup modulo ws/case
                    _q("q4", _LONG_B),
                    _q("q5", '<div class="stem">short</div>'),
                    _q("q6", '<div class="stem">short</div>'),           # short: NEVER deduped
                ],
                "total": 6, "page": 1, "page_size": 25, "mode": "exact",
                "degraded": False, "facets": {}}


def test_dedupe_drops_normalized_duplicates_keeps_order_and_shorts(export_dir, monkeypatch):
    monkeypatch.setattr(paper, "QxClient", _DupQx)
    res = paper.build_paper("circular-motion", variant="paper")
    data = _deck_json(export_dir, "circular-motion-paper.json")
    assert [q["q_uid"] for q in data["questions"]] == ["q1", "q4", "q5", "q6"]
    assert res["questions"] == 4


def test_dedupe_runs_before_the_drill_slice(export_dir, monkeypatch):
    # 12 rows where rows 0..8 are one repeated body: a post-slice dedupe would
    # leave a drill of 1 distinct + slice waste; pre-slice dedupe fills the drill
    # with 8 DISTINCT questions.
    class _NineDupsQx(_FakeQx):
        def search(self, **kw):
            rows = [_q(f"d{i}", _LONG_A) for i in range(9)]
            rows += [_q(f"u{i}", f'<div class="stem">Unique question number {i} '
                                 f'with enough length to clear the threshold.</div>')
                     for i in range(9)]
            return {"results": rows, "total": 18, "page": 1, "page_size": 25,
                    "mode": "exact", "degraded": False, "facets": {}}
    monkeypatch.setattr(paper, "QxClient", _NineDupsQx)
    paper.build_paper("circular-motion", variant="drill")
    data = _deck_json(export_dir, "circular-motion-drill.json")
    uids = [q["q_uid"] for q in data["questions"]]
    assert len(uids) == paper._DRILL_SIZE
    assert uids == ["d0", "u0", "u1", "u2", "u3", "u4", "u5", "u6"]   # 8 distinct


def test_dedupe_results_is_pure_and_deterministic():
    rows = [{"html": _LONG_A}, {"html": _LONG_A}, {"html": _LONG_B}]
    once = paper._dedupe_results(list(rows))
    twice = paper._dedupe_results(list(rows))
    assert once == twice and len(once) == 2


# --- Finding 2: dedupe must be blind to identical prose but distinct math ---

_MATH_PROSE = ('<div class="stem">A charged particle moves in a uniform magnetic '
               'field. Find the radius of the path for the given expression '
               '<span class="mwrap"><span class="ktx" data-tex="{tex}"></span>'
               '<img class="eq eq-hidden" src="/asset?slug=x&amp;id=eq1"></span></div>')


def test_dedupe_keeps_rows_that_differ_only_by_data_tex(export_dir, monkeypatch):
    class _MathQx(_FakeQx):
        def search(self, **kw):
            return {"results": [
                        _q("m1", _MATH_PROSE.format(tex="r=mv/(qB)")),
                        _q("m2", _MATH_PROSE.format(tex="r=2mv/(qB)")),
                    ],
                    "total": 2, "page": 1, "page_size": 25, "mode": "exact",
                    "degraded": False, "facets": {}}
    monkeypatch.setattr(paper, "QxClient", _MathQx)
    res = paper.build_paper("circular-motion", variant="paper")
    data = _deck_json(export_dir, "circular-motion-paper.json")
    assert [q["q_uid"] for q in data["questions"]] == ["m1", "m2"]   # BOTH kept
    assert res["questions"] == 2


def test_dedupe_drops_rows_fully_identical_including_data_tex(export_dir, monkeypatch):
    class _MathQx(_FakeQx):
        def search(self, **kw):
            return {"results": [
                        _q("m1", _MATH_PROSE.format(tex="r=mv/(qB)")),
                        _q("m2", _MATH_PROSE.format(tex="r=mv/(qB)")),   # fully identical
                    ],
                    "total": 2, "page": 1, "page_size": 25, "mode": "exact",
                    "degraded": False, "facets": {}}
    monkeypatch.setattr(paper, "QxClient", _MathQx)
    res = paper.build_paper("circular-motion", variant="paper")
    data = _deck_json(export_dir, "circular-motion-paper.json")
    assert [q["q_uid"] for q in data["questions"]] == ["m1"]   # m2 dropped
    assert res["questions"] == 1


def test_projection_appends_data_tex_sources():
    a = _MATH_PROSE.format(tex="r=mv/(qB)")
    b = _MATH_PROSE.format(tex="r=2mv/(qB)")
    assert paper._projection(a) != paper._projection(b)
    assert "r=mv/(qb)" in paper._projection(a)
    assert "r=2mv/(qb)" in paper._projection(b)
