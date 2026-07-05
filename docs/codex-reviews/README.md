# Codex / adversarial review index

Dedicated pre-merge and audit reviews of SAMAGRA, in chronological order. Convention
going forward: each numbered review saves `NN-<slug>.report.md` (the findings +
verdict) and, when a CLI session log exists, a companion `NN-<slug>.run.log`.
Verdicts: **GO** / **GO-WITH-CAVEATS** (ship after the caveats are closed) / **NO-GO**
(remediate + re-review) / APPROVE / REQUEST-CHANGES / BLOCK (early naming).

| # | Subject | Verdict |
|---|---------|---------|
| 01 | Baseline adversarial security audit (5 HIGH: unauth mutating routes, gate bypass, HTML injection, /open exposure, path traversal) | findings-only |
| 02 | Vision / architecture soundness | advisory |
| 03 | Phase-1 loop planning (CEO/Khanak) | planning doc |
| 04–06 | Lock discipline pre-merge (stale-reclaim race → atomic O_CREAT excl lock) | BLOCK → REQUEST-CHANGES → APPROVE-WITH-NITS |
| 07–11 | Phase-2 pre-commit governance hook (never-wedge / fail-open chain) | REQUEST-CHANGES ×5 |
| 12 | Workflow invariant audit (CEO-run, 7 agents; INV-1 downgrade counterexample found + fixed) | 1 confirmed, fixed |
| 13 | Phase-2 hook final confirm | APPROVE-WITH-NITS |
| 14–18 | Capture control plane slices (munshi capture, mcd seeds, sims, QX facets, live-read passthroughs) | GO / GO-WITH-FIXES |
| 19–21 | Whole-codebase doc-claim audit (Codex static + 51-agent dynamic + consolidation) | 16 confirmed findings |
| 22–23 | Phase 3 bridge — the first prod-write boundary | NO-GO → GO-WITH-CAVEATS |
| 24–25 | Content factory Phase 1 dispatch spine (gdocs-upload reachability HIGH) | NO-GO → GO-WITH-CAVEATS → GO |
| 26 | Phase C3 seed-fold — the ONE assignment-driven mcd write | GO-WITH-CAVEATS → closed |
| 27 | Whole-codebase adversarial bug hunt (post-G1; 7 Codex dims × Claude refute-verify) | 0 HIGH / 3 MED / 12 LOW |
| 28 | Phase G3 identity + publish-write boundaries (DEC-7 pre-merge) | GO-WITH-CAVEATS → both caveats fixed TDD → effectively GO |
| 29 | Phase G4 adaptive-twin pre-merge (student progress write + `/learn/next` recommender) | GO-WITH-CAVEATS: 0 findings, all 6 DEC-13 invariants PASS; caveat = sandbox couldn't execute pytest (test-gap closed post-review) |

The Phase D2 LLM generation boundary review (NO-GO → GO) is recorded in the D2 plan
(`docs/superpowers/plans/2026-06-25-samagra-content-factory-phase-d2-samadhan.md`)
rather than as a numbered report. Unnumbered companions: `12-workflow-invariant-audit.md`,
`21-consolidated-critical-review.md`, `PHASE1-loop-runbook.md`, `SAMAGRA-review-briefing.html`,
`_prompts/`.
