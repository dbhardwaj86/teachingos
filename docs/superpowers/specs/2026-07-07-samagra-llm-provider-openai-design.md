# SAMAGRA LLM Provider Mini-Slice — OpenAI backend for the samadhan generation boundary

**Status:** SHIPPED 2026-07-07 (Chairman: "go for next task llm slice"; the interface was
pre-declared by the Chairman in the live `.env`: `SAMAGRA_LLM_PROVIDER=openai`,
`SAMAGRA_LLM_MODEL=gpt-5.5`, `SAMAGRA_LLM_EFFORT=medium`, `OPENAI_API_KEY` present.)

**Slice type:** mini-slice on the Phase-D2 generation boundary. Dedicated Codex pre-merge
review REQUIRED (house convention: any change to the network/secrets generation boundary
gets a DEC-7-style review — this will be **review 32**).

## 1. Problem

`samagra/clients/llm_client.py` is the ONE LLM call site (Phase D2) and is Anthropic-only.
The live `.env` carries no `ANTHROPIC_API_KEY` — the samadhan lane is currently
unconfigured/dead. The Chairman added an OpenAI key and declared the provider interface in
`.env`. This slice makes the client provider-aware so the samadhan lane runs live on
OpenAI `gpt-5.5`, without touching any consumer.

## 2. Scope

- **In:** `samagra/clients/llm_client.py` (provider adapters), `configured()`
  provider-awareness, `.env.example` + `requirements.txt`, provider-aware live smoke,
  tests. Nothing else.
- **Out:** any change to `samagra/factory/samadhan.py`, `dispatch.py`, `build()` guards,
  prompts, schemas, StyleSeed, governance. Phase F lanes (image-gen, slides/NotebookLM)
  are a separate future slice.

## 3. Design

### 3.1 Provider resolution
- `SAMAGRA_LLM_PROVIDER` ∈ {`anthropic`, `openai`}; **default `anthropic`** when
  unset/empty (byte-identical D2 back-compat; every standing test keeps passing
  unchanged). Unknown value → `RuntimeError` at construction (fail-closed, no silent
  fallback).
- Per-provider model defaults: anthropic → `claude-opus-4-8` (unchanged), openai →
  `gpt-5.5`. `SAMAGRA_LLM_MODEL` overrides either.
- `SAMAGRA_LLM_EFFORT` (default `medium`) is consumed ONLY by the openai path (Responses
  API `reasoning.effort`); the anthropic path keeps `thinking={"type": "adaptive"}`
  untouched.

### 3.2 Public surface — UNCHANGED
`configured()`, `LLMClient(sdk=, model=)`, `.generate_samadhan(chapter, *, system)`,
`.review_samadhan(items, chapter)` keep their exact signatures and return shapes
(parsed dict). `LLMClient` gains an optional `provider=` kwarg (env-first resolution).
No consumer file changes.

### 3.3 OpenAI path (Responses API, openai>=2.32)
- `client.responses.create(model=…, reasoning={"effort": effort},
  max_output_tokens=_MAX_TOKENS, input=[{"role":"system"|"user", …}],
  text={"format": {"type":"json_schema", "name":…, "schema":…, "strict": true}})`.
  Both existing schemas already satisfy strict-mode rules (all-required,
  `additionalProperties:false`).
- System text stays the FIRST system input item (the StyleSeed conditioning for
  generate; the reviewer system for review) — the **DEC-8 reviewer firewall is
  provider-independent and structural**: `review_samadhan` still never receives the
  StyleSeed, on either path.
- Extraction hardening mirrors `_extract_json`: refusal output item → clean
  `RuntimeError("LLM declined …")`; `status=="incomplete"` / empty output text →
  `RuntimeError` with status only; bad JSON → `RuntimeError` with char count only.
  NEVER echo content, prompt, or key.

### 3.4 configured() and preflight
`configured()` returns True iff the key for the SELECTED provider is present
(`OPENAI_API_KEY` for openai, `ANTHROPIC_API_KEY` for anthropic). The D2 anti-wedge
contract is preserved automatically: `build()`'s llm preflight calls `configured()`
BEFORE recording intent, so a missing key still refuses without wedging.

### 3.5 Injectable fakes / offline gate
`sdk=` injection keeps working for both providers (an Anthropic-shaped fake when
provider=anthropic — all standing tests untouched; an OpenAI-shaped fake — object with
`.responses.create` — for the new tests). No standing test hits the network or needs a
key. The opt-in live smoke stays gated on `SAMAGRA_LIVE_LLM_SMOKE=1` and becomes
provider-aware; with the real key present it will be RUN ONCE during this slice
(provider=openai) to validate the real boundary — closing the D2 owner follow-up that
was never runnable (no Anthropic key ever arrived).

## 4. Invariants (extend D2/DEC-8 — no new DEC needed; recorded here)
1. Keys env-only from the gitignored `.env`; never hardcoded, logged, or repr'd.
2. Missing/unknown provider or missing key → fail-closed `RuntimeError` at
   construction; `configured()` False → preflight refusal, never a wedge.
3. DEC-8 reviewer firewall structural on BOTH providers.
4. No new prod write path; publish gate untouched; no migration; the 7 subsystems
   untouched; outbound generation is the only network use.
5. Rollback = `SAMAGRA_LLM_PROVIDER=anthropic` (or unset) restores D2 behavior exactly.

## 5. Verification
- TDD offline: provider resolution (default/anthropic/openai/unknown), per-provider
  model defaults + override, effort pass-through + default, configured() per provider,
  openai fake gen + review round-trip, refusal / incomplete / empty / bad-JSON paths,
  key-missing construction failure, no-key-in-repr.
- Live smoke run once (real OpenAI key, `SAMAGRA_LIVE_LLM_SMOKE=1`).
- Full gates (pytest ≈695+new, vitest 639 untouched).
- Codex pre-merge review 32 on the generation boundary; remediate TDD; merge ff; push
  is owner-performed.

## 6. Implementation outcome (2026-07-07)

Built on branch `feature/llm-provider-openai`, commits `48e1556..e3ae45f` (5 commits):
`48e1556` (this spec + 4-task plan), `af2dadd` (provider-aware client — OpenAI Responses
backend beside Anthropic), `145dc2b` (provider env template + openai requirement;
live smoke provider-aware), `42ce9d3` (review-32 M fix — `.env.example` model line made
inert), `e3ae45f` (review-32 L fix — preflight names the selected provider's key var).

**Review chronicle:** per-task 2-lens review (spec compliance + code quality) on each of
the 4 plan tasks = PASS/PASS throughout; OpenAI Responses call shape verified directly
against the installed `openai==2.32` SDK types. Dedicated Codex pre-merge review 32 (the
DEC-7-style generation-boundary review this slice's house convention required) returned
**GO-WITH-CAVEATS**:
- **M** — `.env.example`'s active `SAMAGRA_LLM_MODEL=claude-opus-4-8` line masked the
  code's OpenAI default (`gpt-5.5`) for anyone following the template with only
  `SAMAGRA_LLM_PROVIDER=openai` + `OPENAI_API_KEY` set. **Closed** same-slice in `42ce9d3`
  (the model line is now a commented-out, provider-inert override example; per-provider
  defaults are the documented rule).
- **L** — the missing-key preflight message hardcoded `ANTHROPIC_API_KEY` even when
  `openai` was the selected provider and its key was missing. **Closed** same-slice in
  `e3ae45f` (preflight now names the selected provider's actual key var via the new
  `required_key_var()`).
- **Named finding (not a caveat, adjudicated):** `SAMAGRA_LLM_MODEL` could in principle
  name a non-reasoning OpenAI model while `_create()` always sends `reasoning.effort`.
  Adjudicated **accept-as-operator-responsibility** — this only fires on an explicit
  manual override, and the OpenAI API fails closed cleanly (a clean build-time HTTP
  error, no wedge, no silent misbehavior) rather than corrupting output.

Net: **effectively GO** — both real caveats closed TDD in the same slice, the one
open item is a documented, accepted, fail-closed edge case.

**Live-smoke result:** the opt-in `SAMAGRA_LIVE_LLM_SMOKE=1` smoke was run for real
against the live OpenAI key — **PASS, ~52s**, a genuine `gpt-5.5` generation +
adversarial-review round-trip on the `circular-motion` chapter, artifacts written to
disk. This is the first-ever live validation of the Phase D2 generation boundary end to
end (the Anthropic path never had a key to run this against).

**Gate:** 713 pytest (0 failures, 2 skips = the two opt-in live smokes) + 639 vitest
baseline (frontend untouched by this slice).

**Invariants (§4) status:** all 5 HELD as designed; rollback path
(`SAMAGRA_LLM_PROVIDER=anthropic` or unset) not exercised live this slice but is
structurally identical to pre-slice D2 code (no anthropic-path lines changed in
substance).
