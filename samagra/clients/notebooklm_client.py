"""The ONE NotebookLM call site (Phase F2, the slides lane) — mirrors
clients/image_client.py as the single boundary to an external generation service,
but the "SDK" is the external `nlm` CLI reached through a SUBPROCESS runner.

SAFETY: this lane holds NO SAMAGRA secret — `nlm` stores the Google OAuth creds
itself (run `nlm login`). configured() probes `nlm login --check` and parses its
STDOUT for the authenticated marker, NOT the exit code (nlm can print
'Authentication Error' — pinned in the spec). Every `nlm` invocation funnels
through ONE injectable `runner` callable (default = a thin subprocess.run wrapper),
so tests inject a fake runner and NO standing test shells out or touches Google.
A non-success raises a concise RuntimeError naming the nlm subcommand and a
sanitized reason — it NEVER echoes raw `nlm` stderr blobs (which can carry
cookies/session hints), the chapter text, or notebook content. `__repr__` carries
no secret. NO AUDIO/VIDEO: this client exposes only slides + notebook-lifecycle
methods, so audio/video verbs are unreachable by construction (spec 4.10).
"""
from __future__ import annotations

import json
import os
import re
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
        errors="replace",
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
        except Exception as e:  # noqa: BLE001 - never leak: wrap ANY runner error
            raise RuntimeError(f"nlm {verb} failed: unexpected error") from e
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


_NB_ID_RE = re.compile(r"created notebook:\s*(\S+)", re.IGNORECASE)


def _parse_notebook_id(stdout: str) -> str:
    """Best-effort parse of the created notebook id from `nlm notebook create`
    stdout (nlm prints 'Created notebook: <id>'). Anchored on the literal label so
    an unexpected line shape FAILS CLOSED (returns '' -> create_notebook raises)
    rather than returning a garbage-but-truthy token from an unrelated colon line.
    The exact live shape is confirmed by the opt-in live smoke; if it differs, the
    documented fallback is `nlm notebook list --json --quiet` (spec note)."""
    m = _NB_ID_RE.search(stdout or "")
    return m.group(1) if m else ""
