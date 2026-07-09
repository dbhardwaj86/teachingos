# SAMAGRA (repo & Python package = `samagra`) — project notes

> **Naming:** the working directory is still `TeachingOS/` (legacy), but the **repo, the GitHub remote and the
> Python package are `samagra`** since the Phase-0 rename (2026-06-19). Where the auto-generated memory block
> below still says "TeachingOS", read it as the legacy directory / historical name only.
>
> **▶▶▶▶▶▶ ✅ CONTENT-FACTORY PIVOT — RATIFIED 2026-06-23 by Deepak (Founder & Chairman, carte blanche). NEW TOP
> DIRECTION.** SAMAGRA converts from a **static read-only operator console** into an **active, style-conditioned,
> multi-output content factory** for JEE/NEET **physics**: ONE seed (a lecture/chapter, a question, a captured idea)
> fans out to a wide spread of catalogued/indexed/categorized content types, in Deepak's style, behind the
> never-automated publish gate. **The reframe = activation, not teardown:** the 2026-06-19 spec already designed +
> parked this machinery — A6 (a learner-facing product is a SEPARATE entity consuming the published corpus), the
> dormant DRAFTER + ONE adversarial REVIEWER (anchored only to external ground-truth; catch-rate→0 = red flag), and
> the demand compass. The pivot ACTIVATES those + generalizes the bridge's single write into a many-output dispatch.
> **Decisions (binding):** **DEC-7** bridge → guarded **dispatch** boundary (1 approved seed → N child assignments,
> each board-approved + single-write + terminal; an EXTENSION that strengthens the firewall; needs a Codex pre-merge
> review of the new boundary); **DEC-8** **StyleSeed** = durable owner-curated voice profile from the 59 chapters,
> advisory style-fit scoring (never auto-advances the gate), owner-ratified learning loop over `review_overlay`;
> **DEC-9** **PRATHAM** student twin = the A6 separate entity, DEFERRED (DEC-1 "no audience" scoped to the console
> only). **4 forks ratified:** (1) **dispatch spine first** (throughput; StyleSeed layers after the deterministic
> lanes), (2) **PRATHAM deferred to Phase G**, (3) **publish gate = per-seed batch** (`approve_seed` — never silent
> auto-approve; mandatory adversarial review on LLM lanes), (4) **scope = teaching leverage** (no GTM; multi-seed
> from day one). **PRESERVED & still binding:** the never-automated publish gate; the read-only firewall over the 7
> source subsystems (munshi/mcd/QX/textbook/booklets/INSP/sims); the 5 crash-safety guards; DEC-1 bounded console
> scope. **Plan A–G** (spine → deterministic lanes → StyleSeed → coverage graph → async lanes → deferred PRATHAM).
> **Phase 1 = `samagra/factory/` dispatch spine + 2 deterministic local-write lanes (`revision`/`lecture`) from a
> textbook-chapter seed — NO new prod write path** (strictly safer than the existing bridge); reuses existing
> `assignments` columns (`pipeline`=lane, `seed_ref`, `artifact_ref`) so **no migration**. Spec
> `docs/superpowers/specs/2026-06-23-samagra-content-factory-design.md`; Phase-1 plan
> `docs/superpowers/plans/2026-06-23-samagra-content-factory-phase1-dispatch.md`; Chairman vision
> `CONTENT-FACTORY-VISION.html`. Synthesis from a 16-agent Workflow (run `wf_5fb88c46-838`).
>
> **✅ PHASE 1 (dispatch spine) BUILT TDD + Codex-reviewed + MERGED to `main` + PUSHED to `origin/main` 2026-06-23**
> (ff `67a509c`; HEAD `0758cd6` — durable): `samagra/factory/` (`lines` · `dispatch` · `run` · `outbox`) + CLI
> **`samagra factory plan|approve|approve-seed|build`**. ONE seed fans to 2 deterministic local-write lanes
> (`revision`=thin + `lecture`=thick) via the existing lecture renderer (`lectures.export.export_one`); the guarded
> **`build()`** boundary inherits the bridge's 5 crash-safety guards; **per-seed batch gate** (`approve-seed`, fork 3);
> **4-entry-point workflow firewall** (factory + bridge approve/build refuse cross-workflow pipelines); **NO new prod
> write path** (gdocs-upload opt-out; local artifacts + `governance.db` ledger only); **no migration** (reuses
> `assignments.pipeline`/`seed_ref`/`artifact_ref`). Golden thread **PROVEN LIVE** (`textbook:circular-motion` → 2
> distinct CAPTURED artifacts via the real renderer; durable `governance.db` untouched). **DEC-7 Codex pre-merge
> review:** review 24 **NO-GO** (factory build could trigger the lecture exporter's EXTERNAL Google Docs upload) →
> remediated TDD (H1 gdocs opt-out · M1 factory outbox + workflow firewall · L1 assignment-scoped event query · L2
> seed_ref normalize · I1 guard-2 isolation) → re-review 25 **GO-WITH-CAVEATS** (1 new Low: `approve_seed` firewall)
> → caveat closed → effectively **GO**. Gate **303 pytest**. Reports `docs/codex-reviews/24,25`.
>
> **✅ PHASE C DESIGN — RATIFIED 2026-06-23/24 (Chairman).** Phase C = "more deterministic lanes" (**NOT** StyleSeed —
> that is **Phase D**). Three forks ruled: (F-C1) include all 3 lanes now (`deck` + `paper`/`drill` + `seed`/mcd);
> (F-C2) **fold the bridge** — the factory `seed` lane becomes the canonical munshi→mcd write, `samagra bridge`
> deprecated/delegates, so exactly ONE prod-write path; (F-C3) **three sub-slices, lowest-risk first** (**C1** `deck`
> → **C2** `paper`/`drill` → **C3** `seed`-fold, C3 getting a dedicated DEC-7 Codex pre-merge review). Architecture:
> lanes gain a `kind` (`local|qx|mcd`); the one guarded `build()` boundary branches while the 5 guards stay identical.
> Spec `docs/superpowers/specs/2026-06-23-samagra-content-factory-phase-c-design.md`.
>
> **✅ PHASE C1 (`deck` lane) BUILT subagent-driven TDD + adversarial-multi-lens-reviewed + MERGED to `main` + PUSHED
> to `origin/main` 2026-06-24** (ff `6084952`): new PURE engine `samagra/factory/deck.py` — `build_deck(slug)` projects
> a chapter's **equation + callout** blocks into `{front,back,ref}` flashcards, writing `<slug>-deck.json` + a
> printable MathJax `<slug>-deck.html` under `EXPORT_DIR`. **Zero external-write code** (no-prod-write enforced
> STRUCTURALLY — stronger than the lecture lane's opt-out). The **`Line.kind` seam** (`local|qx|mcd`, default local)
> lands here (consumed by C2/C3); `dispatch.run_line` routes deck→engine; `classify("textbook:<slug>")` now fans to
> **[revision, lecture, deck]** — **one chapter → 3 captured local artifacts**. Golden thread **PROVEN LIVE**
> (`circular-motion` → **50 flashcards** [27 eqn + 23 callout] + 3 distinct artifacts; durable `governance.db`
> untouched). **Adversarial final review** (9-agent Workflow, 4 lenses × independent verify) caught **1 HIGH** the
> per-task reviews missed — equation LaTeX injected UNESCAPED into the printable corrupts ~18 real-corpus formulas
> carrying `<`/`>`/`&` (e.g. gauss-law `E(r<R)=0`: the HTML tokenizer ate the math, MathJax never typeset it) →
> **FIXED** (escape the equation back at the HTML boundary keyed on card kind; the deck JSON keeps RAW tex) +
> regression test, proven on gauss-law (32 cards, zero bogus tags); other 4 findings verified false; the safety lens
> confirmed all 6 load-bearing invariants HELD. **NO new prod write path · no migration · publish gate untouched.**
> Gate **316 pytest** (lone red = pre-existing env `test_gdocs`, Google API libs). Plan
> `docs/superpowers/plans/2026-06-24-samagra-content-factory-phase-c1-deck.md`.
>
> **✅ PHASE C2 (`paper`/`drill` lanes) BUILT TDD + adversarial-multi-lens-reviewed + MERGED to `main` + PUSHED to
> `origin/main` 2026-06-24** (ff `78cf72a`): new PURE engine `samagra/factory/paper.py` — `build_paper(slug, *, variant)`
> reads the **read-only** QX `/api/qsearch` (question-only render — stem/options/passage/matrix with KaTeX `data-tex`
> spans + figures; QX's search route NEVER renders `rj["answer"]`), assembles an **answer-free** printable KaTeX
> `paper` (full page) / `drill` (first `_DRILL_SIZE=8`), absolutizes asset URLs, writes `<slug>-<variant>.{json,html}`
> under `EXPORT_DIR`. **NO new prod write path** (QX is read-only; only local file writes — no gdocs/network). The
> **`Line.kind="qx"` seam** (from C1) is consumed: `run_line` routes `kind=="qx"` → engine; **`classify("textbook:<slug>")`
> now fans to `[revision, lecture, deck, paper, drill]` — one chapter → 5 captured local artifacts**. The real
> **`_assert_no_answer_leak`** guard is ACTIVATED for `kind=="qx"`: a structural-marker scan over BOTH written artifacts
> (html + json) that refuses any answer/solution marker at the guarded `build()` boundary; **false-positive-free**
> (anchors on QX-specific class tokens — `class="answer"`/`answer-label`/`pq-ans`/`pkey` — never the bare word "answer",
> so a stem mentioning "answer" passes). **QX-down ⇒ `ValueError` before any write** (clean refusal, no partial artifact).
> **`build()` is unchanged** — the 5 crash-safety guards are identical for every kind. Golden thread **PROVEN LIVE
> against the live QX engine** (`circular-motion` → **paper 25 q + drill 8 q**, both answer-free, both captured; durable
> `governance.db` untouched). **Adversarial final review** (10-agent Workflow, 4 lenses × independent verify; run
> `wf_3ffe75d5-cc1`): 6 raw → **4 confirmed (0 HIGH, 1 MED, 3 LOW), 2 refuted**. The MED (the load-bearing catch, like
> C1's): the marker set missed QX's **THIRD** answer renderer — its teacher `paper_render` markup (`pq-ans` / the `pkey`
> answer-key appendix) — a **latent defense-in-depth gap** (no live leak: the search render is structurally answer-free)
> → **FIXED** (add `pq-ans`+`pkey` markers + scan the JSON sidecar) + regression. 3 LOWs fixed (json-scan, parametrize
> the `drill` e2e path, assert the drill cap on-disk); 2 findings correctly refuted. **6 load-bearing invariants HELD**
> (no new prod write · read-only firewall · publish gate · 5 guards · no migration · no secrets). Gate **341 pytest**
> (340 green; lone red = pre-existing env `test_gdocs`). Plan
> `docs/superpowers/plans/2026-06-24-samagra-content-factory-phase-c2-paper-drill.md`. **Phase C3 SHIPPED (below).**
>
> **✅ PHASE C3 (`seed`/mcd lane — the BRIDGE FOLD) BUILT TDD + adversarial-multi-lens-reviewed + DEC-7-Codex-pre-merge-
> reviewed + MERGED to `main` + PUSHED to `origin/main` 2026-06-24**: the munshi→mcd write FOLDS into the factory as the
> canonical `seed` lane (`Line.kind="mcd"`, prefix `munshi:`). New PURE `samagra/factory/seed_payload.py` (relocated
> canonical home; `bridge/seed_payload.py` = re-export shim) + `dispatch.run_seed(payload)` = the ONE prod write
> (`validate_seed_payload` → `McdClient.create_seed` → assert id → `artifact_ref="mcd:<seed_id>"`); `run_line` refuses
> `kind=="mcd"`. `factory.run` grows `scan()` (the folded `bridge.scan` over munshi content items), `plan("munshi:<id>")`,
> and a `build()` **mcd branch**: load proposed payload + `validate_seed_payload` **BEFORE** recording the
> `product_building` intent (**anti-wedge** — a structurally-bad payload refuses without wedging the assignment in-flight),
> then `run_seed`, `product_created` (`subsystem_ref`=seed id), flip → terminal `captured`. **`build()`'s 5 crash-safety
> guards are written ONCE + shared across every lane kind** (only the produce/validate step branches). `classify("munshi:<id>")
> → [seed]`; **textbook still fans to the 5 content lanes** (seed excluded by the `munshi:` prefix). **F-C2 bridge fold:**
> `samagra bridge {scan,approve,submit}` are now thin **deprecating delegators** (stderr notice + forward; `submit →
> factory.build`); the bridge's own `create_seed` write is **RETIRED** ⇒ the factory seed lane is the **only
> assignment-driven mcd writer** (the pre-existing **DEC-3 owner-capture web endpoint** `POST /api/mcd/seeds` remains the
> separate sanctioned UI path — untouched by C3; F-C2's "one path" = one agent/CLI path). New CLI `samagra factory scan`.
> **NO new prod write *mechanism*** (reuses the existing `create_seed` capture contract) · **no migration** (reuses
> `assignments` cols + `product_*` verbs) · **publish gate untouched** · **read-only firewall intact**. Golden thread
> **PROVEN LIVE** (real `munshi:52` → real seed `seed_01KVWDS8NTEV1C0NVN7T6EN79W`, captured; durable `governance.db`
> untouched). ⚠ **OWNER CLEANUP:** archive that prod test seed `seed_01KVWDS8NTEV1C0NVN7T6EN79W`. **Adversarial final
> review** (10-agent Workflow, 4 lenses × independent verify; run `wf_eeac9f1a-4e6`): 6 raw → **1 confirmed (MED), 5
> refuted** — the MED: `cmd_bridge` scan CLI print used the stale `p['item']['uid']` key the folded `factory.scan` no
> longer emits (KeyError on a real proposal, masked by tests returning `[]`) → **FIXED** (`seed_ref`) + regression. **DEC-7
> dedicated Codex pre-merge review (`docs/codex-reviews/26`) = GO-WITH-CAVEATS** (0 HIGH/MED; 1 LOW F1: `_load_proposed_payload`
> could surface a downstream `AttributeError` on a non-dict note payload) → **FIXED** (return only a dict payload, else
> `None`) + 6-case regression → **effectively GO**. Gate **360 pytest** (359 green; lone red = pre-existing env
> `test_gdocs`). Plan `docs/superpowers/plans/2026-06-24-samagra-content-factory-phase-c3-seed-fold.md`. **PHASE C COMPLETE**
> (C1 deck · C2 paper/drill · C3 seed-fold) — exactly ONE prod-write path, behind the never-automated publish gate.
>
> **✅ PHASE D RESUMED 2026-06-25 on the user's "go for phase D" (the gate the prior pause required); 4 forks ruled —
> F-D1=(B) moat + a first live LLM lane · F-D2=Samadhan misconception brief (the lane) · F-D3=(C) git-committed JSON moat
> (owner accepts public-repo exposure) · F-D4=samadhan opt-in (excluded from the default textbook fan-out).** Phase D =
> the durable style MOAT + a first generative lane: a versioned 5-facet voice profile (voice · sequencing · analogy ·
> rigor-from-`flags[]` · selection priors) from the 59 `content.json` chapters, a conditioning interface for the LLM
> lanes, a **deterministic advisory style-fit scorer** (never auto-advances the gate), and an owner-ratified learning
> loop over `review_overlay`. Spec `docs/superpowers/specs/2026-06-24-samagra-content-factory-phase-d-design.md`
> (extends the umbrella spec §3.4/§4).
>
> **✅ PHASE D1 (the StyleSeed MOAT — the deterministic, no-API-key half) BUILT subagent-driven TDD (10 tasks, fresh
> implementer + spec+quality review each) + final-opus-review (READY-TO-MERGE, all 4 invariants HELD) + MERGED to `main`
> + PUSHED to `origin/main` 2026-06-25** (ff `df8c1ef..214597b`; durable): new PURE package `samagra/factory/style/` —
> `text.py` (single-source tokenizer + 4 frozen marker vocabularies) · `extract.py` (5 deterministic facets over the 59
> chapters: voice/sequencing/analogy/**rigor-from-`section.flags[]`**/selection + `load_corpus`/`build_profile`) ·
> `profile.py` (`StyleSeed` frozen dataclass + sha256 content/corpus hash + versioned git-committed JSON +
> `extract_candidate` change-detect; `created_at` excluded from the hash ⇒ idempotent re-runs) · `condition.py`
> (`to_system_prompt` = the conditioning interface the LLM lanes prompt-cache; embeds `<facets>` JSON) · `score.py`
> (`style_fit` deterministic **ADVISORY** scorer — structurally never gates, DEC-8). `config.STYLESEED_DIR =
> REPO_ROOT/styleseed` (fork C: git-committed = the review surface). CLI **`samagra factory style-extract|style-show`**.
> **v0 committed** (`styleseed/styleseed-v0.json`): real 59-chapter profile (rigor.kind_mix `[clarified 0.77, corrected
> 0.13, note 0.10]` proves the real `section.flags[]` are read). **Invariants HELD:** no API key/no LLM (pure
> deterministic) · no new prod write path (only the local `styleseed/*.json`; the 7 subsystems stay read-only) · the
> advisory scorer never auto-advances the gate · **NO governance/`assignments` migration** (the `style_events` table is
> D2/D3). Gate **384 pytest green** (25 new style tests; lone red = pre-existing env `test_gdocs`). Plan
> `docs/superpowers/plans/2026-06-25-samagra-content-factory-phase-d1-styleseed.md`. ⚠ **Process learning:** a review
> subagent's git inspection left HEAD detached mid-run → Tasks 8/9/tidy/v0 committed off-branch; caught by `git merge
> --ff-only`'s "leaving N commits behind" warning and recovered to the true tip — **after subagent-driven git work,
> verify the branch ref is at the true HEAD before merging.**
>
> **✅ PHASE D3 (the StyleSeed LEARNING-LOOP SCAFFOLD — owner-ratified-only, DEC-8) BUILT subagent-driven TDD (5 tasks,
> fresh implementer each) + 2-lens adversarial final review (1 MED fixed) + MERGED to `main` + PUSHED to `origin/main`
> 2026-06-25** (ff `b756cc2..a9ae176`; durable). Driven by the user's **"go for D3"** — built BEFORE D2 (independent: D3
> is the substrate D2 will later feed). **Additive migration** `_MIGRATIONS[2]` (`samagra/governance/store.py`) → a
> `style_events` table; `SCHEMA_VERSION` 1→2; verified to upgrade a fresh DB AND an existing `user_version=1` DB, idempotent,
> never touches `assignments`/`events`/`review_overlay` (**no `assignments` migration**). New PURE `samagra/factory/style/learn.py`:
> **`mine_deltas`** scans owner `changes`-reviews on samadhan artifacts (`verdict='changes' AND artifact_uid LIKE 'samadhan:%'`)
> → proposes `style_events`, **deterministic + idempotent** (dedup key `subsystem_ref='review:<id>'`); a frozen `_RULES`
> keyword→facet-nudge table (transparent **PLACEHOLDER**, Phase-F-replaceable) → a match emits a `facet_delta`, no match a
> `review_signal` (no candidate lost; no-profile/missing-key falls back safely). **`ratify`** applies the candidate's **signed
> STEP** to the THEN-current profile facet (clamped) → writes `styleseed-v<N+1>.json` → marks the event `ratified` → stamps a
> `style_seed_promoted` governance event; all guards (unknown id / non-`proposed` / non-`facet_delta` / no current profile)
> raise **before any write**; mutation-safe deep-merge. **`reject`** dismisses a candidate. New CLI **`samagra factory
> style-mine|style-events|style-ratify <id>|style-reject <id>`**. **§11 schema pinned** (the spec left it to the plan):
> `facet_delta = {facet, step:{key:signed_step}, rationale, source_review_ids}` · `review_signal = {artifact_uid, rationale,
> source_review_id}`. **2-lens adversarial review** (two independent subagents — the user chose subagent-driven, not a Workflow):
> **Lens A (correctness/determinism) = GO** (0 HIGH/MED); **Lens B (safety/invariants) = GO-WITH-CAVEATS**, all 5 invariants
> PASS + **1 real MED** — ratify stored a mine-time ABSOLUTE and OVERWROTE, so two `changes`-reviews both mined against v0
> (hedge 0.05) collapsed to one value and the recorded `from_version` was ignored → **FIXED** (`a9ae176`: store the **signed
> step**, re-apply to the then-current profile ⇒ corrections COMPOUND; regression `test_two_corrections_on_same_key_compound`
> proves 0.05→0.03→0.01); 2 LOWs **accepted** under the single-operator manual-CLI threat model (non-atomic FS+DB write
> ordering — commented + owner-recoverable via git; timestamp cosmetic, excluded from the hash). **Invariants HELD:**
> owner-ratified-only — **NOTHING auto-applies** (`mine` only INSERTs `proposed`; only owner-CLI `ratify`/`extract` write a
> profile) · **NO new prod write path** (local `styleseed/*.json` + additive `style_events` rows only; the 7 subsystems
> read-only; **no network / no secrets / no API key**) · governance **additive-only, never reset** · the deterministic moat +
> factory `build()` 5 guards + **publish gate untouched** · the **known re-extraction limitation** (a later `style-extract`
> re-extracts a pure-corpus candidate that would DROP a ratified delta) is **documented in `learn.py` + git-protected by fork
> F-D3**. **No dedicated Codex pre-merge review needed** (D3 is deterministic/additive — that gate is D2's network/secrets
> boundary). Gate **409 pytest** (410 collected; lone red = pre-existing env `test_gdocs`; +25 over D1's 385). **Contract D2
> must honor:** record samadhan reviews via `store.add_review(..., artifact_uid=f"samadhan:{slug}", ...)` so `mine_deltas`
> finds them. Plan `docs/superpowers/plans/2026-06-25-samagra-content-factory-phase-d3-learning-loop.md`. **D2 is now the only
> remaining Phase-D slice.**
>
> **✅ PHASE D2 (the SAMADHAN LIVE LLM LANE — SAMAGRA's FIRST generative content lane, fork F-D2) BUILT subagent-driven
> TDD (5 tasks) + dedicated Codex DEC-7 generation-boundary review (NO-GO → remediated → re-review GO; caveats closed) +
> 2 Claude adversarial lenses + MERGED to `main` + PUSHED to `origin/main` 2026-06-25** (ff `f7d2be6..30e7bcc`; durable).
> Driven by the user's **"ok start D2"**. **⇒ PHASE D COMPLETE** (D1 moat · D2 lane · D3 learning loop). New
> **`samagra/clients/llm_client.py`** = the ONE Anthropic call site (`claude-opus-4-8`, adaptive thinking, **structured
> output** `output_config` json_schema [installed anthropic 0.96.0 supports it], the StyleSeed system block prompt-cached
> `cache_control:ephemeral`; **key ONLY from the gitignored `.env`, never logged/repr'd, missing-key → `RuntimeError`**;
> **injectable fake SDK ⇒ no standing test hits the network or needs a key**; `generate_samadhan`/`review_samadhan` own the
> SDK call + parsing; **`review_samadhan` NEVER receives the StyleSeed = the DEC-8 reviewer firewall, STRUCTURAL**;
> `_extract_json` hardened — refusal/empty/bad-JSON → clean `RuntimeError`, no content/key leak). New
> **`samagra/factory/samadhan.py`** `build_samadhan(slug, *, client=None)`: load chapter ground-truth → require committed
> StyleSeed → `condition.to_system_prompt` → generate → **adversarial reviewer anchored ONLY to the chapter, refute-framed**
> → advisory `style_fit` (never gates) → write local `<slug>-samadhan.{json,html}`; **`preflight()`** anti-wedge;
> **fail-closed verdict mapping** (an item with no explicit `ok` verdict → `error`); **HTML-escapes untrusted LLM text** at
> the boundary (the C1 lesson), JSON keeps RAW. Wiring: **`Line.auto_fan`** (samadhan `kind="llm"`, `auto_fan=False` →
> **opt-in F-D4**: `classify("textbook:")` still = `[revision,lecture,deck,paper,drill]`; samadhan reached only via
> `factory plan textbook:<slug> --lane samadhan`); `run_line` llm branch; **`build()` llm preflight (chapter+StyleSeed+key)
> BEFORE the `product_building` intent** (anti-wedge) + **capture/changes gate** (reviewer `errors>0` OR empty `items==0` →
> `changes` [owner review], else → `captured`; never a silent capture) + **rollback-on-failure** (records
> `product_build_failed` for LOCAL-write lanes; `_build_in_flight` now count-based ⇒ a transient LLM failure is
> **RETRYABLE**, not a permanent wedge — **the mcd lane keeps its fail-safe wedge**, never double-writing a seed); `plan(lane=)`;
> CLI `build_parser()` extract + **`factory plan --lane`**; opt-in live smoke gated on **`SAMAGRA_LIVE_LLM_SMOKE` (a flag,
> not key-only)** so the standing gate stays offline even once `.env` carries a key. `requirements.txt` += `anthropic>=0.96`;
> `.env.example` += blank `ANTHROPIC_API_KEY=` + `SAMAGRA_LLM_MODEL`. **DEC-7 Codex review:** round-1 **NO-GO** (HIGH: the LLM
> in-flight window wedged on any post-intent failure; MED: partial reviewer verdicts defaulted to `ok`; MED: `_extract_json`
> crashed on stop/refusal/empty/truncated; LOW: stray `"name"` not in the 0.96 schema) → **remediated TDD** (rollback /
> fail-closed / robust parse / drop name / empty→changes) → **re-review GO-WITH-CAVEATS** (all 3 RESOLVED, 0 new) → 2
> caveats closed (regressions pinning the mcd fail-safe wedge + the mis-indexed-verdict fail-close). **Invariants HELD:**
> secrets env-only (never logged/committed; `.env` gitignored) · **no new prod write path** (the Anthropic call is outbound
> generation, never a write to the 7 read-only subsystems; only local files + governance rows) · **publish gate untouched**
> · the **five `build()` crash-safety guards intact** · **DEC-8 reviewer firewall structural** · advisory scorer never gates
> · **no migration**. Gate **439 pytest** (441 collected; lone red = pre-existing env `test_gdocs`; 1 skipped = opt-in live
> smoke). ⚠ **git-race process learning:** a **background** plan-commit overlapping the Task-1 implementer subagent (which
> also committed) raced the index during the ~90s pre-commit hook → the plan commit was **orphaned** (recovered by
> re-commit). **NEVER run a background git commit concurrently with a subagent that also commits** — serialize all git.
> ✅ **D2 fast-follow SHIPPED 2026-06-26** (ff `3540f61..8c5b1dc`, durable): `samagra factory reopen <aid>` closes the
> `changes`→regenerate loop the DEC-7 review deferred — `run.reopen()` flips a terminal `changes` brief back to
> `in-review` (re-approve → rebuild; board gate re-crossed, publish gate intact) with a `reopened` audit event;
> **guard 2 made reopen-aware (count-based, not delete-based)** so the prior `product_created` is forgiven for EXACTLY
> ONE rebuild and the ledger stays append-only — **no event deleted** (mirrors the `product_build_failed` reconciliation);
> refuses unknown / non-factory pipeline / **the mcd seed lane on KIND grounds (structural single-write guarantee)** /
> any status but `changes`. TDD +9 tests; gate **448 pytest** (1 skip = opt-in live smoke; lone red = pre-existing env
> `test_gdocs`). ⚠ **Owner action:** run the live smoke once — `SAMAGRA_LIVE_LLM_SMOKE=1 ANTHROPIC_API_KEY=… python -m
> pytest tests/test_samadhan_live_smoke.py -v` — to validate the real generation boundary. Plan
> `docs/superpowers/plans/2026-06-25-samagra-content-factory-phase-d2-samadhan.md` (incl. the review/remediation log).
>
> **▶ PHASE D COMPLETE** (D1 deterministic moat · D2 Samadhan LLM lane · D3 learning loop).
>
> **✅ PHASE E (the COVERAGE GRAPH / CONCEPT ATLAS — the read-only STEERING layer) BUILT subagent-driven TDD (17 tasks,
> fresh implementer + spec+quality review each) + adversarial multi-lens final review (11-agent Workflow, 4 lenses ×
> independent verify; run `wf_2f09d96c-ff5`) + remediation + MERGED to `main` + PUSHED to `origin/main` 2026-06-26**
> (ff `ab67968..288d458`; durable). Driven by the user's **"lets go for phase E"**. New PURE package
> `samagra/factory/coverage/`: `concepts.py` (the QX concept spine — `chapter_id LIKE 'physics.%'` over a **read-only**
> `builder.sqlite`, demand `concept.size` + distinct-paper count via `question_concept→search_index.slug`) ·
> `aliases.py` (the git-committed `concept_aliases.json` normalization overlay — label→id, **now also slug-validated**) ·
> `edges.py` (in-memory FTS5 chapter↔concept edges: **AND-prefix primary + OR-prefix fallback** when a multi-word label
> co-locates nowhere; `apply_overlay` add/remove deltas; `factory_produced_counts`) · `matrix.py` (the **3-state**
> produced/base/gap cell rule, factory-produced-only) · `gaps.py` (the **deficit-weighted** ranker `demand/(corpus_n+1)`,
> samadhan-first) · `store.py` (`concept_graph.db` — REBUILDABLE, gitignored, sibling of `samagra.db`; idempotent
> DELETE-then-insert; `connect_ro`) · `build.py` (the idempotent rebuild orchestrator; stamps provenance hashes). CLI
> **`samagra factory coverage-build|coverage|gaps`**; read-only **`GET /api/coverage`** + **`/api/coverage/concept/{id}`**
> (NOT in `_PROTECTED_GETS`); new React **Atlas** app (heatmap + deficit-ranked gap queue with copyable `plan_command`).
> **Locked decisions:** factory-produced-only coverage · 3-state cells · deficit-weighted ranking · FTS base + committed
> overlay · QX read read-only · gap emission ONLY via the existing `samagra factory plan` CLI (the owner's deliberate act).
> Golden thread **PROVEN LIVE** (real QX + 59 chapters + governance → **86 concepts, 727 chapter edges, 516 cells, 498
> gap seeds**; durable `governance.db` byte-unchanged). **Adversarial final review: 0 HIGH; the invariants + contracts
> lenses found NOTHING** (no firewall/write-path/publish-gate breach, no cross-stack contract drift, the break-glass
> incident left no bypass artifact); **7 confirmed (1 MED, 4 LOW, 2 NIT), ALL remediated TDD** (commit `288d458`). The
> **MED**: the FTS **AND-prefix** silently dropped **11 high-demand concepts** (incl. dimensional analysis 2387) from the
> gap queue → **FIXED** (OR-prefix fallback marked `fts-or` + `build` returns/CLI prints the residual **by name**: real
> build **11→3** no-pointer concepts [8 rescued], edges 553→727, gaps 450→498; the residual polarisation/radioactivity/
> transistors now surfaced for overlay curation). LOWs: overlay slug validation · `list_gaps(top=0)` falsy-LIMIT ·
> golden produced↔produced_n invariant + spec §12 honesty (real governance.db has 0 captured `textbook:` seeds ⇒ 0
> produced expected; path covered synthetically) · governance-byte-unchanged regression. NITs: `graph_meta` provenance
> hashes (`qx_builder_sha`/`aliases_sha`/`builder_version`, **no `built_at`** ⇒ byte-idempotent) · `concepts.py`
> `path.resolve().as_uri()`. **Invariants HELD:** **NO new prod write path** (web GET read-only; `concept_graph.db`
> derived/rebuildable; the ONLY gap action reuses `factory plan`→`approve_seed`→`build`) · **publish gate untouched**
> (Phase E only *proposes* a ranked queue) · **governance read-only / NO migration** · the 7 source subsystems read-only
> (QX via read-only `builder.sqlite`) · **no secrets / no LLM** (Tier-1 deterministic). Gate **479 pytest** (1 skipped =
> opt-in live LLM smoke; lone red = pre-existing env `test_gdocs`). Spec
> `docs/superpowers/specs/2026-06-26-samagra-content-factory-phase-e-coverage-graph-design.md`; plan
> `docs/superpowers/plans/2026-06-26-samagra-content-factory-phase-e-coverage-graph.md`. ⚠ **OWNER follow-ups:** (1)
> curate `concept_aliases.json` for the 3 residual no-pointer concepts (polarisation spelling-split, radioactivity,
> transistors); (2) `concept_graph.db` is gitignored — run `samagra factory coverage-build` after pulling.
>
> **✅ PHASE G OPENED + G1 (the PUBLISH BOUNDARY — the foundation) BUILT subagent-driven TDD (11 tasks, fresh
> implementer + 2-stage spec+quality review each) + adversarial multi-lens final review (10-agent Workflow
> `wf_1aabf2a8-843`, 4 lenses × independent refute-verify) + MERGED to `main` + PUSHED to `origin/main`
> 2026-06-26** (branch `feature/content-factory-phase-g1`, 19 commits, spec `480665a` → `947d62b`; durable).
> Driven by the Chairman re-scope of DEC-9 ("lets go for phase G before phase F"), un-deferring PRATHAM (the
> A6 downstream student entity). **G1 = the publish boundary** — `published` becomes a real, durable,
> owner-gated state via a manual CLI **`samagra factory publish|unpublish|published`**. `publish <chapter>
> [--lanes ...]` COPIES a chapter's CAPTURED factory artifacts into an immutable, append-only **`published/`**
> snapshot: a derived `manifest.json` + frozen artifact copies + immutable per-publication records — the
> export contract a future PRATHAM (G2+) reads INSTEAD of the inward stores. Append-only `unpublish` retract
> + `published` list. **Proposed DEC-10 pins this invariant set.** New PURE-modules-plus-orchestrator package
> **`samagra/factory/publish/`**: `manifest.py` (PURE — schema/sha256/`derive_manifest` last-write-wins
> replay/`unchanged_lanes` idempotency) · `store.py` (atomic writes under `config.PUBLISHED_DIR`, immutable
> records, path-traversal segment guards) · `run.py` (`publish`/`unpublish`/`list_published` + captured-artifact
> recovery from `product_created` notes). New config `PUBLISHED_DIR` (durable + gitignored — like `governance.db`,
> never reset). **Invariants HELD (the safest firewall crossing):** NO public/outward network surface, NO identity
> (those are G2/G3); NO new write path to the 7 source subsystems; NO governance migration / NO new table / NO
> assignment-state-machine change (only new append-only event verbs `published`/`unpublished`); the inward
> `build()` boundary + its 5 crash-safety guards untouched; the never-automated publish gate is manual-CLI only;
> mcd/`seed` lane excluded (no local artifact). **Adversarial final review (10-agent Workflow `wf_1aabf2a8-843`,
> 4 lenses × independent verify): 6 raw → 2 MED confirmed+fixed, 4 refuted; the firewall, security, and spec
> lenses found NOTHING real** (no firewall/write-path breach, no leak, no contract drift). The 2 MEDs (both
> crash-window consistency): **MED#1** — publish wrote the record before the `published` event, so a crash +
> records-based no-op retry could SILENTLY lose the audit event → **FIXED** (events-before-record on BOTH publish
> and unpublish; the record is the crash-authoritative key). **MED#2** — unpublish read the stale `manifest.json`
> cache, so a crash made `list_published` lie and a retry wrote a duplicate retract → **FIXED** (unpublish +
> `list_published` derive from the immutable records). Per-task review fixes also landed: strict manifest action
> state-machine, `_norm_lanes` empty-filter guard, 2 path-traversal guards on the write firewall,
> crash-safe idempotency-from-records + manifest self-heal. **Golden thread PROVEN:** a real textbook chapter
> captured via plan→approve→build → `publish` writes the immutable manifest + frozen copy + a `published` event;
> `unpublish` drops it from the current view while records + bytes persist; the durable `governance.db`
> assignments table is **byte-unchanged** (only append-only events added). Gate **534 pytest** (1 skipped =
> opt-in live-LLM smoke; lone red = pre-existing env `test_gdocs`). Spec
> `docs/superpowers/specs/2026-06-26-samagra-content-factory-phase-g1-publish-boundary-design.md`; plan
> `docs/superpowers/plans/2026-06-26-samagra-content-factory-phase-g1-publish-boundary.md`. ⚠ **OWNER:**
> `published/` is gitignored — it's created on first `samagra factory publish`. G2 (outward read surface), G3
> (multi-tenant identity), and G4 (the student twin) remain deferred.
>
> **✅ PHASE G2 (the OUTWARD READ SURFACE + PRATHAM `/learn` reader — SAMAGRA's FIRST outward, read-only,
> public-by-design crossing) BUILT subagent-driven TDD (9 tasks, fresh implementer + 2-stage spec+quality review
> each) + adversarial multi-lens final review (14-agent Workflow `wf_d4ae0d21-6cf`, 4 lenses × independent
> refute-verify) + MERGED to `main` + PUSHED to `origin/main` 2026-06-27** (branch `feature/content-factory-phase-g2`,
> 15 commits, spec `bcaa2a9` → tip `d95267b`; durable). Driven by the user's **"lets go for phase G2."** G2 = the
> first consumer of the G1 published corpus. **Backend:** new PURE `samagra/factory/publish/read.py` over G1's
> `run.list_published()` — `published_manifest()` (graceful-empty delegate) + `resolve_artifact(chapter,lane,kind=html)`
> that resolves the file **FROM the manifest** (never a client path), re-validates a `<safe>/<safe>` `_SAFE_SEGMENT`
> pair + `relative_to(PUBLISHED_DIR)` containment, **re-verifies sha256** (mismatch raises), returns
> `{rel,abs_path,bytes,sha256,media_type}` (unknown chapter/lane/kind/missing → `None`). Two **PUBLIC** endpoints
> (deliberately **NOT** in `_PROTECTED_GETS` — the `/api/coverage` precedent): **`GET /api/published`** (the manifest,
> graceful-empty) + **`GET /api/published/{chapter}/{lane}`** (`?kind=html|json|docx`, sha-verified bytes, 404 unknown,
> 500 integrity-breach, **defense-in-depth headers** `nosniff`/`no-referrer` + CSP `sandbox allow-scripts` for html).
> **Frontend:** a one-line `main.tsx` split on `isLearnPath` mounts a **SEPARATE full-page `<Pratham/>` reader at
> `/learn`** (no operator OS-shell chrome) else the console; PURE `frontend/src/lib/published/` (`manifest.ts`:
> `chaptersList`·`laneSort`[Saar-led]·`laneLabel`[**Saar·Vaani·Smriti·Pariksha·Abhyaas·Samadhan**]·`artifactUrl`·
> `pickChapter`·`pickLane`·`fileExts`; `route.ts`: `isLearnPath`·`parseLearnPath`·`learnPath`); the reader = chapter
> list + Saar-led lane tabs + **sandboxed iframe** (`allow-scripts`, `no-referrer`) + empty/error/loading states +
> docx download + deep-link. **4 forks locked:** separate `/learn` route in the shared Vite build · render all
> published lanes Saar-led · **code-only deploy-ready** (actual public exposure = a separate owner step) ·
> manifest-resolved + sha-verified artifact endpoint (no static `published/` mount). **Invariants HELD —
> READ-ONLY/ADDITIVE:** NO new write path anywhere; serves **only** owner-published bytes resolved through the manifest
> (never `_publications/`, `governance.db`, `EXPORT_DIR`, or the 7 subsystems); **public-by-design** (the gate was
> already crossed at G1 publish); **separate-entity** (the console at `/` is byte-unchanged; the reader imports NO
> shell module); the inward `build()` + 5 guards + the never-automated publish gate **untouched**; **NO
> migration/table/state-machine change**. **Proposed DEC-11 pins the outward-read-surface invariant set.**
> **Adversarial final review (14-agent Workflow `wf_d4ae0d21-6cf`, 4 lenses × independent verify): 10 raw → 8
> confirmed (0 HIGH, 0 MED, 2 LOW, 6 NIT), 2 refuted; the FIREWALL lens found NOTHING** (read-only proven end-to-end),
> the separate-entity lens only NITs, and path-traversal was independently **attacked with planted hostile `rel`
> values — every one blocked.** The 2 LOWs (same root): the public artifact response lacked `nosniff`/CSP/`no-referrer`
> so the in-reader iframe sandbox didn't cover **direct navigation** to a shared deep-link / the docx href → **FIXED**
> (the defense-in-depth headers above; CSP `sandbox allow-scripts` forces an opaque origin on direct nav **without** a
> restrictive `script-src` that would break the artifacts' CDN-loaded KaTeX/MathJax) + regression. NITs closed: exact
> docx label, a distinct `/api/published` fetch-error state, and spec/plan doc reconciliation. ⚠ **Process catches:** a
> subagent caught a real error in the PLAN's golden-test assertion (the `revision` lane renders the **`thin`** variant,
> not `"revision"`) and a latent **`.gitignore` collision** (G1's unanchored `published/` was silently hiding the new
> `frontend/src/lib/published/` source dir — fixed by anchoring to `/published/` + a negation). Gate **562 pytest**
> (1 skipped = opt-in live-LLM smoke; **no failures**) + **583 vitest** (68 files) + build green. Spec
> `docs/superpowers/specs/2026-06-27-samagra-content-factory-phase-g2-outward-read-surface-design.md`; plan
> `docs/superpowers/plans/2026-06-27-samagra-content-factory-phase-g2-outward-read-surface.md`. ⚠ **OWNER:** the
> `/learn` surface is **code-only / deploy-ready** — actually exposing it publicly (a separate hostname or a
> Cloudflare-Access bypass for `/learn` + `/api/published`) is a separate owner-driven deploy step (a G2 follow-up).
>
> **✅ PHASE G3 (MULTI-TENANT PRATHAM IDENTITY + THE OUTWARD PUBLISH WRITE PATH — SAMAGRA's FIRST inbound HTTP
> write boundaries) BUILT TDD + dedicated DEC-7 Codex pre-merge review (review **28 GO-WITH-CAVEATS → both caveats
> remediated TDD → effectively GO**) + 4-lens adversarial final review + MERGED to `main` + PUSHED 2026-07-05**
> (branch `feature/content-factory-phase-g3`; spec `74682b2` → remediation `4b0ee9a`; durable). Two PHYSICALLY
> ISOLATED write boundaries: **(1) owner publish over HTTP** — `POST /api/factory/publish|unpublish` added to
> `origin_auth._PROTECTED_POSTS` (now 7 protected POSTs + 4 protected GETs; `docs/deploy-tunnel.md` re-synced), a
> THIN delegate to the already-reviewed G1 `publish.run` — **no new write mechanism**, the never-automated gate
> only gained a second owner trigger beside the CLI; **(2) student identity** — new `samagra/pratham/`
> (`identity` pure crypto/rate-limit · `store` I/O · `service` orchestration) over a SEPARATE durable gitignored
> **`pratham.db`** (students + sessions, secrets sha256-at-rest, schema v1): owner-minted enrollment codes
> (`token_urlsafe(9)`, printed exactly ONCE) → public `POST /api/learn/login|logout` + `GET /api/learn/me`
> (opaque 256-bit sessions; HttpOnly+SameSite=Lax+Secure cookie **scoped `path=/api/learn`**; identical-401
> no-oracle incl. rate-limited; revoke = instant invalidation). CLI **`samagra pratham enroll|students|revoke`**
> (code hash never shown). Frontend: **additive** student sign-in/out in the `/learn` reader (anonymous reading
> byte-identical; hydration-race hardened) + the operator **Publish** app (19th console app) over PURE
> `lib/publishctl/rows.ts`. Golden threads PROVEN: publish-over-HTTP ≡ G1 CLI result · enroll→login→me→revoke ·
> `governance.db` BYTE-ISOLATED from every identity write. **Reviews:** Codex 28 = 0 HIGH/MED on both boundaries;
> its LOW (the Publish GUI typed `/api/assignments` as a bare array — the real `{assignments,events}` shape threw
> mid-render; the GUI's own mocks encoded the same wrong shape) + the known cookie `path="/"` were BOTH fixed TDD
> with regressions (`4b0ee9a`). Adversarial 4-lens × 3-skeptic refute-verify: firewall lens = NOTHING (transitive
> import trace clean); spec-fidelity = PASS, zero findings; separate-entity = 1 LOW (the cookie path) FIXED;
> security = 0 HIGH/MED + 3 LOW ACCEPTED as documented (best-effort spoofable rate key — entropy is the real
> defense; benign 409 `str(e)` vocabulary; the pre-existing weaker email-header fallback now also gates publish →
> owner follow-up (d) below). A 5-agent plans-consistency audit also ran: fixes = `docs/deploy-tunnel.md`
> endpoint enumeration, `.env.example` origin-auth + QX-sidecar blocks, the G3 plan's tracker pointer, a
> `docs/codex-reviews/README.md` index. **DEC-12 RATIFIED** (and DEC-10/DEC-11 formally promoted alongside it in
> `HANDOFF.md`): the publish gate holds (owner-gated, never-automated, delegates only to reviewed G1 code) ·
> identity is owner-enrolled/session-based/OPTIONAL (no open registration; `/learn` stays public; NO per-student
> learning state until G4) · firewall by physical isolation (publish writes only `published/` + append-only
> governance events; login writes ONLY `pratham.db`; the 7 subsystems + inward `build()` + 5 guards untouched) ·
> `pratham.db` durable + gitignored · NO governance migration/table/state-machine change. Gate **608 pytest**
> (609 collected; 1 skip = opt-in live-LLM smoke; 0 failures) + **604 vitest** (72 files) + tsc + build green.
> ⚠ **OWNER:** (a) `pratham.db` is created on first `samagra pratham enroll`; (b) set
> `SAMAGRA_PRATHAM_COOKIE_SECURE=0` for local http dev; (c) public exposure of `/learn` + `/api/published` +
> `/api/learn/*` is still the separate owner deploy step (G2 carry-over — now urgent, login endpoints exist);
> (d) configure `SAMAGRA_ACCESS_AUD` + `SAMAGRA_ACCESS_TEAM_DOMAIN` (templated in `.env.example`) so the origin
> gate verifies real Access JWTs — the spoofable email-header fallback's blast radius now includes publish;
> (e) the live stores are still EMPTY (no `published/`, 0 students, 1 legacy assignment) — the next milestone is
> the first REAL throughput run: `factory plan textbook:<slug>` → `approve-seed` → `build` → `publish` → verify at
> `/learn`. Spec `docs/superpowers/specs/2026-06-28-samagra-content-factory-phase-g3-identity-and-publish-write-design.md`;
> plan `docs/superpowers/plans/2026-06-28-samagra-content-factory-phase-g3-identity-and-publish-write.md`; review
> `docs/codex-reviews/28`.
>
> **✅ PHASE G4 (the ADAPTIVE STUDENT TWIN, v1) CODE COMPLETE on branch `feature/content-factory-phase-g4`, built
> subagent-driven TDD (13-task plan, Tasks 0–11 done, each spec+quality double-reviewed) 2026-07-05.** G4 closes the
> PRATHAM arc's last deferred piece — per-student progress tracking + a deterministic "what's next" queue over the
> Phase-E coverage graph. **(a) Progress:** an additive `progress` table in `pratham.db` (`SCHEMA_VERSION` 1→2; PK
> `(student_id,chapter,lane)`; idempotent upsert; a real v1→v2 db upgrade proven) + `service.mark_done` (a
> **60/min rate limiter keyed on the authenticated `student_id`**) + `progress_for`. **(b) Ranker:** a PURE
> deterministic `samagra/factory/coverage/next_best.rank_next` — demand × published minus done, Saar-led lane
> priority mirroring the frontend's `LANE_ORDER`, `_QUEUE_SIZE=8`. **(c) Glue:** `samagra/api/learn_next.py` — the
> ONE module joining pratham × factory (published manifest × concept-graph demand via `connect_ro` × the student's
> done-set), graceful-empty and graceful on a **corrupt** `concept_graph.db` too (a quality-review catch: `build.py`
> writes non-atomically, so a killed rebuild can leave a corrupt db — now caught via `sqlite3.Error`). **(d) Two new
> endpoints:** **`POST /api/learn/progress`** — SAMAGRA's **FIRST authenticated student write** (session-cookie-only
> identity ⇒ structural IDOR prevention, no student id ever accepted from the client; 400 validation; 404-before-write
> against the LIVE published manifest; 429 rate-limit; idempotent `{"ok": true}`; deliberately public-prefix —
> session-gated, NOT origin-gated) and **`GET /api/learn/next`** — the session-gated deterministic queue (F-G4-4:
> adaptivity is a reward for signing in). **(e) Frontend:** `/learn` reader gains a student-gated "Mark done" button
> + Done badge + a top-5 "What's next" deep-link strip; the anonymous-invariance baseline was frozen in its own
> commit BEFORE any adaptive JSX landed (spec §11 discipline). **Golden threads** (`tests/test_g4_golden.py`) prove
> the adaptive loop end-to-end AND that the durable `governance.db` stays BYTE-unchanged through the whole loop,
> anonymous requests get clean 401s, and `/api/published` is untouched. **Proposed DEC-13** (pending ratification):
> (1) all student writes touch ONLY `pratham.db`, `samagra/pratham/` imports no factory/governance module; (2)
> student identity is server-derived only — no student id parameter anywhere under `/api/learn/*`, ever; (3)
> progress rows only reference published content — the 404-before-write manifest gate is load-bearing; (4) the
> recommender is Tier-1 deterministic (no LLM/network/key) — any future LLM recommender is a distinct
> phase+decision+review, never a silent upgrade; (5) the v1 progress write's CSRF acceptance is scoped narrowly
> (own-data, no escalation; `SameSite=Lax` + cookie `path=/api/learn`) — any new `/api/learn/*` write re-opens it;
> (6) anonymous `/learn` stays byte-identical, `/api/published*` untouched, the publish gate + inward `build()` + 5
> guards + the 7 subsystems + `governance.db` (no migration/table/state-machine change) all untouched. **Gate: 637
> pytest** (1 skip = opt-in live-LLM smoke; 0 failures; up from the G3 baseline of 608) **+ 612 vitest** (74 files;
> up from 604); `tsc --noEmit` + `npm run build` green. **REMAINING BEFORE MERGE (Task 13, NOT yet done):** a
> dedicated Codex pre-merge review of the student write boundary (→ `docs/codex-reviews/29`) + a 4-lens adversarial
> final review → remediate → `merge --ff-only` → push. Spec
> `docs/superpowers/specs/2026-07-05-samagra-content-factory-phase-g4-adaptive-twin-design.md`; plan
> `docs/superpowers/plans/2026-07-05-samagra-content-factory-phase-g4-adaptive-twin.md`. ⚠ **OWNER:** queue size
> (`_QUEUE_SIZE=8`) + the rate limit (60/min) are code constants, tunable later; an operator progress view is
> deferred (spec §12); `/learn` public exposure is still the separate owner deploy step; the first live throughput
> run is still pending (stores are still empty); the samagra server needs a restart post-merge before
> `/api/learn/next` exists live.
>
> **NEXT: Phase G4 is CODE COMPLETE, review gate PENDING.** Immediate next action = Task 13 (Codex pre-merge review
> of the student write boundary + 4-lens adversarial final review, then merge to `main` + push). After that: the
> first REAL live throughput run (`factory plan textbook:<slug>` → `approve-seed` → `build` → `publish` → verify at
> `/learn` with a real signed-in student exercising mark-done + what's-next). Phase F (the heavy async LLM lanes —
> NotebookLM audio/slides, image-gen figures, Tier-2/3 coverage edges) follows after G4 fully lands, per DEC-9's
> ratified ordering. The `/learn` public exposure remains a separate owner deploy step. **DEC-8 invariants
> unchanged.**
>
> **✅ PHASE G5 (FACTORY RUN OVER HTTP — the Publish app's "Factory run" stepper) BUILT TDD + Codex-30-reviewed
> (GO + addendum GO) + 4-lens-adversarially-reviewed (3 MED remediated + re-verified) + DEC-14 RATIFIED + MERGED
> to `main` + PUSHED 2026-07-06** (branch `feature/factory-run-http`). G5 gives the Chairman a GUI path through the same
> plan→approve-seed→build→publish recipe the CLI already runs, so a real throughput run no longer needs a
> terminal. **Three new origin-gated endpoints** — `POST /api/factory/plan`, `POST /api/factory/approve-seed`,
> `POST /api/factory/build` — added to `origin_auth._PROTECTED_POSTS` (now **9 protected POSTs** + the
> `/api/gate/` pattern route + 4 protected GETs), each a **thin delegate to the already-reviewed
> `samagra/factory/run.py`** (zero new write logic — only HTTP argument-parsing + error-mapping). **The
> structural refusal:** `POST /api/factory/build` refuses `kind in {"llm","mcd"}` with **403** before calling
> `run.build` — enforced by the `LINES` registry's `kind` field, so the one production-write path (the mcd seed
> lane) and the opt-in LLM lane keep **zero** HTTP triggers, full stop. A `_FACTORY_RUN_LOCK` serializes the
> read-then-write windows the GUI can now double-click/race (a caught review finding: an unserialized endpoint
> duplicated governance rows under concurrent POSTs — fixed by holding the lock across the dedup-check + write).
> **Frontend:** pure `frontend/src/lib/publishctl/recipe.ts` (stepper-state derivation + fetch wrappers) + a
> "Factory run" panel in the Publish app — per-gate buttons (Plan / Approve / Build-all / Publish), each its own
> explicit owner click, in-flight disable so a slow request can't be double-fired from the UI itself (belt to the
> lock's suspenders). **Golden threads** (`tests/test_g5_golden.py`) prove the HTTP recipe produces the same
> result as the CLI recipe, the llm/mcd 403 holds, origin-gating holds, and the student surface (`/learn`,
> `/api/learn/*`, `/api/published*`) carries zero diffs. **Deferred review cleanups closed same-slice:** the
> `origin_auth.is_protected` docstring (stale "five mutating POSTs" wording, now tracks the real 9-entry set +
> pattern route) and the concurrency-race test (was reusing one seed across its 5 iterations, so only iteration 1
> exercised the true race window — now uses a distinct seed per iteration so dedup is proven on every pass, not
> just the first). **DEC-14 RATIFIED 2026-07-06** (the Chairman's explicit merge-gate go; the dedicated ratify
> commit flipped the spec's Status header + trackers — the DEC-13 precedent. Post-review, invariant 3 is enforced
> at BOTH HTTP gates: `approve-seed` skips llm/mcd children — commit `336d670` — and `build` 403s them): (1) no
> new write mechanism — the three endpoints add zero logic to `run.py`; (2) the
> never-automated publish gate is unchanged — the GUI is a second owner trigger beside the CLI, `build-all` is
> client-side sugar over N single-assignment calls, never a server-side batch-write primitive; (3) the llm/mcd
> lanes are structurally unreachable over HTTP (the `kind` refusal, not a maintained allowlist); (4) all three
> POSTs are origin-gated, never public-prefix; (5) the student surface is untouched; (6) no migration, no
> governance schema change. **Gate: 667 pytest** (666 passed, 1 skip = opt-in live-LLM smoke, 0 failures) **+ 639
> vitest** (75 files); `tsc --noEmit` + `npm run build` green. **Review gate CLOSED:** dedicated Codex pre-merge
> review 30 = **GO** (0 findings, 6/6 DEC-14 invariants) **+ addendum GO** on the remediation delta (1 LOW —
> pre-lock scan race in `approve-seed` — fixed TDD, 5/5 red pre-fix); 4-lens adversarial Workflow
> (`wf_1a3c272d-9db`: firewall + separate-entity lenses clean; **3 MED confirmed** — approve-seed rubber-stamped
> CLI-planned samadhan rows for the same seed · DEC-14 ratification overclaim in trackers · golden thread 1
> under-proved — all **remediated + independently re-verified** by live exploit replay; golden thread 1 now
> builds all 5 lanes + publishes via the G3 endpoint). Report
> `docs/codex-reviews/30-g5-factory-run-http-premerge.report.md`. Spec
> `docs/superpowers/specs/2026-07-06-samagra-content-factory-phase-g5-factory-run-http-design.md`;
> plan `docs/superpowers/plans/2026-07-06-samagra-content-factory-phase-g5-factory-run-http.md`. ⚠ **OWNER:**
> server restarted post-merge (the 3 endpoints + the Factory-run panel are live); the Chairman should run one
> real GUI-driven recipe as the **first GUI-driven throughput run** (plan → approve → build → publish, verified
> at `/learn`); `/learn` public exposure remains the separate owner deploy step. **Chairman directive
> 2026-07-06:** SAMAGRA's question bank should use `C:\SandBox\claude_khanak_box\combinedDBQues` (the combined
> question-DB project) as its source — wiring it in (today the paper/drill lanes + the Questions app read the QX
> engine on :8783) is a future slice needing its own design + review.
>
> **✅ FIRST GUI-DRIVEN THROUGHPUT RUN DONE 2026-07-06 (Chairman-directed) — the G5 milestone is CLOSED.**
> `gauss-law` ran the whole recipe as clicks in the Publish app's Factory-run stepper (Plan 5 lanes → Approve
> seed 5 → Build all 5, incl. paper/drill against live QX → Publish) and is LIVE at `/learn/gauss-law` (all 5
> lane tabs render; Pariksha spot-checked answer-free). The **G4 adaptive loop was exercised live in the same
> pass** (fresh student enrolled → signed in → mark-done accepted with Done badge → deterministic What's-next
> queue; smoke student revoked after). `published/` now carries TWO chapters — circular-motion (published
> 2026-07-05 22:59Z during the G5 session's live review-replay, `pub_c5b532ad64eb`) + gauss-law (today's GUI
> run) — **the live stores are no longer empty.** ⚠ Run evidence for the rewire: QX served Q1≡Q2 duplicates
> for the gauss-law paper (only 2 exact hits); QX was also cold/slow (28–48s vs the client's 30s timeout)
> before warming mid-run — QX-lane build failures are clean + retryable by re-clicking Build.
>
> **✅ SLICE R (combinedDBQues question-bank rewire) SHIPPED + spec RATIFIED + DEC-15 RATIFIED 2026-07-07** — built
> on branch `feature/combineddbques-rewire`, commits `2fa3e8f..3581d63` (docs-synced same date). Repoints SAMAGRA's
> question bank from the old QX engine (:8783, `C:\SandBox\gpt_box\gpt-extract-ques`) to **combinedDBQues** (:8790,
> `C:\SandBox\claude_khanak_box\combinedDBQues` — 48,589 physics questions, live WAL sqlite corpus), on the
> Chairman's 2026-07-06 directive and the same-day run evidence (QX served Q1≡Q2 duplicates for the gauss-law
> paper; QX was also cold-slow). **Config repoint:** `COMBINED_DB_ROOT` (env `SAMAGRA_COMBINED_DB_ROOT`),
> `QX_SERVER_URL` default :8790, unified DB paths (`app/qx/unified_{content,builder}.sqlite`) with rollback env
> overrides `SAMAGRA_QX_BUILDER_DB`/`SAMAGRA_QX_CONTENT_DB`. **Chapter mapping:** a git-committed 59-row
> `chapter_map.json` (slug → `{chapter_id, chapter display name}`) + PURE loader `samagra/factory/chapter_map.py`
> (graceful on missing/bad JSON) + a frozen 30-chapter taxonomy fixture (no live dependency in unit tests). **The
> load-bearing rework — tiered topical retrieval** in `samagra/factory/paper.py`'s `_retrieve`: **tier 1** exact
> query+chapter-scoped → if fewer than `_DRILL_SIZE` (8) distinct post-dedupe hits, **tier 2** semantic
> query+chapter-scoped → if empty/unmapped, **tier 3** the legacy exact text-only fallback; meta
> `{query, chapter, mode}` recorded in the artifact JSON with `mode` mirrored verbatim from the server
> (degradation-honest, never overclaims a stronger retrieval tier than what ran). **Dedupe** —
> `_dedupe_results` (tag-stripped visible text + `data-tex` math-aware projection; figure src/alt deliberately
> excluded per a 127-row live census showing every real collision is a true duplicate) runs BEFORE the drill slice,
> pinned by regression. **`adapters/qx.py`** dropped `immutable=1` (WAL-resident data was invisible under it) → plain
> `mode=ro`. Opt-in live smoke `SAMAGRA_LIVE_QX_SMOKE` (live-proven: paper 25 q / drill 8, answer-free, dedupe held).
> Docs: `.env.example` + `docs/deploy-tunnel.md` (3-line rollback recipe + 2 DB-path overrides for non-standard
> layouts, LAN demo mode, the `COMBINEDDB-QX` autostart schtask as a **pending owner registration** with a verbatim
> one-liner). `concept_aliases.json` re-curated + coverage rebuilt: **128 concepts, 1054 edges, 768 cells, 600
> gaps** (was 86/727/516/498); residual no-pointer concepts (transistors/modulation/radioactivity) are legitimately
> out of textbook scope. **Plan deltas D1–D5:** D1 `SAMAGRA_HOST` already existed; D2 rollback also needs the 2
> DB-path env overrides; D3 dropped `immutable=1` (WAL invisibility); D4 tiered retrieval REPLACED the spec's
> original chapter-listing-primary design (the review HIGH below); D5 dedupe projection extended with `data-tex`
> (the Codex MED below). **Review gate:** **4-lens adversarial Workflow `wf_7cf5c7d9-ac4`** — 1 HIGH (chapter-only
> listing made 51/59 same-chapter textbook slugs return byte-identical papers/drills, live-reproduced) → fixed by
> the tiered retrieval; 1 MED (docs claimed a non-existent schtask) → fixed; an independent re-verifier confirmed
> all 4 findings FIXED via a fresh live slug-pair replay (`kinematics-2-d` vs `kinematics-relative-motion` via
> tier-2 semantic; `electric-field` vs `electric-dipole` via tier-1 — distinct, answer-free drills). **Codex
> pre-merge review 31** (DEC-7-style, the QX-seam boundary): **NO-GO** (MED dedupe blind to `data-tex` math; LOW
> weak rollback fail-visibility) → remediated TDD → **addendum NO-GO** (MED image src/alt dedupe — **REFUTED** with
> a live 127-row census, pinned by design; LOW rollback-docs overclaim — fixed; LOW mode metadata lying on degraded
> semantic — fixed) → **addendum-2 GO-WITH-CAVEATS** (all 3 resolved; 1 new LOW mode-schema caveat → closed
> same-slice, commit `3c4d21e`) = effectively **GO**. Report committed
> `docs/codex-reviews/31-combineddbques-rewire-premerge.report.md`. **Invariants HELD (DEC-15):** (1) combinedDBQues
> strictly READ-ONLY for samagra (HTTP GET + direct sqlite `mode=ro` only); (2) the answer-leak guard
> (`_ANSWER_MARKERS`/`_assert_no_answer_leak`) unchanged, covering the fork's render output; (3) no new prod write
> path, publish gate untouched, no migration, no secrets; (4) `chapter_map.json` is the git-committed curated
> crosswalk — retrieval-curation changes are reviewed commits, never runtime state; (5) rollback = the documented
> env-line set. **Gate: 695 pytest** (0 failures, 2 skips = opt-in live smokes) **+ 639 vitest + tsc + build green.**
> **DEC-15 RATIFIED 2026-07-07** on the Chairman's standing "slice r spec approved... auto approve and execute"
> delegation, now that the review gate above is fully closed. Spec
> `docs/superpowers/specs/2026-07-06-samagra-combineddbques-rewire-design.md` (Status flipped to RATIFIED & SHIPPED,
> §15 records the full implementation-outcome chronicle); plan
> `docs/superpowers/plans/2026-07-06-samagra-combineddbques-rewire.md`. **⚠ OWNER:** (a) register the
> `COMBINEDDB-QX` schtask (one-liner in `docs/deploy-tunnel.md`); (b) `git push origin main` after merge (agent push
> is classifier-blocked); (c) delete 3 Codex-sandbox-owned throwaway dirs — `tmp/pytest-addendum2-focused`,
> `tmp/pytest-addendum2-full`, `tmp/pytest-review31` — owned by the `CodexSandboxOffline` principal, need
> `takeown /F ... /R /D Y` then `rmdir /S /Q`.
>
> **✅ LLM PROVIDER MINI-SLICE (OpenAI backend for the D2 samadhan generation boundary) SHIPPED 2026-07-07** —
> built on this branch, commits `48e1556..e3ae45f` (5 commits + tracker sync). `samagra/clients/llm_client.py`
> (the ONE LLM call site, Phase D2) is now **provider-aware**: `SAMAGRA_LLM_PROVIDER` ∈ {anthropic (default —
> byte-identical D2 back-compat), openai}. OpenAI path: Responses API (`openai>=2.32`), default model `gpt-5.5`,
> `SAMAGRA_LLM_EFFORT` validated (none/minimal/low/medium/high/xhigh, fail-closed), strict `json_schema` output,
> `_extract_json_openai` with the same never-leak-content hardening; `configured()` + new `required_key_var()`
> are provider-aware; samadhan preflight names the selected provider's key var. `requirements.txt` +=
> `openai>=2.32`; `.env.example` provider block (`SAMAGRA_LLM_MODEL` now an inert override-only knob —
> per-provider defaults rule). Live `.env`: provider=openai, gpt-5.5, effort medium, key present. Interface was
> pre-declared by the Chairman in `.env`; slice executed on "go for next task llm slice". **⭐ FIRST-EVER LIVE
> VALIDATION of the D2 generation boundary:** the opt-in live smoke (`SAMAGRA_LIVE_LLM_SMOKE=1`) was RUN for
> real — PASS, 52s, real gpt-5.5 generation + adversarial review round-trip on circular-motion, artifacts
> written (the D2-era owner follow-up that was never runnable — no Anthropic key ever arrived — is closed).
> **Reviews:** per-task 2-lens (spec compliance + code quality) = PASS/PASS, call shape verified against the
> installed openai 2.32 SDK types. Dedicated Codex pre-merge review 32 (generation boundary) = **GO-WITH-CAVEATS**:
> M (`.env.example`'s active `claude-opus-4-8` model line masked the openai default for template followers) + L
> (preflight refusal message hardcoded `ANTHROPIC_API_KEY`) — **both closed TDD same-slice** (`42ce9d3`,
> `e3ae45f`); the named finding (`SAMAGRA_LLM_MODEL` could name a non-reasoning model while `reasoning.effort` is
> always sent) adjudicated **accept-as-operator-responsibility** (explicit override; OpenAI API fails closed
> cleanly at build time). Effectively **GO**. **Invariants HELD:** keys env-only from the gitignored `.env`,
> never logged/repr'd/echoed (both providers) · fail-closed on unknown provider/effort/missing key;
> `configured()` False → preflight refusal, never a wedge · **DEC-8 reviewer firewall structural on BOTH
> providers** (`review_samadhan` never receives StyleSeed) · no new prod write path · publish gate untouched ·
> no migration · rollback = `SAMAGRA_LLM_PROVIDER=anthropic` (or unset) restores D2 exactly. **Gate: 713 pytest**
> (0 failures, 2 skips = opt-in live smokes) **+ 639 vitest baseline** (frontend untouched). Spec
> `docs/superpowers/specs/2026-07-07-samagra-llm-provider-openai-design.md` (Status flipped to SHIPPED, records
> the implementation-outcome chronicle); report `docs/codex-reviews/32-llm-provider-openai-premerge.report.md`.
>
> **✅ PHASE F1 (the `figure` lane — image-gen physics figures) SHIPPED 2026-07-07 — review gate CLOSED, DEC-16
> RATIFIED, merged `--ff-only` to local `main` (⚠ OWNER PUSH PENDING — agent `git push` classifier-blocked).**
> Branch `feature/content-factory-phase-f1-figures`, 14 commits `7494ceb..<docs tip>`. Chairman: **"go for phase F
> - full auto, carry to completion — use opus subagents only for spec,
> plan and implementation, you orchestrate."** F1 = the first Phase-F heavy/external lane + SAMAGRA's first
> **image-generation** network boundary; it rides the EXISTING `kind="llm"` synchronous build path (same envelope
> as D2 samadhan; NO async-pending state machine). New `samagra/clients/image_client.py` (the ONE image call site,
> OpenAI gpt-image-1, mirrors the llm_client provider pattern — key env-only never logged, fail-closed
> provider/size/quality, `_extract_png` never-leak, injectable fake); `samagra/factory/figure.py` (`_targets`
> selects the 52 owner-authored `image-need` briefs capped at 6 / `SAMAGRA_FIGURE_CAP` [cap≤0 disables];
> `build_figures` generate → per-image vision-review (refute-framed, fail-closed) → data-URI gallery HTML + JSON
> manifest + `fig-NN.png`; `preflight` no-StyleSeed); `llm_client.review_figure` (DEC-8 structural firewall — no
> StyleSeed param); wiring `lines.py`/`dispatch.py`/`run.py` (figure Line kind=llm auto_fan=False so default
> fan-out is unchanged; `SAMAGRA_FIGURE_AUTOCAPTURE` default OFF → every figure build lands `changes`; the 5 build
> guards byte-identical; samadhan unchanged). Forks locked: **A1** briefs-only · **B1** Images API b64 · **C1**
> vision recorded + autocapture-OFF · **D** data-URI gallery HTML = publishable single-file (fork-D, via unchanged
> G1/G2) · **E** no StyleSeed · **F** cap 6 / whole-build-raise / retryable. Built subagent-driven TDD (6 tasks,
> fresh Opus implementer + 2-lens spec+quality review each; 5 per-task issues fixed TDD). **⭐ Live image smoke
> RUN FOR REAL** (`SAMAGRA_LIVE_IMAGE_SMOKE=1`): **PASS ~41s** (real gpt-image-1 + gpt-5.5 vision on
> circular-motion). **Review gate:** **Codex 33 = GO, 0 findings** (`docs/codex-reviews/33-*`); **4-lens
> adversarial** `wf_e335375a-c12` = **2 MED confirmed (live-reproduced) + 1 LOW refuted**, BOTH remediated
> (`80baf3d`) + **independently re-verified FIXED** — **MED#1** per-image `review_figure` verdicts were matched on
> the chapter-global `idx-1` so figures 2..N always fail-closed to `error` (12 multi-brief chapters could never
> capture; fabricated ledger verdicts) → fixed (take the per-image reply's first verdict as authoritative; empty
> list still fails closed; the old FakeVisionClient encoded the wrong shape — corrected + regression);
> **MED#2** blank `SAMAGRA_FIGURE_CAP=` in `.env.example` → `int('')` at IMPORT bricked the whole factory surface
> → fixed (`_read_cap()` blank/invalid → 6; ship concrete `=6`). **Invariants held (both gates):** no new prod
> write path · publish gate untouched (autocapture-OFF = never silent capture) · figure kind=llm 403 over HTTP · 5
> guards byte-identical · no migration · opt-in lane. **DEC-16 RATIFIED** (the F1 figure-lane invariant set — see
> HANDOFF.md). **Gate 771 pytest** (0 fail, 3 skips = opt-in live smokes) **+ 639 vitest**. Spec
> `docs/superpowers/specs/2026-07-07-samagra-content-factory-phase-f1-figure-lane-design.md`; plan
> `docs/superpowers/plans/2026-07-07-samagra-content-factory-phase-f1-figure-lane.md`; review
> `docs/codex-reviews/33-f1-figure-lane-premerge.report.md`.
>
> **✅ PHASE F2 (the `slides` lane — NotebookLM-generated slide decks) SHIPPED 2026-07-07 — review gate CLOSED,
> DEC-17 RATIFIED, merged `--ff-only` to local `main` (⚠ OWNER PUSH PENDING — agent `git push` classifier-blocked).**
> Branch `feature/content-factory-phase-f2-slides`, 19 commits `c7d9986..8939051`, on the Chairman's full-auto
> Phase-F delegation ("go for phase F … carry to completion — use opus subagents only for spec, plan and
> implementation, you orchestrate"). **⇒ PHASE F COMPLETE** (F1 image-gen figures · F2 NotebookLM slides; **NO AUDIO,
> ever** — DEC-9 absolute). F2 = SAMAGRA's FIRST **subprocess / external-CLI generation boundary**: one textbook
> chapter → a NotebookLM slide deck. Rides the EXISTING `kind="llm"` synchronous build path (D2 samadhan envelope —
> preflight anti-wedge, capture/changes gate, retryable rollback); **NO async-pending state machine** (S1
> synchronous-blocking bounded poll chosen over the umbrella spec's parked async design). New
> **`samagra/clients/notebooklm_client.py`** = the ONE `nlm` call site: an injectable subprocess `runner` seam (every
> invocation is a LIST — no shell string / no shell injection); `configured()` parses `nlm login --check` STDOUT
> (never the exit code — nlm can misreport it); deck-format env knobs fail-closed; never-leak errors (verb-named,
> never the raw stderr / chapter text / notebook content); no-secret repr (SAMAGRA holds NO secret — nlm owns the
> Google OAuth). New **`samagra/factory/slides.py`**: `_source_text*` (bounded to **16000 chars — a HARD
> Windows-cmdline safety cap**: `list2cmdline`'s 2× worst case stays under the 32767 CreateProcess limit for ANY
> content), `_wrapper_html` (self-contained data-URI PDF/PPTX, title HTML-escaped — the publishable single-file
> artifact via the UNCHANGED G1/G2 path, fork D), `build_slides` (create EPHEMERAL notebook → add source → generate →
> **synchronous bounded poll** [`SAMAGRA_SLIDES_TIMEOUT` default 900s, a SHARED budget across source-add + poll] →
> download → wrap → write → **`finally`-delete** the notebook; a delete-failure never masks the outcome), `preflight`
> (chapter + nlm authed + deck-format knobs valid + **safe-slug** — anti-wedge, **NO StyleSeed / NO key**). The DEC-8
> reviewer firewall is trivially structural (the lane has NO StyleSeed and NO model-review call at all — NotebookLM
> composes the deck, the owner reviews it). Wiring: `slides` Line (`kind="llm"`, `auto_fan=False`, `textbook:`
> prefix — opt-in; default fan-out unchanged), `run_line` route, `validate_product` deck-file assert, lane-dispatched
> build() preflight (figure/samadhan byte-identical), **`SAMAGRA_SLIDES_AUTOCAPTURE` default OFF → every build lands
> `changes`** (owner review; a NotebookLM deck is a draft, never a silent capture); the 5 build guards byte-identical;
> **kind=llm → 403 over HTTP + skipped by approve-seed** (CLI-only). **NO new prod write path · publish gate
> untouched · no migration · no secret.** Built subagent-driven TDD (6 tasks, fresh Opus implementer + 2-lens
> spec+quality review each; per-task findings fixed TDD incl. never-leak parse hardening, `dl_format` path clamp, the
> airtight NO-AUDIO tripwire). **⭐ Live slides smoke is OWNER-run** (opt-in `SAMAGRA_LIVE_SLIDES_SMOKE`; `nlm` auth
> EXPIRED on the box — the first live validation is an owner action). **Review gate CLOSED:** **Codex pre-merge
> review 34** (DEC-7 subprocess boundary) = NO-GO (0 HIGH, 1 MED slug path-containment, 1 LOW preflight knob-drift) →
> **both remediated TDD → effectively GO** (8/10 boundary invariants PASSed first pass); **4-lens adversarial
> Workflow `wf_3229f26e-2b0`** = **0 firewall/security findings, 0 HIGH**; 6 raw → 4 confirmed (1 MED
> double-timeout-budget · 1 LOW preflight · 2 NIT), 2 refuted — MED+LOW+NITs all remediated (shared timeout deadline ·
> eager knob validation · poll-interval floor · slug containment) + regressions. **DEC-17 RATIFIED** (the F2
> slides-lane invariant set — see HANDOFF.md). **Gate 848 pytest** (0 fail, 4 skips = opt-in live smokes) **+ 639
> vitest** (frontend untouched). Spec `docs/superpowers/specs/2026-07-07-samagra-content-factory-phase-f2-slides-lane-design.md`;
> plan `docs/superpowers/plans/2026-07-07-samagra-content-factory-phase-f2-slides-lane.md`; review
> `docs/codex-reviews/34-f2-slides-lane-premerge.report.md`. **⚠ OWNER:** (a) `git push origin main` (agent push
> classifier-blocked — F1 + F2 now ~33 commits ahead of origin); (b) re-auth `nlm login`, then run the live slides
> smoke once (`SAMAGRA_LIVE_SLIDES_SMOKE=1 …`); (c) a factory-wide slug path-containment hardening (the raw
> slug → `EXPORT_DIR` pattern in every lane + `render.load_chapter`) is tracked as a SEPARATE slice (Codex 34 MED's
> broader class; F2 hardened its own boundary).
>
> **✅ SLICE "DESKTOP ICONS + 3 READ-ONLY CORPUS APPS" BUILT 2026-07-09 — review gate CLOSED, DEC-18 PROPOSED
> (pending Chairman ratification), committed `f7038dc` on branch `feature/desktop-icons-corpus-apps` (⚠ merge to
> `main` pending).** 4 tasks (T4 pipeline multi-stream = an exploration ANNEX in the plan only, ZERO implementation).
> **T1** desktop icons with full app names on the SAMAGRA OS desktop (pure `frontend/src/lib/desktop` layout math,
> column-flow wrap clamped to the work-area; `pointerEvents:none` wrapper so a bare-desktop right-click still opens
> the desktop menu; tile-click dismisses menus; 3 themes + mobile untouched). **T2** THREE read-only source
> subsystems — GN-OCR (`C:\SandBox\claude_box\claude-GN-OCR`) · onedpulls (`C:\SandBox\gemini_box\onedpulls`) ·
> lecturepdfs (`C:\SandBox\claude_box\lecturepdfs`): env-overridable `*_ROOT` config vars, adapters (sqlite `mode=ro`
> / filesystem only) registered in `ALL_ADAPTERS`, and the origin-GATED reverse-proxy surface `GET /api/corpus/{name}`
> (listing) + `GET /api/corpus/{name}/serve/{path}` (`is_protected` gained a GET `startswith "/api/corpus/"` prefix
> branch). Proxy hardening: exact positive per-corpus allowlists · normalize-before-match · no-redirect transport +
> final-URL host revalidation · hard wall-clock read deadline + 25MB cap · userinfo-rejecting base URLs · onedpull
> answer-family exclusion + defense-in-depth body scan · `<base href>` + JS fetch-literal rewrite · graceful
> daemon-down 503. **T3** three windowed apps (`GnBrain`/`CorpusBrain`/`LectureBrain`, AppIds
> `gnocr`/`onedpull`/`lecturepdf`) = same-origin iframes of the gated serve proxy, NO sandbox attr (trusted gated
> owner apps; the Pratham published-artifact CSP untouched + distinct), offline+retry panels; the
> `AppId`/`APPS`/`ORDER`/`ICONS` registry grows 19→22 apps. **Reviews:** opus-xhigh per-task + fable-medium
> whole-slice final (2 MED fixed TDD: lecturepdf date-key data-loss ~69 lectures + lecturepdf Vue JS fetch-literal
> rewrite); dedicated Codex pre-merge review 35 (the proxy/serve/gate boundary) = NO-GO (MED SSRF-via-redirect · MED
> slow-drip DoS · LOW cred-leak in an error hint) → all 3 remediated TDD → addendum GO-WITH-CAVEATS (lone accepted
> caveat: the read deadline is bounded-not-exact — one in-flight `read1` may run to the socket timeout; accepted
> under the single-operator origin-gated-owner threat model) = effectively GO. Report
> `docs/codex-reviews/35-corpus-apps-premerge.report.md`. **Invariants HELD:** read-only firewall over the 3 new
> corpora + the 7 existing subsystems · NO new prod write path · publish gate untouched · student surface (`/learn`,
> `/api/published*`, `/api/learn/*`) byte-identical (golden test) · `governance.db` no migration/table/state-machine
> change · inward `build()` + 5 crash-safety guards untouched. **Proposed DEC-18** (pending ratification — text in
> HANDOFF.md's decisions block) = the read-only corpus subsystem + proxy invariant set: corpora READ-ONLY (SAMAGRA
> never writes into any corpus root) · `/api/corpus/*` entirely GET + origin-gated, no public-prefix, no new POST ·
> the proxy hardening set above · onedpull answer families excluded + body-scanned, nothing from the proxies feeds
> `published/` or `/learn` · same-origin no-sandbox trusted iframes (Pratham sandbox precedent untouched + distinct)
> · student surface / publish gate / inward `build()`+5 guards / 7 subsystems / `governance.db` all untouched.
> **Gate: 919 pytest** (915 passed, 4 opt-in live-smoke skips, 0 fail; up from the F2 baseline of 848) **+ 668
> vitest** (80 files; up from 639) + `tsc --noEmit` + `npm run build` green. Also same session (separate commit
> `dd233c3`): the mcd root repointed to `C:\SandBox\claude_khanak_box\mycontentdev` via env-overridable
> `config.MCD_ROOT`.
>
> **NEXT: Chairman ratifies DEC-18 → merge `feature/desktop-icons-corpus-apps` to `main`.** Phase F remains COMPLETE
> (F1 figures · F2 slides; NO audio — DEC-9 absolute). Remaining owner steps: `git push origin main`; re-auth + live
> slides smoke; the `/learn` public deploy; the first live throughput run. **DEC-8 invariants unchanged.**
>
> **✅ Direction-coherence decision (ratified 2026-06-21 by Deepak; amended by DEC-6 on 2026-06-22):** a coherence
> audit found execution solid but the strategic direction drifting — "SAMAGRA OS" had re-introduced the OS-sized
> scope the 2026-06-19 vision deliberately retired. **Decided & binding:** SAMAGRA OS is a *bounded operator
> console* (UI metaphor only); a scope firewall is in force (DEC-1/DEC-3); the never-automated publish gate holds;
> Phase 3 (active loop) is the primary value engine (DEC-5). **⚠ DEC-6 (2026-06-22, Chairman): the pre-E3
> attention-ROI gate (DEC-4) is RETIRED** (not deferred), and the **attention-ROI north-star + kill-criterion
> (DEC-2) are relaxed from binding to advisory** — E3 + the public deploy shipped ahead of the gate and the
> bounded console is judged already proven; Phase 3 is now ungated. See `HANDOFF.md` →
> *✅ Direction-coherence DECISION* (DEC-1…DEC-6) and `STATUS.html` → *Direction coherence*.
>
> **✅ DEC-3 AMENDMENT (2026-06-21, Chairman):** the read-only firewall is amended to allow **owner-initiated
> capture** — exactly two **subsystem** write paths, `POST /api/munshi/capture` (munshi item) and `POST /api/mcd/seeds`
> (mcd seed). The human **publish gate stays never-automated**, there is **no munshi→mcd bridge**, and the
> invariant is now *"read-only except owner-initiated capture."* The capture control plane is **live-verified**
> on branch `feature/control-plane-capture` (capture apps read the live workers via `GET /api/munshi/library` +
> `GET /api/mcd/seeds`; Simulations shows the 482 deployed pratyaksh sims; the QX browser facet bug is fixed).
> See `docs/superpowers/specs/2026-06-21-samagra-control-plane-capture-design.md`.
>
> **✅ PHASE 3 — ACTIVE LOOP (the bridge) BUILT + MERGED to `main` + PUSHED to `origin/main` 2026-06-23**
> (ff `88d31e0`; pushed HEAD `1c5ec5d`), per the
> reconciled `docs/superpowers/{specs/2026-06-22-phase3-active-loop-design.md,plans/2026-06-22-phase3-active-loop.md}`.
> `samagra/bridge/` + CLI `samagra bridge scan|approve|submit`: munshi item → classify → propose seed + pointers →
> `in-review` board assignment → **manual `approve`** → **manual `submit`** (creates the mcd seed). **Governance
> consistency:** this is the **board-approved, owner-driven** munshi→seed loop of spec §8/§9.4 — it is **NOT** the
> *automated* munshi→mcd promotion DEC-3 forbade (every seed needs an explicit human approve+submit), it adds **NO
> new subsystem write path** (`submit` reuses the existing `create_seed` behind `POST /api/mcd/seeds`; still exactly
> two write paths) and **no new web endpoint**, and the **never-automated publish gate is untouched**. It was
> **explicitly directed by the Chairman** ("go for phase 3"), the action DEC-3 reserved, and is DEC-5's primary
> value engine (ungated by DEC-6). Golden thread proven live (seed `seed_01KVRFPPT98HJVQ5NRBJ63MKR3`). **Codex
> pre-merge review done:** review 22 returned **NO-GO** (prod double-write robustness) → all findings remediated TDD
> (H3 scan dedups status-blind incl. terminal `captured`; H1 fail-safe `seed_submitting` intent guard refuses a
> crashed/in-flight retry; M1 `validate_seed_payload` at the write boundary; M2 graceful munshi-down; Low
> word-boundary classify + full-id outbox guard) → re-review 23 **GO-WITH-CAVEATS, all 6 resolved** (H2 concurrent
> submit accepted Low under the single-operator manual-CLI threat model). Gate **272 pytest** (was 263).
> Reports `docs/codex-reviews/22,23`.

<!-- scribe:begin v1 -->
## TeachingOS memory — auto-generated by scribe; edit OUTSIDE this block only
_Updated 2026-07-08T22:44. Source: agent session distillation._
- (5) 2026-07-08 claude: External apps are embedded in Samagra with native UI, ensuring layout responsiveness to Samagra window. [embedding, responsive UI, external apps]
- (5) 2026-07-07 claude: Slice R (rewire question bank from old QX to combinedDBQues) is the current primary task for TeachingOS/SAMAGRA post-G5. [SAMAGRA, question bank, Slice R]
- (5) 2026-07-06 claude: The question bank directory for SAMAGRA is set to C:\SandBox\claude_khanak_box\combinedDBQues. [question bank, SAMAGRA, file path]
- (5) 2026-07-06 codex: A 4-lens adversarial review found 3 MEDs, leading to a remediation delta (3 commits). [adversarial review, MED, remediation]
- (5) 2026-07-05 codex: Write endpoint POST /api/learn/progress uses JWT authentication with a token extracted from the Authorization header. [authentication, JWT]
- (5) 2026-07-05 codex: Missing CSRF token validation on the POST /api/learn/progress endpoint; recommendation to integrate existing CSRF middleware. [CSRF, security]
- (5) 2026-07-04 codex: Phase G3 adds the system's first inbound HTTP write surfaces to SAMAGRA. [Phase G3, write surfaces, HTTP]
- (5) 2026-07-02 claude: Samagra's current architecture is too passive; redesign as an active dashboard. [Samagra, architecture, redesign]
- (5) 2026-07-02 claude: Proposed modular redesign with plugins for study tools, tasks, and notes. [modular design, plugins]
- (5) 2026-06-28 claude: Phase G3 of SAMAGRA content factory project involves implementing multi-tenant student identity (PRATHAM) and the outward POST /api/factory/publish write path. [SAMAGRA, G3, PRATHAM, multi-tenant, student identity, POST /api/factory/publish]
- (5) 2026-06-28 claude: Project named TeachingOS is the focus of development. [project, TeachingOS]
- (5) 2026-06-27 claude: Phase G (PRATHAM) was prioritized over Phase F, reversing the original order as per user directive from a previous conversation. [TeachingOS, PRATHAM, Phase G, Phase F, project planning]
- (5) 2026-06-27 claude: Codex agents were launched for adversarial review of the current codebase, performing multidimensional exploration and bug hunting. [codex agents, adversarial review, bug hunting, code review]
- (5) 2026-06-26 codex: Manifest generation fails when concept tags are missing, throwing unhandled KeyError. [manifest, error handling, KeyError]
- (5) 2026-06-26 codex: Missing JWT authentication on POST /api/questions in samagra/questions_proxy.py [authentication, API security]
- (5) 2026-06-26 codex: org.py endpoint GET /org/{id}/members allows enumeration without authorization (IDOR) [IDOR, authorization]
- (5) 2026-06-26 codex: User-provided content (problem statements, solutions) is directly interpolated into LaTeX and HTML templates without sanitization, enabling injection attacks. [input sanitization, injection, LaTeX, HTML]
- (5) 2026-06-26 codex: Hardcoded database credentials and API tokens were found in config.py, committed to version control. [secret leak, credentials, security]
- (5) 2026-06-26 codex: The application does not validate or escape user input in SQL queries via raw string formatting, making it vulnerable to SQL injection. [SQL injection, input validation, database security]
- (5) 2026-06-26 codex: LLM client calls in llm_client.py lack timeout handling; network failures cause indefinite hangs. [LLM client, timeout, network error]
- (5) 2026-06-26 codex: Textbook subsystem violates read-only firewall by performing direct file writes instead of using sanctioned API endpoints. [write firewall, invariant violation]
- (5) 2026-06-26 claude: Phase E of SAMAGRA content-factory is the Concept Atlas (coverage graph), the STEERING layer of the system. [SAMAGRA, Phase E, Concept Atlas, STEERING layer]
- (5) 2026-06-25 claude: Phase D2 Samadhan LLM lane routes reviewer-flagged or empty briefs to 'changes' instead of 'captured'. [SAMAGRA, content factory, Phase D2, Samadhan LLM, brief routing]
- (5) 2026-06-25 claude: Phase D (StyleSeed) is the durable 'style moat' for the SAMAGRA content factory. [StyleSeed, Phase D, SAMAGRA]
- (5) 2026-06-24 claude: SAMAGRA (TeachingOS project) is implementing a content-factory pivot to generate multi-output physics content for JEE/NEET, moving beyond a read-only console. [SAMAGRA, TeachingOS, content factory, JEE/NEET physics]
- (4) 2026-07-08 claude: Samagra app now displays desktop icons with full app names alongside toolbar icons. [desktop icons, Samagra, UI]
- (4) 2026-07-08 claude: Samagra app now reads additional app/corpus directories: claude-GN-OCR, onedpulls, lecturepdfs. [corpus, apps, Samagra]
- (5) 2026-06-24 codex: Core logic matches design spec docs/superp; no fundamental issues. [design, validation]
- (4) 2026-07-08 claude: TeachingOS project has an app and backend that need to be run on localhost. [TeachingOS, localhost, app, backend]
- (5) 2026-06-23 codex: Remediation commit 91baeeb resolves H1 (high severity) and M1 (medium severity) completely. [remediation, severity]
- (5) 2026-06-23 claude: Phase 3 scope is defined as backend bridge plus CLI for the active loop (DEC-5's primary value engine). [phase 3, active loop, backend bridge, CLI]
- (5) 2026-06-22 claude: TDD is enforced strictly: write test first, watch it fail, then minimal code. [TDD]
- (4) 2026-07-07 claude: The implementation plan is documented at docs/superpowers/plans/2026-07-06-samagra-combineddbques-rewire.md. [plans, documentation]
- (5) 2026-06-22 claude: Plan to perform priority fixes and rescope the ROI gate in a new session, with handoff updates. [priority fixes, ROI gate, handoff, TeachingOS]
- (5) 2026-06-22 claude: User finalized deployment by merging and pushing changes to make it durable. [merge, push, durable]
Deep recall: C:\SandBox\claude_box\memboxes\scribe\bin\scribe.cmd q "<topic>"
<!-- scribe:end -->
