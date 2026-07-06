GO

# DEC-7 pre-merge review: Phase F1 figure lane image boundary

Date: 2026-07-07
Repo: `C:/SandBox/claude_box/TeachingOS`
Branch/head reviewed: `feature/content-factory-phase-f1-figures` at `02e26a9`
Base stated by review request: `main` tip, explicit diff base `a45e047`
Review range: `a45e047..HEAD` (11 commits)
Scope: Phase F1 figure lane: new image-generation boundary, vision-review path, figure artifact engine, factory wiring, HTTP unreachability for `kind="llm"`, and publish compatibility. Ground truth checked against `docs/superpowers/specs/2026-07-07-samagra-content-factory-phase-f1-figure-lane-design.md` and `docs/superpowers/plans/2026-07-07-samagra-content-factory-phase-f1-figure-lane.md`.

## Verdict

GO.

No HIGH, MED, or LOW source findings were found in `a45e047..HEAD`.

The new image boundary is constrained to `samagra/clients/image_client.py`; key handling is env-only, provider/size/quality resolution fails closed, `__repr__` does not expose key material, and `_extract_png` raises concise non-echoing errors for empty/missing/bad base64 responses. The installed SDK is `openai 2.44.0`; its `Images.generate` signature accepts the request fields used here (`prompt`, `model`, `size`, `quality`, `n`), and the OpenAI vision `input_image` shape in `llm_client.py` matches the installed `ResponseInputImageParam`.

The figure lane stays in the existing local-write `kind=="llm"` build envelope. The branch adds only the spec-approved lane preflight dispatch and figure autocapture clause. The HTTP build path refuses all `kind=="llm"` rows before `run.build`, and HTTP approve-seed skips all `llm` / `mcd` children, so the image/vision generation path remains CLI-only.

Worktree note: before this report, the branch already had unrelated dirty/untracked items: `AGENTS.md`, `CLAUDE.md`, `.playwright-mcp/`, `samagra_overhaul.html`, and `tmp/`. I did not modify source files.

## Scope

Files inspected with line-level evidence:
- `samagra/clients/image_client.py`
- `samagra/clients/llm_client.py`
- `samagra/factory/figure.py`
- `samagra/factory/dispatch.py`
- `samagra/factory/lines.py`
- `samagra/factory/run.py`
- `samagra/api/app.py`
- `samagra/factory/publish/run.py`
- `samagra/factory/publish/read.py`
- `samagra/factory/publish/store.py`
- `.env.example`
- `requirements.txt`
- `tests/test_image_client.py`
- `tests/test_llm_client_review_figure.py`
- `tests/test_factory_figure.py`
- `tests/test_factory_figure_wiring.py`
- `tests/test_figure_golden.py`
- `tests/test_api_factory_build.py`
- `tests/test_api_factory_approve_seed.py`
- `docs/superpowers/specs/2026-07-07-samagra-content-factory-phase-f1-figure-lane-design.md`
- `docs/superpowers/plans/2026-07-07-samagra-content-factory-phase-f1-figure-lane.md`

Diff scope checked: `git diff --name-status a45e047..HEAD` lists only `.env.example`, `AGENTS.md`, the F1 spec/plan docs, `requirements.txt`, the new/changed figure and LLM client/factory files, and F1 tests. There is no diff under publish, governance, Pratham, source adapters, or frontend.

## Findings

No findings.

| Severity | Description | Citation |
|---|---|---|
| - | No HIGH/MED/LOW source finding in `a45e047..HEAD`. | - |

## Invariants

| # | Invariant | Verdict | Evidence |
|---|---|---|---|
| 1 | No new prod write path. | HELD | The only new external call is outbound image generation through `ImageClient.generate()` at `samagra/clients/image_client.py:99-108`. The figure engine writes local files under `config.EXPORT_DIR / slug` at `samagra/factory/figure.py:185-226`; governance writes still occur through unchanged `run.build()` event/status rows at `samagra/factory/run.py:414-448` and `samagra/factory/run.py:463-464`. |
| 2 | Figure build writes only local files plus governance rows. | HELD | `build_figures()` writes loose PNGs, a JSON sidecar, and a gallery HTML locally at `samagra/factory/figure.py:185-226`, then returns a result dict at `samagra/factory/figure.py:228-230`. `run.build()` records `product_building`, `product_build_failed` on local failure, `product_created`, and terminal status via the existing ledger path at `samagra/factory/run.py:414-448` and `samagra/factory/run.py:463-464`. |
| 3 | Publish gate untouched. | HELD | No publish code is in the diff. Existing G1 publish still selects captured local artifacts at `samagra/factory/publish/run.py:68-99`, copies only `html` / `json` / `docx` keys at `samagra/factory/publish/run.py:93-98`, and remains owner-invoked at `samagra/factory/publish/run.py:102-182`. |
| 4 | No DB migration. | HELD | The branch adds no migration file and no governance schema edit. Tests explicitly pin stable `PRAGMA user_version` across the F1 golden loop at `tests/test_figure_golden.py:64-73`. |
| 5 | The 7 source subsystems remain read-only. | HELD | The figure lane reads chapter content through `render.load_chapter()` at `samagra/factory/figure.py:178` and does not import or call any source-subsystem writer. The HTTP build endpoint still refuses `llm` and `mcd` rows before `run.build()` at `samagra/api/app.py:414-421`, so the new image lane is not exposed as a network-triggered source write path. |
| 6 | Figure is opt-in and default fan-out is unchanged. | HELD | `LINES["figure"]` is registered as `kind="llm"` with `auto_fan=False` at `samagra/factory/lines.py:42-43`; `classify()` includes only `LINES[k].auto_fan` lanes at `samagra/factory/lines.py:57-59`. The F1 wiring test asserts default textbook classification excludes `figure` at `tests/test_factory_figure_wiring.py:25-28`. |

## Boundary Checks

### Image client

`ImageClient` is the single image-generation call site. Provider and key metadata are centralized at `samagra/clients/image_client.py:19-21`; unknown providers raise in `_provider_from_env()` at `samagra/clients/image_client.py:28-33`, while `configured()` catches that and returns `False` at `samagra/clients/image_client.py:36-44`. Size and quality are allow-listed at `samagra/clients/image_client.py:24-25` and fail closed during construction at `samagra/clients/image_client.py:79-86`.

Key material is read only from `os.environ` at construction time, after the selected key variable is resolved at `samagra/clients/image_client.py:90-97`. `__repr__` reports provider/model only at `samagra/clients/image_client.py:110-111`. `_extract_png()` handles empty data, missing `b64_json`, and undecodable base64 with concise errors that do not echo the prompt, key, or response body at `samagra/clients/image_client.py:53-68`; tests cover those cases at `tests/test_image_client.py:147-168` and the repr/key case at `tests/test_image_client.py:171-176`.

Installed SDK shape was checked locally: `openai.__version__ == 2.44.0`; `Images.generate` accepts `prompt`, `model`, `size`, `quality`, and `n`, matching `samagra/clients/image_client.py:101-107`.

### Vision reviewer

The figure-review system prompt is a physics refutation prompt anchored to brief, section text, and the generated image at `samagra/clients/llm_client.py:88-97`. The structural DEC-8 firewall holds: `review_figure()` has signature `(png_bytes, brief, section_text)` and no StyleSeed parameter at `samagra/clients/llm_client.py:278-288`; the signature test pins that at `tests/test_llm_client_review_figure.py:55-60`.

Both provider paths are shaped correctly. Anthropic vision sends a text part plus a base64 PNG image part at `samagra/clients/llm_client.py:226-239`. OpenAI vision sends system text, user `input_text`, and a data-URI `input_image` part with explicit `detail: "auto"` at `samagra/clients/llm_client.py:240-255`; the installed SDK `ResponseInputImageParam` keys were checked locally and are pinned by `tests/test_llm_client_review_figure.py:89-104`. Parsing reuses the existing never-leak `_parse()` branch at `samagra/clients/llm_client.py:257-260`.

### Figure engine

`build_figures()` selects only `image-need` targets in document order at `samagra/factory/figure.py:39-65`, with a cap read at `samagra/factory/figure.py:29`. No StyleSeed enters the prompt: the prompt is the frozen preamble, chapter/section frame, and brief at `samagra/factory/figure.py:31-36` and `samagra/factory/figure.py:56-60`.

Whole-build raise semantics hold for returned state: a generation or review exception leaves `build_figures()` without returning a partial result, and `run.build()` records `product_build_failed` for all non-`mcd` lanes at `samagra/factory/run.py:429-443`. Stale `fig-*.png` files are cleared before a new run at `samagra/factory/figure.py:185-188`. The retry path is pinned by `tests/test_factory_figure_wiring.py:176-199`.

Reviewer verdict mapping is fail-closed. For each target, the engine looks for the exact zero-based `idx`; missing or misindexed verdicts become `error`, and any verdict other than explicit `"ok"` becomes `error` at `samagra/factory/figure.py:197-206`. The reported `errors` count is the count of `figure["verdict"] == "error"` at `samagra/factory/figure.py:213`, so the artifact preserves truthful reviewer error counts even when autocapture is off. Tests cover missing and error verdicts at `tests/test_factory_figure.py:183-196`.

The gallery HTML escapes untrusted text at the boundary. Section, brief, verdict, rationale, title, subtitle, and kicker are escaped at `samagra/factory/figure.py:143-163`; the PNG is embedded as a data URI at `samagra/factory/figure.py:148-152`. The JSON sidecar keeps raw text and base64 at `samagra/factory/figure.py:221-224`, matching the ratified spec. Tests pin escaping and raw JSON behavior at `tests/test_factory_figure.py:148-168`.

The `items==0` early return in `_assert_figures_present()` is structurally sound. `validate_product()` always calls `_assert_review_clean()` before `_assert_figures_present()` at `samagra/factory/dispatch.py:90-93`; `_assert_review_clean()` requires explicit integer `errors` and `items` fields for all `kind=="llm"` results at `samagra/factory/dispatch.py:145-163`. Only after that does `_assert_figures_present()` early-return for `items == 0` at `samagra/factory/dispatch.py:166-178`, allowing the existing `needs_review` gate to route the empty artifact to `changes` at `samagra/factory/run.py:459-463`. The regression test covers this at `tests/test_factory_figure_wiring.py:202-228`.

### Wiring and HTTP reachability

The figure line is `kind="llm"`, `auto_fan=False`, and `textbook:`-scoped at `samagra/factory/lines.py:42-43`; default classification remains auto-fan-only at `samagra/factory/lines.py:57-59`. `dispatch.run_line()` special-cases `figure` ahead of the generic `kind=="llm"` samadhan branch at `samagra/factory/dispatch.py:46-59`, leaving the samadhan branch behaviorally unchanged. The samadhan preflight regression is pinned at `tests/test_factory_figure_wiring.py:231-255`.

The crash-safety guard block stayed intact: unknown assignment, workflow firewall, approved-status guard, already-built guard, in-flight guard, and the seed-ref validation remain at `samagra/factory/run.py:361-380`, matching the base block aside from line-number shifts. The spec-approved preflight indirection dispatches `figure` to `figure.preflight()` and everything else in `kind=="llm"` to `samadhan.preflight()` at `samagra/factory/run.py:403-412`. The non-`mcd` rollback remains at `samagra/factory/run.py:429-443`.

`SAMAGRA_FIGURE_AUTOCAPTURE` defaults off because `config._env_bool("SAMAGRA_FIGURE_AUTOCAPTURE", False)` is used at `samagra/factory/run.py:461-462`; when the flag is absent or false, every figure build reaches `changes` regardless of a clean reviewer count. Tests pin the default-off and opt-in-on behavior at `tests/test_factory_figure_wiring.py:128-157`.

Over HTTP, figure is structurally unreachable. `/api/factory/build` rejects every assignment whose `LINES[pipeline].kind` is `"llm"` or `"mcd"` with 403 before `factory_run.build()` is called at `samagra/api/app.py:414-421`; since `figure` is `kind="llm"`, it inherits that refusal. `/api/factory/approve-seed` filters children to `spec.kind not in ("llm", "mcd")` at `samagra/api/app.py:367-369`, so a GUI approve-seed click skips figure rows as well.

### Publish story

The publish compatibility claim holds without changing G1/G2. A captured figure result provides a single `html` gallery and `json` sidecar at `samagra/factory/figure.py:220-230`. Existing publish code copies exactly source files under keys `("html", "json", "docx")` at `samagra/factory/publish/run.py:93-98`; it stages bytes and hashes at `samagra/factory/publish/run.py:116-125`, writes immutable publication records at `samagra/factory/publish/run.py:145-182`, and validates path segments in `write_published_file()` at `samagra/factory/publish/store.py:101-107`.

The data-URI-heavy HTML artifact does not introduce a new traversal or schema path. It is just bytes copied as `<chapter>/<basename>` with safe-segment checks at `samagra/factory/publish/store.py:101-107`; the read resolver only serves manifest-selected `html` / `json` / `docx` kinds and re-verifies sha256 before returning bytes at `samagra/factory/publish/read.py:33-70`. The golden test proves gallery HTML plus JSON publish and sha-verified resolve at `tests/test_figure_golden.py:76-98`.

## Verification

- `git status --short --branch` confirmed current branch `feature/content-factory-phase-f1-figures` with pre-existing unrelated dirty/untracked files.
- `git log --oneline a45e047..HEAD` confirmed the 11-commit F1 range ending at `02e26a9`.
- `git diff --name-status a45e047..HEAD` and `git diff --stat a45e047..HEAD` matched the expected F1 surface.
- `git diff --check a45e047..HEAD` was clean.
- Local SDK introspection confirmed `openai 2.44.0`, `Images.generate` accepts the image request shape, and `ResponseInputImageParam` accepts the OpenAI vision part keys used by `_create_vision()`.
- I attempted a targeted offline pytest slice covering image client, vision review, figure engine/wiring/golden, and API factory build/approve-seed tests. The first run was blocked before test bodies by `PermissionError: [WinError 5] Access is denied: 'C:\\Users\\abc\\AppData\\Local\\Temp\\pytest-of-abc'`. Retrying with `TEMP`, `TMP`, and `--basetemp C:\\tmp\\pytest-f1-review-33` was also blocked by `PermissionError: [WinError 5] Access is denied: 'C:\\tmp\\pytest-f1-review-33'`. I therefore did not locally confirm the test suite in this pass.
- Review request ground truth states the actual gate already completed: 765 pytest passed / 3 skipped opt-in live smokes / 0 failures, 639 vitest baseline unchanged, and one live image smoke PASS in 41s. I treated that as supplied verification evidence and kept this report grounded in static diff/source inspection plus the local SDK-shape check.

GO
