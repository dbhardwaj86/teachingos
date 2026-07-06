GO-WITH-CAVEATS

# DEC-7 pre-merge review: LLM provider OpenAI boundary

Date: 2026-07-07
Repo: `C:/SandBox/claude_box/TeachingOS`
Branch/head reviewed: `feature/llm-provider-openai` at `145dc2b`
Base stated by review request: `main`
Review range: `main...feature/llm-provider-openai` (`b46e87a..145dc2b`, 3 commits)
Scope: Provider-aware SAMAGRA LLM boundary for the Phase D2 samadhan lane: `samagra/clients/llm_client.py`, provider tests/smoke, `.env.example`, `requirements.txt`, and the OpenAI provider spec/plan docs. Adjacent unchanged boundary code read: `samagra/factory/samadhan.py`, `samagra/factory/dispatch.py`, and `samagra/factory/run.py`.

## Verdict

GO-WITH-CAVEATS.

The core generation boundary holds: keys are read from environment only, the selected provider's key drives `configured()`, unknown providers are fail-closed, OpenAI calls use the Responses API with strict JSON schema output, the reviewer path remains StyleSeed-free, the Anthropic request shape remains unchanged, and the diff does not touch publish/governance/Pratham or add a production write path.

The caveats are configuration-facing. First, the committed env template still sets `SAMAGRA_LLM_MODEL=claude-opus-4-8`, which masks the code's OpenAI default of `gpt-5.5` for anyone following the template and setting only `SAMAGRA_LLM_PROVIDER=openai` plus `OPENAI_API_KEY`. Second, the preflight error message still names `ANTHROPIC_API_KEY` even when OpenAI is the selected provider and the selected key is missing. Both fail cleanly and do not leak secrets or wedge the build, but they are worth fixing before wider operator handoff.

Worktree note: before this report, the branch already had unrelated dirty items: `AGENTS.md`, `.playwright-mcp/`, `samagra_overhaul.html`, and `tmp/`. I did not modify source files.

## Scope

Files inspected with line-level evidence:
- `samagra/clients/llm_client.py`
- `samagra/factory/samadhan.py`
- `samagra/factory/dispatch.py`
- `samagra/factory/run.py`
- `tests/test_llm_client.py`
- `tests/test_llm_client_providers.py`
- `tests/test_samadhan_live_smoke.py`
- `.env.example`
- `requirements.txt`
- `docs/superpowers/specs/2026-07-07-samagra-llm-provider-openai-design.md`
- `docs/superpowers/plans/2026-07-07-samagra-llm-provider-openai.md`

Diff scope checked: `git diff --name-status main...feature/llm-provider-openai` lists only `.env.example`, the two provider spec/plan docs, `requirements.txt`, `samagra/clients/llm_client.py`, and the three LLM tests/smoke files. Targeted checks against `samagra/factory/samadhan.py`, `samagra/factory/dispatch.py`, `samagra/factory/run.py`, `samagra/factory/publish`, `samagra/governance`, `samagra/pratham`, `samagra/api`, and `frontend` returned no diff.

## Findings

| Severity | Description | Citation |
|---|---|---|
| M | The env template's active `SAMAGRA_LLM_MODEL=claude-opus-4-8` overrides the OpenAI provider default, so an operator who follows the new template and sets only `SAMAGRA_LLM_PROVIDER=openai` plus `OPENAI_API_KEY` will call OpenAI with the Anthropic model instead of the documented/code default `gpt-5.5`. | `.env.example:41-45`; `samagra/clients/llm_client.py:161-162`; `tests/test_llm_client_providers.py:75-80` |
| L | OpenAI missing-key preflight fails closed but reports the wrong key name: `samadhan.preflight()` still raises `ANTHROPIC_API_KEY is not set` whenever provider-aware `configured()` is false, including the OpenAI missing-key case. | `samagra/factory/samadhan.py:48-50`; `samagra/clients/llm_client.py:101-105`; `samagra/clients/llm_client.py:170-175`; `samagra/factory/run.py:402-406` |

## Invariant Checklist

| # | Generation-boundary invariant | Verdict | Justification |
|---|---|---|---|
| 1 | SECRETS: keys read only from env/gitignored `.env`; never hardcoded/logged/repr'd/echoed in error paths. | HELD | `.gitignore:2` ignores `.env`; `config.py` loads it at `samagra/config.py:12-16`; selected key names are centralized in `_KEY_VARS` at `samagra/clients/llm_client.py:21-24`; real key values are read only via `os.environ.get` at `samagra/clients/llm_client.py:89-105` and `samagra/clients/llm_client.py:170-181`; `__repr__` includes provider/model only at `samagra/clients/llm_client.py:225-226`. Runtime errors include provider/effort/key variable names and response metadata, not key values or response bodies, at `samagra/clients/llm_client.py:92-93`, `samagra/clients/llm_client.py:115-151`, `samagra/clients/llm_client.py:159-166`, and `samagra/clients/llm_client.py:173-175`. |
| 2 | FAIL-CLOSED: unknown provider / unknown effort / missing key fail closed; `configured()` false on unknown provider; build preflight checks before recording intent. | HELD | `_provider_from_env()` rejects unknown providers at `samagra/clients/llm_client.py:89-94`; `configured()` catches that and returns `False` at `samagra/clients/llm_client.py:101-105`; `LLMClient.__init__` rejects unknown provider and unknown effort at `samagra/clients/llm_client.py:155-166`; missing selected key raises before SDK construction at `samagra/clients/llm_client.py:170-181`. `run.build()` calls `samadhan.preflight()` before `product_building` at `samagra/factory/run.py:402-408`, and `preflight()` delegates to `llm_client.configured()` at `samagra/factory/samadhan.py:42-50`. The LOW finding is diagnostic only: the missing-key preflight message names Anthropic even on the OpenAI path. |
| 3 | DEC-8 REVIEWER FIREWALL: `review_samadhan` must never receive StyleSeed on the OpenAI path. | HELD | StyleSeed conditioning is assembled only for generation in `build_samadhan()` at `samagra/factory/samadhan.py:91-95`. The reviewer call passes only `items` and chapter content at `samagra/factory/samadhan.py:95-98`. `LLMClient.review_samadhan()` uses frozen `_REVIEW_SYSTEM` and constructs the review payload from chapter plus items at `samagra/clients/llm_client.py:216-223`. The OpenAI `_create()` path sends system first and user second at `samagra/clients/llm_client.py:194-201`. The provider test asserts the OpenAI reviewer system contains the ground-truth checker text and no `STYLE` at `tests/test_llm_client_providers.py:150-156`. |
| 4 | RESPONSES-API correctness: valid call shape and fail-closed OpenAI extraction ordering; no silent wrong parse. | HELD | `requirements.txt:20` pins `openai>=2.32`. The OpenAI branch calls `responses.create` with `model`, `max_output_tokens`, `reasoning={"effort": ...}`, `input` roles `system` then `user`, and `text.format` as strict `json_schema` with `name`, `schema`, and `strict` at `samagra/clients/llm_client.py:194-201`; offline tests assert the key shape at `tests/test_llm_client_providers.py:136-147` and effort pass-through at `tests/test_llm_client_providers.py:159-164`. OpenAI's current Responses API reference documents `input` as string or input-item array, system/user role hierarchy, `max_output_tokens`, `reasoning`, response `output_text`, and `text.format` on create responses: https://developers.openai.com/api/reference/resources/responses/methods/create. `_extract_json_openai()` orders failures as incomplete, refusal, empty, bad JSON at `samagra/clients/llm_client.py:132-151`, and tests cover refusal/incomplete/empty/bad-json never-echo behavior at `tests/test_llm_client_providers.py:169-195`. With strict schema plus JSON parse, I did not find a realistic completed-response shape that silently parses the wrong object; failed/incomplete responses either raise from status or empty/bad JSON. |
| 5 | BACK-COMPAT: Anthropic path byte-identical in substance; standing D2 tests not weakened. | HELD | The Anthropic `_create()` branch preserves the same model, max token, adaptive thinking, cached system, Anthropic JSON schema format, and user message shape at `samagra/clients/llm_client.py:183-193` as main's `samagra/clients/llm_client.py` call. Existing `tests/test_llm_client.py` changes are environment-isolation `monkeypatch.delenv("SAMAGRA_LLM_PROVIDER")` additions and do not weaken assertions; the diff keeps model/thinking/cache/output-config/reviewer-firewall/error-cleanliness assertions at `tests/test_llm_client.py:27-110`. The new provider test pins the Anthropic branch at `tests/test_llm_client_providers.py:207-216`. |
| 6 | Named finding to adjudicate: `SAMAGRA_LLM_MODEL` can name a non-reasoning OpenAI model while `_create()` sends `reasoning`. | OPEN-QUESTION | For explicit operator overrides, I accept this as operator responsibility: `_create()` passes the configured model and reasoning effort at `samagra/clients/llm_client.py:194-201`; an incompatible model should be rejected by the OpenAI API as a clean build failure, and the owner's current config is stated to be `gpt-5.5`. However, the env template itself currently seeds the wrong model override for OpenAI users; that is the MED finding above and should not be dismissed as operator error. |
| 7 | No new prod write path / publish gate untouched / no migration / diff confined to listed files. | HELD | The diff is confined to the expected provider client, tests/smoke, env template, requirements, and docs. Targeted diffs for `samagra/factory/publish`, `samagra/governance`, `samagra/pratham`, `samagra/api`, `frontend`, and the adjacent unchanged `samagra/factory/{samadhan,dispatch,run}.py` returned empty. The samadhan lane still writes only local artifacts at `samagra/factory/samadhan.py:115-124`, while terminal capture/changes status remains in `run.build()` at `samagra/factory/run.py:443-452`. |

## Evidence

### M - `.env.example` masks the OpenAI default model

The provider code has the intended per-provider default table: `_DEFAULT_MODELS = {"anthropic": "claude-opus-4-8", "openai": "gpt-5.5"}` at `samagra/clients/llm_client.py:21-23`. But that default is reached only when `SAMAGRA_LLM_MODEL` is absent or blank, because `LLMClient.__init__` chooses `model or os.environ.get("SAMAGRA_LLM_MODEL") or _DEFAULT_MODELS[self._provider]` at `samagra/clients/llm_client.py:161-162`.

The committed template still sets `SAMAGRA_LLM_MODEL=claude-opus-4-8` as an active line immediately before the new provider controls at `.env.example:40-46`. Therefore a fresh operator copying the template and enabling only `SAMAGRA_LLM_PROVIDER=openai` plus `OPENAI_API_KEY` will not get the documented OpenAI default `gpt-5.5`; the env override forces the Anthropic model name into the OpenAI call. The OpenAI default test deliberately deletes `SAMAGRA_LLM_MODEL` before asserting `gpt-5.5` at `tests/test_llm_client_providers.py:75-80`, so it does not cover the template-as-copied path.

This fails cleanly at the API/model boundary, not as a secret leak or governance write, so I am treating it as a merge caveat rather than a hard safety blocker.

### L - OpenAI missing-key preflight names Anthropic

The provider-aware low-cost check is correct: `configured()` resolves the selected provider and checks only `_KEY_VARS[p]` at `samagra/clients/llm_client.py:101-105`. The real constructor also emits the selected key variable name in the missing-key error at `samagra/clients/llm_client.py:170-175`.

However, the build preflight path does not call the constructor before recording intent. It calls `samadhan.preflight()` first at `samagra/factory/run.py:402-406`; `preflight()` checks `llm_client.configured()` and then raises a hardcoded `ANTHROPIC_API_KEY is not set` message at `samagra/factory/samadhan.py:48-50`. With `SAMAGRA_LLM_PROVIDER=openai` and no `OPENAI_API_KEY`, the refusal is still before `product_building`, so the no-wedge contract holds, but the operator gets the wrong remediation.

### Clean Checks

| Area | Verdict | Evidence |
|---|---|---|
| Secret values | HELD | `.env` is ignored at `.gitignore:2`; the provider client reads only env variables and never stores key values in `__repr__` at `samagra/clients/llm_client.py:170-181` and `samagra/clients/llm_client.py:225-226`; tests assert no key/body echo at `tests/test_llm_client.py:42-46`, `tests/test_llm_client.py:95-101`, `tests/test_llm_client_providers.py:190-202`. |
| OpenAI reviewer firewall | HELD | `review_samadhan()` uses `_REVIEW_SYSTEM`, not the StyleSeed-conditioned system, at `samagra/clients/llm_client.py:216-223`; OpenAI system-first input is at `samagra/clients/llm_client.py:194-201`; the OpenAI test checks no `STYLE` in reviewer system at `tests/test_llm_client_providers.py:150-156`. |
| Anthropic back-compat | HELD | Existing tests retain request shape assertions at `tests/test_llm_client.py:49-62` and `tests/test_llm_client.py:104-110`; new provider test pins the Anthropic branch at `tests/test_llm_client_providers.py:207-216`. |
| Build/publish boundary | HELD | The LLM preflight still runs before `product_building` at `samagra/factory/run.py:402-408`; local produce failures emit `product_build_failed`, not a permanent in-flight wedge, at `samagra/factory/run.py:424-437`; publish/governance/Pratham/API/frontend files are outside the diff. |

## Verification

- `git status --short --branch` confirmed current branch `feature/llm-provider-openai` at `145dc2b` with pre-existing unrelated dirty/untracked items.
- `git log --oneline main..feature/llm-provider-openai` confirmed the 3 stated commits: `48e1556`, `af2dadd`, `145dc2b`.
- `git diff --stat main...feature/llm-provider-openai` and `git diff --name-status main...feature/llm-provider-openai` matched the requested file scope.
- `git diff --check main...feature/llm-provider-openai` was clean.
- Targeted no-diff checks for publish/governance/Pratham/API/frontend and adjacent factory boundary files were clean.
- I did not rerun the live OpenAI smoke or pytest suite in this read-only review pass. The review is grounded in static diff/source inspection plus the request's stated prior live smoke result.

GO-WITH-CAVEATS
