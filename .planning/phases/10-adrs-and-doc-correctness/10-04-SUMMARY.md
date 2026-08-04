---
phase: 10-adrs-and-doc-correctness
plan: 04
subsystem: docs
tags: [documentation, adr, correctness, pricing, memory-backends, cross-linking]

# Dependency graph
requires:
  - "Plans 10-01 and 10-02 — the five ADR files whose exact slugs this plan links to; a mismatch would have shipped dangling links"
  - "src/research_agent/memory.py:432-435 — the BACKENDS registry, the ground truth for the backend count"
  - "src/research_agent/usage.py:63,67 — until=date(2026, 8, 31) and since=date(2026, 9, 1), the boundaries the prose must match"
provides:
  - "docs/DESIGN.md § Memory — a backend count that matches the code (four, including pgvector)"
  - "docs/DESIGN.md § Cost — a pricing paragraph dated in ISO form, with /pricing named as the live source"
  - "docs/DESIGN.md — forward-links from all five promoted passages to ADR-0001…0005, plus an adr/README.md pointer in the preamble"
  - "SC-2 (bidirectional ADR traceability), SC-4 (four backends) and the DESIGN half of SC-6"
affects: [10-05 verifies these gates phase-wide; Phases 12/16/17 supersede records that DESIGN.md now points at by number]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Forward-links carry the record number and the path together, so a supersession notice quoting ADR-000N is findable from the prose"
    - "Every extracted link path is resolved with test -f before the gate passes, so a slug mismatch fails loudly instead of shipping a dangling link"
    - "Dated claims use ISO dates that match a code constant, never wording relative to the writing date"
key-files:
  created:
    - .planning/phases/10-adrs-and-doc-correctness/10-04-SUMMARY.md
  modified:
    - docs/DESIGN.md

key-decisions:
  - "ADR-0006 is deliberately NOT linked from docs/DESIGN.md. Records 0001-0005 carry **Promoted from:** lines naming the DESIGN passage they came from; ADR-0006 originates in the Phase 10.5 hotfix and carries **Source:** instead. Linking it from DESIGN.md would assert a provenance that does not exist, and would break the 000[1-5] gates that 10-01 established."
  - "The link text carries both the number and the path — `Recorded as [ADR-000N](adr/000N-slug.md)` — rather than linking the record title. Supersession notices reference records by number, so the number is what a reader needs to see in the prose."
  - "\"because one of them expires this month\" became \"because one of them is time-boxed\", not a refreshed relative date. Any wording anchored to a writing date decays the same way; the two ISO dates carry the fact and the clause now dates itself."
  - "The pricing sentence keeps both rates on one line by construction, because the SC-6 gate is line-scoped: a line quoting $2/$10 must also quote $3/$15. Splitting the windows into two sentences on two lines would have failed the gate correctly."
  - "The 'A test asserts the graph never reaches past those four methods' sentence was left byte-identical. It counts the four ABC methods (add/query/len/describe), not backends; the paragraph now legitimately contains both 'four implementations' and 'those four methods' and both are true."
  - "No un-promoted decision gained a link. DEC-03, DEC-05, DEC-10, DEC-15 and DEC-20 stay as narrative — a link to a record that does not exist is worse than no link."

patterns-established:
  - "Each of the three gates was probed for non-vacuity before its commit: the backend gate was run against the pre-edit text (rejected), the SC-6 gate against a scratch file quoting the introductory rate alone (caught it), and the link resolver against a fabricated 0009-nope.md path (failed as required). This repo has shipped four vacuous gates; a gate that passes first try is now assumed broken until it has been shown to fail."

requirements-completed: []  # REQ-adr-promotion is phase-scoped; 10-05 closes it

# Metrics
duration-minutes: 8
completed: 2026-08-05
tasks-completed: 3
files-changed: 1
---

# Phase 10 Plan 04: docs/DESIGN.md corrections and ADR forward-links Summary

Corrected the two false claims left in `docs/DESIGN.md` — three backends where there are four, and a rate change written as "September 1, this month" — and closed the ADR loop by pointing each of the five promoted passages at the record that now holds it.

## What Was Built

**Task 1 — four `MemoryStore` implementations** (commit `49056e5`)

The seams paragraph in § Memory said the `MemoryStore` ABC had "three implementations behind a `VECTOR_STORE` env var: JSON (default), in-memory, and Chroma". `BACKENDS` in `src/research_agent/memory.py:432-435` registers four — `json`, `memory`, `chroma`, `pgvector` — and pgvector has been there since Phase 8. `docs/OPERATIONS.md:168` has said "four backends" all along, so the two documents disagreed. The clause now reads "four implementations … JSON (default), in-memory, Chroma, and pgvector", on the same line, with the rest of the paragraph untouched.

The trap the plan flagged held: the paragraph's closing sentence, "A test asserts the graph never reaches past those four methods", counts the four ABC methods and not the backends. It was not renumbered or merged. The paragraph now contains "four implementations" and "those four methods" and both are correct.

**Task 2 — the rate change stated as `2026-09-01`** (commit `7d6617e`)

The § Cost pricing paragraph opened "because one of them expires this month" — true when written, false the moment the month turned — and ended its window sentence with "moves to $3/$15 on September 1", a prose date with no year. Both are gone. The paragraph now opens "because one of them is time-boxed" and reads: introductory $2/$10 per MTok through `2026-08-31`, the standard $3/$15 rate from `2026-09-01`. Both figures and both ISO dates sit on the one line, which is what the line-scoped SC-6 gate requires, and `/pricing` stays named as the source for what accounting is using today. The dates match `usage.py`'s `until=date(2026, 8, 31)` / `since=date(2026, 9, 1)` exactly. The neighbouring unpriced-model and metrics-denominator paragraphs were not touched.

**Task 3 — forward-links to the five records** (commit `c0d3450`)

Each promoted paragraph now ends with a trailing `Recorded as [ADR-000N](adr/000N-slug.md).`:

| Passage | Section | Record |
|---|---|---|
| "Routing is a state machine, not a prompt" | The graph | ADR-0001 |
| "The critic is a separate node with its own rubric" | The graph | ADR-0002 |
| "Follow-ups reuse the critic instead of bypassing it" | The graph | ADR-0003 |
| "Sessions store completed runs, not mid-run checkpoints" | Data and backends | ADR-0004 |
| "The judge runs on a different, stronger model than the pipeline" | Testing | ADR-0005 |

The preamble gained three lines after the README pointer, linking `adr/README.md` and saying what the split is for: the prose is the argument, the records are what a later reversal has to supersede explicitly. That gives a reader arriving at DESIGN.md the directory rather than five links scattered across five sections.

ADR-0006 is not mentioned. No un-promoted paragraph gained a link.

## Deviations from Plan

None — plan executed as written. No deviation rule fired; nothing outside `docs/DESIGN.md` was touched.

## Verification

| Gate | Result |
|---|---|
| `grep -c 'three implementations' docs/DESIGN.md` | 0 |
| `grep -c 'four implementations' docs/DESIGN.md` | 1 |
| `grep 'four implementations' docs/DESIGN.md \| grep -c 'pgvector'` / `'Chroma'` | 1 / 1 |
| `grep -c 'those four methods' docs/DESIGN.md` (ABC sentence survives) | 1 |
| `grep -c 'September 1'` / `'expires this month'` | 0 / 0 |
| `grep -c '2026-08-31'` / `'2026-09-01'` in DESIGN.md | 1 / 1 |
| `grep '2026-09-01' docs/DESIGN.md \| grep -c '/pricing'` | 1 |
| `grep -c 'pricing_unknown' docs/DESIGN.md` (neighbour survives) | 1 |
| **SC-6 cross-doc:** `grep -rn '2/\$10' docs README.md \| grep -v '3/\$15' \| wc -l` | 0 |
| `grep -o 'adr/000[1-5]-[a-z0-9-]*\.md' docs/DESIGN.md \| sort -u \| wc -l` | 5 |
| Every linked path resolves under `docs/` (`test -f`) | no output — clean |
| `grep -c 'adr/README.md'` / `grep -c 'ADR-000'` | 1 / 5 |
| `grep -c 'adr/0006' docs/DESIGN.md` (must stay 0) | 0 |
| **Reverse:** `grep -L 'DESIGN.md' docs/adr/000[1-5]-*.md \| wc -l` | 0 |
| `git diff --name-only HEAD~3 HEAD` | `docs/DESIGN.md` only |
| Deletions in the three commits | none |
| `.venv/bin/pytest` (bare, so `-q` is not doubled) | **388 passed, 28 skipped** |
| `.venv/bin/ruff check .` | All checks passed |
| `git status --porcelain src/ tests/ evals/ \| wc -l` | 0 |

**Non-vacuity probes.** All three gates were shown capable of failing:

| Gate | Probe | Outcome |
|---|---|---|
| Backend count | Run against a scratch file holding the verbatim pre-edit clause | Rejected — gate is not vacuous |
| SC-6 line-scoped rate | Scratch file containing `$2/$10` and no `$3/$15` | Caught — `wc -l` returned non-zero |
| Link resolver | Path list with a fabricated `adr/0009-nope.md` appended | Failed as required |

## Threat Register Outcome

| ID | Disposition | Outcome |
|---|---|---|
| T-10-13 | mitigated | All five extracted paths resolved with `test -f "docs/$f"`; the resolver was probed with a fabricated slug and failed correctly |
| T-10-14 | mitigated | `those four methods` still returns 1; the ABC sentence is byte-identical in the diff |
| T-10-15 | mitigated | Both stale phrases gated to zero; replacements are ISO dates matching `usage.py`'s window boundaries |
| T-10-16 | mitigated | The SC-6 gate names `docs README.md` as its roots and counts with `wc -l`, so BSD grep's missing `./` prefix cannot make it vacuous — and it was proven to catch a lone rate |
| T-10-17 | mitigated | Five un-promoted decisions (DEC-03, 05, 10, 15, 20) gained no links; `grep -c 'ADR-000'` is exactly 5, not more |
| T-10-SC | accepted | Nothing installed; documentation only |

## Known Stubs

None.

## Threat Flags

None — no network, auth, file-access or schema surface touched. Documentation only.

## For Next Phase

- **Phase 10's corrective work is complete.** SC-1 through SC-4 and SC-6 have all landed across plans 10-01…10-04. Plan 10-05 is verification plus the SC-5 live re-check, which the CONTEXT notes is already satisfied by the Fly v4 cutover and needs re-verifying, not redeploying.
- **ROADMAP still shows Phase 10.5 as `4/5` In Progress** although it completed and shipped as release v4. Left alone deliberately, as 10-03 also noted; 10-05 reconciles it.
- **`docs/DESIGN.md` is now a two-way index into `docs/adr/`.** Renaming any ADR file requires updating both the index rows in `docs/adr/README.md` and the five links here. The dangling-link check is in STATE.md's carry-forward section.
- **`grep -c 'ADR-000'` returning exactly 5 is a meaningful invariant, not a coincidence.** It is 5 because exactly five records were promoted from this file. A future phase promoting a sixth DESIGN passage raises it; a phase linking ADR-0006 from here would raise it wrongly.

## Self-Check: PASSED

`docs/DESIGN.md` and this SUMMARY exist on disk. All three task commits resolve in `git log`: `49056e5`, `7d6617e`, `c0d3450`.
