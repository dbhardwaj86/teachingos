"""chapter_map.load(): pure parse/validate of the committed slug->chapter map,
plus curation pins on the committed artifact itself (all 59 slugs, every row
canonical against the frozen combinedDBQues taxonomy vocabulary)."""
import json
from pathlib import Path

from samagra import config
from samagra.factory import chapter_map

_FIXTURE = Path(__file__).parent / "fixtures" / "combineddb_taxonomy.json"


def _vocab():
    data = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    return {c["code"]: c["name"] for c in data["chapters"]}


def test_load_parses_valid_rows(tmp_path, monkeypatch):
    p = tmp_path / "chapter_map.json"
    p.write_text(json.dumps({
        "gauss-law": {"chapter_id": "physics.c12.electric_charges_and_fields",
                      "chapter": "Electric Charges and Fields"}}), encoding="utf-8")
    monkeypatch.setattr(config, "CHAPTER_MAP", p)
    m = chapter_map.load()
    assert m["gauss-law"]["chapter"] == "Electric Charges and Fields"


def test_load_missing_file_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CHAPTER_MAP", tmp_path / "nope.json")
    assert chapter_map.load() == {}


def test_load_drops_malformed_rows(tmp_path, monkeypatch):
    p = tmp_path / "chapter_map.json"
    p.write_text(json.dumps({
        "ok": {"chapter_id": "physics.c11.waves", "chapter": "Waves"},
        "bad-string": "Waves",
        "bad-missing-key": {"chapter_id": "physics.c11.waves"},
        "bad-types": {"chapter_id": 3, "chapter": None}}), encoding="utf-8")
    monkeypatch.setattr(config, "CHAPTER_MAP", p)
    assert list(chapter_map.load()) == ["ok"]


def test_load_bad_json_returns_empty(tmp_path, monkeypatch):
    p = tmp_path / "chapter_map.json"
    p.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(config, "CHAPTER_MAP", p)
    assert chapter_map.load() == {}


def test_committed_map_covers_all_59_slugs_canonically():
    m = chapter_map.load()          # reads the real committed chapter_map.json
    vocab = _vocab()
    assert len(m) == 59
    for slug, entry in m.items():
        assert entry["chapter_id"] in vocab, f"{slug}: non-canonical chapter_id"
        assert entry["chapter"] == vocab[entry["chapter_id"]], f"{slug}: display-name drift"
    # The two live-proven chapters pin the crosswalk direction:
    assert m["circular-motion"]["chapter"] == "Laws of Motion"
    assert m["gauss-law"]["chapter"] == "Electric Charges and Fields"
