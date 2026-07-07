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
    # Scan EVERY argv the runner saw for an audio/video nlm verb. The audio/video
    # guarantee lives in the nlm COMMAND GRAMMAR — the positional subcommand tokens
    # (group + verb) and the flag NAMES — never in free-form VALUE tokens (a `-o`
    # download path, a `--text` chapter body). Those value tokens are caller/OS
    # controlled: pytest derives tmp_path from THIS test's own name, so the download
    # path literally contains the substring "audio" — a raw whole-argv join would
    # false-positive on the path, not on any real verb. So we scan only the command
    # tokens: the subcommand group+verb (positions 1..2) and every flag-name token
    # (starts with "-"), skipping the value that follows a value-taking flag.
    _VALUE_FLAGS = {"-o", "--text", "--id", "--format", "--length",
                    "--wait-timeout", "--out"}
    for argv in runner.calls:
        cmd_tokens = list(argv[1:3])                # the nlm <group> <verb>
        i = 3
        while i < len(argv):
            tok = argv[i]
            if isinstance(tok, str) and tok.startswith("-"):
                cmd_tokens.append(tok)              # a flag NAME is grammar, keep it
                if tok in _VALUE_FLAGS:
                    i += 2                           # skip its VALUE (path/text) token
                    continue
            i += 1
        joined = " ".join(str(t) for t in cmd_tokens).lower()
        assert "audio" not in joined, argv
        assert "video" not in joined, argv
    # the studio verbs seen are ONLY create-slides / status / download-slide-deck /
    # notebook lifecycle — never `studio create` for a non-slides artifact.
    verbs = {tuple(a[1:3]) for a in runner.calls}
    assert ("slides", "create") in verbs
    assert ("download", "slide-deck") in verbs
    assert not any(v[0] == "download" and v[1] in ("audio", "video") for v in verbs)


# ---------- T17: HTTP 403 + approve-seed skip ----------
# Bound against the REAL G5 endpoints (verified against samagra/api/app.py's
# api_factory_build + api_factory_approve_seed and samagra/api/origin_auth.py):
#   * origin bypass — a plain TestClient request originates from a LOOPBACK client
#     host, so origin_auth.is_loopback_host passes it (the cloudflared-origin path).
#     No knob is set; this mirrors the G5 golden happy-path tests exactly. (The G5
#     origin-gating test instead OVERRIDES _client_host to a remote IP to prove the
#     gate fires — the inverse direction, not needed here.)
#   * build 403 detail — "the {kind} lane ({pipeline}) is CLI-only — ..." (contains
#     'cli-only' case-insensitively); the llm/mcd branch fires BEFORE run.build.
#   * approve-seed response — {"seed_ref": ..., "approved": [...]}; the llm/mcd
#     children are filtered out, left in-review (CLI-only through their whole HTTP
#     lifecycle).

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
    # endpoint — kind=llm must 403 BEFORE run.build is called. The build 403 branch
    # keys on the assignment's lane KIND, so it holds regardless of approval status.
    props = run.plan("textbook:circular-motion", dry=False, lane="slides")
    aid = props[0]["assignment_id"]
    run.approve(aid)
    # Belt: even if the endpoint delegated, run.build must not be reached for slides.
    monkeypatch.setattr("samagra.factory.run.build",
                        lambda a: pytest.fail("run.build was reached for the slides lane"))
    r = _client().post("/api/factory/build", json={"assignment_id": aid})
    assert r.status_code == 403
    assert "cli-only" in r.json()["detail"].lower()


def test_http_approve_seed_skips_the_slides_lane(envfx, monkeypatch):
    # approve-seed over HTTP leaves the kind=llm slides child in-review (CLI-only):
    # the endpoint filters children whose LINES[pipeline].kind is llm/mcd, so the
    # slides row is never rubber-stamped by a GUI batch click.
    run.plan("textbook:circular-motion", dry=False, lane="slides")
    r = _client().post("/api/factory/approve-seed",
                       json={"seed_ref": "textbook:circular-motion"})
    assert r.status_code == 200
    assert r.json()["approved"] == []
    conn = store.connect()
    try:
        a = [x for x in store.list_assignments(conn)
             if x.get("seed_ref") == "textbook:circular-motion"][0]
    finally:
        conn.close()
    assert a["status"] == "in-review"
