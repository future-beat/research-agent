---
phase: 10-adrs-and-doc-correctness
plan: 01
subsystem: docs
tags: [adr, nygard, supersession, documentation]

# Dependency graph
requires: []
provides:
  - "docs/adr/ — the ADR directory, created by this plan"
  - "The Nygard section contract every record in the phase follows"
  - "A verbatim supersession convention, greppable via 'Superseded by ADR-'"
  - "The six-row index, including the two expected reversals and the ADR-0006 origin note"
  - "ADR-0001 — deterministic Python routing (DEC-01)"
  - "ADR-0002 — separate critic node, notes as sole source of truth (DEC-02)"
affects: [10-02 records 0003-0006, 10-04 DESIGN.md forward-links, phase-16 supersedes 0005, phase-17 supersedes 0003, phase-12 supersedes 0006]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Nygard ADR: Title, Status, provenance line, Context/Decision/Consequences"
    - "Supersession by status-line edit only — a superseded record's body is never rewritten"
key-files:
  created:
    - docs/adr/README.md
    - docs/adr/0001-deterministic-python-routing.md
    - docs/adr/0002-separate-critic-node.md
  modified: []

key-decisions:
  - "Provenance is a two-form contract, not one: '**Promoted from:**' for the five DESIGN.md promotions, '**Source:**' for ADR-0006 which has no DESIGN.md passage. The index says so in prose so a reader does not hunt for a passage that never existed."
  - "The supersession convention is written as three numbered imperative steps a future phase can follow verbatim, including the explicit prohibition on editing a superseded record's Context/Decision/Consequences."
  - "Expected supersessions (Phase 16 -> 0005, Phase 17 -> 0003, Phase 12 -> 0006) are carried in the index as italicised forecasts, with a sentence stating nothing is superseded today. Everything is Accepted."
  - "Consequences split into '### Accepted' / '### Rejected alternative' (planner's discretion), with a third '### Known limit' subsection in ADR-0002 to carry the shared-model caveat and hand the model-independence argument to ADR-0005."
  - "ADR-0001 deliberately omits bounded loops (DEC-03) — it is not promoted in this phase and must not read as a decision of record."

patterns-established:
  - "Every phase-10 grep gate is scoped to docs/ or a named file and piped to wc -l, never 'grep -rn . | grep -v ^./' — the BSD-grep vacuous-pass trap this repo has hit three times"

requirements-completed: []  # REQ-adr-promotion is phase-scoped; plans 10-02/03/04/05 complete it

# Metrics
duration: 12min
completed: 2026-08-04
---

# Phase 10 Plan 01: ADR directory, index, and the first two records Summary

Created `docs/adr/` with a Nygard section contract, a supersession convention a later phase
can follow verbatim, a six-row index, and the first two promoted records — DEC-01
(deterministic Python routing) and DEC-02 (separate critic node).

## What was built

**`docs/adr/README.md`** carries four things: what the directory is (numbered,
status-bearing promotions of `docs/DESIGN.md`, which stays as the readable argument); the
record shape (zero-padded `NNNN-slug.md`, a `**Status:**` line, a provenance line, and
`## Context` / `## Decision` / `## Consequences` in that order); the supersession convention;
and the index.

The convention is the load-bearing part, because Phases 12, 16 and 17 have to execute it
without inventing anything. It is three numbered steps: the overturned record's status line
becomes `**Status:** Superseded by ADR-000N (Phase NN)`, the new record's reads
`**Status:** Accepted — supersedes ADR-000M`, and both index rows update. It then states
plainly that a superseded record's Context, Decision and Consequences are **never** edited —
the record stays as written, including claims that stopped being true, because that is the
point of keeping it.

The index lists all six filenames the phase will produce, including 0003–0006 which plan
10-02 writes in the same wave. Records 0001–0005 are DESIGN.md promotions; ADR-0006
originates in the Phase 10.5 hotfix, carries `**Source:**` rather than `**Promoted from:**`,
and the index says so in prose beneath the table.

**ADR-0001** records that `supervisor_node` is a chain of `if` statements over `AgentState`
with no model call deciding the next hop, cites `docs/DESIGN.md` § The graph and DEC-01,
and names the rejected LLM-router alternative — flexibility traded away for reproducibility
and offline testability the pipeline actually needs.

**ADR-0002** records that drafting and grounding-checking are separate calls with the
research notes as the critic's sole source of truth, cites DEC-02, and rejects
single-call self-assessment ("reliably produces 'looks good to me'"). Its `### Known limit`
subsection states that the critic is independent in *rubric* but not in *model* and points
at ADR-0005 rather than arguing model independence here. Nothing pre-empts Phase 16's
reversal — the record is `Accepted` as written.

## Task-by-task

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | ADR index, section contract, supersession convention | `f4411bc` | `docs/adr/README.md` |
| 2 | ADR-0001 — deterministic Python routing | `cfc0e6c` | `docs/adr/0001-deterministic-python-routing.md` |
| 3 | ADR-0002 — separate critic node | `715407e` | `docs/adr/0002-separate-critic-node.md` |

## Verification

All three task gates printed `GATE_OK`. Plan-level verification from the repo root:

| Check | Result |
|-------|--------|
| `ls docs/adr/` | `README.md`, `0001-…`, `0002-…` |
| Nygard headings in `docs/adr/000[12]*.md` | printed nothing (all present) |
| `grep -L '^\*\*Status:\*\* Accepted' docs/adr/000[12]*.md \| wc -l` | 0 |
| `grep -c 'Superseded by ADR-' docs/adr/README.md` | ≥ 1 |
| `grep -o '000[1-5]-[a-z0-9-]*\.md' README.md \| sort -u \| wc -l` | 5 |
| `git status --porcelain src/ tests/ evals/ \| wc -l` | 0 |
| `git diff --quiet 715e9aa -- src/` | exit 0 |
| `.venv/bin/pytest` (bare) | **388 passed, 28 skipped** — baseline unchanged |
| `.venv/bin/ruff check .` | All checks passed |

**Anti-vacuity check.** The filename gate was sanity-checked so it can fail: widening the
pattern to `000[1-6]` returns six distinct names, confirming the `000[1-5]` gate is
discriminating and not matching an empty set. Every gate in this plan is scoped to `docs/`
or a named file, so the BSD-grep `^./` exclusion trap does not apply.

## Deviations from Plan

None — plan executed exactly as written. No Rule 1/2/3 auto-fixes were needed, and no
architectural question arose. No package was installed.

## Threat register

| Threat | Disposition | How this plan discharged it |
|--------|-------------|------------------------------|
| T-10-01 supersession convention unusable | mitigated | Written as three verbatim steps with the literal token `Superseded by ADR-`; both expected reversals pre-named from the ROADMAP register |
| T-10-02 ADR provenance repudiable | mitigated | Both records carry `**Promoted from:**` naming the DESIGN.md section and the DEC id; gated by `grep 'DESIGN.md'` and `grep 'DEC-0N'` |
| T-10-03 ADR asserts untested `src/` behaviour | mitigated | Both records written only from `.planning/intel/decisions.md` and the cited DESIGN.md lines; no new claim about `src/` introduced |
| T-10-04 vacuous grep gate | mitigated | Every gate scoped and piped to `wc -l`; filename gate explicitly probed for falsifiability |
| T-10-SC package installs | accepted | Nothing installed — documentation only |

No new threat flags. This plan adds no network surface, no auth path, and no schema.

## Known Stubs

None. Every file this plan created is complete as written. The four filenames referenced in
the index that do not yet exist on disk (`0003`–`0006`) are plan 10-02's deliverables in the
same wave, not stubs — the index is the shared contract both plans were written against, and
10-02 is explicitly instructed not to modify it.

## For the next plan

- **10-02 must not touch `docs/adr/README.md`.** The index already carries its four rows,
  with the titles and expected superseders it should match.
- The provenance line for 0003–0005 is `**Promoted from:**`; for 0006 it is `**Source:**`,
  and `grep -c 'Promoted from' docs/adr/0006-*.md` must return 0 per VALIDATION.
- The section contract to match is the one in the index: `**Status:** Accepted`, a
  provenance line, then `## Context` / `## Decision` / `## Consequences` as `##` headings in
  that order.
- **10-04** adds the DESIGN.md forward-links; ADR-0002 already links forward to ADR-0005, so
  that path must resolve once 10-02 lands.

## Self-Check: PASSED

- `docs/adr/README.md` — FOUND
- `docs/adr/0001-deterministic-python-routing.md` — FOUND
- `docs/adr/0002-separate-critic-node.md` — FOUND
- Commit `f4411bc` — FOUND
- Commit `cfc0e6c` — FOUND
- Commit `715407e` — FOUND
