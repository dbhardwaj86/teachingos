NO-GO

# DEC-7 pre-merge review: Slice R combinedDBQues rewire

Date: 2026-07-06
Repo: `C:/SandBox/claude_box/TeachingOS`
Branch/head reviewed: `feature/combineddbques-rewire` at `207ae08`
Base stated by review request: `main`
Review range: `main...feature/combineddbques-rewire` (`2fa3e8f..207ae08`, 10 commits)
Scope: Slice R question-bank seam rewire from legacy QX `:8783` to combinedDBQues `:8790`, including config defaults/rollback envs, `chapter_map.json`, `samagra/factory/paper.py` retrieval and dedupe, direct QX sqlite readers, QX HTTP client/proxy behavior, focused tests, and read-only fork-side renderer evidence from `C:/SandBox/claude_khanak_box/combinedDBQues`.

## Verdict

NO-GO.

The read-only firewall held: I found no SAMAGRA write path to combinedDBQues, no non-`mode=ro` sqlite reader for the QX DBs in the touched code, and no mutating HTTP verb to `/api/qsearch`/`:8790`. The answer-leak guard also still fires for `kind == "qx"` artifacts and covers the fork's observed answer-bearing renderers.

The blocker is dedupe correctness. Slice R says `_dedupe_results` mirrors the fork's `dupes.py` 40-character normalization, but SAMAGRA dedupes from rendered HTML after stripping tags. The fork's duplicate detector normalizes `text_projection`, while `/api/qsearch` puts math in rendered HTML attributes (`data-tex`, `title`, `alt`). SAMAGRA's tag-strip projection erases those formulas/images and can collapse distinct questions before drill slicing.

Worktree note: before this report, the branch already had unrelated dirty items: `AGENTS.md`, `CLAUDE.md`, `.playwright-mcp/`, and `samagra_overhaul.html`. Running the focused pytest suite created `tmp/pytest-review31`; cleanup attempts were blocked by shell policy, so that temp directory remains untracked. I did not modify source files.

## Scope

Files inspected with line-level evidence:
- `samagra/factory/paper.py`
- `samagra/factory/chapter_map.py`
- `samagra/factory/dispatch.py`
- `samagra/factory/lines.py`
- `samagra/factory/run.py`
- `samagra/adapters/qx.py`
- `samagra/clients/qx_client.py`
- `samagra/api/app.py`
- `samagra/config.py`
- `.env.example`
- `chapter_map.json`
- `tests/test_factory_paper.py`
- `tests/test_chapter_map.py`
- `tests/test_config_combineddb.py`
- `tests/test_adapters_qx_live.py`
- `tests/test_qx_live_smoke.py`
- `C:/SandBox/claude_khanak_box/combinedDBQues/app/gui/qx_browser.py`
- `C:/SandBox/claude_khanak_box/combinedDBQues/app/tools/qx/json_search.py`
- `C:/SandBox/claude_khanak_box/combinedDBQues/app/tools/qx/render_html.py`
- `C:/SandBox/claude_khanak_box/combinedDBQues/app/tools/qx/dupes.py`
- `C:/SandBox/claude_khanak_box/combinedDBQues/app/tools/qx/paper_render.py`

Diff scope checked: `git diff --name-only main...feature/combineddbques-rewire` lists only the 17 expected seam/config/docs/test files. No `governance/`, `pratham/`, publish implementation, or frontend Publish files are in the diff.

## Findings

| Severity | Description | Citation |
|---|---|---|
| M | `_dedupe_results` can drop distinct math/image questions because it strips rendered HTML tags/attributes instead of normalizing the fork's `text_projection`. | `samagra/factory/paper.py:43-56`; fork `app/tools/qx/dupes.py:19-25`; fork `app/tools/qx/render_html.py:90-98` |
| L | Retrieval/rollback is not fail-visible: mapped chapter lookup and fallback remain active under the documented legacy rollback, so the three rollback env lines do not restore old paper/drill retrieval semantics end-to-end. | `.env.example:60-63`; `samagra/factory/paper.py:154-160`; `samagra/factory/chapter_map.py:20-23` |

## Evidence

### M - Dedupe erases formulas/images before comparing questions

`_dedupe_results` builds its duplicate key from `r.get("html")`, removes every HTML tag with `_TAG_RE`, collapses whitespace, lowercases, and treats equal strings of length at least 40 as duplicates at `samagra/factory/paper.py:43-56`. That is not the same input the fork uses: combinedDBQues `dupes.py` defines `MIN_PROJECTION_CHARS = 40` and `_norm(text) = " ".join((text or "").split()).lower()` over the `questions.text_projection` rows at fork `app/tools/qx/dupes.py:19-25` and `app/tools/qx/dupes.py:28-42`.

The served `/api/qsearch` route calls `_api_qsearch` at fork `app/gui/qx_browser.py:1411-1413`, which delegates to `json_search.search_payload` at fork `app/gui/qx_browser.py:1131-1156`. That payload renders each result through `render_question_html`, which includes passage/stem/options/matrix only at fork `app/tools/qx/json_search.py:27-71` and inserts the rendered HTML into result rows at fork `app/tools/qx/json_search.py:110-120`.

For math, the fork's standalone renderer emits the formula in tag attributes: `<span class="ktx" data-tex="...">` plus hidden `<img ... title="..." alt="...">` at fork `app/tools/qx/render_html.py:90-98`. SAMAGRA's `_TAG_RE` removes those complete tags, including the attributes, so two questions with identical prose but different formulas collapse to the same projection.

I verified the pure-function repro locally:

```text
rows q1/q2 differed only by data-tex/title/alt: r=mv/(qB) vs r=2mv/(qB)
paper._dedupe_results(rows) -> ['q1']
both SAMAGRA projections -> "a charged particle moves in a uniform magnetic field. find the radius of the path for the given expression"
```

This can understock a drill because dedupe runs before the drill slice at `samagra/factory/paper.py:178-180`. The tests cover exact HTML duplicates, whitespace/case duplicates, short-text exemption, purity, and pre-slice ordering at `tests/test_factory_paper.py:221-253`, but they do not cover formula-distinct or image-distinct rows.

Suggested fix: dedupe on a stable upstream text field that preserves math/image distinctions. If `/api/qsearch` does not expose full `text_projection`, extend the QX payload to include it or include a server-provided `cluster_hash`; do not derive duplicate identity by stripping rendered HTML.

### L - Rollback/fallback does not restore old paper/drill semantics

The documented rollback says the old engine is restored with only three env lines: `SAMAGRA_QX_SERVER_URL=http://127.0.0.1:8783`, `SAMAGRA_QX_BUILDER_DB=...builder.sqlite`, and `SAMAGRA_QX_CONTENT_DB=...qx_content.sqlite` at `.env.example:60-63`.

Those lines do switch the HTTP client/DB paths, but paper/drill retrieval still unconditionally consults the new committed `chapter_map.json`: `_retrieve` loads `chapter_map.load().get(slug)`, sends `client.search(q="", mode="exact", chapter=entry["chapter"], page=1)`, and returns that payload if it has any results at `samagra/factory/paper.py:154-158`. Only unmapped or zero-hit chapter calls fall back to the legacy de-hyphenated text query at `samagra/factory/paper.py:159-160`.

That means rollback does not guarantee the old retrieval behavior for mapped slugs. Against an old engine that has any matching broad NCERT chapter facet, a paper for a slug like `circular-motion` is chapter-wide rather than the old slug text query. Against an old engine or curation state with zero mapped hits, the fallback can still make the build pass and record `"chapter": null`, masking the mapping/engine drift rather than failing visible. The loader also deliberately returns `{}` on missing or malformed map files at `samagra/factory/chapter_map.py:20-23`, which routes every slug into fallback.

Suggested fix: make rollback disable chapter-map retrieval explicitly, or add an env/version guard such as `SAMAGRA_QX_RETRIEVAL=legacy|chapter_map`. For curation drift, consider failing mapped slugs on zero chapter hits unless an explicit legacy fallback flag is set.

## Invariant Checks

| # | DEC-15 candidate invariant | Verdict | Evidence |
|---|---|---|---|
| 1 | READ-ONLY invariant on combinedDBQues: only HTTP GET `/api/qsearch` or sqlite `mode=ro`; no writes or mutating verbs to `:8790`. | HELD | `QxClient.search` uses `requests.get(.../api/qsearch)` at `samagra/clients/qx_client.py:29-37`. The QX adapter `_ro` opens `file:{path}?mode=ro` at `samagra/adapters/qx.py:20-25`. Repo search found no `immutable=1` remaining in SAMAGRA code and no mutating HTTP verb aimed at QX; existing `requests.post` users are MCD/Munshi/notify clients, not the question-bank seam. |
| 2 | Answer-leak guard integrity for `kind == "qx"` artifacts and marker coverage for fork renderers. | HELD | `paper` and `drill` are `kind="qx"` at `samagra/factory/lines.py:32-35`; `run.build` calls `dispatch.validate_product` after producing non-mcd artifacts at `samagra/factory/run.py:413-420`; `validate_product` calls `_assert_no_answer_leak` at `samagra/factory/dispatch.py:79-90`; `_assert_no_answer_leak` scans both html and json artifacts for answer markers at `samagra/factory/dispatch.py:106-139`. Fork `/api/qsearch` renders only passage/stem/options/matrix at fork `app/tools/qx/json_search.py:27-71`; fork answer-bearing renderers use `class="answer"`/`answer-label` at fork `app/gui/qx_browser.py:1058-1077` and `pq-ans`/`pkey` at fork `app/tools/qx/paper_render.py:109-120` and `app/tools/qx/paper_render.py:210-220`. |
| 3 | Retrieval fallback correctness: mapped, unmapped, and zero-hit branches do not silently return wrong content or mask curation errors. | VIOLATED | Mapped slugs return the first nonempty chapter-facet payload with no independent slug/concept validation at `samagra/factory/paper.py:154-158`; unmapped and zero-hit mapped slugs fall back to text query at `samagra/factory/paper.py:159-160`; malformed/missing maps become `{}` at `samagra/factory/chapter_map.py:20-23`. This is fail-open for curation drift. |
| 4 | Dedupe purity/correctness: order preserving, no input mutation, short-text exemption, and drill slicing after dedupe. | VIOLATED | Order/purity/short-text/pre-slice behavior is covered by `samagra/factory/paper.py:43-56` and `samagra/factory/paper.py:178-180`, with tests at `tests/test_factory_paper.py:221-253`; but the duplicate key itself is wrong for formula/image-distinct rows because it strips rendered HTML tags and attributes instead of using the fork's `text_projection` normalization. See MED finding. |
| 5 | Config rollback honesty: the three documented rollback lines restore the old engine end-to-end. | VIOLATED | `.env.example:60-63` documents only URL/DB path overrides. The new chapter-map retrieval path remains active regardless of URL/DB root at `samagra/factory/paper.py:154-160`, so rollback can still use broad mapped chapter listing or silent fallback instead of legacy slug text retrieval. |
| 6 | Invariant preservation: no new prod write path; publish gate untouched; no DB/governance migration; no secrets added/logged; diff remains inside question-bank seam. | HELD | Diff scope is the 17 expected files: `.env.example`, `chapter_map.json`, `concept_aliases.json`, docs, QX adapter/client/config/paper/chapter_map, and tests. No `samagra/governance/`, `samagra/pratham/`, publish implementation, or frontend Publish files are touched. `git diff --check main...feature/combineddbques-rewire` was clean. |
| 7 | Live-WAL correctness: plain `mode=ro` is safe/correct for live WAL, and no other touched reader still uses `immutable=1`. | HELD | `_ro` now uses `file:{path}?mode=ro` at `samagra/adapters/qx.py:20-25`. The focused WAL regression proves a read-only connection sees a commit after open and refuses writes at `tests/test_adapters_qx_live.py:9-31`. Repo search found no remaining `immutable=1` in SAMAGRA code. |

## Test Evidence

Commands and checks run:

- `git diff --stat main...feature/combineddbques-rewire` -> 17 files, `+615/-52`, matching the requested scope.
- `git diff --name-only main...feature/combineddbques-rewire` -> only the expected seam/config/docs/test files; no governance/pratham/publish implementation files.
- `git diff --check main...feature/combineddbques-rewire` -> clean.
- Repo search for `immutable=1`, `mode=ro`, `sqlite3.connect`, mutating HTTP verbs, `/api/qsearch`, and QX envs across `samagra`, `tests`, `.env.example`, and `docs/deploy-tunnel.md`.
- Fork-side read-only search/inspection of combinedDBQues `app/gui/qx_browser.py`, `app/tools/qx/json_search.py`, `app/tools/qx/render_html.py`, `app/tools/qx/dupes.py`, and `app/tools/qx/paper_render.py`.
- Live sidecar smoke: `GET http://127.0.0.1:8790/api/qsearch?q=gauss&mode=exact&page=1` returned HTTP 200.
- Focused pytest: `SAMAGRA_LIVE_QX_SMOKE=1 .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider --basetemp .\tmp\pytest-review31 tests\test_factory_paper.py tests\test_chapter_map.py tests\test_config_combineddb.py tests\test_adapters_qx_live.py tests\test_qx_live_smoke.py` -> `28 passed in 2.93s`.
- Pure-function repro for the MED finding: two rows differing only by formula attributes (`r=mv/(qB)` vs `r=2mv/(qB)`) collapsed to one row under `paper._dedupe_results`.

Test gap assessment:

- Covered strongly: mapped/unmapped/zero-hit retrieval branch calls, artifact `chapter`/`query` recording, answer-free live smoke markers, dedupe order/short-text/pre-slice/purity for text-only rows, config defaults, committed map canonical vocabulary, WAL read visibility, and write refusal for `mode=ro`.
- Missing and load-bearing: formula/image-distinct dedupe regression test, and an explicit rollback-mode test proving paper/drill use legacy text retrieval when the three rollback env lines are set.

NO-GO

## ADDENDUM

Date: 2026-07-07
Delta reviewed: `207ae08..b714b28` on `feature/combineddbques-rewire`
Commits reviewed: `b8a29a9`, `e019787`, `b714b28`

Delta verdict: NO-GO on the `b8a29a9..b714b28` remediation delta.

Updated OVERALL verdict for `main...feature/combineddbques-rewire`: NO-GO.

### Direct Answers To Review Focus

1. Does `e019787` fully resolve the original MED?

No. It resolves the common KaTeX formula path: `_projection()` now appends `data-tex` values before tag stripping at `samagra/factory/paper.py:41-49`, and `_dedupe_results()` uses that projection at `samagra/factory/paper.py:52-64`. That covers the combinedDBQues standalone math render where non-empty math segments produce `<span class="ktx" data-tex="...">` plus hidden equation images at `C:/SandBox/claude_khanak_box/combinedDBQues/app/tools/qx/render_html.py:73-98`.

It does not fully close the false-collision class from review 31. Upstream figure segments still render as `<img class="fig" ... alt="{asset_id}">` at `C:/SandBox/claude_khanak_box/combinedDBQues/app/tools/qx/render_html.py:111-114`, but `_projection()` strips the whole tag and appends only `data-tex`, not `alt`, `src`, or another image identity at `samagra/factory/paper.py:41-49`. Two long-enough questions with identical visible prose and different figures can still collapse under the `len(proj) >= 40` duplicate gate at `samagra/factory/paper.py:58-64`. The new tests cover only `data-tex` differences at `tests/test_factory_paper.py:330-373`; there is no image/alt/src-distinct regression.

2. Does `b714b28` resolve the original LOW honestly?

Partially, but not completely. The docs now honestly say the COMBINEDDB-QX scheduled task is not registered and give the owner one-liner at `.env.example:54-60` and `docs/deploy-tunnel.md:219-233`; that resolves the separate owner-step visibility claim.

For rollback, the code is materially better than review 31 because mapped retrieval is no longer chapter-only: tier 1 sends `q=<slug text>, mode=exact, chapter=<mapped chapter>`, tier 2 sends the same query in semantic mode, and tier 3 falls back to exact query with no chapter at `samagra/factory/paper.py:173-186`. However, the documentation still says chapter-scoped tiers "will no-op against the old engine" and "Pre-Slice-R retrieval semantics come back with zero code changes" at `.env.example:68-73` and `docs/deploy-tunnel.md:244-249`. That is not enforced by the code; mapped tiers remain active under rollback, and fallback is silent rather than fail-visible. If the legacy engine returns any chapter-scoped hits for the mapped display name, SAMAGRA will accept those before tier 3. So the original LOW is reduced but not fully resolved.

3. Does `b8a29a9` introduce a new defect?

Yes, one LOW around mode/meta fidelity. The answer-leak guard still covers all paper/drill response shapes that become artifacts: `paper` and `drill` are `kind="qx"` at `samagra/factory/lines.py:32-35`; `run.build()` validates non-MCD products after `dispatch.run_line()` at `samagra/factory/run.py:418-420`; and `_assert_no_answer_leak()` scans both written `html` and sibling `json` artifacts at `samagra/factory/dispatch.py:118-139`. `build_paper()` writes only `q_uid`, `q_type`, and `html` into the JSON artifact at `samagra/factory/paper.py:216-223`, so all returned tiers are checked through the same artifact boundary.

The new tiered retrieval also preserves the no-partial-artifact property for `_retrieve()` exceptions: `_retrieve()` runs inside the `try` at `samagra/factory/paper.py:195-202`, while `out.mkdir()` and both `write_text()` calls happen only after the try at `samagra/factory/paper.py:210-233`. Through the higher-level factory boundary, a failed qx/local produce can still emit the pre-existing `product_building` and compensating `product_build_failed` events at `samagra/factory/run.py:407-437`; it does not emit `product_created`.

The new defect is metadata fidelity when semantic search degrades. `_retrieve()` records `{"mode": "semantic"}` whenever the semantic request returns any results at `samagra/factory/paper.py:180-183`, and `build_paper()` persists that value in the artifact at `samagra/factory/paper.py:216-223`. But QX explicitly surfaces degraded semantic searches as exact results with `degraded=True`: `json_search.search_payload()` documents that semantic can degrade to exact at `C:/SandBox/claude_khanak_box/combinedDBQues/app/tools/qx/json_search.py:93-99`, returns `mode` and `degraded` in the payload at `C:/SandBox/claude_khanak_box/combinedDBQues/app/tools/qx/json_search.py:123-129`, and `search.run_search()` returns `mode: "exact", degraded: True` after `SemanticUnavailable` at `C:/SandBox/claude_khanak_box/combinedDBQues/app/tools/qx/search.py:148-174`. SAMAGRA ignores those returned fields, so an exact-degraded fallback can be mislabeled as semantic.

### Findings

| Severity | Description | Citation |
|---|---|---|
| M | Remaining from review 31: dedupe can still drop distinct figure/image-based questions because `_projection()` preserves only visible text plus `data-tex`, while upstream figure identity lives in stripped `<img>` attributes such as `alt`/`src`. | `samagra/factory/paper.py:41-49`; `samagra/factory/paper.py:58-64`; `C:/SandBox/claude_khanak_box/combinedDBQues/app/tools/qx/render_html.py:111-114`; `tests/test_factory_paper.py:330-373` |
| L | Remaining from review 31: rollback docs now disclose the tiered fallback, but they overclaim that mapped chapter tiers will no-op under legacy rollback; the code still silently accepts mapped-tier hits before tier 3. | `.env.example:68-73`; `docs/deploy-tunnel.md:244-249`; `samagra/factory/paper.py:173-186` |
| L | New in `b8a29a9`: artifact `mode` can say `semantic` even when QX degraded semantic search to exact, because `_retrieve()` records the requested mode instead of the returned `mode`/`degraded` payload. | `samagra/factory/paper.py:180-183`; `samagra/factory/paper.py:216-223`; `C:/SandBox/claude_khanak_box/combinedDBQues/app/tools/qx/search.py:148-174`; `C:/SandBox/claude_khanak_box/combinedDBQues/app/tools/qx/json_search.py:123-129` |

### Clean Checks

| Area | Verdict | Evidence |
|---|---|---|
| `data-tex` formula collision from original MED | RESOLVED for normal standalone math | `_projection()` appends `data-tex` values at `samagra/factory/paper.py:41-49`; upstream standalone math emits `data-tex` for non-empty latex at `C:/SandBox/claude_khanak_box/combinedDBQues/app/tools/qx/render_html.py:73-98`; tests pin data-tex distinctness at `tests/test_factory_paper.py:336-373`. |
| Same-chapter byte-identical artifacts from chapter-only listing | RESOLVED in the inspected code path | `_retrieve()` now sends a slug-derived query in both mapped tiers at `samagra/factory/paper.py:173-183`, and only then falls back to the same slug query without chapter at `samagra/factory/paper.py:184-186`; the regression test checks different same-chapter slugs send different queries at `tests/test_factory_paper.py:180-190`. |
| Answer-leak guard coverage across exact, semantic, and legacy tiers | HELD | All tiers feed the same `build_paper()` artifact writer at `samagra/factory/paper.py:195-223`; `paper`/`drill` remain `kind="qx"` at `samagra/factory/lines.py:32-35`; `dispatch._assert_no_answer_leak()` scans both artifact files at `samagra/factory/dispatch.py:118-139`. |
| New tiered retrieval exception path | HELD for artifacts; governance has intentional failure rows | `_retrieve()` exceptions occur before output directory creation and `write_text()` at `samagra/factory/paper.py:195-233`. Via `run.build()`, qx/local failures append `product_build_failed` to reconcile the earlier `product_building`, but no `product_created` is emitted at `samagra/factory/run.py:407-437`. |

### Test / Verification Note

I did not rerun the stated 689-test full gate or the live circular-motion/friction replay in this addendum pass. This review is grounded in the requested diff, surrounding source, and upstream combinedDBQues render/search source. `git diff --check 207ae08..b714b28` was clean.

NO-GO

## ADDENDUM-2

Date: 2026-07-07
Delta reviewed: `b714b28..5ca4f98` on `feature/combineddbques-rewire`
Commits reviewed: `ce24ff6`, `d412346`, `5ca4f98`

Delta verdict: GO-WITH-CAVEATS on the `b714b28..5ca4f98` remediation delta.

Updated OVERALL verdict for `main...feature/combineddbques-rewire` (`2fa3e8f..5ca4f98` combined): GO-WITH-CAVEATS.

### Per-Finding Resolution Verdicts

| Prior finding | Resolution verdict | Evidence |
|---|---|---|
| L from ADDENDUM: artifact `mode` could lie as `semantic` when QX degraded semantic to exact. | RESOLVED for the valid QX server contract. | `_retrieve()` now records `payload.get("mode")` before falling back to the requested tier mode at all three return sites: tier 1 exact+chapter at `samagra/factory/paper.py:193-197`, tier 2 semantic+chapter at `samagra/factory/paper.py:198-202`, and tier 3 legacy exact/no chapter at `samagra/factory/paper.py:203-206`. The fork source confirms semantic degradation falls through to exact and returns `{"mode": "exact", "degraded": True}` at `C:/SandBox/claude_khanak_box/combinedDBQues/app/tools/qx/search.py:148-174`, and `json_search.search_payload()` propagates those fields at `C:/SandBox/claude_khanak_box/combinedDBQues/app/tools/qx/json_search.py:93-99` and `C:/SandBox/claude_khanak_box/combinedDBQues/app/tools/qx/json_search.py:123-130`. The new regression is not vacuous: `_DegradedSemanticQx` returns only 2 exact rows to force tier 2, then returns a semantic-request payload with `mode: "exact", degraded: True` at `tests/test_factory_paper.py:293-306`; `test_meta_records_server_reported_mode_not_requested_mode` asserts the persisted artifact mode is `exact` at `tests/test_factory_paper.py:309-319`. That assertion would fail under the pre-fix `mode: "semantic"` return. The companion undegraded test still pins normal semantic metadata at `tests/test_factory_paper.py:322-334`. |
| L from ADDENDUM: rollback docs overclaimed mapped tiers would no-op / rollback would be byte-identical. | RESOLVED. | `.env.example` now says most mapped display names are absent from the old engine vocabulary, but specifically carves out Current Electricity, Laws of Motion, Gravitation, Thermodynamics, Electromagnetic Induction, and Electromagnetic Waves as old-engine chapter-scoped rollback, deterministic and answer-free but not byte-identical, at `.env.example:68-78`. `docs/deploy-tunnel.md` says the same at `docs/deploy-tunnel.md:244-255`. That matches current code behavior: mapped slugs try exact+chapter, then semantic+chapter, then exact/no-chapter fallback at `samagra/factory/paper.py:190-206`; the six display names are present in `chapter_map.json` at `chapter_map.json:9`, `chapter_map.json:12`, `chapter_map.json:22-23`, `chapter_map.json:29`, and `chapter_map.json:53-54`. I also live-checked the legacy `:8783` server with empty-query chapter facets: the six named chapters returned nonzero totals, while negative examples such as `Motion in a Plane` and `Electric Charges and Fields` returned zero, so the carve-out is behaviorally accurate in the current environment. |
| M from ADDENDUM: dedupe blind to `img` `src`/`alt` could collapse distinct figure/image questions. | RESOLVED as accepted-by-design, with residual quality-only risk. | `_projection()` now explicitly documents the design pin: it includes visible text plus `data-tex`, deliberately excludes `img` `src`/`alt`, explains per-paper asset-path divergence, generic alt text, the 127-row/5-chapter census claim, and alignment with combinedDBQues text-only `text_projection` at `samagra/factory/paper.py:44-61`. The fork's own duplicate detector normalizes `questions.text_projection` only at `C:/SandBox/claude_khanak_box/combinedDBQues/app/tools/qx/dupes.py:1-7` and `C:/SandBox/claude_khanak_box/combinedDBQues/app/tools/qx/dupes.py:24-42`. The new regression pins the intended behavior by creating two raw-HTML-distinct rows differing only by equation image `src`, then asserting dedupe collapses them to `["f1"]` at `tests/test_factory_paper.py:420-447`; that test would fail if `src` were added back into the projection. The 127-row/25-collision census itself is not traceable to a saved script, fixture, or data artifact in `b714b28..5ca4f98`; it appears only in comments/docstrings found at `samagra/factory/paper.py:48-58` and `tests/test_factory_paper.py:421-430`. Even so, the design rationale is coherent because including per-paper asset paths would split true duplicate captures, and the residual risk is a content-quality edge case, not a read-only/firewall/answer-leak correctness invariant violation. |

### New Findings

| Severity | Description | Citation |
|---|---|---|
| L | New hardening gap from `ce24ff6`: `_retrieve()` accepts `payload.get("mode")` without schema validation. Missing, `None`, or empty-string `mode` silently falls back to the requested tier mode, which can recreate metadata mislabeling if a degraded/malformed server response omits the mode; a truthy non-string mode can be persisted into the artifact JSON unchanged. I found no downstream crash path in the current code, but this is still a metadata integrity caveat. | `samagra/factory/paper.py:193-206`; `samagra/factory/paper.py:236-243`; current downstream proxy/client mode handling is pass-through at `samagra/clients/qx_client.py:29-37` and `samagra/api/app.py:157-165`. |

### Verification

- `git diff --stat b714b28..5ca4f98` -> 4 files changed, `+120/-15`.
- `git diff --name-only b714b28..5ca4f98` -> `.env.example`, `docs/deploy-tunnel.md`, `samagra/factory/paper.py`, `tests/test_factory_paper.py`.
- `git diff --check b714b28..5ca4f98` -> clean.
- First focused pytest attempt without `--basetemp` failed in setup because pytest tried to scan `C:\Users\abc\AppData\Local\Temp\pytest-of-abc`, which is permission-blocked in this sandbox.
- Focused rerun with workspace temp: `.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider --basetemp .\tmp\pytest-addendum2-focused tests/test_factory_paper.py tests/test_qx_client.py` -> `27 passed in 0.44s`.
- Full suite with workspace temp: `.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider --basetemp .\tmp\pytest-addendum2-full` -> `692 passed, 2 skipped, 1 warning in 35.99s`. This independently verifies a clean gate, but the observed count differs from the reported `694 pytest, 0 failures, 2 skips`.
- Legacy rollback live spot-check against `http://127.0.0.1:8783/api/qsearch?q=&mode=exact&chapter=<name>&page=1`: the six documented carve-out chapter names returned nonzero totals; `Motion in a Plane` and `Electric Charges and Fields` returned zero.

GO-WITH-CAVEATS
