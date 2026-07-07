# SAMAGRA Content Factory — Phase F2: the `slides` lane (NotebookLM-generated slide decks)

**Status:** RATIFIED 2026-07-07 (orchestrator adjudication under the Chairman's full-auto Phase-F delegation — "go for phase F - full auto, carry to completion". Forks locked: **S1** synchronous-blocking poll (bounded `SAMAGRA_SLIDES_TIMEOUT` default 900s, retryable rollback, NO new build() state, NO migration) · **A1** ephemeral per-build notebook (create→source→generate→download→delete in `finally`) · **B1** rendered chapter text via `nlm source add --text` · **C** self-contained data-URI wrapper HTML = the publishable single-file artifact (ZERO G1/G2 change, F1 playbook) · **D2** owner-reviewed only, `SAMAGRA_SLIDES_AUTOCAPTURE` default OFF → every deck lands `changes`, no vision call (DEC-8 holds by construction) · **E** fail-closed-before-intent / retryable-rollback-after-intent. `configured()` parses `nlm login --check` STDOUT (it exits 0 even when auth is expired). Live smoke is opt-in + owner-run (`SAMAGRA_LIVE_SLIDES_SMOKE` + configured); the standing gate is 100% offline via an injectable fake subprocess runner; merge does not depend on any live run. HTTP-403 free via `kind="llm"`.)

**Slice type:** the SECOND and FINAL Phase-F lane, and SAMAGRA's first **subprocess / external-CLI** generation boundary (it drives Google NotebookLM through the `nlm` CLI). It rides the existing `kind="llm"` synchronous `build()` envelope — the SAME path F1 (figure) and D2 (samadhan) use — and adds no new build() state and no governance migration. **NO AUDIO — ever** (Chairman, absolute). A dedicated Codex pre-merge review of the new subprocess/NotebookLM async boundary is REQUIRED — **review 34** (house convention: any new network/secrets/generation boundary gets a DEC-7-style review, precedent D2/review 27, the LLM-provider mini-slice/review 32, F1/review 33).

---

## 1. Problem

The umbrella spec's lane table (`docs/superpowers/specs/2026-06-23-samagra-content-factory-design.md` §3.1) parks a `slides` lane: `slides | NotebookLM studio_create | Google Slides / deck | async, external | F`. F1 proved the heavy/external generative-lane shape end-to-end (figure: select targets → generate → adversarial ground-truth review → local write → conservative capture/changes gate), riding the proven `kind="llm"` build envelope. But no lane yet produces a **slide deck**, and no SAMAGRA code has ever shelled out to an external CLI as its generation boundary.

Google **NotebookLM** turns source documents into studio artifacts — including slide decks — and the owner already drives it through the installed `nlm` CLI (`C:\Users\abc\.local\bin\nlm`, Google-OAuth authed, 244 notebooks). F2 wires SAMAGRA's factory to that CLI so a textbook chapter fans (opt-in) to a NotebookLM-generated deck behind the same never-automated publish gate every other lane sits behind.

Two hard truths F2 must design around:

1. **NotebookLM slide generation is asynchronous and slow.** `nlm slides create` kicks off generation that can take minutes; readiness is polled via `nlm studio status`, and the artifact is fetched with a separate `nlm download slide-deck`. The lane must handle a multi-minute wait, a timeout, and a flaky external service cleanly — with no partial capture.

2. **A NotebookLM deck is a DRAFT for owner eyes.** The model composes slides from sources it summarizes; for JEE/NEET physics the geometry, notation, and emphasis are frequently off. Like F1, F2 defaults conservative — every generated deck lands `changes` for owner review, never a silent auto-capture.

3. **The downloaded artifact is a binary (PDF or PPTX), not a single HTML/JSON/DOCX file** — which is the only shape G1/G2 can publish today. F2 must solve this the way F1 did (self-contained artifact, zero G1/G2 change) or the deck can never reach `/learn`.

---

## 2. Scope

### In
- New client module **`samagra/clients/notebooklm_client.py`** — the ONE NotebookLM call site, SHELLING OUT to the `nlm` CLI. It mirrors `llm_client.py`/`image_client.py`'s boundary pattern but with a subprocess runner instead of an SDK: `configured()` (probe `nlm` present + authed — NO env secret; §3.3), an **injectable subprocess runner** (a fake stands in for the runner so NO standing test shells out or hits Google), never-leak error extraction (never echoes notebook content / cookies / raw `nlm` stderr blobs), fail-closed. **All `nlm` invocations go through ONE run helper** (injectable) — no scattered `subprocess.run`.
- New engine **`samagra/factory/slides.py`** — `build_slides(slug, *, nlm=None)`: render the chapter to a source document (§3.A/B) → create an ephemeral notebook → add the source → `nlm slides create --confirm` → **synchronously poll** `nlm studio status --json` until the deck is ready or a bounded timeout → `nlm download slide-deck` → wrap the deck into a **self-contained publishable HTML** (§3.C) → **delete the ephemeral notebook** → return a factory-compatible result dict.
- `lines.py`: register the `slides` lane (`kind="llm"`, `auto_fan=False`, prefix `textbook:`).
- `dispatch.py`: `run_line` routes the `slides` lane to the new engine; `validate_product` gains a slides branch (existence/non-empty of the wrapper html + the embedded deck file), reusing the `kind=="llm"` `_assert_review_clean` gate.
- `build()`: the `slides` lane reaches the EXISTING `kind=="llm"` preflight-before-intent / capture-changes / retryable-rollback path; the only touch points are the preflight dispatch (§3.6.2) and the conservative-default `needs_review` clause (§3.6.3), mirroring F1 exactly.
- CLI: `factory plan textbook:<slug> --lane slides` already works via the existing `plan(lane=...)`; no new subcommand. `.env.example` gains a NotebookLM slides block.
- Tests: full offline TDD matrix (a **fake subprocess runner** scripting `nlm` stdout/exit codes; no standing test shells out or hits Google) + one **opt-in owner-run** live smoke gated on `SAMAGRA_LIVE_SLIDES_SMOKE` **AND** `configured()`.

### Out
- **AUDIO — permanently, absolutely (Chairman).** F2 uses ONLY `nlm slides create` / `nlm download slide-deck` / `nlm studio status`. It never calls `nlm audio`, `nlm video`, or any non-slides studio verb. This is an invariant, not a scoping convenience (§4.10).
- Any **async / pending `build()` state machine.** F2 is strictly synchronous on the existing `kind="llm"` path (central decision → **S1**, §3.0). A slides build that blocks for minutes runs inline exactly as an mcd, samadhan, or multi-image figure build does. A timeout → whole-build raise → the existing retryable rollback.
- **A first-class binary/PDF/PPTX/link publish surface** (a `pdf`/`pptx` publish kind, a directory artifact, a Google-Slides URL). F2 makes the deck publish-**compatible** by embedding it in a single self-contained HTML the G1/G2 pipeline already copies and serves (§3.C). A native binary publish surface, if ever wanted, is a G-phase follow-up.
- **Slide-level revision** (`nlm slides revise`), **NotebookLM chat/query**, cross-notebook, and every other `nlm` verb outside the create→status→download→delete slides path.
- **StyleSeed conditioning** on the deck. The deck is composed by NotebookLM from the source document; there is no SAMAGRA prompt to condition (§3.5). `style_fit` is omitted for this lane.
- **A per-slide vision/adversarial review** of the generated deck. F2 is **owner-reviewed only** (autocapture OFF → every deck lands `changes`), which is strictly more conservative than a model review and avoids a second slow/costly model hop (central decision D → **D2**, §3.4).

---

## 3. Design

### 3.0 The central fork — synchronous-blocking (S1) vs async-pending state machine (S2)

NotebookLM slide generation is asynchronous and can take minutes. Two designs were weighed.

- **(S1) Synchronous-blocking poll.** `build_slides` creates the deck, then polls `nlm studio status --json` in-process until the deck reports `completed` (or a bounded `SAMAGRA_SLIDES_TIMEOUT`, default **900s / 15 min**), downloads it, wraps it, deletes the ephemeral notebook, and returns — riding F1's EXACT synchronous `kind="llm"` envelope with **no new `build()` state and no governance migration**. A timeout (or any step failure) → whole-build raise → the existing local-write-lane retryable rollback (records `product_build_failed`, rolls back the in-flight intent, assignment is retryable). Reuses everything proven in F1/D2.
- **(S2) Async-pending state machine.** `build()` kicks off generation, records a genuine `pending` assignment state, and returns immediately; a separate `factory collect`/poll step later finds ready artifacts and finishes the capture. This is what the umbrella spec §6 parked — but it is a large new `build()` surface: a new assignment status, a new state-machine transition, almost certainly a governance migration (the status set + a poll/collect verb), a new crash-window (a deck completes but the collect never runs; the notebook is orphaned), and a new re-entrancy story for the collect step.

**Decision → S1.** S1 is strictly smaller and reuses the whole proven envelope. The owner-driven CLI/GUI already tolerates multi-minute builds: paper/drill block on live QX, samadhan blocks on a live LLM round-trip, and F1's live image smoke blocked ~41s — all synchronous, all fine. NotebookLM slide generation is minutes, not hours, and a **bounded timeout + retryable rollback** handles the slow-and-failed case cleanly (re-clicking Build re-runs from a clean state — the ephemeral notebook from the failed run is either already deleted or is a harmless orphan the cleanup path prunes on the next run, §3.E). S2's separate `collect` machinery — a new status, a migration, a new crash-window — is not justified to ship a working slides lane; it would be the correct move ONLY if generation reliably exceeded any tolerable in-process block, which minutes-scale generation does not. **S1 is the recommendation; S2 is explicitly rejected for F2** and remains available as a future slice if NotebookLM's generation latency ever regresses past the timeout in practice.

**One consequence pinned:** because `build()` holds the governance connection for the whole synchronous window, a slides build occupies the `_FACTORY_RUN_LOCK` (G5) and the DB connection for minutes. This is already true of samadhan/paper/figure and is acceptable for the single-operator console; the timeout bounds it. (Over HTTP the lane is 403'd anyway — §3.6.4 — so only the CLI holds the long lock.)

### 3.A Notebook lifecycle (design question A)

**Options weighed**
- **(A1) Per-build ephemeral notebook** — create → add source → generate → download → **delete**, all within one `build_slides` call. Leaves no NotebookLM state; each build is hermetic and idempotent (a retry starts fresh). Cost: two extra `nlm` calls (create + delete) per build, and a cleanup obligation on the failure path.
- **(A2) Reused per-chapter notebook** — one durable notebook per slug, re-generate the deck into it on rebuild. Saves the create call but requires SAMAGRA to persist a slug→notebook-id map (new durable state — a new store, which F2 has explicitly avoided), and it accumulates 59 notebooks in the owner's account, muddying the 244 that already exist.
- **(A3) Single scratch notebook** — one shared notebook, cleared and reused across all slugs. Minimal account clutter but NOT concurrency-safe (two builds would race the same notebook's sources/artifacts) and it entangles unrelated chapters' sources.

**Recommendation → A1 (per-build ephemeral).** Create a titled notebook (`nlm notebook create "SAMAGRA slides: <slug> <uuid>"`), add the chapter source, generate, download, then **delete the notebook** (`nlm notebook delete <id> --confirm`) in a `finally` so a mid-build failure still cleans up. This keeps F2 **stateless** (no slug→notebook map, no new store), hermetic (each build fresh), and leaves the owner's 244 real notebooks untouched. **Failure/cleanup path:** the delete runs in a `finally`; if the delete itself fails (e.g. `nlm` flaky at teardown), F2 logs a concise warning naming the orphaned notebook id and STILL raises/returns on the primary outcome — a leaked ephemeral notebook is a harmless, owner-pruneable artifact (titled with the `SAMAGRA slides:` prefix so the owner can bulk-find them), never a correctness problem. The delete-failure is deliberately NOT allowed to mask a successful download or to convert a success into a rollback (§3.E).

### 3.B Source fed to the notebook (design question B)

To make a deck, the ephemeral notebook needs the chapter content as a source. `nlm source add <id>` accepts `--url`, `--text`, `--file` (PDF etc.), `--drive`, `--youtube`.

**Options weighed**
- **(B1) The rendered lecture text/HTML.** The lecture lane already renders chapter HTML via the lecture exporter; F2 can render the chapter to plain-ish text (the same `render.load_chapter` ground truth the other lanes read) and feed it as `--text`. Deterministic, no extra file to manage, no upload, and it is EXACTLY the ground truth the corpus already carries.
- **(B2) A generated PDF of the chapter.** Feed `--file chapter.pdf`. Requires F2 to first render a PDF (a new local render step + a temp file), then upload it, then wait for source processing — more moving parts and a heavier `--wait` upload path, for no quality gain over the raw text NotebookLM would extract from the PDF anyway.
- **(B3) The raw `content.json` prose.** Feed the raw structured JSON as `--text`. NotebookLM would have to parse JSON scaffolding (block types, tex, flags) as if it were prose — noisier than clean rendered text.

**Recommendation → B1 (rendered chapter text as `--text`).** `build_slides` calls `render.load_chapter(slug)` (the shared ground-truth loader every lane uses) and projects it to a clean text document (title + section headings + prose/equation/callout text — the same projection `figure._section_text` already does per section, generalized to the whole chapter). It feeds that via `nlm source add <id> --text "<chapter text>" --wait` (block until the source finishes processing, bounded by `--wait-timeout` = the slides timeout). No temp PDF, no upload, no new render engine — deterministic and simplest. (If a chapter's text exceeds a sane `--text` size, F2 truncates to a bounded prefix and records `source_truncated: true` in the manifest — a safety rail, not a common case.)

### 3.C Download artifact shape + publish story (design question C) — THE central codebase risk, resolved

**What `nlm download slide-deck` actually produces** (pinned live from `nlm download slide-deck --help` and `nlm --ai`, no `--confirm` run):

```
nlm download slide-deck <notebook-id> [--id <artifact-id>] [--format pdf|pptx] [-o <path>]
  # --format pdf (DEFAULT) or pptx. Default output ./{notebook_id}_slides.{ext}
```

The authoritative `--help` says **"Download Slide Deck (PDF or PPTX)"** with `--format pdf` (default) or `pptx`. (Note a documentation inconsistency: the `nlm --ai` "Supported Formats" summary line also lists "Slide Deck: `.txt` (slide content)". The authoritative per-command help is PDF/PPTX; the `.txt` line appears to describe an alternate slide-content export. F2 pins **`--format pdf`** as the download and the live smoke (§5.2) is the confirming owner-run check of the exact bytes; if the live smoke reveals `.txt`, the wrapper (below) trivially embeds text instead of a PDF data-URI — the publish story is unchanged either way.)

**The risk.** G1's `publish.run._captured_publishable` copies exactly the file keys `("html","json","docx")` and **requires `result["html"]` to be a single existing file**; G2's `read.resolve_artifact` only knows kinds `html`/`json`/`docx` (`_KIND_EXT`). **A binary PDF/PPTX is not a first-class publish citizen today** — the same wall F1 hit with a PNG directory.

**Resolution → self-contained wrapper HTML, ZERO G1/G2 change** (F1's exact playbook). `build_slides` writes, under `EXPORT_DIR/<slug>/`:

```
EXPORT_DIR/<slug>/
  <slug>-slides/deck.pdf              # the raw downloaded deck (working copy; NOT published)
  <slug>-slides.json                  # manifest sidecar (deck bytes as base64 + meta)
  <slug>-slides.html                  # the SELF-CONTAINED publishable wrapper (see below)
```

The **wrapper `<slug>-slides.html`** is a single self-contained file that embeds the deck as a **data URI** and renders it inline:
- For a **PDF** deck: an `<embed type="application/pdf" src="data:application/pdf;base64,...">` inside a sized container, plus a same-page download link (`<a download href="data:application/pdf;base64,...">`) so a reader on a browser without inline-PDF support can still get the deck. No external references — consistent with the sandboxed-iframe CSP the G2 reader enforces on published html (the CSP is `sandbox allow-scripts`; a data-URI `<embed>` needs no script and no external host).
- For a **PPTX** deck (if `--format pptx` is ever selected) or a `.txt` slide-content export: the same wrapper with a download link + (for `.txt`) the escaped slide text rendered inline. PPTX is not browser-renderable inline, so the wrapper is a titled download card — still a single self-contained html.

The wrapper title, chapter, and any deck-status text are HTML-escaped at the boundary (the C1 deck lesson). The `.json` sidecar keeps the raw base64 + metadata (deck format, artifact id, generation timing, source-truncation flag).

**Both `<slug>-slides.html` and `<slug>-slides.json` are single files under the keys G1 already copies**, so `publish textbook:<slug> --lanes slides` works with **zero G1/G2 change**, and `resolve_artifact(chapter,"slides","html")` serves the wrapper sha-verified in the existing sandboxed iframe. The raw `deck.pdf` under `<slug>-slides/` is intentionally NOT published (it is the working/debuggable copy, exactly like F1's loose `fig-NN.png`). A first-class binary published surface (a `pdf` kind, per-deck deep links) is a deliberate G-phase follow-up, out of F2 scope. A regression test pins `publish --lanes slides` on the wrapper html + the G2 resolve (T16).

**Data-URI size note.** A NotebookLM PDF deck is typically a few hundred KB to a couple MB. Base64 inflates it ~33%. This is well within a single-file html budget for the single-operator reader; the manifest records `deck_bytes` so an oversize deck is visible. (If a future deck is pathologically large, the wrapper degrades to a download-only card with no inline `<embed>` above a size threshold `SAMAGRA_SLIDES_EMBED_MAX`, default 8 MB — still self-contained, still zero G1/G2 change.)

### 3.3 The subprocess client boundary — `configured()`, the run helper, never-leak (design question, client shape)

`notebooklm_client.py` mirrors `image_client.py` but its "SDK" is the `nlm` CLI reached through subprocess. Key differences from the SDK clients, all pinned:

**`configured()` = probe `nlm` present + authed (NO env secret).** This lane holds NO SAMAGRA secret — `nlm` stores Google OAuth creds itself. `configured()`:
1. Resolves the `nlm` executable (PATH lookup, or `SAMAGRA_NLM_BIN` override; default just `nlm`). Absent → `False`.
2. Runs the auth probe `nlm login --check` through the run helper.
3. **Parses STDOUT for the success marker, NOT the exit code.** ⚠ Pinned live: `nlm login --check` prints `✓ Authenticated` when good and `✗ Authentication Error` when expired, but **exits 0 in BOTH cases** (`notebook list` behaves the same). Relying on the exit code would read an expired session as configured. `configured()` returns `True` iff stdout contains the authenticated marker (`"✓ Authenticated"` / absence of `"Authentication Error"`), `False` otherwise. This stdout-parse subtlety is a named review-34 focus.

`configured()` is cheap-ish (one fast `nlm` call) but does hit the local CLI; it is called by `slides.preflight` BEFORE `build()` records intent (anti-wedge), and it never raises (a missing `nlm` / probe failure → `False`, a clean fail-closed refusal).

**ONE injectable run helper.** `NotebookLMClient` takes a `runner` callable (default = a thin `subprocess.run` wrapper). Every `nlm` invocation — create, source add, slides create, studio status, download, notebook delete, the auth probe — goes through `self._run(args, ...)`. Tests inject a **fake runner** that returns scripted `{stdout, stderr, returncode}` per command, so **no standing test shells out or touches Google**. The helper:
- Passes args as a **list** (never a shell string) — no shell injection; the chapter text goes via `--text` as a single argv element.
- Enforces a per-call timeout; a hung `nlm` is killed and surfaced as a concise `RuntimeError`.
- **Never leaks:** on a non-success it raises a `RuntimeError` naming the `nlm` subcommand and a short, sanitized reason — it does NOT echo raw `nlm` stderr blobs (which can carry cookies/session hints), the chapter text, or notebook content. A small allowlist of known-safe status words is surfaced; everything else is collapsed to a generic "nlm <verb> failed".

**Idempotency / parsing.** `studio status --json` output is parsed for the slides artifact's `status` and `id`; unparseable JSON → fail-closed `RuntimeError`. The client exposes typed methods: `configured()`, `create_notebook(title) -> id`, `add_text_source(nb, text) -> None`, `create_slides(nb, *, fmt, length) -> None`, `poll_slides(nb, *, timeout) -> artifact_id` (the synchronous poll loop), `download_slides(nb, artifact_id, out_path) -> Path`, `delete_notebook(nb) -> None`. The engine composes them; the client owns every `nlm` call.

### 3.1 The exact `nlm` command strings (pinned live)

All pinned from `--help` / `--ai` reads only — **no `--confirm` was ever run** (no live artifact created). `<nb>` = the ephemeral notebook id; `<aid>` = the slides artifact id from `studio status`.

| Step | Command (argv list) | Notes |
|---|---|---|
| auth probe (`configured()`) | `nlm login --check` | Exits 0 even on failure → **parse stdout** for `✓ Authenticated` / `✗ Authentication Error`. |
| create notebook | `nlm notebook create "SAMAGRA slides: <slug> <uuid8>"` | `[TITLE]` positional. Parse the created id from stdout (or `nlm notebook list --json --quiet` if stdout id is not machine-clean — pinned in the live smoke). |
| add source | `nlm source add <nb> --text "<chapter text>" --wait --wait-timeout <T>` | `--text`/`-t` inline; `--wait`/`-w` blocks on processing; bounded by `--wait-timeout` (float seconds, default 600). |
| create deck (ASYNC) | `nlm slides create <nb> --confirm --format detailed_deck --length default` | `--confirm`/`-y` REQUIRED for automation. `--format` ∈ {`detailed_deck` (default), `presenter_slides`}; `--length` ∈ {`short`,`default`}. Returns after kickoff; generation continues async. |
| poll status | `nlm studio status <nb> --json` | Machine-readable artifact list + status. Poll until the slides artifact is `completed` (or the timeout). `--full`/`-a` for detail. |
| download | `nlm download slide-deck <nb> --id <aid> --format pdf -o <out> --no-progress` | **PDF (default) or PPTX.** `--id` targets the exact artifact; `--no-progress` for clean non-TTY output. |
| cleanup | `nlm notebook delete <nb> --confirm` | In a `finally`; a delete failure logs + is swallowed (never masks the primary outcome). |

**F2 uses ONLY the slides + notebook-lifecycle verbs above. It NEVER calls `nlm audio`, `nlm video`, or any other studio create verb (§4.10 — audio is a hard invariant).**

**Deck format defaults (env-tunable, validated fail-closed at construction like `SAMAGRA_LLM_EFFORT`):** `SAMAGRA_SLIDES_FORMAT` ∈ {`detailed_deck` (default), `presenter_slides`}; `SAMAGRA_SLIDES_LENGTH` ∈ {`default` (default), `short`}; `SAMAGRA_SLIDES_DOWNLOAD_FORMAT` ∈ {`pdf` (default), `pptx`}. An unknown value refuses at client construction, never mid-build.

### 3.2 The synchronous poll loop (S1 mechanics)

`poll_slides(nb, *, timeout)` runs the S1 wait entirely in-process:
- Loop: `nlm studio status <nb> --json`, parse the slides artifact's status.
- `completed` → return its artifact id.
- an explicit `failed`/`error` status → raise `RuntimeError` (NotebookLM rejected the generation) → whole-build raise → retryable rollback.
- still pending → sleep a bounded interval (`SAMAGRA_SLIDES_POLL_INTERVAL`, default 15s) and retry.
- total elapsed ≥ `SAMAGRA_SLIDES_TIMEOUT` (default 900s) → raise `TimeoutError` → whole-build raise → retryable rollback (the assignment is retryable; re-clicking Build re-runs fresh).

The poll is the only place F2 blocks for minutes; it is bounded on both the per-call timeout (a hung `nlm status`) and the total timeout (slow generation). No busy-wait — the interval sleep keeps it cheap.

### 3.4 Review step (design question D)

**Options weighed**
- **(D1) An adversarial/vision review of the generated deck** (like F1's per-figure vision review): download the deck, render slides to images, send each to a vision model anchored to the chapter to refute. Cost: N extra vision calls per deck + a PDF→image render step. Value: a recorded verdict per slide.
- **(D2) Owner-reviewed only** — no model review; autocapture OFF → every deck lands `changes` for owner eyes.

**Recommendation → D2 (owner-reviewed only).** Because F2's default posture is autocapture OFF (§3.6.3) — **every deck build lands `changes` for the owner to open the wrapper and eyeball the deck** — a heavy per-slide vision review adds real cost (a PDF→image step + N vision calls) and latency for no gate benefit: the owner already reviews every deck before it can be captured or published. D2 is strictly MORE conservative than a model review (a model might wrongly clear a bad deck; the owner will not auto-capture anything). F2 therefore ships with **no adversarial review call** and no vision hop.

**DEC-8 firewall (trivially structural).** Because there is NO review call and NO StyleSeed anywhere near this lane (§3.5), there is nothing that could receive the StyleSeed — the firewall holds by construction. If a future slice adds an optional deck review (a distinct decision + review), it MUST be anchored ONLY to chapter ground truth and MUST NOT receive the StyleSeed, exactly like `llm_client.review_figure`.

**Capture-gate consequence.** With no review, the `kind=="llm"` `_assert_review_clean` gate (which requires integer `errors`/`items` and, when `items>0`, a non-empty `verdicts` list) must not spuriously refuse a slides result. F2 reports `items` = 1 (the deck) and `errors` = 0 with an empty-but-present `verdicts` list is NOT valid (the gate requires non-empty verdicts when items>0). **Resolution:** F2 sets `items = 0` semantics do not fit a deck. Instead F2 records `items = 1`, `errors = 0`, and a single **synthetic owner-review verdict** `verdicts = [{"idx": 0, "verdict": "changes", "rationale": "NotebookLM deck — owner review required"}]` so `_assert_review_clean` passes structurally, AND the conservative default clause (§3.6.3) routes to `changes` regardless. (Alternatively, `_assert_review_clean` gains a slides-lane carve-out; the synthetic-verdict approach is preferred — it needs zero change to the shared guard and keeps the artifact self-describing.) This is pinned by T13/T15.

### 3.5 StyleSeed conditioning (design question E — same as F1)

**No StyleSeed on the slides lane.** NotebookLM composes the deck from the source document; there is no SAMAGRA prompt to condition on the StyleSeed (a prose-voice profile), so conditioning is not even structurally possible here. This keeps the DEC-8 reviewer firewall trivially structural (no StyleSeed anywhere near the lane) and means `slides.preflight` does NOT require a committed StyleSeed (unlike samadhan) — a chapter can produce a deck with no StyleSeed present. `style_fit` is omitted; the manifest records no style score.

### 3.6 build() integration — the existing `kind="llm"` path (design decision 2)

The slides lane is `kind="llm"`, so it flows through the guard block `build()` already has, with the SAME five crash-safety guards and the SAME retryable-rollback semantics (local-write lane → a transient `nlm`/NotebookLM failure rolls back the in-flight intent → the assignment is retryable, never wedged). Touch points (all mirroring F1):

1. **`run_line`** gains `if line == "slides": return slides.build_slides(slug)` before the generic `kind=="llm" → samadhan` branch (deck/figure are special-cased ahead of it today; slides joins them — the lane KEY disambiguates among the `kind=="llm"` lanes).
2. **The `kind=="llm"` preflight** in `build()` is already lane-dispatched (F1 made it a dispatch on `line`): `figure → figure.preflight`, else `samadhan.preflight`. F2 adds `slides → slides.preflight(slug)` — chapter exists (`render.load_chapter`) + `notebooklm_client.configured()` (nlm present + authed) + the deck-format env knobs valid; **no StyleSeed requirement, no API-key requirement** (nlm holds the creds). Raises `FileNotFoundError`/`RuntimeError` BEFORE any intent is recorded (anti-wedge).
3. **The capture/changes gate** applies verbatim (`errors>0 or items==0 → changes`) AND F2's conservative default clause routes to `changes` whenever `SAMAGRA_SLIDES_AUTOCAPTURE` is off (default). This mirrors F1's `SAMAGRA_FIGURE_AUTOCAPTURE` clause exactly: `build()`'s `needs_review` gains `if line == "slides" and not config._env_bool("SAMAGRA_SLIDES_AUTOCAPTURE", False): needs_review = True`. When the owner opts in (`=1`), the standard llm gate applies (a `failed` deck already raised before capture, so an opted-in clean deck → `captured`).
4. **HTTP 403 (executive decision 4) — FREE.** The slides lane is `kind="llm"`, and `api_factory_build` already refuses `spec.kind in ("llm","mcd")` with **403** before calling `run.build`, while `api_factory_approve-seed` skips `spec.kind in ("llm","mcd")` children. So the slides lane is **structurally unreachable over HTTP at BOTH gates** with zero new code — the same property figure/samadhan enjoy. (No new `kind` is introduced; reusing `kind="llm"` is cleaner than a new kind and inherits the 403 automatically — executive decision 4's "whichever is cleaner".) This also means only the CLI ever holds the long synchronous lock (§3.0).

No new assignment status, no async pending state, no migration.

### 3.7 CLI + config

- CLI: no new subcommand. `factory plan textbook:<slug> --lane slides` uses the existing `plan(lane=...)`, then the existing `approve` / `approve-seed` / `build` / (optional) `publish`. (Reachable via the CLI only — the HTTP factory-run stepper cannot plan/build it, per §3.6.4.)
- `.env.example` gains a **NotebookLM slides block** mirroring the F1 image block:
  ```
  # --- NotebookLM slides (Phase F2, the slides lane) ---
  # Drives the `nlm` CLI (Google NotebookLM). NO SAMAGRA secret — nlm stores the
  # Google OAuth creds itself (run `nlm login`). configured() probes `nlm login
  # --check`. NO AUDIO, ever.
  SAMAGRA_NLM_BIN=                    # override the nlm executable path (default: nlm on PATH)
  SAMAGRA_SLIDES_FORMAT=             # detailed_deck (default) | presenter_slides
  SAMAGRA_SLIDES_LENGTH=             # default (default) | short
  SAMAGRA_SLIDES_DOWNLOAD_FORMAT=    # pdf (default) | pptx
  SAMAGRA_SLIDES_TIMEOUT=900         # max seconds to block on generation (S1 poll)
  SAMAGRA_SLIDES_POLL_INTERVAL=15    # seconds between studio-status polls
  SAMAGRA_SLIDES_EMBED_MAX=          # bytes; decks larger than this wrap as download-only (default 8MB)
  SAMAGRA_SLIDES_AUTOCAPTURE=        # 0 (default, every build -> changes) | 1
  SAMAGRA_LIVE_SLIDES_SMOKE=         # 1 to run the opt-in owner-run live smoke
  ```
- `requirements.txt`: **no new Python dependency** — the client shells to the external `nlm` binary (installed at `C:\Users\abc\.local\bin\nlm`), which is an owner-provisioned tool, not a pip package. A comment documents the external `nlm` dependency + that `nlm login` is an owner prerequisite.

---

## 4. Invariants (must HOLD; the review 34 checklist)

1. **No SAMAGRA secret; auth is nlm's.** F2 holds no key. `notebooklm_client` reads no `*_API_KEY`. `configured()` probes `nlm login --check` and parses stdout (NOT the exit code — pinned §3.3). A missing/expired auth → `configured()` False → `slides.preflight` refuses BEFORE recording build intent (no wedge). `__repr__` names the lane, never any creds.
2. **No new prod write path.** NotebookLM is an EXTERNAL owner-driven tool reached by an OUTBOUND subprocess call — a generation boundary, **NOT one of the 7 read-only source subsystems**, and never a write to them. The lane writes ONLY local files under `EXPORT_DIR` (+ the raw deck working copy) + append-only governance rows (via the unchanged `build()` path). The ephemeral notebook it creates/deletes is NotebookLM state in the owner's own Google account, not a SAMAGRA store.
3. **Publish gate untouched.** F2 only *produces* a local wrapper artifact; capture is `build()`'s existing gate, publish is the existing owner-gated G1 CLI. The default posture (`SAMAGRA_SLIDES_AUTOCAPTURE` off) routes every deck build to `changes` — the owner must act.
4. **DEC-8 adversarial-reviewer firewall — structural.** F2 runs NO model review and uses NO StyleSeed (§3.4/§3.5), so there is nothing that could receive the StyleSeed. Any future optional deck review must be chapter-anchored and StyleSeed-free.
5. **Advisory scoring never gates.** N/A — no style score for a deck.
6. **The 5 build() crash-safety guards unchanged.** The slides lane rides the existing `kind=="llm"` guards verbatim; only the preflight dispatch (§3.6.2) and one `needs_review` clause (§3.6.3) change — neither is a guard. Guard 3 (record `product_building` intent BEFORE the produce step) is load-bearing here: the produce step blocks for MINUTES, so a crash inside it must leave a reconcilable in-flight marker — exactly what the retryable rollback handles for this local-write lane.
7. **No governance migration.** Reuses `assignments.pipeline`/`seed_ref` + the existing `product_*` event verbs. No new table, no schema version bump, no state-machine change, no `pending` status (S1, §3.0).
8. **Retryable, never wedged.** The slides lane is a LOCAL-write lane (its only external effect — the ephemeral notebook — is torn down in a `finally` and is idempotent to recreate), so a `nlm`/NotebookLM/timeout failure records `product_build_failed`, rolls back the in-flight intent, and the assignment is retryable. Partial output from a failed build is overwritten on retry; a stale-file clear runs before writing the new set (§3.E, F1's precedent).
9. **The 7 source subsystems + the inward build() boundary stay read-only** except the local artifact write.
10. **NO AUDIO — ever (Chairman, absolute).** F2 calls ONLY `nlm slides create` / `download slide-deck` / `studio status` / `notebook create|delete` / `source add` / `login --check`. It NEVER calls `nlm audio`, `nlm video`, or any other studio create verb. Enforced by construction — the client exposes no audio/video method — and pinned by a test that the run helper is never invoked with an `audio`/`video` argv (T18).
11. **Structurally CLI-only over HTTP.** `kind="llm"` inherits the existing `/api/factory/build` 403 and `/api/factory/approve-seed` skip at both gates — the slides lane cannot be planned-to-build or approved over HTTP (§3.6.4). Pinned by T17.

---

## 5. Verification

### 5.1 Offline TDD matrix (no network, no `nlm` shell-out)

A **fake subprocess runner** scripts per-command `{stdout, stderr, returncode}` (create → notebook id, source add → ok, slides create → ok, studio status → pending×k then completed+aid, download → writes a tiny fake PDF, delete → ok), injected via `NotebookLMClient(runner=...)` and `build_slides(..., nlm=...)`. **No standing test shells out or touches Google**, mirroring `llm_client`/`image_client`'s injectable-fake discipline.

| # | Test | Asserts |
|---|---|---|
| T1 | `configured()` — authed stdout | `✓ Authenticated` in probe stdout → True |
| T2 | `configured()` — expired stdout, **exit 0** | `✗ Authentication Error` + returncode 0 → **False** (exit-code trap pinned) |
| T3 | `configured()` — nlm absent | missing executable → False, no raise |
| T4 | run helper never-leak | a non-zero `nlm` call raises RuntimeError naming the verb, echoing NO raw stderr blob / chapter text / notebook content |
| T5 | run helper argv, not shell | args passed as a list; chapter text is one argv element (no shell string) |
| T6 | deck-format env validation | unknown `SAMAGRA_SLIDES_FORMAT`/`LENGTH`/`DOWNLOAD_FORMAT` → RuntimeError at construction (fail-closed) |
| T7 | `poll_slides` — completes | pending×2 then completed → returns the artifact id |
| T8 | `poll_slides` — explicit failed status | NotebookLM `failed`/`error` → RuntimeError |
| T9 | `poll_slides` — timeout | never completes within `SAMAGRA_SLIDES_TIMEOUT` → TimeoutError |
| T10 | `build_slides` happy path (fake runner) | creates nb, adds text source, creates+polls+downloads deck, deletes nb; writes wrapper html + json + working deck; result keys present |
| T11 | wrapper html self-contained | deck embedded as a `data:` URI (or download-only card above `EMBED_MAX`); title/chapter HTML-escaped; NO external ref |
| T12 | ephemeral cleanup in `finally` | a mid-build raise (download fails) STILL calls `notebook delete`; a delete-failure logs + does NOT mask the primary raise |
| T13 | capture gate — autocapture OFF (default) | a clean build → `changes` (conservative default); `_assert_review_clean` passes on the synthetic owner-review verdict |
| T14 | capture gate — autocapture ON, clean deck | → `captured`; a `failed` deck raised before capture (retryable) |
| T15 | `validate_product` slides branch | wrapper html present but the embedded/working deck missing → ValueError; a legit result passes |
| T16 | publish compatibility | `publish --lanes slides` copies the wrapper html + json; `resolve_artifact(chapter,"slides","html")` serves it sha-verified |
| T17 | HTTP 403 / approve-seed skip | `kind="llm"` slides lane → `/api/factory/build` 403; `/api/factory/approve-seed` leaves it in-review |
| T18 | **NO-AUDIO invariant** | over a full `build_slides`, the fake runner is NEVER invoked with an `audio`/`video`/non-slides studio argv |
| T19 | build() retryable rollback | a `nlm`/timeout raise → `product_build_failed` recorded, intent rolled back, a second build succeeds |
| T20 | governance untouched (no migration) | full plan→approve→build→(changes/capture) leaves `PRAGMA user_version` UNCHANGED, adds NO new table, and does not alter the `assignments` state-machine — it only appends the expected events/rows a normal build writes (mirror F1's `test_figure_golden` no-migration assertion; do NOT assert whole-`governance.db` byte identity, since a build legitimately appends event rows) |
| T21 | `slides.preflight` | chapter absent → FileNotFoundError; nlm unconfigured → RuntimeError; **no StyleSeed, no API key required** |

### 5.2 Opt-in owner-run live smoke

`tests/test_slides_live_smoke.py`, gated on `SAMAGRA_LIVE_SLIDES_SMOKE=1` **AND** `notebooklm_client.configured()` (both required — interactive Google auth may be absent in headless/subagent/CI, and generation is slow/flaky, so the standing gate stays 100% offline and this NEVER runs by default). It runs one REAL chapter (e.g. `circular-motion`) end-to-end against live NotebookLM: create ephemeral notebook → add source → create deck → poll to completion → download → wrap → delete notebook, asserting a real deck file was written, the wrapper embeds it, and the ephemeral notebook is gone afterward. **This is the FIRST live validation of the NotebookLM subprocess boundary** (and the confirming check of the exact download format — PDF vs the `.txt` ambiguity, §3.C). **The merge does NOT depend on this run** (executive decision 5): it is an owner follow-up, because `nlm` auth cannot be assumed present in the merge/CI/subagent context.

### 5.3 Gates
- **pytest** green (current baseline 771 + the ~21 F2 tests), lone allowed skips = the opt-in live smokes (LLM + image + QX + slides).
- **vitest** unchanged (frontend untouched in F2 — the deck renders in the existing G2 reader's sandboxed iframe) + `tsc --noEmit` + `npm run build` green.

### 5.4 Codex pre-merge review 34 (REQUIRED)
A dedicated DEC-7-style review of the new **subprocess / NotebookLM async boundary** → `docs/codex-reviews/34-slides-lane-premerge.report.md`. Focus: the subprocess run helper (argv-list not shell string; per-call + total timeouts; never-leak error extraction that does not echo raw `nlm` stderr / notebook content); the `configured()` stdout-parse (NOT exit-code) auth probe; the S1 synchronous-poll bound + the retryable rollback on timeout; the ephemeral-notebook cleanup `finally` (no orphan-leak masking a success, no cleanup-failure converting success to rollback); the NO-AUDIO invariant (only slides verbs reachable); the publish-compatibility boundary (self-contained wrapper html, no directory/binary artifact leaking into G1/G2); and the HTTP-403 CLI-only property. Merge only after review 34 is GO (caveats remediated TDD) + a 4-lens review-gate adversarial pass, per house convention (D2/F1 precedent).

---

## 6. Retry / partial-output / cleanup story (design question E, consolidated)

Every external failure maps to either a fail-closed refusal BEFORE intent (anti-wedge) or a retryable rollback AFTER intent — never a partial capture:

| Failure | Where | Handling |
|---|---|---|
| `nlm` not present / not authed | `slides.preflight` (before intent) | `configured()` False → RuntimeError, refuses without recording build intent (no wedge). |
| chapter absent | `slides.preflight` (before intent) | `render.load_chapter` → FileNotFoundError, no intent recorded. |
| bad deck-format env | client construction (before intent) | RuntimeError at construct, refuses cleanly. |
| notebook-create / source-add failure | inside produce (after intent) | whole-build raise → `product_build_failed` → in-flight intent rolled back → retryable. The `finally` deletes the (possibly partly-created) notebook. |
| generation `failed`/`error` status | `poll_slides` (after intent) | RuntimeError → retryable rollback; `finally` deletes the notebook. |
| generation timeout | `poll_slides` (after intent) | TimeoutError (bounded by `SAMAGRA_SLIDES_TIMEOUT`) → retryable rollback; `finally` deletes the notebook. |
| download failure | inside produce (after intent) | whole-build raise → retryable rollback; `finally` deletes the notebook. |
| **notebook-delete failure** | `finally` (cleanup) | logged with the orphan notebook id (titled `SAMAGRA slides:` for owner pruning); does NOT mask the primary outcome, does NOT convert a success to a rollback. A leaked ephemeral notebook is harmless owner-pruneable state, never a correctness issue. |

**No resume; clean overwrite.** A retry re-runs `build_slides` from the top with a fresh ephemeral notebook. Deterministic filenames (`<slug>-slides.html/.json`, `<slug>-slides/deck.pdf`) are overwritten; a stale-clear of the `<slug>-slides/` working dir runs before writing the new deck (F1's precedent), so a shorter re-run leaves no orphan deck file. There is no partial-state to reconcile — the local artifact is safe to overwrite (the property that makes every local-write lane retryable), and the only external state (the ephemeral notebook) is torn down each run.

**Cost / latency note.** Each build = create + source-add + slides-create + N status-polls + download + delete `nlm` calls, plus a minutes-scale generation wait bounded by the timeout. The conservative `changes` default means the owner reviews the deck (and the cost/quality) before any auto-capture posture is enabled. Because the lane is HTTP-403'd, only a deliberate CLI Build ever incurs this — never a GUI double-click.

---

## 7. Open questions

None. The central fork (S1 vs S2) resolves to **S1** (§3.0); A–E resolve to ephemeral-per-build (A1), rendered chapter text (B1), self-contained wrapper HTML (C, zero G1/G2 change), owner-reviewed-only (D2), and the fail-closed/retryable failure map (E, §6). The one real codebase risk — G1/G2 publish only single html/json/docx files, not a binary deck — is resolved by the self-contained data-URI wrapper (§3.C) with a publish-compatibility regression (T16). The one live-CLI subtlety — `nlm login --check` exits 0 even when auth is expired — is resolved by the stdout-parse `configured()` (§3.3, T2). The one documentation ambiguity — `download slide-deck` per-command help says PDF/PPTX while the `--ai` summary line mentions `.txt` — is pinned to `--format pdf` with the owner-run live smoke as the confirming check (§3.C/§5.2), and the wrapper handles either shape without a publish-story change.
