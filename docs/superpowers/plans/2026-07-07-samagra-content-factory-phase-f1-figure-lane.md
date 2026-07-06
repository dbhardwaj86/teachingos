# Phase F1 — figure lane Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> Each task is a fresh implementer: write the failing test FIRST, watch it fail, write the
> minimal code, watch it pass, then commit. No task starts before the previous one is green.

**Goal:** Ship SAMAGRA's first image-generation lane. One textbook chapter's
author-written `image-need` briefs → generated PNG figures → a vision review that
records a per-figure verdict → a self-contained data-URI gallery HTML (+ manifest JSON +
loose PNGs) written locally, routed through build()'s existing `kind="llm"` path. The
default posture (`SAMAGRA_FIGURE_AUTOCAPTURE` off) routes every figure build to `changes`
for owner eyes — a generated diagram is a draft, never a silent capture.

**Architecture:** A new call site `samagra/clients/image_client.py` (the ONE image API
boundary, mirroring `llm_client.py`'s provider pattern: `SAMAGRA_IMAGE_PROVIDER` default
`openai`, `gpt-image-1`, injectable fake SDK, key env-only never logged/repr'd,
`configured()` / `required_key_var()`, fail-closed size/quality, never-leak `_extract_png`).
A new engine `samagra/factory/figure.py` (`build_figures(slug, *, image_client=None,
vision_client=None)`): pure deterministic target selection from `image-need` briefs (cap 6)
→ generate PNGs (deterministic `fig-NN.png`, stale `fig-*.png` cleared first) → vision-review
each via the existing `llm_client.review_figure` (refute-framed, fail-closed) → write
`<slug>-figures/` PNGs + `<slug>-figures.json` + a data-URI `<slug>-figures.html` gallery →
return a factory-compatible result dict whose `items`/`errors`/`verdicts` keys the existing
`kind="llm"` gate already consumes. Wiring is minimal: a `figure` Line (`kind="llm"`,
`auto_fan=False`), a `run_line` special-case ahead of the generic samadhan branch, a
lane-dispatched build() preflight, a `validate_product` binary branch, and one explicit
`needs_review` clause honoring `SAMAGRA_FIGURE_AUTOCAPTURE`. No new prod write path, no
migration, no new assignment status, publish gate untouched.

**Tech Stack:** Python 3.11, `openai>=2.32` (installed 2.44.0 — `images.generate` ships in
it; no new dependency), pytest with injectable fake SDKs (fully offline). Windows; tests via
`.\.venv\Scripts\python.exe -m pytest`.

**Spec:** `docs/superpowers/specs/2026-07-07-samagra-content-factory-phase-f1-figure-lane-design.md`
**Branch:** `feature/content-factory-phase-f1-figures` (already checked out)

**Baseline gate before Task 1:** 713 pytest (2 skips = opt-in live LLM smoke + soon the
image smoke) / 639 vitest. Frontend is untouched by F1, so the 639 vitest baseline is
unchanged and is asserted-by-inspection in Task 6 (no vitest rerun needed).

**Corpus fact (verified against real chapters):** an `image-need` block is exactly
`{"type": "image-need", "brief": "<author prose>"}`. Sections carry `title`; the chapter
carries `title`. 52 such blocks across 40 of the 59 chapters (circular-motion = 1,
capacitance = 1, centre-of-mass-all-in-one = 2, gauss-law = 0). The plan's loader keys on
`type == "image-need"` and the `brief` field — exact.

**Commit discipline (house rule, learned the hard way):** serialize ALL git — never run a
background git commit while a subagent is also committing. Each task commits exactly once at
its end.

---

### Task 1: `image_client.py` — the ONE image-generation call site (TDD)

**Files:**
- Create: `samagra/clients/image_client.py`
- Create: `tests/test_image_client.py`

- [ ] **Step 1: Write the failing tests** — `tests/test_image_client.py`:

```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_image_client.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'samagra.clients.image_client'`
(the module does not exist yet).

- [ ] **Step 3: Minimal implementation** — `samagra/clients/image_client.py`:

```python
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
```

- [ ] **Step 4: Run again**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_image_client.py -q`
Expected: PASS (all ~18 tests green).

- [ ] **Step 5: Commit**

```bash
git add samagra/clients/image_client.py tests/test_image_client.py
git commit -m "feat(f1): image_client — the ONE image-generation call site (OpenAI gpt-image-1)

SAMAGRA_IMAGE_PROVIDER selects the backend (default openai, the only F1
backend). images.generate(gpt-image-1) with size/quality validated fail-closed
at construction. generate() returns raw PNG bytes; _extract_png never leaks the
prompt/key/body on refusal/empty/bad-base64. Key env-only, never logged/repr'd.
configured()/required_key_var() provider-aware for the anti-wedge preflight.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: `figure.py` — pure target selection + prompt build (TDD)

**Files:**
- Create: `samagra/factory/figure.py`
- Create: `tests/test_factory_figure.py`

The deterministic, I/O-free half: `_targets(content)` selects `image-need` blocks in
document order, caps at `_FIGURE_CAP`, and builds each prompt from the fixed style
preamble + chapter title + section title + the verbatim `brief`. No SDK, no network, no
disk (beyond the caller's fixture) — the pure engine unit-tested against a frozen fixture.

- [ ] **Step 1: Write the failing tests** — `tests/test_factory_figure.py`:

```python
"""Phase F1 figure lane — pure target selection + prompt build. Offline; a frozen
in-memory fixture chapter, no live corpus dependency."""
import pytest

from samagra.factory import figure


# A frozen fixture chapter mirroring the REAL schema:
#   chapter.title; section.title; block {"type":"image-need","brief": "..."}.
_CHAPTER = {
    "title": "Circular Motion",
    "sections": [
        {"title": "Uniform circular motion",
         "blocks": [
             {"type": "prose", "html": "<p>text</p>"},
             {"type": "image-need", "brief": "A disc spinning about a vertical axis."},
         ]},
        {"title": "Coriolis force",
         "blocks": [
             {"type": "equation", "tex": "F=ma"},
             {"type": "image-need", "brief": "A rotating frame with the Coriolis vector."},
             {"type": "callout", "html": "<div>note</div>"},
         ]},
    ],
}


def test_targets_selects_only_image_need_in_document_order():
    ts = figure._targets(_CHAPTER)
    assert len(ts) == 2
    assert ts[0]["brief"] == "A disc spinning about a vertical axis."
    assert ts[1]["brief"] == "A rotating frame with the Coriolis vector."
    # idx is 1-based document order; section title carried alongside.
    assert [t["idx"] for t in ts] == [1, 2]
    assert ts[0]["section"] == "Uniform circular motion"
    assert ts[1]["section"] == "Coriolis force"


def test_targets_prompt_is_preamble_plus_frame_plus_brief_verbatim():
    ts = figure._targets(_CHAPTER)
    p = ts[1]["prompt"]
    assert p.startswith(figure._STYLE_PREAMBLE)
    assert "Chapter: Circular Motion." in p
    assert "Section: Coriolis force." in p
    assert "A rotating frame with the Coriolis vector." in p   # brief verbatim


def test_targets_empty_when_no_image_need():
    ch = {"title": "Gauss Law", "sections": [
        {"title": "S1", "blocks": [{"type": "prose", "html": "<p>x</p>"}]}]}
    assert figure._targets(ch) == []


def test_targets_caps_at_figure_cap(monkeypatch):
    monkeypatch.setattr(figure, "_FIGURE_CAP", 2)
    ch = {"title": "Many", "sections": [
        {"title": "S", "blocks": [
            {"type": "image-need", "brief": f"fig {i}"} for i in range(5)]}]}
    ts = figure._targets(ch)
    assert len(ts) == 2
    assert [t["brief"] for t in ts] == ["fig 0", "fig 1"]   # first N in order


def test_figure_cap_default_is_six():
    assert figure._FIGURE_CAP == 6
```

- [ ] **Step 2: Run to verify failure**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_factory_figure.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'samagra.factory.figure'`.

- [ ] **Step 3: Minimal implementation** — `samagra/factory/figure.py` (this task
    creates the module with ONLY the pure pieces; Task 3 extends the SAME file with
    `build_figures` / `preflight` / the HTML gallery):

```python
"""The figure lane engine (Phase F1 — the first image-generation lane).

One textbook chapter (seed 'textbook:<slug>') -> rendered PNG figures for its
author-written `image-need` briefs: select targets (deterministic, document order,
capped) -> generate a PNG per brief -> an adversarial vision reviewer anchored ONLY
to the chapter ground truth (the brief + section text + the image; NEVER the
StyleSeed) -> write <slug>-figures/ PNGs + <slug>-figures.json + a self-contained
data-URI gallery <slug>-figures.html under EXPORT_DIR/<slug>/.

The prompt is DETERMINISTIC: a frozen style preamble + chapter/section frame + the
brief verbatim. No StyleSeed enters the figure prompt (E: minimal), so the DEC-8
reviewer firewall is trivially structural — there is no StyleSeed anywhere near
this lane. The publish gate is untouched: this writes LOCAL artifacts only;
capturing is build()'s job, and F1 defaults conservative (SAMAGRA_FIGURE_AUTOCAPTURE
off -> every build routes to `changes`).
"""
from __future__ import annotations

import os

_FIGURE_CAP = int(os.environ.get("SAMAGRA_FIGURE_CAP", "6"))

# Frozen module constant — changing it is a reviewed commit. No StyleSeed (E).
_STYLE_PREAMBLE = (
    "A clean, labelled physics diagram for a JEE/NEET textbook. Neutral line-art "
    "on a transparent/white background, one accent colour, legible labels. No "
    "photorealism."
)


def _targets(content: dict) -> list[dict]:
    """PURE: every `image-need` block in document order, capped at _FIGURE_CAP.
    Each target = {idx (1-based doc order), section, brief, prompt}. The prompt is
    the frozen preamble + a chapter/section frame + the brief verbatim (no LLM in
    the prompt-build step, no StyleSeed)."""
    title = str(content.get("title", "") or "")
    targets: list[dict] = []
    idx = 0
    for section in content.get("sections", []) or []:
        sec_title = str(section.get("title", "") or "")
        for block in section.get("blocks", []) or []:
            if block.get("type") != "image-need":
                continue
            idx += 1
            brief = str(block.get("brief", "") or "")
            prompt = (
                f"{_STYLE_PREAMBLE}\n"
                f"Chapter: {title}.  Section: {sec_title}.\n"
                f"Figure brief: {brief}"
            )
            targets.append({"idx": idx, "section": sec_title,
                            "brief": brief, "prompt": prompt})
            if len(targets) >= _FIGURE_CAP:
                return targets
    return targets
```

- [ ] **Step 4: Run again**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_factory_figure.py -q`
Expected: PASS (5 tests green).

- [ ] **Step 5: Commit**

```bash
git add samagra/factory/figure.py tests/test_factory_figure.py
git commit -m "feat(f1): figure lane target selection — image-need briefs, capped, deterministic prompt

_targets(content) selects every image-need block in document order (capped at
_FIGURE_CAP=6, env SAMAGRA_FIGURE_CAP), building each prompt from a frozen style
preamble + chapter/section frame + the brief verbatim. Pure, no I/O, no StyleSeed,
no LLM — unit-tested against a frozen fixture matching the real corpus schema.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: `figure.py` — generation + vision review + artifact write (TDD)

**Files:**
- Modify: `samagra/factory/figure.py` (add `build_figures`, `preflight`, gallery HTML)
- Modify: `samagra/clients/llm_client.py` (add `review_figure` + `_REVIEW_FIGURE_SYSTEM`
  + a per-image vision-input path)
- Modify: `tests/test_factory_figure.py` (append `build_figures` / `preflight` tests)
- Create: `tests/test_llm_client_review_figure.py`

`build_figures(slug, *, image_client=None, vision_client=None)` clears stale `fig-*.png`,
generates a PNG per target, vision-reviews each (fail-closed), writes the PNGs + JSON
manifest + data-URI gallery HTML, and returns the factory-compatible result dict. A raise
in ANY image call raises the whole build (no partial return) — build()'s `except` rolls it
back retryably. `preflight` asserts chapter-present + image client configured + vision
client configured (NO StyleSeed requirement).

`llm_client.review_figure(png_bytes, brief, section_text)` is the DEC-8-firewalled vision
reviewer — it NEVER receives a StyleSeed argument (structural). It reuses `_REVIEW_SCHEMA`'s
verdict shape and sends the PNG as a vision input part.

- [ ] **Step 1a: Write the failing `review_figure` tests** — `tests/test_llm_client_review_figure.py`:

```python
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
```

- [ ] **Step 1b: Write the failing `build_figures` / `preflight` tests** — append to
    `tests/test_factory_figure.py`:

```python
# --- Task 3: build_figures + preflight (fake image + fake vision clients) ------
import base64
import json
from pathlib import Path

from samagra import config


class FakeImageClient:
    """Returns a fixed tiny PNG per call; records prompts; can be told to raise on
    the K-th call to exercise the whole-build-raise path."""
    _PNG = b"\x89PNG\r\n\x1a\nFAKE-PNG-BYTES"

    def __init__(self, raise_on=None):
        self.prompts = []
        self._raise_on = raise_on

    def generate(self, prompt):
        self.prompts.append(prompt)
        if self._raise_on is not None and len(self.prompts) == self._raise_on:
            raise RuntimeError("transient image-API 500")
        return self._PNG


class FakeVisionClient:
    """Returns a scripted verdict list from review_figure. NEVER accepts a
    StyleSeed (mirrors llm_client.review_figure's real signature)."""
    def __init__(self, verdicts):
        self._verdicts = verdicts
        self.calls = []

    def review_figure(self, png_bytes, brief, section_text):
        self.calls.append((png_bytes, brief, section_text))
        return {"verdicts": self._verdicts}


@pytest.fixture()
def export(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "EXPORT_DIR", tmp_path / "lectures")
    return tmp_path


@pytest.fixture()
def fake_chapter(monkeypatch):
    from samagra.lectures import render
    monkeypatch.setattr(render, "load_chapter", lambda slug: _CHAPTER)


def _ok_verdicts(n):
    return [{"idx": i, "verdict": "ok", "rationale": "matches"} for i in range(n)]


def test_build_figures_happy_path_writes_pngs_gallery_json(export, fake_chapter):
    img = FakeImageClient()
    vis = FakeVisionClient(_ok_verdicts(2))
    res = figure.build_figures("circular-motion", image_client=img, vision_client=vis)
    assert res["variant"] == "figure"
    assert res["items"] == 2 and res["errors"] == 0 and res["capped"] is False
    assert len(res["verdicts"]) == 2
    # Two loose PNGs on disk, non-empty, zero-padded doc-order names.
    figdir = config.EXPORT_DIR / "circular-motion" / "circular-motion-figures"
    assert (figdir / "fig-01.png").stat().st_size > 0
    assert (figdir / "fig-02.png").stat().st_size > 0
    # Gallery html + json sidecar present.
    assert Path(res["html"]).is_file() and Path(res["json"]).is_file()
    data = json.loads(Path(res["json"]).read_text(encoding="utf-8"))
    assert len(data["figures"]) == 2
    assert data["figures"][0]["verdict"] == "ok"


def test_gallery_embeds_data_uris_and_escapes_untrusted_text(export, monkeypatch):
    from samagra.lectures import render
    ch = {"title": "Gauss & Fields", "sections": [
        {"title": "Flux <through> a cube", "blocks": [
            {"type": "image-need", "brief": "A cube with E>0 and label <n̂>"}]}]}
    monkeypatch.setattr(render, "load_chapter", lambda slug: ch)
    img = FakeImageClient()
    vis = FakeVisionClient([{"idx": 0, "verdict": "error", "rationale": "label <wrong>"}])
    res = figure.build_figures("gauss-law", image_client=img, vision_client=vis)
    html = Path(res["html"]).read_text(encoding="utf-8")
    # PNG embedded as a data URI — no external image reference.
    assert "data:image/png;base64," in html
    assert "src=\"fig-" not in html and "http://" not in html and "https://" not in html.replace("fonts.googleapis", "")
    # Untrusted brief + rationale HTML-escaped at the boundary (the C1 lesson).
    assert "E>0" not in html and "E&gt;0" in html
    assert "label <wrong>" not in html and "label &lt;wrong&gt;" in html
    # JSON keeps raw text + raw base64.
    data = json.loads(Path(res["json"]).read_text(encoding="utf-8"))
    assert data["figures"][0]["brief"] == "A cube with E>0 and label <n̂>"
    assert base64.b64decode(data["figures"][0]["png_b64"])   # decodes


def test_build_figures_empty_when_no_image_need(export, monkeypatch):
    from samagra.lectures import render
    monkeypatch.setattr(render, "load_chapter",
                        lambda slug: {"title": "Empty", "sections": []})
    res = figure.build_figures("gauss-law",
                               image_client=FakeImageClient(),
                               vision_client=FakeVisionClient([]))
    assert res["items"] == 0 and res["errors"] == 0
    # No image call, no PNG written — an empty set drives build()'s changes path.
    figdir = config.EXPORT_DIR / "gauss-law" / "gauss-law-figures"
    assert not any(figdir.glob("fig-*.png")) if figdir.exists() else True


def test_missing_verdict_fails_closed(export, fake_chapter):
    # 2 targets but only 1 verdict -> the unreviewed figure counts as an error.
    img = FakeImageClient()
    vis = FakeVisionClient([{"idx": 0, "verdict": "ok", "rationale": "ok"}])
    res = figure.build_figures("circular-motion", image_client=img, vision_client=vis)
    assert res["items"] == 2 and res["errors"] == 1


def test_error_verdict_is_counted(export, fake_chapter):
    img = FakeImageClient()
    vis = FakeVisionClient([{"idx": 0, "verdict": "error", "rationale": "wrong vectors"},
                            {"idx": 1, "verdict": "ok", "rationale": "ok"}])
    res = figure.build_figures("circular-motion", image_client=img, vision_client=vis)
    assert res["errors"] == 1


def test_whole_build_raises_on_image_failure_no_partial_return(export, fake_chapter):
    # Second image call raises -> build_figures raises (no partial result dict).
    img = FakeImageClient(raise_on=2)
    vis = FakeVisionClient(_ok_verdicts(2))
    with pytest.raises(RuntimeError):
        figure.build_figures("circular-motion", image_client=img, vision_client=vis)


def test_stale_figs_cleared_on_rebuild(export, monkeypatch):
    from samagra.lectures import render
    # First build: 2 figures.
    monkeypatch.setattr(render, "load_chapter", lambda slug: _CHAPTER)
    figure.build_figures("circular-motion",
                         image_client=FakeImageClient(),
                         vision_client=FakeVisionClient(_ok_verdicts(2)))
    figdir = config.EXPORT_DIR / "circular-motion" / "circular-motion-figures"
    assert len(list(figdir.glob("fig-*.png"))) == 2
    # Rebuild with a SHORTER set (1 figure) -> no orphan fig-02.png.
    one = {"title": "Circular Motion", "sections": [
        {"title": "S", "blocks": [{"type": "image-need", "brief": "just one"}]}]}
    monkeypatch.setattr(render, "load_chapter", lambda slug: one)
    figure.build_figures("circular-motion",
                         image_client=FakeImageClient(),
                         vision_client=FakeVisionClient(_ok_verdicts(1)))
    assert sorted(p.name for p in figdir.glob("fig-*.png")) == ["fig-01.png"]


def test_preflight_ok(export, fake_chapter, monkeypatch):
    monkeypatch.setattr(figure.image_client, "configured", lambda: True)
    monkeypatch.setattr(figure.llm_client, "configured", lambda: True)
    figure.preflight("circular-motion")   # no raise


def test_preflight_missing_chapter_raises(export, monkeypatch):
    from samagra.lectures import render
    def boom(slug):
        raise FileNotFoundError(slug)
    monkeypatch.setattr(render, "load_chapter", boom)
    monkeypatch.setattr(figure.image_client, "configured", lambda: True)
    monkeypatch.setattr(figure.llm_client, "configured", lambda: True)
    with pytest.raises(FileNotFoundError):
        figure.preflight("nope")


def test_preflight_image_unconfigured_raises(export, fake_chapter, monkeypatch):
    monkeypatch.setattr(figure.image_client, "configured", lambda: False)
    monkeypatch.setattr(figure.llm_client, "configured", lambda: True)
    with pytest.raises(RuntimeError):
        figure.preflight("circular-motion")


def test_preflight_vision_unconfigured_raises(export, fake_chapter, monkeypatch):
    monkeypatch.setattr(figure.image_client, "configured", lambda: True)
    monkeypatch.setattr(figure.llm_client, "configured", lambda: False)
    with pytest.raises(RuntimeError):
        figure.preflight("circular-motion")


def test_preflight_requires_no_styleseed(export, fake_chapter, monkeypatch, tmp_path):
    # Unlike samadhan, the figure preflight does NOT require a committed StyleSeed.
    monkeypatch.setattr(config, "STYLESEED_DIR", tmp_path / "no-styleseed-here")
    monkeypatch.setattr(figure.image_client, "configured", lambda: True)
    monkeypatch.setattr(figure.llm_client, "configured", lambda: True)
    figure.preflight("circular-motion")   # no raise despite absent StyleSeed
```

- [ ] **Step 2: Run to verify failure**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_llm_client_review_figure.py tests/test_factory_figure.py -q`
Expected: FAIL — `AttributeError: ... has no attribute 'review_figure'` and
`AttributeError: module 'samagra.factory.figure' has no attribute 'build_figures'`.

- [ ] **Step 3a: Add `review_figure` to `samagra/clients/llm_client.py`** — add the frozen
    reviewer system + a vision-input `_create` path. Insert `_REVIEW_FIGURE_SYSTEM` next to
    `_REVIEW_SYSTEM`:

```python
_REVIEW_FIGURE_SYSTEM = (
    "You are a physics diagram ground-truth checker. You are given an author's "
    "figure BRIEF, the chapter SECTION text it belongs to, and a generated IMAGE. "
    "TRY TO REFUTE the image: does it match the brief; are all labels spelled "
    "correctly; is the geometry and physics right; do the vector directions and "
    "magnitudes agree with the section? Judge ONLY against the brief, the section "
    "text, and physics — NOT drawing style. Default to verdict 'error' when the "
    "image is wrong, mislabelled, or unsupported by the brief. Return strict JSON "
    "{\"verdicts\":[{\"idx\":0,\"verdict\":\"ok\"|\"error\",\"rationale\":<str>}]}."
)
```

Add a vision-capable create + the public method to `LLMClient` (uses the same
`_REVIEW_SCHEMA` and `_parse`; the image is a base64 block, one per provider shape):

```python
    def _create_vision(self, *, system_text, user_text, png_bytes, schema):
        import base64
        b64 = base64.b64encode(png_bytes).decode("ascii")
        if self._provider == "anthropic":
            return self._sdk.messages.create(
                model=self._model,
                max_tokens=_MAX_TOKENS,
                thinking={"type": "adaptive"},
                system=[{"type": "text", "text": system_text,
                         "cache_control": {"type": "ephemeral"}}],
                output_config={"format": {"type": "json_schema", "schema": schema}},
                messages=[{"role": "user", "content": [
                    {"type": "text", "text": user_text},
                    {"type": "image", "source": {"type": "base64",
                                                 "media_type": "image/png", "data": b64}},
                ]}],
            )
        return self._sdk.responses.create(
            model=self._model,
            max_output_tokens=_MAX_TOKENS,
            reasoning={"effort": self._effort},
            input=[{"role": "system", "content": system_text},
                   {"role": "user", "content": [
                       {"type": "input_text", "text": user_text},
                       {"type": "input_image",
                        "image_url": f"data:image/png;base64,{b64}"},
                   ]}],
            text={"format": {"type": "json_schema", "name": "samagra_output",
                             "schema": schema, "strict": True}},
        )

    def review_figure(self, png_bytes, brief, section_text) -> dict:
        """DEC-8-firewalled vision reviewer for the figure lane. Anchored ONLY to
        the chapter ground truth (the brief + section text + the image) — NEVER a
        StyleSeed (there is no StyleSeed parameter: the firewall is structural)."""
        resp = self._create_vision(
            system_text=_REVIEW_FIGURE_SYSTEM,
            user_text=("FIGURE BRIEF (ground truth):\n" + str(brief)
                       + "\n\nSECTION TEXT:\n" + str(section_text)),
            png_bytes=png_bytes,
            schema=_REVIEW_SCHEMA)
        return self._parse(resp)
```

- [ ] **Step 3b: Extend `samagra/factory/figure.py`** — add imports, the gallery HTML, the
    `preflight`, and `build_figures`. Prepend the new imports and append the code:

```python
import html as _html
import json

from .. import config
from ..clients import image_client, llm_client
from ..clients import image_client as _image_client_mod   # alias: the build_figures
from ..lectures import render                              # PARAMETER shadows the module


_FIGURE_CSS = """
.figs{display:flex;flex-direction:column;gap:22px;margin-top:8px}
.fig-item{border:1px solid #e3e3e6;border-radius:10px;padding:14px 16px;background:#fff}
.fig-item img{max-width:100%;height:auto;border:1px solid #ececed;border-radius:6px}
.fig-sec{color:#8a8f98;font-weight:600;font-size:12px;margin-bottom:6px}
.fig-brief{margin:8px 0;color:#1f2328}
.fig-verdict{font-size:12px;font-weight:600;margin-top:6px}
.v-ok{color:#1a6f3c}.v-error{color:#9a2a2a}
@media print{.fig-item{break-inside:avoid}}
"""


def preflight(slug: str) -> None:
    """Anti-wedge pre-check (called by build() BEFORE recording intent): the
    chapter exists, the image client is configured, and the vision (llm) client is
    configured. NO StyleSeed requirement (E: the figure prompt uses no StyleSeed).
    Raises FileNotFoundError / RuntimeError without writing anything."""
    render.load_chapter(slug)                       # FileNotFoundError if absent
    if not image_client.configured():
        try:
            key_var = image_client.required_key_var()
        except RuntimeError:
            key_var = "the image API key"
        raise RuntimeError(
            f"{key_var} is not set — refusing an image build without a key")
    if not llm_client.configured():
        try:
            key_var = llm_client.required_key_var()
        except RuntimeError:
            key_var = "the LLM API key"
        raise RuntimeError(
            f"{key_var} is not set — refusing a figure vision review without a key")


def _section_text(content: dict, section_title: str) -> str:
    """The plain-ish text of the named section, as ground truth for the reviewer."""
    for s in content.get("sections", []) or []:
        if str(s.get("title", "")) == section_title:
            return " ".join(
                str(b.get("html") or b.get("tex") or b.get("brief") or "")
                for b in s.get("blocks", []) or [])
    return ""


def _gallery_html(content: dict, figures: list[dict]) -> str:
    """Self-contained gallery: each PNG embedded as a data URI (no external image
    ref); the brief + rationale HTML-escaped at the boundary (the C1 lesson)."""
    parts = ['<section class="figs">']
    for f in figures:
        section = _html.escape(str(f.get("section", "")))
        brief = _html.escape(str(f.get("brief", "")))
        verdict = f.get("verdict", "ok")
        vcls = "v-error" if verdict == "error" else "v-ok"
        rationale = _html.escape(str(f.get("rationale", "")))
        data_uri = f"data:image/png;base64,{f['png_b64']}"
        parts.append(
            f'<article class="fig-item">'
            f'<div class="fig-sec">{f.get("idx")}. {section}</div>'
            f'<img alt="{brief}" src="{data_uri}">'
            f'<div class="fig-brief">{brief}</div>'
            f'<div class="fig-verdict {vcls}">reviewer: {_html.escape(str(verdict))}'
            f'{(" — " + rationale) if rationale else ""}</div>'
            f'</article>')
    parts.append("</section>")
    return render.DOC_TEMPLATE.format(
        title=_html.escape(str(content.get("title", "Figures"))),
        subtitle=_html.escape(str(content.get("subtitle", ""))),
        kicker=_html.escape("Generated figures (Figure lane)"),
        css=render.DOC_CSS + _FIGURE_CSS,
        body="\n".join(parts))


def build_figures(slug, *, image_client=None, vision_client=None) -> dict:
    """Generate, vision-review (fail-closed), and write the figure gallery. Raises
    FileNotFoundError (no chapter) BEFORE any write; raises (no partial result) if
    ANY image call fails — build() rolls that back retryably. Clears stale
    fig-*.png before writing the new set so a shorter rebuild leaves no orphans."""
    import base64 as _b64

    content = render.load_chapter(slug)             # ground truth (raises if absent)
    targets = _targets(content)
    # NOTE: the `image_client` param shadows the imported module in this scope, so
    # the real-client default is constructed via the module ALIAS `_image_client_mod`.
    img = image_client or _image_client_mod.ImageClient()
    vis = vision_client or llm_client.LLMClient()

    figdir = config.EXPORT_DIR / slug / f"{slug}-figures"
    figdir.mkdir(parents=True, exist_ok=True)
    for stale in figdir.glob("fig-*.png"):          # clear stale before writing (retry-safe)
        stale.unlink()

    figures: list[dict] = []
    verdicts: list[dict] = []
    for t in targets:
        png = img.generate(t["prompt"])             # a raise here raises the whole build
        name = f"fig-{t['idx']:02d}.png"
        (figdir / name).write_bytes(png)
        section_text = _section_text(content, t["section"])
        vres = vis.review_figure(png, t["brief"], section_text)
        vlist = vres.get("verdicts", []) if isinstance(vres, dict) else []
        v = next((x for x in vlist if x.get("idx") == t["idx"] - 1), None)
        # FAIL-CLOSED: an unreviewed / non-ok figure counts as an error (mirrors
        # samadhan) so a partial-coverage reviewer can never let one reach capture.
        if v is None:
            v = {"verdict": "error", "rationale": "no reviewer verdict for this figure"}
        verdict = "ok" if v.get("verdict") == "ok" else "error"
        rationale = str(v.get("rationale", ""))
        verdicts.append({"idx": t["idx"] - 1, "verdict": verdict, "rationale": rationale})
        figures.append({
            "idx": t["idx"], "png": name, "brief": t["brief"], "section": t["section"],
            "verdict": verdict, "rationale": rationale,
            "sha256": __import__("hashlib").sha256(png).hexdigest(),
            "png_b64": _b64.b64encode(png).decode("ascii")})

    errors = sum(1 for f in figures if f["verdict"] == "error")
    capped = len([1 for s in content.get("sections", []) or []
                  for b in s.get("blocks", []) or []
                  if b.get("type") == "image-need"]) > len(targets)

    out = config.EXPORT_DIR / slug
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / f"{slug}-figures.json"
    json_path.write_text(json.dumps(
        {"slug": slug, "title": content.get("title", slug),
         "figures": figures, "items": len(targets), "errors": errors,
         "capped": capped}, ensure_ascii=False, indent=2), encoding="utf-8")
    html_path = out / f"{slug}-figures.html"
    html_path.write_text(_gallery_html(content, figures), encoding="utf-8")

    return {"variant": "figure", "html": str(html_path), "json": str(json_path),
            "figures": figures, "items": len(targets), "errors": errors,
            "verdicts": verdicts, "capped": capped}
```

> **Implementer note — the module/parameter name clash (deliberate design):** the spec's
> binding signature `build_figures(slug, *, image_client=None, vision_client=None)` gives
> the function an `image_client` PARAMETER that shadows the imported `image_client` MODULE
> inside the function body. The plan resolves this by importing the module a second time
> under the alias `_image_client_mod` and constructing the real default via
> `_image_client_mod.ImageClient()`. Do NOT rename the parameter (the signature is binding),
> and KEEP the plain `image_client` module import too — `preflight` (no such parameter) calls
> `image_client.configured()`/`.required_key_var()`, and the tests monkeypatch
> `figure.image_client.configured`. Both bindings point at the same module object.

- [ ] **Step 4: Run new + standing tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_llm_client_review_figure.py tests/test_factory_figure.py tests/test_llm_client_providers.py tests/test_llm_client.py tests/test_factory_samadhan.py -q`
Expected: ALL PASS (figure tests green + the standing llm/samadhan tests unchanged —
`review_figure` is additive, `generate_samadhan`/`review_samadhan` untouched).

- [ ] **Step 5: Commit**

```bash
git add samagra/factory/figure.py samagra/clients/llm_client.py tests/test_factory_figure.py tests/test_llm_client_review_figure.py
git commit -m "feat(f1): figure build — generate, vision-review, data-URI gallery artifact

build_figures(slug, *, image_client=, vision_client=) generates a PNG per
image-need brief (deterministic fig-NN.png, stale fig-*.png cleared first),
vision-reviews each via llm_client.review_figure (DEC-8-firewalled, fail-closed),
and writes <slug>-figures/ PNGs + <slug>-figures.json + a self-contained data-URI
gallery <slug>-figures.html. Untrusted brief/rationale HTML-escaped at the
boundary; JSON keeps raw. Any image-call failure raises the whole build (no
partial return) for build()'s retryable rollback. preflight requires chapter +
image + vision configured, NO StyleSeed.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: Wiring — Line, dispatch, validate_product, lane-dispatched preflight, capture gate (TDD)

**Files:**
- Modify: `samagra/factory/lines.py` (register the `figure` Line)
- Modify: `samagra/factory/dispatch.py` (`run_line` route + `validate_product` binary branch)
- Modify: `samagra/factory/run.py` (lane-dispatched preflight + the autocapture `needs_review` clause)
- Create: `tests/test_factory_figure_wiring.py`

The figure lane is `kind="llm"`, so it rides the existing five build() guards + retryable
rollback verbatim. Touch points: (1) a `figure` Line; (2) `run_line` special-cases `figure`
ahead of the generic samadhan branch (both `kind=="llm"`, disambiguated by KEY — exactly as
`deck` is special-cased); (3) `validate_product` asserts ≥1 non-empty PNG for the figure
variant; (4) build()'s `kind=="llm"` preflight becomes lane-dispatched (`figure` →
`figure.preflight`, `samadhan` → `samadhan.preflight` UNCHANGED); (5) build()'s
`needs_review` gains one clause — a `figure` build with `SAMAGRA_FIGURE_AUTOCAPTURE` off
routes to `changes` regardless of the (truthfully-recorded) vision verdict.

- [ ] **Step 1: Write the failing tests** — `tests/test_factory_figure_wiring.py`:

```python
"""Phase F1 wiring: the figure Line, run_line routing, validate_product binary
branch, the lane-dispatched build() preflight, and the SAMAGRA_FIGURE_AUTOCAPTURE
capture gate. Offline: fake image + fake vision clients, isolated governance.db."""
from __future__ import annotations

from pathlib import Path

import pytest

from samagra import config
from samagra.factory import dispatch, figure, run
from samagra.factory.lines import LINES, classify
from samagra.governance import store


# ---------- lane registration ----------

def test_figure_line_registered_llm_optin_textbook():
    spec = LINES["figure"]
    assert spec.kind == "llm"
    assert spec.auto_fan is False                    # opt-in (F-D4 analogue)
    assert spec.source_prefixes == ("textbook:",)


def test_classify_textbook_excludes_figure():
    # figure is opt-in: NOT in the default textbook fan-out (like samadhan).
    assert "figure" not in classify("textbook:circular-motion")


def test_plan_lane_figure_proposes_only_that_lane():
    props = run.plan("textbook:circular-motion", dry=True, lane="figure")
    assert [p["line"] for p in props] == ["figure"]


# ---------- run_line routing ----------

class _FakeImg:
    def generate(self, prompt):
        return b"\x89PNG\r\n\x1a\nX"


class _FakeVis:
    def review_figure(self, png, brief, section):
        return {"verdicts": [{"idx": 0, "verdict": "ok", "rationale": "ok"}]}


def test_run_line_routes_figure_to_build_figures(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "EXPORT_DIR", tmp_path / "lectures")
    from samagra.lectures import render
    monkeypatch.setattr(render, "load_chapter", lambda slug: {
        "title": "T", "sections": [{"title": "S", "blocks": [
            {"type": "image-need", "brief": "b"}]}]})
    called = {}
    real = figure.build_figures
    def spy(slug, **kw):
        called["slug"] = slug
        return real(slug, image_client=_FakeImg(), vision_client=_FakeVis())
    monkeypatch.setattr(figure, "build_figures", spy)
    res = dispatch.run_line("figure", "circular-motion")
    assert called["slug"] == "circular-motion"
    assert res["variant"] == "figure"


# ---------- validate_product binary branch ----------

def test_validate_product_requires_a_png(tmp_path):
    # A gallery html present but ZERO png files on disk -> ValueError.
    html = tmp_path / "x-figures.html"
    html.write_text("<html>gallery</html>", encoding="utf-8")
    result = {"variant": "figure", "html": str(html), "json": None,
              "items": 1, "errors": 0, "verdicts": [{"idx": 0, "verdict": "ok"}],
              "figures": [{"idx": 1, "png": "fig-01.png"}]}
    with pytest.raises(ValueError):
        dispatch.validate_product("figure", result)


def test_validate_product_passes_with_a_png(tmp_path):
    figdir = tmp_path / "x-figures"
    figdir.mkdir()
    (figdir / "fig-01.png").write_bytes(b"\x89PNG\r\n\x1a\nX")
    html = tmp_path / "x-figures.html"
    html.write_text("<html>gallery</html>", encoding="utf-8")
    result = {"variant": "figure", "html": str(html), "json": None,
              "items": 1, "errors": 0, "verdicts": [{"idx": 0, "verdict": "ok"}],
              "figures": [{"idx": 1, "png": "fig-01.png"}]}
    dispatch.validate_product("figure", result)      # no raise


# ---------- build() capture gate + preflight + retryable ----------

@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "GOVERNANCE_DB", tmp_path / "governance.db")
    monkeypatch.setattr(config, "DATA_DB", tmp_path / "samagra.db")
    monkeypatch.setattr(config, "EXPORT_DIR", tmp_path / "lectures")
    store._INITIALIZED.clear()
    store.ensure_tables()
    monkeypatch.chdir(tmp_path)
    from samagra.lectures import render
    monkeypatch.setattr(render, "load_chapter", lambda slug: {
        "title": "Circular Motion", "sections": [{"title": "S", "blocks": [
            {"type": "image-need", "brief": "a spinning disc"}]}]})
    # figure preflight sees both clients configured.
    monkeypatch.setattr(figure.image_client, "configured", lambda: True)
    monkeypatch.setattr(figure.llm_client, "configured", lambda: True)
    yield tmp_path
    store._INITIALIZED.clear()


def _fake_build_figures_ok(monkeypatch):
    def fake(slug, **kw):
        return figure.build_figures(slug, image_client=_FakeImg(), vision_client=_FakeVis())
    monkeypatch.setattr(figure, "build_figures", fake)


def _approve_and_build(seed_ref):
    props = run.plan(seed_ref, dry=False, lane="figure")
    run.approve_seed(seed_ref)
    return run.build(props[0]["assignment_id"])


def test_autocapture_off_default_routes_to_changes(env, monkeypatch):
    monkeypatch.delenv("SAMAGRA_FIGURE_AUTOCAPTURE", raising=False)
    _fake_build_figures_ok(monkeypatch)
    res = _approve_and_build("textbook:circular-motion")
    assert res["status"] == "changes"                # conservative default (C3-equivalent)
    c = store.connect()
    try:
        verbs = [e["verb"] for e in store.list_events_for_assignment(c, res["assignment_id"])]
    finally:
        c.close()
    assert "product_created" in verbs                # the artifact WAS produced + recorded


def test_autocapture_on_clean_build_is_captured(env, monkeypatch):
    monkeypatch.setenv("SAMAGRA_FIGURE_AUTOCAPTURE", "1")
    _fake_build_figures_ok(monkeypatch)
    res = _approve_and_build("textbook:circular-motion")
    assert res["status"] == "captured"


def test_autocapture_on_error_verdict_routes_to_changes(env, monkeypatch):
    monkeypatch.setenv("SAMAGRA_FIGURE_AUTOCAPTURE", "1")
    class _ErrVis:
        def review_figure(self, png, brief, section):
            return {"verdicts": [{"idx": 0, "verdict": "error", "rationale": "wrong"}]}
    def fake(slug, **kw):
        return figure.build_figures(slug, image_client=_FakeImg(), vision_client=_ErrVis())
    monkeypatch.setattr(figure, "build_figures", fake)
    res = _approve_and_build("textbook:circular-motion")
    assert res["status"] == "changes"                # error -> changes even with autocapture on


def test_figure_preflight_refuses_before_intent_no_wedge(env, monkeypatch):
    monkeypatch.setattr(figure.image_client, "configured", lambda: False)
    props = run.plan("textbook:circular-motion", dry=False, lane="figure")
    run.approve_seed("textbook:circular-motion")
    aid = props[0]["assignment_id"]
    with pytest.raises(RuntimeError):
        run.build(aid)
    c = store.connect()
    try:
        verbs = [e["verb"] for e in store.list_events_for_assignment(c, aid)]
        a = [x for x in store.list_assignments(c) if x["id"] == aid][0]
    finally:
        c.close()
    assert "product_building" not in verbs and a["status"] == "approved"   # not wedged


def test_figure_image_failure_rolls_back_and_is_retryable(env, monkeypatch):
    monkeypatch.setenv("SAMAGRA_FIGURE_AUTOCAPTURE", "1")
    class _BoomImg:
        def generate(self, prompt):
            raise RuntimeError("transient image-API 500")
    def boom(slug, **kw):
        return figure.build_figures(slug, image_client=_BoomImg(), vision_client=_FakeVis())
    monkeypatch.setattr(figure, "build_figures", boom)
    props = run.plan("textbook:circular-motion", dry=False, lane="figure")
    run.approve_seed("textbook:circular-motion")
    aid = props[0]["assignment_id"]
    with pytest.raises(RuntimeError):
        run.build(aid)
    c = store.connect()
    try:
        a = [x for x in store.list_assignments(c) if x["id"] == aid][0]
        verbs = [e["verb"] for e in store.list_events_for_assignment(c, aid)]
    finally:
        c.close()
    assert a["status"] == "approved"                 # not wedged (local-write lane rollback)
    assert "product_build_failed" in verbs and "product_created" not in verbs
    # retry with a working client -> succeeds and captures.
    _fake_build_figures_ok(monkeypatch)
    assert run.build(aid)["status"] == "captured"


def test_samadhan_preflight_unchanged(env, monkeypatch):
    # Regression pin: the samadhan lane still routes to samadhan.preflight, not
    # figure.preflight (the lane-dispatch must not break the D2 lane). build() calls
    # its own `samadhan` binding (run.py line: `from . import ... samadhan`), and
    # dispatch.run_line calls its own `samadhan` binding — both point at the one
    # module object, so patching the module attribute covers every call site.
    from samagra.factory import samadhan
    calls = {"preflight": 0}
    def spy_preflight(slug):
        calls["preflight"] += 1
        return None                                  # skip StyleSeed/key checks for the pin
    monkeypatch.setattr(samadhan, "preflight", spy_preflight)
    # Stub the produce step so we prove ONLY the preflight dispatch, not the D2 lane.
    (config.EXPORT_DIR).mkdir(parents=True, exist_ok=True)
    (config.EXPORT_DIR / "s.html").write_text("<h1>s</h1>", encoding="utf-8")
    monkeypatch.setattr(
        samadhan, "build_samadhan",
        lambda slug: {"variant": "samadhan",
                      "html": str(config.EXPORT_DIR / "s.html"),
                      "json": None, "items": 1, "errors": 0,
                      "verdicts": [{"idx": 0, "verdict": "ok"}]})
    props = run.plan("textbook:circular-motion", dry=False, lane="samadhan")
    run.approve_seed("textbook:circular-motion")
    run.build(props[0]["assignment_id"])
    assert calls["preflight"] == 1                   # samadhan.preflight WAS called
```

- [ ] **Step 2: Run to verify failure**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_factory_figure_wiring.py -q`
Expected: FAIL — `KeyError: 'figure'` in `LINES` / `run_line` returns a samadhan result /
`validate_product` doesn't assert the PNG / build() calls `samadhan.preflight` for the
figure lane.

- [ ] **Step 3a: Register the `figure` Line in `samagra/factory/lines.py`** — add to `LINES`
    (after `samadhan`) and to `_ORDER`:

```python
    "figure": Line("figure", "Generated figures (image-gen, LLM-reviewed)",
                   None, ("textbook:",), "llm", auto_fan=False),
```

and extend `_ORDER`:

```python
_ORDER = ["revision", "lecture", "deck", "paper", "drill", "seed", "samadhan", "figure"]
```

- [ ] **Step 3b: Route `figure` in `samagra/factory/dispatch.py`** — import `figure`, add the
    `run_line` special-case AHEAD of the generic `kind=="llm"` branch, and add the binary
    `validate_product` branch. In the import line:

```python
from . import deck, figure, paper, samadhan
```

In `run_line`, add BEFORE the `if spec.kind == "llm":` branch (mirrors the `deck` special-case):

```python
    if line == "figure":
        return figure.build_figures(slug)
```

At the end of `validate_product`, after `_assert_review_clean(line, result)`, add:

```python
    _assert_figures_present(line, result)
```

and add the new helper at module end:

```python
def _assert_figures_present(line: str, result: dict) -> None:
    """For the figure lane ONLY: the gallery html check (above) is not enough — a
    build that produced a gallery but zero image files must be refused, not
    captured. Assert at least one non-empty PNG exists on disk under the sibling
    <slug>-figures/ directory."""
    if result.get("variant") != "figure":
        return
    pngs = []
    for f in result.get("figures", []) or []:
        html = result.get("html")
        if not html:
            continue
        figdir = Path(html).parent / f"{Path(html).stem}"   # <slug>-figures
        p = figdir / str(f.get("png", ""))
        if p.is_file() and p.stat().st_size > 0:
            pngs.append(p)
    if not pngs:
        raise ValueError(
            f"line {line!r} produced no non-empty PNG figure — refusing to capture "
            f"a figure gallery with no images")
```

> **Implementer note:** `Path(html).stem` for `<slug>-figures.html` is `<slug>-figures`,
> and `build_figures` writes PNGs under `EXPORT_DIR/<slug>/<slug>-figures/` while the html
> lives at `EXPORT_DIR/<slug>/<slug>-figures.html` — so `Path(html).parent / "<slug>-figures"`
> is exactly the PNG dir. The `test_validate_product_*` tests construct that same layout, so
> keep the dir-name derivation as `Path(html).parent / Path(html).stem`.

- [ ] **Step 3c: Lane-dispatch the preflight + add the autocapture clause in
    `samagra/factory/run.py`** — import `figure` and `config`, replace the `elif spec.kind ==
    "llm":` preflight block, and extend `needs_review`.

In the imports at the top of `run.py`:

```python
from .. import config
from . import dispatch, figure, samadhan
```

Replace the existing preflight block:

```python
        elif spec.kind == "llm":
            # anti-wedge: chapter exists + StyleSeed committed + LLM configured,
            # asserted BEFORE recording build intent (a missing key refuses without
            # wedging the in-flight state — mirrors the mcd validate-before-intent).
            samadhan.preflight(seed_ref.split(":", 1)[-1])
```

with the lane-dispatched form (samadhan path byte-identical; figure gets its own preflight):

```python
        elif spec.kind == "llm":
            # anti-wedge: preflight BEFORE recording build intent (a missing key /
            # absent chapter refuses without wedging the in-flight state). Both llm
            # lanes are kind=="llm"; the lane KEY disambiguates which preflight runs
            # (figure requires no StyleSeed; samadhan's path is unchanged).
            _slug = seed_ref.split(":", 1)[-1]
            if line == "figure":
                figure.preflight(_slug)
            else:
                samadhan.preflight(_slug)
```

Replace the `needs_review` computation:

```python
        needs_review = spec.kind == "llm" and (
            result.get("errors", 0) > 0 or result.get("items", 0) == 0)
```

with the autocapture-aware form:

```python
        # llm capture/changes gate (verbatim): a reviewer error OR an empty brief
        # routes to `changes`. F1 default posture: a figure build ALSO routes to
        # `changes` whenever SAMAGRA_FIGURE_AUTOCAPTURE is off, so a generated
        # diagram is always owner-reviewed until the owner trusts the corpus's
        # failure rate. The reviewer's real error count stays truthful in the
        # artifact — this clause only affects the terminal status, not the ledger.
        needs_review = spec.kind == "llm" and (
            result.get("errors", 0) > 0 or result.get("items", 0) == 0)
        if line == "figure" and not config._env_bool("SAMAGRA_FIGURE_AUTOCAPTURE", False):
            needs_review = True
```

> **Implementer note:** `config._env_bool` already exists (used for
> `SAMAGRA_PRATHAM_COOKIE_SECURE` etc.) and reads the env at call time, so the tests'
> `monkeypatch.setenv/delenv("SAMAGRA_FIGURE_AUTOCAPTURE", ...)` take effect per-build with
> no import-time capture. Do NOT read a module-level constant for autocapture — read it live
> here so the flag is honored without a restart.

- [ ] **Step 4: Run new + standing wiring/build tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_factory_figure_wiring.py tests/test_factory_lines.py tests/test_factory_dispatch.py tests/test_factory_run.py tests/test_factory_samadhan_wiring.py tests/test_cli_factory_lane.py -q`
Expected: ALL PASS (figure wiring green + every standing lane/run/samadhan test unchanged —
the samadhan preflight regression pin proves D2 is intact).

- [ ] **Step 5: Commit**

```bash
git add samagra/factory/lines.py samagra/factory/dispatch.py samagra/factory/run.py tests/test_factory_figure_wiring.py
git commit -m "feat(f1): wire the figure lane — Line, run_line route, validate_product, capture gate

figure Line (kind=llm, auto_fan=False, textbook: prefix). run_line special-cases
figure ahead of the generic samadhan branch (KEY disambiguates, like deck).
validate_product asserts >=1 non-empty PNG for the figure variant. build()'s
kind==llm preflight is now lane-dispatched (figure->figure.preflight, samadhan
UNCHANGED, regression-pinned) and needs_review gains one clause: a figure build
routes to changes whenever SAMAGRA_FIGURE_AUTOCAPTURE is off (default), read live.
Rides the existing 5 guards + retryable rollback verbatim — no new status, no
migration.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: Docs + publish-compat golden + opt-in live smoke (TDD)

**Files:**
- Modify: `.env.example` (image block)
- Modify: `requirements.txt` (comment only — `openai>=2.32` already pins it)
- Create: `tests/test_figure_golden.py` (publish-compat + governance-byte golden thread)
- Create: `tests/test_figure_live_smoke.py` (opt-in live smoke, gated on `SAMAGRA_LIVE_IMAGE_SMOKE`)

- [ ] **Step 1: Write the failing golden thread** — `tests/test_figure_golden.py`:

```python
"""Phase F1 golden threads: the plan->approve->build->(changes/capture) loop, the
publish-compatibility of the gallery html, and governance-byte consistency (no
migration). Offline: fake image + fake vision clients, isolated stores. Mirrors
tests/test_g4_golden.py's governance-byte discipline."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from samagra import config
from samagra.factory import figure, run
from samagra.factory.publish import read as pub_read, run as pub_run
from samagra.governance import store


class _FakeImg:
    def generate(self, prompt):
        return b"\x89PNG\r\n\x1a\nGOLDEN"


class _FakeVis:
    def review_figure(self, png, brief, section):
        return {"verdicts": [{"idx": 0, "verdict": "ok", "rationale": "ok"}]}


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "GOVERNANCE_DB", tmp_path / "governance.db")
    monkeypatch.setattr(config, "DATA_DB", tmp_path / "samagra.db")
    monkeypatch.setattr(config, "EXPORT_DIR", tmp_path / "lectures")
    monkeypatch.setattr(config, "PUBLISHED_DIR", tmp_path / "published")
    store._INITIALIZED.clear()
    store.ensure_tables()
    monkeypatch.chdir(tmp_path)
    from samagra.lectures import render
    monkeypatch.setattr(render, "load_chapter", lambda slug: {
        "title": "Circular Motion", "sections": [{"title": "S", "blocks": [
            {"type": "image-need", "brief": "a spinning disc"}]}]})
    monkeypatch.setattr(figure.image_client, "configured", lambda: True)
    monkeypatch.setattr(figure.llm_client, "configured", lambda: True)
    # build() calls dispatch.run_line("figure", slug) -> figure.build_figures(slug)
    # with NO injected clients, so replace build_figures with a version that injects
    # the offline fakes (the real production path, just with fakes swapped in).
    monkeypatch.setattr(figure, "build_figures", lambda slug, **kw: _real_build(slug))
    yield tmp_path
    store._INITIALIZED.clear()


# Capture the genuine engine once at import time, before any monkeypatch, so the
# fixture's replacement can still reach the real build_figures with fakes injected.
_REAL_BUILD_FIGURES = figure.build_figures


def _real_build(slug):
    return _REAL_BUILD_FIGURES(slug, image_client=_FakeImg(), vision_client=_FakeVis())


def test_golden_default_routes_to_changes_governance_schema_stable(env, monkeypatch):
    monkeypatch.delenv("SAMAGRA_FIGURE_AUTOCAPTURE", raising=False)
    # schema version BEFORE (no migration expected across the whole loop).
    ver_before = store.connect().execute("PRAGMA user_version").fetchone()[0]
    props = run.plan("textbook:circular-motion", dry=False, lane="figure")
    run.approve_seed("textbook:circular-motion")
    res = run.build(props[0]["assignment_id"])
    assert res["status"] == "changes"                 # conservative default
    ver_after = store.connect().execute("PRAGMA user_version").fetchone()[0]
    assert ver_after == ver_before                    # NO migration / schema bump


def test_golden_publish_compat_on_gallery_html(env, monkeypatch):
    # With autocapture ON the build captures; publish --lanes figure copies the
    # gallery html + json; the G2 read surface serves it sha-verified. (The `env`
    # fixture already routes figure.build_figures through the offline fakes.)
    monkeypatch.setenv("SAMAGRA_FIGURE_AUTOCAPTURE", "1")
    props = run.plan("textbook:circular-motion", dry=False, lane="figure")
    run.approve_seed("textbook:circular-motion")
    assert run.build(props[0]["assignment_id"])["status"] == "captured"

    pub = pub_run.publish("circular-motion", lanes=["figure"])
    assert pub["chapter"] == "circular-motion" or pub.get("published")   # publish succeeded

    art = pub_read.resolve_artifact("circular-motion", "figure", "html")
    assert art is not None
    assert art["media_type"].startswith("text/html")
    # sha-verified serving: the resolver re-hashes the bytes against the manifest.
    assert art["sha256"] == __import__("hashlib").sha256(art["bytes"]).hexdigest()
    # The published gallery is self-contained (data-URI PNG embedded).
    assert b"data:image/png;base64," in art["bytes"]
```

> **Implementer note:** the load-bearing mechanic is: build() calls
> `dispatch.run_line("figure", slug)` → `figure.build_figures(slug)` with NO injected
> clients, so the `env` fixture replaces `figure.build_figures` with `_real_build`, which
> calls the import-time-captured `_REAL_BUILD_FIGURES` with the offline fakes. Capturing the
> real engine into `_REAL_BUILD_FIGURES` at module import (before any monkeypatch) is what
> lets the replacement still reach the genuine engine. When implementing
> `test_golden_publish_compat_on_gallery_html`, verify the `pub_run.publish(...)` return
> shape against the real `publish()` in `samagra/factory/publish/run.py` and set the "publish
> succeeded" assertion to the actual key — the load-bearing asserts are
> `resolve_artifact(...) is not None`, the sha re-verify, and the embedded `data:image/png`
> URI, not the exact publish-return key.

- [ ] **Step 2a: Run the golden to verify failure**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_figure_golden.py -q`
Expected: FAIL initially only if the publish-return-key assertion is mis-shaped — fix that
assertion to the real `publish()` return key (read `samagra/factory/publish/run.py::publish`
first), then it PASSES on the already-wired lane. (The changes-default + governance-schema
test should pass immediately given Task 4.)

- [ ] **Step 2b: Write the opt-in live smoke** — `tests/test_figure_live_smoke.py`:

```python
"""OPT-IN live smoke: one real figure build end-to-end against the configured image
provider + a real vision review. Gated on an EXPLICIT flag (SAMAGRA_LIVE_IMAGE_SMOKE),
NOT merely on the key: config.py auto-loads the gitignored .env, so a key-only gate
would fire this on every `pytest` run — billing tokens + hitting the network during
the standing gate. Requiring a separate flag keeps the standing CI gate strictly
offline. Run it manually to validate the real image boundary:
  SAMAGRA_LIVE_IMAGE_SMOKE=1 OPENAI_API_KEY=… python -m pytest tests/test_figure_live_smoke.py -v
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from samagra import config
from samagra.clients import image_client, llm_client
from samagra.factory import figure


def _truthy(name):
    return (os.environ.get(name) or "").strip().lower() in {"1", "true", "yes", "on"}


pytestmark = pytest.mark.skipif(
    not (_truthy("SAMAGRA_LIVE_IMAGE_SMOKE")
         and image_client.configured() and llm_client.configured()),
    reason="opt-in live smoke: set SAMAGRA_LIVE_IMAGE_SMOKE=1 + a configured image+vision key")


def test_live_figure_build_circular_motion(tmp_path, monkeypatch):
    try:
        from samagra.lectures import render
        content = render.load_chapter("circular-motion")
    except FileNotFoundError:
        pytest.skip("circular-motion chapter not present in this checkout")
    if not figure._targets(content):
        pytest.skip("circular-motion has no image-need briefs in this checkout")
    monkeypatch.setattr(config, "EXPORT_DIR", tmp_path / "lectures")
    res = figure.build_figures("circular-motion")     # real image + real vision clients
    assert res["items"] >= 1
    assert isinstance(res["errors"], int)
    assert Path(res["html"]).is_file() and Path(res["json"]).is_file()
    figdir = config.EXPORT_DIR / "circular-motion" / "circular-motion-figures"
    assert any(figdir.glob("fig-*.png"))              # >=1 real PNG written
    assert len(res["verdicts"]) == res["items"]       # a real vision verdict per figure
```

- [ ] **Step 3: Update `.env.example`** — append the image block after the LLM block:

```
# --- Image generation (Phase F1, the figure lane) ---
# Provider: openai (default, the only F1 backend). OPENAI_API_KEY is REUSED (same
# key as the LLM lane). Model/size/quality default per provider; overrides only.
SAMAGRA_IMAGE_PROVIDER=
SAMAGRA_IMAGE_MODEL=
SAMAGRA_IMAGE_SIZE=
SAMAGRA_IMAGE_QUALITY=
SAMAGRA_FIGURE_CAP=
# 0 (default) = every figure build routes to `changes` for owner review; 1 = the
# standard llm capture gate applies (clean review -> captured).
SAMAGRA_FIGURE_AUTOCAPTURE=
# 1 to run the opt-in live image smoke (tests/test_figure_live_smoke.py).
SAMAGRA_LIVE_IMAGE_SMOKE=
```

- [ ] **Step 4: Update `requirements.txt`** — no new dependency; update the comment on the
    `openai>=2.32` line to note image use (e.g. append `  # LLM (Responses) + image (Images) API`).
    If there is no comment, add one; do NOT change the version pin.

- [ ] **Step 5: Run the golden + smoke (smoke skips offline)**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_figure_golden.py tests/test_figure_live_smoke.py -q`
Expected: golden PASSES; the live smoke is SKIPPED (no `SAMAGRA_LIVE_IMAGE_SMOKE` flag) — 1
skipped, rest passed.

- [ ] **Step 6: Commit**

```bash
git add .env.example requirements.txt tests/test_figure_golden.py tests/test_figure_live_smoke.py
git commit -m "docs(f1): image env block + publish-compat golden + opt-in live image smoke

.env.example gains the image block (provider/model/size/quality/cap/autocapture/
live-smoke flag); requirements comment notes image use (openai>=2.32 already
pins it — no new dep). Golden thread proves plan->approve->build->changes (default)
leaves the governance schema unbumped (no migration), and that with autocapture on
a captured figure lane publishes via the existing G1 CLI + resolves sha-verified
through the G2 read surface with the PNG embedded as a data URI. Live smoke gated
on SAMAGRA_LIVE_IMAGE_SMOKE stays offline in the standing gate.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: Full gates

**Files:** none (verification only — no commit unless a fix is needed).

- [ ] **Step 1: Full pytest run**

Run: `.\.venv\Scripts\python.exe -m pytest -q --junit-xml=<scratchpad>\gate-f1.xml`
(substitute the session scratchpad dir for `<scratchpad>`.)
Expected: read the junit-xml root attrs — `failures="0"`, `errors="0"`. Test count ≈ 713
baseline + ~50 new F1 tests (image_client ~18, figure pure ~5, review_figure ~4, figure
build/preflight ~13, wiring ~11, golden ~2). `skipped="2"` — the opt-in live LLM smoke AND
the new opt-in live image smoke (both gated, both skip in the offline gate).

- [ ] **Step 2: Confirm the two skips are ONLY the live smokes**

Run: `.\.venv\Scripts\python.exe -m pytest -q -rs 2>&1 | grep -i skip`
Expected: exactly two SKIPPED lines — `test_samadhan_live_smoke` and
`test_figure_live_smoke`, both reasoned "opt-in live smoke". No unexpected skips.

- [ ] **Step 3: Frontend untouched — vitest baseline asserted by inspection**

F1 changed ZERO files under `frontend/`. Confirm with:
Run: `git diff --name-only main...HEAD -- frontend/`
Expected: empty output. The 639 vitest baseline stands unchanged — no vitest rerun needed
(recorded per house convention). If the diff is non-empty, STOP: a frontend file was touched
unexpectedly and must be explained before proceeding.

- [ ] **Step 4: Record the gate result** in the task report: total tests, failures=0,
    skipped=2 (the two live smokes), the junit-xml path, and the empty frontend diff. Do NOT
    commit (verification-only task). The orchestrator runs Codex review 33 + the adversarial
    review-gate pass + the merge OUTSIDE this plan.

---

## Spec-coverage map (self-review — every §Design item points to a task)

| Spec item | Task |
|---|---|
| §2 In: `image_client.py` (provider/configured/required_key_var/fail-closed/never-leak) | 1 |
| §2 In: `figure.py` `build_figures(slug, *, image_client=, vision_client=)` | 2 (targets) + 3 (build) |
| §2 In: `lines.py` figure Line (kind=llm, auto_fan=False, textbook:) | 4 |
| §2 In: `dispatch.run_line` route + `validate_product` binary branch | 4 |
| §2 In: build() reaches existing kind==llm path (one preflight indirection) | 4 |
| §2 In: CLI `plan … --lane figure` via existing `plan(lane=)`; `.env.example`+`requirements.txt` | 5 (no new subcommand — confirmed by `test_plan_lane_figure_proposes_only_that_lane`) |
| §2 In: offline TDD matrix + opt-in live smoke | 1–5 (matrix), 5 (smoke) |
| §3.1 A1 image-need-only, document order, deterministic prompt, empty→changes | 2 (`_targets`, empty), 4 (empty→changes gate) |
| §3.1 `_FIGURE_CAP=6`, `capped:true`+total | 2 (cap test) + 3 (manifest `capped`) |
| §3.1 prompt shape (preamble + chapter/section frame + brief verbatim) | 2 |
| §3.2 B1 `images.generate(gpt-image-1)`, size/quality env fail-closed, `_extract_png` never-leak, provider seam | 1 |
| §3.3 C1 vision review recorded + fail-closed verdict | 3 (`review_figure`, missing/error verdict) |
| §3.3 `SAMAGRA_FIGURE_AUTOCAPTURE` default off → every build to changes; on → std gate | 4 |
| §3.3 DEC-8 firewall structural (`review_figure` no StyleSeed) | 3 (signature test) |
| §3.4.1 files under `EXPORT_DIR/<slug>/` (PNGs + json + gallery html) | 3 |
| §3.4.1 data-URI gallery, HTML-escape untrusted, JSON raw | 3 (`test_gallery_embeds_data_uris_and_escapes_untrusted_text`) |
| §3.4.2 result dict keys (variant/html/json/figures/items/errors/verdicts/capped) | 3 |
| §3.4.3 answer-leak no-op for llm; `_assert_review_clean` reused; new `_assert_figures_present` | 4 |
| §3.4.4 publish-compat (gallery html publishes; loose PNGs out of publish; G2 resolve sha-verified) | 5 (golden) |
| §3.5 E no StyleSeed on prompt; preflight needs no StyleSeed; no style score | 2 (prompt), 3 (preflight no-StyleSeed) |
| §3.6 build() one preflight indirection + samadhan unchanged | 4 (lane-dispatch + samadhan regression pin) |
| §3.6.3 needs_review autocapture clause (honest error count in artifact) | 4 |
| §3.7 CLI + `.env.example` image block | 5 |
| §4 invariants 1–9 (keys env-only, no prod write, publish gate, DEC-8, 5 guards, no migration, retryable) | 1 (keys), 4 (gate/guards/retryable), 5 (no migration golden) |
| §5.1 T1–T17 offline matrix | T1–T3→Task2/3, T4–T5→Task3, T6–T8→Task1, T9–T11→Task3, T12–T15→Task4, T16–T17→Task5 |
| §5.2 opt-in live smoke `SAMAGRA_LIVE_IMAGE_SMOKE` | 5 |
| §5.3 gates (pytest green, 2 live-smoke skips; vitest unchanged) | 6 |
| §6 retry/partial: whole-build raise, retryable rollback, stale fig-*.png cleared, no resume | 3 (whole-build raise + stale clear) + 4 (retryable rollback) |

**Not in this plan (per the task brief):** Codex review 33, the adversarial review-gate pass,
and the merge — the orchestrator runs those outside the plan (§5.4).
