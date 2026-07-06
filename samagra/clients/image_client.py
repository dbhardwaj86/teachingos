"""The ONE image-generation call site (Phase F1, the figure lane) — mirrors
clients/llm_client.py as the single boundary to an external generation API.
Text prompt -> PNG bytes via the OpenAI Images API (gpt-image-1).

SAFETY (PUBLIC REPO): the key is read only from the env var for the SELECTED
provider (OPENAI_API_KEY; config.py load_dotenv's the gitignored .env). It is
NEVER hardcoded, logged, or repr'd. A missing key raises RuntimeError at
construction — callers (figure.preflight / build() preflight) check
`configured()` BEFORE recording any build intent, so a missing key refuses
without wedging an in-flight assignment. `_extract_png` is the image analogue of
llm_client._extract_json: a refusal / empty / malformed response raises a concise
RuntimeError that NEVER echoes the prompt, key, or response body.
"""
from __future__ import annotations

import base64
import os

_PROVIDERS = ("openai",)
_DEFAULT_MODELS = {"openai": "gpt-image-1"}
_KEY_VARS = {"openai": "OPENAI_API_KEY"}
# gpt-image-1 accepts these sizes/qualities; validate fail-closed at construction
# exactly like SAMAGRA_LLM_EFFORT so a typo refuses cleanly, never mid-build.
_SIZES = ("1024x1024", "1024x1536", "1536x1024", "auto")
_QUALITIES = ("low", "medium", "high", "auto")


def _provider_from_env() -> str:
    p = (os.environ.get("SAMAGRA_IMAGE_PROVIDER") or "openai").strip().lower()
    if p not in _PROVIDERS:
        raise RuntimeError(
            f"SAMAGRA_IMAGE_PROVIDER must be one of {_PROVIDERS} (got {p!r})")
    return p


def configured() -> bool:
    """True iff an API key for the SELECTED provider is present. Cheap; no SDK
    import, no network. Preflight calls this BEFORE recording intent. An unknown
    provider reads as unconfigured (fail-closed refusal, no wedge)."""
    try:
        p = _provider_from_env()
    except RuntimeError:
        return False
    return bool(os.environ.get(_KEY_VARS[p]))


def required_key_var() -> str:
    """The env var name of the SELECTED provider's API key (for error messages).
    An unknown provider raises here, same as elsewhere."""
    return _KEY_VARS[_provider_from_env()]


def _extract_png(response) -> bytes:
    """Pull the raw PNG bytes out of an Images-API response. Raises a concise
    RuntimeError — never echoing the prompt / key / response body — on an empty
    response, a missing b64 payload, or non-decodable base64, so the lane surfaces
    a clean error instead of an opaque crash."""
    data = getattr(response, "data", None) or []
    if not data:
        raise RuntimeError("image API returned no image data")
    b64 = getattr(data[0], "b64_json", None)
    if not b64:
        raise RuntimeError("image API response carried no b64_json payload")
    try:
        return base64.b64decode(b64, validate=True)
    except (ValueError, TypeError) as e:
        raise RuntimeError(
            f"image API returned undecodable base64 (chars={len(b64)})") from e


class ImageClient:
    def __init__(self, *, sdk=None, model=None, provider=None):
        self._provider = ((provider or "").strip().lower() or _provider_from_env())
        if self._provider not in _PROVIDERS:
            raise RuntimeError(
                f"provider must be one of {_PROVIDERS} (got {self._provider!r})")
        self._model = (model or os.environ.get("SAMAGRA_IMAGE_MODEL")
                       or _DEFAULT_MODELS[self._provider])
        self._size = (os.environ.get("SAMAGRA_IMAGE_SIZE") or "1024x1024").strip()
        if self._size not in _SIZES:
            raise RuntimeError(
                f"SAMAGRA_IMAGE_SIZE must be one of {_SIZES} (got {self._size!r})")
        self._quality = (os.environ.get("SAMAGRA_IMAGE_QUALITY") or "medium").strip().lower()
        if self._quality not in _QUALITIES:
            raise RuntimeError(
                f"SAMAGRA_IMAGE_QUALITY must be one of {_QUALITIES} (got {self._quality!r})")
        if sdk is not None:
            self._sdk = sdk
            return
        key_var = _KEY_VARS[self._provider]
        key = os.environ.get(key_var)
        if not key:
            raise RuntimeError(
                f"{key_var} is not set — add it to the gitignored .env. "
                "Refusing to start an image build without a key.")
        import openai
        self._sdk = openai.OpenAI(api_key=key)

    def generate(self, prompt: str) -> bytes:
        """One brief -> one PNG. Returns raw PNG bytes (never base64)."""
        resp = self._sdk.images.generate(
            model=self._model,
            prompt=prompt,
            size=self._size,
            quality=self._quality,
            n=1,
        )
        return _extract_png(resp)

    def __repr__(self) -> str:
        return f"ImageClient(provider={self._provider!r}, model={self._model!r})"
