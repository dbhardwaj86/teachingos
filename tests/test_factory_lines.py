from samagra.factory import lines
from samagra.factory.lines import LINES, classify, Line


def test_samadhan_registered_as_llm_optin():
    s = LINES["samadhan"]
    assert s.kind == "llm" and s.auto_fan is False
    assert s.source_prefixes == ("textbook:",)


def test_classify_excludes_optin_lanes():
    assert classify("textbook:circular-motion") == ["revision", "lecture", "deck",
                                                     "paper", "drill"]


def test_existing_lanes_default_auto_fan_true():
    assert LINES["revision"].auto_fan is True and LINES["deck"].auto_fan is True


def test_textbook_seed_fans_to_five_content_lanes():
    assert lines.classify("textbook:circular-motion") == [
        "revision", "lecture", "deck", "paper", "drill"]


def test_unknown_source_fans_to_nothing():
    assert lines.classify("mcd:123") == []
    assert lines.classify("") == []


def test_registry_has_expected_output_labels():
    for key in ("revision", "lecture", "deck", "paper", "drill", "seed", "samadhan",
                "figure", "slides"):
        assert lines.LINES[key].expected_output
    assert set(lines.LINES) == {
        "revision", "lecture", "deck", "paper", "drill", "seed", "samadhan", "figure",
        "slides"}


def test_munshi_seed_fans_to_the_seed_lane_only():
    assert lines.classify("munshi:42") == ["seed"]


def test_textbook_seed_still_fans_to_five_content_lanes_not_seed():
    # the mcd seed lane has a munshi: prefix, so a textbook seed never reaches it
    assert lines.classify("textbook:circular-motion") == [
        "revision", "lecture", "deck", "paper", "drill"]


def test_seed_line_is_mcd_kind_and_munshi_sourced():
    seed = lines.LINES["seed"]
    assert seed.kind == "mcd"
    assert seed.source_prefixes == ("munshi:",)


def test_registry_now_has_six_lanes_including_seed():
    assert {"revision", "lecture", "deck", "paper", "drill", "seed"} <= set(lines.LINES)


def test_deck_line_is_local_kind_and_textbook_sourced():
    deck = lines.LINES["deck"]
    assert deck.kind == "local"
    assert deck.source_prefixes == ("textbook:",)


def test_existing_lanes_default_to_local_kind():
    assert lines.LINES["revision"].kind == "local"
    assert lines.LINES["lecture"].kind == "local"


def test_paper_and_drill_are_qx_kind_and_textbook_sourced():
    for key in ("paper", "drill"):
        ln = lines.LINES[key]
        assert ln.kind == "qx"
        assert ln.source_prefixes == ("textbook:",)
        assert ln.variant == key      # the engine reads variant to size paper vs drill
