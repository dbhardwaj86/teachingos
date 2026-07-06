"""The samadhan lane engine: condition -> generate -> adversarially review ->
advisory score -> write local artifacts. The LLM is a FakeLLM (no network)."""
from __future__ import annotations

import json

import pytest

from samagra import config
from samagra.factory import samadhan
from samagra.factory.style import profile as P


FACETS = {"voice": {"mean_sentence_len": 16.0, "second_person_rate": 0.08,
                    "hedge_rate": 0.05, "imperative_rate": 0.1},
          "sequencing": {"mean_sections_per_chapter": 5.0},
          "analogy": {"analogy_block_rate": 0.03},
          "rigor": {"flags_per_section": 0.9}, "selection": {"callout_density": 0.2}}


class FakeLLM:
    def __init__(self, items, verdicts):
        self._items, self._verdicts = items, verdicts
        self.gen_system = None
    def generate_samadhan(self, chapter, *, system):
        self.gen_system = system
        return {"items": self._items}
    def review_samadhan(self, items, chapter):
        return {"verdicts": self._verdicts}


@pytest.fixture()
def styleseed(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "STYLESEED_DIR", tmp_path / "styleseed")
    monkeypatch.setattr(P, "_now", lambda: "t")
    P.save(P.StyleSeed(0, FACETS, "h", "t"))


@pytest.fixture()
def export(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "EXPORT_DIR", tmp_path / "lectures")


@pytest.fixture()
def fake_chapter(monkeypatch):
    from samagra.lectures import render
    monkeypatch.setattr(render, "load_chapter",
                        lambda slug: {"title": "Circular Motion", "subtitle": "",
                                      "sections": []})


def test_clean_brief_writes_artifacts_and_zero_errors(styleseed, export, fake_chapter):
    client = FakeLLM(items=[{"concept": "centripetal", "misconception": "force outward",
                             "correction": "net force points inward",
                             "why": "you feel pushed out"}],
                     verdicts=[{"idx": 0, "verdict": "ok", "rationale": "correct"}])
    res = samadhan.build_samadhan("circular-motion", client=client)
    assert res["variant"] == "samadhan" and res["items"] == 1 and res["errors"] == 0
    assert res["style_seed_version"] == 0 and "overall" in res["style_score"]
    assert "voice" in (client.gen_system or "").lower()
    from pathlib import Path
    assert Path(res["html"]).is_file() and Path(res["json"]).is_file()
    data = json.loads(Path(res["json"]).read_text(encoding="utf-8"))
    assert data["items"][0]["verdict"] == "ok"
    assert data["style_seed_version"] == 0


def test_error_verdict_is_counted(styleseed, export, fake_chapter):
    client = FakeLLM(items=[{"concept": "c", "misconception": "m",
                             "correction": "k", "why": "w"}],
                     verdicts=[{"idx": 0, "verdict": "error", "rationale": "wrong"}])
    res = samadhan.build_samadhan("x", client=client)
    assert res["errors"] == 1


def test_missing_verdict_defaults_to_error_failclosed(styleseed, export, fake_chapter):
    # DEC-7 remediation: 2 items but only 1 verdict -> the UNREVIEWED item fails
    # CLOSED (counts as an error), so partial reviewer coverage can't let an
    # unreviewed item slip to `captured`.
    client = FakeLLM(items=[{"concept": "a", "misconception": "m", "correction": "k", "why": "w"},
                            {"concept": "b", "misconception": "m2", "correction": "k2", "why": "w2"}],
                     verdicts=[{"idx": 0, "verdict": "ok", "rationale": "ok"}])
    res = samadhan.build_samadhan("x", client=client)
    assert res["items"] == 2 and res["errors"] == 1


def test_misindexed_verdict_clears_no_item(styleseed, export, fake_chapter):
    # DEC-7 re-review caveat: a verdict whose idx matches no item must clear NOTHING
    # (both items stay unreviewed -> fail-closed -> errors==2), so a mis-indexed
    # reviewer response can't smuggle an unreviewed item to `captured`.
    client = FakeLLM(items=[{"concept": "a", "misconception": "m", "correction": "k", "why": "w"},
                            {"concept": "b", "misconception": "m2", "correction": "k2", "why": "w2"}],
                     verdicts=[{"idx": 99, "verdict": "ok", "rationale": "stray"}])
    res = samadhan.build_samadhan("x", client=client)
    assert res["items"] == 2 and res["errors"] == 2


def test_html_escapes_untrusted_text_but_json_keeps_raw(styleseed, export, fake_chapter):
    client = FakeLLM(items=[{"concept": "Gauss", "misconception": "E(r<R) & B>0 always",
                             "correction": "for r<R the field is 0",
                             "why": "symmetry & <flux>"}],
                     verdicts=[{"idx": 0, "verdict": "ok", "rationale": "ok"}])
    res = samadhan.build_samadhan("gauss-law", client=client)
    from pathlib import Path
    html = Path(res["html"]).read_text(encoding="utf-8")
    assert "E(r<R)" not in html and "E(r&lt;R)" in html
    data = json.loads(Path(res["json"]).read_text(encoding="utf-8"))
    assert data["items"][0]["misconception"] == "E(r<R) & B>0 always"


def test_missing_chapter_raises_before_any_write(styleseed, export, monkeypatch):
    from samagra.lectures import render
    def boom(slug):
        raise FileNotFoundError(slug)
    monkeypatch.setattr(render, "load_chapter", boom)
    with pytest.raises(FileNotFoundError):
        samadhan.build_samadhan("nope", client=FakeLLM([], []))


def test_preflight_raises_without_key(styleseed, fake_chapter, monkeypatch):
    from samagra.clients import llm_client
    monkeypatch.setattr(llm_client, "configured", lambda: False)
    with pytest.raises(RuntimeError):
        samadhan.preflight("circular-motion")


def test_preflight_raises_without_styleseed(export, fake_chapter, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "STYLESEED_DIR", tmp_path / "none")
    from samagra.clients import llm_client
    monkeypatch.setattr(llm_client, "configured", lambda: True)
    with pytest.raises(RuntimeError):
        samadhan.preflight("circular-motion")


def test_preflight_names_selected_provider_key_var_openai(styleseed, fake_chapter, monkeypatch):
    # review 32 caveat L: under provider=openai with no OPENAI_API_KEY, the
    # preflight refusal must name OPENAI_API_KEY, never ANTHROPIC_API_KEY.
    monkeypatch.setenv("SAMAGRA_LLM_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError) as exc:
        samadhan.preflight("circular-motion")
    assert "OPENAI_API_KEY" in str(exc.value)
    assert "ANTHROPIC_API_KEY" not in str(exc.value)
