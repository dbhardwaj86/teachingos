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


def test_mapped_slug_uses_chapter_scoped_listing(export_dir, tmp_path, monkeypatch):
    _map(monkeypatch, tmp_path, {"circular-motion": {
        "chapter_id": "physics.c11.laws_of_motion", "chapter": "Laws of Motion"}})
    monkeypatch.setattr(paper, "QxClient", _FakeQx)
    res = paper.build_paper("circular-motion", variant="paper")
    assert _FakeQx.last_kw["q"] == ""                       # listing, not text query
    assert _FakeQx.last_kw["chapter"] == "Laws of Motion"   # display-name facet
    assert _FakeQx.last_kw["mode"] == "exact"
    assert res["questions"] == 2


def test_unmapped_slug_falls_back_to_dehyphenated_text_query(export_dir, tmp_path, monkeypatch):
    _map(monkeypatch, tmp_path, {})                         # empty map
    monkeypatch.setattr(paper, "QxClient", _FakeQx)
    paper.build_paper("circular-motion", variant="paper")
    assert _FakeQx.last_kw["q"] == "circular motion"
    assert "chapter" not in _FakeQx.last_kw


def test_mapped_slug_with_zero_chapter_hits_falls_back(export_dir, tmp_path, monkeypatch):
    class _EmptyThenHits(_FakeQx):
        calls = []
        def search(self, **kw):
            _EmptyThenHits.calls.append(kw)
            if kw.get("chapter"):
                return {"results": [], "total": 0, "page": 1, "page_size": 25,
                        "mode": "exact", "degraded": False, "facets": {}}
            return super().search(**kw)
    _EmptyThenHits.calls = []
    _map(monkeypatch, tmp_path, {"circular-motion": {
        "chapter_id": "physics.c11.laws_of_motion", "chapter": "Laws of Motion"}})
    monkeypatch.setattr(paper, "QxClient", _EmptyThenHits)
    res = paper.build_paper("circular-motion", variant="paper")
    assert len(_EmptyThenHits.calls) == 2                   # chapter listing, then fallback
    assert _EmptyThenHits.calls[1]["q"] == "circular motion"
    assert res["questions"] == 2


def test_artifact_json_records_chapter_and_query(export_dir, tmp_path, monkeypatch):
    _map(monkeypatch, tmp_path, {"circular-motion": {
        "chapter_id": "physics.c11.laws_of_motion", "chapter": "Laws of Motion"}})
    monkeypatch.setattr(paper, "QxClient", _FakeQx)
    paper.build_paper("circular-motion", variant="paper")
    data = _deck_json(export_dir, "circular-motion-paper.json")
    assert data["chapter"] == "Laws of Motion" and data["query"] == ""


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
