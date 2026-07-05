# SAMAGRA — Handoff

> **▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶ ✅ PHASE G4 (the ADAPTIVE STUDENT TWIN, v1) CODE COMPLETE on branch `feature/content-factory-phase-g4`, built subagent-driven TDD (13-task plan, Tasks 0–11 done, each spec+quality double-reviewed), 2026-07-05. Review gate (Task 13) + merge to `main` are PENDING.**
> G4 closes the PRATHAM arc's last deferred piece — per-student progress tracking + a deterministic "what's next" queue over the Phase-E coverage graph. Driven by the ratified DEC-9 ordering (Phase G before Phase F) continuing past G3.
> - **(a) Progress store** — an additive `progress` table in `pratham.db` (`SCHEMA_VERSION` 1→2; PK `(student_id,chapter,lane)`; idempotent upsert; a real v1→v2 db upgrade proven) + `service.mark_done` (a `_PROGRESS_LIMITER` — 60/min keyed on the **authenticated `student_id`**) + `progress_for`.
> - **(b) Ranker** — a new PURE `samagra/factory/coverage/next_best.rank_next`: demand × published minus done, Saar-led lane priority mirroring the frontend's `LANE_ORDER`, `_QUEUE_SIZE=8`, fully deterministic.
> - **(c) Glue** — new `samagra/api/learn_next.py`, the ONE module joining pratham × factory: published manifest inventory × concept-graph demand (via `connect_ro`) × the signed-in student's done-set; graceful-empty, and graceful on a **corrupt** `concept_graph.db` too — a quality-review catch (`build.py` writes non-atomically, so a killed rebuild can leave a corrupt db) fixed by catching `sqlite3.Error`.
> - **(d) Two new endpoints** — **`POST /api/learn/progress`**, SAMAGRA's **FIRST authenticated student write**: session-cookie-only identity (structural IDOR prevention — no student id ever accepted from path/query/body), 400 validation, 404-before-write against the LIVE published manifest, 429 rate-limit, idempotent `{"ok": true}`; deliberately public-prefix (session-gated, NOT origin-gated). **`GET /api/learn/next`** — the session-gated deterministic queue + done-set (F-G4-4: adaptivity is a reward for signing in).
> - **(e) Frontend** — `lib/pratham/plan.ts` request wrappers (anonymous-safe null/false degrade); a student-gated "Mark done" button + Done badge + a top-5 "What's next" deep-link strip in the `/learn` reader. The **anonymous-invariance baseline was frozen in its own commit BEFORE any adaptive JSX landed** (spec §11 discipline) so byte-identical anonymous behavior is a pinned regression, not an afterthought.
> - **Golden threads** (`tests/test_g4_golden.py`) prove the adaptive loop end-to-end AND that the durable `governance.db` stays **byte-unchanged** through the whole loop; anonymous requests get clean 401s; `/api/published` is untouched.
> - **Reviews so far:** every task spec-reviewed (verbatim-vs-plan + independent test runs) + quality-reviewed; **1 Important finding total** (the corrupt-concept-graph-db degrade above) — fixed TDD, re-reviewed clean; all invariants held per-review.
> - **Proposed DEC-13** (text below, pending ratification — this banner records it as **RATIFIED 2026-07-05** per the Chairman's go on this docs pass; see the decisions block).
> - **Gate: 637 pytest** (1 skip = opt-in live-LLM smoke; 0 failures; up from the G3 baseline of 608) + **612 vitest** (74 files; up from 604); `tsc --noEmit` + `npm run build` green.
> - **⚠ REMAINING BEFORE MERGE (Task 13, explicitly NOT done yet):** a dedicated Codex pre-merge review of the student write boundary (`POST /api/learn/progress` + store/service) and the session-gated read surface (→ `docs/codex-reviews/29`) + a 4-lens adversarial final review (firewall/store-isolation · security · spec-fidelity · identity-optional/separate-entity) → remediate any findings TDD → re-run the full gate → `merge --ff-only` to `main` → push.
> - **⚠ Owner follow-ups:** (a) queue size (`_QUEUE_SIZE=8`) and the rate limit (60/min) are code constants, tunable later; (b) an operator progress view is deferred (spec §12); (c) `/learn` public exposure remains the separate owner deploy step (carried from G2/G3); (d) the first REAL live throughput run is still pending — the stores are still empty; (e) the samagra server needs a restart post-merge before `/api/learn/next` exists live.
> - **Artifacts:** spec `docs/superpowers/specs/2026-07-05-samagra-content-factory-phase-g4-adaptive-twin-design.md`; plan `docs/superpowers/plans/2026-07-05-samagra-content-factory-phase-g4-adaptive-twin.md`; new code `samagra/factory/coverage/next_best.py`, `samagra/api/learn_next.py`, `samagra/pratham/{store,service}.py` (progress additions); tests `tests/test_pratham_progress_store.py`, `tests/test_pratham_progress_service.py`, `tests/test_next_best.py`, `tests/test_learn_next_glue.py`, `tests/test_api_learn_progress.py`, `tests/test_api_learn_next.py`, `tests/test_g4_golden.py`.
> - **▶ NEXT: Task 13 — the review gate — then merge.** After merge: the first live throughput run (`factory plan textbook:<slug>` → `approve-seed` → `build` → `publish` → verify at `/learn` with a real signed-in student exercising mark-done + what's-next). **Phase F** (the heavy async LLM lanes) follows after G4 fully lands.
>
> ---
>
> **▶▶▶▶▶▶▶▶▶▶▶▶▶▶ ✅ PHASE G3 (multi-tenant PRATHAM identity + the outward publish write path — SAMAGRA's FIRST inbound HTTP writes) BUILT TDD + DEC-7 Codex pre-merge review + adversarial multi-lens final review + MERGED to `main` + PUSHED to `origin/main` 2026-07-05 (branch `feature/content-factory-phase-g3`) — durable.**
> G3 opens two physically isolated write boundaries on top of G1/G2. Driven by the owner's continuation of the ratified DEC-9 ordering (Phase G before Phase F).
> - **(a) Owner publish over HTTP** — `POST /api/factory/publish` + `POST /api/factory/unpublish`, added to `origin_auth._PROTECTED_POSTS` (now **7 protected POSTs + 4 protected GETs**), a **thin delegate to the already-reviewed G1 `publish.run`** — no new write mechanism, the never-automated publish gate simply gained a second owner trigger beside the CLI. Plus a minimal operator **Publish** GUI app — the console's **19th app**.
> - **(b) Student identity** — new `samagra/pratham/` package over a **SEPARATE durable gitignored `pratham.db`** (students + sessions, secrets sha256-at-rest). Owner-minted enrollment codes (shown exactly once by `samagra pratham enroll`) redeem at public `POST /api/learn/login` for opaque 256-bit sessions in an `HttpOnly`/`SameSite=Lax`/`Secure` cookie scoped `path=/api/learn`; `POST /api/learn/logout` + `GET /api/learn/me` complete the trio; revoke = instant invalidation; identical-401 no-oracle. `/learn` stays public — sign-in is purely **additive** (anonymous reading unchanged). CLI: `samagra pratham enroll | students | revoke`.
> - **Golden threads PROVEN:** publish-over-HTTP ≡ the G1 CLI result; enroll→login→me→revoke round trip; the durable `governance.db` byte-isolated from every identity write.
> - **DEC-7 dedicated Codex pre-merge review** (`docs/codex-reviews/28-g3-identity-publish-write-premerge.report.md`) = **GO-WITH-CAVEATS, 0 HIGH/MED** — both caveats (the Publish GUI crashing on the real `{assignments,events}` response shape; the session cookie's `path="/"`) **remediated TDD with regressions** → effectively **GO**.
> - **Adversarial final review** (4 lenses — firewall / security / spec-fidelity / separate-entity, every finding refute-verified by 3 independent skeptics): **0 HIGH/MED** — the firewall lens found **NOTHING**, spec-fidelity **PASSED with zero findings**; 3 security LOWs **accepted as documented risks** (best-effort rate limiter; benign 409 error text; the pre-existing weaker email-header owner-gate fallback now also covering publish — closed by owner config, see follow-ups).
> - **DEC-12 RATIFIED** — pins the G3 invariant set (see the Direction-coherence DECISION block below). **DEC-10 and DEC-11** (previously *proposed* in the G1/G2 banners) are **formally promoted to ratified** at the same time.
> - **Gate: 608 pytest** (1 skipped = opt-in live-LLM smoke) + **604 vitest** (72 files); `tsc --noEmit` + `npm run build` green.
> - **⚠ Owner follow-ups:** (a) `pratham.db` is created on first `samagra pratham enroll`; (b) set `SAMAGRA_PRATHAM_COOKIE_SECURE=0` for local http dev; (c) public exposure of `/learn` + `/api/published` + `/api/learn/*` remains a separate owner deploy step (carried from G2, now **urgent** since login endpoints exist); (d) configure `SAMAGRA_ACCESS_AUD` + `SAMAGRA_ACCESS_TEAM_DOMAIN` (now templated in `.env.example`) so the origin gate verifies real Cloudflare Access JWTs — the spoofable email-header fallback's blast radius now includes publish; (e) the live stores are still **EMPTY** (`published/` doesn't exist, 0 students, 1 legacy assignment) — the next real milestone is the **first live throughput run**: `factory plan textbook:<slug>` → `approve-seed` → `build` → `publish` → verify at `/learn`.
> - **▶ NEXT: Phase G3 is COMPLETE.** **Phase G4** (the adaptive student twin — per-student selection over the Phase-E coverage graph, progress tracking) is being planned in detail next, per DEC-9's ratified ordering (Phase G before Phase F); **Phase F** (the heavy async LLM lanes) follows after G4.
>
> ---
>
> **▶▶▶▶▶▶▶▶▶▶▶▶▶ ✅ PHASE G2 (the OUTWARD READ SURFACE + PRATHAM `/learn` reader — SAMAGRA's FIRST outward, read-only, public-by-design crossing) BUILT subagent-driven TDD (9 tasks, fresh implementer + 2-stage spec+quality review each) + adversarial multi-lens final review (14-agent Workflow `wf_d4ae0d21-6cf`, 4 lenses × independent refute-verify) + MERGED to `main` + PUSHED to `origin/main` 2026-06-27 (branch `feature/content-factory-phase-g2`, 15 commits; ff `e753f02..d95267b`) — durable.**
> G2 = the first consumer of the G1 published corpus. Driven by the user's **"lets go for phase G2."**
> - **(a) Backend `samagra/factory/publish/read.py`** (new, PURE, read-only over `run.list_published()`): `published_manifest()` (graceful-empty delegate) + `resolve_artifact(chapter,lane,kind=html)` — resolves the file **FROM the manifest** (never a client path), re-validates a `<safe>/<safe>` `_SAFE_SEGMENT` pair + `relative_to(PUBLISHED_DIR)` containment, **re-verifies sha256** (mismatch raises), returns `{rel,abs_path,bytes,sha256,media_type}` (unknown chapter/lane/kind/missing → `None`).
> - **(b) Two PUBLIC endpoints** (deliberately NOT in `_PROTECTED_GETS` — the `/api/coverage` precedent): **`GET /api/published`** (manifest, graceful-empty) + **`GET /api/published/{chapter}/{lane}`** (`?kind=html|json|docx`, sha-verified bytes, 404 unknown, 500 integrity-breach, **defense-in-depth headers** `nosniff`/`no-referrer` + CSP `sandbox allow-scripts` for html). No static `published/` mount.
> - **(c) Frontend** — a one-line `main.tsx` split on `isLearnPath` mounts a **SEPARATE full-page `<Pratham/>` reader at `/learn`** (no operator OS-shell chrome) else the console; PURE `frontend/src/lib/published/` (`manifest.ts`: `chaptersList`·`laneSort`[Saar-led]·`laneLabel`[Saar·Vaani·Smriti·Pariksha·Abhyaas·Samadhan]·`artifactUrl`·`pickChapter`·`pickLane`·`fileExts`; `route.ts`: `isLearnPath`·`parseLearnPath`·`learnPath`); the reader = chapter list + Saar-led lane tabs + **sandboxed iframe** (`allow-scripts`, `no-referrer`) + empty/error/loading states + docx download + deep-link.
> - **4 forks locked:** separate `/learn` route in the shared Vite build · render all published lanes Saar-led · **code-only deploy-ready** (actual public exposure = a separate owner step) · manifest-resolved + sha-verified artifact endpoint (no static mount). **Proposed DEC-11** pins the outward-read-surface invariant set.
> - **Invariants HELD — READ-ONLY/ADDITIVE:** NO new write path anywhere; serves **only** owner-published bytes resolved through the manifest (never `_publications/`, `governance.db`, `EXPORT_DIR`, or the 7 subsystems); **public-by-design** (the gate was crossed at G1 publish); **separate-entity** (the console at `/` is byte-unchanged; the reader imports NO shell module); the inward `build()` + 5 guards + the never-automated publish gate **untouched**; NO migration/table/state-machine change.
> - **Adversarial final review (14-agent Workflow `wf_d4ae0d21-6cf`, 4 lenses × independent verify): 10 raw → 8 confirmed (0 HIGH, 0 MED, 2 LOW, 6 NIT), 2 refuted; the FIREWALL lens found NOTHING** (read-only proven end-to-end); the separate-entity lens only NITs; path-traversal was independently **attacked with planted hostile `rel` values — every one blocked.** The 2 LOWs (same root): the public artifact response lacked `nosniff`/CSP/`no-referrer` so the in-reader iframe sandbox didn't cover **direct navigation** (a shared deep-link / the docx href) → **FIXED** (the defense-in-depth headers above; CSP `sandbox allow-scripts` forces an opaque origin on direct nav **without** a restrictive `script-src` that would break the artifacts' CDN-loaded KaTeX/MathJax) + regression. NITs closed: exact docx label, a distinct `/api/published` fetch-error state, spec/plan doc reconciliation.
> - **⚠ Process catches:** a subagent caught a real error in the PLAN's golden-test assertion (the `revision` lane renders the **`thin`** variant, not `"revision"`) and a latent **`.gitignore` collision** (G1's unanchored `published/` was silently hiding the new `frontend/src/lib/published/` source dir — fixed by anchoring to `/published/` + a negation). Both verified before applying.
> - **Gate: 562 pytest** (1 skipped = opt-in live-LLM smoke; **no failures**) + **583 vitest** (68 files) + build green.
> - **Artifacts:** spec `docs/superpowers/specs/2026-06-27-samagra-content-factory-phase-g2-outward-read-surface-design.md`; plan `docs/superpowers/plans/2026-06-27-samagra-content-factory-phase-g2-outward-read-surface.md`; new `samagra/factory/publish/read.py`; API `samagra/api/app.py`; frontend `frontend/src/{main.tsx,apps/Pratham,lib/published}`; tests `tests/test_publish_read.py` + `tests/test_published_api.py`.
> - **▶ NEXT (at G2 time): Phase G2 is COMPLETE.** Remaining choices (owner's call): **Phase G3** (multi-tenant identity — PRATHAM identity + the outward `POST /api/factory/publish` write path live here) · **Phase G4** (the adaptive student twin) · or **Phase F** (the heavy async LLM lanes). **⚠ OWNER:** the `/learn` surface is **code-only / deploy-ready** — actually exposing it publicly (a separate hostname or a Cloudflare-Access bypass for `/learn` + `/api/published`) is a separate owner-driven deploy step. **(Update: Phase G3 — multi-tenant PRATHAM identity + the outward publish write path — has since SHIPPED 2026-07-05; see the top banner. Next: Phase G4.)**
>
> ---
>
> **▶▶▶▶▶▶▶▶▶▶▶▶▶ ✅ PHASE G OPENED + G1 (the PUBLISH BOUNDARY — the foundation) BUILT subagent-driven TDD (11 tasks, fresh implementer + 2-stage spec+quality review each) + adversarial multi-lens final review (10-agent Workflow `wf_1aabf2a8-843`, 4 lenses × independent refute-verify) + MERGED to `main` + PUSHED to `origin/main` 2026-06-26 (branch `feature/content-factory-phase-g1`, 19 commits; HEAD `947d62b`) — durable.**
> Phase G un-defers PRATHAM (the A6 downstream student entity) on the Chairman's re-scope of DEC-9. G1 = the publish boundary: `published` becomes a real, durable, owner-gated state via a manual CLI **`samagra factory publish|unpublish|published`**. Driven by the user's **"lets go for phase G before phase F"**.
> - **(a) `samagra/factory/publish/`** — a new PURE-modules-plus-orchestrator package: `manifest.py` (PURE — schema/sha256/`derive_manifest` last-write-wins replay/`unchanged_lanes` idempotency) · `store.py` (atomic writes under `config.PUBLISHED_DIR`, immutable records, path-traversal segment guards) · `run.py` (`publish`/`unpublish`/`list_published` + captured-artifact recovery from `product_created` notes). New config `PUBLISHED_DIR` (durable + gitignored — like `governance.db`, never reset).
> - **(b) What publish does:** `publish <chapter> [--lanes ...]` COPIES a chapter's CAPTURED factory artifacts into an immutable, append-only **`published/`** snapshot — a derived `manifest.json` + frozen artifact copies + immutable per-publication records. This is the export contract a future PRATHAM (G2+) reads INSTEAD of the inward stores. `unpublish` appends a retract (bytes persist); `published` lists the current view.
> - **Proposed DEC-10** pins the invariant set for G1 and all future G-sub-phases.
> - **Adversarial final review (10-agent Workflow `wf_1aabf2a8-843`, 4 lenses × independent verify): 6 raw → 2 MED confirmed+fixed, 4 refuted; the firewall, security, and spec lenses found NOTHING real** (no firewall/write-path breach, no leak, no contract drift). The 2 MEDs (both crash-window consistency): **MED#1** — publish wrote the record before the `published` event, so a crash + records-based no-op retry could SILENTLY lose the audit event → **FIXED** (events-before-record on BOTH publish and unpublish; the record is the crash-authoritative key). **MED#2** — unpublish read the stale `manifest.json` cache, so a crash made `list_published` lie and a retry wrote a duplicate retract → **FIXED** (unpublish + `list_published` derive from the immutable records). Per-task review fixes also landed: strict manifest action state-machine, `_norm_lanes` empty-filter guard, 2 path-traversal guards on the write firewall, crash-safe idempotency-from-records + manifest self-heal.
> - **Invariants HELD:** NO public/outward network surface, NO identity (those are G2/G3); NO new write path to the 7 source subsystems; NO governance migration / NO new table / NO assignment-state-machine change (only new append-only event verbs `published`/`unpublished`); the inward `build()` boundary + its 5 crash-safety guards untouched; the never-automated publish gate is manual-CLI only; mcd/`seed` lane excluded (no local artifact).
> - **Golden thread PROVEN:** a real textbook chapter captured via plan→approve→build → `publish` (Saar sheet) writes the immutable manifest + frozen copy + a `published` event; `unpublish` drops it from the current view while records + bytes persist; the durable `governance.db` assignments table is **byte-unchanged** (only append-only events added).
> - **Gate: 534 pytest** (1 skipped = opt-in live-LLM smoke; lone red = pre-existing env `test_gdocs`, Google API libs absent — fails on `main` too).
> - **Artifacts:** spec `docs/superpowers/specs/2026-06-26-samagra-content-factory-phase-g1-publish-boundary-design.md`; plan `docs/superpowers/plans/2026-06-26-samagra-content-factory-phase-g1-publish-boundary.md`; new package `samagra/factory/publish/`; CLI `samagra/__main__.py`; tests `tests/test_publish_*.py`.
> - **▶ NEXT: Phase G1 is COMPLETE.** Remaining choices (owner's call): **Phase G2** (the outward read-only surface — `GET /api/published` + a student app, Saar sheets first) · **Phase G3** (multi-tenant identity; PRATHAM identity lives here) · or **Phase F** (the heavy async LLM lanes — NotebookLM audio/slides, image-gen figures). **⚠ OWNER:** `published/` is gitignored — created on first `samagra factory publish`. G2/G3/G4 remain deferred.
>
> ---
>
> **▶▶▶▶▶▶▶▶▶▶▶▶ ✅ PHASE E (the COVERAGE GRAPH / CONCEPT ATLAS — the read-only STEERING layer) BUILT subagent-driven TDD (17 tasks) + an 11-agent adversarial multi-lens final review (4 lenses × independent verify) + remediation + MERGED to `main` + PUSHED to `origin/main` 2026-06-26 (ff `ab67968..288d458`; HEAD `288d458`) — durable.**
> SAMAGRA can now *see its own coverage*: ONE rebuildable read-only graph maps the **86 QX physics concepts × 6 producible lanes** into a 3-state heatmap and a demand-ranked gap queue, so the owner steers what to build next. Driven by the user's **"lets go for phase E."**
> - **(a) `samagra/factory/coverage/`** — a new PURE package: `concepts.py` (the QX concept spine, read-only `builder.sqlite`) · `aliases.py` (the git-committed `concept_aliases.json` normalization overlay, label+slug validated) · `edges.py` (in-memory **FTS5** chapter↔concept edges, **AND-prefix primary + OR-prefix fallback**) · `matrix.py` (the **3-state** produced/base/gap rule, factory-produced-only) · `gaps.py` (the **deficit-weighted** ranker `demand/(corpus_n+1)`) · `store.py` (`concept_graph.db` — REBUILDABLE, gitignored) · `build.py` (the idempotent rebuild orchestrator).
> - **(b) Surfaces** — CLI `samagra factory coverage-build | coverage | gaps`; read-only `GET /api/coverage` + `/api/coverage/concept/{id}` (not in `_PROTECTED_GETS`); a new React **Atlas** app (heatmap + deficit-ranked gap queue, each row carrying a copyable `plan_command`).
> - **Locked decisions:** factory-produced-only coverage · 3-state cells · deficit-weighted ranking · FTS base + committed overlay · QX read read-only · gap emission ONLY via the existing `samagra factory plan` CLI (no new write path; the owner's deliberate act).
> - **Adversarial final review (11-agent Workflow `wf_2f09d96c-ff5`, 4 lenses × verify): 0 HIGH; the invariants + contracts lenses found NOTHING** (no firewall/write-path/publish-gate breach, no cross-stack contract drift, the earlier break-glass incident left no bypass artifact). **7 confirmed (1 MED, 4 LOW, 2 NIT), ALL remediated TDD** (commit `288d458`). The **MED**: the FTS **AND-prefix** silently dropped **11 high-demand concepts** (incl. dimensional analysis 2387) from the gap queue → **FIXED** with an OR-prefix fallback (`fts-or`) + the build/CLI now name the residual concepts (real build **11→3** no-pointer; edges 553→727; gaps 450→498). LOWs: overlay slug validation · `list_gaps(top=0)` falsy-LIMIT · golden `produced↔produced_n` invariant + spec §12 honesty (the cleaned-up `governance.db` has 0 captured `textbook:` seeds ⇒ 0 produced cells expected; path covered synthetically) · a governance-byte-unchanged regression. NITs: `graph_meta` provenance hashes (`qx_builder_sha`/`aliases_sha`, **no `built_at`** ⇒ byte-idempotent) · `concepts.py` `path.resolve().as_uri()`.
> - **Invariants HELD:** **no new prod write path** (web GET read-only; `concept_graph.db` derived/rebuildable; the only gap action reuses `factory plan`→`approve_seed`→`build`); **publish gate untouched** (Phase E only *proposes*); **governance read-only / no migration**; the 7 source subsystems stay read-only; **no secrets / no LLM** (Tier-1 deterministic).
> - **Golden thread PROVEN LIVE:** real QX + 59 chapters + governance → **86 concepts, 727 chapter edges, 516 cells, 498 gap seeds**; the durable `governance.db` is **byte-unchanged**.
> - **Gate: 479 pytest** (1 skipped = opt-in live LLM smoke; lone red = pre-existing env `test_gdocs`, Google API libs absent — fails on `main` too).
> - **Artifacts:** spec `docs/superpowers/specs/2026-06-26-samagra-content-factory-phase-e-coverage-graph-design.md`; plan `docs/superpowers/plans/2026-06-26-samagra-content-factory-phase-e-coverage-graph.md`; new package `samagra/factory/coverage/`; API `samagra/api/app.py`; CLI `samagra/__main__.py`; frontend `frontend/src/{apps/Atlas,lib/atlas,types/contracts.ts,registry.ts,App.tsx}`; tests `tests/test_coverage_*.py` (11 suites) + `frontend/src/{apps/Atlas,lib/atlas}/*.test.*`.
> - **▶ NEXT (at E time): Phase F or Phase G.** *(Update: **Phase G1 — the publish boundary — has since SHIPPED 2026-06-26**, branch `feature/content-factory-phase-g1`; see the top banner. The next choice is G2 / G3 / F — owner's call.)* **⚠ OWNER follow-ups (E):** (1) curate `concept_aliases.json` for the 3 residual no-pointer concepts (polarisation [UK/US spelling-split], radioactivity, transistors — surfaced by name at `coverage-build`); (2) `concept_graph.db` is gitignored — run `samagra factory coverage-build` after pulling to materialize it; (3) (carried from D2) run the opt-in Samadhan live smoke once (`SAMAGRA_LIVE_LLM_SMOKE=1 ANTHROPIC_API_KEY=… python -m pytest tests/test_samadhan_live_smoke.py -v`).
>
> ---
>
> **▶▶▶▶▶▶▶▶▶▶▶ ✅ PHASE D2 (the Samadhan live LLM lane — SAMAGRA's FIRST generative content lane) BUILT subagent-driven TDD (5 tasks) + a dedicated DEC-7 Codex generation-boundary review + 2 independent Claude adversarial lenses + MERGED to `main` + PUSHED to `origin/main` 2026-06-25 (ff `f7d2be6..30e7bcc`; HEAD `30e7bcc`) — durable. PHASE D COMPLETE.**
> The first lane that actually *generates* prose is shipped — and with it **Phase D is COMPLETE** (D1 deterministic StyleSeed moat · D2 Samadhan LLM lane · D3 learning-loop scaffold). Three pieces:
> - **(a) `samagra/clients/llm_client.py`** — the ONE Anthropic call site (`claude-opus-4-8`, adaptive thinking, structured output, the StyleSeed system block prompt-cached). The **API key comes only from the gitignored `.env`, never logged or committed**; the client is dependency-injected with an injectable fake so **no test hits the network**.
> - **(b) `samagra/factory/samadhan.py`** — `build_samadhan(slug)`: condition on the StyleSeed → generate → **adversarial reviewer anchored ONLY to the chapter ground-truth, refute-framed** → advisory `style_fit` score → local write.
> - **(c) Factory wiring** — an **opt-in lane** (`auto_fan=False`, reached via `factory plan textbook:<slug> --lane samadhan`; excluded from the default textbook fan-out, F-D4), an **anti-wedge preflight**, and a **capture/changes gate**: a clean brief → `captured`; a reviewer-flagged or empty brief → `changes` for owner review, **never a silent publish**.
> - **DEC-7 dedicated Codex pre-merge review of the generation/compute/secret boundary:** returned **NO-GO** (1 HIGH: a transient LLM failure could permanently wedge an assignment; 2 MED: partial reviewer verdicts defaulted to "ok"; brittle JSON parsing) → all remediated TDD (rollback-on-failure so LLM failures are retryable while the mcd prod-write keeps its fail-safe wedge; fail-closed verdict mapping; robust, non-leaking JSON parsing) → **re-review GO, all findings resolved, no new defects.** The two Claude lenses passed (secrets airtight; the reviewer firewall is structural; the five `build()` guards intact).
> - **Invariants HELD:** **no new prod write path** (the Anthropic call is outbound *generation*, never a write to the 7 read-only source subsystems; only local files are written); the never-automated publish gate is untouched; secrets live only in the gitignored `.env`; no governance/database migration.
> - **Gate: 439 passing / 441 collected · 1 pre-existing env red (`tests/test_gdocs.py::test_upload_happy_path_returns_weblink`, Google API libs absent — unrelated, fails on `main` too) · 1 skipped (the opt-in live smoke `tests/test_samadhan_live_smoke.py`, gated on an explicit `SAMAGRA_LIVE_LLM_SMOKE` flag).**
> - **Artifacts:** plan `docs/superpowers/plans/2026-06-25-samagra-content-factory-phase-d2-samadhan.md`; new code `samagra/clients/llm_client.py` + `samagra/factory/samadhan.py`; wiring in `samagra/factory/{lines,run,dispatch}.py` + `samagra/__main__.py`; tests `tests/test_llm_client.py`, `tests/test_factory_samadhan.py`, `tests/test_factory_samadhan_wiring.py`, `tests/test_cli_factory_lane.py`, `tests/test_samadhan_live_smoke.py`.
> - **▶ NEXT: Phase D is complete.** Per the umbrella roadmap the next phases are **Phase E (the coverage graph / Concept Atlas)** or **Phase F (the heavy async LLM lanes — NotebookLM audio/slides, image-generation figures)**; the PRATHAM student twin remains **Phase G** (deferred). **Owner action:** run the opt-in live smoke once (`SAMAGRA_LIVE_LLM_SMOKE=1 ANTHROPIC_API_KEY=… python -m pytest tests/test_samadhan_live_smoke.py -v`) to validate the real generation boundary. **✅ Fast-follow SHIPPED 2026-06-26** (ff `3540f61..8c5b1dc`): `samagra factory reopen <aid>` closes the `changes`→regenerate loop — `run.reopen()` flips a terminal `changes` brief back to `in-review` (re-approve → rebuild) with a `reopened` audit event; **guard 2 is now reopen-aware count-based** (the prior `product_created` is forgiven for exactly one rebuild; ledger stays append-only — no event deleted); refuses unknown / non-factory / **the mcd seed lane (structural)** / any status but `changes`. TDD +9 tests, gate **448 pytest**.
>
> ---
>
> **▶▶▶▶▶▶▶▶▶▶ ✅ PHASE D3 (StyleSeed LEARNING-LOOP scaffold, owner-ratified-only · DEC-8) BUILT subagent-driven TDD (5 tasks) + a 2-lens independent adversarial review + MERGED to `main` + PUSHED to `origin/main` 2026-06-25 (ff `b756cc2..a9ae176`) — durable.**
> The owner-ratified-only learning loop is shipped. *(Update: **Phase D2 — the Samadhan live LLM lane — has since SHIPPED 2026-06-25**, ff `f7d2be6..30e7bcc`; see the top banner. **Phase D is now COMPLETE.**)* Nothing auto-applies: mining only *proposes*; the owner *ratifies*. Three pieces:
> - **(a) The `style_events` table** — an **additive governance migration `_MIGRATIONS[2]`** (`SCHEMA_VERSION 1→2`; additive + idempotent; **NO `assignments` migration**).
> - **(b) `samagra/factory/style/learn.py`** — `mine_deltas` (mine owner **"changes"-reviews** on samadhan artifacts → proposed candidate style deltas; deterministic + idempotent), `ratify` (promote a candidate's **signed step** into the next committed `styleseed-v<N+1>.json` + a `style_seed_promoted` governance event), and `reject`.
> - **(c) CLI** — `samagra factory style-mine | style-events | style-ratify <id> | style-reject <id>`.
> - **Adversarial review:** **Lens A** (correctness/determinism) = **GO**; **Lens B** (safety/invariants) = **GO-WITH-CAVEATS** with all 5 load-bearing invariants holding + **1 MEDIUM found and FIXED** — `ratify` originally stored a mine-time absolute and overwrote, so two corrections on one facet-key collapsed to a single value; **fixed by storing a signed step re-applied to the then-current profile, so corrections compound** (regression test added). 2 LOWs accepted under the single-operator manual-CLI threat model.
> - **No dedicated Codex pre-merge review was required** — D3 is deterministic + additive (that gate belongs to D2's network/secret boundary).
> - **Invariants HELD:** owner-ratified-only (nothing auto-applies — mining only proposes; the owner ratifies); no new prod write path (only the local `styleseed/*.json` + additive `style_events` rows; the 7 source subsystems stay read-only; no network, no secrets, no API key); governance DB additive-only / never reset; the deterministic StyleSeed moat, the factory `build()` 5 crash-safety guards, and the never-automated publish gate all untouched.
> - **Gate: 409 passing / 410 collected / 1 pre-existing env red** (`tests/test_gdocs.py::test_upload_happy_path_returns_weblink` — Google API libs not installed in this env; unrelated to D3, the same red as D1/Phase-C; fails on `main` too). That is +25 tests over D1's 385.
> - **Artifacts:** plan `docs/superpowers/plans/2026-06-25-samagra-content-factory-phase-d3-learning-loop.md`; new module `samagra/factory/style/learn.py`; migration in `samagra/governance/store.py`; CLI in `samagra/__main__.py`; tests `tests/test_style_events_migration.py`, `tests/test_style_learn.py`, additions to `tests/test_style_cli.py`.
> - **▶ NEXT (at D3 time): Phase D2 — Samadhan live LLM lane (the only remaining Phase-D slice):** `samagra/clients/llm_client.py` (the ONE Anthropic call site, `claude-opus-4-8`, key from gitignored `.env`, never logged) + `samagra/factory/samadhan.py` (`build_samadhan(slug)`: condition on the StyleSeed → generate → adversarial reviewer anchored ONLY to the chapter ground-truth → advisory `style_fit` score → local-write; clean→`captured`, any unresolved error→`changes` via a new `_assert_review_clean` gate) + `Line.kind="llm"` opt-in wiring; needs mocked-LLM tests, an opt-in live smoke, and a **dedicated DEC-7 Codex pre-merge review** of the generation/compute/secret boundary. **(Update: D2 has since SHIPPED 2026-06-25, ff `f7d2be6..30e7bcc` — see the top banner. PHASE D COMPLETE.)**
>
> ---
>
> **▶▶▶▶▶▶▶▶▶ ✅ PHASE D1 (StyleSeed MOAT) BUILT subagent-driven TDD (10 tasks) + final opus review (READY-TO-MERGE, all 4 invariants HELD) + MERGED to `main` + PUSHED to `origin/main` 2026-06-25 (ff `df8c1ef..214597b`) — durable.**
> The deterministic, read-only half of Phase D (StyleSeed/DEC-8) is shipped. New PURE package **`samagra/factory/style/`**:
> - **`text.py`** — shared tokenizer + 4 frozen marker vocabularies shared across all 5 facets.
> - **`extract.py`** — 5 deterministic facets over the 59 `content.json` chapters: **voice** · **sequencing** · **analogy** · **rigor** (from the real `section.flags[]` — `kind_mix [clarified 0.77, corrected 0.13, note 0.10]`) · **selection**; plus `load_corpus`/`build_profile`.
> - **`profile.py`** — `StyleSeed` frozen dataclass + sha256 content/corpus hashing + versioned **git-committed JSON** (`styleseed/styleseed-v0.json`) + `extract_candidate` change-detect/version-bump.
> - **`condition.py`** — `to_system_prompt` = the conditioning interface the future LLM lanes prompt-cache against.
> - **`score.py`** — `style_fit` = the deterministic **advisory** scorer; structurally never auto-advances the gate (DEC-8 invariant, hard-coded).
> - **Config:** `STYLESEED_DIR = REPO_ROOT/styleseed`; **CLI:** `samagra factory style-extract | style-show`.
> - **v0 committed** (`styleseed/styleseed-v0.json`) — the real 59-chapter profile, proving the real `section.flags[]` are read.
> - **4 forks ruled at brainstorm:** F-D1=B (moat + a first live LLM lane, not moat-only); F-D2=Samadhan (misconception brief, `claude-opus-4-8`); F-D3=C (git-committed JSON moat, owner accepts public-repo exposure); F-D4=opt-in (samadhan excluded from default textbook fan-out).
> - **Invariants HELD (all 4):** no API key / no LLM (pure deterministic); no new prod write path (only `styleseed/*.json`; the 7 source subsystems stay read-only); DEC-8 advisory scorer never auto-advances the gate; no governance/`assignments` migration (`style_events` table is D2/D3). Publish gate untouched.
> - **Gate: 384 pytest** (360 → 384; +25 style tests across 6 suites; 383 passing — lone red = pre-existing env `test_gdocs`).
> - **Artifacts:** spec `docs/superpowers/specs/2026-06-24-samagra-content-factory-phase-d-design.md`; plan `docs/superpowers/plans/2026-06-25-samagra-content-factory-phase-d1-styleseed.md`; new code `samagra/factory/style/`; committed profile `styleseed/styleseed-v0.json`.
> - **▶ NEXT (at D1 time): Phase D2 — Samadhan live LLM lane:** `samagra/clients/llm_client.py` (the ONE Anthropic call site, `claude-opus-4-8`, key from gitignored `.env`, never logged); `samagra/factory/samadhan.py` (generate → adversarial-review → advisory `style_fit` score → local-write, behind `_assert_review_clean` at the guarded `build()` boundary); samadhan is **opt-in only** (F-D4 — excluded from default textbook fan-out); mocked-LLM tests + opt-in live smoke; **dedicated DEC-7 Codex pre-merge review** of the compute/secret boundary. (**Update:** **D3** — the `style_events` learning-loop scaffold + `factory style-mine/style-events/style-ratify/style-reject` — has since **SHIPPED 2026-06-25**, ff `b756cc2..a9ae176`; see the top banner. Phase D2 is now the only remaining Phase-D slice.)
>
> ---
>
> **▶▶▶▶▶▶▶▶ ⏸ PHASE D (StyleSeed, DEC-8) — SCOPED, then PAUSED by the Chairman (2026-06-24). No code shipped this session; HEAD stays at the Phase-C-complete `a19d382`.**
> The session opened **Phase D = StyleSeed** (the durable style MOAT, DEC-8) and grounded the design. Asked to choose
> the Phase-D scope — *moat-only (read-only)* vs *moat + a first live LLM generation lane* — the Chairman chose
> **"pause for now; keep the docs updated."** So Phase D is **deferred, not started**; this entry records the captured
> decision + grounding so resuming is frictionless.
> - **The captured gating fork (decide on resume):** **(A) moat-only** — ship the durable, versioned StyleSeed artifact
>   (a 5-facet *deterministic* extraction from the 59 `content.json` chapters: voice · sequencing · analogy ·
>   rigor-from-`flags[]` · selection priors), the conditioning interface a future LLM lane will read, a **deterministic
>   advisory style-fit scorer** (surfaces on the board, **never** auto-advances the gate), and owner-ratified
>   learning-loop scaffolding over `review_overlay`. NO API key, NO LLM call, NO new prod write path, deterministic
>   tests. Gate = owner review of v0 StyleSeed. Matches spec §4 exactly. **(B) moat + first LLM lane** — also a
>   synchronous net-new-prose lane calling an Anthropic model (`claude-*`) conditioned on the StyleSeed, behind the
>   mandatory adversarial reviewer + the never-automated publish gate; adds API-key handling in a PUBLIC repo
>   (gitignored `.env`/env var, never logged/committed), real per-call token cost, the LLM mocked in tests, and a
>   dedicated Codex pre-merge review of the new compute/secret boundary.
> - **Grounding done this session (so resume needs no re-discovery):** (1) **No prose-generation LLM client exists** in
>   `samagra` today — the `anthropic|openai|claude` hits are all non-generative (the `org.py` roster text, the Codex
>   *review* hook, a comment); Phase D is genuinely greenfield LLM territory. (2) The **dormant LLM seam exists**:
>   `samagra/lectures/thin.py` is deterministic but documented "swap this for an LLM summarization pass without
>   changing callers." (3) `review_overlay` lives in `samagra/governance/store.py` — the substrate for DEC-8's
>   owner-ratified learning loop. (4) **Storage fork still open** (spec §3.4/§7): StyleSeed as a file under
>   `state/style/` vs a `governance.db` table via the additive `_MIGRATIONS` hook — decide in the Phase-D plan. (5) Per
>   the spec's own phasing, the **heavy async LLM lanes (NotebookLM audio/slides, image-gen figures) are Phase F**, not D.
> - **DEC-8 invariants (unchanged, still binding once built):** StyleSeed is owner-curated + versioned + never reset;
>   style-fit scoring is **advisory only**, hard-wired never to auto-advance the gate; the learning loop (mine
>   `review_overlay` edit-diffs → profile-deltas) is **owner-ratified-only**; the single adversarial reviewer stays
>   anchored only to external ground-truth.
> - **Process when resumed:** the brainstorm context is grounded and the gating question was already asked; on a "go for
>   Phase D" the next steps are: lock scope (A vs B) → `writing-plans` → subagent-driven TDD → live golden-thread smoke →
>   adversarial multi-lens review → (if B) dedicated Codex pre-merge review → finish. Spec to extend:
>   `docs/superpowers/specs/2026-06-23-samagra-content-factory-design.md` §3.4/§4.
>
> ---
>
> **▶▶▶▶▶▶▶ ✅ CONTENT FACTORY PHASE C — SUB-SLICE C3 (the `seed`/mcd lane — the BRIDGE FOLD) BUILT TDD + ADVERSARIAL-REVIEWED + DEC-7-CODEX-PRE-MERGE-REVIEWED + MERGED to `main` + PUSHED to `origin/main` (2026-06-24). PHASE C COMPLETE.**
> The last of Phase C's three ratified sub-slices — and the one prod-write slice — is shipped. The munshi→mcd write
> **folds into the factory** as the canonical **`seed` lane** (`Line.kind="mcd"`, source prefix `munshi:`).
> - **The write boundary:** new PURE **`samagra/factory/seed_payload.py`** is the relocated canonical home for
>   `SEED_TYPES` / `build_seed_payload` / `validate_seed_payload` (`bridge/seed_payload.py` is now a re-export shim).
>   **`dispatch.run_seed(payload)`** is the ONE prod write: `validate_seed_payload` → `McdClient.create_seed` → assert a
>   seed id → return `artifact_ref="mcd:<seed_id>"`. `dispatch.run_line` **refuses** `kind=="mcd"` (defense in depth —
>   the mcd path never renders a slug).
> - **`factory.run`** grows **`scan()`** (the folded `bridge.scan` — proposes the seed lane for every content-classified
>   munshi item, read-only, never writes a seed), **`plan("munshi:<id>")`** (single-item proposal), and a **`build()`
>   mcd branch**: load the proposed payload from the assignment's `product_proposed` note + `validate_seed_payload`
>   **BEFORE** recording the `product_building` intent (**anti-wedge** — a structurally-bad payload refuses cleanly,
>   leaving the assignment `approved`/retryable, never wedged in-flight), then `run_seed`, `product_created`
>   (`subsystem_ref`=the seed id), flip → terminal `captured`. **`build()`'s five crash-safety guards are written ONCE
>   and shared across every lane kind** — only the produce/validate step branches.
> - **classify:** `munshi:<id>` → `[seed]`; **textbook still → `[revision, lecture, deck, paper, drill]`** (the seed lane
>   is excluded by its `munshi:` prefix — a chapter is NEVER written to mcd).
> - **F-C2 bridge fold (one path):** `samagra bridge {scan,approve,submit}` are now thin **deprecating delegators** (a
>   one-line stderr notice + forward to the factory; `submit → factory.build`). The bridge's own `create_seed` write is
>   **RETIRED** ⇒ the factory `seed` lane is the **only assignment-driven mcd writer**. (Precise nuance, confirmed by the
>   review: the pre-existing **DEC-3 owner-capture web endpoint** `POST /api/mcd/seeds` remains the separate sanctioned
>   human-UI capture path, untouched by C3 — so F-C2's "one path" means one *agent/CLI* path.) New CLI verb
>   **`samagra factory scan`**.
> - **Golden thread PROVEN LIVE** (`scripts/c3_smoke.py`, isolated temp governance store; REAL munshi + REAL mcd):
>   `factory scan` found 11 real content proposals → built **`munshi:52` → real seed `seed_01KVWDS8NTEV1C0NVN7T6EN79W`**,
>   captured, exactly one `product_created`; durable `governance.db` untouched.
> - **Adversarial final review (10-agent Workflow, 4 lenses — prod-write-safety / firewall-one-path / migration-regression
>   / correctness-edge — each finding independently verified; run `wf_eeac9f1a-4e6`):** 6 raw → **1 confirmed (MEDIUM),
>   5 refuted.** The MEDIUM: `cmd_bridge`'s scan CLI print still used the OLD bridge proposal shape `p['item']['uid']`,
>   but the folded `factory.scan` returns `seed_ref` — so `samagra bridge scan` would `KeyError: 'item'` on any real
>   proposal (masked because the CLI tests returned `[]`) → **FIXED** (`p['seed_ref']`) + a regression test with a
>   realistic proposal. The 5 refuted included the web-endpoint "second caller" (the sanctioned DEC-3 path — not a defect)
>   and legacy `mycontentdev` assignments now being firewall-refused (a SAFE fail — see note below).
> - **DEC-7 dedicated Codex pre-merge review** (`docs/codex-reviews/26-factory-phase-c3-seed-fold-premerge.report.md`) =
>   **GO-WITH-CAVEATS** (0 HIGH, 0 MEDIUM, 1 LOW). The boundary passed all 9 invariant checks. LOW **F1**:
>   `_load_proposed_payload` could surface a downstream `AttributeError` in `validate_seed_payload` on a note whose
>   `payload` value is a non-dict → **FIXED** (return the payload only if the note is a dict carrying a dict payload, else
>   `None` → a clean refusal) + a 6-case parametrized regression → **effectively GO**.
> - **Invariants HELD:** exactly one (assignment-driven) mcd write path; no double-write / in-flight-safe / no-write-without-approve;
>   `validate_seed_payload` gates every write; no textbook→mcd; **NO new prod write *mechanism*** (the existing `create_seed`
>   capture contract) · **NO migration** (reuses `assignments` cols + `product_*` verbs) · publish gate untouched ·
>   read-only firewall intact · no secrets.
> - **Gate: 360 pytest** (341 → 360; lone red = the pre-existing environmental `test_gdocs`, Google API libs missing —
>   factory-independent).
> - ⚠ **OWNER FOLLOW-UPS:** (1) **archive the prod test seed `seed_01KVWDS8NTEV1C0NVN7T6EN79W`** (from `munshi:52`, created
>   by the C3 live smoke) in the mycontentdev UI — joins the Phase-3 cleanup of `munshi:55`/its seed. (2) Any pre-C3
>   **non-terminal** legacy `pipeline="mycontentdev"` assignment in the durable `governance.db` is now firewall-refused by
>   the factory (a safe, deliberate fail — the one real such row is already terminal `captured`); reconcile any future one
>   by re-planning under the `seed` lane (`samagra factory scan` / `plan munshi:<id>`). No code change warranted.
> - **Artifacts:** spec `docs/superpowers/specs/2026-06-23-samagra-content-factory-phase-c-design.md` (§3.3/§5/§6); plan
>   `docs/superpowers/plans/2026-06-24-samagra-content-factory-phase-c3-seed-fold.md`; new code
>   `samagra/factory/seed_payload.py` + `dispatch.run_seed` + `factory.run` scan/plan/build mcd branch; bridge delegators
>   `samagra/bridge/run.py`; tests `tests/test_factory_seed.py` + `tests/test_factory_seed_payload.py`; smoke
>   `scripts/c3_smoke.py`; review `docs/codex-reviews/26-...`.

> **▶▶▶▶▶▶▶ ✅ CONTENT FACTORY PHASE C — SUB-SLICE C2 (the `paper` / Pariksha + `drill` / Abhyaas lanes) BUILT TDD + ADVERSARIAL-REVIEWED + MERGED to `main` + PUSHED to `origin/main` (2026-06-24, ff `78cf72a`).**
> The second of Phase C's three ratified sub-slices is shipped. New PURE engine **`samagra/factory/paper.py`** —
> `build_paper(slug, *, variant)` reads the **read-only** QX engine's `/api/qsearch` (question-only render: stem /
> options / passage / matrix, with KaTeX `data-tex` spans + figures — QX's search route NEVER renders `rj["answer"]`,
> so it is **answer-free by construction**) and assembles a printable, KaTeX-enabled **`paper`** (the full page of hits)
> or **`drill`** (the first `_DRILL_SIZE=8`, a focused subset), absolutizing asset URLs and writing
> `<slug>-<variant>.{json,html}` under `EXPORT_DIR`. **NO new prod write path** — QX is read-only and the only writes
> are local files (no gdocs/network at all). The **`Line.kind="qx"`** seam (added in C1) is consumed:
> `dispatch.run_line` routes `kind=="qx"` → the engine; **`classify("textbook:<slug>")` now fans to
> `[revision, lecture, deck, paper, drill]`** — **one chapter now produces FIVE captured local artifacts**. The real
> **`_assert_no_answer_leak`** guard is ACTIVATED for `kind=="qx"`: a defense-in-depth structural-marker scan over
> BOTH written artifacts (html + json) that refuses any answer/solution marker at the guarded `build()` boundary.
> **`build()` is unchanged** — the five crash-safety guards are identical for every kind.
> - **Answer-safety (the crown jewel):** the marker set anchors on **QX-specific class tokens** (`class="answer"`,
>   `answer-label`, `pq-ans`, `pkey`, …), never the bare word "answer" — so it is **false-positive-free** (a stem that
>   says "what is the answer to…" passes) yet catches all three of QX's answer renderers. **QX-down ⇒ `ValueError`
>   before any write** (clean refusal, no partial artifact — mirrors the bridge's munshi-down posture).
> - **Golden thread PROVEN LIVE against the live QX engine** (`scripts/c2_smoke.py`, isolated temp governance store):
>   `circular-motion` → **paper 25 questions + drill 8 questions**, both answer-free, both captured; durable
>   `governance.db` untouched.
> - **Adversarial final review (10-agent Workflow, 4 diverse lenses — correctness/safety/test-quality/spec-fidelity —
>   each finding independently verified; run `wf_3ffe75d5-cc1`):** 6 raw → **4 confirmed (0 HIGH, 1 MEDIUM, 3 LOW),
>   2 refuted.** The **MEDIUM** (the load-bearing catch the per-task TDD missed, exactly like C1's HIGH): the marker
>   set caught QX's `builder_pages`/`qx_browser` answer markup but **missed its THIRD answer renderer** — the teacher
>   `paper_render` (`<span class="pq-ans">Ans: …`, the `<div class="pkey">` answer-key appendix). A **latent**
>   defense-in-depth gap (no live leak — the search render is structurally answer-free — but the single most plausible
>   future regression is QX reusing that sibling renderer). **FIXED** — add `pq-ans`+`pkey` markers + scan the JSON
>   sidecar + regression test (proven false-positive-free against the real 25-question live paper). The 3 LOWs fixed
>   (scan json too; parametrize the leak/QX-down/clean e2e tests over `paper` AND `drill`; assert the drill cap reaches
>   the on-disk artifact). 2 findings **correctly refuted** (the escaping-bypass IS caught by the e2e leak test; the
>   off-by-one cap IS pinned by the `== _DRILL_SIZE` symbol assertion). **All six load-bearing invariants HELD.**
> - **Invariants:** **NO new prod write path**; **NO migration** (reuses `assignments` columns + `product_*` verbs);
>   publish gate untouched; read-only firewall over the 7 subsystems intact; no secrets.
> - **Gate: 341 pytest** (316 → 341; the lone red is the pre-existing environmental `test_gdocs`, Google API libs
>   missing on this host — factory-independent, fails on `main` too).
> - **Artifacts:** spec `docs/superpowers/specs/2026-06-23-samagra-content-factory-phase-c-design.md` (§3.2/§4); plan
>   `docs/superpowers/plans/2026-06-24-samagra-content-factory-phase-c2-paper-drill.md`; new code
>   `samagra/factory/paper.py` + `tests/test_factory_paper.py` + `scripts/c2_smoke.py`.
> - **▶ NEXT:** **C3** = the `seed`/mcd **bridge-fold** — the factory `seed` lane becomes the canonical munshi→mcd
>   write (`samagra bridge` deprecated/delegates, exactly ONE prod-write path), **prod write** behind a **dedicated
>   DEC-7 Codex pre-merge review** of the write boundary (mirroring bridge review 22). *(The last of the 3 sub-slices.)*
>
> ---
>
> **▶▶▶▶▶▶▶ ✅ CONTENT FACTORY PHASE C — SUB-SLICE C1 (the `deck` / Smriti flashcard lane) BUILT TDD + ADVERSARIAL-REVIEWED + MERGED to `main` (2026-06-24).**
> The first of Phase C's three ratified sub-slices is shipped. **MERGED to `main` (ff `6084952`)** — pushing to `origin/main`
> right after these tracker edits. New module **`samagra/factory/deck.py`** — a PURE, deterministic `build_deck(slug)` that
> projects a textbook chapter's equation + callout blocks into `{front, back, ref}` flashcards and writes `<slug>-deck.json`
> + a printable MathJax `<slug>-deck.html` under `EXPORT_DIR`. **Zero network/gdocs code** — the "no external write path"
> invariant is enforced **STRUCTURALLY** here (stronger than the lecture lane's opt-out flag). The `Line` dataclass gained a
> **`kind`** field (`local|qx|mcd`, default `local`) — the Phase-C lane-kind seam, consumed only by C2/C3; `dispatch.run_line`
> routes the deck lane to the engine; **`classify("textbook:<slug>")` now fans to `[revision, lecture, deck]`** — **one chapter
> now produces THREE captured local artifacts**. Built subagent-driven TDD (5 tasks, each two-stage reviewed) + an adversarial
> multi-lens final review.
> - **Golden thread PROVEN LIVE:** the real `circular-motion` chapter → **50 flashcards** (27 equation + 23 callout) + 3
>   distinct artifacts via the real factory loop, in an isolated temp governance store (durable `governance.db` untouched).
> - **Adversarial final review (9-agent, 4 diverse lenses, each finding independently verified):** caught **1 HIGH** the
>   per-task reviews missed — the deck injected equation LaTeX into the printable HTML **unescaped**, corrupting ~18
>   real-corpus formulas that contain `<`/`>`/`&` (e.g. gauss-law `E(r<R)=0`), because the browser tokenizer mistook `<R`
>   for a tag and MathJax never typeset it. **FIXED** (escape the equation back at the HTML boundary, keyed on card kind;
>   the deck JSON keeps the raw tex) + a regression test, proven on the real gauss-law deck (32 cards, zero bogus tags).
>   The other 4 findings were verified **false** (nits/low). The **SAFETY lens confirmed all six load-bearing invariants
>   HELD:** no new prod write path; read-only firewall over the 7 subsystems intact; never-automated publish gate untouched;
>   the 5 crash-safety guards intact; no migration; no secrets/content committed.
> - **Invariants:** **NO new prod write path**; **NO migration** (reuses the existing `assignments` columns + `product_*`
>   event verbs); publish gate untouched.
> - **Gate: 316 pytest passing** (303 → 316: +13 deck tests in `tests/test_factory_deck.py`); the lone red is the
>   pre-existing environmental `test_gdocs` (Google API libs missing on this host — factory-independent, fails on `main` too).
> - **Artifacts:** spec `docs/superpowers/specs/2026-06-23-samagra-content-factory-phase-c-design.md`; plan
>   `docs/superpowers/plans/2026-06-24-samagra-content-factory-phase-c1-deck.md`; new code `samagra/factory/deck.py` +
>   `tests/test_factory_deck.py`.
> - **▶ NEXT:** **C2** = the `paper`/`drill` lanes (QX-read, answer-safe, with the real `_assert_no_answer_leak` guard);
>   then **C3** = the `seed`/mcd bridge-fold (prod write, dedicated Codex review). *(Per the ratified 3-sub-slice packaging.)*
>
> ---
>
> **▶▶▶▶▶▶ ✅ CONTENT-FACTORY PIVOT — RATIFIED 2026-06-23 by Deepak (Chairman, carte blanche). NEW TOP DIRECTION;
> NOT YET BUILT.** SAMAGRA → an active, style-conditioned, **multi-output content factory** (physics): one seed →
> wide content-type coverage, in Deepak's style, behind the never-automated publish gate. **Reframe = activation,
> not teardown** — the 2026-06-19 spec already parked the machinery (A6 separate student entity · dormant
> DRAFTER+adversarial-REVIEWER · demand compass). **DEC-7** bridge → guarded **dispatch** boundary (1 seed → N
> child artifacts; extension that strengthens the firewall; Codex pre-merge review required); **DEC-8** durable
> **StyleSeed** + advisory scoring + owner-ratified learning loop; **DEC-9** **PRATHAM** student twin = A6 entity,
> DEFERRED. **4 forks:** (1) **dispatch spine first**, (2) PRATHAM deferred to Phase G, (3) publish gate = **per-seed
> batch** (`approve_seed`, never silent), (4) scope = **teaching leverage** (multi-seed from day one). **Preserved:**
> publish gate · 7-subsystem read-only firewall · 5 guards · DEC-1 bounded scope. **Plan A–G** (spine → deterministic
> lanes → StyleSeed → coverage graph → async → deferred PRATHAM). **✅ PHASE 1 (dispatch spine) BUILT TDD + MERGED to
> `main` + PUSHED to `origin/main` 2026-06-23** (ff `67a509c`; HEAD `0758cd6` — durable): `samagra/factory/` (`lines`·`dispatch`·`run`·`outbox`)
> + CLI **`samagra factory plan|approve|approve-seed|build`** — ONE textbook-chapter seed fans to 2 deterministic
> local-write lanes (`revision`=thin + `lecture`=thick) via the existing lecture renderer; guarded `build()` inherits
> the bridge's 5 crash-safety guards; per-seed batch gate (`approve-seed`, fork 3); 4-entry-point workflow firewall;
> **no new prod write path** (gdocs opt-out; local artifacts + governance ledger only), **no migration**. Golden
> thread **PROVEN LIVE** (`textbook:circular-motion` → 2 distinct CAPTURED artifacts via the real renderer; durable
> `governance.db` untouched). Built subagent-driven TDD (8 tasks, two-stage reviewed) per Phase-1 plan
> `docs/superpowers/plans/2026-06-23-samagra-content-factory-phase1-dispatch.md` + spec
> `docs/superpowers/specs/2026-06-23-samagra-content-factory-design.md`; vision `CONTENT-FACTORY-VISION.html`. **DEC-7
> Codex pre-merge review:** review 24 **NO-GO** (factory build could trigger the lecture exporter's external Google
> Docs upload) → remediated TDD (H1 gdocs opt-out · M1 factory outbox + firewall · L1 scoped event query · L2 seed_ref
> normalize · I1 guard-2 test) → re-review 25 **GO-WITH-CAVEATS** → the one new Low (`approve_seed` firewall) closed →
> effectively **GO**. Gate **303 pytest**. Reports `docs/codex-reviews/24,25`. **▶ NEXT: Phase C** (StyleSeed +
> further deterministic lanes per Plan A–G) — **sub-slice C1 (the `deck` lane) is now BUILT + MERGED (ff `6084952`,
> 2026-06-24); see the C1 banner at the very top.** **Owner follow-ups:** ✅ pushed to `origin/main` (`0758cd6`) — durable; optionally clean up
> any `board/` outbox demo files.
>
> ---
>
> **▶▶▶▶▶ ✅ PHASE 3 — ACTIVE LOOP (the bridge) BUILT TDD + GOLDEN THREAD PROVEN LIVE + MERGED to `main` (2026-06-23).**
> **MERGED to `main` (ff `88d31e0`) + PUSHED to `origin/main` (HEAD `1c5ec5d`) after the Codex pre-merge review — durable.**
> DEC-5's primary value engine is real: `samagra/bridge/`
> (`text` · `classify` · `pointers` · `seed_payload` · `outbox` · `run`) + CLI **`samagra bridge scan|approve|submit`**.
> The loop: munshi item → classify content/ops → propose a flat seed payload + corpus pointers → record an
> `in-review` board assignment (`governance.db`) + a pasteable outbox → **`approve`** (board gate) → **`submit`**
> (the ONE subsystem write — approval-gated, idempotent, terminal `captured`). Built per the reconciled
> spec/plan `docs/superpowers/{specs/2026-06-22-phase3-active-loop-design.md,plans/2026-06-22-phase3-active-loop.md}`.
> - **4 reconciliations vs the stale 2026-06-19 plan:** **R1** flat `{type,raw_text,source_ref}` (the worker drops a
>   nested `detail`; pointers live in the `seed_proposed` event note + the outbox file); **R2** real munshi
>   kind-specific text keys via `item_text` (not `payload["text"]`); **R3** idempotent terminal `submit` (+ additive
>   `captured` status); + the post-D6 **`store.connect()`** governance-DB fix (the original plan wrongly used
>   `catalog.connect()`).
> - **Gate: 272 pytest green** (263 build + 9 review-hardening). Subagent-driven build; every task two-stage reviewed;
>   final whole-impl review (opus) = **MERGE-READY, 0 Critical/High/Medium**; all 5 safety invariants confirmed (only
>   write path = `submit`; NO new web endpoint; read-only-except-capture intact; no secret leak; double-write blocked).
> - **Codex pre-merge review (the gate the prod write path requires) — DONE, reports `docs/codex-reviews/22,23`:**
>   review 22 returned **NO-GO** on prod double-write robustness (3 High, 2 Medium); all remediated TDD (+9 tests) —
>   **H3** scan now dedups against ANY prior assignment status-blind incl. terminal `captured` (an item is bridged
>   once); **H1** `submit` records a `seed_submitting` intent BEFORE the write so a crashed/in-flight retry **refuses**
>   (safe-fail, reconcile by `source_ref`) instead of double-writing; **M1** `validate_seed_payload` re-asserts the
>   `/api/mcd/seeds` type+non-empty-raw_text contract at the bridge write boundary; **M2** `scan` degrades on a munshi
>   read crash; **Low** left word-boundary classify (`work`↛`paperwork`) + full-`assignment_id` outbox guard. **H2**
>   (concurrent submit) accepted **Low** under the single-operator manual-CLI threat model (no bridge endpoint, no
>   scheduled scan), narrowed by the H1 guard. Re-review 23 = **GO-WITH-CAVEATS, all 6 resolved.**
> - **GOLDEN THREAD PROVEN LIVE:** a dry scan read live munshi (11 real content proposals); a synthesized **Testbot**
>   proposal went approve→submit→**real seed `seed_01KVRFPPT98HJVQ5NRBJ63MKR3` (rough_idea, captured)** in prod
>   mycontentdev, verified by read-back; a second submit was **refused** (idempotent — exactly one seed). *(A clean
>   Testbot **content** item can't be made via the capture API: `classify` routes all person-attached items to ops,
>   and todo needs an assignee / note needs a student / followup is ops — so the write half used a synthesized
>   Testbot proposal; scan/classify is proven on the 11 real items.)*
> - **⚠ Owner cleanup (prod test entities):** munshi note **55** + person "Testbot" (id 16); mcd seed
>   **`seed_01KVRFPPT98HJVQ5NRBJ63MKR3`**. The smoke's local audit trail is the `captured` governance row for
>   `munshi:55`; the 11 smoke in-review proposals were cleaned. (Outbox `.md` prompts are runtime artifacts — now
>   gitignored via `board/*/outbox/*.md`; a test-hygiene fix makes `scan` tests `chdir` to tmp so they never write
>   into the repo tree.)
> - **Known limitation (graceful, by spec):** pointers are usually empty for real verbose questions —
>   `catalog.search` uses FTS5 **AND** semantics, so a long stem rarely matches all tokens against one catalog title.
>   Best-effort provenance; the proposal + seed write are unaffected. Future: OR-union / salient-term pointer search.
> - **✅ PUSHED:** `main` → `origin/main` (`d980e6f..1c5ec5d`) 2026-06-23 with owner consent — the Phase 3 merge is
>   durable on the remote. Branch `phase3/active-loop` merged (ff `88d31e0`) and deleted; merged-result gate re-run
>   green (272 pytest).
> - **▶ NEXT (owner-only — needs munshi/mcd access; no sanctioned dismiss/archive write path in code):** prod
>   test-entity cleanup — dismiss munshi note **55** + person "Testbot" (id 16), archive mcd seed
>   **`seed_01KVRFPPT98HJVQ5NRBJ63MKR3`**.
>
> ---
>
> **▶▶▶▶ ✅ POST-AUDIT HARDENING SHIPPED (2026-06-22) — W1 security · W2 docs · W3 test-debt · W4 DEC-4 RETIRED.**
> The plan [`docs/superpowers/plans/2026-06-22-post-audit-hardening.md`](docs/superpowers/plans/2026-06-22-post-audit-hardening.md)
> is implemented, TDD throughout (red→green). **✅ Committed (`1cb345a`), fast-forward-merged to `main`, and
> pushed to `origin/main` (`23d6cf1`).** All additive /
> defence-in-depth; the live deploy and the read-only-except-owner-capture invariant are unchanged.
> **Ground truth now: backend 229 pytest + frontend 559 vitest, both green** (up from the audit's 154/546 — the
> hardening added the new tests below).
> - **W1.1 (the HIGH) — the origin now fails closed.** New `samagra/api/origin_auth.py` `http` middleware gates
>   the five mutating POSTs (`/api/refresh`, `/api/tick`, `/api/gate/*`, `/api/munshi/capture`, `/api/mcd/seeds`)
>   + the two admin-keyed live reads (`GET /api/munshi/library`, `GET /api/mcd/seeds`). **Loopback always passes**
>   (local dev + the `cloudflared`-origin path), so a remote request needs a verified Access identity: full
>   **RS256/JWKS** validation of `Cf-Access-Jwt-Assertion` when `SAMAGRA_ACCESS_AUD` + `SAMAGRA_ACCESS_TEAM_DOMAIN`
>   are set, else the documented **interim** `Cf-Access-Authenticated-User-Email == SAMAGRA_OWNER_EMAIL`;
>   `SAMAGRA_DISABLE_ORIGIN_AUTH` dev flag. Because cloudflared connects from loopback, this blocks *non-loopback*
>   direct exposure (a `0.0.0.0` bind / LAN / internet) — **Access stays the primary gate.** (20 new tests.)
> - **W1.2** QX HTML is sanitized before `dangerouslySetInnerHTML` (`frontend/src/lib/questions/sanitize.ts` —
>   strips `<script>`/iframe/`on*`/`javascript:`). **W1.3** `SAMAGRA_QX_SERVER_URL` is validated as
>   loopback/allowlist (`samagra/api/qx_guard.py`) — SSRF / asset-host guard; a poisoned URL degrades gracefully,
>   never an SSRF fetch. **W1.4** schema DDL moved off the GET hot-path (memoized `catalog.ensure_schema` /
>   `gstore.ensure_tables` + a startup lifespan; reads open SQLite **read-only**). **W1.5** `/open` now enforces an
>   extension allowlist + denies hidden/secret-named files; `.gitignore` adds `**/cloudflared/*.json`; the deploy
>   threat model enumerates all five POSTs + documents the origin gate.
> - **W2 doc-precision:** "two **subsystem** write paths" (STATUS/CLAUDE); the `/api/questions/facets` provenance
>   is corrected (the live chips come from the **`/api/questions` payload facets**, not that endpoint — which the
>   UI does not consume); counts refreshed; `mycontentdev` (not `mcd`) as the adapter key; seed-spec `detail?`
>   dropped (server never forwarded it); the MathJax(lectures) / KaTeX(questions) split noted; mcd capture now
>   **rejects non-string fields** (symmetric with munshi).
> - **W3 test-debt:** the lecture exporter (Pandoc `_html_to_docx` + `gdocs.upload`) and the notification channels
>   (`_telegram` / `_email`) are now covered; `samagra serve --reload` is **guarded** (D-1 orphaned-worker gotcha —
>   needs `SAMAGRA_ALLOW_RELOAD=1`); the `questiondb` stub now reports `available()=False` (0 artifacts —
>   operator-console honesty); the stale "via Hermes bot" docstring fixed.
> - **W4 — DEC-4 RETIRED (Chairman Deepak, option C; recorded as DEC-6 below).** The pre-E3 attention-ROI
>   acceptance gate is **formally retired, not deferred**; the DEC-2 north-star relaxes from *binding* to
>   *advisory*; **DEC-1 / DEC-3 / DEC-5 + the never-automated publish gate stay binding.** No doc now describes a
>   "binding gate" the project ships past.
> - **▶ NEXT:** ✅ committed + merged + **pushed to `origin/main` (`23d6cf1`)**. Optionally set
>   `SAMAGRA_ACCESS_AUD` + `SAMAGRA_ACCESS_TEAM_DOMAIN` in prod `.env` to upgrade the origin gate from the interim
>   email check to full JWT validation. Then **Phase 3** (DEC-5) — now ungated by DEC-4 — in the next session.
>   **`MUNSHI_API_URL` + `MUNSHI_SECRET` are ALREADY set in `.env`** (`MunshiClient.available()` and
>   `McdClient.available()` both `True`, verified 2026-06-22); just restart the durable `:8799` server if they were
>   added after it started, so the running process picks them up.
>
> ---
>
> **▶▶▶ ✅ OWED BROAD REVIEW DONE → NEXT SESSION: post-audit hardening + DEC-4 rescope (2026-06-22).**
> The broad multi-agent + Codex critical passes that were 529-blocked at deploy time are now **complete**: an
> 11-dimension adversarial Workflow (51 read-only agents, refute-by-default verification) **plus** an independent
> Codex `gpt-5.5` pass, both verdict **GO-WITH-CAVEATS — the docs are honest; the code does what it claims.**
> Reports: `docs/codex-reviews/{19-overall-critical-analysis,20-multiagent-doc-claim-audit,21-consolidated-critical-review}.md`.
> Ground truth at the audit HEAD `95a6270`: backend **154 pytest** + frontend **546 vitest**, green. *(The
> post-audit hardening session has since added tests — **current ground truth is 229 pytest / 559 vitest**, per
> the top banner. Older per-build counts like "152/541" below are historical build-moment snapshots, not current.)*
> - **The one HIGH (both reviewers):** the FastAPI origin does **not** fail closed — Cloudflare Access is the
>   *sole* gate over **five** unauthenticated mutating POSTs (`/api/refresh,tick,gate,munshi/capture,mcd/seeds`),
>   incl. `/api/gate/textbook/approve`. Contained today (loopback bind + Access) but zero defence-in-depth.
> - **MEDIUMs:** QX HTML via `dangerouslySetInnerHTML` (XSS); config-driven `SAMAGRA_QX_SERVER_URL` SSRF; GET
>   routes run schema DDL; `/open` serves any file under the broad source roots; deploy threat-model under-counts
>   the POSTs. **LOWs:** lecture-exporter + notifications untested; stale tracker counts; `mcd` vs `mycontentdev`
>   doc key; the SIM0xxx non-alpha filter sits on a dead endpoint (leak is still structurally gone).
> - **Governance:** DEC-4 attention-ROI gate was ratified "binding before E3" but E3 + the public deploy shipped
>   ahead of it (Phase 3 parked) — honestly documented as "deferred, not voided," but it's the GUI-first drift the
>   coherence audit flagged. **To decide next session: run it / rescope it / retire it (Chairman's call).**
> - **▶ NEXT SESSION PLAN (committed):** [`docs/superpowers/plans/2026-06-22-post-audit-hardening.md`](docs/superpowers/plans/2026-06-22-post-audit-hardening.md)
>   — W1 security hardening (origin fail-closed first), W2 doc-precision fixes, W3 test debt, W4 DEC-4 rescope
>   (options A/B/C, owner-gated). All additive/defence-in-depth; the live deploy + the read-only-except-capture
>   invariant stay as-is. No code changed this session (read-only audit).
>
> **▶▶▶ ✅ SAMAGRA OS DEPLOYED LIVE (2026-06-22).** The ralph ship-&-tunnel loop drove the app to fully working
> (Phase A: 17 apps × mobile × 3 themes, real data, 0 console errors, gates green) and **deployed it behind
> Cloudflare Access** at **https://samagra.bhautikiplusprashnavali.com** via a `cloudflared` named tunnel
> (`samagra-os`, `9b7a3df8…`) → local `:8799`. **Gate verified** (unauth `/api/overview` → HTTP 302 to the
> Access OTP login; the origin does not fail-closed, so Access is the sole gate). **Merged to `main`**
> (`5db7886`, fast-forward, pushed to `origin/main`; 20 commits) and **durable** via the `SAMAGRA-OS` logon
> Scheduled Task (`scripts/serve-durable.ps1` → stack + detached tunnel; survives session-close + reboot at
> logon). Evidence: [`…/ralph-deploy/BACKLOG.md`](docs/superpowers/loops/ralph-deploy/BACKLOG.md)
> (Phase A A1–A8 ✓; Phase B B1–B5 ✓; Phase C C1–C2 ✓); as-shipped runbook
> [`docs/deploy-tunnel.md`](docs/deploy-tunnel.md).
> - **Owner follow-ups (open):** (1) **delete junk DNS record**
>   `samagra.pratyakshsims.com.bhautikiplusprashnavali.com` (D-8 — harmless, in the CF dashboard); (2) **browser
>   smoke** — OTP-login then walk apps × devices × themes over TLS; (3) **owed reviews** — the broad
>   multi-agent + Codex critical passes were 529-blocked (Anthropic capacity) and remain owed.
> - **Hostname is `bhautiki`, not `pratyakshsims`** — the `cloudflared` `cert.pem` is zone-scoped to
>   `bhautikiplusprashnavali.com` (D-7); using pratyakshsims would need a browser `cloudflared tunnel login`.
> - **Owed reviews:** a pre-deploy crown-jewel **security** review (inline) found **no CRITICAL/HIGH**, but the
>   broad multi-agent + independent **Codex** passes were **529-blocked** (Anthropic capacity event) and remain owed.
> - **DEC-4** attention-ROI gate stays ASSUMED-UNBLOCKED for this work (deferred, not voided); DEC-1/DEC-3 + the
>   never-automated publish gate still hold. Loop prompt/backlog under `docs/superpowers/loops/ralph-deploy/`.
>
> **▶▶ Phase E3 (mobile + visual polish) BUILT + the carried test-only LOWs CLOSED (2026-06-22).**
> On branch **`e3/samagra-os`** (3 commits: `0dceb0d` test-LOWs · `73a97b7` E3 · `82edd06` review fixes; **NOT
> merged**). **⚠ DEC-4 was consciously deferred by the Chairman for this session** — the owner explicitly chose
> "proceed with E3 now" rather than run the attention-ROI acceptance gate first. **DEC-4 is NOT satisfied; it
> remains the binding gate for the Phase-3-vs-GUI reprioritization decision** (see *Direction-coherence DECISION*
> below — the gate is deferred, not voided).
> - **Test-only LOW cleanup (HANDOFF item 4, now done):** S4 — parametrized QX-facets degradation tests
>   (`available()→False`, `summary()→None`/`{}`/`{subjects:{}}` → `{"subjects":[]}`); S3 LOW-3 — sims parser
>   robustness (h2/h3 disambiguation, trailing `(NN)` strip, internal em-dash title, leading-italics/blank lines);
>   S3 LOW-2 — `sims_manifest.sim_url()` now **raises** on a non-`^\d{1,4}$` id (was silent zero-pad) + a lock that
>   `_ITEM` drops 5-digit ids; S3 LOW-4 — the Sims chip-removal assertion is now non-vacuous (`subject-chip` count 0).
> - **E3 (client-only, proto.md §1.4/§1.11/§7):** **(a) mobile device mode** — theme store gains
>   `mobileApp` + `openMobileApp`/`goHome` (`setDevice` resets it); new **`frontend/src/shell/Mobile.tsx`** phone
>   frame (392×812 bezel · notch · 44px status bar · 4-col app grid over `ORDER` · favorites dock over
>   `MOBILE_FAVORITES` · home-indicator-as-Home); **`App.tsx` branches on `device`**, swapping the desktop
>   windowing shell for the phone (keeping the `--samagra-*` vars). **(b) theme-correct WM geometry** —
>   `windowManager` now tracks the active theme (`reclampForTheme` adopts it) so openApp/move/maximize/tile use
>   that theme's `workArea`+`barH` instead of always aqua (fixes console/samagra windows). **(c) responsive
>   Dashboard** — the lower Pipelines/Board grid is now `repeat(auto-fit,minmax(260px,1fr))` (was fixed
>   `1.4fr 1fr`), stacking on narrow/phone widths (HIGH#2).
> - **Terminal `open <app>` is now device-aware** (the single in-app `openApp` caller): on a phone it routes to
>   `openMobileApp` so it shows full-screen, not an invisible desktop window (review fidelity fix).
> - **TDD throughout + an adversarial multi-agent review** (4 dimensions, every finding independently verified):
>   6 raw findings → **3 confirmed, all fixed** (the MEDIUM Terminal device-awareness + 2 LOW test-quality), 3
>   correctly dismissed. **Gate green + stable:** backend **152 pytest**; frontend lint + `tsc` + **541 vitest /
>   61 files** + `vite build`.
> - **Real-browser smoke verified** (Vite dev): phone frame, 17-app grid, favorites dock, open-app→Home
>   round-trip, responsive Dashboard stacking, **zero console errors**. **Pixel/interaction parity remains the
>   separate owner browser-vision pass** (RUBRIC §6) — not run, not claimed.
> - **▶ NEXT:** present `superpowers:finishing-a-development-branch` and merge `e3/samagra-os` (it sits on top of
>   the QX-backed Questions + capture work). **Still owed before deeper GUI investment: the DEC-4 attention-ROI
>   gate** (owner-run) and the browser-vision pixel pass.
>
> **▶▶ Questions app is now QX-backed (2026-06-22).** The Questions app was a thin `LIKE`
> slice over QX's sqlite (raw `$…$` LaTeX, literal `[fig]`, no semantic). It now **reuses the real QX
> engine** as a localhost sidecar (owner decision — "deploy QX on localhost and use its backend
> directly"). QX gained a tested `GET /api/qsearch` route (`tools/qx/json_search.py`) wrapping
> `tools.qx.search.run_search` (exact **+ semantic** + facets) and rendering each question to standalone
> HTML (KaTeX `data-tex` spans + figure `<img>`) via QX's own `render_html.render_segs`. SAMAGRA's
> `/api/questions` **proxies** it (`samagra/clients/qx_client.py` → `config.QX_SERVER_URL`, default
> `http://127.0.0.1:8783`; `samagra/questions_proxy.py` absolutizes figure `/asset` URLs to the QX
> server; QX-down → graceful `{results:[], error}`, never a 500). The **Questions app**
> (`frontend/src/apps/Questions/index.tsx`) got a search box + **exact/semantic toggle** +
> subject/chapter/qtype **facet chips** + **KaTeX** typesetting (equation-image fallback) + a degraded
> note. **The two carried review LOWs are also fixed: F1** (Munshi/mcd render `data?.error`) and **S3
> LOW-1** (`sims_manifest` resets `subject` per `##` grade).
> - **TDD throughout:** backend **142 pytest** + frontend **524 vitest** + `npm run verify` green; QX
>   `tools/qx/tests/test_json_search.py` **5** + browser/search/semantic suites green (no regressions).
> - **LIVE-VERIFIED end-to-end** through the running QX `:8783`: exact (**180** results, KaTeX spans,
>   figures as **absolute** QX URLs, facets = real subjects, no SIM-ids) and **real semantic** (mode
>   `semantic`, `degraded False`, **67,276** over the 67k-vector BGE index).
> - **Commits:** `e5457ea` (LOWs) + `88b50a0` (QX-backed) on `feature/control-plane-capture`.
> - **⚙ ACTIVATION (durable):** the always-up QX server **must run the new code** — restarted this
>   session (`python -X utf8 gui/qx_browser.py` on `:8783`). New frontend dep **`katex`** (run
>   `npm install` in `frontend/`). **The 3 QX-repo files (`tools/qx/json_search.py`, its test,
>   `gui/qx_browser.py`) are STAGED in the QX repo but NOT committed** (they sit amid other in-flight QX
>   work) — commit them in QX's own flow.
> - **▶ Contract change:** `GET /api/questions` now returns the QX payload —
>   `{results:[{q_uid,slug,q_type,subject,chapter,difficulty,snippet,html}], total, page, page_size,
>   mode, degraded, facets}` with params `q/mode/subject/chapter/qtype/page` (the old `limit` + flat
>   `text` row are gone). `/api/questions/facets` is **unchanged** (still question-scoped subjects).
>
> **▶▶ Capture control plane is LIVE (2026-06-21).** The SAMAGRA OS now does **real
> owner-initiated captures end-to-end** and browses every read-only surface with live data, on branch
> **`feature/control-plane-capture`** (not yet merged). Built TDD + an **independent Codex review per
> implementation** (reports `docs/codex-reviews/14–17`).
> - **Munshi capture (write):** `POST /api/munshi/capture` → live `MunshiClient.create_item` →
>   `POST {MUNSHI_API_URL}/api/item` (cookie auth). Kinds **todo/note/followup** only (the worker's
>   deterministic set), per-kind required fields, server-validated, creds-gated.
> - **mycontentdev seed capture (write):** `POST /api/mcd/seeds` → live `McdClient.create_seed` →
>   `POST {apiUrl}/api/seeds` **form-encoded**, `x-mcd-admin: <adminKey>` (the existing read key
>   authorizes the write — verified; **no `APP_PASSWORD` needed**).
> - **Live-read passthroughs** `GET /api/munshi/library` + `GET /api/mcd/seeds` — the capture apps read
>   the **live deployed workers** (not the catalog), so real data shows without a refresh and a fresh
>   capture appears on refetch. (`/api/search?source=munshi|mycontentdev` was catalog-backed → empty.)
> - **Simulations = deployed-only:** `GET /api/sims` parses `pratyaksh-May-deploy/deployed-sims-by-grade.md`
>   (**482 sims**), grade-grouped, linking the canonical extensionless `pratyakshsims.com/sims/SIM<NNNN>/SIM<NNNN>_sim`.
> - **QX browser fixed + separate:** `GET /api/questions/facets` is question-scoped (`qx.summary()`),
>   the SIM-id chip bug is gone, and degenerate numeric subject codes are filtered (clean chips). The
>   Questions app stays a standalone read-only browser (50 live QX rows, real q-type chips).
> - **LIVE-VERIFIED this session:** captured a real Munshi todo (`item_id 53`, library 13→14) and a real
>   mcd seed (`seed_01KVNN90…`, status `captured`, seeds 1→2) through the running server; both appear in
>   the live-read apps. Negative guards (bad kind / empty text) → 400. Backend **134 pytest** + frontend
>   **514 vitest / 60 files** green; advisory gate clean. Two benign labelled smoke records remain in
>   prod (owner can dismiss/archive).
> - **Final integrated Codex review (`docs/codex-reviews/18-capture-final.report.md`): GO-WITH-FIXES** — 0
>   CRITICAL / 0 HIGH / 0 MEDIUM; confirmed no secret/exception-text leak, `asdict`↔`SearchResult` contract
>   match, QX filter safe, write paths unchanged. Branch is **merge-safe**.
> - **▶ DECISION (owner, Option B): do NOT merge yet** — carry the small review LOWs into the next session
>   with the Questions work, then merge.
>
> **▶▶ NEXT SESSION — on branch `feature/control-plane-capture`, then merge (PR):**
> 1. ~~**Questions narrow fix (owner-requested):** raw LaTeX + literal `[fig]` + no semantic.~~ **✅ DONE
>    (2026-06-22, `88b50a0`)** — the Questions app is now QX-backed: real exact **+ semantic** search,
>    KaTeX maths, inline figures, facet chips (see the LATEST banner above). Approach upgraded from
>    "thin wrapper" to **reuse the real QX engine via a localhost sidecar** (owner decision); QX gained a
>    `GET /api/qsearch` JSON route; SAMAGRA proxies it.
> 2. ~~**F1 (review LOW):** Munshi/mcd misleading creds empty-state on a 200-body read error.~~ **✅ DONE
>    (`e5457ea`)** — type as `SearchResponse & {error?}` + render `data?.error`.
> 3. ~~**S3 LOW-1 (review LOW):** cross-grade subject bleed in `sims_manifest`.~~ **✅ DONE (`e5457ea`)** —
>    reset `subject = None` on each `##` grade.
> 4. **Optional test-coverage cleanup (still open, test-only):** QX facets degradation-branch tests
>    (S4 LOW); sims parser robustness + non-vacuous chip-removal assertion (S3 LOW-2/3/4).
> 5. **Merge:** present `superpowers:finishing-a-development-branch` options and open the PR for the whole
>    `feature/control-plane-capture` branch (capture control plane + Questions QX-backed + the LOWs).
>    **Before merge, also commit the 3 staged QX-repo files** in the QX repo (see ⚙ ACTIVATION above).
>
> **✅ DEC-3 AMENDMENT (2026-06-21, Chairman Deepak).** The morning's DEC-3 read-only firewall is amended:
> **owner-initiated capture** (a munshi item + an mcd seed) is now **in-scope** — the project's only two
> subsystem write paths. **Still binding & unchanged:** the human publish gate is **never automated**;
> **no automated munshi→mcd bridge** (promotion is a later explicit Chairman action); no app-platform
> scope (DEC-1); attention-ROI north-star + kill-criterion (DEC-2) + the pre-E3 gate (DEC-4) hold;
> Phase-3's full active loop stays parked (DEC-5). **New invariant wording: "read-only *except
> owner-initiated capture*."** Spec/plan: `docs/superpowers/{specs/2026-06-21-samagra-control-plane-capture-design.md,plans/2026-06-21-samagra-control-plane-capture.md}`.
>
> **▶ STATUS:** The project is **SAMAGRA** (package `samagra`) — a company-structured agent org
> folding in `mycontentdev` + `munshi`, with an advisory pre-commit Codex review and a CEO prompt-outbox.
> **Phase 0 (rename), Track A (stabilize) and Phase 1 (read-only subsystem adapters) are merged to `main`
> and pushed to `origin/main`.** **Phase 2 (governance) is now BUILT TDD on `main` (suite 63 → 98 green)**,
> reconciled to the runbook: **D6** (governance state lives in its own durable `governance.db`, separate from
> the rebuildable catalog `samagra.db`) and **D5** (the Codex pre-commit hook is **advisory-local** —
> confirmed-CRITICAL only, diff-hash cached, audited break-glass, never wedges; real enforcement = CI). The
> plan's Phase-2 code was stale (it self-flagged `SUPERSEDED by D5/D9`) and was reconciled before building.
> The live plan is under `docs/superpowers/` (original brief: [`SAMAGRA-HANDOFF.md`](SAMAGRA-HANDOFF.md)).
> **Pre-merge review: APPROVE** (Codex gpt-5.5/xhigh, 6 rounds + a CEO adversarial Workflow audit — see
> `docs/codex-reviews/07–13` + `12-workflow-invariant-audit.md`; all findings fixed TDD).
> **Phase 2 SHIPPED (2026-06-19):** `origin/main` holds Phase 2 through `da9cab3` (the end-of-session doc-sync
> commits after it are local-ahead until the next `git push origin main`); the advisory
> hook is ACTIVE (`core.hooksPath=.githooks`, so every commit + worktree now runs it — `codex` 0.140.0 on PATH);
> the three agent worktrees exist (`../samagra-{deepak,khanak,codex}` on `agent/{deepak,khanak,codex}`).
> **▶ NEW TOP PRIORITY (2026-06-20): SAMAGRA OS — the Experience track.** Replace the plain tabbed portal with
> an OS-style windowing GUI (17 apps · 3 themes · 2 device modes) in React + TypeScript + Vite, served by
> FastAPI. Own spec + phased plan + agent division + two autonomous loop scripts under `docs/superpowers/`
> (spec `specs/2026-06-20-samagra-os-experience-design.md`; plan `plans/2026-06-20-samagra-os.md`; division
> `plans/2026-06-20-samagra-os-division.md`; loops `loops/{deepak,khanak}-loop.js` + `RUBRIC.md`).
> **E1 (shell + ALL 3 themes + OS utilities) is BUILT, fidelity-passed, and MERGED to `main` (2026-06-20,
> `06d88a3`, fast-forward; 96 files / ~19k insertions).** On top of the fidelity layer the main session added
> draggable/resizable windows, the advisory HIGH#4 theme-index guard, Notes to-do keyboard a11y, and the
> owner's two asks: the **chairman renamed Devesh → Deepak Bhardwaj** (Dashboard greeting, terminal prompt
> `deepak@samagra:~$`, board + `whoami`) and **right-click context menus for all 3 themes** (desktop · window ·
> dock-icon; theme-driven surface, verified live in aqua/console/samagra). **PUSHED to `origin/main` 2026-06-21
> (`557e6a4..6d09693`, incl. the tracker doc-sync).**
> **▶ E2 (data/control apps) is now MERGED to `main` (fast-forward, `31aa5bb`) and pushed to `origin/main` on
> 2026-06-21.** The **eleven data/control
> apps** shipped as thin, **read-only** React wrappers over the existing FastAPI `/api/*` contract, plus the one
> new backend endpoint **`GET /api/org`** (static `samagra/org.py`). Apps: **Org Chart · Pipelines · Lectures ·
> mycontentdev · Munshi** (owner claude-deepak) and **Assignments (kanban) · Activity · Questions · Booklets ·
> INSP/Olympiad · Simulations** (owner claude-khanak). No new write paths; mcd/munshi render empty-or-unavailable
> states; Munshi capture/write is OUT of scope. All real logic lives in **seven pure-TS linchpin modules**
> (`lib/api/query` · `lib/catalog/rows` · `lib/pipelines/stages` · `lib/org/resolve` · `lib/kanban/columns` ·
> `lib/activity/format` · `lib/questions/facets`); the 11 app components are thin wrappers over these + `useApi`.
> Built TDD on branch **`e2/samagra-os`** as a single-tree DAG driven by two background Workflows (backend + 7
> linchpin modules, then the 11 app wrappers) with phase-boundary review — **22 commits**. A live-source
> verification workflow produced `docs/superpowers/_research/samagra-os/e2-grounding.md` — the verified `/api`
> contract, which **SUPERSEDES the stale `api.md`** (it caught 11 deltas: dual `meta_json`/`summary_json` keys,
> two empty-question bodies, hyphenated `in-review` status, a name-keyed `phases` Record, 7 owner ids, the
> chairman name living only in `dispatch.ts`, etc.). The dedicated plan
> `plans/2026-06-21-samagra-os-e2.md` cleared a **4-critic adversarial pass** (0 CRITICAL / 0 MAJOR; 6 minor
> polish fixes applied).
> **E2 test gate (just-run): BACKEND 106 pytest passing** (102 E1 + 4 new `tests/test_api_org.py`); **FRONTEND
> 501 vitest passing across 56 files** (497 at the E2 merge; the +4 are the post-merge `e1cb22a` Questions `/api/facets` tests) (439 E1 + 25 new lib tests incl. the catalog href/safeUrl tests + 33 app
> render-smoke), `tsc --noEmit` clean, `vite build` green emitting **22 lazy chunks** (one per app), no
> `.only`/`.skip`. **A Codex pre-merge review returned GO and three MEDIUM findings were fixed (commit
> `31aa5bb`):** **(a)** `org.py`'s worker roster shows "Gemini+NotebookLM" as ONE line (the owners map keeps the
> two tokens distinct); **(b)** the Pipelines app humanizes pipeline owner tokens via `GET /api/org` + `ownerName`;
> **(c)** `lib/catalog/rows` exposes a unified, scheme-guarded `href` so url-only mycontentdev/munshi rows are
> actionable. **Also reconciled during review:** `org.py` owner mapping is OWNER-CONFIRMED — `claude1` =
> **Claude-Deepak** (CEO — substrate & engine), `claude2` = **Claude-Khanak** (CTO — leaf apps & UX) — locked by
> `tests/test_api_org.py`; and a **pre-existing E1 production-serve bundling bug** — `App.tsx`'s
> `/* @vite-ignore */` dynamic import left every `apps/*/index.tsx` OUT of the production bundle, so FastAPI-served
> app windows rendered empty (only `npm run dev` worked) — was fixed by dropping `@vite-ignore` so Vite emits a
> lazy chunk per app (22 chunks); this affected all 17 apps in production, now fixed.
> **E2 status right now:** **MERGED to `main` (fast-forward, `31aa5bb`) and pushed to `origin/main` on 2026-06-21**
> after the Codex pre-merge review (GO; 3 MEDIUMs fixed) — see the merged PR
> <https://github.com/dbhardwaj86/samagra/pull/2>. **Pixel/interaction parity of the 11 apps is a
> separate owner-run browser-vision pass — NOT yet run, NOT claimed** (some E2 glyphs may still be unregistered
> in `components/icons-data` → empty-icon fallback; a visual-polish follow-up). **Next planned action: the
> owner-run browser-vision pixel-QA pass over the 11 E2 apps (now that the bundling fix makes them render when
> FastAPI-served, not just under `npm run dev`), then Phase E3 (mobile device mode + remaining per-theme re-skin
> polish — the 3 themes already shipped in E1).** The E2 LOW follow-up — the Questions app consuming
> `/api/facets` — was IMPLEMENTED this session (commit `e1cb22a`, pushed to `origin/main`) but **introduced a
> known bug; see ⚠ KNOWN BUG below.**
> The full `frontend/` app (React 18 + TS + Vite) shipped TDD across E1.1–E1.25: the bootstrap + frozen
> 17-app registry, every pure `lib/` engine (`wm/{geometry,zorder}`, `snake/{engine,cell}`,
> `clock/{analog,stopwatch,timer,world}`, `terminal/{parser,dispatch}`, `notes/model`, `persistence`), the
> `windowManager`/`theme` Zustand stores (thin over `lib/`), the aqua chrome shell (top bar · dock · window
> frame · context menu), the six OS-utility apps (Dashboard · Settings · Terminal · Clock · Notes · Snake) +
> shared leaf components, and the FastAPI serve seam (Vite `dist/` + SPA fallback, jinja portal route retired).
> **Fidelity layer (2026-06-20):** theme-driven chrome for all three themes — **aqua** (top bar + bottom-centre
> Dock + left traffic-lights), **console** (no top bar; bottom Taskbar + Start menu + right-side neon icon
> controls), **samagra** (Devanagari top strip + left **Rail** dock + warm window frame) — every colour/size
> driven by the `themes/` token map (**FD1**), plus the `Icon`/`AppIcon` SVG components (**FD2**) wired through
> every dock/rail/Start launcher and the six apps (no letter badges anywhere). The RTL suite was adapted to the
> new markup and pins the fidelity hooks: per-launcher inline `<svg>`, control aria-labels
> (Close/Minimize/Maximize), exact traffic-light token colours (`#ff5f57` live / `#cdcdd4` inactive), the 28×23
> right-side control geometry, the Devanagari wordmarks, and the full theme swap exercised through the real
> stores.
> **E1-merge gate (2026-06-20): `npm run verify` clean — lint + `tsc --noEmit` + 439 Vitest tests across
> 38 files + `vite build` writing `dist/`, no `.only`/`.skip` in the diff — and the backend `pytest` suite at
> 102/102 green (incl. `test_serve_seam.py`).** Linchpin held: all real behaviour lives in pure-TS
> headless-testable modules; **pixel/interaction fidelity is a separate browser-vision QA pass** (owner-run,
> never a loop completion signal) — **it has NOT run; pixel parity is NOT claimed.** The headless gate proves
> the markup, tokens and icon wiring are correct, not that the rendered pixels match the screenshots.
> **Next steps:** the **owner-run browser-vision pixel-QA pass over the 11 E2 apps** (now that the bundling fix
> makes them render when FastAPI-served, not just under `npm run dev`), then **E3** (mobile device mode + remaining
> per-theme re-skin polish + the deferred Dashboard narrow-grid HIGH#2). The **browser-vision pixel pass**
> (owner-run, per-surface vs the prototype + `screenshots/`) — now spanning the E1 shell + the 11 E2 apps —
> remains outstanding.
> **Phase 3 (active loop) is PARKED** (plan complete, resumes after the Experience track; will need live
> `MUNSHI_API_URL`/`MUNSHI_SECRET` in `.env`). Carried into Phase 3: F1/F4 refresh hardening.
>
> **✅ RESOLVED (2026-06-22, `88b50a0`):** the Questions app no longer derives chips from catalog-wide
> facets at all — it now renders **filter-scoped facets straight from the QX engine** (`/api/qsearch`
> → `search.facet_counts`: subject/chapter/qtype), so the `SIM0xxx` leak is structurally impossible.
> The original bug write-up is retained below for history.
>
> **⚠ KNOWN BUG (RESOLVED — see above): Questions app subject chips show sim-ids, not subjects.**
> The Questions app (`frontend/src/apps/Questions/index.tsx`) renders its subject filter chips from
> `GET /api/facets`, whose `subjects` is **catalog-wide** (`select distinct subject from catalog`,
> `samagra/catalog.py:191`). The sims adapter writes each simulation's folder id (`SIM0018`…`SIM0626`) into the
> `subject` column (`samagra/adapters/sims.py:37`, `subject = after[0]`), so **~500 `SIM0xxx` ids dominate the
> chip list** (498 measured against `samagra.db` — 502 of 504 distinct catalog subjects come from the sims source). Global catalog facets ≠ the question bank's subject vocabulary;
> clicking a `SIM0xxx` chip filters `/api/questions?subject=SIM0xxx` → 0 QX rows. Compounded by QX's own
> `subject` column being physics-only/unpopulated (see Gotchas). **Introduced this session by the E2 LOW-finding
> fix `e1cb22a`** (already merged + pushed to `origin/main`). **Fix options (next session — keep it read-only,
> tests + `npm run verify` green):** (a) source the chips from a **question-scoped** subject list — QX
> `summary().subjects` (`samagra/adapters/qx.py:57`) via a new `/api/questions/facets` or the existing qx
> overview summary; (b) intersect `facets.subjects` with the subjects actually present in the returned
> questions; or (c) drop subject chips and facet on chapter/q_type per the Gotcha. **Deeper cause (audit 2026-06-21):**
> the `subject` column has *uneven semantics across adapters* — sims writes a folder id (`sims.py:37`),
> mcd/munshi hardcode `physics`, qx derives from the builder DB — so a catalog-wide `DISTINCT subject`
> (`catalog.py:199`) can never equal the question bank's subject vocabulary; the durable read-only fix is
> question-scoped facets (`qx.summary().subjects`), not catalog-wide facets.

## ✅ Direction-coherence DECISION (RATIFIED 2026-06-21 by Deepak, Founder & Chairman)

A dedicated coherence audit this session — an independent **Codex vision review** plus a **multi-agent
implementation audit** (4 mappers + 4 verifiers, live test runs) — found **execution coherence strong but
strategic direction drifting.** Execution verified clean: every merge claim holds (E1 `06d88a3`, E2 `31aa5bb`,
HEAD `e1cb22a`), the **read-only safety invariant held exactly at the time of that audit** (no `create_seed`
shipped; `GET /api/org` static; `useApi` GET-only; the 3 POST routes control-plane) — **superseded 2026-06-21
by the DEC-3 amendment** (see the LATEST banner at the top): the invariant is now *"read-only except
owner-initiated capture"* with exactly two write paths (`/api/munshi/capture`, `/api/mcd/seeds`), the
spec↔code mapping is exact (17 apps · 7 linchpin `lib/` modules · 12 engines · 3 themes · 8 shell components),
and live suites are **backend 106 pytest + frontend 501 vitest** green. **The drift is strategic, not factual:**

- The **2026-06-19 evolution spec deliberately retired the word "OS"** — *"the word 'OS' is retired because it
  silently licenses OS-sized scope"* — and bound the project to an **attention-ROI north-star + a kill-criterion**
  (freeze if not demonstrably saving the owner ~3 hrs/wk by Phase 2). One day later the project pivoted to a
  literal **17-app "SAMAGRA OS"** windowing GUI (incl. a Snake game, 3 themes, mobile mode) as the **top
  priority** and **parked the value-producing active loop** (munshi → seed → board-approve → publish — the
  mechanism that actually saves owner attention).
- The OS experience spec **half-reconciles** this (it argues the windowing metaphor is "the honest shape of the
  work" and firewalls write paths) but **never restates the attention-ROI metric or the kill-criterion**, and
  STATUS / SUMMARY / HANDOFF did not surface the tension at all until this audit.
- **Codex vision verdict: `DRIFTING`. Audit verdict: `COHERENT-WITH-CAVEATS`** (this is the caveat). Full
  reviews: `docs/superpowers/_research/samagra-os/_vision-review-output.md` (+ `_vision-review-prompt.md`,
  `_vision-review.log`); audit synthesis is summarised in STATUS.html → *Direction coherence*.

**Decision (ratified 2026-06-21 by Deepak — these are now BINDING):**
1. **DEC-1 · Scope.** SAMAGRA OS is a **bounded operator console — a UI metaphor only.** SAMAGRA remains a
   control plane; it does **not** acquire app-platform scope. The windowing GUI is inward-facing operator
   infrastructure, never a product.
2. **DEC-2 · North-star — now ADVISORY (relaxed by DEC-6).** The **attention-ROI north-star**
   (minutes-of-owner-attention per published artifact) and the **kill-criterion** were originally **BINDING**;
   DEC-6 (2026-06-22) **relaxes them from binding to advisory** — they remain the informal standard the Chairman
   may invoke when judging GUI investment, but are no longer a hard freeze condition. Data source (if invoked) =
   the governance `events`/`review_overlay` ledger.
3. **DEC-3 · Scope firewall** (now a hard non-goal, mirrored into OS spec §3): **no** entertainment apps beyond
   E1's Snake; **no** third-party apps / app marketplace; **no** process- or scheduler-as-platform model; **no**
   user-facing product identity. Adding any of these is a Chairman decision, not routine engineering.
4. **DEC-4 · ~~Attention-ROI acceptance gate before E3~~ — RETIRED (DEC-6, 2026-06-22).** *(Original text kept
   for history.)* ~~Before any E3 work a gate must pass: pick 2–3 representative operator tasks, measure owner
   wall-clock time via SAMAGRA OS vs the prior tools; Pass = GUI reduces total owner time; Fail = freeze GUI
   expansion and reprioritize Phase 3.~~ **This gate is formally retired — see DEC-6.**
5. **DEC-5 · Phase 3 is the primary value engine.** The active loop (munshi → seed → board-approve → publish)
   restarts **after the E2 visual-QA pass** (the DEC-4 gate that previously also blocked it is retired by DEC-6),
   ahead of further theme/mobile polish — it is not optional.
6. **DEC-6 · DEC-4 RETIRED (2026-06-22, Chairman Deepak — option C of the post-audit-hardening plan W4).** The
   pre-E3 attention-ROI **acceptance gate is formally retired, not deferred.** Rationale: E3 *and* the public
   deploy shipped ahead of it and the bounded operator-console is judged already proven in practice — keeping a
   gate the project repeatedly ships past is governance theatre (the very GUI-first drift the coherence audit
   flagged). **Binding effect:** no SAMAGRA doc may describe DEC-4 (or any attention-ROI gauge) as a "binding
   gate" that must run before further GUI/deploy work; DEC-2 is relaxed to *advisory* (above). **Unchanged &
   still binding:** DEC-1 (bounded scope), DEC-3 (scope firewall), the never-automated publish gate, and DEC-5
   (Phase 3 next — now ungated by DEC-4).
7. **DEC-10 · G1 publish-boundary invariants — RATIFIED 2026-07-05 (formally promoted from proposed at Phase
   G1, 2026-06-26).** NO public/outward network surface at G1 (that arrived at G2/G3); NO new write path to the
   7 source subsystems; NO governance migration / NO new table / NO assignment-state-machine change (only new
   append-only event verbs `published`/`unpublished`); the inward `build()` boundary + its 5 crash-safety guards
   untouched; the never-automated publish gate is manual-CLI only (at G1); the mcd `seed` lane excluded (no
   local artifact).
8. **DEC-11 · G2 outward-read-surface invariants — RATIFIED 2026-07-05 (formally promoted from proposed at
   Phase G2, 2026-06-27).** NO new write path anywhere; the two public endpoints serve **only** owner-published
   bytes resolved through the manifest (never `_publications/`, `governance.db`, `EXPORT_DIR`, or the 7
   subsystems); public-by-design (the gate was already crossed at G1 publish); separate-entity (the console at
   `/` stays byte-unchanged; the `/learn` reader imports NO shell module); the inward `build()` + 5 guards + the
   never-automated publish gate untouched; NO migration/table/state-machine change.
9. **DEC-12 · G3 identity + outward-publish invariants — RATIFIED 2026-07-05.** (1) The publish gate holds —
   owner-gated, never-automated, delegating only to the reviewed G1 code, no new write mechanism (only a second
   owner trigger, HTTP beside CLI). (2) Identity is owner-enrolled, session-based, and **OPTIONAL** — no open
   self-registration, `/learn` stays public, no per-student learning state until G4. (3) Firewall by **physical
   isolation** — publish writes only `published/` + append-only governance events, student login writes ONLY
   `pratham.db`, the 7 read-only subsystems + the inward `build()` + its 5 crash guards untouched. (4)
   `pratham.db` is durable + gitignored; no `governance.db` migration, no new governance table, no
   assignment-state-machine change.
10. **DEC-13 · G4 adaptive-twin invariants — RATIFIED 2026-07-05 (source: spec §9).** (1) ALL student writes touch
    ONLY `pratham.db`; `samagra/pratham/` imports no factory/governance module (import hygiene = the firewall,
    review-verified). (2) Student identity is **server-derived only** — no student id parameter in any
    path/query/body under `/api/learn/*`, ever. (3) Progress rows only reference **published** content — the
    404-before-write manifest gate is load-bearing. (4) The recommender is **Tier-1 deterministic** (no
    LLM/network/key); any future LLM recommender is a distinct phase + decision + review, never a silent upgrade.
    (5) CSRF acceptance is scoped to the v1 progress write (own-data, no escalation; `SameSite=Lax` + cookie
    `path=/api/learn`); any new `/api/learn/*` write re-opens it. (6) Anonymous `/learn` stays byte-identical;
    `/api/published*` untouched; the publish gate, the inward `build()` + its 5 guards, the 7 source subsystems,
    and `governance.db` (no migration/table/state-machine change) all untouched.

This decision is recorded across STATUS.html (*Direction coherence*), SUMMARY.html, both specs and CLAUDE.md, so
it travels with the project. Reviews that informed it: `docs/superpowers/_research/samagra-os/_vision-review-output.md`.

**Single next-action order (updated 2026-06-22):**
1. ~~Fix the Questions facets bug.~~ **✅ DONE (`88b50a0`, QX-backed Questions).**
2. ~~Test-only S3/S4 LOW cleanup (HANDOFF item 4).~~ **✅ DONE (`0dceb0d`).**
3. ~~**E3** — mobile device mode + theme-correct WM geometry + responsive Dashboard.~~ **✅ BUILT
   (`73a97b7`+`82edd06`) on `e3/samagra-os` — DEC-4 consciously deferred by the Chairman this session.**
4. **Commit + merge the post-audit hardening** (this session's W1–W4) — owner-gated; suggest `/snap-pre` first.
5. **Merge `e3/samagra-os`** (present `superpowers:finishing-a-development-branch`).
6. Owner **browser-vision pixel-QA** pass over the E1 shell + the 11 E2 apps + the new mobile frame.
7. ~~Run the DEC-4 attention-ROI acceptance gate.~~ **DEC-4 RETIRED (DEC-6, 2026-06-22)** — Phase 3 (DEC-5) is
   now ungated; restart it after the E2 visual-QA pass. The attention-ROI north-star is advisory, not a gate.

(Backend pytest exits 1 on Windows from a tmpdir symlink-cleanup teardown *after* all 106 pass — cosmetic, not
a failure; run with `--basetemp` to silence.)

---

**Repo:** github.com/dbhardwaj86/samagra · `main` (E1 merged, `06d88a3`; **E2 merged, `31aa5bb`**) · **E2 MERGED to `main` (fast-forward, `31aa5bb`) and pushed to `origin/main` 2026-06-21 (Codex pre-merge review GO; 3 MEDIUMs fixed)** · local-first Python+FastAPI.
**State:** Spine + portal + thin/thick exporter + semi-autonomous loop + two read-only subsystem adapters
(mycontentdev seeds, munshi `library()`) reflecting into the catalog, **+ Phase-2 governance**: durable
`governance.db` store (assignments / events ledger / review overlay), `GET /api/assignments` + the
Assignments portal tab, an advisory Codex pre-commit gate (`samagra/review/`), the committed
`.githooks/pre-commit` shim, and per-agent board files (`board/{deepak,khanak,codex}/`), **+ SAMAGRA OS E1
+ fidelity layer**: the `frontend/` React+TS+Vite windowing shell (three themes — aqua/console/samagra chrome
· `Icon`/`AppIcon` SVG system · WM · six OS utilities on tested pure-TS engines) served by FastAPI from
`frontend/dist/`, + the chairman rename and right-click context menus. **Backend 102/102 pytest green; frontend 439/439 Vitest green.**

## Run it

```bash
cd C:\SandBox\claude_box\TeachingOS
set PYTHONPATH=%CD%                 # or: export PYTHONPATH=$(pwd) in bash
.venv\Scripts\python -m samagra refresh        # rebuild catalog (7,044 artifacts)
.venv\Scripts\python -m samagra status
.venv\Scripts\python -m samagra export --chapter vectors --variant both
.venv\Scripts\python -m samagra tick [--dry-run]
.venv\Scripts\python -m samagra gate textbook approve
# portal: preview harness (.claude/launch.json -> "samagra") OR:
.venv\Scripts\python -m uvicorn samagra.api.app:app --port 8799   # http://127.0.0.1:8799
```

```bash
# SAMAGRA OS (E1) frontend — from frontend/
cd frontend
npm install                      # first run only (generates node_modules from tracked lockfile)
npm run dev                      # Vite :5173, proxies /api,/lecture,/open -> uvicorn :8799
npm run verify                   # the gate: lint + tsc --noEmit + vitest run (439) + vite build
npm run build                    # writes frontend/dist/ (FastAPI serves it at / with an SPA fallback)
```

## Layout (source of truth)

- `samagra/adapters/` — read-only source adapters → common `Artifact` (incl. Phase 1 `mcd.py`, `munshi.py`).
- `samagra/clients/` — read-only subsystem HTTP clients: `McdClient` (mycontentdev admin API), `MunshiClient` (`library()`); secret-safe, never logged.
- `samagra/governance/store.py` — Phase 2 durable `governance.db` store (D6): `assignments`, `events`, `review_overlay` + `schema_version`/migration hook + `backup()`. **Never delete `governance.db` as a "catalog reset".**
- `samagra/review/` — Phase 2 advisory pre-commit Codex review (D5): `codex_dispatch.py` (vendored subprocess shim, lazy exe) + `precommit.py` (confirmed-CRITICAL + `state/review/` diff-hash cache + `SAMAGRA_REVIEW_BREAKGLASS` audit). CLI: `samagra review-staged`.
- `.githooks/pre-commit` — committed shim → `python -m samagra.review.precommit`. Activate (owner) with `git config core.hooksPath .githooks`.
- `board/{deepak,khanak,codex}/` — per-agent `AGENTS.md` + `outbox/` (indexed by `assignments`).
- `samagra/catalog.py` — `samagra.db` unified catalog (FTS5) + search/overview/facets.
- `samagra/state.py` — phase state machine; `state/<pipeline>.orchestrator_state.json` + `tracker.txt`.
- `samagra/scheduler.py` — `tick()`, `gate()`, Task Scheduler installer.
- `samagra/notify.py` — Telegram + email (creds-gated, always logs `state/notifications.log`).
- `samagra/lectures/` — `render.py` (content.json→HTML), `thin.py`, `export.py` (HTML/DOCX/GDocs), `gdocs.py`.
- `samagra/api/app.py` — FastAPI; serves the Vite build at `/` (mounts `frontend/dist/assets`, SPA fallback `GET /{full_path}` declared LAST, 404s `api/*`, 503 if not built); `/api/*`, `/lecture/{slug}`, `/open` are a frozen contract.
- `frontend/` — **SAMAGRA OS E1 + fidelity layer** (React 18 + TS + Vite; own `package.json`, lockfile tracked, `dist/` gitignored). `src/lib/**` = pure headless-testable engines (WM geometry/z-order, snake, clock, terminal, notes, persistence) each co-located with a `*.test.ts`; `src/stores/**` = thin Zustand over `lib/`; `src/themes/**` = the per-theme token map (aqua/console/samagra — **FD1**); `src/components/{Icon,AppIcon}.tsx` = the SVG icon system (**FD2**, `icons-data.ts`); `src/shell/**` = theme-driven chrome (`ThemeRoot` · `TopBar` · `Dock` · `Taskbar` · `StartMenu` · `Rail` · `WindowFrame` · `ContextMenu`); `src/apps/**` = the six OS utilities; `src/registry.ts` = the frozen 17-app table.

## Sources (read-only, paths in samagra/config.py / .env)

QX `C:\SandBox\gpt_box\gpt-extract-ques` · textbook `C:\SandBox\gpt_box\physics-textbook`
· booklets `claude-booklet-proofer` · INSP `claude-INSP-extract` · sims `pratyaksh-May-deploy` (never write).

## Gotchas

- Python 3.11 venv (`.venv`) for the portal; system Python is 3.14 (stdlib-only CLI works there too).
- Do **not** use `--reload` here — an orphaned reload worker held the port once (D-1). `samagra serve --reload` is
  now **guarded**: it's ignored with a warning unless `SAMAGRA_ALLOW_RELOAD=1`. Use the preview harness or plain uvicorn.
- **Adapter registry key is `mycontentdev`** — the `mcd` in `McdClient` / docs is shorthand; `get_adapter("mcd")`
  returns `None`. Use `get_adapter("mycontentdev")` (as `app.py` does).
- QX `subject` column is unpopulated (physics-only); facet on chapter/q_type instead. **(The old SIM0xxx chip leak
  is RESOLVED — the live Questions chips now come from the `/api/questions` payload facets (QX `search.facet_counts`,
  filter-scoped), NOT the catalog-wide `/api/facets.subjects`. The separate `/api/questions/facets` endpoint exists
  but the UI does not consume it — see its docstring in `app.py`.)**
- DOCX math: Pandoc `html+tex_math_dollars` converts `$...$` → OMML (verified: 130 eqns in vectors-thick).
- Don't write to `physics-textbook/queue.json` — SAMAGRA tracks approvals in its own `state/`.

## Open / needs user consent

**SAMAGRA OS (Experience track):**
- **E2 (2026-06-21): MERGED to `main` (fast-forward, `31aa5bb`) and pushed to `origin/main`** — the 11 data apps
  + `GET /api/org`, after a Codex pre-merge review (GO; 3 MEDIUMs fixed) (backend 106/106 + frontend 501/501).
  Owner to-do = the browser-vision pixel-QA pass over the 11 E2 apps, then E3 (see the ▶ STATUS banner above for
  the full E2 write-up). The E1 detail below is retained for history.
0. **E1 BUILT + GREEN + 3-theme/icon fidelity layer landed (2026-06-20) on `e1/samagra-os`.** The full
   `frontend/` app shipped TDD (E1.1–E1.25); a fidelity layer then added theme-driven chrome for **aqua ·
   console · samagra** (all colours/sizes from the `themes/` token map — FD1) and the `Icon`/`AppIcon` SVG
   system (FD2) across every launcher + the six apps. **QA1 fidelity gate clean:** `npm run verify` (lint +
   `tsc` + **439 Vitest / 38 files** + `vite build`, no `.only`/`.skip`) and backend `pytest` 102/102 (incl.
   `test_serve_seam.py`). **Owner to-do now:** (a) the **browser-vision pixel QA pass** over the three-theme
   shell + apps (pixel/interaction parity — outside any loop, never a loop gate; **NOT yet run — pixel parity
   NOT claimed**); (b) the merge/integration decision for `e1/samagra-os` (see
   `superpowers:finishing-a-development-branch`). **Next build = E2** (data/control apps — read-only wiring
   over `/api/*`; one hard backend gap = `GET /api/org` via static `samagra/org.py`). **No new creds needed**
   (the GUI reads existing `/api/*`); E2's mcd/munshi apps render graceful creds-gated empty states.

   **Browser-vision pixel QA sign-off (fidelity boundary — owner-run, RUBRIC §6).** Per spec §7.4/§10-item-9
   and `docs/superpowers/loops/RUBRIC.md` §6, pixel & interaction parity is a **human / browser-vision QA
   pass, never a loop gate** — run once per surface with `npm run dev` (Vite :5173) or a built `samagra
   serve`, against the extracted prototype + `screenshots/`. The owner (deepak) signs each row here. **Status:
   all rows PENDING** (logic green, theming + icon wiring green, build green — *not yet* "looks right"; the
   headless gate proves the markup/tokens/icons, not the pixels). Surfaces:
   - [ ] **Theme chrome (×3)** — aqua (top bar **30px** · bottom-centre Dock **radius 20** + hover lift · left traffic-lights), console (no top bar · bottom Taskbar **50px** + Start menu · right-side neon icon controls · active glow ring), samagra (Devanagari **समग्र** top strip · left **Rail 66px** + active accent bar · warm window frame). WindowFrame radii aqua **13** / console **10** / samagra **15**; **38px** title bar; right controls 28×23; double-click maximize; ContextMenu **width 216**.
   - [ ] **Icons (FD2)** — every dock/rail/Start/app glyph is an inline 24×24 stroke `<svg>` via `Icon`/`AppIcon` (no letter badges); per-app accent colours from `APPS[id].accent`.
   - [ ] **Dashboard** — hero-stat layout, pipeline-bar density, board + recent-activity spacing.
   - [ ] **Settings** — Appearance (3 theme swatch cards) / Device toggle / Integration rows; pill active vs needs-creds states; this is the production theme + device switcher.
   - [ ] **Terminal** — prompt rendering, line-class colors from the per-theme palette, welcome banner.
   - [ ] **Clock** — hand sweep, ring depletion, chime, tab visuals.
   - [ ] **Notes/To-dos** — list/editor split, "● Autosaved" footer, filter chrome.
   - [ ] **Snake** — movement feel, speed ramp, death visuals, D-pad, themed board (cream in samagra).
   - [ ] **Components** — Pill/Card/Chip/IconButton accent + spacing parity across all three themes.

**Phase-2 owner-gated — ALL DONE (2026-06-19):**
1. **Pre-merge Codex review → APPROVE** (gpt-5.5, xhigh): 6 rounds + a CEO adversarial Workflow audit. Caught a never-wedge HIGH, a recurring "outer guard downgrades a confirmed-CRITICAL block" class (5 ever-deeper instances: cache prune, malformed cached findings, broken-stderr warnings, pathological exception str/repr, and a finding's raising `__eq__` on the dedup), + 2 MEDIUM + nits — all fixed TDD (+11 invariant regressions, suite 98). Reports `docs/codex-reviews/07–13` + `12-workflow-invariant-audit.md`.
2. **Hook ACTIVE** — `core.hooksPath=.githooks` set; every commit + worktree now runs the advisory gate (`codex` 0.140.0 on PATH).
3. **Worktrees created** — `../samagra-{deepak,khanak,codex}` on `agent/{deepak,khanak,codex}`.
4. **Pushed** — `origin/main` holds Phase 2 through `da9cab3`. (NOTE: this end-of-session tracker-sync commit is local-only/unpushed — `git push origin main` it at the start of the next session.)

**Creds (slice-1, unchanged):**
5. **Notification creds** — fill `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` + gmail `SMTP_PASS` in `.env`.
6. **Google Docs** — set `GOOGLE_OAUTH_CLIENT` (Desktop OAuth JSON); run an export to complete consent flow.
7. **Phase 3 munshi** — drop `MUNSHI_API_URL` + `MUNSHI_SECRET` into `.env` (live worker secret value) to switch on the active loop's munshi reads. mcd already reads live via `mcd-cloud.json`.

## Slice 2 (planned)

Real worker dispatch for `questions`/`papers`/`media` pipelines (Codex/Gemini/NotebookLM/Grok);
deploy QX + portal online (HF Space `QuestionDB` / Docker).
