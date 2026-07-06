"""The ONE LLM call site (mirrors clients/{mcd_client,qx_client}.py as the
single boundary to an external subsystem). Generation + the adversarial
ground-truth reviewer for the samadhan lane. Two provider backends:
Anthropic (Messages API, default) and OpenAI (Responses API, opt-in via
SAMAGRA_LLM_PROVIDER=openai).

SAFETY (PUBLIC REPO): the key is read only from the env var for the SELECTED
provider (ANTHROPIC_API_KEY / OPENAI_API_KEY; config.py load_dotenv's the
gitignored .env). It is NEVER hardcoded, logged, or repr'd. A missing key
raises RuntimeError at construction — callers (build() preflight) check
`configured()` BEFORE recording any build intent so a missing key refuses
without wedging an in-flight assignment.
"""
from __future__ import annotations

import json
import os

_MAX_TOKENS = 8000

_PROVIDERS = ("anthropic", "openai")
_DEFAULT_MODELS = {"anthropic": "claude-opus-4-8", "openai": "gpt-5.5"}
_KEY_VARS = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}
_EFFORTS = ("none", "minimal", "low", "medium", "high", "xhigh")

_SAMADHAN_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "concept": {"type": "string"},
                    "misconception": {"type": "string"},
                    "correction": {"type": "string"},
                    "why": {"type": "string"},
                },
                "required": ["concept", "misconception", "correction", "why"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["items"],
    "additionalProperties": False,
}

_REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "verdicts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "idx": {"type": "integer"},
                    "verdict": {"type": "string", "enum": ["ok", "error"]},
                    "rationale": {"type": "string"},
                },
                "required": ["idx", "verdict", "rationale"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["verdicts"],
    "additionalProperties": False,
}

_GEN_TASK = (
    "\n\nTASK: From the chapter below, surface the most important student "
    "MISCONCEPTIONS for JEE/NEET physics. For each, give a JSON item with: "
    "`concept` (the idea), `misconception` (the wrong belief, stated plainly), "
    "`correction` (the right physics), and `why` (why the misconception is "
    "tempting and how to see past it). Ground every claim ONLY in the chapter. "
    "Return 4-8 items as strict JSON {\"items\":[...]}."
)

_REVIEW_SYSTEM = (
    "You are a physics ground-truth checker. You are given a chapter and a list "
    "of misconception->correction items. For EACH item, TRY TO REFUTE it: flag "
    "any 'misconception' that is actually correct physics, any 'correction' that "
    "is wrong or imprecise, and any claim not supported by the chapter. Judge "
    "ONLY against physics and the chapter text — NOT writing style. Default to "
    "verdict 'error' when a claim is unsupported or wrong. Return strict JSON "
    "{\"verdicts\":[{\"idx\":<int>,\"verdict\":\"ok\"|\"error\",\"rationale\":<str>}]}."
)


def _provider_from_env() -> str:
    p = (os.environ.get("SAMAGRA_LLM_PROVIDER") or "anthropic").strip().lower()
    if p not in _PROVIDERS:
        raise RuntimeError(
            f"SAMAGRA_LLM_PROVIDER must be one of {_PROVIDERS} (got {p!r})")
    return p


def configured() -> bool:
    """True iff an API key for the SELECTED provider is present. Cheap; no SDK
    import, no network. build() preflight calls this BEFORE recording intent.
    An unknown provider reads as unconfigured (fail-closed refusal, no wedge)."""
    try:
        p = _provider_from_env()
    except RuntimeError:
        return False
    return bool(os.environ.get(_KEY_VARS[p]))


def _extract_json(response) -> dict:
    """Pull the JSON object out of a Messages response's text blocks. Raises a
    concise RuntimeError — never echoing the content / prompt / key — on a
    refusal, an empty/blocked response, or a non-JSON / truncated body, so the
    lane surfaces a clean error instead of an opaque crash (DEC-7 remediation)."""
    stop = getattr(response, "stop_reason", None)
    if stop == "refusal":
        raise RuntimeError("LLM declined the request (stop_reason=refusal)")
    parts = []
    for block in getattr(response, "content", None) or []:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    raw = "".join(parts).strip()
    if not raw:
        raise RuntimeError(f"LLM returned no text content (stop_reason={stop!r})")
    try:
        return json.loads(raw)
    except ValueError as e:                 # JSONDecodeError is a ValueError subclass
        raise RuntimeError(
            f"LLM response was not valid JSON (stop_reason={stop!r}, "
            f"chars={len(raw)})") from e


def _extract_json_openai(response) -> dict:
    """OpenAI Responses-API sibling of _extract_json: same never-leak contract."""
    status = getattr(response, "status", None)
    if status == "incomplete":
        details = getattr(response, "incomplete_details", None)
        reason = getattr(details, "reason", None)
        raise RuntimeError(f"LLM response incomplete (reason={reason!r})")
    for item in getattr(response, "output", None) or []:
        for part in getattr(item, "content", None) or []:
            if getattr(part, "type", None) == "refusal":
                raise RuntimeError("LLM declined the request (refusal)")
    raw = (getattr(response, "output_text", None) or "").strip()
    if not raw:
        raise RuntimeError(f"LLM returned no text content (status={status!r})")
    try:
        return json.loads(raw)
    except ValueError as e:
        raise RuntimeError(
            f"LLM response was not valid JSON (status={status!r}, "
            f"chars={len(raw)})") from e


class LLMClient:
    def __init__(self, *, sdk=None, model=None, provider=None):
        self._provider = ((provider or "").strip().lower()
                          or _provider_from_env())
        if self._provider not in _PROVIDERS:
            raise RuntimeError(
                f"provider must be one of {_PROVIDERS} (got {self._provider!r})")
        self._model = (model or os.environ.get("SAMAGRA_LLM_MODEL")
                       or _DEFAULT_MODELS[self._provider])
        self._effort = (os.environ.get("SAMAGRA_LLM_EFFORT") or "medium").strip().lower()
        if self._effort not in _EFFORTS:
            raise RuntimeError(
                f"SAMAGRA_LLM_EFFORT must be one of {_EFFORTS} (got {self._effort!r})")
        if sdk is not None:
            self._sdk = sdk
            return
        key_var = _KEY_VARS[self._provider]
        key = os.environ.get(key_var)
        if not key:
            raise RuntimeError(
                f"{key_var} is not set — add it to the gitignored .env. "
                "Refusing to start an LLM build without a key.")
        if self._provider == "anthropic":
            import anthropic
            self._sdk = anthropic.Anthropic(api_key=key)
        else:
            import openai
            self._sdk = openai.OpenAI(api_key=key)

    def _create(self, *, system_text, user_text, schema):
        if self._provider == "anthropic":
            return self._sdk.messages.create(
                model=self._model,
                max_tokens=_MAX_TOKENS,
                thinking={"type": "adaptive"},
                system=[{"type": "text", "text": system_text,
                         "cache_control": {"type": "ephemeral"}}],
                output_config={"format": {"type": "json_schema", "schema": schema}},
                messages=[{"role": "user", "content": user_text}],
            )
        return self._sdk.responses.create(
            model=self._model,
            max_output_tokens=_MAX_TOKENS,
            reasoning={"effort": self._effort},
            input=[{"role": "system", "content": system_text},
                   {"role": "user", "content": user_text}],
            text={"format": {"type": "json_schema", "name": "samagra_output",
                             "schema": schema, "strict": True}},
        )

    def _parse(self, response) -> dict:
        if self._provider == "anthropic":
            return _extract_json(response)
        return _extract_json_openai(response)

    def generate_samadhan(self, chapter: dict, *, system: str) -> dict:
        resp = self._create(
            system_text=system + _GEN_TASK,
            user_text="CHAPTER (ground truth):\n" + json.dumps(chapter, ensure_ascii=False),
            schema=_SAMADHAN_SCHEMA)
        return self._parse(resp)

    def review_samadhan(self, items: list, chapter: dict) -> dict:
        resp = self._create(
            system_text=_REVIEW_SYSTEM,
            user_text=("CHAPTER (ground truth):\n"
                       + json.dumps(chapter, ensure_ascii=False)
                       + "\n\nITEMS:\n" + json.dumps(items, ensure_ascii=False)),
            schema=_REVIEW_SCHEMA)
        return self._parse(resp)

    def __repr__(self) -> str:
        return f"LLMClient(provider={self._provider!r}, model={self._model!r})"
