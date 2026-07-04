# DEC-7 pre-merge review: Phase G3 identity + publish write boundaries

Date: 2026-07-05
Repo: `C:/SandBox/claude_box/TeachingOS`
Branch/head reviewed: `feature/content-factory-phase-g3` at `840c079`
Base stated by review request: `main` at `5f714d0`
Scope: Phase G3's two inbound write boundaries and support code: `POST /api/factory/publish`, `POST /api/factory/unpublish`, their `origin_auth` registration, delegation to `samagra/factory/publish/run.py` and path guards; `POST /api/learn/login`, `POST /api/learn/logout`, `GET /api/learn/me`, `samagra/pratham/*`, G3 config/CLI additions; and a lighter pass over PRATHAM sign-in plus the Publish operator UI.

## Verdict

GO-WITH-CAVEATS.

I found no HIGH or MEDIUM issue in the two new backend write boundaries under the ratified G3 security model. The owner publish HTTP routes are in the protected POST table and only delegate to the already-reviewed G1 publish runner. The public PRATHAM login path writes through `samagra/pratham/store.py` to `config.PRATHAM_DB` only; I found no import or call path from PRATHAM login into `governance.db`, `published/`, `EXPORT_DIR`, inward factory `build()`, or the seven source subsystems.

One confirmed LOW frontend integration issue remains: the new Publish GUI expects the wrong shape from `/api/assignments`, so it can crash against the live backend response before the owner can use it.

## Findings

### 1. LOW - Publish GUI crashes on the real `/api/assignments` response shape

Evidence:
- `samagra/api/app.py:172-181` defines `GET /api/assignments` and returns an object: `{"assignments": gstore.list_assignments(conn), "events": gstore.list_events(conn)}`.
- `frontend/src/apps/Publish/index.tsx:15-18` fetches that endpoint as `useApi<AssignmentLike[]>("/api/assignments?...")` and passes `asg.data` directly to `publishRows`.
- `frontend/src/hooks/useApi.ts:19-37` returns the decoded backend JSON unchanged; it does not unwrap `assignments`.
- `frontend/src/lib/publishctl/rows.ts:19-24` types the first argument as `AssignmentLike[] | null | undefined` and immediately iterates it with `for (const a of assignments ?? [])`.
- `frontend/src/apps/Publish/index.test.tsx:7-11` mocks `/api/assignments` as a raw array, so the test does not cover the production response envelope.

Exploit scenario:
An authenticated owner opens the new Publish app. The backend returns the normal `/api/assignments` object, not an array. The render path calls `publishRows(asg.data, man.data)`, and `publishRows` attempts to iterate the object, producing a runtime `TypeError`. This does not bypass the backend owner gate, but it breaks the Phase G3 GUI publish/unpublish control before the owner can use the new route.

Suggested fix:
Type the fetch as the real assignments envelope and call `publishRows(asg.data?.assignments, man.data)`, or change `publishRows` to accept the backend envelope explicitly. Update `frontend/src/apps/Publish/index.test.tsx` to mock `{assignments, events}` so this cannot regress.

## Known Tracked Item

A parallel adversarial review already confirmed a LOW cookie-scope item: the `pratham_session` cookie is set with `path="/"` even though the spec prose says it should be honored only on `/api/learn/*`. I independently observed the current code sets the cookie at `samagra/api/app.py:315-317` with `path="/"` and deletes it at `samagra/api/app.py:321-327` with the same path. I am treating this as a known/tracked LOW item, not a new finding in this report.

## Boundary Review Notes

Owner publish boundary:
- `samagra/api/origin_auth.py:41-46` adds `/api/factory/publish` and `/api/factory/unpublish` to `_PROTECTED_POSTS`.
- `samagra/api/origin_auth.py:57-64` applies `_PROTECTED_POSTS` to POST requests.
- `samagra/api/origin_auth.py:198-205` allows protected requests through only for explicit dev/loopback paths, disabled-origin-auth mode, or `has_valid_identity()`.
- `samagra/api/origin_auth.py:180-195` implements the ratified G3 owner-auth model: verified Access JWT when `ACCESS_AUD` and `ACCESS_TEAM_DOMAIN` are configured, otherwise the documented weaker owner-email header fallback. This fallback is part of the governing spec's security model section 8, not new G3 auth code.
- `samagra/api/app.py:249-260` validates the HTTP body to a non-empty string `chapter` and optional `list[str]` `lanes`.
- `samagra/api/app.py:263-284` delegates publish/unpublish to `publish_run.publish()` and `publish_run.unpublish()` with `actor="owner"`. The HTTP route does not add a second filesystem writer.
- `samagra/factory/publish/run.py:33-49` normalizes and validates lane filters against publishable lanes.
- `samagra/factory/publish/run.py:102-182` publishes by reading captured local artifacts, writing frozen published files, appending `published` governance events, and refreshing the derived manifest.
- `samagra/factory/publish/run.py:187-242` unpublishes by appending `unpublished` events and immutable publication records; frozen bytes and history are retained.
- `samagra/factory/publish/store.py:21-33` validates path segments, and `samagra/factory/publish/store.py:101-107` applies those checks to `chapter` and artifact basename before writing under `PUBLISHED_DIR`.
- No new publish write mechanism was found beyond the G1 contract: writes remain `published/` frozen copies, publication records/manifest, and append-only governance events.

Public PRATHAM identity boundary:
- `samagra/api/app.py:289-334` marks PRATHAM identity as deliberately public and imports only `samagra.pratham.service` for login/logout/me.
- `samagra/api/app.py:305-317` handles login by validating a string code, calling `service.login()`, returning identical 401 invalid-code response when service returns `None`, and setting an opaque `HttpOnly`, `SameSite=Lax`, `Secure`-by-config cookie with TTL-derived `max_age`.
- `samagra/api/app.py:321-328` logs out by deleting the hashed session server-side and clearing the same cookie name.
- `samagra/api/app.py:331-334` resolves `/api/learn/me` through `service.current_student()` only.
- `samagra/pratham/identity.py:22-32` mints high-entropy enrollment codes/session tokens and hashes bearer secrets with SHA-256.
- `samagra/pratham/identity.py:61-78` documents and implements the in-process `RateLimiter` as best-effort and not a security boundary.
- `samagra/pratham/store.py:40-44` connects only to `config.PRATHAM_DB`; `samagra/pratham/store.py:16-33` creates only `students` and `sessions` tables.
- `samagra/pratham/store.py:94-135` limits PRATHAM mutations to student rows and session rows in `pratham.db`.
- `samagra/pratham/service.py:18-27` returns the plaintext enrollment code only from owner enrollment after persisting only `identity.hash_secret(code)`.
- `samagra/pratham/service.py:30-46` returns `None` for rate-limited, bad, or revoked login attempts and stores only `identity.hash_secret(token)` for sessions.
- `samagra/pratham/service.py:49-60` rejects absent, expired, missing, or revoked sessions; revoked students cannot retain access even if a session row survives.
- `samagra/pratham/service.py:63-71` deletes logout sessions and revokes students by setting `status="revoked"` plus deleting all sessions.
- `samagra/config.py:115-125` defines `PRATHAM_DB`, secure-cookie default, and session TTL; `.gitignore:13` ignores `*.db`, covering `pratham.db`.
- `samagra/__main__.py:331-347` prints the enrollment code only in `pratham enroll`; `pratham students` lists id/status/name/last-login but not the code or hash.
- No PRATHAM import boundary was found into governance store, publish store, `EXPORT_DIR`, factory `build()`, or source subsystem clients.

Frontend lighter pass:
- `frontend/src/lib/pratham/session.ts:9-37` uses only `/api/learn/login`, `/api/learn/logout`, and `/api/learn/me` with same-origin credentials.
- `frontend/src/apps/Pratham/index.tsx:21-61` keeps identity additive; the corpus fetch remains `/api/published`, and anonymous reading is not gated by session state.
- `frontend/src/apps/Pratham/index.tsx:90-117` renders student names and errors through React text nodes, not raw HTML.
- `frontend/src/apps/Pratham/index.tsx:148-160` renders chapter titles/slugs through React text nodes.
- `frontend/src/apps/Pratham/index.tsx:191-197` uses a sandboxed iframe for published artifacts.
- `frontend/src/lib/published/manifest.ts:97-100` percent-encodes chapter/lane/kind into artifact URLs.
- `frontend/src/apps/Publish/index.tsx:55-64` posts only to `/api/factory/publish` and `/api/factory/unpublish`; it does not create a frontend bypass around the backend owner gate.
- `frontend/src/apps/Publish/index.tsx:47-52` renders title and lane strings through React text nodes. No dangerouslySetInnerHTML or equivalent raw HTML rendering was found in the reviewed G3 UI paths.

## Test Evidence

Tests inspected:
- `tests/test_api_factory_publish.py:10-76` covers publish/unpublish protection registration, remote unauthenticated 403, handler reachability on loopback, unknown-chapter 409, delegation to G1 publish/unpublish, and bad lane body validation.
- `tests/test_api_learn.py:16-77` covers `/api/learn/*` staying public, login cookie creation, `/me`, logout, missing/bad code, and identical 401 for rate-limited valid-code attempts.
- `tests/test_g3_golden.py:13-77` covers HTTP publish, enroll-login-me-revoke, and governance byte isolation across PRATHAM operations.
- `tests/test_pratham_config.py:9-23` covers `PRATHAM_DB` as a sibling durable store, secure-cookie default, and positive TTL.
- `tests/test_pratham_service.py:12-22` covers code minting and hash-only persistence; the same file covers login/revoke/session behavior in later tests.
- `tests/test_pratham_cli.py:11-34` covers one-time CLI code print and verifies `students` output does not leak the stored code hash.
- `frontend/src/apps/Publish/index.test.tsx:7-29` covers the GUI action path, but its raw-array `/api/assignments` mock is also the test gap behind Finding 1.

Pytest and vitest were not re-run in this continuation because the task required read-only analysis only and no server/process changes. The review request states the current full gate is green: 607 pytest passed / 1 skip and 603 vitest.

GO-WITH-CAVEATS
