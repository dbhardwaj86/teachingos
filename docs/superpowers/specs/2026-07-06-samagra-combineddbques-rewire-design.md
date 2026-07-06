# SAMAGRA — combinedDBQues question-bank rewire (Slice R) — design

- **Date:** 2026-07-06
- **Status:** PROPOSED (Chairman review pending; design approach B approved in-session with standing delegation for non-critical rulings)
- **Driver:** Chairman directive 2026-07-06 — "SAMAGRA's question bank should use `C:\SandBox\claude_khanak_box\combinedDBQues` as its source." Run evidence from the first GUI-driven throughput run (same day): the old QX corpus served Q1≡Q2 duplicates for the gauss-law paper (only 2 exact hits) and was cold-slow (28–48s vs the 30s client timeout).
- **Review gate:** DEC-7-style dedicated Codex pre-merge review (this slice touches the read-only firewall's QX seam) + adversarial multi-lens final review, per house convention.

## 1. Context

Two question engines exist on this machine:

| | Old QX | combinedDBQues |
|---|---|---|
| Root | `C:\SandBox\gpt_box\gpt-extract-ques` | `C:\SandBox\claude_khanak_box\combinedDBQues` |
| Port | 8783 (task `QX Autostart`) | **8790** (their RUNBOOK hard rule; no autostart task yet) |
| Corpus | 67k mixed-subject | **48,589 physics-only**, 4 sources merged, LLM-validation mid-flight |
| Chapters | free-text | 30 canonical NCERT `chapter_id`s (`physics.c11.laws_of_motion` style) |
| Concepts | 86 (`builder.sqlite`) | 128 (`unified_builder.sqlite`, same table shapes) |
| API | `GET /api/qsearch` | **identical contract** — their `json_search.py` is documented "for the SAMAGRA OS Questions app" |

combinedDBQues is a fork of the same QX engine: response shape (`{results,total,page,page_size,mode,degraded,facets,error?}`; result rows `{q_uid,slug,q_type,subject,chapter,difficulty,snippet,html}`), KaTeX `data-tex` spans, `/asset?slug=&id=` figures, and the answer-render markers (`class="answer"`, `answer-label`) are all identical. The swap is therefore a **source repoint + retrieval upgrade**, not a contract migration.

Known source properties that shape this design:

- **Duplicates:** exact-dup detection only (8,114 clusters, 18,960 member rows); their DECISIONS.md defers serve-path collapse, and `/api/qsearch` results do NOT carry `cluster_hash`. Consumer must dedupe.
- **Live corpus:** WAL mode, staged validation pipeline mutating in place, counts still climbing. Their RUNBOOK rule: consumers read via HTTP; any direct file access must be `mode=ro`.
- **Taxonomy gap:** samagra's 59 kebab-case textbook slugs (`circular-motion`, `gauss-law`) are NOT combinedDBQues chapters; they map into the 30 dotted NCERT `chapter_id`s (e.g. `gauss-law` → `physics.c12.electric_charges_and_fields`), with the old slug-like names living one level down as free-text concept labels.

## 2. Decision to pin (proposed DEC-15)

1. combinedDBQues is **read-only** for samagra: the HTTP `/api/qsearch` + `/asset` surface for serving, and direct sqlite strictly `mode=ro` and only for the manual `coverage-build`. Samagra never writes to any combinedDBQues file or endpoint.
2. **No new write path** anywhere in samagra: the slice changes where questions come FROM, never where anything goes TO. The guarded `build()` boundary, its five crash-safety guards, and the never-automated publish gate are untouched.
3. The **answer-leak guard stays mandatory** for `kind="qx"` lanes; the existing `_ANSWER_MARKERS` set transfers verbatim (fork renders identical markers). Any future marker drift in combinedDBQues re-opens this decision.
4. **Old 8783 is retired from samagra defaults** (config only — the old server itself belongs to another project and is not touched). Rollback to it is two env lines.
5. The chapter mapping (`chapter_map.json`) is a **git-committed, owner-curated** artifact — the same review pattern as `concept_aliases.json`.

## 3. Architecture

```
                     ┌───────────────────────────────┐
                     │ combinedDBQues (:8790)         │
                     │ app/gui/qx_browser.py          │
   HTTP (read-only)  │  GET /api/qsearch  GET /asset  │
  ┌──────────────────┤                                │
  │                  │ app/qx/unified_builder.sqlite ─┼── direct mode=ro read,
  │                  │ app/qx/unified_content.sqlite  │   coverage-build only
  │                  └───────────────────────────────┘
  ▼
 samagra
  ├─ clients/qx_client.py      (unchanged logic; base URL now :8790)
  ├─ factory/paper.py          (chapter-filtered retrieval + dedupe; guard unchanged)
  ├─ factory/chapter_map.py    (NEW pure module: load/validate chapter_map.json)
  ├─ api/app.py /api/questions (unchanged — same payload contract)
  ├─ adapters/qx.py            (summary/artifacts now read unified_content.sqlite)
  └─ factory/coverage/concepts.py (same SQL; now against unified_builder.sqlite)
```

## 4. Config changes (`samagra/config.py`)

| Constant | New default | Env override |
|---|---|---|
| `COMBINED_DB_ROOT` (new) | `C:\SandBox\claude_khanak_box\combinedDBQues` | `SAMAGRA_COMBINED_DB_ROOT` |
| `QX_SERVER_URL` | `http://127.0.0.1:8790` | `SAMAGRA_QX_SERVER_URL` (existing) |
| `QX_BUILDER_DB` | `COMBINED_DB_ROOT/app/qx/unified_builder.sqlite` | via `SAMAGRA_COMBINED_DB_ROOT` |
| `QX_CONTENT_DB` | `COMBINED_DB_ROOT/app/qx/unified_content.sqlite` | via `SAMAGRA_COMBINED_DB_ROOT` |
| `CHAPTER_MAP` (new) | `REPO_ROOT/chapter_map.json` | none (committed artifact) |

Constant NAMES (`QX_*`) are kept — every consumer and test keys on them, and the serving engine is still the QX engine (a fork). `GPT_BOX`/`QX_ROOT` stay for any legacy references but no longer feed the question path. **Rollback = `SAMAGRA_QX_SERVER_URL=http://127.0.0.1:8783` + `SAMAGRA_COMBINED_DB_ROOT` pointing at the old root** (or simply unsetting the new default via env) — documented in `.env.example`.

`qx_guard` (SSRF/loopback allowlist) is unchanged — 8790 is loopback.

## 5. Chapter mapping (`chapter_map.json` + `samagra/factory/chapter_map.py`)

Committed JSON at repo root:

```json
{
  "circular-motion":  {"chapter_id": "physics.c11.laws_of_motion",                "chapter": "Laws of Motion"},
  "gauss-law":        {"chapter_id": "physics.c12.electric_charges_and_fields",  "chapter": "Electric Charges and Fields"},
  "...59 rows total": {}
}
```

- One row per textbook chapter slug (the 59 dirs under `TEXTBOOK_CHAPTERS`). Values must be canonical combinedDBQues `chapter_id`s (validated against `build/taxonomy/physics.json` vocabulary at test time, hard-coded fixture copy — no live dependency in unit tests).
- `chapter_map.load()` (pure): parse + validate shape; unknown slug → `None` (caller falls back, §6). Many-to-one is expected (several textbook slugs map into one NCERT chapter).
- Initial curation: drafted mechanically (taxonomy crosswalk + label matching), ambiguous rows flagged in the PR for the Chairman's eyeball. Curation errors are content-quality bugs, never safety bugs (the answer guard is downstream of retrieval).

## 6. Paper lane retrieval + dedupe (`samagra/factory/paper.py`)

**Retrieval** (replaces bare `q = slug.replace("-", " ")`):

1. `entry = chapter_map.load().get(slug)`.
2. If mapped: `client.search(q="", mode="exact", chapter=entry["chapter"], page=1)` — chapter-scoped listing. (The facet param filters on the `chapter` display string in `search_index`; exact param semantics **verified against the live :8790 server at plan time** — if empty-`q` listing is unsupported, the fallback below becomes the primary and this spec's §12 records the finding.)
3. Fallback (unmapped slug, or chapter-scoped call returns 0): today's behavior — `client.search(q=slug.replace("-", " "), mode="exact", page=1)`.

**Dedupe** (new `_dedupe_results(results)`, pure): normalize each result's text projection (strip tags from `html`, collapse whitespace, lowercase — mirrors combinedDBQues's own `dupes.py` normalization), drop rows whose projection was already seen; projections under 40 chars are never treated as duplicates (their own generic-text threshold). Runs BEFORE the drill `[:_DRILL_SIZE]` slice so a drill is 8 *distinct* questions. Deterministic, order-preserving.

**Unchanged:** `_assert_no_answer_leak` + `_ANSWER_MARKERS` (dispatch.py) verbatim; asset absolutization via `questions_proxy.absolutize_assets` (now absolutizes to :8790); QX-down ⇒ `ValueError` before any write (message updated to name :8790 and the combinedDBQues runbook); `_DRILL_SIZE=8`; `_TIMEOUT=30` (bump only on live-latency evidence at plan time).

## 7. Questions app + adapter

- `GET /api/questions` proxy, frontend Questions app, sanitizer, KaTeX handling: **zero changes** — identical payload contract. Facets improve automatically (physics-only subjects, 30 canonical chapters).
- `adapters/qx.py` (`QXAdapter.summary()/artifacts()/search_questions()`): same table names exist in `unified_content.sqlite`/`unified_builder.sqlite`; paths repoint via §4 config. Dashboard counts switch to the unified corpus.

## 8. Concept spine + coverage graph

- `coverage/concepts.py` SQL runs as-is against `unified_builder.sqlite` (`concept`/`question_concept`/`search_index`, dotted `physics.%` chapter_ids, `concept.size` demand, `paper_count` via `search_index.slug`). 86 → **128 concepts**.
- `coverage/build.py` provenance hashing (`qx_builder_sha` = sha256 of one file) still works.
- Post-swap owner-CLI run: `samagra factory coverage-build` — expected: more edges/cells/gaps; residual no-pointer concepts printed by name.
- `concept_aliases.json` re-curated against the 128 new labels in the same slice (closes the polarisation/radioactivity/transistors residue — their labels may differ in the new concept list; curation happens against reality, not assumption).

## 9. Ops (same slice)

1. **Durable serving:** new logon scheduled task `COMBINEDDB-QX` — `cd <COMBINED_DB_ROOT>\app && PORT=8790 python -X utf8 gui\qx_browser.py` (mirrors `QX Autostart`/`SAMAGRA-OS`). Old `QX Autostart` task left untouched.
2. **LAN demo mode** (Chairman ruling 2026-07-06: local-only, WiFi demos on other devices): today the server binds `127.0.0.1` — unreachable from LAN. Add opt-in `SAMAGRA_BIND_HOST` (default `127.0.0.1`; demo `0.0.0.0`), document `SAMAGRA_PRATHAM_COOKIE_SECURE=0` (Secure cookies die on non-localhost http, so LAN sign-in needs it) and the one-time Windows firewall allow rule. Origin gate already fail-closes non-loopback mutating routes, so LAN devices get read surfaces + student login only — the operator surface stays loopback-gated. Documented as DEMO mode, not a deploy.
3. **Docs:** `docs/deploy-tunnel.md` QX-sidecar section rewritten for :8790/combinedDBQues; `.env.example` new block (`SAMAGRA_COMBINED_DB_ROOT`, rollback lines, bind/cookie demo lines).

## 10. Error handling

- HTTP path: existing graceful shapes proven — Questions app returns 200 + `error` body; paper lane refuses cleanly pre-write and stays retryable (proven live 2026-07-06).
- Live-corpus mutation: HTTP serving is their pipeline's concern (WAL readers see consistent snapshots); `coverage-build`'s existing corrupt-db catch covers the direct-read path.
- Unmapped chapter slug: falls back to text query (§6) — a paper still builds; mapping gaps surface as a content-quality review item, not a failure.
- combinedDBQues down: identical posture to QX-down today (clean refusal naming the runbook command).

## 11. Testing

- **Unchanged contract pins keep passing:** `test_qx_client`, `test_qx_guard`, `test_questions_proxy`, `test_api_questions*`, `test_factory_paper` (fakes carry the same shapes), `test_coverage_*` (fixture schema already matches unified tables).
- **New units:** `chapter_map.load()` (shape validation, unknown-slug None, all 59 slugs present, chapter_ids ∈ taxonomy fixture); `_dedupe_results` (drops exact dupes, keeps order, respects <40-char threshold, dedupe-before-drill-slice pinned on the on-disk artifact); paper retrieval branching (mapped → chapter-filtered, unmapped/0-hit → fallback query) via fake client asserting params.
- **Config tests:** new defaults + env overrides + rollback path.
- **Golden thread (live, isolated temp governance store):** one chapter → paper + drill against the real :8790 server — asserts >2 questions for gauss-law-class chapters, zero duplicate projections, answer-free artifacts, KaTeX spans present, assets absolutized to :8790.
- **Full gates:** pytest + vitest + tsc + build; then dedicated Codex pre-merge review (the firewall-seam DEC-7 convention) + 4-lens adversarial final review; remediate TDD.

## 12. Plan-time verifications (recorded here, resolved in the plan)

1. Does `/api/qsearch` on :8790 accept empty `q` with a `chapter` filter (listing mode)? Determines §6 primary vs fallback.
2. Which value does the `chapter` param match — display `chapter` or `chapter_id`? (Spec assumes display string; verify.)
3. Live latency of :8790 queries (timeout evidence).
4. Whether `search_index.chapter` display names align 1:1 with `taxonomy.py` names (chapter_map validation vocabulary).

## 13. Out of scope

- **Phase F** (image-gen figures + slides lanes — Chairman-ruled order) — separate spec after this slice lands.
- **LLM provider flexibility** (OpenRouter/OpenAI-compatible keys for the samadhan lane) — separate small slice; touches the DEC-7-reviewed D2 generation boundary, so it gets its own mini-design + review addendum. Folded into the Phase F design (both need provider/cost plumbing).
- Dedupe-at-source (serve-path collapse) — combinedDBQues's own deferred decision; samagra's client-side dedupe is independent of it and stays valid either way.
- `/learn` public deploy — Chairman ruling: local-only until full build + testing.
- Old QX server/repo changes — not samagra's asset.

## 14. Rollback

Two env lines (`SAMAGRA_QX_SERVER_URL` → :8783, `SAMAGRA_COMBINED_DB_ROOT` → old root) restore the old engine end-to-end; `chapter_map.json` unknown-slug fallback means the old free-text query path still exists in code. `concept_graph.db` is rebuildable from either source.
