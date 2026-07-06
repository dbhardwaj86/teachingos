# Slice R — combinedDBQues Question-Bank Rewire Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repoint SAMAGRA's question bank from the old QX engine (:8783, 67k mixed) to combinedDBQues (:8790, 48,589 physics-only), upgrading the paper/drill lanes to chapter-scoped, deduplicated retrieval — with zero change to the write paths, guards, or publish gate.

**Architecture:** Config repoint (new `COMBINED_DB_ROOT`; `QX_SERVER_URL` default → :8790; DB paths → the unified sqlites) + a git-committed 59-row `chapter_map.json` with a pure loader + chapter-filtered retrieval with text-query fallback + a pure client-side dedupe in `paper.py`. The concept spine SQL runs unchanged against `unified_builder.sqlite` (86 → 128 concepts). HTTP contract is identical (combinedDBQues is a QX fork), so the Questions app, proxy, sanitizer, and answer-leak guard transfer verbatim.

**Tech Stack:** Python 3.12, FastAPI, sqlite3 (mode=ro), pytest; no frontend changes (vitest/tsc/build still run as gates).

**Spec:** `docs/superpowers/specs/2026-07-06-samagra-combineddbques-rewire-design.md` (approved by the Chairman 2026-07-06, "slice r spec approved... auto approve and execute").

---

## Plan-time verification results (spec §12 — all resolved 2026-07-06 against live :8790)

1. **Empty `q` + `chapter` filter: SUPPORTED.** `GET /api/qsearch?q=&mode=exact&page=1` returns the full listing (total 46,459); adding `chapter=Electric Charges and Fields` returns total 3,583, all rows in that chapter. Chapter-scoped listing is the PRIMARY retrieval.
2. **`chapter` param matches the DISPLAY name**, not the dotted `chapter_id` (`chapter=physics.c12.electric_charges_and_fields` → total 0). `chapter_map.json` rows therefore carry BOTH (`chapter_id` for validation/coverage, `chapter` for the API call).
3. **Latency:** root 2.8s, chapter-filtered listing 11.2s (cold-ish). Under `_TIMEOUT=30`. Keep the timeout at 30.
4. **Facet chapter names ≡ taxonomy names**, exactly (30 facet chapters, strings identical to `build/taxonomy/physics.json` `name` fields — spot-checked incl. `Basic Mathematics & Vectors for Physics`).
5. **Unified DB tables confirmed** (direct `mode=ro` peek): `unified_content.sqlite` has `documents`/`questions` (adapter SQL works); `unified_builder.sqlite` has `concept`/`question_concept`/`search_index` (concepts SQL works); 128 physics concepts.

## Deltas from the spec (found at plan time — record these in the spec's §12 at merge)

- **D1 (spec §9.2):** No new `SAMAGRA_BIND_HOST` env var — `config.HOST` ALREADY reads `SAMAGRA_HOST` (default `127.0.0.1`). LAN demo mode documents the existing var (`SAMAGRA_HOST=0.0.0.0`) instead of adding a duplicate.
- **D2 (spec §14):** Rollback via `SAMAGRA_COMBINED_DB_ROOT` alone can't restore the old DB paths (old layout `<root>/qx/builder.sqlite` vs new `<root>/app/qx/unified_builder.sqlite`). Fix: `QX_BUILDER_DB`/`QX_CONTENT_DB` get their own env overrides (`SAMAGRA_QX_BUILDER_DB`/`SAMAGRA_QX_CONTENT_DB`). Rollback = `SAMAGRA_QX_SERVER_URL` + those two lines, documented in `.env.example`.
- **D3 (spec §7):** `adapters/qx.py::_ro` uses `immutable=1` — WRONG for combinedDBQues's live WAL corpus (immutable makes sqlite skip the WAL and serve stale/torn reads). Task 5 drops it (plain `mode=ro`).

## File structure

| File | Action | Responsibility |
|---|---|---|
| `samagra/config.py` | modify | `COMBINED_DB_ROOT`, `QX_SERVER_URL` :8790 default, DB path repoints + env overrides, `CHAPTER_MAP` |
| `chapter_map.json` | create (repo root) | 59-row owner-curated slug → NCERT-chapter map (git-committed, like `concept_aliases.json`) |
| `samagra/factory/chapter_map.py` | create | pure loader/validator for `chapter_map.json` |
| `samagra/factory/paper.py` | modify | chapter-scoped retrieval + fallback; `_dedupe_results`; :8790 error message |
| `samagra/adapters/qx.py` | modify | drop `immutable=1` (live WAL corpus) |
| `samagra/api/app.py` | modify | stale `:8783` strings in the questions proxy comment/error |
| `samagra/clients/qx_client.py` | modify | stale docstring only (no logic change) |
| `tests/fixtures/combineddb_taxonomy.json` | create | frozen 30-chapter code↔name vocabulary (no live dependency in unit tests) |
| `tests/test_chapter_map.py` | create | loader + committed-map validation |
| `tests/test_factory_paper.py` | modify | retrieval branching + dedupe tests |
| `tests/test_adapters_qx_live.py` | create | live-WAL visibility regression for `_ro` |
| `tests/test_qx_live_smoke.py` | create | OPT-IN golden thread vs real :8790 |
| `.env.example`, `docs/deploy-tunnel.md` | modify | combinedDBQues block, rollback lines, LAN demo mode |

Branch: `feature/combineddbques-rewire` off `main`. **Serialize all git — never commit from a background process or concurrently with a committing subagent** (D2 process learning).

---

### Task 0: Branch

- [ ] **Step 1: Create the feature branch**

```bash
cd C:/SandBox/claude_box/TeachingOS
git checkout main && git pull origin main
git checkout -b feature/combineddbques-rewire
```

Expected: clean checkout, branch created at current `main` tip.

---

### Task 1: Config repoint

**Files:**
- Modify: `samagra/config.py:32-35` (QX block), `samagra/config.py:61` (server URL), add `CHAPTER_MAP` near `CONCEPT_ALIASES` (`samagra/config.py:108`)
- Test: `tests/test_config_combineddb.py` (create)

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_config_combineddb.py
"""Slice R config pins: combinedDBQues is the question-bank source by default.

These assert DEFAULTS, so each guard skips when the corresponding env override is
set in the developer's environment (config reads env at import time).
"""
import os
from pathlib import Path

import pytest

from samagra import config


def _no_env(*names):
    return pytest.mark.skipif(
        any(os.environ.get(n) for n in names), reason="env override set")


@_no_env("SAMAGRA_COMBINED_DB_ROOT")
def test_combined_db_root_default():
    assert config.COMBINED_DB_ROOT == Path(r"C:\SandBox\claude_khanak_box\combinedDBQues")


@_no_env("SAMAGRA_QX_SERVER_URL")
def test_qx_server_url_defaults_to_8790():
    assert config.QX_SERVER_URL == "http://127.0.0.1:8790"


@_no_env("SAMAGRA_COMBINED_DB_ROOT", "SAMAGRA_QX_BUILDER_DB", "SAMAGRA_QX_CONTENT_DB")
def test_qx_dbs_point_at_the_unified_sqlites():
    assert config.QX_BUILDER_DB == config.COMBINED_DB_ROOT / "app" / "qx" / "unified_builder.sqlite"
    assert config.QX_CONTENT_DB == config.COMBINED_DB_ROOT / "app" / "qx" / "unified_content.sqlite"


def test_chapter_map_is_a_committed_repo_root_artifact():
    assert config.CHAPTER_MAP == config.REPO_ROOT / "chapter_map.json"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_config_combineddb.py -v`
Expected: FAIL — `AttributeError: module 'samagra.config' has no attribute 'COMBINED_DB_ROOT'`

- [ ] **Step 3: Implement the config changes**

In `samagra/config.py`, replace the QX block (lines 32-35):

```python
# --- combinedDBQues (the unified physics question bank — Slice R source) ---
# 48,589 physics questions, 30 canonical NCERT chapters, 128 concepts. Serves
# GET /api/qsearch on :8790 (their RUNBOOK hard rule). READ-ONLY for samagra:
# HTTP for serving; direct sqlite strictly mode=ro (coverage-build only).
COMBINED_DB_ROOT = _env_path(
    "SAMAGRA_COMBINED_DB_ROOT", Path(r"C:\SandBox\claude_khanak_box\combinedDBQues"))

# --- QX (question engine — served by combinedDBQues since Slice R) ---
# The QX_* names are kept: every consumer keys on them and the serving engine is
# still the QX engine (combinedDBQues is a fork). QX_ROOT stays for legacy refs
# but no longer feeds the question path. Rollback to the old engine = set
# SAMAGRA_QX_SERVER_URL=http://127.0.0.1:8783 + the two DB overrides below
# (documented in .env.example).
QX_ROOT = _env_path("SAMAGRA_QX_ROOT", GPT_BOX / "gpt-extract-ques")
QX_CONTENT_DB = _env_path(
    "SAMAGRA_QX_CONTENT_DB", COMBINED_DB_ROOT / "app" / "qx" / "unified_content.sqlite")
QX_BUILDER_DB = _env_path(
    "SAMAGRA_QX_BUILDER_DB", COMBINED_DB_ROOT / "app" / "qx" / "unified_builder.sqlite")
```

Change line 61 (and the comment above it — replace `:8783` with `:8790`, name combinedDBQues):

```python
QX_SERVER_URL = os.environ.get("SAMAGRA_QX_SERVER_URL", "http://127.0.0.1:8790")
```

Next to `CONCEPT_ALIASES` (line 108), add:

```python
# The curated textbook-slug -> combinedDBQues NCERT-chapter mapping — git-COMMITTED
# (owner-curated review surface, like concept_aliases.json). One row per textbook
# chapter slug; values carry chapter_id (validation/coverage) + chapter display
# name (the /api/qsearch facet value).
CHAPTER_MAP = REPO_ROOT / "chapter_map.json"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_config_combineddb.py -v`
Expected: 4 PASS

- [ ] **Step 5: Run the full pytest gate — expect coverage/adapter tests to still pass (they inject fixture paths)**

Run: `python -m pytest -q`
Expected: same green count as `main` (667 collected, 1 skip) + 4 new. If anything newly red, it's a test reading `config.QX_*` defaults from disk — fix the test to inject a path, never weaken config.

- [ ] **Step 6: Commit**

```bash
git add samagra/config.py tests/test_config_combineddb.py
git commit -m "feat(rewire): config repoints question bank to combinedDBQues :8790 (Slice R)"
```

---

### Task 2: `chapter_map.json` + taxonomy fixture + pure loader

**Files:**
- Create: `chapter_map.json` (repo root)
- Create: `samagra/factory/chapter_map.py`
- Create: `tests/fixtures/combineddb_taxonomy.json`
- Test: `tests/test_chapter_map.py`

- [ ] **Step 1: Write the taxonomy fixture** — frozen copy of the 30 code↔name pairs from `combinedDBQues/build/taxonomy/physics.json` (aliases dropped; no live dependency in unit tests):

```json
{
  "chapters": [
    {"code": "physics.c11.basic_maths", "name": "Basic Mathematics & Vectors for Physics"},
    {"code": "physics.c11.units_and_measurements", "name": "Units and Measurements"},
    {"code": "physics.c11.motion_in_a_straight_line", "name": "Motion in a Straight Line"},
    {"code": "physics.c11.motion_in_a_plane", "name": "Motion in a Plane"},
    {"code": "physics.c11.laws_of_motion", "name": "Laws of Motion"},
    {"code": "physics.c11.work_energy_and_power", "name": "Work, Energy and Power"},
    {"code": "physics.c11.rotational_motion", "name": "System of Particles and Rotational Motion"},
    {"code": "physics.c11.gravitation", "name": "Gravitation"},
    {"code": "physics.c11.mechanical_properties_of_solids", "name": "Mechanical Properties of Solids"},
    {"code": "physics.c11.mechanical_properties_of_fluids", "name": "Mechanical Properties of Fluids"},
    {"code": "physics.c11.thermal_properties_of_matter", "name": "Thermal Properties of Matter"},
    {"code": "physics.c11.thermodynamics", "name": "Thermodynamics"},
    {"code": "physics.c11.kinetic_theory", "name": "Kinetic Theory"},
    {"code": "physics.c11.oscillations", "name": "Oscillations"},
    {"code": "physics.c11.waves", "name": "Waves"},
    {"code": "physics.c12.electric_charges_and_fields", "name": "Electric Charges and Fields"},
    {"code": "physics.c12.electrostatic_potential_and_capacitance", "name": "Electrostatic Potential and Capacitance"},
    {"code": "physics.c12.current_electricity", "name": "Current Electricity"},
    {"code": "physics.c12.moving_charges_and_magnetism", "name": "Moving Charges and Magnetism"},
    {"code": "physics.c12.magnetism_and_matter", "name": "Magnetism and Matter"},
    {"code": "physics.c12.electromagnetic_induction", "name": "Electromagnetic Induction"},
    {"code": "physics.c12.alternating_current", "name": "Alternating Current"},
    {"code": "physics.c12.electromagnetic_waves", "name": "Electromagnetic Waves"},
    {"code": "physics.c12.ray_optics", "name": "Ray Optics and Optical Instruments"},
    {"code": "physics.c12.wave_optics", "name": "Wave Optics"},
    {"code": "physics.c12.dual_nature", "name": "Dual Nature of Radiation and Matter"},
    {"code": "physics.c12.atoms", "name": "Atoms"},
    {"code": "physics.c12.nuclei", "name": "Nuclei"},
    {"code": "physics.c12.semiconductor_electronics", "name": "Semiconductor Electronics"},
    {"code": "physics.c12.communication_systems", "name": "Communication Systems"}
  ]
}
```

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_chapter_map.py
"""chapter_map.load(): pure parse/validate of the committed slug->chapter map,
plus curation pins on the committed artifact itself (all 59 slugs, every row
canonical against the frozen combinedDBQues taxonomy vocabulary)."""
import json
from pathlib import Path

from samagra import config
from samagra.factory import chapter_map

_FIXTURE = Path(__file__).parent / "fixtures" / "combineddb_taxonomy.json"


def _vocab():
    data = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    return {c["code"]: c["name"] for c in data["chapters"]}


def test_load_parses_valid_rows(tmp_path, monkeypatch):
    p = tmp_path / "chapter_map.json"
    p.write_text(json.dumps({
        "gauss-law": {"chapter_id": "physics.c12.electric_charges_and_fields",
                      "chapter": "Electric Charges and Fields"}}), encoding="utf-8")
    monkeypatch.setattr(config, "CHAPTER_MAP", p)
    m = chapter_map.load()
    assert m["gauss-law"]["chapter"] == "Electric Charges and Fields"


def test_load_missing_file_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CHAPTER_MAP", tmp_path / "nope.json")
    assert chapter_map.load() == {}


def test_load_drops_malformed_rows(tmp_path, monkeypatch):
    p = tmp_path / "chapter_map.json"
    p.write_text(json.dumps({
        "ok": {"chapter_id": "physics.c11.waves", "chapter": "Waves"},
        "bad-string": "Waves",
        "bad-missing-key": {"chapter_id": "physics.c11.waves"},
        "bad-types": {"chapter_id": 3, "chapter": None}}), encoding="utf-8")
    monkeypatch.setattr(config, "CHAPTER_MAP", p)
    assert list(chapter_map.load()) == ["ok"]


def test_load_bad_json_returns_empty(tmp_path, monkeypatch):
    p = tmp_path / "chapter_map.json"
    p.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(config, "CHAPTER_MAP", p)
    assert chapter_map.load() == {}


def test_committed_map_covers_all_59_slugs_canonically():
    m = chapter_map.load()          # reads the real committed chapter_map.json
    vocab = _vocab()
    assert len(m) == 59
    for slug, entry in m.items():
        assert entry["chapter_id"] in vocab, f"{slug}: non-canonical chapter_id"
        assert entry["chapter"] == vocab[entry["chapter_id"]], f"{slug}: display-name drift"
    # The two live-proven chapters pin the crosswalk direction:
    assert m["circular-motion"]["chapter"] == "Laws of Motion"
    assert m["gauss-law"]["chapter"] == "Electric Charges and Fields"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_chapter_map.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'samagra.factory.chapter_map'`

- [ ] **Step 4: Write the loader**

```python
# samagra/factory/chapter_map.py
"""Load the git-committed textbook-slug -> combinedDBQues chapter mapping.

chapter_map.json (repo root, config.CHAPTER_MAP) is the owner-curated crosswalk
from the 59 textbook chapter slugs to the 30 canonical NCERT chapters — the same
review pattern as concept_aliases.json. Each row carries chapter_id (dotted, for
validation/coverage) + chapter (the display name /api/qsearch filters on).
PURE: no HTTP, no sqlite. Missing/invalid file -> {} (callers fall back to the
free-text query path, so a curation gap degrades quality, never safety)."""
from __future__ import annotations

import json

from .. import config


def load() -> dict[str, dict]:
    """Parse + shape-validate the committed map. Malformed rows are DROPPED
    (never raise on curation errors); a valid row is
    slug -> {"chapter_id": str, "chapter": str}."""
    try:
        raw = json.loads(config.CHAPTER_MAP.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict] = {}
    for slug, entry in raw.items():
        if (isinstance(slug, str) and isinstance(entry, dict)
                and isinstance(entry.get("chapter_id"), str)
                and isinstance(entry.get("chapter"), str)):
            out[slug] = {"chapter_id": entry["chapter_id"],
                         "chapter": entry["chapter"]}
    return out
```

- [ ] **Step 5: Write the committed `chapter_map.json`** (repo root) — the full 59-row curation. Mechanical crosswalk via the taxonomy aliases; the 6 rows marked `⚠` below were judgment calls — list them in the PR/commit body for the Chairman's eyeball:

```json
{
  "alternating-current": {"chapter_id": "physics.c12.alternating_current", "chapter": "Alternating Current"},
  "application-of-derivatives": {"chapter_id": "physics.c11.basic_maths", "chapter": "Basic Mathematics & Vectors for Physics"},
  "basic-maths-pre-calculus": {"chapter_id": "physics.c11.basic_maths", "chapter": "Basic Mathematics & Vectors for Physics"},
  "calorimetery": {"chapter_id": "physics.c11.thermal_properties_of_matter", "chapter": "Thermal Properties of Matter"},
  "capacitance": {"chapter_id": "physics.c12.electrostatic_potential_and_capacitance", "chapter": "Electrostatic Potential and Capacitance"},
  "centre-of-mass-all-in-one": {"chapter_id": "physics.c11.rotational_motion", "chapter": "System of Particles and Rotational Motion"},
  "centre-of-mass-and-momentum": {"chapter_id": "physics.c11.rotational_motion", "chapter": "System of Particles and Rotational Motion"},
  "circular-motion": {"chapter_id": "physics.c11.laws_of_motion", "chapter": "Laws of Motion"},
  "conductors": {"chapter_id": "physics.c12.electrostatic_potential_and_capacitance", "chapter": "Electrostatic Potential and Capacitance"},
  "constraints-and-spring": {"chapter_id": "physics.c11.laws_of_motion", "chapter": "Laws of Motion"},
  "current-electricity": {"chapter_id": "physics.c12.current_electricity", "chapter": "Current Electricity"},
  "damped-and-forced-oscillations": {"chapter_id": "physics.c11.oscillations", "chapter": "Oscillations"},
  "dielectrics": {"chapter_id": "physics.c12.electrostatic_potential_and_capacitance", "chapter": "Electrostatic Potential and Capacitance"},
  "differentiation": {"chapter_id": "physics.c11.basic_maths", "chapter": "Basic Mathematics & Vectors for Physics"},
  "dual-nature-of-matter-and-radiation": {"chapter_id": "physics.c12.dual_nature", "chapter": "Dual Nature of Radiation and Matter"},
  "elasticity": {"chapter_id": "physics.c11.mechanical_properties_of_solids", "chapter": "Mechanical Properties of Solids"},
  "electric-dipole": {"chapter_id": "physics.c12.electric_charges_and_fields", "chapter": "Electric Charges and Fields"},
  "electric-field": {"chapter_id": "physics.c12.electric_charges_and_fields", "chapter": "Electric Charges and Fields"},
  "electric-potential": {"chapter_id": "physics.c12.electrostatic_potential_and_capacitance", "chapter": "Electrostatic Potential and Capacitance"},
  "electrical-measuring-instruments": {"chapter_id": "physics.c12.current_electricity", "chapter": "Current Electricity"},
  "electromagnetic-waves": {"chapter_id": "physics.c12.electromagnetic_waves", "chapter": "Electromagnetic Waves"},
  "emi": {"chapter_id": "physics.c12.electromagnetic_induction", "chapter": "Electromagnetic Induction"},
  "equilibrium-stability-vertical-circle-work-power": {"chapter_id": "physics.c11.work_energy_and_power", "chapter": "Work, Energy and Power"},
  "error-analysis": {"chapter_id": "physics.c11.units_and_measurements", "chapter": "Units and Measurements"},
  "fluid-dynamics": {"chapter_id": "physics.c11.mechanical_properties_of_fluids", "chapter": "Mechanical Properties of Fluids"},
  "friction-and-torque-balancing": {"chapter_id": "physics.c11.laws_of_motion", "chapter": "Laws of Motion"},
  "gauss-law": {"chapter_id": "physics.c12.electric_charges_and_fields", "chapter": "Electric Charges and Fields"},
  "gravitation": {"chapter_id": "physics.c11.gravitation", "chapter": "Gravitation"},
  "heat-transfer": {"chapter_id": "physics.c11.thermal_properties_of_matter", "chapter": "Thermal Properties of Matter"},
  "hydrostatics": {"chapter_id": "physics.c11.mechanical_properties_of_fluids", "chapter": "Mechanical Properties of Fluids"},
  "impulse-and-collisions": {"chapter_id": "physics.c11.work_energy_and_power", "chapter": "Work, Energy and Power"},
  "inductance": {"chapter_id": "physics.c12.electromagnetic_induction", "chapter": "Electromagnetic Induction"},
  "integration": {"chapter_id": "physics.c11.basic_maths", "chapter": "Basic Mathematics & Vectors for Physics"},
  "kinematics-1-d": {"chapter_id": "physics.c11.motion_in_a_straight_line", "chapter": "Motion in a Straight Line"},
  "kinematics-2-d": {"chapter_id": "physics.c11.motion_in_a_plane", "chapter": "Motion in a Plane"},
  "kinematics-relative-motion": {"chapter_id": "physics.c11.motion_in_a_plane", "chapter": "Motion in a Plane"},
  "kinetic-theory-of-gases": {"chapter_id": "physics.c11.kinetic_theory", "chapter": "Kinetic Theory"},
  "lom-and-pseudo-force": {"chapter_id": "physics.c11.laws_of_motion", "chapter": "Laws of Motion"},
  "magnetic-field": {"chapter_id": "physics.c12.moving_charges_and_magnetism", "chapter": "Moving Charges and Magnetism"},
  "magnetic-force-and-torque": {"chapter_id": "physics.c12.moving_charges_and_magnetism", "chapter": "Moving Charges and Magnetism"},
  "rc-circuits": {"chapter_id": "physics.c12.current_electricity", "chapter": "Current Electricity"},
  "reflection-of-light": {"chapter_id": "physics.c12.ray_optics", "chapter": "Ray Optics and Optical Instruments"},
  "refraction-curved-surfaces": {"chapter_id": "physics.c12.ray_optics", "chapter": "Ray Optics and Optical Instruments"},
  "refraction-plane-surfaces": {"chapter_id": "physics.c12.ray_optics", "chapter": "Ray Optics and Optical Instruments"},
  "rotation-all-in-one": {"chapter_id": "physics.c11.rotational_motion", "chapter": "System of Particles and Rotational Motion"},
  "screw-gauge-micrometer": {"chapter_id": "physics.c11.units_and_measurements", "chapter": "Units and Measurements"},
  "shm": {"chapter_id": "physics.c11.oscillations", "chapter": "Oscillations"},
  "sound-waves": {"chapter_id": "physics.c11.waves", "chapter": "Waves"},
  "surface-tension": {"chapter_id": "physics.c11.mechanical_properties_of_fluids", "chapter": "Mechanical Properties of Fluids"},
  "temperature-and-thermometery": {"chapter_id": "physics.c11.thermal_properties_of_matter", "chapter": "Thermal Properties of Matter"},
  "thermal-expansion": {"chapter_id": "physics.c11.thermal_properties_of_matter", "chapter": "Thermal Properties of Matter"},
  "thermodynamics-first-law": {"chapter_id": "physics.c11.thermodynamics", "chapter": "Thermodynamics"},
  "thermodynamics-second-law-and-heat-engines": {"chapter_id": "physics.c11.thermodynamics", "chapter": "Thermodynamics"},
  "vectors": {"chapter_id": "physics.c11.basic_maths", "chapter": "Basic Mathematics & Vectors for Physics"},
  "vernier-calipers": {"chapter_id": "physics.c11.units_and_measurements", "chapter": "Units and Measurements"},
  "viscosity": {"chapter_id": "physics.c11.mechanical_properties_of_fluids", "chapter": "Mechanical Properties of Fluids"},
  "wave-optics": {"chapter_id": "physics.c12.wave_optics", "chapter": "Wave Optics"},
  "waves-on-a-string": {"chapter_id": "physics.c11.waves", "chapter": "Waves"},
  "work-power-and-energy": {"chapter_id": "physics.c11.work_energy_and_power", "chapter": "Work, Energy and Power"}
}
```

`⚠` judgment-call rows (state these in the commit body): `conductors` (electrostatics-of-conductors → Electrostatic Potential and Capacitance, not Electric Charges and Fields), `electrical-measuring-instruments` (meter bridge/potentiometer → Current Electricity, some content lives in Moving Charges), `friction-and-torque-balancing` (friction dominant → Laws of Motion; torque half is rotational), `impulse-and-collisions` (taxonomy alias "collisions" → Work, Energy and Power; impulse half is Laws of Motion), `kinematics-relative-motion` (→ Motion in a Plane; 1-D relative lives in Motion in a Straight Line), `rc-circuits` (transients → Current Electricity).

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_chapter_map.py -v`
Expected: 5 PASS

- [ ] **Step 7: Commit**

```bash
git add chapter_map.json samagra/factory/chapter_map.py tests/test_chapter_map.py tests/fixtures/combineddb_taxonomy.json
git commit -m "feat(rewire): 59-row chapter_map.json + pure loader (owner-curated crosswalk to the 30 NCERT chapters)"
```

Commit body: list the 6 `⚠` judgment rows for the Chairman's review.

---

### Task 3: Paper lane — chapter-scoped retrieval with fallback

**Files:**
- Modify: `samagra/factory/paper.py:122-142` (`build_paper` head), import block `samagra/factory/paper.py:25`
- Test: `tests/test_factory_paper.py`

- [ ] **Step 1: Update/add the failing tests**

REPLACE `test_build_paper_queries_qx_with_dehyphenated_slug` (`tests/test_factory_paper.py:68-73`) — the committed map now covers `circular-motion`, so the primary path is chapter-scoped:

```python
def _map(monkeypatch, tmp_path, rows):
    """Point config.CHAPTER_MAP at a throwaway map for retrieval-branch tests."""
    p = tmp_path / "chapter_map.json"
    p.write_text(json.dumps(rows), encoding="utf-8")
    monkeypatch.setattr(config, "CHAPTER_MAP", p)


def test_mapped_slug_uses_chapter_scoped_listing(export_dir, tmp_path, monkeypatch):
    _map(monkeypatch, tmp_path, {"circular-motion": {
        "chapter_id": "physics.c11.laws_of_motion", "chapter": "Laws of Motion"}})
    monkeypatch.setattr(paper, "QxClient", _FakeQx)
    res = paper.build_paper("circular-motion", variant="paper")
    assert _FakeQx.last_kw["q"] == ""                       # listing, not text query
    assert _FakeQx.last_kw["chapter"] == "Laws of Motion"   # display-name facet
    assert _FakeQx.last_kw["mode"] == "exact"
    assert res["questions"] == 2


def test_unmapped_slug_falls_back_to_dehyphenated_text_query(export_dir, tmp_path, monkeypatch):
    _map(monkeypatch, tmp_path, {})                         # empty map
    monkeypatch.setattr(paper, "QxClient", _FakeQx)
    paper.build_paper("circular-motion", variant="paper")
    assert _FakeQx.last_kw["q"] == "circular motion"
    assert "chapter" not in _FakeQx.last_kw


def test_mapped_slug_with_zero_chapter_hits_falls_back(export_dir, tmp_path, monkeypatch):
    class _EmptyThenHits(_FakeQx):
        calls = []
        def search(self, **kw):
            _EmptyThenHits.calls.append(kw)
            if kw.get("chapter"):
                return {"results": [], "total": 0, "page": 1, "page_size": 25,
                        "mode": "exact", "degraded": False, "facets": {}}
            return super().search(**kw)
    _EmptyThenHits.calls = []
    _map(monkeypatch, tmp_path, {"circular-motion": {
        "chapter_id": "physics.c11.laws_of_motion", "chapter": "Laws of Motion"}})
    monkeypatch.setattr(paper, "QxClient", _EmptyThenHits)
    res = paper.build_paper("circular-motion", variant="paper")
    assert len(_EmptyThenHits.calls) == 2                   # chapter listing, then fallback
    assert _EmptyThenHits.calls[1]["q"] == "circular motion"
    assert res["questions"] == 2


def test_artifact_json_records_chapter_and_query(export_dir, tmp_path, monkeypatch):
    _map(monkeypatch, tmp_path, {"circular-motion": {
        "chapter_id": "physics.c11.laws_of_motion", "chapter": "Laws of Motion"}})
    monkeypatch.setattr(paper, "QxClient", _FakeQx)
    paper.build_paper("circular-motion", variant="paper")
    data = _deck_json(export_dir, "circular-motion-paper.json")
    assert data["chapter"] == "Laws of Motion" and data["query"] == ""
```

Also update `test_build_paper_raises_and_writes_nothing_when_qx_unreachable` — no change needed to its body (`_DownQx.search` raises regardless of params), but confirm it still passes.

NOTE: all OTHER existing tests in this file (`_FakeQx`-based) run with the REAL committed `chapter_map.json` (no `_map` fixture) — the mapped branch fires with `chapter="Laws of Motion"`, the fake ignores params and returns results, so assertions on output artifacts hold unchanged.

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `python -m pytest tests/test_factory_paper.py -v`
Expected: the 4 new tests FAIL (`last_kw["q"] == "circular motion"` from the old single-path retrieval); old ones pass.

- [ ] **Step 3: Implement retrieval**

In `samagra/factory/paper.py`, change the import (line 25) to:

```python
from .. import config, questions_proxy
from ..clients import QxClient
from . import chapter_map
```

Add above `build_paper`:

```python
def _retrieve(slug: str, client) -> tuple[dict, dict]:
    """Chapter-scoped listing when the slug is mapped (empty q + the chapter
    display-name facet — /api/qsearch filters on the display string, verified
    live 2026-07-06); fall back to the legacy de-hyphenated text query when
    unmapped or the chapter listing returns 0 hits. Returns (payload, meta)
    where meta = {"query", "chapter"} is recorded into the artifact JSON."""
    entry = chapter_map.load().get(slug)
    if entry:
        payload = client.search(q="", mode="exact", chapter=entry["chapter"], page=1)
        if payload.get("results"):
            return payload, {"query": "", "chapter": entry["chapter"]}
    query = slug.replace("-", " ").strip()
    return client.search(q=query, mode="exact", page=1), {"query": query, "chapter": None}
```

Replace the head of `build_paper` (lines 128-135):

```python
    client = QxClient()
    try:
        payload, meta = _retrieve(slug, client)
    except Exception as exc:   # noqa: BLE001 — engine down / bad URL / timeout / bad JSON
        raise ValueError(
            f"question engine unreachable — cannot build {variant!r} for {slug!r}: {exc}. "
            f"Is combinedDBQues serving on :8790? (see its RUNBOOK; no artifact written)"
        ) from exc
```

And in the `data` dict (line 150), replace `"query": query,` with:

```python
        "slug": slug, "variant": variant, "query": meta["query"], "chapter": meta["chapter"],
```

Also update the module docstring's first paragraph (lines 2-8): QX engine → "the combinedDBQues question engine (a QX fork, :8790)"; keep the answer-free reasoning verbatim.

- [ ] **Step 4: Run the file's tests**

Run: `python -m pytest tests/test_factory_paper.py -v`
Expected: ALL PASS

- [ ] **Step 5: Run the neighbouring suites that fake QX**

Run: `python -m pytest tests/test_factory_run.py tests/test_g5_golden.py tests/test_api_questions.py -q`
Expected: PASS (their fakes ignore search params). If a fake asserts `q`, update it to accept the chapter-scoped call.

- [ ] **Step 6: Commit**

```bash
git add samagra/factory/paper.py tests/test_factory_paper.py
git commit -m "feat(rewire): paper lane retrieves by NCERT chapter facet with text-query fallback"
```

---

### Task 4: Paper lane — client-side dedupe

**Files:**
- Modify: `samagra/factory/paper.py` (new `_dedupe_results` + wiring in `build_paper`)
- Test: `tests/test_factory_paper.py`

- [ ] **Step 1: Write the failing tests**

```python
_LONG_A = ('<div class="stem">A 100 N force is applied to the centre of a rope; '
           'find the tension in the rope at its midpoint.</div>')
_LONG_B = ('<div class="stem">A block slides down a frictionless incline of angle '
           'thirty degrees; find its acceleration.</div>')


class _DupQx(_FakeQx):
    def search(self, **kw):
        return {"results": [
                    _q("q1", _LONG_A),
                    _q("q2", _LONG_A),                                  # exact dup of q1
                    _q("q3", '<div class="stem">  a 100 n force is applied to the '
                             'centre of a rope; find the tension in the rope at its '
                             'midpoint.  </div>'),                       # dup modulo ws/case
                    _q("q4", _LONG_B),
                    _q("q5", '<div class="stem">short</div>'),
                    _q("q6", '<div class="stem">short</div>'),           # short: NEVER deduped
                ],
                "total": 6, "page": 1, "page_size": 25, "mode": "exact",
                "degraded": False, "facets": {}}


def test_dedupe_drops_normalized_duplicates_keeps_order_and_shorts(export_dir, monkeypatch):
    monkeypatch.setattr(paper, "QxClient", _DupQx)
    res = paper.build_paper("circular-motion", variant="paper")
    data = _deck_json(export_dir, "circular-motion-paper.json")
    assert [q["q_uid"] for q in data["questions"]] == ["q1", "q4", "q5", "q6"]
    assert res["questions"] == 4


def test_dedupe_runs_before_the_drill_slice(export_dir, monkeypatch):
    # 12 rows where rows 0..8 are one repeated body: a post-slice dedupe would
    # leave a drill of 1 distinct + slice waste; pre-slice dedupe fills the drill
    # with 8 DISTINCT questions.
    class _NineDupsQx(_FakeQx):
        def search(self, **kw):
            rows = [_q(f"d{i}", _LONG_A) for i in range(9)]
            rows += [_q(f"u{i}", f'<div class="stem">Unique question number {i} '
                                 f'with enough length to clear the threshold.</div>')
                     for i in range(9)]
            return {"results": rows, "total": 18, "page": 1, "page_size": 25,
                    "mode": "exact", "degraded": False, "facets": {}}
    monkeypatch.setattr(paper, "QxClient", _NineDupsQx)
    paper.build_paper("circular-motion", variant="drill")
    data = _deck_json(export_dir, "circular-motion-drill.json")
    uids = [q["q_uid"] for q in data["questions"]]
    assert len(uids) == paper._DRILL_SIZE
    assert uids == ["d0", "u0", "u1", "u2", "u3", "u4", "u5", "u6"]   # 8 distinct


def test_dedupe_results_is_pure_and_deterministic():
    rows = [{"html": _LONG_A}, {"html": _LONG_A}, {"html": _LONG_B}]
    once = paper._dedupe_results(list(rows))
    twice = paper._dedupe_results(list(rows))
    assert once == twice and len(once) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_factory_paper.py -k dedupe -v`
Expected: FAIL — `AttributeError: module ... has no attribute '_dedupe_results'` / duplicate uids present.

- [ ] **Step 3: Implement**

In `samagra/factory/paper.py`, add near the top (after `_DRILL_SIZE`):

```python
import re

# combinedDBQues ships exact-dup detection (8,114 clusters) but its serve path
# does NOT collapse them and /api/qsearch carries no cluster_hash — consumers
# dedupe. Mirror their dupes.py normalization: strip tags, collapse whitespace,
# lowercase. Projections under this length are generic ("short") text their own
# threshold never treats as duplicates.
_DEDUPE_MIN_CHARS = 40
_TAG_RE = re.compile(r"<[^>]+>")


def _dedupe_results(results: list[dict]) -> list[dict]:
    """Drop rows whose normalized text projection was already seen. PURE,
    deterministic, order-preserving; runs BEFORE the drill slice so a drill is
    _DRILL_SIZE distinct questions."""
    seen: set[str] = set()
    out: list[dict] = []
    for r in results:
        proj = " ".join(_TAG_RE.sub(" ", r.get("html") or "").split()).lower()
        if len(proj) >= _DEDUPE_MIN_CHARS:
            if proj in seen:
                continue
            seen.add(proj)
        out.append(r)
    return out
```

In `build_paper`, replace `results = list(payload.get("results") or [])` with:

```python
    results = _dedupe_results(list(payload.get("results") or []))
```

(The drill slice `results = results[:_DRILL_SIZE]` stays where it is — AFTER dedupe.)

- [ ] **Step 4: Run the full paper suite**

Run: `python -m pytest tests/test_factory_paper.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add samagra/factory/paper.py tests/test_factory_paper.py
git commit -m "feat(rewire): client-side dedupe before the drill slice (combinedDBQues serves uncollapsed dup clusters)"
```

---

### Task 5: Adapter live-WAL fix + stale `:8783` string sweep

**Files:**
- Modify: `samagra/adapters/qx.py:18-19` (`_ro`), docstring
- Modify: `samagra/api/app.py:151,164`; `samagra/clients/qx_client.py:4` (docstrings/messages only)
- Test: `tests/test_adapters_qx_live.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_adapters_qx_live.py
"""Regression: adapter reads must see LIVE writes (combinedDBQues is a WAL corpus
mutated in place by their validation pipeline). immutable=1 makes sqlite ignore
the WAL and serve stale/torn reads — the adapter must open plain mode=ro."""
import sqlite3

from samagra.adapters import qx as qx_adapter


def test_ro_connection_sees_rows_committed_after_open(tmp_path):
    db = tmp_path / "live.sqlite"
    rw = sqlite3.connect(db)
    rw.execute("PRAGMA journal_mode=WAL")
    rw.execute("CREATE TABLE t (x)")
    rw.execute("INSERT INTO t VALUES (1)")
    rw.commit()

    ro = qx_adapter._ro(db)
    assert ro.execute("SELECT count(*) FROM t").fetchone()[0] == 1

    rw.execute("INSERT INTO t VALUES (2)")     # live write AFTER the ro open
    rw.commit()
    assert ro.execute("SELECT count(*) FROM t").fetchone()[0] == 2   # visible
    ro.close(); rw.close()


def test_ro_connection_refuses_writes(tmp_path):
    db = tmp_path / "live.sqlite"
    sqlite3.connect(db).execute("CREATE TABLE t (x)").connection.commit()
    ro = qx_adapter._ro(db)
    try:
        import pytest
        with pytest.raises(sqlite3.OperationalError):
            ro.execute("INSERT INTO t VALUES (9)")
    finally:
        ro.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_adapters_qx_live.py -v`
Expected: `test_ro_connection_sees_rows_committed_after_open` FAILS on the second assert (immutable connection can't see the post-open commit; count stays 1 — or the open itself errors). `test_ro_connection_refuses_writes` may already pass.

- [ ] **Step 3: Fix `_ro`**

In `samagra/adapters/qx.py`, replace lines 18-19:

```python
def _ro(path) -> sqlite3.Connection:
    # mode=ro WITHOUT immutable=1: combinedDBQues is a LIVE WAL corpus (their
    # validation pipeline writes in place). immutable=1 would make sqlite skip
    # the WAL and serve stale/torn reads; a plain ro connection attaches the WAL
    # like any reader while still refusing writes (the firewall holds).
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)
```

Update the module docstring (lines 1-7): name combinedDBQues's unified DBs; note the metadata columns live in `unified_builder.sqlite.search_index` same as before.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_adapters_qx_live.py tests/test_adapters*.py -v`
Expected: PASS (existing adapter fixture tests unaffected — plain ro reads fixture DBs fine).

- [ ] **Step 5: Sweep the stale strings**

- `samagra/api/app.py:151` comment: `gui/qx_browser.py :8783` → `combinedDBQues gui/qx_browser.py :8790`.
- `samagra/api/app.py:164` error body: `"questions backend unavailable — is the QX server running on :8783?"` → `"questions backend unavailable — is combinedDBQues serving on :8790?"`. Then: `grep -rn "8783" tests/` — update any test asserting that message text (`tests/test_api_questions.py` if it pins the string; the explicit `base_url="http://127.0.0.1:8783"` fake wiring in tests is FINE — leave it).
- `samagra/clients/qx_client.py:1-11` docstring: `:8783` → `:8790`, name combinedDBQues as the serving fork.
- Confirm `samagra/factory/paper.py` no longer says `:8783` (Task 3 already replaced its error).

- [ ] **Step 6: Full pytest**

Run: `python -m pytest -q`
Expected: green (1 standing skip).

- [ ] **Step 7: Commit**

```bash
git add samagra/adapters/qx.py samagra/api/app.py samagra/clients/qx_client.py tests/
git commit -m "fix(rewire): plain mode=ro for the live WAL corpus (drop immutable=1) + :8790 message sweep"
```

---

### Task 6: Opt-in live golden thread vs the real :8790

**Files:**
- Test: `tests/test_qx_live_smoke.py` (create)

- [ ] **Step 1: Write the opt-in live test** (mirrors `tests/test_samadhan_live_smoke.py`'s flag-gated pattern — standing gate stays offline):

```python
# tests/test_qx_live_smoke.py
"""OPT-IN live smoke: paper + drill against the REAL combinedDBQues server (:8790).

Gated on an explicit flag so the standing pytest gate never needs the sidecar:
  SAMAGRA_LIVE_QX_SMOKE=1 python -m pytest tests/test_qx_live_smoke.py -v
Writes only under a tmp EXPORT_DIR; touches no governance store.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from samagra import config
from samagra.factory import paper


def _truthy(name):
    return (os.environ.get(name) or "").strip().lower() in {"1", "true", "yes", "on"}


pytestmark = pytest.mark.skipif(
    not _truthy("SAMAGRA_LIVE_QX_SMOKE"),
    reason="opt-in live smoke: set SAMAGRA_LIVE_QX_SMOKE=1 with combinedDBQues on :8790")


@pytest.fixture
def export_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "EXPORT_DIR", tmp_path / "exports")
    return tmp_path / "exports"


def test_gauss_law_paper_and_drill_live(export_dir):
    res_paper = paper.build_paper("gauss-law", variant="paper")
    res_drill = paper.build_paper("gauss-law", variant="drill")

    # Chapter-scoped listing beats the old 2-hit text search by construction.
    assert res_paper["questions"] > 2
    assert res_drill["questions"] == paper._DRILL_SIZE

    data = json.loads(Path(res_paper["json"]).read_text(encoding="utf-8"))
    assert data["chapter"] == "Electric Charges and Fields"

    # Zero duplicate projections survive (the run-evidence bug this slice fixes).
    projs = [" ".join(paper._TAG_RE.sub(" ", q["html"] or "").split()).lower()
             for q in data["questions"]]
    long_projs = [p for p in projs if len(p) >= paper._DEDUPE_MIN_CHARS]
    assert len(long_projs) == len(set(long_projs))

    html = Path(res_paper["html"]).read_text(encoding="utf-8")
    low = html.lower()
    for marker in ('class="answer"', "answer-label", "data-answer",
                   'class="solution"', "pq-ans", "pkey"):
        assert marker not in low                       # answer-free held live
    assert "data-tex=" in html                         # KaTeX spans present
    base = config.QX_SERVER_URL.rstrip("/")
    assert 'src="/asset?' not in html                  # assets absolutized
    if "/asset?" in html:
        assert f'src="{base}/asset?' in html
```

- [ ] **Step 2: Verify the standing gate skips it**

Run: `python -m pytest tests/test_qx_live_smoke.py -v`
Expected: 1 SKIPPED (flag unset).

- [ ] **Step 3: Run it LIVE (server must be up — Task 8 makes that durable; it is currently running)**

Run (Git Bash): `SAMAGRA_LIVE_QX_SMOKE=1 python -m pytest tests/test_qx_live_smoke.py -v`
Expected: 1 PASS. Record the question counts + wall time in the commit body (latency evidence).

- [ ] **Step 4: Commit**

```bash
git add tests/test_qx_live_smoke.py
git commit -m "test(rewire): opt-in live golden — chapter-scoped, deduped, answer-free paper+drill vs :8790"
```

---

### Task 7: Docs — `.env.example`, `docs/deploy-tunnel.md`, LAN demo mode

**Files:**
- Modify: `.env.example` (QX sidecar block), `docs/deploy-tunnel.md` (QX sidecar section)

- [ ] **Step 1: Replace the `.env.example` QX block** (currently the two commented `SAMAGRA_QX_SERVER_URL`/`ALLOWED_HOSTS` lines) with:

```dotenv
# --- Question bank: combinedDBQues sidecar (Slice R) ---
# The unified physics corpus (48,589 q, 30 NCERT chapters) serving GET /api/qsearch
# on :8790 — start via the COMBINEDDB-QX logon task or:
#   cd C:\SandBox\claude_khanak_box\combinedDBQues\app && set PORT=8790 && python -X utf8 gui\qx_browser.py
# SAMAGRA_COMBINED_DB_ROOT=C:\SandBox\claude_khanak_box\combinedDBQues
# SAMAGRA_QX_SERVER_URL=http://127.0.0.1:8790
# SAMAGRA_QX_SERVER_ALLOWED_HOSTS=
# ROLLBACK to the old QX engine (three lines):
# SAMAGRA_QX_SERVER_URL=http://127.0.0.1:8783
# SAMAGRA_QX_BUILDER_DB=C:\SandBox\gpt_box\gpt-extract-ques\qx\builder.sqlite
# SAMAGRA_QX_CONTENT_DB=C:\SandBox\gpt_box\gpt-extract-ques\qx\qx_content.sqlite

# --- LAN demo mode (Chairman ruling 2026-07-06: local-only, WiFi demos) ---
# DEMO, not a deploy. Bind to the LAN + allow plain-http student cookies, then
# open Windows firewall for 8799 once (admin):
#   netsh advfirewall firewall add rule name="SAMAGRA LAN demo" dir=in action=allow protocol=TCP localport=8799
# The origin gate keeps ALL mutating routes loopback-only regardless — LAN
# devices get the read surfaces + /learn student login, never the operator surface.
# SAMAGRA_HOST=0.0.0.0
# SAMAGRA_PRATHAM_COOKIE_SECURE=0
```

- [ ] **Step 2: Rewrite the QX-sidecar section of `docs/deploy-tunnel.md`** — read the current section first (`grep -n "8783\|qsearch\|QX" docs/deploy-tunnel.md`), then update it to: combinedDBQues on :8790 as the question sidecar, the `COMBINEDDB-QX` logon task, the rollback lines above, and a short "LAN demo mode" subsection with the same three-line recipe + the note that the origin gate fail-closes mutating routes for non-loopback callers (so demo exposure ≠ operator exposure). Keep the old-QX mention as a one-line "legacy engine (:8783, retired from defaults 2026-07-06)".

- [ ] **Step 3: Commit**

```bash
git add .env.example docs/deploy-tunnel.md
git commit -m "docs(rewire): combinedDBQues sidecar + rollback lines + LAN demo mode"
```

---

### Task 8: Ops — durable `COMBINEDDB-QX` logon task

Not a repo change (record the outcome in HANDOFF at Task 12). The server is already running on :8790 today; this makes it survive reboots — **do this task before the reboot-dependent verification, and note it explicitly since a reboot is planned right after this plan lands.**

- [ ] **Step 1: Inspect the existing pattern**

Run: `schtasks /query /tn "QX Autostart" /xml`
Expected: the old task's XML (working dir + command shape to mirror).

- [ ] **Step 2: Create the task**

```powershell
schtasks /create /tn "COMBINEDDB-QX" /sc onlogon /f /tr "cmd /c \"cd /d C:\SandBox\claude_khanak_box\combinedDBQues\app && set PORT=8790&& python -X utf8 gui\qx_browser.py\""
```

Expected: `SUCCESS: The scheduled task "COMBINEDDB-QX" has successfully been created.`
(If the `QX Autostart` XML shows a different working pattern — e.g. a wrapper script — mirror that instead.)

- [ ] **Step 3: Verify without killing the running server**

If :8790 already answers (`curl -s -m 10 http://127.0.0.1:8790/` → 200), do NOT `schtasks /run` (a second instance would fight the port). Verification after the next reboot: `curl` :8790 → 200. Note this pending check in HANDOFF.

---

### Task 9: Coverage graph rebuild + alias re-curation (owner-CLI, live)

**Files:**
- Modify: `concept_aliases.json` (re-curated against the 128 new concept labels)

- [ ] **Step 1: Rebuild the coverage graph against `unified_builder.sqlite`**

Run: `python -m samagra factory coverage-build`
Expected: completes; prints counts (concepts should be **128**, up from 86; edges/cells/gaps grow) + the residual no-pointer concepts BY NAME. Save that residual list.

(If the CLI entry point differs, the G5-era invocation was `samagra factory coverage-build` — use whichever form `python -m samagra --help` shows.)

- [ ] **Step 2: Re-curate `concept_aliases.json`**

Against the NEW 128 labels: (a) verify the existing `lom-and-pseudo-force` → "newton's laws" alias still matches a real concept label (`python -c "import sqlite3; con=sqlite3.connect(r'file:C:/SandBox/claude_khanak_box/combinedDBQues/app/qx/unified_builder.sqlite?mode=ro', uri=True); print([r[0] for r in con.execute(\"select label from concept where chapter_id like 'physics.%' and label like '%newton%'\")])"`); (b) add `by_chapter` add-rows for each residual no-pointer concept from Step 1 that plausibly belongs to one of the 59 textbook chapters (this closes the old polarisation/radioactivity/transistors residue against the new corpus's actual labels — curate against reality, not the old list). Drop aliases that no longer match any label.

- [ ] **Step 3: Rebuild again and confirm the residual shrank**

Run: `python -m samagra factory coverage-build`
Expected: residual no-pointer list shorter than Step 1's; note final counts.

- [ ] **Step 4: Commit**

```bash
git add concept_aliases.json
git commit -m "feat(rewire): concept_aliases re-curated against the 128-concept unified spine"
```

Commit body: before/after counts (concepts/edges/cells/gaps + residual names).

---

### Task 10: Full gates

- [ ] **Step 1: Backend**

Run: `python -m pytest -q`
Expected: green; skips = 2 opt-in live smokes (LLM + QX). Count should be ≈ 667 baseline + ~20 new.

- [ ] **Step 2: Frontend (unchanged this slice, still gated)**

Run: `cd frontend && npx vitest run && npx tsc --noEmit && npm run build`
Expected: 639 vitest green (75 files), tsc clean, build green.

- [ ] **Step 3: Commit anything the gates surfaced; otherwise no-op.**

---

### Task 11: Review gate (house convention — firewall-seam slice)

- [ ] **Step 1: Dedicated Codex pre-merge review** of the full branch diff (DEC-7-style, the QX-seam firewall focus): read-only invariant on combinedDBQues (HTTP + mode=ro only, no write), answer-leak guard integrity, retrieval fallback correctness, dedupe purity, config rollback honesty. Report → `docs/codex-reviews/31-combineddbques-rewire-premerge.report.md`.
- [ ] **Step 2: 4-lens adversarial final review** (Workflow: firewall / spec-fidelity / correctness / security lenses × independent refute-verify), per the G-phase pattern.
- [ ] **Step 3: Remediate any findings TDD** (failing test first, then fix, then re-verify), commit per finding.
- [ ] **Step 4: Re-run Task 10 gates after remediation.**

---

### Task 12: Trackers, DEC-15, merge, push

- [ ] **Step 1: Spec sync** — flip the spec's Status to reflect the Chairman's 2026-07-06 approval ("slice r spec approved... auto approve and execute"); append the §12 verification results (this plan's header) + deltas D1-D3; record **DEC-15 RATIFIED** on that standing approval, with the review-gate outcome noted (the DEC-14 precedent: ratification recorded in a dedicated commit at the merge gate).
- [ ] **Step 2: Tracker sweep** — `HANDOFF.md` (new top banner: Slice R shipped; COMBINEDDB-QX task created, post-reboot :8790 check pending), `CLAUDE.md` project notes (new ✅ block), `STATUS.html` + `SUMMARY.html` (per the status-pointer-files convention), memory file + `MEMORY.md` index.
- [ ] **Step 3: Merge + push** (serialized, no background git):

```bash
git checkout main
git merge --ff-only feature/combineddbques-rewire
git push origin main
```

Expected: fast-forward; push accepted. **Verify the branch ref is at the true HEAD before merging** (the D1 detached-HEAD lesson): `git log --oneline -1 feature/combineddbques-rewire` matches the last commit made.

- [ ] **Step 4: Restart the samagra server** (owner/ops) so the new config loads; then one GUI Factory-run spot check on a NEWLY-mapped chapter (e.g. `plan textbook:kinematics-1-d` → build paper) to confirm chapter-scoped retrieval end-to-end in prod posture.

---

## Out of scope (unchanged from spec §13)

Phase F (image-gen figures first, then slides — Chairman-ruled order); LLM provider slice (OpenAI `gpt-5.5` medium-effort for samadhan — Chairman has already added the key + `SAMAGRA_LLM_PROVIDER=openai`/`SAMAGRA_LLM_MODEL=gpt-5.5`/`SAMAGRA_LLM_EFFORT=medium` lines to `.env`; `llm_client.py` adjusts in its own mini-slice with a DEC-7-style review addendum); dedupe-at-source; `/learn` public deploy; old QX server/repo changes.
