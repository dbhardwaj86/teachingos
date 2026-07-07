# Phase F2 — slides lane Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> Each task is a fresh implementer: write the failing test FIRST, watch it fail, write the
> minimal code, watch it pass, then commit. No task starts before the previous one is green.

**Goal:** Ship SAMAGRA's second and FINAL Phase-F lane — and its first **subprocess /
external-CLI** generation boundary. One textbook chapter → a NotebookLM-generated slide
deck: render the chapter to plain text → create an ephemeral NotebookLM notebook (via the
`nlm` CLI) → add the text as a source → kick off async slide generation → **synchronously
poll** `nlm studio status` until the deck is ready (bounded by `SAMAGRA_SLIDES_TIMEOUT`,
default 900s) → download the PDF → wrap it in a **self-contained data-URI HTML** (the only
shape G1/G2 can publish) → **delete the ephemeral notebook** in a `finally` → route through
build()'s existing `kind="llm"` path. The default posture (`SAMAGRA_SLIDES_AUTOCAPTURE` off)
routes every deck build to `changes` for owner eyes — a NotebookLM deck is a draft, never a
silent capture. **NO AUDIO, ever** (Chairman, absolute): the client exposes only slides +
notebook-lifecycle verbs.

**Architecture:** A new call site `samagra/clients/notebooklm_client.py` (the ONE NotebookLM
boundary, mirroring `image_client.py`'s shape but with a **subprocess runner** instead of an
SDK: ALL `nlm` invocations funnel through one injectable `runner` callable; tests inject a
fake runner returning canned `(stdout, stderr, returncode)` per command so NO standing test
shells out or hits Google; `configured()` probes `nlm login --check` and parses STDOUT for
the authenticated marker, NOT the exit code; deck-format env knobs validated fail-closed;
never-leak error extraction that never echoes raw `nlm` stderr / notebook text; `__repr__`
carries no secret). A new engine `samagra/factory/slides.py` (`build_slides(slug, *,
nlm=None)`): a deterministic chapter→source-text projection from `render.load_chapter`, a
self-contained data-URI wrapper-HTML builder (embed the PDF as
`data:application/pdf;base64,...`; HTML-escape untrusted title/text), and the orchestration
— preflight-gated create → add source → create slides → poll → download → wrap → write
`<slug>-slides.{html,json}` + the working `deck.pdf` → `finally` delete the ephemeral
notebook. Wiring is minimal: a `slides` Line (`kind="llm"`, `auto_fan=False`), a `run_line`
special-case ahead of the generic samadhan branch, a lane-dispatched build() preflight, a
`validate_product` slides branch, and one explicit `needs_review` clause honoring
`SAMAGRA_SLIDES_AUTOCAPTURE`. No new prod write path, no migration, no new assignment status,
publish gate untouched. HTTP-403 free via `kind="llm"`.

**Tech Stack:** Python 3.11, the external `nlm` CLI (installed at `C:\Users\abc\.local\bin\nlm`,
version 0.6.9 — an owner-provisioned binary, **NOT a pip package**, so requirements.txt gains
NO new dependency), pytest with an injectable fake subprocess runner (fully offline). Windows;
tests via `.\.venv\Scripts\python.exe -m pytest`.

**Spec:** `docs/superpowers/specs/2026-07-07-samagra-content-factory-phase-f2-slides-lane-design.md`
**Branch:** `feature/content-factory-phase-f2-slides` (create it before Task 1 if not present)

**Baseline gate before Task 1:** 771 pytest (2 skips = opt-in live LLM smoke + live image
smoke; the live QX smoke also skips offline) / 639 vitest. Frontend is untouched by F2, so
the 639 vitest baseline is unchanged and is asserted-by-inspection in Task 6 (no vitest rerun
needed).

**Live-pinned `nlm` command strings (confirmed against `nlm` 0.6.9 `--help`, no `--confirm`
ever run):**

| Step | argv list |
|---|---|
| auth probe | `["nlm", "login", "--check"]` |
| create notebook | `["nlm", "notebook", "create", "<title>"]` |
| add source | `["nlm", "source", "add", "<nb>", "--text", "<text>", "--wait", "--wait-timeout", "<T>"]` |
| create deck | `["nlm", "slides", "create", "<nb>", "--confirm", "--format", "<fmt>", "--length", "<len>"]` |
| poll status | `["nlm", "studio", "status", "<nb>", "--json"]` |
| download | `["nlm", "download", "slide-deck", "<nb>", "--id", "<aid>", "--format", "<dl>", "-o", "<out>", "--no-progress"]` |
| delete | `["nlm", "notebook", "delete", "<nb>", "--confirm"]` |

**Deviations from the spec's pinned §3.1 table, reconciled (see also the notes at plan end):**
1. **`nlm login --check` exit code:** the spec §3.3/§3.1 claims it "exits 0 even when auth is
   expired". The REAL 0.6.9 behavior is `EXIT=1` on expired auth (stdout carries
   `✗ Authentication Error`). The spec's **stdout-parse** `configured()` is still exactly
   right and is what this plan implements verbatim (parse stdout for the authenticated
   marker, ignore the exit code) — it is strictly safer regardless of which way the exit code
   points, and it is the named review-34 focus. The only factual correction is that the exit
   code happens to be nonzero on failure here; the design does not depend on that.
2. **`nlm login --check` is an OPTION on `nlm login`** (`nlm login --check`), exactly as the
   spec pinned. Confirmed.
3. All other flags (`notebook create [TITLE]`, `source add … --text/--wait/--wait-timeout`,
   `slides create … --confirm/--format/--length`, `studio status … --json`, `download
   slide-deck … --id/--format/-o/--no-progress`, `notebook delete … --confirm`) match the
   spec pin exactly.

**Commit discipline (house rule, learned the hard way):** serialize ALL git — never run a
background git commit while a subagent is also committing. Each task commits exactly once at
its end.

---

### Task 1: `notebooklm_client.py` — the ONE NotebookLM call site (subprocess runner, TDD)

**Files:**
- Create: `samagra/clients/notebooklm_client.py`
- Create: `tests/test_notebooklm_client.py`

The ONE NotebookLM boundary: an injectable `runner` seam (default = a thin `subprocess.run`
wrapper) through which EVERY `nlm` invocation funnels. `configured()` probes `nlm login
--check` and parses STDOUT for the authenticated marker (NOT the exit code). Deck-format env
knobs validated fail-closed at construction. Typed methods pin the exact argv the fake runner
captures. Never-leak: a non-success raises a concise `RuntimeError` naming the `nlm`
subcommand and a sanitized reason — it never echoes raw `nlm` stderr, the chapter text, or
notebook content. `__repr__` carries no secret (there is no SAMAGRA secret — `nlm` owns the
Google OAuth creds).

- [ ] **Step 1: Write the failing tests** — `tests/test_notebooklm_client.py`:

```python
"""The ONE NotebookLM call site (Phase F2, the slides lane). All offline: a FAKE
subprocess runner scripts per-command {stdout, stderr, returncode}; NO standing
test shells out or touches Google. Mirrors tests/test_image_client.py's discipline
but the seam is a `runner` callable, not an SDK."""
import json

import pytest

from samagra.clients import notebooklm_client
from samagra.clients.notebooklm_client import NotebookLMClient, configured


# ---------- a scriptable fake subprocess runner ----------

class RunResult:
    """The shape the runner returns: stdout / stderr / returncode."""
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


class FakeRunner:
    """Records every argv list; returns a scripted RunResult keyed on a matcher.
    A matcher is (predicate(argv)->bool, RunResult). The first match wins; an
    unmatched argv returns a default ok result so a test only scripts what it cares
    about. NEVER shells out."""
    def __init__(self, script=None, default=None):
        self.calls = []
        self._script = script or []
        self._default = default if default is not None else RunResult(stdout="", returncode=0)

    def __call__(self, args, *, timeout=None):
        self.calls.append(list(args))
        for pred, res in self._script:
            if pred(args):
                return res
        return self._default


def _authed(argv):
    return argv[:3] == ["nlm", "login", "--check"]


def _client(monkeypatch, runner):
    # deck-format knobs unset -> defaults; no env secret needed (nlm owns auth).
    for v in ("SAMAGRA_SLIDES_FORMAT", "SAMAGRA_SLIDES_LENGTH",
              "SAMAGRA_SLIDES_DOWNLOAD_FORMAT", "SAMAGRA_NLM_BIN"):
        monkeypatch.delenv(v, raising=False)
    return NotebookLMClient(runner=runner)


# ---------- configured(): STDOUT parse, NOT exit code ----------

def test_configured_true_on_authenticated_stdout(monkeypatch):
    monkeypatch.delenv("SAMAGRA_NLM_BIN", raising=False)
    runner = FakeRunner(script=[(_authed, RunResult(stdout="✓ Authenticated\n", returncode=0))])
    assert configured(runner=runner) is True


def test_configured_false_on_expired_stdout_even_if_exit_zero(monkeypatch):
    # THE trap the spec pins: nlm login --check can exit 0 while auth is expired.
    # We parse stdout, never the exit code.
    monkeypatch.delenv("SAMAGRA_NLM_BIN", raising=False)
    runner = FakeRunner(script=[(_authed,
        RunResult(stdout="✗ Authentication Error\n  expired.\n", returncode=0))])
    assert configured(runner=runner) is False


def test_configured_false_on_expired_stdout_exit_one(monkeypatch):
    # The REAL nlm 0.6.9 behavior on expiry (EXIT=1) also reads as unconfigured.
    monkeypatch.delenv("SAMAGRA_NLM_BIN", raising=False)
    runner = FakeRunner(script=[(_authed,
        RunResult(stdout="✗ Authentication Error\n", returncode=1))])
    assert configured(runner=runner) is False


def test_configured_false_when_nlm_absent(monkeypatch):
    # A runner that raises FileNotFoundError models a missing nlm executable.
    monkeypatch.delenv("SAMAGRA_NLM_BIN", raising=False)
    def boom(args, *, timeout=None):
        raise FileNotFoundError("nlm")
    assert configured(runner=boom) is False


def test_configured_never_raises_on_runner_error(monkeypatch):
    # Any probe failure -> a clean fail-closed False (no raise into preflight).
    monkeypatch.delenv("SAMAGRA_NLM_BIN", raising=False)
    def boom(args, *, timeout=None):
        raise RuntimeError("subprocess exploded")
    assert configured(runner=boom) is False


# ---------- deck-format env validation (fail-closed at construction) ----------

def test_unknown_format_fails_closed(monkeypatch):
    monkeypatch.setenv("SAMAGRA_SLIDES_FORMAT", "fancy_deck")
    with pytest.raises(RuntimeError):
        NotebookLMClient(runner=FakeRunner())


def test_unknown_length_fails_closed(monkeypatch):
    monkeypatch.setenv("SAMAGRA_SLIDES_LENGTH", "epic")
    with pytest.raises(RuntimeError):
        NotebookLMClient(runner=FakeRunner())


def test_unknown_download_format_fails_closed(monkeypatch):
    monkeypatch.setenv("SAMAGRA_SLIDES_DOWNLOAD_FORMAT", "keynote")
    with pytest.raises(RuntimeError):
        NotebookLMClient(runner=FakeRunner())


def test_default_deck_knobs(monkeypatch):
    for v in ("SAMAGRA_SLIDES_FORMAT", "SAMAGRA_SLIDES_LENGTH",
              "SAMAGRA_SLIDES_DOWNLOAD_FORMAT"):
        monkeypatch.delenv(v, raising=False)
    c = NotebookLMClient(runner=FakeRunner())
    assert c._fmt == "detailed_deck"
    assert c._length == "default"
    assert c._dl_format == "pdf"


# ---------- typed methods pin the exact argv ----------

def test_create_notebook_pins_argv_and_parses_id(monkeypatch):
    runner = FakeRunner(script=[(
        lambda a: a[:3] == ["nlm", "notebook", "create"],
        RunResult(stdout="Created notebook: nb_abc123\n", returncode=0))])
    c = _client(monkeypatch, runner)
    nb = c.create_notebook("SAMAGRA slides: circular-motion deadbeef")
    assert nb == "nb_abc123"
    argv = runner.calls[0]
    assert argv[:3] == ["nlm", "notebook", "create"]
    # title is ONE argv element (never a shell string).
    assert "SAMAGRA slides: circular-motion deadbeef" in argv


def test_add_text_source_pins_argv(monkeypatch):
    runner = FakeRunner(script=[(
        lambda a: a[:3] == ["nlm", "source", "add"],
        RunResult(stdout="ok\n", returncode=0))])
    c = _client(monkeypatch, runner)
    c.add_text_source("nb_1", "the chapter text", wait_timeout=900)
    argv = runner.calls[0]
    assert argv[:4] == ["nlm", "source", "add", "nb_1"]
    assert "--text" in argv
    # the chapter text is a single argv element.
    assert "the chapter text" in argv
    assert "--wait" in argv
    ti = argv.index("--wait-timeout")
    assert argv[ti + 1] == "900"


def test_create_slides_pins_argv(monkeypatch):
    runner = FakeRunner(script=[(
        lambda a: a[:3] == ["nlm", "slides", "create"],
        RunResult(stdout="kicked off\n", returncode=0))])
    c = _client(monkeypatch, runner)
    c.create_slides("nb_1")
    argv = runner.calls[0]
    assert argv[:4] == ["nlm", "slides", "create", "nb_1"]
    assert "--confirm" in argv
    assert argv[argv.index("--format") + 1] == "detailed_deck"
    assert argv[argv.index("--length") + 1] == "default"


def test_studio_status_parses_json(monkeypatch):
    payload = {"artifacts": [
        {"type": "slide_deck", "status": "completed", "id": "art_9"}]}
    runner = FakeRunner(script=[(
        lambda a: a[:3] == ["nlm", "studio", "status"],
        RunResult(stdout=json.dumps(payload), returncode=0))])
    c = _client(monkeypatch, runner)
    out = c.studio_status("nb_1")
    assert out == payload
    argv = runner.calls[0]
    assert argv[:4] == ["nlm", "studio", "status", "nb_1"]
    assert "--json" in argv


def test_studio_status_unparseable_json_fails_closed(monkeypatch):
    runner = FakeRunner(script=[(
        lambda a: a[:3] == ["nlm", "studio", "status"],
        RunResult(stdout="not json at all", returncode=0))])
    c = _client(monkeypatch, runner)
    with pytest.raises(RuntimeError):
        c.studio_status("nb_1")


def test_download_slide_deck_pins_argv_and_returns_path(monkeypatch, tmp_path):
    out = tmp_path / "deck.pdf"
    def _write_pdf(a):
        out.write_bytes(b"%PDF-1.4 fake")
        return True
    runner = FakeRunner(script=[(
        lambda a: a[:3] == ["nlm", "download", "slide-deck"] and _write_pdf(a),
        RunResult(stdout="downloaded\n", returncode=0))])
    c = _client(monkeypatch, runner)
    p = c.download_slide_deck("nb_1", "art_9", out)
    assert str(p) == str(out)
    argv = runner.calls[0]
    assert argv[:3] == ["nlm", "download", "slide-deck"]
    assert argv[3] == "nb_1"
    assert argv[argv.index("--id") + 1] == "art_9"
    assert argv[argv.index("--format") + 1] == "pdf"
    assert argv[argv.index("-o") + 1] == str(out)
    assert "--no-progress" in argv


def test_delete_notebook_pins_argv(monkeypatch):
    runner = FakeRunner(script=[(
        lambda a: a[:3] == ["nlm", "notebook", "delete"],
        RunResult(stdout="deleted\n", returncode=0))])
    c = _client(monkeypatch, runner)
    c.delete_notebook("nb_1")
    argv = runner.calls[0]
    assert argv[:4] == ["nlm", "notebook", "delete", "nb_1"]
    assert "--confirm" in argv


# ---------- never-leak on a non-success ----------

def test_nonzero_call_raises_naming_verb_not_stderr_blob(monkeypatch):
    runner = FakeRunner(script=[(
        lambda a: a[:3] == ["nlm", "slides", "create"],
        RunResult(stdout="", stderr="SECRET-COOKIE=abc123; session=leakme",
                  returncode=2))])
    c = _client(monkeypatch, runner)
    with pytest.raises(RuntimeError) as e:
        c.create_slides("nb_1")
    msg = str(e.value)
    assert "slides create" in msg              # names the verb
    assert "SECRET-COOKIE" not in msg          # never echoes raw stderr
    assert "leakme" not in msg


def test_add_text_source_error_never_echoes_chapter_text(monkeypatch):
    runner = FakeRunner(script=[(
        lambda a: a[:3] == ["nlm", "source", "add"],
        RunResult(stdout="", stderr="boom", returncode=1))])
    c = _client(monkeypatch, runner)
    with pytest.raises(RuntimeError) as e:
        c.add_text_source("nb_1", "SUPER SECRET CHAPTER PROSE", wait_timeout=60)
    assert "SUPER SECRET CHAPTER PROSE" not in str(e.value)


# ---------- nlm binary override + argv shape ----------

def test_nlm_bin_override_changes_argv0(monkeypatch):
    monkeypatch.setenv("SAMAGRA_NLM_BIN", r"C:\tools\nlm.exe")
    runner = FakeRunner(script=[(
        lambda a: a[1:3] == ["notebook", "delete"],
        RunResult(stdout="deleted\n", returncode=0))])
    c = NotebookLMClient(runner=runner)
    c.delete_notebook("nb_1")
    assert runner.calls[0][0] == r"C:\tools\nlm.exe"


def test_args_passed_as_list_never_shell_string(monkeypatch):
    runner = FakeRunner(script=[(
        lambda a: True, RunResult(stdout="Created notebook: nb_x\n", returncode=0))])
    c = _client(monkeypatch, runner)
    c.create_notebook("a title with spaces & <brackets>")
    # every recorded call is a LIST, and the title is one element (no shell join).
    assert isinstance(runner.calls[0], list)
    assert "a title with spaces & <brackets>" in runner.calls[0]


# ---------- repr never leaks ----------

def test_repr_has_no_secret(monkeypatch):
    c = _client(monkeypatch, FakeRunner())
    r = repr(c)
    assert "slides" in r or "NotebookLM" in r
    assert "cookie" not in r.lower() and "token" not in r.lower()
```

- [ ] **Step 2: Run to verify failure**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_notebooklm_client.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'samagra.clients.notebooklm_client'`
(the module does not exist yet).

- [ ] **Step 3: Minimal implementation** — `samagra/clients/notebooklm_client.py`:

```python
"""The ONE NotebookLM call site (Phase F2, the slides lane) — mirrors
clients/image_client.py as the single boundary to an external generation service,
but the "SDK" is the external `nlm` CLI reached through a SUBPROCESS runner.

SAFETY: this lane holds NO SAMAGRA secret — `nlm` stores the Google OAuth creds
itself (run `nlm login`). configured() probes `nlm login --check` and parses its
STDOUT for the authenticated marker, NOT the exit code (nlm can print
'✗ Authentication Error' — pinned in the spec). Every `nlm` invocation funnels
through ONE injectable `runner` callable (default = a thin subprocess.run wrapper),
so tests inject a fake runner and NO standing test shells out or touches Google.
A non-success raises a concise RuntimeError naming the nlm subcommand and a
sanitized reason — it NEVER echoes raw `nlm` stderr blobs (which can carry
cookies/session hints), the chapter text, or notebook content. `__repr__` carries
no secret. NO AUDIO/VIDEO: this client exposes only slides + notebook-lifecycle
methods, so audio/video verbs are unreachable by construction (spec §4.10).
"""
from __future__ import annotations

import json
import os
import subprocess

_FORMATS = ("detailed_deck", "presenter_slides")
_LENGTHS = ("default", "short")
_DL_FORMATS = ("pdf", "pptx")

_AUTH_OK_MARKER = "✓ Authenticated"
_AUTH_FAIL_MARKER = "Authentication Error"

# per-call subprocess timeout (a hung `nlm` is killed); the slides POLL uses the
# lane's own total timeout on top of this, in the engine.
_CALL_TIMEOUT = 120


def _nlm_bin() -> str:
    return (os.environ.get("SAMAGRA_NLM_BIN") or "nlm").strip() or "nlm"


def _default_runner(args, *, timeout=None):
    """The real seam: run `nlm` as a subprocess (args is a LIST — never a shell
    string, so there is no shell injection). Returns a completed-process-like object
    with .stdout / .stderr / .returncode. text=True decodes as UTF-8."""
    return subprocess.run(
        list(args), capture_output=True, text=True, encoding="utf-8",
        timeout=timeout if timeout is not None else _CALL_TIMEOUT)


def configured(*, runner=None) -> bool:
    """True iff `nlm login --check` reports an authenticated session. Parses STDOUT
    for the success marker, NOT the exit code (nlm can exit 0 while expired — and,
    on 0.6.9, exits 1 while expired; either way stdout is authoritative). Never
    raises — a missing `nlm` executable / any probe failure -> a clean fail-closed
    False (so preflight refuses without wedging an in-flight assignment)."""
    run = runner or _default_runner
    try:
        res = run([_nlm_bin(), "login", "--check"], timeout=_CALL_TIMEOUT)
    except Exception:  # noqa: BLE001 - missing nlm / subprocess error -> unconfigured
        return False
    out = getattr(res, "stdout", "") or ""
    if _AUTH_FAIL_MARKER in out:
        return False
    return _AUTH_OK_MARKER in out


class NotebookLMClient:
    def __init__(self, *, runner=None):
        self._runner = runner or _default_runner
        self._bin = _nlm_bin()
        self._fmt = (os.environ.get("SAMAGRA_SLIDES_FORMAT") or "detailed_deck").strip()
        if self._fmt not in _FORMATS:
            raise RuntimeError(
                f"SAMAGRA_SLIDES_FORMAT must be one of {_FORMATS} (got {self._fmt!r})")
        self._length = (os.environ.get("SAMAGRA_SLIDES_LENGTH") or "default").strip()
        if self._length not in _LENGTHS:
            raise RuntimeError(
                f"SAMAGRA_SLIDES_LENGTH must be one of {_LENGTHS} (got {self._length!r})")
        self._dl_format = (os.environ.get("SAMAGRA_SLIDES_DOWNLOAD_FORMAT") or "pdf").strip()
        if self._dl_format not in _DL_FORMATS:
            raise RuntimeError(
                f"SAMAGRA_SLIDES_DOWNLOAD_FORMAT must be one of {_DL_FORMATS} "
                f"(got {self._dl_format!r})")

    # -- the ONE run helper: every nlm call funnels through here --
    def _run(self, args, *, verb: str, timeout=None):
        """Run one nlm invocation (args is a LIST). On a non-zero returncode raise a
        RuntimeError naming the VERB and a sanitized reason — NEVER the raw stderr
        blob (cookies/session), the chapter text, or notebook content."""
        try:
            res = self._runner(list(args), timeout=timeout)
        except FileNotFoundError as e:
            raise RuntimeError(f"nlm {verb} failed: nlm executable not found") from e
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(f"nlm {verb} timed out") from e
        rc = getattr(res, "returncode", 0)
        if rc != 0:
            raise RuntimeError(f"nlm {verb} failed (exit {rc})")
        return res

    def create_notebook(self, title: str) -> str:
        res = self._run([self._bin, "notebook", "create", str(title)],
                        verb="notebook create")
        nb = _parse_notebook_id(getattr(res, "stdout", "") or "")
        if not nb:
            raise RuntimeError("nlm notebook create returned no parseable notebook id")
        return nb

    def add_text_source(self, nb: str, text: str, *, wait_timeout: int) -> None:
        self._run([self._bin, "source", "add", str(nb), "--text", str(text),
                   "--wait", "--wait-timeout", str(int(wait_timeout))],
                  verb="source add", timeout=int(wait_timeout) + _CALL_TIMEOUT)

    def create_slides(self, nb: str) -> None:
        self._run([self._bin, "slides", "create", str(nb), "--confirm",
                   "--format", self._fmt, "--length", self._length],
                  verb="slides create")

    def studio_status(self, nb: str) -> dict:
        res = self._run([self._bin, "studio", "status", str(nb), "--json"],
                        verb="studio status")
        raw = getattr(res, "stdout", "") or ""
        try:
            return json.loads(raw)
        except (TypeError, ValueError) as e:
            # never echo the raw payload (could carry source text)
            raise RuntimeError(
                f"nlm studio status returned unparseable JSON (chars={len(raw)})") from e

    def download_slide_deck(self, nb: str, artifact_id: str, out_path):
        self._run([self._bin, "download", "slide-deck", str(nb), "--id",
                   str(artifact_id), "--format", self._dl_format, "-o",
                   str(out_path), "--no-progress"],
                  verb="download slide-deck")
        return out_path

    def delete_notebook(self, nb: str) -> None:
        self._run([self._bin, "notebook", "delete", str(nb), "--confirm"],
                  verb="notebook delete")

    def __repr__(self) -> str:
        return (f"NotebookLMClient(bin={self._bin!r}, format={self._fmt!r}, "
                f"length={self._length!r}, download={self._dl_format!r})")


def _parse_notebook_id(stdout: str) -> str:
    """Best-effort parse of the created notebook id from `nlm notebook create`
    stdout. nlm prints a line like 'Created notebook: <id>'; take the last
    whitespace token of the first line that mentions a notebook. Returns '' if
    nothing parseable (the caller raises)."""
    for line in (stdout or "").splitlines():
        low = line.lower()
        if "notebook" in low and ":" in line:
            tail = line.rsplit(":", 1)[-1].strip()
            token = tail.split()[-1] if tail.split() else ""
            if token:
                return token
    return ""
```

> **Implementer note — `configured()` is a module function AND parametrized by `runner`.**
> `image_client.configured()` takes no args; F2's `configured(*, runner=None)` does, so a
> test can inject the fake runner without constructing a client. `slides.preflight` calls
> `notebooklm_client.configured()` with NO runner (uses the real `_default_runner`), so a
> missing/expired `nlm` reads as unconfigured and refuses BEFORE build() records intent. Keep
> the marker constants (`✓ Authenticated` / `Authentication Error`) as module constants; the
> stdout-parse is the named review-34 focus.

- [ ] **Step 4: Run again**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_notebooklm_client.py -q`
Expected: PASS (all ~21 tests green).

- [ ] **Step 5: Commit**

```bash
git add samagra/clients/notebooklm_client.py tests/test_notebooklm_client.py
git commit -m "feat(f2): notebooklm_client — the ONE NotebookLM call site (nlm subprocess)

Every nlm invocation funnels through one injectable runner seam (default = a thin
subprocess.run wrapper); tests inject a fake runner so no standing test shells out
or touches Google. configured() parses `nlm login --check` STDOUT for the
authenticated marker, NOT the exit code (nlm can misreport the code on expiry).
Deck-format env knobs (format/length/download-format) validated fail-closed at
construction. Typed methods pin the exact argv (list, never a shell string; the
chapter text is one element). A non-success raises naming the nlm verb and a
sanitized reason — never the raw stderr blob / chapter text / notebook content.
NO AUDIO/VIDEO: the client exposes only slides + notebook-lifecycle methods.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: `slides.py` — pure source-text projection + data-URI wrapper HTML (TDD)

**Files:**
- Create: `samagra/factory/slides.py`
- Create: `tests/test_factory_slides.py`

The deterministic, I/O-free half: `_source_text(content)` projects a chapter to a clean text
document (title + section headings + prose/equation/callout text — the whole-chapter
generalization of figure's `_section_text`), truncated to a bounded prefix; and
`_wrapper_html(...)` embeds the deck PDF as a `data:application/pdf;base64,...` data URI in a
self-contained single file (with an `<embed>` + a same-page download link), HTML-escaping any
untrusted title/text. No `nlm`, no network, no disk (beyond the caller's fixture).

- [ ] **Step 1: Write the failing tests** — `tests/test_factory_slides.py`:

```python
"""Phase F2 slides lane — pure source-text projection + data-URI wrapper HTML.
Offline; a frozen in-memory fixture chapter + fake PDF bytes, no live corpus, no
nlm."""
import base64

import pytest

from samagra.factory import slides


_CHAPTER = {
    "title": "Circular Motion",
    "subtitle": "Uniform & non-uniform",
    "sections": [
        {"title": "Uniform circular motion",
         "blocks": [
             {"type": "prose", "html": "<p>The speed is constant.</p>"},
             {"type": "equation", "tex": "a = v^2/r"},
         ]},
        {"title": "Coriolis force",
         "blocks": [
             {"type": "callout", "html": "<div>Rotating frames add fictitious forces.</div>"},
         ]},
    ],
}


# ---------- source-text projection ----------

def test_source_text_carries_title_headings_and_body():
    txt = slides._source_text(_CHAPTER)
    assert "Circular Motion" in txt
    assert "Uniform circular motion" in txt
    assert "Coriolis force" in txt
    assert "The speed is constant." in txt        # prose html stripped to text
    assert "a = v^2/r" in txt                       # equation tex carried
    assert "Rotating frames add fictitious forces." in txt


def test_source_text_strips_html_tags():
    txt = slides._source_text(_CHAPTER)
    assert "<p>" not in txt and "<div>" not in txt


def test_source_text_empty_chapter_is_nonempty_title_only():
    txt = slides._source_text({"title": "Gauss Law", "sections": []})
    assert "Gauss Law" in txt


def test_source_text_truncates_to_bounded_prefix(monkeypatch):
    monkeypatch.setattr(slides, "_SOURCE_MAX_CHARS", 40)
    big = {"title": "Big", "sections": [
        {"title": "S", "blocks": [{"type": "prose", "html": "x" * 500}]}]}
    txt, truncated = slides._source_text_bounded(big)
    assert len(txt) <= 40
    assert truncated is True


def test_source_text_bounded_not_truncated_when_small():
    txt, truncated = slides._source_text_bounded(_CHAPTER)
    assert truncated is False


# ---------- data-URI wrapper HTML ----------

_PDF = b"%PDF-1.4\nfake-deck-bytes\n%%EOF"


def test_wrapper_embeds_pdf_data_uri_and_download_link():
    html = slides._wrapper_html("Circular Motion", _PDF, deck_format="pdf",
                                embed_max=8 * 1024 * 1024)
    b64 = base64.b64encode(_PDF).decode("ascii")
    assert f"data:application/pdf;base64,{b64}" in html
    assert "<embed" in html and 'type="application/pdf"' in html
    assert "download" in html                        # a same-page download link
    # self-contained: no external references.
    assert "http://" not in html and "https://" not in html
    assert 'src="deck' not in html


def test_wrapper_escapes_untrusted_title():
    html = slides._wrapper_html("Gauss & Fields <cube>", _PDF, deck_format="pdf",
                                embed_max=8 * 1024 * 1024)
    assert "Gauss & Fields <cube>" not in html
    assert "Gauss &amp; Fields &lt;cube&gt;" in html


def test_wrapper_oversize_deck_degrades_to_download_only_card():
    # A deck larger than embed_max wraps as a download-only card (no <embed>), still
    # self-contained.
    html = slides._wrapper_html("Big Deck", _PDF, deck_format="pdf", embed_max=4)
    b64 = base64.b64encode(_PDF).decode("ascii")
    assert "<embed" not in html                      # no inline embed above the cap
    assert f"data:application/pdf;base64,{b64}" in html   # download link still self-contained
    assert "download" in html


def test_wrapper_pptx_is_download_card_not_embed():
    pptx = b"PK\x03\x04 fake pptx"
    html = slides._wrapper_html("Deck", pptx, deck_format="pptx",
                                embed_max=8 * 1024 * 1024)
    assert "<embed" not in html                      # pptx is not browser-renderable inline
    b64 = base64.b64encode(pptx).decode("ascii")
    assert (f"data:application/vnd.openxmlformats-officedocument."
            f"presentationml.presentation;base64,{b64}") in html
    assert "download" in html
```

- [ ] **Step 2: Run to verify failure**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_factory_slides.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'samagra.factory.slides'`.

- [ ] **Step 3: Minimal implementation** — `samagra/factory/slides.py` (this task creates the
    module with ONLY the pure pieces; Task 3 extends the SAME file with `build_slides` /
    `preflight`):

```python
"""The slides lane engine (Phase F2 — the second, final Phase-F lane, and SAMAGRA's
first subprocess/external-CLI generation boundary).

One textbook chapter (seed 'textbook:<slug>') -> a NotebookLM-generated slide deck:
render the chapter to plain text -> create an EPHEMERAL notebook via the `nlm` CLI
-> add the text source -> kick off async slide generation -> SYNCHRONOUSLY poll
`nlm studio status` until the deck is ready (bounded by SAMAGRA_SLIDES_TIMEOUT) ->
download the PDF -> wrap it in a self-contained data-URI HTML (the only shape G1/G2
can publish) -> DELETE the ephemeral notebook in a `finally` -> return a
factory-compatible result dict under EXPORT_DIR/<slug>/.

NO StyleSeed (NotebookLM composes the deck from the source; there is no SAMAGRA
prompt to condition), so the DEC-8 reviewer firewall is trivially structural. NO
model review — the default posture (SAMAGRA_SLIDES_AUTOCAPTURE off) routes every
deck build to `changes` for owner eyes. NO AUDIO — the client exposes no audio verb.
"""
from __future__ import annotations

import base64
import html as _html
import os
import re

_MEDIA_TYPES = {
    "pdf": "application/pdf",
    "pptx": ("application/vnd.openxmlformats-officedocument."
             "presentationml.presentation"),
}

# Bound the source text fed to `nlm source add --text`; a chapter longer than this
# is truncated to a prefix (manifest records source_truncated=True). A safety rail,
# not a common case.
_SOURCE_MAX_CHARS = 60000

# Decks larger than this (bytes) wrap as a download-only card (no inline <embed>),
# still self-contained. Overridable via SAMAGRA_SLIDES_EMBED_MAX (default 8MB).
_DEFAULT_EMBED_MAX = 8 * 1024 * 1024

_TAG_RE = re.compile(r"<[^>]+>")


def _embed_max() -> int:
    raw = os.environ.get("SAMAGRA_SLIDES_EMBED_MAX")
    try:
        return int(raw) if raw not in (None, "") else _DEFAULT_EMBED_MAX
    except ValueError:
        return _DEFAULT_EMBED_MAX


def _strip_html(s: str) -> str:
    return _TAG_RE.sub(" ", str(s or "")).strip()


def _block_text(block: dict) -> str:
    """The plain-ish text of one block (prose/callout html stripped; equation tex
    carried; image-need briefs included as context)."""
    return _strip_html(block.get("html") or block.get("tex") or block.get("brief") or "")


def _source_text(content: dict) -> str:
    """PURE: a clean text document for the whole chapter (title + section headings +
    stripped block text). The whole-chapter generalization of figure._section_text.
    Deterministic; no LLM, no StyleSeed."""
    parts: list[str] = []
    title = str(content.get("title", "") or "")
    if title:
        parts.append(title)
    subtitle = str(content.get("subtitle", "") or "")
    if subtitle:
        parts.append(subtitle)
    for section in content.get("sections", []) or []:
        sec_title = str(section.get("title", "") or "")
        if sec_title:
            parts.append("")
            parts.append(sec_title)
        for block in section.get("blocks", []) or []:
            t = _block_text(block)
            if t:
                parts.append(t)
    return "\n".join(parts).strip()


def _source_text_bounded(content: dict) -> tuple[str, bool]:
    """The source text truncated to _SOURCE_MAX_CHARS. Returns (text, truncated)."""
    txt = _source_text(content)
    if len(txt) > _SOURCE_MAX_CHARS:
        return txt[:_SOURCE_MAX_CHARS], True
    return txt, False


# The wrapper is a SELF-CONTAINED single file: the deck is embedded as a data URI
# and there are NO external references, so the published .html renders standalone in
# the G2 reader's sandboxed iframe (CSP `sandbox allow-scripts`; a data-URI <embed>
# needs no script and no external host).
_WRAPPER_CSS = """
*{box-sizing:border-box}
body{margin:0;background:#fafafa;color:#1f2328;
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  line-height:1.6}
.wrap{max-width:960px;margin:0 auto;padding:32px 20px}
header.doc{margin-bottom:16px}
.kicker{color:#8a8f98;font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.04em}
h1{font-size:26px;margin:6px 0 2px}
.deck{width:100%;height:70vh;min-height:480px;border:1px solid #e3e3e6;border-radius:10px;background:#fff}
.dl{display:inline-block;margin-top:14px;padding:8px 14px;border:1px solid #d0d3d8;
  border-radius:8px;background:#fff;color:#1f2328;text-decoration:none;font-weight:600}
.note{color:#8a8f98;margin-top:10px;font-size:13px}
"""

_WRAPPER_DOC = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>{css}</style></head>
<body><div class="wrap">
<header class="doc"><div class="kicker">{kicker}</div><h1>{title}</h1></header>
{body}
</div></body></html>
"""


def _wrapper_html(title: str, deck_bytes: bytes, *, deck_format: str,
                  embed_max: int) -> str:
    """Self-contained wrapper: the deck embedded as a data URI (no external ref);
    the title HTML-escaped at the boundary (the C1 lesson). A PDF within embed_max
    renders inline via <embed> + a same-page download link; a PDF over embed_max, or
    any PPTX, degrades to a download-only card (still self-contained)."""
    media = _MEDIA_TYPES.get(deck_format, "application/octet-stream")
    b64 = base64.b64encode(deck_bytes).decode("ascii")
    data_uri = f"data:{media};base64,{b64}"
    esc_title = _html.escape(str(title))
    dl = (f'<a class="dl" download="{esc_title} slides.{deck_format}" '
          f'href="{data_uri}">Download the deck ({deck_format.upper()})</a>')
    inline = (deck_format == "pdf" and len(deck_bytes) <= embed_max)
    if inline:
        body = (f'<embed class="deck" type="application/pdf" src="{data_uri}">'
                f'<div>{dl}</div>')
    else:
        reason = ("deck too large to preview inline"
                  if deck_format == "pdf" else "PPTX is not previewable in-browser")
        body = (f'<div class="note">{_html.escape(reason)} — use the download link.</div>'
                f'<div>{dl}</div>')
    return _WRAPPER_DOC.format(
        title=esc_title, kicker=_html.escape("NotebookLM slide deck (Slides lane)"),
        css=_WRAPPER_CSS, body=body)
```

- [ ] **Step 4: Run again**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_factory_slides.py -q`
Expected: PASS (~10 tests green).

- [ ] **Step 5: Commit**

```bash
git add samagra/factory/slides.py tests/test_factory_slides.py
git commit -m "feat(f2): slides source-text projection + self-contained data-URI wrapper HTML

_source_text(content) projects a chapter to a clean text document (title + section
headings + stripped block text) for `nlm source add --text`, bounded to
_SOURCE_MAX_CHARS with a source_truncated flag. _wrapper_html embeds the deck PDF
as a data:application/pdf;base64 URI in a self-contained single file (<embed> +
download link; title HTML-escaped), degrading to a download-only card above
SAMAGRA_SLIDES_EMBED_MAX or for PPTX. Pure, no nlm, no network, no StyleSeed —
unit-tested against a frozen fixture + fake PDF bytes.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: `slides.py` — orchestration: create→source→generate→poll→download→wrap→delete (TDD)

**Files:**
- Modify: `samagra/factory/slides.py` (add `build_slides`, `preflight`, `_poll_until_ready`)
- Modify: `tests/test_factory_slides.py` (append `build_slides` / `preflight` / poll tests)

`build_slides(slug, *, nlm=None)`: load the chapter → create an ephemeral notebook → add the
source text → `create_slides` → **synchronously poll** `studio_status` until the slide deck
reports `completed` (or `SAMAGRA_SLIDES_TIMEOUT`) → download the PDF → wrap → write
`<slug>-slides.{html,json}` + the working `<slug>-slides/deck.pdf` → **`finally` delete the
ephemeral notebook** (delete failure logged, never masks the outcome). Any step failure or a
timeout raises the whole build (no partial capture) — build()'s `except` rolls it back
retryably. `preflight` asserts chapter-present + `notebooklm_client.configured()` (NO
StyleSeed, NO API key). The poll is bounded + injectable (a fake clock + poll-index script;
**NO real `time.sleep`** in tests).

- [ ] **Step 1: Write the failing tests** — append to `tests/test_factory_slides.py`:

```python
# --- Task 3: build_slides + preflight + poll (fake nlm client) -----------------
import json
from pathlib import Path

from samagra import config


class FakeNLM:
    """A fake NotebookLMClient scripting the whole slides lifecycle. Records the
    ordered method calls; studio_status returns pending K times then completed;
    download writes a fake PDF. Can be told to raise on a named step, or to fail on
    delete, to exercise the failure/cleanup paths. NEVER shells out."""
    def __init__(self, *, pending=1, raise_on=None, delete_raises=False,
                 status_failed=False, pdf=b"%PDF-1.4 fake"):
        self.calls = []
        self._pending = pending
        self._polls = 0
        self._raise_on = raise_on
        self._delete_raises = delete_raises
        self._status_failed = status_failed
        self._pdf = pdf

    def _maybe_raise(self, step):
        if self._raise_on == step:
            raise RuntimeError(f"nlm {step} failed")

    def create_notebook(self, title):
        self.calls.append("create_notebook")
        self._maybe_raise("create_notebook")
        return "nb_fake"

    def add_text_source(self, nb, text, *, wait_timeout):
        self.calls.append("add_text_source")
        self._maybe_raise("add_text_source")

    def create_slides(self, nb):
        self.calls.append("create_slides")
        self._maybe_raise("create_slides")

    def studio_status(self, nb):
        self.calls.append("studio_status")
        self._maybe_raise("studio_status")
        self._polls += 1
        if self._status_failed:
            return {"artifacts": [{"type": "slide_deck", "status": "failed", "id": "a1"}]}
        status = "completed" if self._polls > self._pending else "pending"
        return {"artifacts": [{"type": "slide_deck", "status": status, "id": "art_9"}]}

    def download_slide_deck(self, nb, artifact_id, out_path):
        self.calls.append("download_slide_deck")
        self._maybe_raise("download_slide_deck")
        Path(out_path).write_bytes(self._pdf)
        return out_path

    def delete_notebook(self, nb):
        self.calls.append("delete_notebook")
        if self._delete_raises:
            raise RuntimeError("nlm notebook delete failed")


@pytest.fixture()
def export(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "EXPORT_DIR", tmp_path / "lectures")
    # zero the poll interval so the bounded loop spins instantly (no real wait).
    monkeypatch.setenv("SAMAGRA_SLIDES_POLL_INTERVAL", "0")
    return tmp_path


@pytest.fixture()
def fake_chapter(monkeypatch):
    from samagra.lectures import render
    monkeypatch.setattr(render, "load_chapter", lambda slug: _CHAPTER)


def test_build_slides_happy_path_writes_wrapper_json_and_deck(export, fake_chapter, monkeypatch):
    monkeypatch.setattr(slides, "_sleep", lambda s: None)     # no real wait in tests
    nlm = FakeNLM(pending=2)
    res = slides.build_slides("circular-motion", nlm=nlm)
    assert res["variant"] == "slides"
    assert res["items"] == 1 and res["errors"] == 0
    # the synthetic owner-review verdict (D2) so _assert_review_clean passes.
    assert res["verdicts"] and res["verdicts"][0]["verdict"] == "changes"
    # ordered lifecycle: create -> source -> slides -> poll(>=1) -> download -> delete.
    assert nlm.calls[0] == "create_notebook"
    assert nlm.calls[1] == "add_text_source"
    assert nlm.calls[2] == "create_slides"
    assert "download_slide_deck" in nlm.calls
    assert nlm.calls[-1] == "delete_notebook"        # cleanup last
    # artifacts on disk.
    out = config.EXPORT_DIR / "circular-motion"
    assert (out / "circular-motion-slides.html").is_file()
    assert (out / "circular-motion-slides.json").is_file()
    assert (out / "circular-motion-slides" / "deck.pdf").stat().st_size > 0
    assert Path(res["html"]).is_file() and Path(res["json"]).is_file()
    data = json.loads(Path(res["json"]).read_text(encoding="utf-8"))
    assert data["deck_format"] == "pdf"
    assert data["deck_bytes"] > 0 and data["artifact_id"] == "art_9"


def test_wrapper_html_is_self_contained_data_uri(export, fake_chapter, monkeypatch):
    monkeypatch.setattr(slides, "_sleep", lambda s: None)
    res = slides.build_slides("circular-motion", nlm=FakeNLM(pending=0))
    html = Path(res["html"]).read_text(encoding="utf-8")
    assert "data:application/pdf;base64," in html
    assert "http://" not in html and "https://" not in html


def test_build_slides_deletes_notebook_in_finally_on_failure(export, fake_chapter, monkeypatch):
    # A download failure AFTER the notebook is created STILL deletes it.
    monkeypatch.setattr(slides, "_sleep", lambda s: None)
    nlm = FakeNLM(pending=0, raise_on="download_slide_deck")
    with pytest.raises(RuntimeError):
        slides.build_slides("circular-motion", nlm=nlm)
    assert "delete_notebook" in nlm.calls             # cleanup ran despite the raise


def test_delete_failure_does_not_mask_success(export, fake_chapter, monkeypatch):
    # The deck downloaded fine; the delete fails -> the SUCCESS is still returned.
    monkeypatch.setattr(slides, "_sleep", lambda s: None)
    nlm = FakeNLM(pending=0, delete_raises=True)
    res = slides.build_slides("circular-motion", nlm=nlm)   # no raise
    assert res["variant"] == "slides" and res["items"] == 1


def test_delete_failure_does_not_convert_failure_to_success(export, fake_chapter, monkeypatch):
    # The download fails AND the delete fails -> the PRIMARY (download) raise wins.
    monkeypatch.setattr(slides, "_sleep", lambda s: None)
    nlm = FakeNLM(pending=0, raise_on="download_slide_deck", delete_raises=True)
    with pytest.raises(RuntimeError) as e:
        slides.build_slides("circular-motion", nlm=nlm)
    assert "download slide-deck" in str(e.value) or "download_slide_deck" in str(e.value)


def test_poll_explicit_failed_status_raises(export, fake_chapter, monkeypatch):
    monkeypatch.setattr(slides, "_sleep", lambda s: None)
    nlm = FakeNLM(status_failed=True)
    with pytest.raises(RuntimeError):
        slides.build_slides("circular-motion", nlm=nlm)
    assert "delete_notebook" in nlm.calls             # still cleans up


def test_poll_timeout_raises_timeouterror(export, fake_chapter, monkeypatch):
    # Never completes within the timeout -> TimeoutError; cleanup still runs.
    monkeypatch.setenv("SAMAGRA_SLIDES_TIMEOUT", "0")     # immediate timeout
    monkeypatch.setattr(slides, "_sleep", lambda s: None)
    nlm = FakeNLM(pending=9999)
    with pytest.raises(TimeoutError):
        slides.build_slides("circular-motion", nlm=nlm)
    assert "delete_notebook" in nlm.calls


def test_source_truncation_flag_recorded(export, monkeypatch):
    monkeypatch.setattr(slides, "_sleep", lambda s: None)
    monkeypatch.setattr(slides, "_SOURCE_MAX_CHARS", 20)
    from samagra.lectures import render
    big = {"title": "Big Chapter Title Here", "sections": [
        {"title": "S", "blocks": [{"type": "prose", "html": "y" * 500}]}]}
    monkeypatch.setattr(render, "load_chapter", lambda slug: big)
    res = slides.build_slides("big", nlm=FakeNLM(pending=0))
    data = json.loads(Path(res["json"]).read_text(encoding="utf-8"))
    assert data["source_truncated"] is True


def test_preflight_ok(export, fake_chapter, monkeypatch):
    monkeypatch.setattr(slides.notebooklm_client, "configured", lambda: True)
    slides.preflight("circular-motion")               # no raise


def test_preflight_missing_chapter_raises(export, monkeypatch):
    from samagra.lectures import render
    def boom(slug):
        raise FileNotFoundError(slug)
    monkeypatch.setattr(render, "load_chapter", boom)
    monkeypatch.setattr(slides.notebooklm_client, "configured", lambda: True)
    with pytest.raises(FileNotFoundError):
        slides.preflight("nope")


def test_preflight_unconfigured_raises(export, fake_chapter, monkeypatch):
    monkeypatch.setattr(slides.notebooklm_client, "configured", lambda: False)
    with pytest.raises(RuntimeError):
        slides.preflight("circular-motion")


def test_preflight_requires_no_styleseed(export, fake_chapter, monkeypatch, tmp_path):
    # Unlike samadhan, the slides preflight does NOT require a committed StyleSeed.
    monkeypatch.setattr(config, "STYLESEED_DIR", tmp_path / "no-styleseed-here")
    monkeypatch.setattr(slides.notebooklm_client, "configured", lambda: True)
    slides.preflight("circular-motion")               # no raise despite absent StyleSeed
```

- [ ] **Step 2: Run to verify failure**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_factory_slides.py -q`
Expected: FAIL — `AttributeError: module 'samagra.factory.slides' has no attribute
'build_slides'` (and `preflight` / `notebooklm_client` / `_sleep`).

- [ ] **Step 3: Extend `samagra/factory/slides.py`** — prepend the new imports and append the
    orchestration, poll, and preflight:

```python
import json
import time
import uuid

from .. import config
from ..clients import notebooklm_client
from ..lectures import render


_POLL_TERMINAL_OK = "completed"
_POLL_TERMINAL_BAD = ("failed", "error")


def _timeout() -> int:
    raw = os.environ.get("SAMAGRA_SLIDES_TIMEOUT")
    try:
        return int(raw) if raw not in (None, "") else 900
    except ValueError:
        return 900


def _poll_interval() -> float:
    raw = os.environ.get("SAMAGRA_SLIDES_POLL_INTERVAL")
    try:
        return float(raw) if raw not in (None, "") else 15.0
    except ValueError:
        return 15.0


def _sleep(seconds: float) -> None:
    """Indirection so tests can no-op the poll wait (monkeypatched). Never called
    with a real interval in the standing gate."""
    time.sleep(seconds)


def preflight(slug: str) -> None:
    """Anti-wedge pre-check (called by build() BEFORE recording intent): the chapter
    exists and `nlm` is present + authed. NO StyleSeed requirement (NotebookLM
    composes the deck from the source; there is no SAMAGRA prompt to condition), NO
    API key (nlm owns the Google creds). Raises FileNotFoundError / RuntimeError
    without writing anything."""
    render.load_chapter(slug)                           # FileNotFoundError if absent
    if not notebooklm_client.configured():
        raise RuntimeError(
            "nlm is not present or not authenticated (run `nlm login`) — refusing a "
            "slides build without an authed NotebookLM CLI")


def _slide_deck_artifact(status: dict) -> dict | None:
    """The slide-deck artifact record from a `studio status --json` payload, or None
    if not present yet. Tolerant of the artifact-list shape."""
    arts = status.get("artifacts") if isinstance(status, dict) else None
    for a in arts or []:
        t = str(a.get("type", "")).lower()
        if "slide" in t or "deck" in t:
            return a
    return None


def _poll_until_ready(nlm, nb: str) -> str:
    """SYNCHRONOUS S1 poll: studio_status until the slide deck is `completed` (return
    its artifact id), an explicit `failed`/`error` (RuntimeError), or the total
    SAMAGRA_SLIDES_TIMEOUT elapses (TimeoutError). Bounded on both the per-call
    subprocess timeout (in the client) and this total timeout. The interval sleep
    goes through _sleep so tests never wait for real."""
    deadline = time.monotonic() + _timeout()
    interval = _poll_interval()
    while True:
        art = _slide_deck_artifact(nlm.studio_status(nb))
        st = str((art or {}).get("status", "")).lower()
        if st == _POLL_TERMINAL_OK:
            aid = (art or {}).get("id")
            if not aid:
                raise RuntimeError("slide deck completed but carried no artifact id")
            return str(aid)
        if st in _POLL_TERMINAL_BAD:
            raise RuntimeError("NotebookLM slide generation reported a failed status")
        if time.monotonic() >= deadline:
            raise TimeoutError(
                f"slide generation did not complete within {_timeout()}s")
        _sleep(interval)


def build_slides(slug, *, nlm=None) -> dict:
    """Create an ephemeral NotebookLM notebook, generate + download a slide deck,
    wrap it into a self-contained data-URI HTML, and write the artifacts. The
    ephemeral notebook is deleted in a `finally` (a delete failure is logged and
    does NOT mask the primary outcome, nor convert a success into a rollback). Any
    step failure or a timeout raises the whole build (no partial RESULT) — build()
    rolls it back retryably. Clears the stale working dir before writing."""
    content = render.load_chapter(slug)                 # ground truth (raises if absent)
    client = nlm or notebooklm_client.NotebookLMClient()
    source_text, truncated = _source_text_bounded(content)

    out = config.EXPORT_DIR / slug
    out.mkdir(parents=True, exist_ok=True)
    workdir = out / f"{slug}-slides"
    for stale in workdir.glob("deck.*"):                # clear stale before writing (retry-safe)
        stale.unlink()
    workdir.mkdir(parents=True, exist_ok=True)

    title = str(content.get("title", slug) or slug)
    nb = None
    try:
        nb = client.create_notebook(f"SAMAGRA slides: {slug} {uuid.uuid4().hex[:8]}")
        client.add_text_source(nb, source_text, wait_timeout=_timeout())
        client.create_slides(nb)
        artifact_id = _poll_until_ready(client, nb)
        dl_format = getattr(client, "_dl_format", "pdf")
        deck_path = workdir / f"deck.{dl_format}"
        client.download_slide_deck(nb, artifact_id, deck_path)
        deck_bytes = deck_path.read_bytes()
        if not deck_bytes:
            raise RuntimeError("downloaded slide deck is empty")
    finally:
        if nb is not None:
            try:
                client.delete_notebook(nb)
            except Exception:  # noqa: BLE001 - a delete failure must NEVER mask the
                # primary outcome nor convert a success to a rollback. The ephemeral
                # notebook (titled `SAMAGRA slides:`) is harmless owner-pruneable
                # state. Deliberately swallowed; a concise log names the orphan id
                # WITHOUT echoing any nlm stderr / notebook content.
                import logging
                logging.getLogger(__name__).warning(
                    "slides: failed to delete ephemeral notebook %s (owner-pruneable)", nb)

    # The synthetic owner-review verdict (D2 §3.4): items=1, errors=0, and a single
    # `changes` verdict so _assert_review_clean passes structurally, while the
    # conservative default clause routes to `changes` regardless.
    verdicts = [{"idx": 0, "verdict": "changes",
                 "rationale": "NotebookLM deck — owner review required"}]
    deck_b64 = base64.b64encode(deck_bytes).decode("ascii")
    embed_max = _embed_max()

    json_path = out / f"{slug}-slides.json"
    json_path.write_text(json.dumps({
        "slug": slug, "title": title, "deck_format": dl_format,
        "artifact_id": artifact_id, "deck_bytes": len(deck_bytes),
        "deck_b64": deck_b64, "source_truncated": truncated,
        "items": 1, "errors": 0, "verdicts": verdicts,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    html_path = out / f"{slug}-slides.html"
    html_path.write_text(
        _wrapper_html(title, deck_bytes, deck_format=dl_format, embed_max=embed_max),
        encoding="utf-8")

    return {"variant": "slides", "html": str(html_path), "json": str(json_path),
            "deck": str(deck_path), "deck_format": dl_format,
            "artifact_id": artifact_id, "source_truncated": truncated,
            "items": 1, "errors": 0, "verdicts": verdicts}
```

> **Implementer note — the poll never waits for real in tests.** Three seams make the poll
> bounded + injectable with NO `time.sleep`: `_sleep` (monkeypatched to a no-op), the
> `SAMAGRA_SLIDES_POLL_INTERVAL=0` env in the `export` fixture, and `SAMAGRA_SLIDES_TIMEOUT=0`
> for the timeout test. The `FakeNLM.studio_status` returns `pending` K times then
> `completed`, so the happy-path loop terminates by state, not by clock. Do NOT add a real
> sleep anywhere in `build_slides`; route every wait through `_sleep`.

> **Implementer note — the synthetic verdict is load-bearing.** `_assert_review_clean`
> (unchanged) requires an integer `errors`/`items` and — since `items>0` — a NON-EMPTY
> `verdicts` list. A deck has no per-item model review (D2), so `build_slides` records
> `items=1, errors=0` and ONE synthetic `changes` verdict. This passes the shared guard with
> zero change to it, and the §3.6.3 autocapture-off clause (Task 4) routes the build to
> `changes` regardless. Keep `items=1` and `errors=0` exactly — do NOT set `items=0` (that
> would trip the empty-brief changes path for a different reason and confuse the golden).

- [ ] **Step 4: Run new + adjacent tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_factory_slides.py tests/test_factory_samadhan.py tests/test_factory_figure.py -q`
Expected: ALL PASS (slides build/preflight/poll green + the standing samadhan/figure engine
tests unchanged — `slides.py` is a new module, additive).

- [ ] **Step 5: Commit**

```bash
git add samagra/factory/slides.py tests/test_factory_slides.py
git commit -m "feat(f2): slides orchestration — create/source/generate/poll/download/wrap/delete

build_slides(slug, *, nlm=) creates an ephemeral NotebookLM notebook, adds the
chapter text as a source, kicks off slide generation, SYNCHRONOUSLY polls
studio_status until the deck is completed (bounded by SAMAGRA_SLIDES_TIMEOUT;
explicit failed -> RuntimeError; total-timeout -> TimeoutError), downloads the PDF,
wraps it in the self-contained data-URI HTML, and writes <slug>-slides.{html,json}
+ the working <slug>-slides/deck.pdf. The ephemeral notebook is deleted in a
`finally` — a delete failure is logged (orphan id, no stderr/content echoed) and
NEVER masks the outcome nor converts a success to a rollback. Any step failure or a
timeout raises the whole build (no partial RESULT) for build()'s retryable
rollback. The poll wait is routed through _sleep so tests never wait for real.
preflight requires chapter + nlm configured, NO StyleSeed, NO API key. Records the
synthetic owner-review verdict so _assert_review_clean passes unchanged.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: Wiring — Line, dispatch route + validate_product, lane-dispatched preflight, capture gate (TDD)

**Files:**
- Modify: `samagra/factory/lines.py` (register the `slides` Line + extend `_ORDER`)
- Modify: `samagra/factory/dispatch.py` (`run_line` route + `validate_product` slides branch)
- Modify: `samagra/factory/run.py` (lane-dispatched preflight + the autocapture `needs_review` clause)
- Modify: `tests/test_factory_lines.py` (add `"slides"` to the two expected-key sets — the one forced addition)
- Create: `tests/test_factory_slides_wiring.py`

The slides lane is `kind="llm"`, so it rides the existing five build() guards + retryable
rollback verbatim. Touch points, all mirroring F1's figure wiring: (1) a `slides` Line; (2)
`run_line` special-cases `slides` ahead of the generic samadhan branch (both `kind=="llm"`,
disambiguated by KEY — exactly as `deck` and `figure` are); (3) `validate_product` asserts the
wrapper html exists + the working deck file exists for the slides variant; (4) build()'s
`kind=="llm"` preflight is already lane-dispatched (F1 made it a dispatch on `line`) — F2 adds
a `slides → slides.preflight` arm; (5) build()'s `needs_review` gains one clause — a `slides`
build with `SAMAGRA_SLIDES_AUTOCAPTURE` off routes to `changes`.

- [ ] **Step 1: Write the failing tests** — `tests/test_factory_slides_wiring.py`:

```python
"""Phase F2 wiring: the slides Line, run_line routing, validate_product slides
branch, the lane-dispatched build() preflight, and the SAMAGRA_SLIDES_AUTOCAPTURE
capture gate. Offline: a fake nlm client, isolated governance.db."""
from __future__ import annotations

from pathlib import Path

import pytest

from samagra import config
from samagra.factory import dispatch, run, slides
from samagra.factory.lines import LINES, classify
from samagra.governance import store


# ---------- lane registration ----------

def test_slides_line_registered_llm_optin_textbook():
    spec = LINES["slides"]
    assert spec.kind == "llm"
    assert spec.auto_fan is False                    # opt-in (F-D4 analogue)
    assert spec.source_prefixes == ("textbook:",)


def test_classify_textbook_excludes_slides():
    # slides is opt-in: NOT in the default textbook fan-out (like samadhan/figure).
    assert "slides" not in classify("textbook:circular-motion")
    # regression pin: the default fan-out is UNCHANGED.
    assert classify("textbook:circular-motion") == [
        "revision", "lecture", "deck", "paper", "drill"]


def test_plan_lane_slides_proposes_only_that_lane():
    props = run.plan("textbook:circular-motion", dry=True, lane="slides")
    assert [p["line"] for p in props] == ["slides"]


# ---------- run_line routing ----------

class _FakeNLM:
    def __init__(self):
        self.calls = []
    def create_notebook(self, title):
        self.calls.append("create"); return "nb_1"
    def add_text_source(self, nb, text, *, wait_timeout):
        self.calls.append("source")
    def create_slides(self, nb):
        self.calls.append("slides")
    def studio_status(self, nb):
        return {"artifacts": [{"type": "slide_deck", "status": "completed", "id": "a1"}]}
    def download_slide_deck(self, nb, artifact_id, out_path):
        Path(out_path).write_bytes(b"%PDF-1.4 fake"); return out_path
    def delete_notebook(self, nb):
        self.calls.append("delete")
    _dl_format = "pdf"


def test_run_line_routes_slides_to_build_slides(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "EXPORT_DIR", tmp_path / "lectures")
    monkeypatch.setattr(slides, "_sleep", lambda s: None)
    from samagra.lectures import render
    monkeypatch.setattr(render, "load_chapter", lambda slug: {
        "title": "T", "sections": [{"title": "S", "blocks": [
            {"type": "prose", "html": "<p>x</p>"}]}]})
    called = {}
    real = slides.build_slides
    def spy(slug, **kw):
        called["slug"] = slug
        return real(slug, nlm=_FakeNLM())
    monkeypatch.setattr(slides, "build_slides", spy)
    res = dispatch.run_line("slides", "circular-motion")
    assert called["slug"] == "circular-motion"
    assert res["variant"] == "slides"


# ---------- validate_product slides branch ----------

def test_validate_product_requires_the_deck_file(tmp_path):
    # A wrapper html present but the working deck file MISSING -> ValueError.
    html = tmp_path / "x-slides.html"
    html.write_text("<html>wrapper</html>", encoding="utf-8")
    result = {"variant": "slides", "html": str(html), "json": None,
              "deck": str(tmp_path / "x-slides" / "deck.pdf"),
              "items": 1, "errors": 0, "verdicts": [{"idx": 0, "verdict": "changes"}]}
    with pytest.raises(ValueError):
        dispatch.validate_product("slides", result)


def test_validate_product_passes_with_deck(tmp_path):
    workdir = tmp_path / "x-slides"
    workdir.mkdir()
    (workdir / "deck.pdf").write_bytes(b"%PDF-1.4 fake")
    html = tmp_path / "x-slides.html"
    html.write_text("<html>wrapper</html>", encoding="utf-8")
    result = {"variant": "slides", "html": str(html), "json": None,
              "deck": str(workdir / "deck.pdf"),
              "items": 1, "errors": 0, "verdicts": [{"idx": 0, "verdict": "changes"}]}
    dispatch.validate_product("slides", result)      # no raise


# ---------- build() capture gate + preflight + retryable ----------

@pytest.fixture()
def envfx(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "GOVERNANCE_DB", tmp_path / "governance.db")
    monkeypatch.setattr(config, "DATA_DB", tmp_path / "samagra.db")
    monkeypatch.setattr(config, "EXPORT_DIR", tmp_path / "lectures")
    monkeypatch.setattr(slides, "_sleep", lambda s: None)
    store._INITIALIZED.clear()
    store.ensure_tables()
    monkeypatch.chdir(tmp_path)
    from samagra.lectures import render
    monkeypatch.setattr(render, "load_chapter", lambda slug: {
        "title": "Circular Motion", "sections": [{"title": "S", "blocks": [
            {"type": "prose", "html": "<p>the chapter</p>"}]}]})
    monkeypatch.setattr(slides.notebooklm_client, "configured", lambda: True)
    yield tmp_path
    store._INITIALIZED.clear()


def _fake_build_slides_ok(monkeypatch):
    def fake(slug, **kw):
        return slides.build_slides(slug, nlm=_FakeNLM())
    monkeypatch.setattr(slides, "build_slides", fake)


def _approve_and_build(seed_ref):
    props = run.plan(seed_ref, dry=False, lane="slides")
    run.approve_seed(seed_ref)
    return run.build(props[0]["assignment_id"])


def test_autocapture_off_default_routes_to_changes(envfx, monkeypatch):
    monkeypatch.delenv("SAMAGRA_SLIDES_AUTOCAPTURE", raising=False)
    _fake_build_slides_ok(monkeypatch)
    res = _approve_and_build("textbook:circular-motion")
    assert res["status"] == "changes"                # conservative default
    c = store.connect()
    try:
        verbs = [e["verb"] for e in store.list_events_for_assignment(c, res["assignment_id"])]
    finally:
        c.close()
    assert "product_created" in verbs                # the artifact WAS produced + recorded


def test_autocapture_on_clean_build_is_captured(envfx, monkeypatch):
    monkeypatch.setenv("SAMAGRA_SLIDES_AUTOCAPTURE", "1")
    _fake_build_slides_ok(monkeypatch)
    res = _approve_and_build("textbook:circular-motion")
    assert res["status"] == "captured"


def test_slides_preflight_refuses_before_intent_no_wedge(envfx, monkeypatch):
    monkeypatch.setattr(slides.notebooklm_client, "configured", lambda: False)
    props = run.plan("textbook:circular-motion", dry=False, lane="slides")
    run.approve_seed("textbook:circular-motion")
    aid = props[0]["assignment_id"]
    with pytest.raises(RuntimeError):
        run.build(aid)
    c = store.connect()
    try:
        verbs = [e["verb"] for e in store.list_events_for_assignment(c, aid)]
        a = [x for x in store.list_assignments(c) if x["id"] == aid][0]
    finally:
        c.close()
    assert "product_building" not in verbs and a["status"] == "approved"   # not wedged


def test_slides_failure_rolls_back_and_is_retryable(envfx, monkeypatch):
    monkeypatch.setenv("SAMAGRA_SLIDES_AUTOCAPTURE", "1")
    class _BoomNLM(_FakeNLM):
        def create_slides(self, nb):
            raise RuntimeError("nlm slides create failed")
    def boom(slug, **kw):
        return slides.build_slides(slug, nlm=_BoomNLM())
    monkeypatch.setattr(slides, "build_slides", boom)
    props = run.plan("textbook:circular-motion", dry=False, lane="slides")
    run.approve_seed("textbook:circular-motion")
    aid = props[0]["assignment_id"]
    with pytest.raises(RuntimeError):
        run.build(aid)
    c = store.connect()
    try:
        a = [x for x in store.list_assignments(c) if x["id"] == aid][0]
        verbs = [e["verb"] for e in store.list_events_for_assignment(c, aid)]
    finally:
        c.close()
    assert a["status"] == "approved"                 # not wedged (local-write lane rollback)
    assert "product_build_failed" in verbs and "product_created" not in verbs
    # retry with a working client -> succeeds and captures.
    _fake_build_slides_ok(monkeypatch)
    assert run.build(aid)["status"] == "captured"


def test_samadhan_and_figure_preflight_unchanged(envfx, monkeypatch):
    # Regression pin: the samadhan + figure lanes still route to THEIR own preflight,
    # not slides.preflight (the lane-dispatch must not break the D2/F1 lanes).
    from samagra.factory import samadhan, figure
    calls = {"samadhan": 0}
    def spy_preflight(slug):
        calls["samadhan"] += 1
        return None                                  # skip StyleSeed/key checks for the pin
    monkeypatch.setattr(samadhan, "preflight", spy_preflight)
    (config.EXPORT_DIR).mkdir(parents=True, exist_ok=True)
    (config.EXPORT_DIR / "s.html").write_text("<h1>s</h1>", encoding="utf-8")
    monkeypatch.setattr(
        samadhan, "build_samadhan",
        lambda slug: {"variant": "samadhan",
                      "html": str(config.EXPORT_DIR / "s.html"),
                      "json": None, "items": 1, "errors": 0,
                      "verdicts": [{"idx": 0, "verdict": "ok"}]})
    props = run.plan("textbook:circular-motion", dry=False, lane="samadhan")
    run.approve_seed("textbook:circular-motion")
    run.build(props[0]["assignment_id"])
    assert calls["samadhan"] == 1                     # samadhan.preflight WAS called
    # figure.preflight is a distinct callable and is untouched by the slides arm.
    assert figure.preflight is not slides.preflight
```

- [ ] **Step 2: Run to verify failure**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_factory_slides_wiring.py -q`
Expected: FAIL — `KeyError: 'slides'` in `LINES` / `run_line` returns a samadhan result /
`validate_product` doesn't assert the deck / build() calls `samadhan.preflight` for the slides
lane.

- [ ] **Step 3a: Register the `slides` Line in `samagra/factory/lines.py`** — add to `LINES`
    after `figure`, and extend `_ORDER`:

```python
    "slides": Line("slides", "Slide deck (NotebookLM-generated)",
                   None, ("textbook:",), "llm", auto_fan=False),
```

and extend `_ORDER`:

```python
_ORDER = ["revision", "lecture", "deck", "paper", "drill", "seed", "samadhan", "figure", "slides"]
```

- [ ] **Step 3b: Route `slides` in `samagra/factory/dispatch.py`** — import `slides`, add the
    `run_line` special-case AHEAD of the generic `kind=="llm"` branch, and add the
    `validate_product` slides branch. Change the import line:

```python
from . import deck, figure, paper, samadhan, slides
```

In `run_line`, add AFTER the `figure` special-case and BEFORE `if spec.kind == "qx":`:

```python
    if line == "slides":
        return slides.build_slides(slug)
```

At the end of `validate_product`, after `_assert_figures_present(line, result)`, add:

```python
    _assert_slides_present(line, result)
```

and add the new helper at module end:

```python
def _assert_slides_present(line: str, result: dict) -> None:
    """For the slides lane ONLY: the wrapper html check (above) is not enough — a
    build that produced a wrapper but no working deck file must be refused, not
    captured. Assert the downloaded deck file exists and is non-empty."""
    if result.get("variant") != "slides":
        return
    deck = result.get("deck")
    if not (deck and Path(deck).is_file() and Path(deck).stat().st_size > 0):
        raise ValueError(
            f"line {line!r} produced no non-empty deck file — refusing to capture "
            f"a slides wrapper with no deck")
```

> **Implementer note:** the slides variant always has `items==1` (a deck is one artifact), so
> — unlike figure — there is no legitimate empty build to early-return for. The wrapper html
> is checked by the generic `validate_product` head (exists + non-empty); this helper adds the
> deck-file check. `result["deck"]` is the absolute path `build_slides` returns.

- [ ] **Step 3c: Lane-dispatch the preflight + add the autocapture clause in
    `samagra/factory/run.py`** — import `slides`, add the `slides → slides.preflight` arm, and
    extend `needs_review`.

Change the import line:

```python
from . import dispatch, figure, samadhan, slides
```

Extend the lane-dispatched preflight (the `elif spec.kind == "llm":` block) — add a `slides`
arm alongside `figure`, keeping the `samadhan` else-path byte-identical:

```python
        elif spec.kind == "llm":
            # anti-wedge: preflight BEFORE recording build intent (a missing key /
            # absent chapter / unauthed nlm refuses without wedging the in-flight
            # state). Every llm lane is kind=="llm"; the lane KEY disambiguates which
            # preflight runs (figure/slides require no StyleSeed; samadhan unchanged).
            _slug = seed_ref.split(":", 1)[-1]
            if line == "figure":
                figure.preflight(_slug)
            elif line == "slides":
                slides.preflight(_slug)
            else:
                samadhan.preflight(_slug)
```

Extend `needs_review` — add the slides autocapture clause after the figure one:

```python
        needs_review = spec.kind == "llm" and (
            result.get("errors", 0) > 0 or result.get("items", 0) == 0)
        if line == "figure" and not config._env_bool("SAMAGRA_FIGURE_AUTOCAPTURE", False):
            needs_review = True
        if line == "slides" and not config._env_bool("SAMAGRA_SLIDES_AUTOCAPTURE", False):
            needs_review = True
```

> **Implementer note:** `config._env_bool` reads the env at call time, so the tests'
> `monkeypatch.setenv/delenv("SAMAGRA_SLIDES_AUTOCAPTURE", ...)` take effect per-build with no
> import-time capture. Read it live here — do NOT read a module-level constant. The clause
> only affects the terminal status, never the ledger (the synthetic `changes` verdict + real
> `items`/`errors` stay truthful in the artifact).

- [ ] **Step 3d: Add `"slides"` to the two expected-key sets in `tests/test_factory_lines.py`**
    — the ONE forced standing-test edit (the wiring makes it mandatory). In
    `test_registry_has_expected_output_labels`, extend BOTH the label-loop tuple and the
    `set(lines.LINES)` set:

```python
def test_registry_has_expected_output_labels():
    for key in ("revision", "lecture", "deck", "paper", "drill", "seed", "samadhan",
                "figure", "slides"):
        assert lines.LINES[key].expected_output
    assert set(lines.LINES) == {
        "revision", "lecture", "deck", "paper", "drill", "seed", "samadhan",
        "figure", "slides"}
```

> **Implementer note:** this is one of the exactly-two forced standing-test additions the
> wiring requires (the other is `tests/test_publish_run.py`'s PUBLISHABLE set, Task 5). No
> other standing test changes — only pure env-isolation monkeypatch additions elsewhere if a
> test's environment leaks `SAMAGRA_SLIDES_*`.

- [ ] **Step 4: Run new + standing wiring/build tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_factory_slides_wiring.py tests/test_factory_lines.py tests/test_factory_dispatch.py tests/test_factory_run.py tests/test_factory_figure_wiring.py tests/test_factory_samadhan_wiring.py tests/test_cli_factory_lane.py -q`
Expected: ALL PASS (slides wiring green + every standing lane/run/figure/samadhan test
unchanged — the samadhan + figure preflight regression pin proves D2/F1 are intact).

- [ ] **Step 5: Commit**

```bash
git add samagra/factory/lines.py samagra/factory/dispatch.py samagra/factory/run.py tests/test_factory_slides_wiring.py tests/test_factory_lines.py
git commit -m "feat(f2): wire the slides lane — Line, run_line route, validate_product, capture gate

slides Line (kind=llm, auto_fan=False, textbook: prefix). run_line special-cases
slides ahead of the generic samadhan branch (KEY disambiguates, like deck/figure).
validate_product asserts a non-empty deck file for the slides variant. build()'s
kind==llm preflight gains a slides arm (figure/samadhan UNCHANGED, regression-pinned)
and needs_review gains one clause: a slides build routes to changes whenever
SAMAGRA_SLIDES_AUTOCAPTURE is off (default), read live. test_factory_lines gains
'slides' in the two expected-key sets (the forced addition). Rides the existing 5
guards + retryable rollback verbatim — no new status, no migration.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: Docs + no-migration golden + publish-compat golden + opt-in live smoke (TDD)

**Files:**
- Modify: `.env.example` (NotebookLM slides block)
- Modify: `requirements.txt` (comment only — nlm is an external CLI, NOT a pip dep)
- Modify: `tests/test_publish_run.py` (add `"slides"` to the PUBLISHABLE set — the 2nd forced addition)
- Create: `tests/test_slides_golden.py` (no-migration + publish-compat golden thread)
- Create: `tests/test_slides_live_smoke.py` (opt-in live smoke, gated on `SAMAGRA_LIVE_SLIDES_SMOKE`)

- [ ] **Step 1: Add `"slides"` to the PUBLISHABLE set in `tests/test_publish_run.py`** — the
    2nd forced standing-test edit (`kind="llm"` ≠ mcd, so slides IS publishable). In
    `test_publishable_excludes_the_mcd_seed_lane`:

```python
def test_publishable_excludes_the_mcd_seed_lane():
    assert "seed" not in run.PUBLISHABLE
    assert {"revision", "lecture", "deck", "paper", "drill", "samadhan",
            "figure", "slides"} == run.PUBLISHABLE
```

- [ ] **Step 2: Write the failing golden thread** — `tests/test_slides_golden.py`:

```python
"""Phase F2 golden threads: the plan->approve->build->(changes/capture) loop, the
no-migration invariant, and the publish-compatibility of the wrapper html (the deck
embedded as a data URI reaches /learn via the G1/G2 pipeline with ZERO code change).
Offline: a fake nlm client, isolated stores. Mirrors tests/test_figure_golden.py's
governance-schema discipline."""
from __future__ import annotations

from pathlib import Path

import pytest

from samagra import config
from samagra.factory import run, slides
from samagra.factory.publish import read as pub_read, run as pub_run
from samagra.governance import store


class _FakeNLM:
    def create_notebook(self, title):
        return "nb_g"
    def add_text_source(self, nb, text, *, wait_timeout):
        pass
    def create_slides(self, nb):
        pass
    def studio_status(self, nb):
        return {"artifacts": [{"type": "slide_deck", "status": "completed", "id": "a1"}]}
    def download_slide_deck(self, nb, artifact_id, out_path):
        Path(out_path).write_bytes(b"%PDF-1.4 golden-deck-bytes %%EOF")
        return out_path
    def delete_notebook(self, nb):
        pass
    _dl_format = "pdf"


# Capture the genuine engine once at import time, before any monkeypatch, so the
# fixture's replacement can still reach the real build_slides with the fake injected.
_REAL_BUILD_SLIDES = slides.build_slides


def _real_build(slug):
    return _REAL_BUILD_SLIDES(slug, nlm=_FakeNLM())


@pytest.fixture()
def envfx(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "GOVERNANCE_DB", tmp_path / "governance.db")
    monkeypatch.setattr(config, "DATA_DB", tmp_path / "samagra.db")
    monkeypatch.setattr(config, "EXPORT_DIR", tmp_path / "lectures")
    monkeypatch.setattr(config, "PUBLISHED_DIR", tmp_path / "published")
    monkeypatch.setattr(slides, "_sleep", lambda s: None)
    store._INITIALIZED.clear()
    store.ensure_tables()
    monkeypatch.chdir(tmp_path)
    from samagra.lectures import render
    monkeypatch.setattr(render, "load_chapter", lambda slug: {
        "title": "Circular Motion", "sections": [{"title": "S", "blocks": [
            {"type": "prose", "html": "<p>the chapter</p>"}]}]})
    monkeypatch.setattr(slides.notebooklm_client, "configured", lambda: True)
    # build() calls dispatch.run_line("slides", slug) -> slides.build_slides(slug)
    # with NO injected client, so replace build_slides with a version that injects
    # the offline fake (the real production path, just with the fake swapped in).
    monkeypatch.setattr(slides, "build_slides", lambda slug, **kw: _real_build(slug))
    yield tmp_path
    store._INITIALIZED.clear()


def test_golden_default_routes_to_changes_governance_schema_stable(envfx, monkeypatch):
    monkeypatch.delenv("SAMAGRA_SLIDES_AUTOCAPTURE", raising=False)
    # schema version BEFORE (no migration expected across the whole loop).
    ver_before = store.connect().execute("PRAGMA user_version").fetchone()[0]
    props = run.plan("textbook:circular-motion", dry=False, lane="slides")
    run.approve_seed("textbook:circular-motion")
    res = run.build(props[0]["assignment_id"])
    assert res["status"] == "changes"                 # conservative default
    ver_after = store.connect().execute("PRAGMA user_version").fetchone()[0]
    assert ver_after == ver_before                    # NO migration / schema bump


def test_golden_no_new_governance_table(envfx, monkeypatch):
    monkeypatch.delenv("SAMAGRA_SLIDES_AUTOCAPTURE", raising=False)
    c = store.connect()
    try:
        before = {r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    finally:
        c.close()
    props = run.plan("textbook:circular-motion", dry=False, lane="slides")
    run.approve_seed("textbook:circular-motion")
    run.build(props[0]["assignment_id"])
    c = store.connect()
    try:
        after = {r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    finally:
        c.close()
    assert after == before                            # slides adds NO governance table


def test_golden_publish_compat_on_wrapper_html(envfx, monkeypatch):
    # With autocapture ON the build captures; publish --lanes slides copies the
    # wrapper html + json; the G2 read surface serves it sha-verified with the PDF
    # data-URI embedded. (The `envfx` fixture already routes build_slides through the
    # offline fake.)
    monkeypatch.setenv("SAMAGRA_SLIDES_AUTOCAPTURE", "1")
    props = run.plan("textbook:circular-motion", dry=False, lane="slides")
    run.approve_seed("textbook:circular-motion")
    assert run.build(props[0]["assignment_id"])["status"] == "captured"

    pub = pub_run.publish("circular-motion", lanes=["slides"])
    assert pub["chapter"] == "circular-motion"        # publish succeeded

    art = pub_read.resolve_artifact("circular-motion", "slides", "html")
    assert art is not None
    assert art["media_type"].startswith("text/html")
    # sha-verified serving: the resolver re-hashes the bytes against the manifest.
    assert art["sha256"] == __import__("hashlib").sha256(art["bytes"]).hexdigest()
    # the published wrapper is self-contained (data-URI PDF embedded).
    assert b"data:application/pdf;base64," in art["bytes"]
```

> **Implementer note:** the load-bearing mechanic mirrors F1's golden — build() calls
> `dispatch.run_line("slides", slug)` → `slides.build_slides(slug)` with NO injected client,
> so the `envfx` fixture replaces `slides.build_slides` with a version that calls the
> import-time-captured `_REAL_BUILD_SLIDES` with the offline `_FakeNLM`. Verify
> `pub_run.publish(...)`'s return shape against the real `publish()` in
> `samagra/factory/publish/run.py` (it returns `{"chapter", "publication_id", "published",
> ...}` on a real publish) — the load-bearing asserts are `resolve_artifact(...) is not None`,
> the sha re-verify, and the embedded `data:application/pdf` URI. The no-migration asserts
> (`PRAGMA user_version` unchanged + no new table) are the T20 verification — do NOT assert
> whole-`governance.db` byte identity (a build legitimately appends event rows).

- [ ] **Step 3: Write the opt-in live smoke** — `tests/test_slides_live_smoke.py`:

```python
"""OPT-IN live smoke: one real slides build end-to-end against live NotebookLM via
the `nlm` CLI. Gated on an EXPLICIT flag (SAMAGRA_LIVE_SLIDES_SMOKE) AND
notebooklm_client.configured() (both required — interactive Google auth may be
absent in headless/subagent/CI, and generation is slow/flaky, so the standing gate
stays 100% offline and this NEVER runs by default). Run it manually to validate the
real NotebookLM subprocess boundary (the FIRST live validation, and the confirming
check of the exact download format):
  SAMAGRA_LIVE_SLIDES_SMOKE=1 python -m pytest tests/test_slides_live_smoke.py -v
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from samagra import config
from samagra.clients import notebooklm_client
from samagra.factory import slides


def _truthy(name):
    return (os.environ.get(name) or "").strip().lower() in {"1", "true", "yes", "on"}


pytestmark = pytest.mark.skipif(
    not (_truthy("SAMAGRA_LIVE_SLIDES_SMOKE") and notebooklm_client.configured()),
    reason="opt-in live smoke: set SAMAGRA_LIVE_SLIDES_SMOKE=1 + an authed `nlm` (nlm login)")


def test_live_slides_build_circular_motion(tmp_path, monkeypatch):
    try:
        from samagra.lectures import render
        render.load_chapter("circular-motion")
    except FileNotFoundError:
        pytest.skip("circular-motion chapter not present in this checkout")
    monkeypatch.setattr(config, "EXPORT_DIR", tmp_path / "lectures")
    res = slides.build_slides("circular-motion")      # real nlm client, live NotebookLM
    assert res["variant"] == "slides"
    assert res["items"] == 1
    assert Path(res["html"]).is_file() and Path(res["json"]).is_file()
    deck = config.EXPORT_DIR / "circular-motion" / "circular-motion-slides" / "deck.pdf"
    assert deck.is_file() and deck.stat().st_size > 0   # a real deck was downloaded
    html = Path(res["html"]).read_text(encoding="utf-8")
    assert "data:application/pdf;base64," in html or "data:application/" in html
```

- [ ] **Step 4: Update `.env.example`** — append the NotebookLM slides block after the image
    block. Use CONCRETE documented defaults; do NOT leave a value that would crash at import
    (the review-32/F1 lesson — every knob has a safe blank-or-numeric fallback in code, and
    the comments state the defaults):

```
# --- NotebookLM slides (Phase F2, the slides lane) ---
# Drives the external `nlm` CLI (Google NotebookLM). NO SAMAGRA secret — nlm stores
# the Google OAuth creds itself (run `nlm login`; configured() probes `nlm login
# --check`). NO AUDIO, ever. nlm is an owner-provisioned binary, NOT a pip package.
SAMAGRA_NLM_BIN=                    # override the nlm executable path (default: nlm on PATH)
SAMAGRA_SLIDES_FORMAT=             # detailed_deck (default) | presenter_slides
SAMAGRA_SLIDES_LENGTH=             # default (default) | short
SAMAGRA_SLIDES_DOWNLOAD_FORMAT=    # pdf (default) | pptx
SAMAGRA_SLIDES_TIMEOUT=900         # max seconds to block on generation (S1 poll; default 900)
SAMAGRA_SLIDES_POLL_INTERVAL=15    # seconds between studio-status polls (default 15)
SAMAGRA_SLIDES_EMBED_MAX=          # bytes; decks larger wrap download-only (default 8388608 = 8MB)
# 0 (default) = every slides build routes to `changes` for owner review; 1 = the
# standard llm capture gate applies (a completed deck -> captured).
SAMAGRA_SLIDES_AUTOCAPTURE=
# 1 to run the opt-in live slides smoke (tests/test_slides_live_smoke.py).
SAMAGRA_LIVE_SLIDES_SMOKE=
```

- [ ] **Step 5: Update `requirements.txt`** — add a COMMENT (no new dependency) documenting
    the external `nlm` CLI dependency. Append a comment line near the top (or after the
    existing `openai`/`anthropic` lines), e.g.:

```
# Phase F2 slides lane: drives the EXTERNAL `nlm` CLI (Google NotebookLM), an
# owner-provisioned binary (C:\Users\abc\.local\bin\nlm) — NOT a pip package.
# `nlm login` is an owner prerequisite. No Python dependency is added for it.
```

> **Implementer note:** do NOT add `nlm` to any pip requirement — it is an external CLI. Do
> not change any existing version pin.

- [ ] **Step 6: Run the goldens + smoke (smoke skips offline)**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_slides_golden.py tests/test_slides_live_smoke.py tests/test_publish_run.py -q`
Expected: goldens PASS; `test_publish_run` PASS (with the PUBLISHABLE set updated); the live
smoke is SKIPPED (no `SAMAGRA_LIVE_SLIDES_SMOKE` flag) — 1 skipped, rest passed.

- [ ] **Step 7: Commit**

```bash
git add .env.example requirements.txt tests/test_slides_golden.py tests/test_slides_live_smoke.py tests/test_publish_run.py
git commit -m "docs(f2): nlm slides env block + no-migration/publish-compat goldens + opt-in live smoke

.env.example gains the NotebookLM slides block (nlm bin / format / length /
download-format / timeout / poll-interval / embed-max / autocapture / live-smoke
flag) with concrete documented defaults; requirements.txt gains a comment noting
nlm is an external CLI, not a pip dep (no new dependency). Golden thread proves
plan->approve->build->changes (default) leaves the governance schema unbumped
(PRAGMA user_version unchanged, no new table — the no-migration T20 invariant), and
that with autocapture on a captured slides lane publishes via the existing G1 CLI +
resolves sha-verified through the G2 read surface with the PDF embedded as a data
URI (ZERO G1/G2 change). test_publish_run PUBLISHABLE set gains 'slides' (kind=llm
!= mcd). Live smoke gated on SAMAGRA_LIVE_SLIDES_SMOKE stays offline in the standing
gate.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: NO-AUDIO + HTTP-403 invariant pins, then full gates (TDD for the pins)

**Files:**
- Create: `tests/test_slides_invariants.py` (the NO-AUDIO pin + the HTTP-403 / approve-seed-skip pin)
- (verification only otherwise — no other commit unless a fix is needed)

The two invariants the spec singles out for review 34 that are not yet directly pinned: T18
(the run helper is NEVER invoked with an `audio`/`video`/non-slides studio argv over a full
build) and T17 (the `kind="llm"` slides lane is 403'd at `/api/factory/build` and skipped at
`/api/factory/approve-seed`).

- [ ] **Step 1: Write the failing invariant tests** — `tests/test_slides_invariants.py`:

```python
"""Phase F2 invariant pins: the NO-AUDIO guarantee (the nlm runner is NEVER invoked
with an audio/video/non-slides studio argv over a full build) and the HTTP-403 /
approve-seed-skip guarantee (kind=llm slides is structurally CLI-only). Offline."""
from __future__ import annotations

from pathlib import Path

import pytest

from samagra import config
from samagra.factory import run, slides
from samagra.governance import store


# ---------- T18: NO AUDIO ----------

class RecordingRunner:
    """A fake nlm subprocess runner that RECORDS every argv and scripts the whole
    slides lifecycle. Used to assert no audio/video verb is ever invoked."""
    def __init__(self, tmp_path):
        self.calls = []
        self._tmp = tmp_path
        self._polls = 0

    def __call__(self, args, *, timeout=None):
        self.calls.append(list(args))
        a = list(args)
        if a[1:3] == ["login", "--check"]:
            return _RR(stdout="✓ Authenticated\n")
        if a[1:3] == ["notebook", "create"]:
            return _RR(stdout="Created notebook: nb_x\n")
        if a[1:3] == ["source", "add"]:
            return _RR(stdout="ok\n")
        if a[1:3] == ["slides", "create"]:
            return _RR(stdout="kicked off\n")
        if a[1:3] == ["studio", "status"]:
            self._polls += 1
            import json
            return _RR(stdout=json.dumps(
                {"artifacts": [{"type": "slide_deck", "status": "completed", "id": "a1"}]}))
        if a[1:3] == ["download", "slide-deck"]:
            out = a[a.index("-o") + 1]
            Path(out).write_bytes(b"%PDF-1.4 fake")
            return _RR(stdout="downloaded\n")
        if a[1:3] == ["notebook", "delete"]:
            return _RR(stdout="deleted\n")
        return _RR(stdout="")


class _RR:
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def test_no_audio_or_video_verb_over_a_full_build(tmp_path, monkeypatch):
    from samagra.clients.notebooklm_client import NotebookLMClient
    from samagra.lectures import render
    monkeypatch.setattr(config, "EXPORT_DIR", tmp_path / "lectures")
    monkeypatch.setattr(slides, "_sleep", lambda s: None)
    monkeypatch.setattr(render, "load_chapter", lambda slug: {
        "title": "T", "sections": [{"title": "S", "blocks": [
            {"type": "prose", "html": "<p>x</p>"}]}]})
    runner = RecordingRunner(tmp_path)
    client = NotebookLMClient(runner=runner)
    slides.build_slides("circular-motion", nlm=client)
    # scan EVERY argv the runner saw: no audio/video verb, no non-slides studio create.
    for argv in runner.calls:
        joined = " ".join(argv).lower()
        assert "audio" not in joined
        assert "video" not in joined
    # the studio verbs seen are ONLY create-slides / status / download-slide-deck /
    # notebook lifecycle — never `studio create` for a non-slides artifact.
    verbs = {tuple(a[1:3]) for a in runner.calls}
    assert ("slides", "create") in verbs
    assert ("download", "slide-deck") in verbs
    assert not any(v[0] == "download" and v[1] in ("audio", "video") for v in verbs)


# ---------- T17: HTTP 403 + approve-seed skip ----------

@pytest.fixture()
def envfx(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "GOVERNANCE_DB", tmp_path / "governance.db")
    monkeypatch.setattr(config, "DATA_DB", tmp_path / "samagra.db")
    monkeypatch.setattr(config, "EXPORT_DIR", tmp_path / "lectures")
    store._INITIALIZED.clear()
    store.ensure_tables()
    monkeypatch.chdir(tmp_path)
    yield tmp_path
    store._INITIALIZED.clear()


def _client():
    from fastapi.testclient import TestClient
    from samagra.api.app import app
    return TestClient(app)


def test_http_build_403s_the_slides_lane(envfx, monkeypatch):
    # Plan a slides assignment via the CLI path, approve it, then hit the HTTP build
    # endpoint — kind=llm must 403 BEFORE run.build is called.
    monkeypatch.setattr(config, "DISABLE_ORIGIN_AUTH", True)     # local: origin gate open
    props = run.plan("textbook:circular-motion", dry=False, lane="slides")
    aid = props[0]["assignment_id"]
    run.approve(aid)
    r = _client().post("/api/factory/build", json={"assignment_id": aid})
    assert r.status_code == 403
    assert "cli-only" in r.json()["detail"].lower()


def test_http_approve_seed_skips_the_slides_lane(envfx, monkeypatch):
    # approve-seed over HTTP leaves the kind=llm slides child in-review (CLI-only).
    monkeypatch.setattr(config, "DISABLE_ORIGIN_AUTH", True)
    run.plan("textbook:circular-motion", dry=False, lane="slides")
    r = _client().post("/api/factory/approve-seed",
                       json={"seed_ref": "textbook:circular-motion"})
    assert r.status_code == 200
    assert r.json()["approved"] == []                # slides child NOT approved over HTTP
    conn = store.connect()
    try:
        a = [x for x in store.list_assignments(conn)
             if x.get("seed_ref") == "textbook:circular-motion"][0]
    finally:
        conn.close()
    assert a["status"] == "in-review"                # still CLI-only
```

- [ ] **Step 2: Run to verify** (these should PASS immediately — the invariants hold by
    construction from Tasks 1/4; the tests exist to PIN them):

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_slides_invariants.py -q`
Expected: PASS. If the HTTP-403 test fails, verify `app.py::api_factory_build` refuses
`spec.kind in ("llm","mcd")` (it does today at the 403 branch) and that the origin gate is
open under `DISABLE_ORIGIN_AUTH`. If a test needs a small shape tweak to match the real
endpoint response (e.g. the `detail` wording), adjust the ASSERTION to the real endpoint — do
NOT weaken the invariant (403 for build; `approved == []` + still in-review for approve-seed).

- [ ] **Step 3: Commit the invariant pins**

```bash
git add tests/test_slides_invariants.py
git commit -m "test(f2): pin NO-AUDIO + HTTP-403/approve-seed-skip invariants (T18, T17)

The nlm runner is NEVER invoked with an audio/video/non-slides studio argv over a
full build (NO-AUDIO holds by construction — the client exposes no such method; the
recording-runner pin proves it end-to-end). The kind=llm slides lane is 403'd at
POST /api/factory/build and left in-review by POST /api/factory/approve-seed —
structurally CLI-only over HTTP with zero new code (inherits the F-G5-3 gate).

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

- [ ] **Step 4: Full pytest run**

Run: `.\.venv\Scripts\python.exe -m pytest -q --junit-xml=<scratchpad>\gate-f2.xml`
(substitute the session scratchpad dir for `<scratchpad>`.)
Expected: read the junit-xml root attrs — `failures="0"`, `errors="0"`. Test count ≈ 771
baseline + ~50 new F2 tests (notebooklm_client ~21, slides pure ~10, slides
build/preflight/poll ~11, wiring ~12, golden ~3, invariants ~3). `skipped` — the opt-in live
LLM smoke + the live image smoke + the live QX smoke + the NEW live slides smoke (all gated,
all skip in the offline gate).

- [ ] **Step 5: Confirm the skips are ONLY the opt-in live smokes**

Run: `.\.venv\Scripts\python.exe -m pytest -q -rs 2>&1 | grep -i skip`
Expected: only the opt-in live-smoke SKIPPED lines (samadhan/LLM, image, QX, and the new
`test_slides_live_smoke`), each reasoned "opt-in live smoke". No unexpected skips.

- [ ] **Step 6: Frontend untouched — vitest baseline asserted by inspection**

F2 changed ZERO files under `frontend/`. Confirm with:
Run: `git diff --name-only main...HEAD -- frontend/`
Expected: empty output. The 639 vitest baseline stands unchanged — no vitest rerun needed
(recorded per house convention). If the diff is non-empty, STOP: a frontend file was touched
unexpectedly and must be explained before proceeding.

- [ ] **Step 7: Record the gate result** in the task report: total tests, failures=0, the skip
    set (only the opt-in live smokes), the junit-xml path, and the empty frontend diff. Do NOT
    commit (verification-only after the Step-3 pin commit). The orchestrator runs Codex review
    34 + the 4-lens adversarial review-gate pass + the merge OUTSIDE this plan.

---

## Spec-coverage map (self-review — every §Design item + T-row points to a task)

| Spec item | Task |
|---|---|
| §2 In: `notebooklm_client.py` (subprocess runner seam, configured stdout-parse, deck-format fail-closed, never-leak) | 1 |
| §2 In: `slides.py` `build_slides(slug, *, nlm=None)` | 2 (pure) + 3 (orchestration) |
| §2 In: `lines.py` slides Line (kind=llm, auto_fan=False, textbook:) | 4 |
| §2 In: `dispatch.run_line` route + `validate_product` slides branch | 4 |
| §2 In: build() reaches existing kind==llm path (one preflight arm + one needs_review clause) | 4 |
| §2 In: CLI `plan … --lane slides` via existing `plan(lane=)`; `.env.example` slides block | 4 (`test_plan_lane_slides_proposes_only_that_lane`), 5 (env block) |
| §2 In: offline TDD matrix (fake subprocess runner) + opt-in live smoke | 1–6 (matrix), 5 (smoke) |
| §3.0 S1 synchronous-blocking poll, bounded timeout, no new build() state, no migration | 3 (poll + timeout), 5 (no-migration golden) |
| §3.A A1 ephemeral per-build notebook (create→…→delete in `finally`) | 3 (`finally` delete + delete-failure paths) |
| §3.B B1 rendered chapter text via `--text`, bounded/truncation flag | 2 (`_source_text*`), 3 (`add_text_source` + `source_truncated` recorded) |
| §3.C C self-contained data-URI wrapper HTML, zero G1/G2 change, PPTX/oversize degrade | 2 (`_wrapper_html`), 5 (publish-compat golden) |
| §3.3 configured() stdout-parse (NOT exit code); ONE injectable run helper; never-leak | 1 |
| §3.1 the exact `nlm` command strings (pinned argv) | 1 (per-method argv pins) |
| §3.1 deck-format env knobs validated fail-closed at construction | 1 |
| §3.2 the synchronous poll loop (completed / failed-status / timeout / interval) | 3 |
| §3.4 D2 owner-reviewed only; synthetic `changes` verdict so `_assert_review_clean` passes; NO vision call | 3 (synthetic verdict), 4 (autocapture-off → changes) |
| §3.4 DEC-8 firewall structural (no review call, no StyleSeed) | 3 (preflight requires no StyleSeed; no review method exists) |
| §3.5 no StyleSeed on the lane; preflight needs no StyleSeed | 3 (`test_preflight_requires_no_styleseed`) |
| §3.6.1–2 run_line special-case + lane-dispatched preflight (samadhan/figure unchanged) | 4 (route + preflight arm + regression pin) |
| §3.6.3 `SAMAGRA_SLIDES_AUTOCAPTURE` default off → changes; on → std gate | 4 |
| §3.6.4 HTTP-403 FREE via kind=llm (build 403 + approve-seed skip) | 6 (T17 pins) |
| §3.7 CLI (no new subcommand) + `.env.example` + requirements comment (no new dep) | 4 (plan-lane) + 5 (env + requirements) |
| §4 invariants 1–11 (no secret; no prod write; publish gate; DEC-8; 5 guards; no migration; retryable; read-only; NO AUDIO; CLI-only over HTTP) | 1 (no secret/never-leak), 3 (finally cleanup/retryable), 4 (gate/guards/preflight), 5 (no-migration golden), 6 (NO-AUDIO + HTTP-403) |
| §5.1 T1–T21 offline matrix | see the T-row map below |
| §5.2 opt-in live smoke `SAMAGRA_LIVE_SLIDES_SMOKE` | 5 |
| §5.3 gates (pytest green, live-smoke skips; vitest unchanged) | 6 |
| §6 retry/partial/cleanup map (fail-closed-before-intent / retryable-rollback-after-intent / delete-failure never masks) | 3 (whole-build raise, finally, delete-failure) + 4 (retryable rollback) |

### §5.1 T-row → task map

| T# | Test | Task |
|---|---|---|
| T1 | `configured()` authed stdout → True | 1 (`test_configured_true_on_authenticated_stdout`) |
| T2 | `configured()` expired stdout, exit 0 → False (exit-code trap) | 1 (`test_configured_false_on_expired_stdout_even_if_exit_zero`) |
| T3 | `configured()` nlm absent → False, no raise | 1 (`test_configured_false_when_nlm_absent`) |
| T4 | run helper never-leak (verb named, no stderr blob / chapter text) | 1 (`test_nonzero_call_raises_naming_verb_not_stderr_blob`, `test_add_text_source_error_never_echoes_chapter_text`) |
| T5 | run helper argv not shell; text one element | 1 (`test_args_passed_as_list_never_shell_string`, `test_add_text_source_pins_argv`) |
| T6 | deck-format env validation fail-closed | 1 (`test_unknown_format/length/download_format_fails_closed`) |
| T7 | `poll_slides` completes | 3 (`test_build_slides_happy_path…` via pending×2) |
| T8 | `poll_slides` explicit failed status → RuntimeError | 3 (`test_poll_explicit_failed_status_raises`) |
| T9 | `poll_slides` timeout → TimeoutError | 3 (`test_poll_timeout_raises_timeouterror`) |
| T10 | `build_slides` happy path (fake runner) | 3 (`test_build_slides_happy_path…`) |
| T11 | wrapper html self-contained (data URI / download-only / escaped) | 2 (`test_wrapper_*`) + 3 (`test_wrapper_html_is_self_contained_data_uri`) |
| T12 | ephemeral cleanup in `finally` (+ delete-failure never masks) | 3 (`test_build_slides_deletes_notebook_in_finally_on_failure`, `test_delete_failure_does_not_mask_success`, `…_convert_failure_to_success`) |
| T13 | capture gate autocapture OFF → changes; synthetic verdict passes review-clean | 4 (`test_autocapture_off_default_routes_to_changes`) |
| T14 | capture gate autocapture ON, clean deck → captured (a failed deck raised earlier) | 4 (`test_autocapture_on_clean_build_is_captured`) + 3 (failed-status raise) |
| T15 | `validate_product` slides branch (deck missing → ValueError; legit passes) | 4 (`test_validate_product_requires_the_deck_file`, `…_passes_with_deck`) |
| T16 | publish compatibility (wrapper html + json; G2 resolve sha-verified) | 5 (`test_golden_publish_compat_on_wrapper_html`) |
| T17 | HTTP 403 / approve-seed skip | 6 (`test_http_build_403s…`, `test_http_approve_seed_skips…`) |
| T18 | NO-AUDIO invariant (runner never sees audio/video argv) | 6 (`test_no_audio_or_video_verb_over_a_full_build`) |
| T19 | build() retryable rollback (nlm/timeout raise → product_build_failed → retry succeeds) | 4 (`test_slides_failure_rolls_back_and_is_retryable`) |
| T20 | governance untouched (no migration): `PRAGMA user_version` unchanged + no new table | 5 (`test_golden_default_routes_to_changes_governance_schema_stable`, `test_golden_no_new_governance_table`) |
| T21 | `slides.preflight` (chapter absent → FileNotFoundError; unconfigured → RuntimeError; no StyleSeed/key) | 3 (`test_preflight_*`) |

**Not in this plan (per the task brief):** Codex review 34, the 4-lens adversarial review-gate
pass, and the merge — the orchestrator runs those outside the plan (§5.4).

---

## Notes — spec/reality reconciliations & resolved ambiguities

1. **`nlm login --check` exit code (spec §3.3/§3.1 vs reality).** The spec says it "exits 0
   even when auth is expired". The REAL `nlm` 0.6.9 behavior is `EXIT=1` on expiry (stdout:
   `✗ Authentication Error`; the authenticated case prints `✓ Authenticated`). The
   consequence for the design is NIL: the spec's mandated **stdout-parse** `configured()` is
   implemented verbatim (Task 1) and is strictly safer than any exit-code read regardless of
   which way the code points. The plan's `configured()` returns False if stdout contains the
   fail marker OR lacks the ok marker, so it is correct whether the exit code is 0 or 1 on
   failure. The only correction to the spec's prose is factual (the exit code is nonzero on
   failure here), not a design change. T2 pins the exit-0-but-expired trap AND T3/an added case
   pin the exit-1-expired case.
2. **All other `nlm` flags match the spec pin exactly** (verified against `nlm` 0.6.9
   `--help`): `notebook create [TITLE]`; `source add <nb> --text <t> --wait --wait-timeout
   <T>` (`--wait-timeout` default 600.0, we pass the slides timeout); `slides create <nb>
   --confirm --format {detailed_deck|presenter_slides} --length {short|default}`; `studio
   status <nb> --json`; `download slide-deck <nb> --id <aid> --format {pdf|pptx} -o <out>
   --no-progress`; `notebook delete <nb> --confirm`. No deviation.
3. **`download slide-deck` output shape (spec §3.C's PDF-vs-.txt ambiguity).** The
   authoritative per-command help says **"Download Slide Deck (PDF or PPTX)"** — no `.txt`
   flag exists on the real 0.6.9 command (the spec's `.txt` was from an `--ai` summary line).
   The plan pins `--format pdf` (default) and the wrapper handles PDF (inline `<embed>`) or
   PPTX (download-only card) — no `.txt` path is needed. The owner-run live smoke (Task 5) is
   the confirming byte check; the publish story is format-agnostic either way.
4. **Notebook-id parsing (spec §3.1 note: "or `nlm notebook list --json --quiet` if stdout id
   is not machine-clean").** The plan parses the created id from `notebook create` stdout
   (`_parse_notebook_id`, best-effort last-token-of-the-`Created notebook:`-line). The exact
   stdout shape is confirmed only by the live smoke (no `--confirm`/create was ever run
   during planning), so if the live smoke shows the stdout id is not machine-clean, the
   fallback is a one-line change in `create_notebook` to call `notebook list --json --quiet`
   and diff for the new id — a localized follow-up that does not touch the argv pins or the
   engine. Flagged here as the single stdout-parse the offline tests script rather than pin
   against a live shape.
5. **The two forced standing-test additions (called out explicitly per the constraints).**
   Exactly two standing tests change, both because the wiring makes a new lane key mandatory
   in an exact-set assertion: (a) `tests/test_factory_lines.py` — add `"slides"` to the
   label-loop tuple AND the `set(lines.LINES)` set (Task 4, Step 3d); (b)
   `tests/test_publish_run.py` — add `"slides"` to the `PUBLISHABLE` set (Task 5, Step 1,
   since `kind="llm"` ≠ `mcd` ⇒ slides IS publishable). No other standing test is edited;
   any other adjustment would be a pure env-isolation monkeypatch addition (delenv of a
   `SAMAGRA_SLIDES_*` knob) only if a standing test's environment leaks one.
6. **No real `time.sleep` in the standing gate.** The poll wait is routed through
   `slides._sleep` (monkeypatched to a no-op in every poll test), and the `export`/`envfx`
   fixtures set `SAMAGRA_SLIDES_POLL_INTERVAL=0` / `SAMAGRA_SLIDES_TIMEOUT=0` where relevant.
   No standing test blocks on a real interval, and no standing test shells out to `nlm` or
   hits Google — everything routes through the injected fake runner / fake client.
