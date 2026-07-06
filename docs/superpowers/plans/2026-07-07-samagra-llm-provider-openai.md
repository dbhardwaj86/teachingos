# LLM Provider Mini-Slice (OpenAI backend) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `samagra/clients/llm_client.py` provider-aware (anthropic default, openai
opt-in via `SAMAGRA_LLM_PROVIDER`) so the samadhan lane runs live on OpenAI `gpt-5.5`,
with zero consumer changes.

**Architecture:** One module rework. Provider resolved env-first (fail-closed on unknown),
per-provider model defaults + key vars, OpenAI Responses API with `reasoning.effort` +
strict `json_schema` output, per-provider response extraction with the same
never-leak-content hardening. Public surface unchanged.

**Tech Stack:** Python 3.11, openai>=2.32 (installed), anthropic>=0.96 (path unchanged),
pytest with injectable fake SDKs (offline).

**Spec:** `docs/superpowers/specs/2026-07-07-samagra-llm-provider-openai-design.md`
**Branch:** `feature/llm-provider-openai`

---

### Task 1: Provider-aware `llm_client.py` (TDD)

**Files:**
- Modify: `samagra/clients/llm_client.py`
- Create: `tests/test_llm_client_providers.py`

- [ ] **Step 1: Write the failing tests** — `tests/test_llm_client_providers.py`:

```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_llm_client_providers.py -q`
Expected: FAIL (`_provider` attribute missing / unknown-provider not raising / openai
fake never called).

- [ ] **Step 3: Rework `samagra/clients/llm_client.py`**

Keep the module docstring's intent but update it (it is now the ONE LLM call site with
two provider backends). Keep `_SAMADHAN_SCHEMA`, `_REVIEW_SCHEMA`, `_GEN_TASK`,
`_REVIEW_SYSTEM`, `_MAX_TOKENS`, `_extract_json` byte-identical. Add/replace:

```python
_PROVIDERS = ("anthropic", "openai")
_DEFAULT_MODELS = {"anthropic": "claude-opus-4-8", "openai": "gpt-5.5"}
_KEY_VARS = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}
_EFFORTS = ("none", "minimal", "low", "medium", "high", "xhigh")


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
```

`LLMClient` becomes:

```python
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
```

`generate_samadhan` / `review_samadhan` change ONLY their final line to
`return self._parse(resp)`. `__repr__` becomes
`f"LLMClient(provider={self._provider!r}, model={self._model!r})"`.

- [ ] **Step 4: Run new + standing LLM tests**

Run: `python -m pytest tests/test_llm_client_providers.py tests/test_llm_client.py tests/test_factory_samadhan.py tests/test_factory_samadhan_wiring.py -q`
Expected: ALL PASS (standing D2 tests untouched and green — the back-compat proof).

- [ ] **Step 5: Commit**

```bash
git add samagra/clients/llm_client.py tests/test_llm_client_providers.py
git commit -m "feat(llm): provider-aware LLM client — OpenAI Responses backend beside Anthropic

SAMAGRA_LLM_PROVIDER selects the backend (default anthropic, byte-identical
D2 back-compat). OpenAI path: gpt-5.5 default, reasoning effort from
SAMAGRA_LLM_EFFORT, strict json_schema output, same never-leak extraction
hardening. configured() is provider-aware; unknown provider/effort fail
closed. DEC-8 reviewer firewall structural on both paths."
```

---

### Task 2: Live smoke provider-aware + docs + RUN the live smoke

**Files:**
- Modify: `tests/test_samadhan_live_smoke.py` (read first — keep its gate flag)
- Modify: `.env.example`, `requirements.txt`

- [ ] **Step 1:** Read `tests/test_samadhan_live_smoke.py`. If it hardcodes
`ANTHROPIC_API_KEY` checks, make the skip condition provider-aware by delegating to
`llm_client.configured()` (plus the existing `SAMAGRA_LIVE_LLM_SMOKE` flag). Keep it
opt-in exactly as before.
- [ ] **Step 2:** `requirements.txt`: add `openai>=2.32` next to `anthropic>=0.96`.
- [ ] **Step 3:** `.env.example` LLM block: add
```
# Provider: anthropic (default) | openai. Model + effort default per provider
# (claude-opus-4-8 / gpt-5.5 + medium). Key read ONLY for the selected provider.
SAMAGRA_LLM_PROVIDER=
OPENAI_API_KEY=
SAMAGRA_LLM_EFFORT=
```
- [ ] **Step 4:** Commit docs+smoke:
```bash
git add tests/test_samadhan_live_smoke.py requirements.txt .env.example
git commit -m "docs(llm): provider env template + openai requirement; live smoke provider-aware"
```
- [ ] **Step 5: RUN the live smoke ONCE** (the real key is in .env; the controller
authorizes this single live call):
`$env:SAMAGRA_LIVE_LLM_SMOKE='1'; python -m pytest tests/test_samadhan_live_smoke.py -v`
Expected: PASS (a real gpt-5.5 generation + adversarial review round-trip). Record the
runtime + item/verdict counts in the task report. If it fails, capture the exact error —
do NOT commit a fix without understanding it (API-shape errors here mean the Responses
call is wrong and Task 1 must be corrected).

---

### Task 3: Full gates

- [ ] `python -m pytest -q --junit-xml=<scratchpad>\gate-llm-slice.xml` → read xml attrs.
Expected: ~713 tests (695 + ~18 new), failures=0, skipped=2 (live smokes counted per
their gates; the LLM smoke may show as passed if run with the flag, else skipped).
- [ ] Frontend untouched — no vitest rerun needed (record 639 baseline stands).

---

### Task 4: Codex pre-merge review 32 + trackers + merge

- [ ] Dispatch the Codex review (house convention review 32) on
`git diff main...feature/llm-provider-openai`, focus: the generation boundary — key
handling (env-only, never logged/repr'd), fail-closed provider/effort/key resolution,
DEC-8 reviewer firewall on the openai path, no new prod write path, standing-test
back-compat, Responses-API correctness. Report →
`docs/codex-reviews/32-llm-provider-openai-premerge.report.md`.
- [ ] Remediate any findings TDD; re-run gates; commit the report.
- [ ] Trackers: CLAUDE.md ✅ block + NEXT, HANDOFF.md banner, STATUS.html/SUMMARY.html,
spec Status flip to SHIPPED, memory.
- [ ] `git checkout main && git merge --ff-only feature/llm-provider-openai` (verify
branch ref at true HEAD first). Push is OWNER-performed.
- [ ] Restart samagra server (:8799) so the lane picks up the new client, then verify
`samagra factory plan textbook:<slug> --lane samadhan` + approve + build produces a
captured/changes brief end-to-end live (the first-ever live samadhan build).
