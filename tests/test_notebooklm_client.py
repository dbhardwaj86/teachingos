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
