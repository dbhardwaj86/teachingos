# SAMAGRA Content Factory — Phase G4: the adaptive student twin (v1) — Design

**Status:** PROPOSED (forks ruled by a 3-design × adversarial-judge deliberation, workflow
run `wf_df1f8da3-4d4`, 2026-07-05 — every ruling below is reversible by Chairman veto before
or during implementation).
**Author:** Claude (Fable 5), synthesizing the judge directive.
**Depends on:** G1 published corpus (`published/` + manifest) · G2 `/learn` reader ·
G3 identity (`pratham.db` students/sessions, session cookie) · Phase E coverage graph
(`concept_graph.db`, read-only).
**Implements:** the "adaptive/personalized selection + progress tracking" slice that G2 §11
and the umbrella spec's Phase-G row explicitly deferred to G4.

---

## §0 Context

The PRATHAM arc so far: G1 made `published` a durable owner-gated state; G2 gave students a
public read-only reader at `/learn`; G3 gave them optional identity (owner-minted enrollment
codes → opaque sessions in a physically isolated `pratham.db`). The reader today treats every
signed-in student identically to an anonymous one — identity buys nothing yet.

G4 v1 closes the smallest loop that deserves the name "twin": **the student acts → their
state changes → what SAMAGRA recommends to them changes.** One explicit action ("Mark done"
on the artifact they are viewing), one deterministic recommendation surface ("What's next",
ranked by concept demand over the published corpus, minus what they've done).

Everything here degrades gracefully to empty: the live stores currently hold 0 students, 0
published chapters, and a rebuildable `concept_graph.db` — every endpoint and UI state must
be valid (never a 500, never a crash) in that world.

## §1 Goal

Give a signed-in student per-`(chapter, lane)` progress marks and a deterministic,
demand-weighted "what's next" queue over the published corpus — as SAMAGRA's **first
authenticated student write path** — without touching any standing invariant: `/learn` stays
public and byte-identical for anonymous readers, student writes touch **only `pratham.db`**,
`concept_graph.db` stays read-only, the publish gate and the inward factory are untouched.

## §2 Forks ruled (judge directive, run `wf_df1f8da3-4d4`)

| # | Fork | Ruling |
|---|------|--------|
| F-G4-1 | Unit of student state | **`(student_id, chapter, lane)`** — the exact key the published manifest already uses; reuse, don't invent. Concept-level mastery is a READ-time derivation (via `concept_chapter`) if ever needed, **never stored**. No `concept_id` column, not even nullable. |
| F-G4-2 | Implicit read-events vs explicit marks | **Explicit marks only.** A mark is an explicit, honest, cheap-to-implement signal. No view/dwell telemetry, no implicitly-set states. v1 has exactly ONE student write action: "Mark done". |
| F-G4-3 | Status vocabulary | **Boolean-equivalent with an escape hatch:** `status TEXT NOT NULL DEFAULT 'done'` exists in the schema, but v1 only ever writes `'done'`. A future `'again'` (spaced repetition) becomes a new VALUE, not a migration. No "mark again" UI in v1. |
| F-G4-4 | Recommendation exposure | **Session-gated.** `GET /api/learn/next` requires a valid session (401 otherwise) — adaptivity is the reward for signing in; anonymous `/learn` must stay byte-identical (no anonymous recommendation contract). The PURE ranking function still accepts an empty done-set so it is trivially testable. |
| F-G4-5 | Where state lives | **`pratham.db`, one new `progress` table.** No new database file. `concept_graph.db` is opened only via the existing `coverage.store.connect_ro` from the API-layer glue — the pure ranker never imports `sqlite3`; the `samagra/pratham/` package never imports `samagra/factory/` (import-hygiene IS the firewall, as the G3 review's transitive trace established). |
| F-G4-6 | v1 cuts (negative scope) | No streak calculator · no "continue where you left off" banner · no spaced-repetition semantics · no per-question or per-concept granularity · no annotations · no implicit tracking · no server-side ranking cache · no CSRF token (see §8) · no anonymous recommendation surface. Each is a candidate v1.1+, gated on its own decision. |

## §3 Architecture

```
student (signed in, /learn reader)
   │  POST /api/learn/progress {chapter, lane}          GET /api/learn/next
   ▼                                                     ▼
samagra/api/app.py  ── 401 without session ──  samagra/api/learn_next.py (GLUE)
   │ validates (chapter,lane) against                    │ published_manifest()   (factory.publish.read)
   │ read.published_manifest() → 404-before-write        │ chapter demand         (coverage.store.connect_ro;
   ▼                                                     │   FileNotFoundError → {})
samagra/pratham/service.py  (rate limit, timestamps)     │ student done-set       (pratham.store)
   ▼                                                     ▼
samagra/pratham/store.py  → pratham.db ONLY     samagra/factory/coverage/next_best.py (PURE ranker)
```

- The **write path** never leaves the pratham world (app-layer manifest validation happens
  BEFORE the service call, so `samagra/pratham/` needs no factory import).
- The **read path**'s glue lives in the API layer (`samagra/api/learn_next.py`), the only
  place that already legitimately imports both worlds; the ranker itself is a pure function
  in the coverage package, sibling and stylistic mirror of `gaps.rank_gaps`.

## §4 Data model (pratham.db, SCHEMA_VERSION 1 → 2)

Additive DDL appended to the existing `DDL` executescript in `samagra/pratham/store.py`
(idempotent `CREATE TABLE IF NOT EXISTS`; no migrations framework needed — but the upgrade of
an EXISTING v1 `pratham.db` file must be proven by test):

```sql
CREATE TABLE IF NOT EXISTS progress (
  student_id TEXT NOT NULL,
  chapter    TEXT NOT NULL,
  lane       TEXT NOT NULL,
  status     TEXT NOT NULL DEFAULT 'done',  -- v1 writes only 'done' (F-G4-3 escape hatch)
  marked_at  TEXT NOT NULL,
  PRIMARY KEY (student_id, chapter, lane)
);
CREATE INDEX IF NOT EXISTS idx_progress_student ON progress(student_id);
```

The triple PK makes "mark done" naturally idempotent (upsert; a double-click or network retry
re-marks the timestamp, never duplicates). No surrogate id — nothing references a progress row.

## §5 API surface

Both endpoints live in the existing PUBLIC-by-design `/api/learn/*` block of
`samagra/api/app.py` (deliberately NOT in `origin_auth._PROTECTED_*` — they are student
self-service, gated by the session cookie, exactly like `GET /api/learn/me`).

### §5.1 `POST /api/learn/progress` — the first authenticated student write

- **Auth:** `service.current_student(cookie)`; `None` → **401**. The student id is derived
  **server-side from the session only** — there is no student id in the path, query, or body
  (structural IDOR prevention; see §8).
- **Body:** `{chapter: str, lane: str}`. No client-supplied `status` — the write surface
  cannot express arbitrary state (v1 always writes `'done'`).
- **Validation before write:** `(chapter, lane)` must exist in the LIVE
  `read.published_manifest()` (chapter present AND lane among that chapter's
  `artifacts[].lane`) → otherwise **404**. A progress row can never reference unpublished or
  nonexistent content. Malformed body → **400**.
- **Rate limit:** a second in-process `identity.RateLimiter` instance keyed on
  **student_id** (not IP): 60/min — looser than login's 20 (marking is a legitimate
  high-frequency study action), still bounding any client bug. Rate-limited → **429**
  (unlike login there is nothing to oracle-hide: the caller is already authenticated).
- **Write:** `store.mark_progress(student_id, chapter, lane, marked_at)` upsert. → `{ok: true}`.

### §5.2 `GET /api/learn/next` — the deterministic queue

- **Auth:** session required → **401** otherwise (F-G4-4).
- **Response:** `{queue: [{chapter, title, lane, reason, score, rank}...], done:
  [{chapter, lane, status, marked_at}...]}` — `done` rides along so the reader learns button
  state in the same round trip (no third endpoint).
- **Queue computation** (`next_best.rank_next`, PURE): candidates = every `(chapter, lane)`
  in the published manifest, minus the student's done-set; `score` = the chapter's summed
  concept demand (`SUM(concept.demand_size)` over `concept_chapter` edges, computed by the
  glue via `connect_ro`; `FileNotFoundError`/unbuilt graph → all scores 0); sort =
  `(-score, lane_priority, chapter)` with lane priority mirroring the reader's Saar-led
  `LANE_ORDER` (`revision, lecture, deck, paper, drill, samadhan` — a deliberate TS↔Python
  duplication, commented at both sites); cap at `_QUEUE_SIZE = 8`; `reason` = `"high-demand"`
  when score > 0 else `"new"`. Deterministic, no LLM, no network, no API key (Tier-1 — like
  `gaps.rank_gaps`).
- **Graceful-empty:** empty manifest → `{queue: [], done: [...]}`; never 500.

## §6 Reader UI (additive, identity-gated)

All new JSX is wrapped in `{student && (...)}` — the anonymous DOM is **byte-identical** to
pre-G4 (a regression test freezes the anonymous testid set BEFORE any new JSX lands).

- **"Mark done"** button (`data-testid="pratham-mark-done"`) beside the lane tabs, for the
  currently viewed `(chapter, lane)`; shows a done state (`pratham-done-badge`) when that pair
  is in the fetched done-set; POSTs `/api/learn/progress`, then refetches `/api/learn/next`.
- **"What's next"** strip (`data-testid="pratham-next"`): the top queue rows (title + lane
  label + reason badge), each row navigating via the existing `go(chapter, lane)`; hidden when
  the queue is empty.
- New thin typed fetch wrapper `frontend/src/lib/pratham/plan.ts` (mirrors `session.ts`:
  same-origin credentials, null on error) — the ranking logic stays server-side.
- No new route, no new app, no shell import (separate-entity guarantee unchanged).

## §7 Golden threads (acceptance)

1. **The adaptive loop:** enroll → login → `GET /next` (pair X ranked) → `POST /progress` for
   X → `GET /next` again → X is gone from the queue and present in `done`. Deterministic both
   times.
2. **Write-path isolation:** a full mark sequence leaves `governance.db` **byte-unchanged**
   and creates/modifies nothing outside `pratham.db` (mirrors the G3 isolation thread).
3. **Anonymous invariance:** anonymous `GET /api/learn/next` and `POST /api/learn/progress`
   are 401; the anonymous reader DOM is byte-identical to pre-G4; `/api/published*` responses
   are byte-identical.
4. **Empty-world validity:** fresh empty `pratham.db` + no `published/` + no
   `concept_graph.db` → every new endpoint returns clean JSON (or 401/404 as specified),
   never 500; the reader renders without crash.

## §8 Security model

- **Structural IDOR-proofness:** the student id is never accepted from the client — always
  derived server-side from the session cookie. There is no `/api/learn/*/{student_id}` shape
  anywhere. A student can only ever read/write THEIR OWN rows, by construction.
- **Write-surface minimalism:** the body carries only `(chapter, lane)`, both validated
  against the live published manifest before any write (404-before-write). No free text
  reaches storage.
- **CSRF: accepted risk, narrowly scoped.** SameSite=Lax + the cookie's `/api/learn` path
  already blunt most vectors; a forged cross-site POST could at worst mark the victim's OWN
  progress rows 'done' — no privilege escalation, no cross-student effect, no data exposure.
  This acceptance is scoped to the progress write ONLY; any future higher-stakes write under
  `/api/learn/*` re-opens the question (pinned in DEC-13).
- **Rate limiting:** best-effort in-process, keyed on the authenticated student_id (a
  non-spoofable key, unlike login's Cf-Connecting-Ip) — an honest improvement over the login
  limiter's documented weakness.
- **No new secrets, no LLM, no network egress.**

## §9 Invariants — proposed DEC-13

1. **All student writes touch ONLY `pratham.db`** (extends DEC-12's "login writes" to the
   general rule now that a second student write exists). `samagra/pratham/` imports no
   factory/governance module — import hygiene is the firewall, verified by review.
2. **Student identity is server-derived only** — no student id parameter in any path, query,
   or body under `/api/learn/*`, ever.
3. **Progress rows only reference published content** — the 404-before-write manifest gate is
   load-bearing, not advisory.
4. **The recommender is Tier-1 deterministic** (no LLM, no network, no API key). Any future
   personalized/LLM recommender is a distinct phase with its own decision + review, never a
   silent upgrade.
5. **CSRF acceptance is scoped** to the v1 progress write (own-data, no escalation) — any new
   `/api/learn/*` write re-opens it.
6. **Anonymous `/learn` stays byte-identical**; `/api/published*` untouched; the publish gate,
   the inward `build()` + 5 guards, the 7 subsystems, and `governance.db` (no migration, no
   new table, no state-machine change) are all untouched.

## §10 Review gate (before merge)

Per the DEC-7 pattern applied to every prior write boundary: (1) a dedicated Codex pre-merge
review of the student write boundary (`POST /api/learn/progress` + store/service changes) and
the session-gated read surface, report saved under `docs/codex-reviews/`; (2) an adversarial
multi-lens final review (firewall/store-isolation · security · spec-fidelity ·
identity-optional/separate-entity), findings independently refute-verified; (3) remediate TDD,
re-run the full gate, merge `--ff-only`, push.

## §11 Testing strategy

TDD throughout (red first, every task). Backend: store round-trip + EXISTING-v1-db upgrade
proof; service rate-limit/timestamp; pure-ranker table-driven cases (empty everything, done
subtraction, demand ordering, lane priority, cap, determinism); endpoint auth/validation
matrices (401/400/404/429/200); the four golden threads of §7. Frontend: plan.ts wrapper with
fake fetch; the anonymous byte-identical regression (written BEFORE new JSX); signed-in UI
rendering + mark→refetch flow with mocked endpoints; empty-payload states. Full gate: pytest +
vitest + tsc + build.

## §12 Non-goals (v1)

Everything in F-G4-6, plus: no operator-console changes (the owner's view of student progress
is a later, separate read surface); no export of progress data; no email/notifications; no
mobile-specific UI work; no changes to `coverage-build` or the gap queue (the owner's factory
steering and the student's study queue remain separate products of the same graph).

## §13 Open questions (owner)

1. A friendly Sanskrit/Hindi name for the "What's next" strip (house pattern named the lanes
   Saar/Vaani/Smriti/Pariksha/Abhyaas/Samadhan) — e.g. "Aage" (आगे)? Cosmetic; defaults to
   plain "What's next" until named.
2. Queue size (`_QUEUE_SIZE = 8`) and the 60/min progress rate limit are tunable defaults —
   revisit after the first real students.
3. Whether the owner wants a read-only "students' progress" operator view (explicitly out of
   scope for v1; would be its own additive read surface).
