"""DEC-8-firewalled vision reviewer for the figure lane. Offline: fake SDKs.
review_figure NEVER takes a StyleSeed argument (structural firewall) and sends the
PNG as a vision input part alongside the brief + section text."""
import base64
import inspect
import json

import pytest

from samagra.clients import llm_client
from samagra.clients.llm_client import LLMClient


class _FakeAnthropicResponse:
    def __init__(self, text):
        self.stop_reason = "end_turn"
        self.content = [type("B", (), {"text": text})()]


class _FakeAnthropicSDK:
    def __init__(self, payload):
        self.calls = []
        outer = self

        class _Messages:
            def create(self, **kw):
                outer.calls.append(kw)
                return _FakeAnthropicResponse(json.dumps(payload))
        self.messages = _Messages()


class _FakeOpenAIResponse:
    def __init__(self, text):
        self.status = "completed"
        self.output_text = text
        self.output = []


class _FakeOpenAISDK:
    def __init__(self, payload):
        self.calls = []
        outer = self

        class _Responses:
            def create(self, **kw):
                outer.calls.append(kw)
                return _FakeOpenAIResponse(json.dumps(payload))
        self.responses = _Responses()


_PNG = b"\x89PNG\r\n\x1a\nFAKE"
_VERDICTS = {"verdicts": [{"idx": 0, "verdict": "ok", "rationale": "matches brief"}]}


def test_review_figure_signature_has_no_styleseed():
    # DEC-8 firewall is STRUCTURAL: the vision reviewer cannot receive a StyleSeed
    # because its signature has no such parameter.
    params = list(inspect.signature(LLMClient.review_figure).parameters)
    assert params == ["self", "png_bytes", "brief", "section_text"]


def test_review_figure_anthropic_round_trip(monkeypatch):
    monkeypatch.delenv("SAMAGRA_LLM_PROVIDER", raising=False)
    sdk = _FakeAnthropicSDK(_VERDICTS)
    out = LLMClient(sdk=sdk).review_figure(_PNG, "brief text", "section text")
    assert out == _VERDICTS
    kw = sdk.calls[0]
    # The reviewer system is the frozen figure-review checker, never a StyleSeed.
    sys_text = kw["system"][0]["text"]
    assert "diagram" in sys_text.lower()
    # The PNG is carried as a base64 image block; brief + section text are present.
    blob = json.dumps(kw["messages"], ensure_ascii=False)
    assert base64.b64encode(_PNG).decode("ascii") in blob
    assert "brief text" in blob and "section text" in blob


def test_review_figure_openai_round_trip(monkeypatch):
    monkeypatch.setenv("SAMAGRA_LLM_PROVIDER", "openai")
    sdk = _FakeOpenAISDK(_VERDICTS)
    out = LLMClient(sdk=sdk).review_figure(_PNG, "brief text", "section text")
    assert out == _VERDICTS
    kw = sdk.calls[0]
    sys_text = kw["input"][0]["content"]
    assert isinstance(sys_text, str) and "diagram" in sys_text.lower()
    blob = json.dumps(kw["input"], ensure_ascii=False)
    assert base64.b64encode(_PNG).decode("ascii") in blob


def test_openai_vision_image_part_matches_sdk_typeddict(monkeypatch):
    # Pin the input_image content part's shape against the INSTALLED openai SDK's
    # TypedDict, so a silent SDK contract drift breaks here, not live. The SDK
    # declares `detail` Required (the server defaults it, but house style =
    # explicit knobs), so we send it explicitly and assert it.
    from openai.types.responses import ResponseInputImageParam

    monkeypatch.setenv("SAMAGRA_LLM_PROVIDER", "openai")
    sdk = _FakeOpenAISDK(_VERDICTS)
    LLMClient(sdk=sdk).review_figure(_PNG, "brief text", "section text")
    kw = sdk.calls[0]
    user_content = kw["input"][1]["content"]
    part = next(p for p in user_content if p.get("type") == "input_image")
    assert set(part.keys()) <= set(ResponseInputImageParam.__annotations__.keys())
    assert part["detail"] == "auto"
    assert part["type"] == "input_image"
