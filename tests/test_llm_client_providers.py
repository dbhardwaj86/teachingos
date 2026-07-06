"""Provider-awareness tests for the ONE LLM call site. All offline: fake SDKs
injected, keys set via monkeypatch only. No network, ever."""
import json

import pytest

from samagra.clients import llm_client
from samagra.clients.llm_client import LLMClient, configured


# ---------- fakes ----------

class _FakeAnthropicResponse:
    def __init__(self, text):
        self.stop_reason = "end_turn"
        self.content = [type("B", (), {"text": text})()]


class _FakeAnthropicSDK:
    """Anthropic-shaped: .messages.create(**kw)."""
    def __init__(self, payload):
        self.calls = []
        self._payload = payload
        outer = self

        class _Messages:
            def create(self, **kw):
                outer.calls.append(kw)
                return _FakeAnthropicResponse(json.dumps(outer._payload))
        self.messages = _Messages()


class _FakeOpenAIResponse:
    def __init__(self, text, status="completed", refusal=False):
        self.status = status
        self.output_text = text
        if refusal:
            part = type("P", (), {"type": "refusal", "refusal": "no"})()
            self.output = [type("I", (), {"content": [part]})()]
            self.output_text = ""
        else:
            self.output = []


class _FakeOpenAISDK:
    """OpenAI-shaped: .responses.create(**kw)."""
    def __init__(self, payload=None, response=None):
        self.calls = []
        self._response = response or _FakeOpenAIResponse(json.dumps(payload))
        outer = self

        class _Responses:
            def create(self, **kw):
                outer.calls.append(kw)
                return outer._response
        self.responses = _Responses()


_CHAPTER = {"slug": "demo", "sections": []}
_ITEMS = [{"concept": "c", "misconception": "m", "correction": "r", "why": "w"}]
_GEN_PAYLOAD = {"items": _ITEMS}
_REVIEW_PAYLOAD = {"verdicts": [{"idx": 0, "verdict": "ok", "rationale": "fine"}]}


# ---------- provider resolution ----------

def test_default_provider_is_anthropic(monkeypatch):
    monkeypatch.delenv("SAMAGRA_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("SAMAGRA_LLM_MODEL", raising=False)
    c = LLMClient(sdk=_FakeAnthropicSDK(_GEN_PAYLOAD))
    assert c._provider == "anthropic"
    assert c._model == "claude-opus-4-8"


def test_openai_provider_from_env(monkeypatch):
    monkeypatch.setenv("SAMAGRA_LLM_PROVIDER", "openai")
    monkeypatch.delenv("SAMAGRA_LLM_MODEL", raising=False)
    c = LLMClient(sdk=_FakeOpenAISDK(_GEN_PAYLOAD))
    assert c._provider == "openai"
    assert c._model == "gpt-5.5"


def test_model_env_overrides_either_provider(monkeypatch):
    monkeypatch.setenv("SAMAGRA_LLM_PROVIDER", "openai")
    monkeypatch.setenv("SAMAGRA_LLM_MODEL", "gpt-5.5-mini")
    assert LLMClient(sdk=_FakeOpenAISDK(_GEN_PAYLOAD))._model == "gpt-5.5-mini"


def test_unknown_provider_fails_closed(monkeypatch):
    monkeypatch.setenv("SAMAGRA_LLM_PROVIDER", "gemini")
    with pytest.raises(RuntimeError):
        LLMClient(sdk=_FakeOpenAISDK(_GEN_PAYLOAD))


def test_unknown_effort_fails_closed(monkeypatch):
    monkeypatch.setenv("SAMAGRA_LLM_PROVIDER", "openai")
    monkeypatch.setenv("SAMAGRA_LLM_EFFORT", "turbo")
    with pytest.raises(RuntimeError):
        LLMClient(sdk=_FakeOpenAISDK(_GEN_PAYLOAD))


# ---------- configured() ----------

def test_configured_checks_selected_provider_key(monkeypatch):
    monkeypatch.setenv("SAMAGRA_LLM_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "unused-other-provider-key")
    assert configured() is False
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    assert configured() is True


def test_configured_false_on_unknown_provider(monkeypatch):
    monkeypatch.setenv("SAMAGRA_LLM_PROVIDER", "gemini")
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    assert configured() is False


def test_missing_key_refuses_construction(monkeypatch):
    monkeypatch.setenv("SAMAGRA_LLM_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        LLMClient()


# ---------- openai round-trips ----------

def _openai_client(monkeypatch, payload=None, response=None):
    monkeypatch.setenv("SAMAGRA_LLM_PROVIDER", "openai")
    monkeypatch.delenv("SAMAGRA_LLM_MODEL", raising=False)
    monkeypatch.delenv("SAMAGRA_LLM_EFFORT", raising=False)
    sdk = _FakeOpenAISDK(payload=payload, response=response)
    return LLMClient(sdk=sdk), sdk


def test_openai_generate_samadhan_round_trip(monkeypatch):
    c, sdk = _openai_client(monkeypatch, payload=_GEN_PAYLOAD)
    out = c.generate_samadhan(_CHAPTER, system="STYLE")
    assert out == _GEN_PAYLOAD
    kw = sdk.calls[0]
    assert kw["model"] == "gpt-5.5"
    assert kw["reasoning"] == {"effort": "medium"}
    assert kw["text"]["format"]["type"] == "json_schema"
    assert kw["text"]["format"]["strict"] is True
    roles = [m["role"] for m in kw["input"]]
    assert roles == ["system", "user"]
    assert kw["input"][0]["content"].startswith("STYLE")


def test_openai_review_never_gets_system_styleseed(monkeypatch):
    c, sdk = _openai_client(monkeypatch, payload=_REVIEW_PAYLOAD)
    out = c.review_samadhan(_ITEMS, _CHAPTER)
    assert out == _REVIEW_PAYLOAD
    system_text = sdk.calls[0]["input"][0]["content"]
    assert "ground-truth checker" in system_text  # the frozen reviewer system
    assert "STYLE" not in system_text


def test_openai_effort_env_passthrough(monkeypatch):
    monkeypatch.setenv("SAMAGRA_LLM_EFFORT", "high")
    monkeypatch.setenv("SAMAGRA_LLM_PROVIDER", "openai")
    sdk = _FakeOpenAISDK(payload=_GEN_PAYLOAD)
    LLMClient(sdk=sdk).generate_samadhan(_CHAPTER, system="s")
    assert sdk.calls[0]["reasoning"] == {"effort": "high"}


# ---------- openai failure hardening (never leak content/key) ----------

def test_openai_refusal_raises_clean(monkeypatch):
    c, _ = _openai_client(
        monkeypatch, response=_FakeOpenAIResponse("", refusal=True))
    with pytest.raises(RuntimeError) as e:
        c.generate_samadhan(_CHAPTER, system="s")
    assert "refus" in str(e.value).lower()


def test_openai_incomplete_raises_clean(monkeypatch):
    c, _ = _openai_client(
        monkeypatch, response=_FakeOpenAIResponse("{}", status="incomplete"))
    with pytest.raises(RuntimeError):
        c.generate_samadhan(_CHAPTER, system="s")


def test_openai_empty_raises_clean(monkeypatch):
    c, _ = _openai_client(monkeypatch, response=_FakeOpenAIResponse("   "))
    with pytest.raises(RuntimeError):
        c.generate_samadhan(_CHAPTER, system="s")


def test_openai_bad_json_never_echoes_body(monkeypatch):
    secret_body = "SECRET-CONTENT not json"
    c, _ = _openai_client(monkeypatch, response=_FakeOpenAIResponse(secret_body))
    with pytest.raises(RuntimeError) as e:
        c.generate_samadhan(_CHAPTER, system="s")
    assert "SECRET-CONTENT" not in str(e.value)


def test_repr_never_contains_key(monkeypatch):
    monkeypatch.setenv("SAMAGRA_LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-super-secret")
    c = LLMClient(sdk=_FakeOpenAISDK(_GEN_PAYLOAD))
    assert "sk-super-secret" not in repr(c)


# ---------- anthropic back-compat ----------

def test_anthropic_path_unchanged(monkeypatch):
    monkeypatch.delenv("SAMAGRA_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("SAMAGRA_LLM_MODEL", raising=False)
    sdk = _FakeAnthropicSDK(_GEN_PAYLOAD)
    out = LLMClient(sdk=sdk).generate_samadhan(_CHAPTER, system="STYLE")
    assert out == _GEN_PAYLOAD
    kw = sdk.calls[0]
    assert kw["model"] == "claude-opus-4-8"
    assert kw["thinking"] == {"type": "adaptive"}
    assert kw["output_config"]["format"]["type"] == "json_schema"
