"""The guarded engine layer: map a lane -> an existing renderer; validate I/O.

Phase 1 lanes are DETERMINISTIC and write only LOCAL artifacts via the lecture
exporter (no new prod write path). validate_product re-asserts the output contract
at the write boundary exactly as bridge.seed_payload.validate_seed_payload does
(spec §3.2 guard 4); the answer-leak hook is a no-op for Phase 1's lecture lanes
but is the structural seam for the later QX/paper lanes.
"""
from __future__ import annotations

from pathlib import Path

from ..lectures import export as lex
from ..clients.mcd_client import McdClient
from . import deck, figure, paper, samadhan
from .lines import LINES
from .seed_payload import validate_seed_payload


def _slug(seed_ref: str) -> str:
    return seed_ref.split(":", 1)[-1]


def validate_seed_for_line(line: str, seed_ref: str) -> None:
    """Cheap pre-check (before recording any build intent): the seed_ref matches
    the lane's source prefix and names a slug."""
    spec = LINES.get(line)
    if spec is None:
        raise ValueError(f"unknown line {line!r}")
    if not any((seed_ref or "").startswith(p) for p in spec.source_prefixes):
        raise ValueError(f"seed {seed_ref!r} is not valid input for line {line!r}")
    if not _slug(seed_ref):
        raise ValueError(f"seed {seed_ref!r} has no slug")


def run_line(line: str, slug: str) -> dict:
    """Run the lane's engine. Phase-C lane-kind dispatch:
      - deck            -> the pure local flashcard engine (no external write).
      - paper/drill     -> the QX-backed answer-safe paper engine (kind 'qx';
        read-only QX, local write; variant = the lane key sizes paper vs drill).
      - revision/lecture-> the lecture exporter (upload_gdocs=False keeps the
        Phase-1 invariant: local artifacts only, never an external Google Docs
        upload — review 24 H1).
    The mcd (seed) branch lands in C3.
    """
    spec = LINES[line]
    if line == "deck":
        return deck.build_deck(slug)
    if line == "figure":
        return figure.build_figures(slug)
    if spec.kind == "qx":
        return paper.build_paper(slug, variant=line)
    if spec.kind == "mcd":
        raise ValueError(
            f"line {line!r} is an mcd lane — built via the seed path (run_seed), "
            f"not run_line")
    if spec.kind == "llm":
        return samadhan.build_samadhan(slug)
    return lex.export_one(slug, spec.variant, upload_gdocs=False)


def run_seed(payload: dict) -> dict:
    """The mcd (`seed`) lane produce step — the ONE prod write after the bridge
    fold (F-C2). Re-assert the payload contract at the literal write boundary
    (belt-and-suspenders: build() also validates BEFORE recording intent, but
    run_seed is the only mcd writer and must never POST an unvalidated body even
    if a future caller forgets), create the seed via the existing owner-initiated
    capture contract (McdClient.create_seed), and return a result carrying the new
    seed id. Raises ValueError on a bad payload OR a response with no id — never a
    silent blank/duplicate write."""
    validate_seed_payload(payload)
    seed = McdClient().create_seed(payload)
    seed_id = seed.get("id") if isinstance(seed, dict) else None
    if not seed_id:
        raise ValueError(
            "mcd create_seed returned no seed id — refusing to mark captured")
    return {"variant": "seed", "seed": seed, "seed_id": str(seed_id),
            "artifact_ref": f"mcd:{seed_id}"}


def validate_product(line: str, result: dict) -> None:
    """Write-boundary output guard: the artifact exists, is non-empty, and (for
    answer-bearing lanes — none in Phase 1) carries zero answer data. Raises ValueError."""
    html = result.get("html")
    if not html:
        raise ValueError(f"line {line!r} produced no html artifact")
    p = Path(html)
    if not p.is_file() or p.stat().st_size == 0:
        raise ValueError(f"line {line!r} artifact missing or empty: {html}")
    # Answer-leak structural hook (no-op for lecture lanes; enforced for QX in Phase C).
    _assert_no_answer_leak(line, result)
    _assert_review_clean(line, result)
    _assert_figures_present(line, result)


# Structural answer/solution markers QX uses across its THREE answer renderers,
# none of which appear in the read-only /api/qsearch student render (stem / options
# / passage / matrix only):
#   - builder_pages / qx_browser authoring views: class="answer" / answer-label
#   - paper_render teacher paper:               class="pq-ans" (or "pq-ans unv"),
#                                               and the class="pkey" answer-key appendix
# All are HTML class/attribute tokens — they cannot occur in legitimately rendered
# question PROSE (a stem may contain the word "answer"; it can never contain
# class="answer" or pq-ans), so scanning for them is false-positive-free. The guard
# is defense in depth: there is no live leak today (the search render never reads
# rj["answer"]), but the single most plausible future regression is QX reusing its
# sibling teacher renderer (paper_render._question_html), whose pq-ans / pkey markup
# these markers now catch.
_ANSWER_MARKERS = (
    'class="answer"',
    "answer-label",
    "answer_confidence",
    "data-answer",
    "data-correct",
    'class="solution"',
    "pq-ans",
    "pkey",
)


def _assert_no_answer_leak(line: str, result: dict) -> None:
    """For QX (paper/drill) lanes ONLY: re-assert the published artifacts carry no
    answer/solution data. Defense in depth — we do not trust the upstream render to
    be answer-free and re-check at our write boundary. Scans EVERY written artifact
    (the printable html AND the sibling json, which embeds each question's raw QX
    body verbatim) and raises ValueError on any structural answer/solution marker.
    kind in {local, mcd} keep the no-op (lecture/deck carry no answer columns; the
    mcd payload is validated by validate_seed_payload, not this guard)."""
    spec = LINES.get(line)
    if spec is None or spec.kind != "qx":
        return
    blobs = []
    for key in ("html", "json"):          # scan every written artifact, not just the html
        path = result.get(key)
        if path and Path(path).is_file():  # read what was actually written (defensive)
            blobs.append(Path(path).read_text(encoding="utf-8"))
    text = "\n".join(blobs).lower()
    for marker in _ANSWER_MARKERS:
        if marker in text:
            raise ValueError(
                f"line {line!r} artifact carries an answer/solution marker "
                f"({marker!r}) — refusing to publish a paper that may leak answers")


def _assert_review_clean(line: str, result: dict) -> None:
    """For llm (samadhan) lanes ONLY: assert the result is well-formed enough to be
    routed (an integer `errors` + an integer `items` count, and — when there ARE
    items — a non-empty `verdicts` list, so a brief whose reviewer was skipped is
    never captured). It does NOT raise on errors>0 or on an empty brief (items==0):
    those are valid artifacts that build() routes to `changes` (owner review), never
    silent capture. This is the llm analog of _assert_no_answer_leak — the artifact
    records the verdicts; the capture GATE (errors==0 and items>0) is applied by
    build()."""
    spec = LINES.get(line)
    if spec is None or spec.kind != "llm":
        return
    if not isinstance(result.get("errors"), int) or not isinstance(result.get("items"), int):
        raise ValueError(f"line {line!r} produced no reviewer error/item count — "
                         f"refusing to capture an unreviewed brief")
    if result["items"] > 0 and (
            not isinstance(result.get("verdicts"), list) or not result["verdicts"]):
        raise ValueError(f"line {line!r} produced no reviewer verdicts — "
                         f"refusing to capture an unreviewed brief")


def _assert_figures_present(line: str, result: dict) -> None:
    """For the figure lane ONLY: the gallery html check (above) is not enough — a
    build that produced a gallery but zero image files must be refused, not
    captured. Assert at least one non-empty PNG exists on disk under the sibling
    <slug>-figures/ directory. A legitimately EMPTY build (items==0 — a chapter
    with no image-need briefs) is NOT a defect: it flows through to build()'s
    needs_review gate and lands in 'changes' (the samadhan empty-brief precedent),
    so it early-returns here instead of raising into the rollback path."""
    if result.get("variant") != "figure":
        return
    if result.get("items", 0) == 0:
        # a legitimate empty brief set; build()'s needs_review gate routes it to `changes`
        return
    pngs = []
    for f in result.get("figures", []) or []:
        html = result.get("html")
        if not html:
            continue
        figdir = Path(html).parent / f"{Path(html).stem}"   # <slug>-figures
        p = figdir / str(f.get("png", ""))
        if p.is_file() and p.stat().st_size > 0:
            pngs.append(p)
    if not pngs:
        raise ValueError(
            f"line {line!r} produced no non-empty PNG figure — refusing to capture "
            f"a figure gallery with no images")
