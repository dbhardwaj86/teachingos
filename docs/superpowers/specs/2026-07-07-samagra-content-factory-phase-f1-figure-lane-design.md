# SAMAGRA Content Factory — Phase F1: the `figure` lane (image-gen physics figures)

**Status:** RATIFIED 2026-07-07 (orchestrator adjudication under the Chairman's full-auto Phase-F delegation — "go for phase F - full auto, carry to completion". Forks locked: A1 image-need briefs only · B1 Images API gpt-image-1 · C1 vision review recorded + `SAMAGRA_FIGURE_AUTOCAPTURE` default OFF (every figure build → `changes`) · D data-URI gallery html = the publishable single-file artifact · E no StyleSeed · F cap 6, whole-build-raise retryable.)

**Slice type:** the FIRST Phase-F heavy/external LLM lane. It rides the existing
`kind="llm"` synchronous build path (same envelope as the D2 samadhan lane) and adds
SAMAGRA's first **image-generation** network boundary. A dedicated Codex pre-merge review
of that boundary is REQUIRED — **review 33** (house convention: any new network/secrets
generation boundary gets a DEC-7-style review, precedent D2/review 27 and the LLM-provider
mini-slice/review 32).

---

## 1. Problem

The umbrella spec's lane table (`docs/superpowers/specs/2026-06-23-samagra-content-factory-design.md`
§3.1) parks a `figure` lane: `figure | image-gen | local PNG | async, external | F`. Phase D
proved the generative-lane shape end-to-end (samadhan: condition → generate → adversarial
ground-truth review → advisory score → local write → capture/changes gate), and the
LLM-provider mini-slice made the text call site provider-aware and live on OpenAI `gpt-5.5`.
Nothing yet emits an **image** artifact.

The physics-textbook corpus already tells us exactly which figures are missing. Across the
59 chapters, **52 `image-need` blocks in 40 chapters** carry an author-written `brief`
field — a detailed natural-language description of a diagram the author flagged as needed
but never drew (e.g. circular-motion's Coriolis-frame perspective, capacitance's cube→circuit
reduction, centre-of-mass's standard-solids CM gallery). These briefs are effectively
ready-made, owner-authored image-generation prompts. F1 turns them into rendered PNG figures
behind the same never-automated publish gate every other lane sits behind.

The hard truth F1 must design around: **raster image models are unreliable at physics
diagrams.** Labels get misspelled, vectors point the wrong way, geometry is subtly wrong
(a CM dot at `h/3` instead of `h/4`). F1 must therefore default conservative — a generated
figure is a *draft for owner eyes*, not an auto-captured teaching artifact.

---

## 2. Scope

### In
- New client module **`samagra/clients/image_client.py`** — the ONE image-generation call
  site, mirroring `llm_client.py`'s provider pattern (env `SAMAGRA_IMAGE_PROVIDER` default
  `openai`, per-provider default model, injectable fake SDK, key env-only never
  logged/repr'd, `configured()`, `required_key_var()`, fail-closed resolution,
  never-leak error extraction).
- New engine **`samagra/factory/figure.py`** — `build_figures(slug, *, image_client=None,
  vision_client=None)`: select figure targets from the chapter's `image-need` briefs →
  generate PNG(s) → vision-review each against its brief (DEC-8 analogue, refute-framed,
  fail-closed) → write a local figure directory + manifest JSON + printable gallery HTML →
  return a factory-compatible result dict.
- `lines.py`: register the `figure` lane (`kind="llm"`, `auto_fan=False`, prefix
  `textbook:`).
- `dispatch.py`: `run_line` routes the `figure` lane to the new engine; `validate_product`
  gains a binary-lane branch (existence/non-empty of the gallery html + at least one PNG,
  plus the llm review-clean gate reused).
- `build()`: the `figure` lane reaches the EXISTING `kind=="llm"` preflight-before-intent /
  capture-changes / rollback-retryable path with **no new branch** in the guard block
  (§3.6 explains the one preflight indirection).
- CLI: `factory plan textbook:<slug> --lane figure` already works via the existing
  `plan(lane=...)`; no new subcommand. `.env.example` + `requirements.txt` gain the image
  provider block.
- Tests: full offline TDD matrix (fake image + fake vision SDKs, no standing test hits the
  network or needs a key) + one opt-in live smoke gated on `SAMAGRA_LIVE_IMAGE_SMOKE`.

### Out
- **F2** (slides / NotebookLM) — a separate later spec. **No audio, ever** (Chairman).
- Any **async / pending** build state machine. F1 is strictly synchronous on the existing
  `kind="llm"` path (executive decision 2). A multi-image build that takes a minute runs
  inline exactly as an mcd or samadhan build does.
- Generating figures from `figure` blocks that already carry hand-authored `svg`, from
  `equation`/`callout`/`prose` blocks, or from a free-text prompt. F1's target set is the
  `image-need` briefs ONLY (§3.1). Widening the target set is a later slice + decision.
- **Publish/G1 integration for the figure directory** is scoped OUT of F1 as a *shipped
  capability* and handled explicitly (§3.4.4): F1 makes the artifact publish-**compatible**
  (a single gallery `.html` + sidecar `.json` that G1 already copies), and the PNG payload
  is embedded so no G1/G2 code needs to learn a new `png` kind or a directory artifact. A
  first-class multi-PNG publish surface, if ever wanted, is a G-phase follow-up.
- StyleSeed *learning loop* wiring (D3 `mine_deltas`) — figures are reviewed but do not feed
  `style_events` in F1.

---

## 3. Design

### 3.1 Figure-target selection (design question A)

**The corpus already carries the targets and the prompts.** A per-chapter census (all 59
chapters) found:

| block type | count | carries |
|---|---|---|
| `prose` | 2159 | html |
| `equation` | 1199 | tex |
| `callout` | 1040 | html + variant |
| `figure` | 663 | **hand-authored `svg`** + caption (already illustrated) |
| `subheading` | 370 | html |
| `image-need` | **52** (in 40 chapters) | **author-written `brief`** |

**Options weighed**
- **(A1) `image-need` briefs only.** Deterministic target = every block with
  `type=="image-need"`, in document order. The prompt is the author's `brief` verbatim
  (plus a small deterministic frame — chapter title, section title, and a fixed physics-
  diagram style preamble). These are the *only* blocks the author explicitly marked as a
  missing figure, and the `brief` is already a polished image prompt.
- **(A2) `figure`-block captions.** Re-illustrate the 663 existing `svg` figures from their
  `caption`. Rejected for F1: those figures already exist as clean vectors; regenerating
  them as raster risks *replacing correct hand-drawn geometry with a worse model guess*, and
  a caption ("RMS is the square-root of the average of v²(t)…") is a summary, not a drawing
  brief — the model would have to invent the composition.
- **(A3) LLM-built prompts.** Have `gpt-5.5` write an image prompt from an
  equation/callout/prose block. Rejected for F1: adds a second generative hop (cost + a new
  failure mode), and it is unnecessary while 52 owner-authored briefs sit unused. It is the
  natural *later* widening once the `image-need` set is exhausted.

**Recommendation → A1.** Select `image-need` blocks in document order; the figure prompt is
**deterministic** (`brief` verbatim + a fixed style/frame preamble — no LLM in the prompt-
build step). A chapter with zero `image-need` blocks (e.g. gauss-law) produces an **empty**
figure set, which build() routes to `changes` for owner attention (never a silent empty
capture — mirrors samadhan's `items==0 → changes` rule, §3.6).

**Per-build cap (cost bound).** `_FIGURE_CAP` (default **6**, env `SAMAGRA_FIGURE_CAP`)
caps figures per build; if a chapter has more than the cap `image-need` blocks, the first
`_FIGURE_CAP` in document order are generated and the manifest records
`capped: true` + the total. (Max observed in one chapter is small; the cap is a safety rail,
not a common truncation.) The prompt-build helper `_targets(content)` is PURE and unit-
tested against the frozen fixture with zero live dependency.

**Prompt shape (deterministic, per target):**
```
<fixed style preamble: "A clean, labelled physics diagram for a JEE/NEET
  textbook. Neutral line-art on a transparent/white background, one accent
  colour, legible labels. No photorealism.">
Chapter: <title>.  Section: <section title>.
Figure brief: <block.brief verbatim>
```
The preamble is a frozen module constant (change = a reviewed commit). No StyleSeed enters
the prompt (§3.5).

### 3.2 Generation mechanics (design question B)

**Installed SDK: `openai 2.44.0`** (confirmed in `.venv`). Two candidate APIs:

- **(B1) Images API — `client.images.generate(model="gpt-image-1", ...)`.** Purpose-built
  for text→image; returns a base64 PNG directly (`b64_json`), a small stable surface, no
  reasoning/tool plumbing.
- **(B2) Responses API `image_generation` tool.** Powerful (multi-turn, edits) but heavier;
  we do not need conversation or tool orchestration for a one-shot brief→PNG.

**Recommendation → B1: `images.generate` with `gpt-image-1`.** Concrete request shape,
pinned in `image_client.py`:
```python
resp = self._sdk.images.generate(
    model=self._model,              # default "gpt-image-1"; SAMAGRA_IMAGE_MODEL overrides
    prompt=prompt,                  # the deterministic per-target prompt (§3.1)
    size=self._size,                # default "1024x1024"; SAMAGRA_IMAGE_SIZE overrides
    quality=self._quality,          # default "medium"; SAMAGRA_IMAGE_QUALITY overrides
    n=1,
)
# never-leak extraction: pull b64_json -> raw PNG bytes; a response with no image
# data raises a concise RuntimeError that echoes NO prompt/key/content.
```
Output = **PNG bytes** written locally (§3.4). Env knobs: `SAMAGRA_IMAGE_MODEL`,
`SAMAGRA_IMAGE_SIZE` (validated against a fixed allow-set), `SAMAGRA_IMAGE_QUALITY`
(validated against `{"low","medium","high","auto"}`), all fail-closed at construction like
`SAMAGRA_LLM_EFFORT`. `_extract_png(resp)` is the image analogue of `llm_client._extract_json`:
refusal / empty / malformed → concise `RuntimeError`, never leaking the prompt or key. The
provider seam (`SAMAGRA_IMAGE_PROVIDER` default `openai`, unknown → `RuntimeError`) mirrors
`_provider_from_env`; only `openai` is implemented in F1 (the only key in the live `.env`),
but the seam is structural so a second backend is a later drop-in, exactly as the LLM slice did.

### 3.3 Adversarial review of images (design question C)

The never-silent-capture principle (a generated artifact is never captured without a
ground-truth check that could refute it) is load-bearing and must hold for images. But
raster physics diagrams are *frequently* subtly wrong, so the review must be honest about
what it can and cannot certify.

**Options weighed**
- **(C1) Vision review via `gpt-5.5` (the existing `llm_client`), refute-framed,
  fail-closed.** Send the generated PNG + its author `brief` + chapter section text to a
  vision-capable model asked to REFUTE: does the image match the brief; are the labels
  spelled correctly; is the geometry/physics right; are the vector directions correct?
  Verdict `ok`/`error` per figure, fail-closed (no explicit `ok` → `error`), exactly like
  samadhan. Cost: one extra model call per figure.
- **(C2) Caption/metadata-only review.** Cheap, but it certifies nothing about the actual
  pixels — precisely where image models fail. Rejected: it would rubber-stamp a wrong
  diagram.
- **(C3) Owner-only review — every figure lands as `changes`.** Zero model cost, maximally
  conservative: NO figure is ever auto-captured; the owner eyeballs every one in the gallery
  before it can be published.

**Recommendation → C1 + a conservative default that behaves like C3 until proven.** Run the
vision review (C1) so the reviewer *records* a per-figure verdict and rationale in the
artifact (the audit trail + a real refutation attempt). BUT gate capture conservatively:
a **new env flag `SAMAGRA_FIGURE_AUTOCAPTURE` (default `0`/off)** means that in F1's default
posture **every figure build routes to `changes`** for owner review regardless of the
vision verdict — the vision pass is advisory-recorded, not gating, until the owner has seen
the failure-rate for their own corpus. When the owner opts in (`=1`), the standard llm gate
applies (`errors>0` or `items==0` → `changes`, else `captured`). This defaults to the
safest posture (C3-equivalent) while still capturing the vision reviewer's findings, and it
lets the owner graduate to auto-capture once they trust it — no code change, just a flag.

**DEC-8 firewall (structural).** The vision reviewer is anchored ONLY to chapter ground
truth (the `brief` + section text + the image) and **NEVER receives the StyleSeed** — the
figure prompt does not use StyleSeed at all (§3.5), so there is nothing to leak, and the
review call goes through `llm_client`'s existing StyleSeed-free `review_*` path. A new
`llm_client.review_figure(png_bytes, brief, section_text)` is added (vision input, the
`_REVIEW_*` never-StyleSeed contract), reusing the provider adapter. It uses a new strict
schema `{"verdicts":[{"idx","verdict":"ok"|"error","rationale"}]}` (same shape as
`_REVIEW_SCHEMA`).

### 3.4 Artifact shape (design question D)

#### 3.4.1 Files written under `EXPORT_DIR/<slug>/`
Mirroring deck/samadhan's `<slug>/` convention:
```
EXPORT_DIR/<slug>/
  <slug>-figures/fig-01.png            # generated PNG, zero-padded index in document order
  <slug>-figures/fig-02.png
  ...
  <slug>-figures.json                  # manifest sidecar (see below)
  <slug>-figures.html                  # printable gallery (figure + brief + verdict per item)
```
The gallery HTML embeds each PNG as a **data URI** (`data:image/png;base64,...`) so the
single `.html` file is fully self-contained — no external image references, consistent with
the sandboxed-iframe CSP the G2 reader already enforces on published html. Untrusted text
(the `brief`, the reviewer rationale) is HTML-escaped at the boundary (the C1 deck lesson);
the JSON keeps raw text + raw base64.

#### 3.4.2 Result dict (returned to build())
```python
{"variant": "figure",
 "html": ".../<slug>-figures.html",   # the gallery — build()/validate_product/publish key
 "json": ".../<slug>-figures.json",   # sidecar manifest
 "figures": [{"idx","png","brief","section","verdict","rationale","sha256"} ...],
 "items": <n_targets>,                # count of image-need briefs attempted
 "errors": <n_reviewer_errors>,       # for the llm capture/changes gate
 "verdicts": [...],                   # for _assert_review_clean
 "capped": <bool>}
```
`items`/`errors`/`verdicts` are the SAME keys the existing `kind=="llm"` capture gate and
`_assert_review_clean` already consume — so build()'s llm branch needs **no new field
awareness** (§3.6).

#### 3.4.3 `validate_product` / the answer-leak guard (design question D, cont.)
- The answer-leak guard (`_assert_no_answer_leak`) is `kind=="qx"`-scoped and stays a no-op
  for `kind=="llm"` — figures carry no QX answer markup. No change there.
- `_assert_review_clean` is `kind=="llm"`-scoped and already applies to the figure lane
  unchanged (asserts integer `errors`/`items` and, when `items>0`, a non-empty `verdicts`
  list). Reused verbatim.
- **New binary check in `validate_product`.** Today it hard-requires `result["html"]` to be
  a non-empty file — the figure gallery satisfies this. F1 ADDS, for the figure lane, an
  assertion that **at least one PNG file exists on disk and is non-empty** (so a build that
  produced a gallery but zero image files is refused, not captured). This is a small,
  additive, lane-scoped branch (`_assert_figures_present`) keyed on `variant=="figure"` —
  it does not alter the existing html check for any other lane.

#### 3.4.4 Publish / G1 handling — the real risk, resolved (design question D, cont.)
G1's `publish.run._captured_publishable` copies exactly the file keys
`("html","json","docx")` from the result and **requires `result["html"]` to be a single
existing file**; the G2 read surface only knows kinds `html`/`json`/`docx`. **A directory of
PNGs is not a first-class publish citizen today.** F1 handles this WITHOUT touching G1/G2:

- The publishable, self-contained artifact is the **gallery `.html`** (PNGs embedded as data
  URIs) + the `.json` sidecar. Both are single files under the keys G1 already copies. So
  `publish textbook:<slug> --lanes figure` works with **zero G1/G2 change** — the owner
  publishes the gallery and the reader renders it in the existing sandboxed iframe, images
  and all.
- The **loose `fig-NN.png` files are intentionally NOT published** in F1 (they are the
  working/debuggable copies under EXPORT_DIR). The published contract is "one self-contained
  gallery html per chapter's figure lane." This is stated as an explicit F1 boundary, not an
  oversight.
- A first-class multi-PNG published surface (a `png` kind, a directory artifact, per-figure
  deep links) is a deliberate **G-phase follow-up**, out of F1 scope. F1 must add a
  regression test proving `publish --lanes figure` succeeds on the gallery html and that the
  G2 `resolve_artifact(chapter,"figure","html")` serves it sha-verified.

### 3.5 StyleSeed conditioning (design question E)

**Recommendation → NO StyleSeed on the figure prompt (minimal).** StyleSeed is a *prose
voice* profile (voice · sequencing · analogy · rigor · selection priors) extracted from
chapter text; none of it describes how to draw a labelled diagram. Conditioning the image
prompt on it would add noise, not signal, and — critically — it keeps the DEC-8 reviewer
firewall trivially structural (there is no StyleSeed anywhere near the figure lane, so the
vision reviewer cannot possibly receive it). The figure preflight therefore does NOT require
a committed StyleSeed (unlike samadhan) — a chapter can produce figures with no StyleSeed
present. `style_fit` scoring is omitted for this lane (a diagram has no prose to score); the
manifest records no style score.

### 3.6 build() integration — the existing `kind="llm"` path, one indirection (design decision 2)

The figure lane is `kind="llm"`, so it flows through the guard block build() already has,
with the SAME five crash-safety guards and the SAME retryable-rollback semantics
(local-write lane → a transient image-API failure rolls back the in-flight intent → the
assignment is retryable, never wedged). The only touch points:

1. **`run_line`** gains `if spec.key == "figure": return figure.build_figures(slug)` before
   the generic `kind=="llm" → samadhan` branch (both are `kind=="llm"`; the lane KEY
   disambiguates, exactly as `deck` is special-cased ahead of the generic path today).
2. **The `kind=="llm"` preflight** in build() currently hard-calls
   `samadhan.preflight(slug)`. F1 makes this **lane-dispatched**: `figure` → a new
   `figure.preflight(slug)` (chapter exists + image client configured + vision client
   configured; **no StyleSeed requirement**); `samadhan` → `samadhan.preflight(slug)`
   unchanged. This is a small dispatch table keyed on `a["pipeline"]`, not a new guard.
3. The **capture/changes gate** (`errors>0 or items==0 → changes`) applies verbatim; F1's
   default posture additionally routes to `changes` whenever `SAMAGRA_FIGURE_AUTOCAPTURE`
   is off (§3.3) — implemented inside `figure.build_figures` by reporting the vision
   `errors` count truthfully AND a `needs_owner` intent the engine encodes as `errors>0`
   when autocapture is off is **rejected** as a hack; instead build()'s `needs_review`
   computation gains an explicit, minimal clause: `figure` lane with autocapture off →
   `changes`. This keeps the gate honest (the reviewer's real error count is preserved in
   the artifact) while defaulting conservative.

No new assignment status, no async pending state, no migration.

### 3.7 CLI + config

- CLI: no new subcommand. `factory plan textbook:<slug> --lane figure` uses the existing
  `plan(lane=...)` (which validates the `textbook:` prefix against the lane), then the
  existing `approve` / `approve-seed` / `build` / (optional) `publish`.
- `.env.example` gains an **image block** mirroring the LLM block:
  ```
  # --- Image generation (Phase F1, the figure lane) ---
  SAMAGRA_IMAGE_PROVIDER=            # openai (default) — the only backend in F1
  # OPENAI_API_KEY reused (same key as the LLM lane)
  SAMAGRA_IMAGE_MODEL=              # override; default gpt-image-1
  SAMAGRA_IMAGE_SIZE=               # override; default 1024x1024
  SAMAGRA_IMAGE_QUALITY=            # override; default medium
  SAMAGRA_FIGURE_CAP=               # override; default 6 figures/build
  SAMAGRA_FIGURE_AUTOCAPTURE=       # 0 (default, every build -> changes) | 1
  SAMAGRA_LIVE_IMAGE_SMOKE=         # 1 to run the opt-in live smoke
  ```
- `requirements.txt` already pins `openai>=2.32`; F1 bumps the comment to note image use
  (no new dependency — `images.generate` ships in the installed 2.44.0).

---

## 4. Invariants (must HOLD; the review 33 checklist)

1. **Keys env-only.** `OPENAI_API_KEY` read only from the gitignored `.env`, never
   logged / repr'd / committed. `image_client.__repr__` names provider + model only (like
   `LLMClient`). Missing key → `RuntimeError` at construction; `configured()` False →
   preflight refusal BEFORE recording build intent (no wedge).
2. **No new prod write path.** The image API is an OUTBOUND generation call, never a write
   to the 7 read-only source subsystems. The lane writes ONLY local files under `EXPORT_DIR`
   + append-only governance rows (via the unchanged build() path).
3. **Publish gate untouched.** F1 only *produces* + *reviews* a local artifact; capture is
   build()'s existing gate, publish is the existing owner-gated G1 CLI. The default posture
   routes every figure build to `changes` (owner must act).
4. **DEC-8 adversarial-reviewer firewall — structural.** The vision reviewer is anchored
   ONLY to chapter ground truth (brief + section text + the image) and NEVER receives the
   StyleSeed. The figure prompt uses no StyleSeed at all, so there is nothing to leak.
5. **Advisory scoring never gates.** N/A here — no style score for figures.
6. **The 5 build() crash-safety guards unchanged.** The figure lane rides the existing
   `kind=="llm"` guards verbatim; only the preflight indirection (§3.6.2) and one
   `needs_review` clause (§3.6.3) change, neither of which is a guard.
7. **No governance migration.** Reuses `assignments.pipeline`/`seed_ref` + the existing
   `product_*` event verbs. No new table, no schema version bump, no state-machine change.
8. **Retryable, never wedged.** The figure lane is a LOCAL-write lane, so a transient
   image-API failure records `product_build_failed` and rolls back the in-flight intent —
   the assignment is retryable (existing build() rollback path). Partial output from a
   failed multi-image build is overwritten on retry (§6).
9. **The 7 source subsystems + the inward build() boundary stay read-only** except the local
   artifact write.

---

## 5. Verification

### 5.1 Offline TDD matrix (no network, no key)
A **fake image SDK** (returns a fixed tiny base64 PNG) and a **fake vision client** (returns
a scripted verdict list), injected via `build_figures(..., image_client=, vision_client=)`
and `image_client.ImageClient(sdk=...)` — so **no standing test hits the network or needs a
key**, mirroring `llm_client`'s injectable-fake discipline.

| # | Test | Asserts |
|---|---|---|
| T1 | `_targets` over a frozen fixture chapter (image-need briefs + one no-brief block) | selects only `image-need` blocks, in document order, prompt = preamble + brief |
| T2 | `_targets` on a chapter with zero image-need blocks | returns `[]` (drives the empty → changes path) |
| T3 | `_FIGURE_CAP` truncation | at most cap targets; `capped:true` + total recorded |
| T4 | `build_figures` happy path (fake SDKs, all verdicts ok) | writes N PNGs + gallery html + json; result keys present; PNGs non-empty |
| T5 | gallery html | each PNG embedded as a data URI; brief + rationale HTML-escaped; no external image ref |
| T6 | `image_client` provider resolution | unknown provider → RuntimeError; default openai; unknown size/quality → RuntimeError (fail-closed) |
| T7 | `image_client._extract_png` | refusal / empty / malformed response → concise RuntimeError, NO prompt/key echo |
| T8 | `configured()` / `required_key_var()` | provider-aware; missing key → False; unknown provider → False (no raise in configured) |
| T9 | `figure.preflight` | chapter absent → FileNotFoundError; image/vision unconfigured → RuntimeError; **no StyleSeed required** |
| T10 | DEC-8 firewall | `review_figure` receives no StyleSeed argument (signature + call-site assertion) |
| T11 | vision `error` verdict fail-closed | a figure with no explicit `ok` → counts as error in `errors` |
| T12 | build() capture gate — autocapture OFF (default) | clean build → `changes` (conservative default) |
| T13 | build() capture gate — autocapture ON, all ok | → `captured`; any error or empty → `changes` |
| T14 | build() retryable rollback | image-API raise → `product_build_failed` recorded, intent rolled back, second build succeeds |
| T15 | `validate_product` binary branch | gallery html present but zero PNG files → ValueError |
| T16 | publish compatibility | `publish --lanes figure` copies the gallery html + json; `resolve_artifact(chapter,"figure","html")` serves it sha-verified |
| T17 | governance untouched | full plan→approve→build→(changes/capture) leaves `assignments` schema + `governance.db` byte-consistent (no migration) |

### 5.2 Opt-in live smoke
`tests/test_figure_live_smoke.py`, gated on `SAMAGRA_LIVE_IMAGE_SMOKE=1` (a flag, not
key-only, so the standing gate stays offline even once `.env` carries a key). Builds figures
for one real chapter with `image-need` briefs (e.g. `circular-motion`), asserts ≥1 real PNG
written + a real vision verdict recorded + the gallery renders. This is the FIRST live
validation of the image boundary (parallels the LLM slice's first live samadhan smoke).

### 5.3 Gates
- **pytest** green (current baseline 713 + the ~17 F1 tests), lone allowed skips = the
  opt-in live smokes (LLM + image).
- **vitest** unchanged (frontend untouched in F1) + `tsc --noEmit` + `npm run build` green.

### 5.4 Codex pre-merge review 33 (REQUIRED)
A dedicated DEC-7-style review of the new image-generation **network/secrets boundary** →
`docs/codex-reviews/33-figure-lane-premerge.report.md`. Focus: key handling (never
logged/repr'd), never-leak `_extract_png`, the DEC-8 no-StyleSeed firewall on the vision
reviewer, the conservative-default capture gate, the local-only write path, and the
publish-compatibility boundary (no accidental directory-artifact assumption leaking into
G1/G2). Merge only after review 33 is GO (caveats remediated TDD) + a review-gate adversarial
pass, per house convention.

---

## 6. Retry / partial-output story (design question F)

- **Per-build cap** `_FIGURE_CAP=6` (env `SAMAGRA_FIGURE_CAP`), default **size**
  `1024x1024`, default **quality** `medium`, all env-tunable and validated fail-closed.
- **Partial multi-image failure.** `build_figures` generates figures in document order. If
  the K-th image call raises, the whole `build_figures` raises (it does not return a partial
  result), which drops into build()'s `except` for a local-write lane: `product_build_failed`
  is recorded, the in-flight intent is rolled back, and the assignment is **retryable**.
- **No resume; clean overwrite.** A retry re-runs `build_figures` from the top and
  **overwrites** `fig-NN.png` / the gallery / the json (deterministic filenames in document
  order). There is no partial-state resume to reconcile — the local artifact is safe to
  overwrite (the same property that makes every local-write lane retryable). To avoid leaving
  orphan PNGs from a shorter successful re-run, `build_figures` clears the
  `<slug>-figures/` directory of stale `fig-*.png` before writing the new set (a pure local
  cleanup, no external state).
- **Cost note.** Each figure = one image call + one vision-review call. With the cap at 6,
  the worst case is 12 model calls per build — bounded and owner-visible. The conservative
  `changes` default means the owner reviews the cost/quality before any auto-capture posture
  is enabled.

---

## 7. Open questions

None. A–F are resolved above; the one real codebase risk (publish/G1 treats artifacts as
single html/json/docx files, not a PNG directory) is resolved by the self-contained
data-URI gallery + the explicit "loose PNGs not published in F1" boundary (§3.4.4), with a
publish-compatibility regression pinning it (T16).
