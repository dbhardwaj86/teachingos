# SAMAGRA — Implementation Plan: Desktop Icons + 3 Read-Only Corpus Apps + Native-Fidelity Embedding

**Repo:** `C:\SandBox\claude_box\TeachingOS` · **Package:** `samagra` · **Branch (suggested):** `feature/desktop-icons-and-corpus-apps`
**Status:** FINAL amended plan (remediation of the GO-WITH-CHANGES review, findings F1–F10 all folded in as BINDING rulings). READ-ONLY exploration performed; nothing edited except this plan file.
**Binding constraints:** read-only firewall over all source subsystems; **no new prod write path**; publish gate untouched; `origin_auth` conventions respected (every new GET's public-vs-gated decision justified below — and per the F1/F2 rulings ALL `/api/corpus/*` serve+proxy GETs are now **ORIGIN-GATED**); **no governance migration**; pytest + vitest TDD throughout; surgical diffs.

This plan covers **four tasks**:
- **Task 1** — SAMAGRA-OS desktop icons (labeled, clickable, 3 themes, mobile-safe).
- **Task 2** — three new read-only source subsystems + gated list/serve/proxy endpoints (config roots + adapters + proxy core). **Backend only** — no frontend registry change.
- **Task 3** — the three windowed corpus apps that embed each corpus's own UI (registry/AppId/icon additions + iframe app components). **Frontend only** — depends on Task 2's endpoint paths.
- **Task 4** — **annex only** (the pipeline-integration exploration, attached verbatim; **zero implementation tasks**).

### Execution order (dependency-clean; this is the shape the review mandated)

```
STAGE A  (two lanes, fully parallel — disjoint file sets)
  ├─ Task 1  frontend-only  (shell/App.tsx/lib/desktop; NO samagra/, NO tests/*.py)
  └─ Task 2  backend-only   (samagra/ + tests/*.py; NO frontend/ registry change)
STAGE B  (after A)
  └─ Task 3  frontend apps  (registry/AppId/icons + apps/*/index.tsx + vitest; consumes Task 2 endpoint PATHS)
Task 4     annex, zero implementation, no stage
```

Task 1 touches ONLY `frontend/src/shell/*`, `frontend/src/App.tsx`, `frontend/src/lib/desktop/*`, `frontend/src/App.test.tsx`. Task 2 touches ONLY `samagra/**` + `tests/**.py` + `.env.example` + `docs/deploy-tunnel.md`. Their file sets are disjoint → they run as two subagents with no merge conflict. Task 3 touches `frontend/src/{types,registry,components,App.tsx,apps/*}` and depends on the Task-2 endpoint contract (paths only, as strings — it compiles before the backend runs; only the end-to-end smoke needs both).

### Anchor corrections applied during re-verification (config.py + mcd_client.py were dirty at plan time)

- `samagra/questions_proxy.py` is **top-level**, NOT `samagra/api/questions_proxy.py`. `absolutize_assets` is at `questions_proxy.py:14`; `_REL = 'src="/asset?'` at `:11`. (The draft mis-pathed it.)
- `config.py` MCD_ROOT precedent is now at **`config.py:68`** (the block spans `:63-68`); `_env_path` at `:23-25`; QX server-URL SSRF pattern at `:82-85` — all re-verified against the dirty working tree.
- `origin_auth._PROTECTED_GETS` = `{/api/munshi/library, /api/mcd/seeds, /api/search, /api/assignments}` (`origin_auth.py:58-60`); `is_protected` GET arm is **exact-match only** (`origin_auth.py:70`), POST arm has the `startswith("/api/gate/")` pattern branch (`:68`). F2 requires a **new GET startswith branch** — grounded.
- onedpulls answer-bearing endpoint families (verified from `_brain/scripts/webui.py`): **`/api/questions`, `/api/question/<id>`, `/api/coverage`, `/api/similar/<id>`** all emit `answer`/`solution_md`.
- lecturepdf non-read endpoint families (verified from `brain/api/app.py`): **`/api/prep_pack` (POST), `/api/reveal` (POST), `/api/compositions` (GET+POST), `/api/compositions/{id}/export/docx` (POST), `/api/excalidraw/open` (POST), `/api/synthesize` (POST), `/api/questions/generate` (POST)** — the compositions family (even its GET) is excluded from v1 to stay clear of the write surface.
- Baseline gates re-verified: **848 pytest** (sum of per-file collection), **639 vitest**. All frontend anchors (App.tsx:157/341/366, Dock.tsx:65-69, Pratham/index.tsx:253-258, geometry.ts:17-36) confirmed live.

---

## 0. Architectural decisions (LOCKED — reflect the F1–F10 rulings)

### 0.1 The `/api/corpus/*` namespace + ORIGIN-GATING (F1 + F2, both HIGH — BINDING)

**All new corpus endpoints live under a single `/api/corpus/` prefix** so one gate rule covers the whole surface:

- `GET /api/corpus/<name>` — the coarse catalog listing (docs/topics/lectures counts + a bounded artifact list).
- `GET /api/corpus/<name>/serve/{path:path}` — the native-UI serve + read-proxy (the `{path:path}` reverse-proxy route).

where `<name> ∈ {gnocr, onedpull, lecturepdf}`.

**Ruling F2 (HIGH): every `/api/corpus/*` GET is ORIGIN-GATED.** These are the owner's operator-console apps that reverse-proxy three **unhardened localhost hobby daemons**; a public `{path:path}` proxy would inherit every traversal/DoS bug in those Flask/FastAPI servers (the review-27 MED-2 class — `QX_ROOT` was pulled from `/open` for exactly this). This is **not** the `/api/coverage` / `/api/published` precedent (derived local data / a single fixed endpoint). Loopback callers (local dev AND the cloudflared origin) always pass the gate (`origin_auth.py:74-79`), so gating costs the owner nothing while closing the surface to any direct non-loopback caller.

Because `is_protected`'s GET arm is exact-match (`origin_auth.py:70`), a `{path:path}` route needs a **new startswith-prefix branch mirroring the existing `/api/gate/` POST pattern** (`origin_auth.py:68`):

```python
# origin_auth.py — is_protected(), GET arm
if method == "GET":
    return path in _PROTECTED_GETS or path.startswith("/api/corpus/")
```

The listing endpoints are covered by the same prefix (they too begin `/api/corpus/`), so the whole namespace is gated by one branch. **Task 2 owns this branch + its tests.**

**Ruling F1 (HIGH): the iframes load same-origin gated content WITHOUT a CORS-breaking sandbox origin.** The draft's plan to serve `Content-Security-Policy: sandbox allow-scripts` on these pages is **rejected for the corpus apps**: `sandbox allow-scripts` forces an **opaque origin**, so every `fetch`/XHR the embedded card-catalog/Vue pages make (all three are fetch-driven — verified: GN-OCR/onedpull emit `fetch("/api/...")`, lecturepdf's Vue app fetches `/api/*`) becomes an `Origin: null` cross-origin request, and SAMAGRA registers **no CORS middleware**, so the browser blocks every response. Pratham's published-artifact iframe works only because a published artifact fetches nothing.

Decision: the corpus serve endpoints are **same-origin trusted owner apps behind the origin gate**, so:
- Backend `/api/corpus/<name>/serve/*` returns `X-Content-Type-Options: nosniff` + `Referrer-Policy: no-referrer` **but NOT** the `sandbox allow-scripts` CSP. Same-origin fetches from the iframe therefore resolve normally against SAMAGRA's own origin (and hit the gated proxy, which loopback-passes).
- The frontend `<iframe>` sets `referrerPolicy="no-referrer"` and a fill style, and **omits the `sandbox` attribute** (or, if any sandbox is used, includes `allow-same-origin allow-scripts` so the frame keeps SAMAGRA's origin and its fetches are same-origin, not `null`). These are the owner's own trusted local corpora served from SAMAGRA's own gated origin — the threat model that motivates a sandbox (untrusted third-party published bytes on a public surface) does not apply here.

**The Pratham published-artifact sandbox precedent stays UNTOUCHED and is explicitly distinguished:** `GET /api/published/{chapter}/{lane}` keeps its `sandbox allow-scripts` CSP (`app.py:245-246`) and the `/learn` reader keeps `sandbox="allow-scripts"` on its iframe (`Pratham/index.tsx:256`) — because those serve **untrusted, self-contained, public-by-design** artifact bytes that fetch nothing. The corpus apps are the **opposite** case (trusted owner apps, gated origin, fetch-driven) and correctly get a different, CORS-safe embedding posture. No change to any published/Pratham code.

### 0.2 Reverse-proxy, not static byte-rewrite (F5 — MED, BINDING)

**Ruling F5:** the native UIs are served via a **live reverse-proxy to the upstream daemon** (GN Brain `127.0.0.1:8931`, Corpus Brain `127.0.0.1:8137`, Lecture Brain `127.0.0.1:8000`) **plus an injected `<base href="/api/corpus/<name>/serve/">`** (or a minimal fetch-shim) — NOT a brittle prefix byte-rewrite of the 43–54 KB minified single-file apps, and NOT a static-index-from-disk shortcut. A pure prefix-replace misses dynamically-constructed URLs, and any surviving absolute `fetch("/api/search")` from the iframe would otherwise hit SAMAGRA's OWN `/api/search` (which is in `_PROTECTED_GETS`).

Mechanism (in `CorpusProxy`, T3.1):
1. On the HTML document response (`index.html` / the SPA shell), inject `<base href="/api/corpus/<name>/serve/">` immediately after `<head>` so every relative fetch/asset the page issues resolves under the gated same-origin serve prefix. A `<base>` covers relative URLs; for the pages' **absolute** `/api/...` / `/static/...` / `/preview/...` fetches, apply a bounded, **enumerated** literal rewrite (per-corpus list — see the regression tests) that rewrites those absolute prefixes to `/api/corpus/<name>/serve/api/...` etc. The enumeration is derived from the REAL index bytes (verified literals below), not guessed.
2. Everything else (`/static/js/app.js`, `/api/stats`, `/preview/...`, `/api/diagrams/png/...`) is proxied byte-for-byte from the daemon.

**Verified rewrite literals (from the live index files):**
- GN Brain: `fetch("/api/stats`, `fetch("/api/search?`, `fetch("/api/topics`, `fetch("/api/ask`, `fetch("/api/brief`, `/preview/`, `/pdf/`, `/gn-assets/`.
- Corpus Brain: `fetch("/api/stats`, `fetch("/api/search?`, `fetch("/api/topics`, `fetch("/api/ask`, `fetch("/api/brief`, `fetch("/api/questions?`, `fetch("/api/question/`, `fetch("/api/similar/`, `fetch("/api/coverage`, `/preview/`, `/pdf/`.
- Lecture Brain: shell links `/static/css/app.css`, `/static/vendor/vue.global.prod.js`, `/static/js/app.js`; the Vue app fetches `/api/stats`, `/api/topics`, `/api/query_lexical`, `/api/topic/{slug}`, `/api/examples`, `/api/lectures`, `/api/lecture`, `/api/lecture_overlap`, `/api/diagrams/png/...`, `/api/diagrams/scene/...`.

**Regression test (T3.2/T3.3):** against the REAL `index.html` bytes, assert (a) the `<base href>` (or shim) is injected, and (b) **no un-rewritten `fetch("/api/` literal survives** in the served HTML for the write/answer-bearing paths that are excluded from the allowlist (a surviving one would either hit SAMAGRA's gated `/api/search` or leak an answer path). The `ask`/`brief` POST paths are structurally unreachable through the GET-only proxy regardless, but their literals in the page are harmless (the POST never forwards).

**Graceful daemon-down (F5 + annex invariant 9):** when the upstream daemon is unreachable, the proxy returns a clean in-app error body (a small themed "brain offline — start the sidecar" panel + retry affordance), **never a 500 that wedges the window**. The listing endpoint (`GET /api/corpus/<name>`) reads the local `catalog.db` / `corpus.jsonl` directly (no daemon) so the app's catalog view survives a down daemon; only the embedded live UI degrades. Each daemon's launch command is documented in the owner notes (§ global gate 6).

### 0.3 Positive allowlist + normalization (F4 — MED, BINDING) and answer-leak posture (F3 — MED, BINDING)

**Ruling F4 — exact positive allowlist per corpus (no broad `^/api/` prefix-allow), with normalization BEFORE matching.** `CorpusProxy` holds a per-corpus frozenset of exactly-enumerable upstream path patterns; a request path is **normalized first** — single URL-decode, collapse duplicate `//`, **reject any backslash**, and **reject any post-decode `..` segment** — then matched against the allowlist. Anything not on the list is refused (404/403) before any upstream call. Absolute-URL smuggling (`serve/http://evil/...`, `serve//evil`) is rejected by the normalization + the `_SAFE_SEGMENT` per-segment guard + the SSRF host-allowlist (§0.4).

Per-corpus positive allowlists (GET-only; `<id>` = integer, `<page>` = integer, `<path>` = `_SAFE_SEGMENT` chain):

| Corpus | Allowed upstream GET paths (v1) | Explicitly EXCLUDED |
|---|---|---|
| **gnocr** | `/` (shell), `/static/*` (none — single-file), `/api/stats`, `/api/search`, `/api/topics`, `/preview/<id>/<page>.png`, `/gn-assets/<id>/<path>`, `/pdf/<id>`, `/briefs/<file>` | `POST /api/ask`, `POST /api/brief` (POST — structurally unreachable) |
| **onedpull** | `/` (shell), `/api/stats`, `/api/search`, `/api/topics`, `/preview/<id>/<page>.png`, `/pdf/<id>`, `/extracted/<path>` | **`/api/questions`, `/api/question/<id>`, `/api/coverage`, `/api/similar/<id>`** (answer-bearing — see F3), `POST /api/ask`, `POST /api/brief` |
| **lecturepdf** | `/` (shell), `/static/*`, `/api/health`, `/api/stats`, `/api/topics`, `/api/query_lexical`, `/api/topic/<slug>`, `/api/examples`, `/api/lectures`, `/api/lecture`, `/api/lecture_overlap`, `/api/diagrams/png/<run>/<doc>/<name>`, `/api/diagrams/scene/<run>/<uid>` | `/api/query` (key-consuming semantic — v1 lexical-only), the whole **compositions family** (`GET`+`POST /api/compositions*`), `POST /api/prep_pack`, `POST /api/reveal`, `POST /api/export/docx`, `POST /api/excalidraw/open`, `POST /api/synthesize`, `POST /api/questions/generate` |

**Ruling F3 — answer/solution content in proxied onedpull responses is ACCEPTABLE, with a stated rationale + a student-surface byte-untouched golden test.** Because every `/api/corpus/*` endpoint is **origin-gated owner-only** (F2) and **nothing from these proxies feeds `published/` or any student surface in this slice** (the corpus apps are pure read/browse windows; no factory seed, no publish, no `/learn`), answer content that a proxied onedpull response *might* carry is not an exposure. To keep the surface conservative anyway, the v1 onedpull allowlist **excludes the four answer-bearing endpoint families outright** (table above), so in practice no answer/solution bytes flow even to the owner in v1. The plan STATES this rationale explicitly and adds:
- A **defense-in-depth body-scan** in `CorpusProxy` for the onedpull corpus: every proxied response body is scanned with the existing `_assert_no_answer_leak`-style structural marker set (extended with onedpulls' render markers — `answer`/`solution_md` JSON keys, the `pq-ans`/`pkey` render tokens) and **refused** if a marker is present. Test: a fixture payload containing `solution_md` is refused (403), proving the scan is live even though the allowlist already excludes the emitting endpoints.
- A **slice-wide student-surface golden test** (see global gate, `tests/test_corpus_student_surface_untouched.py`): asserts that exercising the entire corpus slice leaves `/learn`, `/api/published*`, and `/api/learn/*` **byte-untouched** (response bytes + status identical to a pre-slice baseline; `governance.db` and `pratham.db` unreferenced by any corpus code path).

### 0.4 SSRF, size, timeout (F5-supporting + F7 — BINDING)

- **SSRF:** each corpus's `*_SERVER_URL` is validated by a per-corpus reuse of the `qx_guard` pattern (`validate_qx_url` at `qx_guard.py:28-37`, loopback-or-allowlist-only) — an off-loopback base URL raises at proxy construction.
- **Ruling F7 — proxy response-size cap + timeout.** `CorpusProxy` enforces a byte cap (default 25 MB, env-tunable per corpus) and a request timeout (default 15 s) on every upstream fetch; over-cap or timeout returns the graceful in-app error body, never an unbounded read or a hang. Tests cover both.

### 0.5 Origin-gate decision table (post-rulings)

| New endpoint | Gated? | Justification |
|---|---|---|
| `GET /api/corpus/gnocr` (list) | **GATED** (F2) | Under the `/api/corpus/` prefix branch. Owner-only console read. |
| `GET /api/corpus/gnocr/serve/{path}` | **GATED** (F2) | Reverse-proxy to an unhardened daemon — owner-only. |
| `GET /api/corpus/onedpull` (list) | **GATED** | Same. List carries counts only (no answers). |
| `GET /api/corpus/onedpull/serve/{path}` | **GATED** (F2) + answer-family excluded (F3) + body-scan (F3) | Owner-only; answer paths off the allowlist AND scanned. |
| `GET /api/corpus/lecturepdf` (list) | **GATED** | Same. |
| `GET /api/corpus/lecturepdf/serve/{path}` | **GATED** (F2) | Reverse-proxy; POST/write/compositions/key paths excluded. |

**No new POST anywhere.** `_PROTECTED_POSTS` unchanged. The read-only firewall + publish gate untouched by construction.

### 0.6 Governance / migration

**Zero** governance schema change. Adapters flow into `catalog.refresh()` → `/api/overview`/`/api/search`/`/api/facets` automatically (the abort-on-error swap in `catalog.py:69-168` contains a throwing adapter). No `assignments` change, no new table.

---

# TASK 1 — Desktop icons (labeled, clickable, 3 themes, mobile-safe) · STAGE A · frontend-only

**Goal:** a labeled clickable icon grid on the bare desktop background of the windowing shell (PC only), each icon showing the **full app name** under a tile, opening/focusing the app on click (matching `openApp` open-or-focus) and opening the app context menu on right-click. Works across `aqua`/`console`/`samagra`; entirely bypassed in mobile mode. **Must not break bare-desktop right-click** (F6).

**File set (disjoint from Task 2):** `frontend/src/lib/desktop/layout.ts` + `.test.ts`, `frontend/src/shell/DesktopIcons.tsx` + `.test.tsx`, `frontend/src/App.tsx`, `frontend/src/App.test.tsx`.

**Design (grounded):**
- Pure layout module `frontend/src/lib/desktop/layout.ts` — computes `{col,row → x,y}` inside the theme's `workArea()` insets (`geometry.ts:17-36`; never overlaps TopBar/Rail/Dock/Taskbar). Zero DOM. Colocated `layout.test.ts`.
- Shell component `frontend/src/shell/DesktopIcons.tsx` — iterates `ORDER`/`APPS`, one labeled tile per app: `<AppIcon app accent label={app.name}/>` + a visible `<span>{app.name}</span>` caption ~10.5px (the StartMenu tile+caption precedent, `StartMenu.tsx:109-114`).
- **F6 (MED, BINDING) — the wrapper must NOT swallow the bare-desktop right-click.** The root `onContextMenu` (`App.tsx:337-344`) opens the desktop menu ONLY when `e.target === e.currentTarget` (`App.tsx:341`). A viewport-filling `DesktopIcons` wrapper would become the target everywhere and kill the desktop menu. Fix (choose one, pinned in the test): **either** render each tile as a direct absolutely-positioned child of the shell root (no full-bleed wrapper), **or** give the wrapper `pointerEvents:"none"` with each tile `pointerEvents:"auto"` — so a right-click on empty desktop passes THROUGH the wrapper to the root and `e.target===e.currentTarget` still holds. This plan uses the **`pointerEvents:"none"` wrapper + per-tile `auto`** approach (single mount point, cleaner than N root children).
- **F9 (LOW, BINDING) — tile click must dismiss an open context menu.** The root `onClick` (`App.tsx:333-336`) clears menus/start; a tile handler that `stopPropagation()`s on click would leave a floating menu. Fix: the tile `onClick` calls `onOpen(id)` **and explicitly dismisses any open menu** (pass an `onDismiss` prop wired to the same `setMenu(null); setStartOpen(false)` the root does), OR only `stopPropagation()` on `contextmenu` (not on click) so the root's click-dismiss still runs. This plan wires an explicit `onDismiss` so the tile both opens the app and clears menus. Right-click still `stopPropagation()`s (so it doesn't retrigger the bare-desktop menu) and opens the app menu via `onAppContextMenu`.
- **F10 (NIT, BINDING) — pin overflow.** `iconPositions` lays out **vertical column-flow, wrapping to the next column**, and **clamps within the work area — never scrolls** (if the app count exceeds the grid capacity, later icons clamp to the last valid cell rather than painting under chrome or introducing a scrollbar). Pinned by the T1.1 overflow test. Aqua bottom-dock clearance is already guaranteed by `workArea` (`h = vh-barH-92`).
- Mounted in `App.tsx` inside `#samagra-os-shell`, AFTER `<TopBar>` and BEFORE `windows.map(...)` (`App.tsx:366`) at low z (behind windows). NOT rendered in the `device === "mobile"` branch (`App.tsx:297-328`).

### Task 1 — subtasks (TDD-ordered)

**T1.1 — Pure grid-layout module**
- **Test first:** `frontend/src/lib/desktop/layout.test.ts`
  - `it("places the first icon at the theme work-area top-left inset")` — per theme, `iconPositions(theme,vw,vh,count)[0]` sits at/after `workArea(theme,vw,vh).{x,y}`.
  - `it("lays out a vertical column then wraps to the next column")` — column-major ordering with fixed `CELL_W`/`CELL_H`/`GAP`.
  - `it("clamps overflow icons within the work area and never scrolls")` — (F10) with a `count` exceeding capacity, every returned `{x,y}`+cell ≤ `workArea` right/bottom edge; the overflow icons clamp to the last valid cell (assert no position exits the area).
  - `it("shifts the whole grid clear of the samagra rail")` — samagra positions start at `x ≥ rail+8`.
  - `it("returns [] for count 0")`.
- **Implement:** `frontend/src/lib/desktop/layout.ts` — `export function iconPositions(theme, vw, vh, count): {x:number;y:number}[]` using `workArea` from `lib/wm/geometry` + `CELL_W=92, CELL_H=92, GAP=10`. No React.
- **Gate:** `npx vitest run src/lib/desktop/layout.test.ts` green; `tsc --noEmit`.

**T1.2 — DesktopIcons component** *(depends: T1.1)*
- **Test first:** `frontend/src/shell/DesktopIcons.test.tsx`
  - `it("renders one labeled tile per app in ORDER")` — `render(<DesktopIcons theme="aqua" onOpen={vi.fn()} onAppContextMenu={vi.fn()} onDismiss={vi.fn()} vw={1440} vh={900}/>)`; assert one addressable tile per `ORDER` id and every `APPS[id].name` visible as caption text. (Note: `<AppIcon label>` sets `role="img" aria-label`; count tiles by a stable `data-testid="desktop-tile"` rather than `role="button"` to avoid the img/button ambiguity.)
  - `it("calls onOpen with the app id on click")` — click the "Dashboard" tile → `onOpen("dashboard")`.
  - `it("also opens on double-click")` — `fireEvent.doubleClick` → `onOpen` called (open-or-focus idempotent).
  - `it("dismisses open menus on click")` — (F9) click → `onDismiss` called.
  - `it("opens the app context menu on right-click with stopPropagation")` — (F6) `fireEvent.contextMenu` → `onAppContextMenu(id,x,y)` called; a parent `onContextMenu` spy did NOT fire.
  - `it("lets a bare-wrapper right-click pass through (pointerEvents none)")` — (F6) assert the wrapper style is `pointerEvents:"none"` and each tile `pointerEvents:"auto"`.
  - `it("paints captions with the theme text token")` — caption `style.color` uses `var(--samagra-text)` for each of the 3 themes.
- **Implement:** `DesktopIcons.tsx` — props `{ theme; vw; vh; onOpen:(id:AppId)=>void; onAppContextMenu:(id:AppId,x:number,y:number)=>void; onDismiss:()=>void }`; call `iconPositions`; wrapper `pointerEvents:"none"` at `zIndex:1`; each tile absolutely-positioned, `pointerEvents:"auto"`, `data-testid="desktop-tile"`, `onClick={() => { onDismiss(); onOpen(id); }}`, `onDoubleClick={() => { onDismiss(); onOpen(id); }}`, `onContextMenu={(e)=>{ e.preventDefault(); e.stopPropagation(); onAppContextMenu(id,e.clientX,e.clientY); }}`; reuse `<AppIcon>` + caption span.
- **Gate:** `npx vitest run src/shell/DesktopIcons.test.tsx` green; `tsc --noEmit`.

**T1.3 — Mount in App shell + wire handlers + mobile exclusion + bare-desktop regression** *(depends: T1.2)*
- **Test first:** extend `frontend/src/App.test.tsx` (real shared stores, `App.test.tsx:19-30`)
  - `it("renders labeled desktop icons on the aqua desktop")` — render App (default theme); a desktop tile labeled "Dashboard" exists and is NOT inside a `WindowFrame`.
  - `it("opens a window when a desktop icon is clicked")` — click the desktop "Notes" tile → a `WindowFrame` titled "Notes" mounts (via the real `wmStore.openApp`).
  - **`it("still opens the desktop context menu on a bare-desktop right-click with DesktopIcons mounted")`** — (F6, the required regression) `fireEvent.contextMenu(shellRoot)` where `target===currentTarget` → the desktop menu (New Terminal / Appearance / …) renders. Proves the `pointerEvents:none` wrapper doesn't steal the target.
  - `it("does NOT render desktop icons in mobile device mode")` — `themeStore.getState().setDevice("mobile")`; re-render; the desktop grid is absent.
  - `it("renders desktop icons across all three themes")` — loop `setTheme("aqua"|"console"|"samagra")`; grid present each time; click an icon → its `WindowFrame` renders above the grid (z-order).
- **Implement:** in `App.tsx` PC branch (after `<TopBar>`, before `windows.map`), add `<DesktopIcons theme={theme} vw={vw} vh={vh} onOpen={openApp} onAppContextMenu={openAppMenu} onDismiss={() => { setMenu(null); setStartOpen(false); }}/>`. Add `vw/vh` state + a `useEffect` window-`resize` listener (cleared on unmount) mirroring the clock `useEffect` (`App.tsx:148-151`). Do NOT add to the mobile branch.
- **Gate:** `npx vitest run src/App.test.tsx` green; full `npm run build` + `tsc --noEmit` green.

**T1.4 — Visual/interaction verification (non-blocking, manual)** — build, preview, confirm across 3 themes: labeled icons clear of chrome, click/double-click opens, right-click app-menu works, bare-desktop right-click still opens the desktop menu, windows above icons, mobile unchanged. Smoke note in the PR; no test artifact.

**Task 1 acceptance gate:** vitest (new + `App.test.tsx`) green; `tsc --noEmit` clean; `npm run build` green; no regression in `Dock.test.tsx`/`Rail.test.tsx`/`StartMenu.test.tsx`/`Mobile.test.tsx`.

---

# TASK 2 — Three read-only corpus subsystems: config + adapters + gated endpoints + proxy core · STAGE A · backend-only

Follows the MCD_ROOT precedent (`config.py:63-68`) + the sims/booklets adapter recipe + the catalog auto-flow. All three corpora are **read-only**; adapters read via `sqlite3 mode=ro` (A/B `catalog.db`) or filesystem/JSONL (C). **No frontend change in this task.**

**File set (disjoint from Task 1):** `samagra/config.py`, `samagra/adapters/{gnocr,onedpull,lecturepdf}.py`, `samagra/adapters/__init__.py`, `samagra/api/corpus_proxy.py`, `samagra/api/app.py`, `samagra/api/origin_auth.py`, `tests/{test_config_corpus_roots,test_subsystem_adapters,test_corpus_api,test_corpus_proxy,test_origin_auth,test_corpus_student_surface_untouched}.py`, `.env.example`, `docs/deploy-tunnel.md`.

**Shared constants:**
- Prefixes/names: `gnocr`, `onedpull`, `lecturepdf`.
- Env roots: `SAMAGRA_GNOCR_ROOT`, `SAMAGRA_ONEDPULL_ROOT`, `SAMAGRA_LECTUREPDF_ROOT`.
- Defaults: `C:\SandBox\claude_box\claude-GN-OCR` (`_brain` under it), `C:\SandBox\gemini_box\onedpulls` (`_brain` under it), `C:\SandBox\claude_box\lecturepdfs` (`brain` under it). (All three verified present on disk.)
- Live server URLs: `SAMAGRA_GNOCR_SERVER_URL` (default `http://127.0.0.1:8931`), `SAMAGRA_ONEDPULL_SERVER_URL` (`http://127.0.0.1:8137`), `SAMAGRA_LECTUREPDF_SERVER_URL` (`http://127.0.0.1:8000`), each with a `*_SERVER_ALLOWED_HOSTS` sibling (loopback always allowed) — copying `QX_SERVER_URL`/`QX_SERVER_ALLOWED_HOSTS` (`config.py:82-85`).

### Task 2 — subtasks (TDD-ordered)

**T2.1 — Config roots + server URLs** *(no deps)*
- **Test first:** `tests/test_config_corpus_roots.py`
  - `test_corpus_roots_are_env_overridable(monkeypatch)` — set each `SAMAGRA_*_ROOT`, reload `config`, assert the `Path` reflects env.
  - `test_corpus_roots_have_sane_defaults()` — defaults point at the documented dirs.
  - `test_corpus_server_urls_default_to_local_ports()` — `:8931/:8137/:8000` defaults.
- **Implement:** append to `samagra/config.py` (bottom, after MCD_ROOT `:68`) a commented block per the MCD_ROOT template:
  ```python
  GNOCR_ROOT        = _env_path("SAMAGRA_GNOCR_ROOT",       Path(r"C:\SandBox\claude_box\claude-GN-OCR"))
  GNOCR_BRAIN_DB    = _env_path("SAMAGRA_GNOCR_BRAIN_DB",   GNOCR_ROOT / "_brain" / "catalog.db")
  ONEDPULL_ROOT     = _env_path("SAMAGRA_ONEDPULL_ROOT",    Path(r"C:\SandBox\gemini_box\onedpulls"))
  ONEDPULL_BRAIN_DB = _env_path("SAMAGRA_ONEDPULL_BRAIN_DB", ONEDPULL_ROOT / "_brain" / "catalog.db")
  LECTUREPDF_ROOT   = _env_path("SAMAGRA_LECTUREPDF_ROOT",  Path(r"C:\SandBox\claude_box\lecturepdfs"))
  LECTUREPDF_BRAIN  = _env_path("SAMAGRA_LECTUREPDF_BRAIN", LECTUREPDF_ROOT / "brain")
  GNOCR_SERVER_URL      = os.environ.get("SAMAGRA_GNOCR_SERVER_URL",      "http://127.0.0.1:8931")
  GNOCR_SERVER_ALLOWED_HOSTS      = os.environ.get("SAMAGRA_GNOCR_SERVER_ALLOWED_HOSTS", "")
  ONEDPULL_SERVER_URL   = os.environ.get("SAMAGRA_ONEDPULL_SERVER_URL",   "http://127.0.0.1:8137")
  ONEDPULL_SERVER_ALLOWED_HOSTS   = os.environ.get("SAMAGRA_ONEDPULL_SERVER_ALLOWED_HOSTS", "")
  LECTUREPDF_SERVER_URL = os.environ.get("SAMAGRA_LECTUREPDF_SERVER_URL", "http://127.0.0.1:8000")
  LECTUREPDF_SERVER_ALLOWED_HOSTS = os.environ.get("SAMAGRA_LECTUREPDF_SERVER_ALLOWED_HOSTS", "")
  ```
- **Docs:** add all env vars to `.env.example` (a block per corpus, with the read-only note + rollback note, mirroring the MCD/QX blocks).
- **Gate:** `pytest tests/test_config_corpus_roots.py`.

**T2.2 — GN-OCR adapter** *(depends: T2.1; parallel with T2.3/T2.4)*
- **Test first:** extend `tests/test_subsystem_adapters.py`
  - Build a tiny `catalog.db` fixture in `tmp_path` (`files`/`documents`/`topics` tables, 2-3 rows); `monkeypatch.setattr(config, "GNOCR_ROOT", tmp_path)` + `GNOCR_BRAIN_DB` to the fixture.
  - `test_gnocr_adapter_identity` — `name=="gnocr"`, `label=="GN Brain (Handwritten)"`.
  - `test_gnocr_available_true_when_db_exists` / `..._false_when_missing`.
  - `test_gnocr_summary_counts` — `{"documents": N, "topics": M, "chunks": K}`.
  - `test_gnocr_artifacts_field_by_field` — one `Artifact` per document: `uid==f"gnocr:{doc_id}"`, `source=="gnocr"`, `kind=="chapter"` (coarse; doc≈chapter), `title`=documents.title, `meta` = `{page_count, topic}`. No answer/solution fields exist.
  - `test_gnocr_registered` — `"gnocr" in {a.name for a in ALL_ADAPTERS}` + `isinstance(get_adapter("gnocr"), GnocrAdapter)`.
  - `test_gnocr_reads_readonly` — the helper uses `mode=ro` (assert the connect URI; the `qx._ro` convention).
- **Implement:** `samagra/adapters/gnocr.py` — subclass `Adapter`; `available()`=`config.GNOCR_BRAIN_DB.exists()`; a `_ro(path)` = `sqlite3.connect(f"file:{path}?mode=ro", uri=True)` (copy `qx.py:20-25`, **no `immutable=1`** — WAL corpus, the Slice-R lesson); `summary()` COUNTs `documents`/`topics`/`chunks`; `artifacts()` SELECTs documents joined to any tagged topic → `Artifact`s. Read-only docstring (`sims.py:1`). Missing/locked DB → `available()` False (kept out of `refresh`); never raise.
- **Gate:** `pytest tests/test_subsystem_adapters.py -k gnocr`.

**T2.3 — onedpulls adapter** *(depends: T2.1; parallel)*
- **Test first:** extend `tests/test_subsystem_adapters.py` with a `tmp_path` `catalog.db` fixture (`files`/`documents`/`topics`/`questions`).
  - `test_onedpull_adapter_identity` — `name=="onedpull"`, `label=="Corpus Brain (onedpulls)"`.
  - `test_onedpull_available_*`.
  - `test_onedpull_summary_counts` — `{"documents": N, "questions": Q, "topics": T}` — **counts only; NO question stems/answers** into the catalog (coarse altitude; `base.py:1-7` forbids question-level rows).
  - `test_onedpull_artifacts_field_by_field` — one `Artifact` per document, `uid==f"onedpull:doc:{doc_id}"`, `kind` mapped from `documents.kind` (test_paper/notes/book → `paper`/`chapter`/`booklet` at coarse altitude), `meta` = `{kind, exam, year, pages}`. **Assert no `answer`/`solution_md` string appears in any Artifact field** (catalog-boundary answer-leak firewall).
  - `test_onedpull_registered`.
- **Implement:** `samagra/adapters/onedpull.py` — same `_ro` helper; `summary()`/`artifacts()` over `documents` (+ COUNT of `questions`); NEVER select `answer`/`solution_md` into an Artifact. Read-only docstring.
- **Gate:** `pytest tests/test_subsystem_adapters.py -k onedpull`.

**T2.4 — lecturepdfs adapter** *(depends: T2.1; parallel)*
- **Test first:** extend `tests/test_subsystem_adapters.py` with a `tmp_path` `brain/data/corpus.jsonl` fixture (rows with `id/topic/lecture_no/type/source_path`) + optional `data/examples.json`.
  - `test_lecturepdf_adapter_identity` — `name=="lecturepdf"`, `label=="Lecture Brain"`.
  - `test_lecturepdf_available_true_when_corpus_jsonl_exists`.
  - `test_lecturepdf_summary_counts` — `{"lectures": L, "topics": T, "examples": E, "chunks": C}` from the jsonl + examples.json (no LanceDB, no OpenAI — no-key path only).
  - `test_lecturepdf_artifacts` — one `Artifact` per distinct lecture (grouped by `source_path`/`lecture_no`), `uid==f"lecturepdf:{batch_slug}/{lecture_no}"`, `kind=="chapter"`, `meta` = `{batch, topic, lecture_no, date}`.
  - `test_lecturepdf_reads_no_lancedb_no_key` — the module imports neither lancedb nor any OpenAI key (assert by construction).
  - `test_lecturepdf_registered`.
- **Implement:** `samagra/adapters/lecturepdf.py` — `available()`=`(config.LECTUREPDF_BRAIN / "data" / "corpus.jsonl").exists()`; stream `corpus.jsonl` + read `data/examples.json`; group chunks into lectures. Read-only, no daemon, no key. Derive a safe display slug from the batch dir name inline (slugify spaces/parens); the serve endpoint (Task 3) sanitizes segments anyway. A git-committed crosswalk is deferred to Task 4 annex.
- **Gate:** `pytest tests/test_subsystem_adapters.py -k lecturepdf`.

**T2.5 — Register all three adapters** *(depends: T2.2/T2.3/T2.4)*
- **Test first:** `test_all_three_corpora_registered` — `{"gnocr","onedpull","lecturepdf"} <= {a.name for a in ALL_ADAPTERS}` and each `get_adapter(name)` returns the right instance.
- **Implement:** `samagra/adapters/__init__.py` — import the 3 classes (`:5-12`) and append 3 instances to `ALL_ADAPTERS` (`:14-23`).
- **Gate:** `pytest tests/test_subsystem_adapters.py`; also `tests/test_catalog_refresh_safety.py` (the abort-on-error swap holds with 3 new adapters — a throwing new adapter must not corrupt the catalog).

**T2.6 — `corpus_proxy` pure module (reverse-proxy core: allowlist + normalization + SSRF + size/timeout + body-scan + base-inject)** *(depends: T2.1; parallel with the adapters)*
- **Test first:** `tests/test_corpus_proxy.py`
  - `test_rejects_non_get_method` — POST/PUT/DELETE refused (structural — lecturepdf writes unreachable).
  - `test_path_not_in_positive_allowlist_refused` — (F4) `/api/compositions`, `/api/reveal`, `/api/excalidraw/open`, `/api/synthesize`, `/api/prep_pack`, `/api/questions/generate`, `/api/query` all refused even via GET; only the enumerated read paths pass.
  - `test_onedpull_answer_families_refused` — (F3/F4) `/api/questions`, `/api/question/5`, `/api/coverage`, `/api/similar/5` refused for onedpull.
  - `test_normalization_before_match` — (F4) encoded traversal (`%2e%2e%2f`), backslash segments (`\..\`), double-slash (`//api/stats`), a `/api/./stats` collapse, and absolute-URL smuggling (`http://evil/`, `serve//evil`) are each rejected BEFORE any upstream call.
  - `test_offhost_base_url_rejected` — a base_url off the loopback allowlist raises (reuse the `qx_guard` pattern).
  - `test_base_href_injected_into_html` — (F5) the served shell HTML carries `<base href="/api/corpus/<name>/serve/">`.
  - `test_no_unrewritten_api_fetch_survives_for_excluded_paths` — (F5) against the REAL index bytes, no un-rewritten `fetch("/api/questions`/`fetch("/api/coverage`/etc. (the excluded families) survives in the served onedpull HTML.
  - `test_response_size_cap_enforced` / `test_upstream_timeout_graceful` — (F7) over-cap and timeout return the graceful error body, never unbounded/hang.
  - `test_onedpull_body_scan_refuses_solution_md` — (F3) a fixture upstream body containing `solution_md` is refused (403) by the body-scan.
  - `test_media_type_for_js_css_png` — (F8) `.js`→`application/javascript`, `.css`→`text/css`, `.png`→`image/png` on the proxied branch (nosniff + wrong media type would brick the JS).
  - `test_daemon_down_graceful` — upstream unreachable → graceful in-app error body, not a raise.
- **Implement:** `samagra/api/corpus_proxy.py` — `class CorpusProxy` holding `{base_url, allowlist:frozenset[pattern], size_cap, timeout}`; `serve(path, method) -> (bytes, media_type, status)` doing: assert `method=="GET"`; `_normalize(path)` (single-decode, collapse `//`, reject `\`, reject post-decode `..`); per-segment `_SAFE_SEGMENT` (copy `publish/store.py:21`); match against the positive allowlist (refuse otherwise); `validate_qx_url`-style SSRF check on `base_url`; HTTP-GET the loopback daemon with the size cap + timeout; on the HTML shell inject `<base href>` + apply the enumerated absolute-prefix rewrite; for onedpull run the answer-marker body-scan; return bytes + correct media_type (extension → mimetype map, F8). Never forward POST. Graceful error body on daemon-down/timeout/over-cap.
- **Gate:** `pytest tests/test_corpus_proxy.py`.

**T2.7 — List + serve/proxy GET endpoints (all ORIGIN-GATED) + the `is_protected` prefix branch** *(depends: T2.5, T2.6)*
- **Test first:** `tests/test_corpus_api.py` (template: `test_published_api.py:2-4,27-34` — `TestClient(app)` + `monkeypatch.setattr(config, "<ROOT>", tmp_path)`), plus extend `tests/test_origin_auth.py`.
  - Per corpus: `test_<name>_list_empty_graceful` — missing root → 200 `{"available": false, ...}`, never 500 (mirror `/api/coverage`).
  - `test_<name>_list_populated` — with a fixture root, returns docs/topics/lectures + counts.
  - **`test_<name>_endpoints_are_origin_gated`** — (F2) `origin_auth.is_protected("GET","/api/corpus/<name>")` is `True` AND `is_protected("GET","/api/corpus/<name>/serve/anything")` is `True`; a non-loopback request without identity → 403.
  - **`test_is_protected_gets_corpus_prefix_branch`** — (F2) in `test_origin_auth.py`: `is_protected("GET","/api/corpus/x")` True, `is_protected("GET","/api/coverage")` still False (no regression to the existing exact-match set), `is_protected("GET","/api/published")` still False.
  - `test_gnocr_serve_index_headers` — `GET /api/corpus/gnocr/serve/` returns the native HTML with `X-Content-Type-Options: nosniff` + `Referrer-Policy: no-referrer` and **NO** `Content-Security-Policy` (F1 — no opaque-origin CSP on the same-origin trusted app).
  - `test_gnocr_serve_traversal_blocked` — hostile `../` / encoded / backslash path → 403/404.
  - `test_gnocr_serve_daemon_down_graceful` — :8931 down → graceful body, not 500.
  - `test_onedpull_serve_answer_path_refused` — `GET /api/corpus/onedpull/serve/api/question/5` → 403/404.
  - `test_lecturepdf_serve_read_apis_pass` — `/static/js/app.js`, `/api/stats`, `/api/lectures`, `/api/query_lexical`, `/api/diagrams/png/<r>/<d>/<n>` pass.
  - `test_lecturepdf_serve_write_apis_refused` — the whole write/compositions/key family refused.
  - `test_media_type_js_css_png_over_endpoint` — (F8) end-to-end media types correct on the serve branch.
- **Implement:**
  1. `origin_auth.py` — add the GET startswith branch (§0.1): `return path in _PROTECTED_GETS or path.startswith("/api/corpus/")`. Update the `is_protected` docstring.
  2. `app.py` — `@app.get("/api/corpus/{name}")` (delegates to `get_adapter(name).summary()` + a bounded artifact list; graceful-empty) and `@app.get("/api/corpus/{name}/serve/{path:path}")` (delegates to a `CorpusProxy` configured per corpus; returns `Response(content=bytes, media_type=..., headers={"X-Content-Type-Options":"nosniff","Referrer-Policy":"no-referrer"})` — **no CSP**, F1). `name` validated against `{gnocr,onedpull,lecturepdf}` (404 otherwise).
- **Gate:** `pytest tests/test_corpus_api.py tests/test_origin_auth.py`.

**T2.8 — Student-surface byte-untouched golden (F3)** *(depends: T2.7)*
- **Test first + implement:** `tests/test_corpus_student_surface_untouched.py` — with the corpus slice fully wired, assert `GET /learn`, `GET /api/published`, `GET /api/published/<c>/<l>`, and the `/api/learn/*` reads return **byte-identical + same-status** responses vs a baseline captured before the corpus routes are hit, and that no corpus code path references `governance.db`/`pratham.db`. (Grep-assert `corpus_proxy.py` + the 3 adapters import neither governance nor pratham modules.)
- **Gate:** `pytest tests/test_corpus_student_surface_untouched.py`.

**Task 2 acceptance gate:** all corpus config/adapter/proxy/api/origin/student-surface tests green; full `pytest` green (baseline 848 → +N); catalog-safety holds; **no** frontend change; **no** `_PROTECTED_POSTS` change; the new gated prefix branch proven.

---

# TASK 3 — The three windowed corpus apps (embed the native UI) · STAGE B · frontend-only · depends on Task 2

Each new corpus gets a windowed app whose body embeds the corpus's own UI via an `<iframe src="/api/corpus/<name>/serve/">` (same-origin, gated, CORS-safe per F1). **Depends on the Task-2 endpoint paths** (as string constants — compiles before the backend runs; only the smoke needs both).

**File set:** `frontend/src/types/contracts.ts`, `frontend/src/registry.ts`, `frontend/src/components/icons-data.ts`, `frontend/src/App.tsx` (APP_DIR only), `frontend/src/apps/{GnBrain,CorpusBrain,LectureBrain}/index.tsx` + `.test.tsx`, `frontend/src/App.test.tsx`.

**T3.1 — Registry + icons + AppId for the 3 apps** *(depends: Task 2 merged; the §7 checklist)*
- **Test first:** extend `frontend/src/App.test.tsx` (iterates `ORDER`, auto-covers wiring)
  - `it("registers gnocr, onedpull, lecturepdf apps")` — each id in `APPS`, `ORDER`, `ICONS`, `APP_DIR`.
  - `it("every ORDER id has an icon path")` — `ICONS[id]` non-empty for all `ORDER`.
- **Implement (surgical):**
  1. `contracts.ts:2-5` — add `"gnocr" | "onedpull" | "lecturepdf"` to the `AppId` union.
  2. `registry.ts` — add 3 `APPS` entries (`gnocr:{id:"gnocr",name:"GN Brain",accent:"#a16207",w:1000,h:680}`, `onedpull:{id:"onedpull",name:"Corpus Brain",accent:"#b45309",w:1040,h:700}`, `lecturepdf:{id:"lecturepdf",name:"Lecture Brain",accent:"#0369a1",w:1080,h:720}`) + append the 3 ids to `ORDER`.
  3. `icons-data.ts:10-41` — add 3 `ICONS` path entries (24×24, `|`-joined: card-catalog/book glyph for the two brains, projector/slide glyph for lectures).
  4. `App.tsx:60-80` `APP_DIR` — `gnocr:"GnBrain"`, `onedpull:"CorpusBrain"`, `lecturepdf:"LectureBrain"`.
- **Gate:** `npx vitest run src/App.test.tsx`; `tsc --noEmit`.

**T3.2 — The three embed-host apps** *(depends: T3.1; the 3 leaf apps parallel)*
- **Test first (one per app):** `apps/GnBrain/index.test.tsx`, `apps/CorpusBrain/index.test.tsx`, `apps/LectureBrain/index.test.tsx`
  - `it("renders an iframe pointing at the corpus serve endpoint")` — an `<iframe>` with `src` starting `/api/corpus/<name>/serve/`, `referrerPolicy="no-referrer"`, a fill style (`flex:1; width:100%; height:100%; border:0`), and **no `sandbox` attribute** (F1 — or, if present, `sandbox` includes `allow-same-origin allow-scripts`; the test asserts whichever is chosen and that it does NOT force an opaque origin).
  - `it("fills and reflows with the window (no fixed px height)")` — the iframe container uses `flex:1`/`100%`, not a hardcoded height (CSS box-model reflow; no ResizeObserver, per shell §3).
  - `it("shows an offline fallback when the serve endpoint errors")` — a health probe (`GET /api/corpus/<name>`) failure → a themed "brain offline — start the sidecar :<port>" panel instead of a blank iframe.
- **Implement:** `apps/GnBrain/index.tsx`, `apps/CorpusBrain/index.tsx`, `apps/LectureBrain/index.tsx` — each `export default function`, a flex-column filling the WindowFrame body with `<iframe src="/api/corpus/<name>/serve/" referrerPolicy="no-referrer" style={{flex:1,width:"100%",height:"100%",border:0,background:"#fff"}}/>`. A lightweight health probe (`GET /api/corpus/<name>`) swaps in the offline card on failure (theme via `var(--samagra-*)`). NO `sandbox` attribute (F1), distinguishing these trusted same-origin apps from the Pratham published-artifact iframe (which keeps its sandbox — untouched).
- **Gate:** `npx vitest run src/apps/GnBrain src/apps/CorpusBrain src/apps/LectureBrain`; `tsc --noEmit`; `npm run build`.

**T3.3 — (Optional) pure list-lib per corpus** — only if an app shows a SAMAGRA-native doc/lecture list in ADDITION to the iframe; factor the shaping into `frontend/src/lib/<corpus>/list.ts` + `.test.ts` (pure). **Default: pure iframe, skip T3.3.**

**Task 3 acceptance gate:** all 3 app vitest green; `App.test.tsx` green; `tsc --noEmit` + `npm run build` green; manual smoke: open each app across 3 themes, native UI renders inside the window (fetches succeed same-origin — F1 proven live), reflows on resize; offline card shows when a daemon is down.

---

## Cross-task dependency + parallelization map

```
STAGE A (parallel, disjoint file sets)
  Lane 1  Task 1 (frontend):  T1.1 → T1.2 → T1.3 → T1.4
  Lane 2  Task 2 (backend):   T2.1 → {T2.2, T2.3, T2.4, T2.6 parallel} → T2.5 → T2.7 → T2.8
STAGE B (after A merges)
  Lane 3  Task 3 (frontend):  T3.1 → T3.2 (3 leaf apps parallel) → [T3.3 skipped]
```

Recommended: Lanes 1 and 2 by two subagents concurrently (no shared files → no merge conflict); Lane 3 after both land. **Serialize all git commits** — a committing subagent must not overlap another (the D2 git-race lesson).

---

## Global acceptance gates (before merge)

1. `pytest` full suite green (baseline **848**; expect ~+35-50 new). Only the documented pre-existing reds/skips (`test_gdocs`, opt-in live smokes) — no NEW failures.
2. `npx vitest run` full suite green (baseline **639**; expect +new).
3. `tsc --noEmit` clean; `npm run build` green.
4. **Firewall/gate audit (grep the diff):** no new POST in `_PROTECTED_POSTS`; **every `/api/corpus/*` GET is gated** (the `is_protected` prefix branch proven); no write to any corpus root; `corpus_proxy` GET-only + positive-allowlist + normalization proven; onedpull answer families excluded AND body-scanned; **no `sandbox allow-scripts` CSP on the corpus serve endpoints** (F1) while the Pratham/`published` CSP is untouched; `_SAFE_SEGMENT` + normalization on every proxied path; size cap + timeout enforced; media types correct; no governance migration; the **student-surface byte-untouched golden** green (F3).
5. **Review gate (MANDATORY, not optional):** the new generic reverse-proxy boundary makes a dedicated **DEC-7-style Codex pre-merge review** of the proxy/serve/gate boundary REQUIRED (per the review's FIREWALL/GATE ruling), plus a `/review-gate` multi-lens adversarial pass (firewall + security + separate-entity + spec lenses). Report → `docs/codex-reviews/<N>-corpus-apps-premerge.report.md`.
6. **Owner notes / docs:** update `.env.example` (per-corpus block) and `docs/deploy-tunnel.md` — record the three optional localhost sidecars **with their exact launch commands**:
   - GN Brain: `python scripts\webui.py --port 8931` (cwd `C:\SandBox\claude_box\claude-GN-OCR\_brain`) → `http://127.0.0.1:8931`.
   - Corpus Brain: `C:\Python314\python.exe scripts\webui.py --port 8137` (cwd `C:\SandBox\gemini_box\onedpulls\_brain`) → `http://127.0.0.1:8137`.
   - Lecture Brain: `.venv\Scripts\python.exe -m uvicorn api.app:app --host 127.0.0.1 --port 8000` (cwd `C:\SandBox\claude_box\lecturepdfs\brain`) → `http://127.0.0.1:8000`.
   Note each daemon is OPTIONAL — the corpus listing works from the local store even when the daemon is down; only the embedded live UI degrades to the offline card. Update project trackers / `STATUS.html` at the phase boundary.

---

# TASK 4 — Pipeline-integration ANNEX (exploration only; ZERO implementation tasks)

> Attached **verbatim** as an exploration annex per Chairman Task 4. It is a discussion draft, NOT a ratified spec, and defines **no** implementation tasks in this plan. It is included so the reader understands where the read-only corpus apps built above could later feed the content factory. Any work it describes is a separate, separately-decided, separately-reviewed future phase (proposed "Phase H").

---

## PLAN (discussion draft — NOT a ratified spec): Integrating claude-GN-OCR, onedpulls, lecturepdfs into the SAMAGRA content factory + multi-stream publication

**Status:** exploration/plan only, per Chairman Task 4. Grounded in `docs/superpowers/specs/2026-06-23-samagra-content-factory-design.md`, `samagra/factory/{lines,dispatch,run}.py`, `samagra/factory/publish/{manifest,store,run,read}.py`, and the Mission-2 corpus intel. No code touched.

### 0. Fit assessment (one paragraph of honesty)

The factory's seed machinery is already prefix-generic: `Line.source_prefixes` is a tuple, `classify()` matches any prefix, `plan()` normalizes an arbitrary `seed_ref` string, and the `assignments` table stores `pipeline`/`seed_ref`/`artifact_ref` free-form — so **new seed families need NO governance migration**. The two real gaps are (a) **read adapters** for three new stores (two SQLite+Chroma catalogs, one LanceDB/JSONL brain — none of which the factory can read today; every current lane reads either `content.json` chapters, munshi, or combinedDBQues), and (b) the **publish layer is chapter-keyed**: `publish(chapter, lanes)` recovers artifacts from `product_created` events by textbook slug, and the G2 `/learn` reader assumes chapter→lane tabs. Multi-stream publication is therefore a publish/reader-shape change, not a factory-core change.

### 1. Seed-type candidates per corpus

All three corpora are **read-only sources** (DEC-3 family). Seeds are pointers, never copies.

#### A. claude-GN-OCR (`gnocr:` prefix)
- **Primary seed:** `gnocr:<doc_id>` — one of the 242 brain documents (`catalog.db documents.id`, stable; resolves title, page_count, chunks, assets). Example: `gnocr:117`.
- **Secondary (later):** `gnocr:topic:<topic_id>` — one of the 28 NCERT topics, fanning a *topic-synthesis* seed over its tagged docs. Deferred: only 25/242 docs are topic-tagged (10.3%) — topic seeds are starved until GN Brain's tagging improves (owner question Q3).
- **Adapter:** read-only `samagra/adapters/gnocr.py` over `_brain/catalog.db` via `sqlite3 mode=ro` (the Slice-R lesson: plain `mode=ro`, NOT `immutable=1` — both brains run WAL) + optional HTTP proxy to :8931 for previews/assets. Env: `SAMAGRA_GNOCR_BRAIN=C:\SandBox\claude_box\claude-GN-OCR\_brain`.
- **What the seed carries:** doc title, page span, chunk texts (`chunks.text_md`), figure crops (`assets`), preview URLs.

#### B. onedpulls (`onedpull:` prefix)
- **Primary seed:** `onedpull:doc:<doc_id>` — one of the 446 documents (kind ∈ test_paper/solutions/notes/book/question_bank/slides).
- **Question-set seed:** `onedpull:qset:<topic_id>[:<qtype>]` — a slice of the 13,015-question crown jewel; the natural feed for paper/drill-style lanes and the coverage graph.
- **Adapter:** `samagra/adapters/onedpull.py` over `_brain/catalog.db` (284 MB, `mode=ro`) and/or the :8137 GET endpoints (`/api/questions`, `/api/question/<id>`, `/api/coverage`, `/api/similar`). ⚠ This is a SECOND question engine beside combinedDBQues (:8790, DEC-15). Decision needed on precedence (Q1 below) — the honest default is: onedpulls is a *seed source and answer/solution-bearing corpus*, combinedDBQues stays the retrieval engine for the existing answer-free paper/drill lanes; do NOT silently merge them.
- ⚠ **Answer-leak surface:** onedpulls questions carry `answer` + `solution_md` inline. Any lane consuming them MUST route through the existing `_assert_no_answer_leak` structural guard (extended with onedpulls' render markers) or be an explicitly answer-BEARING lane behind its own gate (e.g. a `solutions` teacher-only lane) — never both in one artifact.

#### C. lecturepdfs (`lecturepdf:` prefix)
- **Primary seed:** `lecturepdf:topic:<slug>` — one of the ~16 distilled "How I teach this" topics; the highest-value unit (aligned with the StyleSeed mission — this is the teacher's own voice, distilled).
- **Secondary:** `lecturepdf:<batch-slug>/<lecture-id>` — a single lecture (897 total; batch + lecture_no + date from `/api/lectures`). Batch slugs need normalization (dir names have spaces/parentheses) — a git-committed crosswalk like Slice R's `chapter_map.json`.
- **Example seed:** `lecturepdf:example:<id>` — one of the 338 tagged worked examples.
- **Adapter:** prefer HTTP GETs against :8000 (`/api/lectures`, `/api/topic/{slug}`, `/api/examples`, `/api/query_lexical` — the no-key lexical path is the safe default; never call the write/compose/export/excalidraw endpoints), falling back to direct `data/corpus.jsonl` + `data/topics/*.md` reads. Avoid LanceDB/OpenAI-embedding coupling in v1.

**seed_ref discipline:** all three families must pass the F2/Codex-34 safe-slug/path-containment rule at any write boundary (the tracked factory-wide slug-hardening slice becomes a *prerequisite*, since these refs embed foreign IDs and path-ish segments — colons and slashes in `seed_ref` must never reach `EXPORT_DIR` paths unsanitized).

### 2. Lanes: existing vs new

#### Existing lanes that generalize cheaply (add a prefix to `source_prefixes` + teach the engine a second loader)
| Lane | Applies to | Work needed |
|---|---|---|
| `revision` / `lecture` | `gnocr:` docs, `lecturepdf:topic:` | The renderer reads `content.json` chapters today; needs a source-loader seam (`chapter-like dict` from OCR markdown / distilled topic notes). Medium effort, no new invariant. |
| `deck` | `gnocr:` (equations in chunks), `lecturepdf:topic:` | Same seam; equation extraction from OCR markdown is noisier — accept lower yield, never fabricate. |
| `samadhan` (LLM, opt-in) | all three | Cheapest win: ground-truth = the seed's own chunk text instead of a textbook chapter. DEC-8 reviewer firewall unchanged. |
| `figure` (LLM, opt-in) | `gnocr:` (8542 assets → redraw briefs), `lecturepdf:` (diagram runs) | Brief source changes from image-need flags to corpus figures; autocapture stays OFF. |
| `slides` (LLM, opt-in) | `lecturepdf:topic:`, `gnocr:` docs | `_source_text` already bounded to 16k chars — corpus-agnostic by construction. |
| `paper` / `drill` | **unchanged** — keep on combinedDBQues | Do NOT rewire to onedpulls in this slice (DEC-15 just landed; see Q1). |

#### New lane candidates (each opt-in `auto_fan=False` at birth, ordered by risk)
1. **`worksheet`** (`lecturepdf:` seeds, deterministic, local-write) — project a topic's worked examples (338-bank, difficulty/exam-style tagged) into a printable answer-free worksheet. Mirrors the deck/paper pattern; lowest risk.
2. **`digest`** (`gnocr:` seeds, deterministic, local-write) — a cleaned single-file HTML of an OCR'd notebook doc (chunks + figure crops, KaTeX). Essentially a re-render; escape-at-boundary lesson (C1) applies.
3. **`qcurate`** (`onedpull:qset:` seeds, deterministic) — an answer-free curated question selection with provenance, feeding the coverage graph's gap queue with a second supply. Requires the answer-leak guard extension FIRST.
4. **`solutionpack`** (`onedpull:` — answer-BEARING, teacher-only) — deliberately deferred; needs its own stream visibility decision (see §3) and its own DEC because it inverts the answer-free invariant.

**Default fan-out:** all new (prefix, lane) pairs start `auto_fan=False` except at most `revision` for `gnocr:` — proposal: keep EVERY new-corpus lane opt-in in v1, so `classify()` for the new prefixes returns `[]` and nothing changes for textbook seeds. Zero behavioral drift until the owner plans a lane explicitly.

### 3. Multi-stream publication — what it means concretely

**Recommendation: one `published/` store, a `stream` field in the manifest, N stream views in one reader.** Not separate stores, not separate readers.

- **Stream = seed family** (v1): `textbook` (existing, implicit), `gnocr`, `onedpull`, `lecturepdf`. Derived mechanically from the `seed_ref` prefix — no free-form taxonomy to curate.
- **Manifest:** G1's `manifest.json` is derived from immutable records (the MED#2 fix); add `stream` to each publication record + manifest entry, defaulting `"textbook"` when absent — **backward-compatible replay, no migration of existing records** (circular-motion + gauss-law re-derive as `stream=textbook`). `publish` CLI/HTTP gains `--stream` or infers it from the seed prefix of the recovered assignment.
- **Keying:** today `publish(chapter, lanes)` keys on textbook slug. Generalize the key to the seed_ref's tail with the stream as namespace: `published/<stream>/<key>/...` (the `_SAFE_SEGMENT` pair guard already anticipates two segments; a third segment needs the same containment review — flag for the DEC-7-style pre-merge review).
- **G2 reader:** `/api/published` grows a `stream` field per entry (additive JSON — old readers ignore it); `/learn` gets a stream switcher (tabs or a top-level filter) above the existing chapter list + Saar-led lane tabs. Anonymous `/learn` for the textbook stream must stay byte-equivalent-in-behavior (the G2/G4 invariant); a frozen-baseline commit before any stream JSX lands (the G4 §11 discipline).
- **Explicitly NOT multi-stream v1:** per-stream visibility/audience rules (public vs teacher-only) — that is the `solutionpack` question and a separate decision (Q4).

### 4. Invariants that MUST hold (all pre-existing, restated against the new surface)

1. **Read-only firewall extends to the 3 new corpora**: adapters use HTTP GET and/or `sqlite3 mode=ro` only; NEVER call lecturepdfs' write endpoints (`/api/compositions`, export, excalidraw, reveal); no file writes into any corpus root. The subsystem count goes 7→10 read-only sources; the two owner-capture write paths (munshi/mcd) stay the only subsystem writes.
2. **Never-automated publish gate unchanged** — new streams cross the SAME `approve-seed` → `build` → owner `publish` path; no stream auto-publishes; LLM lanes keep autocapture-OFF/adversarial review.
3. **No new prod write path** — new lanes are local-write (`kind="local"`) or `kind="llm"` (403 over HTTP, CLI-only); the mcd `seed` lane stays the sole prod writer; nothing writes back to GN Brain/onedpulls/lecturepdfs.
4. **No governance migration** — `assignments.pipeline/seed_ref/artifact_ref` absorb everything; the publish `stream` field is additive-JSON on the (non-governance) publication records; if a stream column ever seems needed in `governance.db`, that's a smell — stop and re-design.
5. **Answer-leak guard covers every onedpulls render** — extend `_ANSWER_MARKERS` with onedpulls' render vocabulary before ANY onedpulls-consuming lane ships; answer-bearing output is a separate, separately-decided lane, never mixed.
6. **DEC-8 reviewer firewall + advisory-only style scoring** structural on all new LLM lanes; DEC-9 NO AUDIO absolute.
7. **Path containment** — foreign IDs in seed_refs sanitized at every write boundary (the tracked factory-wide slug-hardening slice is a hard prerequisite).
8. **5 build() crash-safety guards byte-identical** — new lanes ride the existing lane-kind branch, never a new envelope.
9. **Localhost coupling is soft-fail** — the 3 brains live on fixed local ports (8931/8137/8000) and may be down; `preflight`/plan must refuse cleanly before any intent record (the anti-wedge pattern), like QX-down in C2.

### 5. Phased rollout suggestion

- **Phase H0 — prerequisite:** factory-wide slug/path-containment hardening (already tracked from Codex 34). Small, own review.
- **Phase H1 — adapters + catalog visibility (read-only, zero factory change):** three read-only adapters + catalog/console listing (docs/topics/lectures counts, search proxy). No lanes, no seeds, no publish change. Proves the stores are readable and the firewall shape. Own mini-review (new read surfaces only). *(NOTE: Tasks 2 + 3 of THIS plan implement exactly the read-only adapter/listing/native-UI-embedding half of H1 — the factory-seed half of H1 remains future work.)*
- **Phase H2 — first foreign-seed lane, deterministic:** `lecturepdf:topic:` → `worksheet` (or `gnocr:<doc>` → `digest`), opt-in, local-write. Golden thread: one real topic → captured artifact → NOT yet published. This is the first non-`textbook:`/`munshi:` seed through `plan/approve-seed/build` — expect small `run.py` seams (pointer resolution currently does `seed_ref.split(':',1)[-1].replace('-',' ')` — fine, but verify).
- **Phase H3 — multi-stream publish + reader:** `stream` field, `published/<stream>/<key>` layout, `/learn` stream switcher, additive `/api/published`. DEC-7-style Codex pre-merge review (publish boundary + path containment change) + 4-lens adversarial. Golden thread: publish the H2 artifact, verify at `/learn` alongside textbook chapters, anonymous textbook behavior unchanged, `governance.db` byte-isolated.
- **Phase H4 — onedpulls question integration:** answer-leak marker extension + `qcurate` lane + coverage-graph second-supply wiring. Own review (the leak guard is load-bearing).
- **Phase H5 (optional/deferred):** LLM lanes over foreign seeds (samadhan/slides/figure ground-truth seam), topic seeds for GN Brain once tagging improves, `solutionpack` + per-stream visibility (needs its own DEC).

Each phase: subagent-driven TDD, per-phase review gate, no phase piggybacks another's invariant change — the established cadence.

### 6. Open questions for the Chairman

1. **onedpulls vs combinedDBQues:** two question engines now exist (13,015 tagged w/ solutions vs 48,589 via :8790). Keep combinedDBQues as the paper/drill retrieval engine and treat onedpulls as a curation/coverage source (my recommendation), merge them (big slice, own design), or rewire paper/drill again?
2. **First foreign stream:** which corpus leads H2 — lecturepdfs topics (highest voice/StyleSeed affinity) or GN-OCR docs (largest untapped handwritten corpus)? Plan assumes lecturepdfs.
3. **GN Brain topic tagging:** only 10.3% of docs are topic-tagged. Is improving GN Brain's tagging (in ITS repo, not SAMAGRA's) an owner-side prerequisite for topic seeds, or do we stay doc-seeded?
4. **Stream visibility:** is every stream public on `/learn` like textbook chapters, or do some streams (raw handwritten digests? anything answer-bearing) want a signed-in/teacher-only tier? v1 assumes all-public, answer-free only.
5. **Brains as runtime dependencies:** should SAMAGRA depend on the three localhost GUIs being up (proxy model), or read their stores directly (sqlite/jsonl, no daemon)? Plan prefers direct-store for A/B and HTTP-GET for C — confirm.
6. **`lecturepdf` semantic search needs an OpenAI key** (LanceDB/1536-dim). v1 uses the no-key lexical fallback only — acceptable, or wire the key (a new key-consuming read path, worth a note in the review)?
7. **Console mirroring of the native GUIs** (iframing the card-catalog HTML / Vue SPA behind SAMAGRA's origin gate) — in scope at all, or is the catalog listing (H1) enough? Plan treats mirroring as out of scope. *(NOTE: Task 3 of THIS plan answers Q7 affirmatively for the read-only embedding case — the native GUIs ARE mirrored via the hardened, ORIGIN-GATED serve/proxy endpoints; the annex's "out of scope" note predates that Task-3 decision.)*

---

## Appendix — key verified anchors (absolute paths; re-verified 2026-07-09 against the dirty tree)

- Origin gate sets: `samagra\api\origin_auth.py:58-60` (`_PROTECTED_GETS`), `:63-71` (`is_protected`; POST arm has the `startswith("/api/gate/")` pattern `:68`; GET arm exact-match `:70` — F2 adds a `/api/corpus/` GET prefix branch here).
- Config precedent (MCD_ROOT): `samagra\config.py:63-68` (MCD_ROOT itself at `:68`); `_env_path` `:23-25`; QX server-URL SSRF pattern `:82-85`.
- SSRF guard to reuse per corpus: `samagra\api\qx_guard.py:21-37` (`host_is_allowed` / `validate_qx_url`).
- Adapter base + recipe: `samagra\adapters\base.py`; minimal templates `sims.py`, `booklets.py`; read-only sqlite `_ro` `qx.py:20-25` (no `immutable=1`, WAL); registry `samagra\adapters\__init__.py:14-23`.
- Catalog auto-flow + abort-on-error: `samagra\catalog.py:69-168`; read-only `connect_ro` `catalog.py:56-59`.
- Byte-serve + CSP/sandbox trio (published PRECEDENT — kept, distinguished, NOT copied to corpus serve): `samagra\api\app.py:223-247` (html-kind CSP at `:245-246`); segment guard `samagra\factory\publish\store.py:21`; resolve template `samagra\factory\publish\read.py:33-71`.
- Pure asset-rewrite reference (TOP-LEVEL, not under api/): `samagra\questions_proxy.py:11-23` (`_REL` `:11`, `absolutize_assets` `:14`).
- `/open` allowlist + guards: `samagra\api\app.py:61-64` (`ALLOWED_ROOTS`), `:72-113` (`_under_root`/`_open_servable`).
- Frontend registry/wiring: `frontend\src\registry.ts`; `frontend\src\types\contracts.ts:2-5`; `frontend\src\components\icons-data.ts:10-41`; `App.tsx` `APP_DIR:60-80`, root mount `:330-388`, `openApp`/`openAppMenu` `:157-159`, root click-dismiss `:333-336`, bare-desktop `onContextMenu` `:337-344` (`e.target!==e.currentTarget` guard `:341`), `windows.map` `:366`.
- Desktop-icon precedents: caption tile `frontend\src\shell\StartMenu.tsx:109-114`; stopPropagation `frontend\src\shell\Dock.tsx:65-69` (`AppIcon label=app.name` at `:86` → `role="img"`); work-area insets `frontend\src\lib\wm\geometry.ts:17-36`.
- Embedding precedent (iframe): `frontend\src\apps\Pratham\index.tsx:253-258` (`sandbox="allow-scripts"` `:256` — KEPT for published, NOT used on corpus apps).
- Corpus daemons (verified present + route-inventoried): GN Brain `_brain/webui/index.html` (43 KB, `fetch("/api/{stats,search,topics,ask,brief}"`) + `scripts/webui.py`; onedpull `_brain/webui/index.html` (54 KB, answer families `/api/{questions,question/<id>,coverage,similar/<id>}`) + `scripts/webui.py`; lecturepdf `brain/api/static/index.html` (Vue shell) + `brain/api/app.py` (read GETs vs write POSTs enumerated in §0.3).
- Test conventions: pytest `tests\test_published_api.py`, `tests\test_subsystem_adapters.py`, `tests\test_origin_auth.py`, `tests\test_catalog_refresh_safety.py`; vitest colocated `.test.tsx`/`.test.ts`, `App.test.tsx` (real stores). Baselines: **848 pytest / 639 vitest**.
