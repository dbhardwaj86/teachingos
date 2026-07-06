"""Provider-awareness + never-leak tests for the ONE image-generation call site.
All offline: a fake OpenAI Images SDK injected, keys set via monkeypatch only.
No network, ever — mirrors tests/test_llm_client_providers.py's discipline."""
import base64

import pytest

from samagra.clients import image_client
from samagra.clients.image_client import ImageClient, configured, required_key_var


# ---------- fakes ----------

_TINY_PNG = base64.b64encode(b"\x89PNG\r\n\x1a\nFAKEPNGBYTES").decode("ascii")


class _FakeImageResponse:
    """Shape of client.images.generate(...): .data[0].b64_json."""
    def __init__(self, b64=None, empty=False):
        if empty:
            self.data = []
        else:
            self.data = [type("D", (), {"b64_json": b64})()]


class _FakeOpenAIImageSDK:
    """OpenAI-shaped image SDK: .images.generate(**kw)."""
    def __init__(self, response=None, b64=None):
        self.calls = []
        self._response = response if response is not None else _FakeImageResponse(b64=b64 or _TINY_PNG)
        outer = self

        class _Images:
            def generate(self, **kw):
                outer.calls.append(kw)
                return outer._response
        self.images = _Images()


def _openai_client(monkeypatch, response=None, b64=None):
    monkeypatch.setenv("SAMAGRA_IMAGE_PROVIDER", "openai")
    monkeypatch.delenv("SAMAGRA_IMAGE_MODEL", raising=False)
    monkeypatch.delenv("SAMAGRA_IMAGE_SIZE", raising=False)
    monkeypatch.delenv("SAMAGRA_IMAGE_QUALITY", raising=False)
    sdk = _FakeOpenAIImageSDK(response=response, b64=b64)
    return ImageClient(sdk=sdk), sdk


# ---------- provider + knob resolution ----------

def test_default_provider_is_openai(monkeypatch):
    monkeypatch.delenv("SAMAGRA_IMAGE_PROVIDER", raising=False)
    monkeypatch.delenv("SAMAGRA_IMAGE_MODEL", raising=False)
    c = ImageClient(sdk=_FakeOpenAIImageSDK())
    assert c._provider == "openai"
    assert c._model == "gpt-image-1"


def test_model_env_overrides(monkeypatch):
    monkeypatch.setenv("SAMAGRA_IMAGE_PROVIDER", "openai")
    monkeypatch.setenv("SAMAGRA_IMAGE_MODEL", "gpt-image-1-mini")
    assert ImageClient(sdk=_FakeOpenAIImageSDK())._model == "gpt-image-1-mini"


def test_unknown_provider_fails_closed(monkeypatch):
    monkeypatch.setenv("SAMAGRA_IMAGE_PROVIDER", "midjourney")
    with pytest.raises(RuntimeError):
        ImageClient(sdk=_FakeOpenAIImageSDK())


def test_unknown_size_fails_closed(monkeypatch):
    monkeypatch.setenv("SAMAGRA_IMAGE_PROVIDER", "openai")
    monkeypatch.setenv("SAMAGRA_IMAGE_SIZE", "999x999")
    with pytest.raises(RuntimeError):
        ImageClient(sdk=_FakeOpenAIImageSDK())


def test_unknown_quality_fails_closed(monkeypatch):
    monkeypatch.setenv("SAMAGRA_IMAGE_PROVIDER", "openai")
    monkeypatch.setenv("SAMAGRA_IMAGE_QUALITY", "ultra")
    with pytest.raises(RuntimeError):
        ImageClient(sdk=_FakeOpenAIImageSDK())


def test_default_size_and_quality(monkeypatch):
    monkeypatch.setenv("SAMAGRA_IMAGE_PROVIDER", "openai")
    monkeypatch.delenv("SAMAGRA_IMAGE_SIZE", raising=False)
    monkeypatch.delenv("SAMAGRA_IMAGE_QUALITY", raising=False)
    c = ImageClient(sdk=_FakeOpenAIImageSDK())
    assert c._size == "1024x1024"
    assert c._quality == "medium"


# ---------- configured() / required_key_var() ----------

def test_configured_checks_selected_provider_key(monkeypatch):
    monkeypatch.setenv("SAMAGRA_IMAGE_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert configured() is False
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    assert configured() is True


def test_configured_false_on_unknown_provider(monkeypatch):
    monkeypatch.setenv("SAMAGRA_IMAGE_PROVIDER", "midjourney")
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    assert configured() is False


def test_required_key_var_openai(monkeypatch):
    monkeypatch.setenv("SAMAGRA_IMAGE_PROVIDER", "openai")
    assert required_key_var() == "OPENAI_API_KEY"


def test_missing_key_refuses_construction(monkeypatch):
    monkeypatch.setenv("SAMAGRA_IMAGE_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        ImageClient()


# ---------- generate round-trip: request shape + b64 -> bytes ----------

def test_generate_returns_png_bytes_and_pins_request_shape(monkeypatch):
    c, sdk = _openai_client(monkeypatch)
    out = c.generate("a clean physics diagram")
    assert out == base64.b64decode(_TINY_PNG)   # raw PNG bytes, not b64
    kw = sdk.calls[0]
    assert kw["model"] == "gpt-image-1"
    assert kw["prompt"] == "a clean physics diagram"
    assert kw["size"] == "1024x1024"
    assert kw["quality"] == "medium"
    assert kw["n"] == 1


def test_generate_honors_env_knobs(monkeypatch):
    monkeypatch.setenv("SAMAGRA_IMAGE_PROVIDER", "openai")
    monkeypatch.setenv("SAMAGRA_IMAGE_SIZE", "1024x1536")
    monkeypatch.setenv("SAMAGRA_IMAGE_QUALITY", "high")
    sdk = _FakeOpenAIImageSDK()
    ImageClient(sdk=sdk).generate("p")
    kw = sdk.calls[0]
    assert kw["size"] == "1024x1536"
    assert kw["quality"] == "high"


# ---------- never-leak extraction (refusal / empty / bad-b64) ----------

def test_empty_data_raises_clean(monkeypatch):
    c, _ = _openai_client(monkeypatch, response=_FakeImageResponse(empty=True))
    with pytest.raises(RuntimeError) as e:
        c.generate("secret prompt text")
    assert "secret prompt text" not in str(e.value)


def test_none_b64_raises_clean(monkeypatch):
    c, _ = _openai_client(monkeypatch, response=_FakeImageResponse(b64=None))
    with pytest.raises(RuntimeError) as e:
        c.generate("secret prompt text")
    assert "secret prompt text" not in str(e.value)


def test_bad_base64_raises_clean_never_echoes_body(monkeypatch):
    c, _ = _openai_client(monkeypatch, response=_FakeImageResponse(b64="!!!not-base64!!!"))
    with pytest.raises(RuntimeError) as e:
        c.generate("secret prompt text")
    assert "!!!not-base64!!!" not in str(e.value)
    assert "secret prompt text" not in str(e.value)


def test_repr_never_contains_key(monkeypatch):
    monkeypatch.setenv("SAMAGRA_IMAGE_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-super-secret-image")
    c = ImageClient(sdk=_FakeOpenAIImageSDK())
    assert "sk-super-secret-image" not in repr(c)
    assert "openai" in repr(c) and "gpt-image-1" in repr(c)
