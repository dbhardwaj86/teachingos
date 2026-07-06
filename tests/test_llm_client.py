"""The single Anthropic call site. No network: a fake SDK is injected; the only
real-network path is the opt-in live smoke (separate file). A missing key raises;
the key is never logged or repr'd."""
from __future__ import annotations

import pytest

from samagra.clients import llm_client


class _FakeMessages:
    def __init__(self, payload_text):
        self._payload_text = payload_text
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        block = type("B", (), {"type": "text", "text": self._payload_text})()
        return type("R", (), {"content": [block], "stop_reason": "end_turn"})()


class _FakeSDK:
    def __init__(self, payload_text):
        self.messages = _FakeMessages(payload_text)


def test_configured_reflects_env(monkeypatch):
    monkeypatch.delenv("SAMAGRA_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert llm_client.configured() is False
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    assert llm_client.configured() is True


def test_missing_key_raises_runtimeerror(monkeypatch):
    monkeypatch.delenv("SAMAGRA_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        llm_client.LLMClient()


def test_repr_never_leaks_key(monkeypatch):
    monkeypatch.delenv("SAMAGRA_LLM_PROVIDER", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-SECRET-zzz")
    c = llm_client.LLMClient(sdk=_FakeSDK('{"items": []}'))
    assert "SECRET" not in repr(c)


def test_generate_samadhan_builds_request_and_parses(monkeypatch):
    monkeypatch.delenv("SAMAGRA_LLM_PROVIDER", raising=False)
    sdk = _FakeSDK('{"items": [{"concept": "c", "misconception": "m", '
                   '"correction": "k", "why": "w"}]}')
    c = llm_client.LLMClient(sdk=sdk, model="claude-opus-4-8")
    out = c.generate_samadhan({"title": "Circular Motion"}, system="STYLE-BLOCK")
    assert out["items"][0]["concept"] == "c"
    kw = sdk.messages.calls[0]
    assert kw["model"] == "claude-opus-4-8"
    assert kw["thinking"] == {"type": "adaptive"}
    assert kw["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert "STYLE-BLOCK" in kw["system"][0]["text"]
    assert kw["output_config"]["format"]["type"] == "json_schema"


def test_review_samadhan_uses_groundtruth_only_system(monkeypatch):
    monkeypatch.delenv("SAMAGRA_LLM_PROVIDER", raising=False)
    sdk = _FakeSDK('{"verdicts": [{"idx": 0, "verdict": "ok", "rationale": "r"}]}')
    c = llm_client.LLMClient(sdk=sdk)
    out = c.review_samadhan([{"concept": "c", "misconception": "m",
                              "correction": "k", "why": "w"}],
                            {"title": "Circular Motion"})
    assert out["verdicts"][0]["verdict"] == "ok"
    sys_text = sdk.messages.calls[0]["system"][0]["text"].lower()
    assert "refute" in sys_text or "ground" in sys_text
    assert "styleseed" not in sys_text


# --- DEC-7 remediation: response parsing must fail cleanly, never leak --------
def test_extract_json_raises_clean_on_empty_refusal_and_bad():
    from samagra.clients import llm_client as L
    # empty content (e.g. stop_reason=max_tokens with no text)
    empty = type("R", (), {"content": [], "stop_reason": "max_tokens"})()
    with pytest.raises(RuntimeError):
        L._extract_json(empty)
    # refusal
    ref = type("R", (), {"content": [], "stop_reason": "refusal"})()
    with pytest.raises(RuntimeError):
        L._extract_json(ref)
    # non-JSON / truncated body
    block = type("B", (), {"type": "text", "text": "not json {"})()
    bad = type("R", (), {"content": [block], "stop_reason": "end_turn"})()
    with pytest.raises(RuntimeError):
        L._extract_json(bad)


def test_extract_json_error_never_leaks_content():
    from samagra.clients import llm_client as L
    block = type("B", (), {"type": "text", "text": "SECRET-PLAINTEXT not json"})()
    bad = type("R", (), {"content": [block], "stop_reason": "end_turn"})()
    with pytest.raises(RuntimeError) as ei:
        L._extract_json(bad)
    assert "SECRET-PLAINTEXT" not in str(ei.value)


def test_output_config_has_no_unknown_name_field(monkeypatch):
    monkeypatch.delenv("SAMAGRA_LLM_PROVIDER", raising=False)
    sdk = _FakeSDK('{"items": []}')
    c = llm_client.LLMClient(sdk=sdk)
    c.generate_samadhan({"title": "X"}, system="S")
    fmt = sdk.messages.calls[0]["output_config"]["format"]
    assert set(fmt.keys()) == {"type", "schema"}        # no stray "name" (not in SDK 0.96 schema)
