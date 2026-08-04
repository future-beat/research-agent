---
phase: 10-adrs-and-doc-correctness
plan: 02
subsystem: docs
tags: [adr, nygard, supersession, auth, documentation]

# Dependency graph
requires:
  - "docs/adr/README.md — the Nygard section contract and index (plan 10-01)"
  - "ADR-0002 — the shared-model known limit that ADR-0005 links back to"
provides:
  - "ADR-0003 — follow-ups reuse the critic; no prior notes stops with no_prior_research (DEC-04)"
  - "ADR-0004 — sessions persist completed runs in SQLite, not LangGraph's checkpointer (DEC-14)"
  - "ADR-0005 — the eval judge runs on Opus 5 against a Sonnet 5 pipeline (DEC-22)"
  - "ADR-0006 — a separate, fail-closed SESSIONS_TOKEN, and the DEMO_TOKEN production footgun (Phase 10.5)"
  - "The complete six-record set the index promised — every filename in docs/adr/README.md now resolves"
affects: [10-04 DESIGN.md forward-links, phase-12 supersedes 0006, phase-16 supersedes 0005, phase-17 supersedes 0003]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Nygard ADR with a two-form provenance line: '**Promoted from:**' for DESIGN.md promotions, '**Source:**' for records with no DESIGN.md passage"
    - "Expected reversals carried as a '### Expected reversal' subsection under Consequences — named, dated to a phase, and explicitly not applied"
key-files:
  created:
    - docs/adr/0003-followups-reuse-critic-no-prior-research.md
    - docs/adr/0004-sessions-in-sqlite-not-langgraph-checkpointer.md
    - docs/adr/0005-opus-5-eval-judge.md
    - docs/adr/0006-separate-sessions-token-fails-closed.md
  modified: []

key-decisions:
  - "Each of the three records with a named future reversal carries a '### Expected reversal' subsection rather than a passing mention. It states which phase, which requirement, what specifically breaks — ADR-0005's is the sharpest: Phase 16 removes this record's *premise*, so the judge rationale must be re-derived rather than inherited."
  - "ADR-0005 quotes model identifiers verbatim from the code (JUDGE_MODEL/EVAL_JUDGE_MODEL in evals/graders.py:28, MODEL in graph.py:38) and both were re-read against the source before commit — the record cannot drift from the code by transcription error."
  - "ADR-0006 leads its Consequences with a dedicated '### DEMO_TOKEN must never be set in production' heading rather than a bullet. The record exists for that one consequence; burying it in a list would defeat the purpose."
  - "ADR-0006 states all four decision parts with their individual reasons, because the parts are separable and a future refactor is most likely to pick off just one (apply guard to the reads, or make the credential open-when-unset) without seeing the others."
  - "ADR-0004 stays strictly inside DEC-14 — Postgres appears only as 'the same schema under a different backend'. DEC-15 (one DATABASE_URL moves all three stores) is not promoted and is verifiably absent (grep -c 'DEC-15' returns 0)."

patterns-established:
  - "Every grep gate in this plan was probed for falsifiability against a file that should NOT match, so a passing gate proves a property rather than an empty set"

requirements-completed: []  # REQ-adr-promotion is phase-scoped; 10-03/04/05 remain

# Metrics
duration: 14min
completed: 2026-08-05
---

# Phase 10 Plan 02: Records 0003–0006 Summary

Wrote the four remaining ADRs — the three `docs/DESIGN.md` promotions (DEC-04, DEC-14,
DEC-22) and the one record that originates in the Phase 10.5 hotfix. `docs/adr/` is now the
complete six-record set its index promised.

## What was built

**ADR-0003 (DEC-04)** records that the responder writes into the same `draft` field the
writer does, so the critic grades a follow-up with the same rubric and the same revision
loop. It states the `no_prior_research` stop — a follow-up with no notes does not answer
from parametric knowledge — and names that as "the single failure mode this whole pipeline
exists to prevent". Both rejected alternatives are recorded: a cheaper uncritiqued
follow-up path, and answering from model knowledge when notes are absent. Phase 17
(`REQ-followup-live-search`) is named as the expected reversal; the record is `Accepted`.

**ADR-0004 (DEC-14)** records that the final state of each run is persisted to SQLite
(Postgres under `DATABASE_URL`, same schema) because a follow-up arrives as a separate
request, likely on a different worker, possibly after a redeploy. LangGraph's checkpointer
is rejected with its reason — it solves resuming a half-finished graph, a different feature
with a different failure model, and would couple the schema to framework internals. The
accepted consequence is stated plainly: a crash mid-run loses that run and the caller
retries, which is honest when the alternative is resuming into a half-researched report.

**ADR-0005 (DEC-22)** records the judge on Opus 5 (`JUDGE_MODEL`, `EVAL_JUDGE_MODEL`
overridable, `evals/graders.py`) against a Sonnet 5 pipeline (`MODEL`,
`src/research_agent/graph.py`), returning a structured verdict rather than a text
convention. Its Context opens on [ADR-0002](../../../docs/adr/0002-separate-critic-node.md)'s
known limit — the critic shares the writer's model — because that caveat *is* this record's
premise. Both rejected alternatives are recorded, including the text verdict: a harness
that mis-parses reports a confident wrong number, which is worse than crashing. Phase 16 is
named as the expected reversal, with the note that it removes the premise, so the rationale
must be re-derived rather than inherited.

**ADR-0006** is the odd record. It carries `**Source:** Phase 10.5 (2026-08-04), shipped as
Fly release v4` and no `Promoted from:` line, because there is no DESIGN.md passage behind
it. Context states that the exposure was confirmed against production, not inferred — an
anonymous `GET /sessions` returned real session contents and two `DELETE` calls returned
204 from the open internet — and that `DEMO_TOKEN` did not close it because `check_token`
runs only inside `guard`, which those four paths never reached.

Its Decision has four parts, each with its own reason, because they are separable and a
future refactor is most likely to pick off one without seeing the rest: the separate
`SESSIONS_TOKEN` with `DEMO_TOKEN` as a fallback *value*; failing closed at 403 when unset,
deliberately diverging from `check_token`'s open-when-unset convention; `guard` deliberately
**not** applied to the reads, because it bundles `check_token` + `check_rate_limit` +
`check_daily_cap` indivisibly and would 429 reads at the daily cap in direct contradiction
of the cap's own "Read-only endpoints still work" message; and the `APIRouter` grouping, so
membership is structural rather than four routes each remembering a credential.

Consequences leads with its own heading — **`DEMO_TOKEN` must never be set in production** —
rather than a bullet, because that single consequence is why the record exists. `guard`
fronts `POST /research/stream` and the demo page sends no token header, so setting it 401s
every anonymous visitor and takes the public demo offline. The record states that any future
refactor "tidying" the two tokens into one reintroduces exactly that. Phase 12
(`REQ-store-lifecycle-and-ownership`) is the expected reversal.

## Task-by-task

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | ADR-0003 — follow-ups reuse the critic | `b1d15e8` | `docs/adr/0003-followups-reuse-critic-no-prior-research.md` |
| 2 | ADR-0004 — sessions in SQLite, not the checkpointer | `3a7fb73` | `docs/adr/0004-sessions-in-sqlite-not-langgraph-checkpointer.md` |
| 3 | ADR-0005 — the Opus 5 eval judge | `dc444cd` | `docs/adr/0005-opus-5-eval-judge.md` |
| 4 | ADR-0006 — separate, fail-closed `SESSIONS_TOKEN` | `544ff3a` | `docs/adr/0006-separate-sessions-token-fails-closed.md` |

## Verification

All four task gates printed `GATE_OK`. Plan-level verification from the repo root:

| Check | Result |
|-------|--------|
| `ls docs/adr/000[1-5]-*.md \| wc -l` | 5 |
| `grep -L '^\*\*Status:\*\* Accepted' docs/adr/000[1-5]-*.md \| wc -l` | 0 |
| Nygard headings across `docs/adr/000[1-5]-*.md` | printed nothing (all three present in each) |
| `grep -L 'DESIGN.md' docs/adr/000[1-5]-*.md \| wc -l` | 0 |
| Subject coverage (`deterministic`, `critic`, `no_prior_research`, `checkpointer`, `judge`) | printed nothing — all five covered |
| `grep -c 'Superseded by' docs/adr/0003-*.md` | 0 |
| `grep -c 'Promoted from' docs/adr/0006-*.md` | 0 |
| `grep -c 'Superseded' docs/adr/0006-*.md` | 0 |
| `grep -c 'SESSIONS_TOKEN' / 'DEMO_TOKEN' / 'Phase 12'` in 0006 | 3 / 6 / 1 |
| `git status --porcelain src/ tests/ evals/ \| wc -l` | 0 |
| `git diff --stat HEAD~4 HEAD -- docs/adr/README.md` | empty — the index is untouched |
| `git diff --stat HEAD~4 HEAD` | 4 files, all under `docs/adr/`, 238 insertions, 0 deletions |
| `.venv/bin/pytest` (bare, so `addopts = "-q"` does not become `-qq`) | **388 passed, 28 skipped** — baseline unchanged |
| `.venv/bin/ruff check .` | All checks passed |

**Anti-vacuity checks.** This repo has been bitten three times by gates that pass by
matching nothing, so each distinguishing gate was probed against a file that should *not*
match:

| Gate | Probe | Result |
|------|-------|--------|
| `no_prior_research` present in 0003 | same grep against `0001-*.md` | 0 — the gate discriminates |
| `Promoted from` absent from 0006 | same grep against `0005-*.md` | 1 — the gate can fail |
| `DESIGN.md` absent from 0006 | direct count | 0, as designed — 0006 has no DESIGN.md passage |
| `000[1-5]` filename glob | widened to `000[1-6]` | 6 — the narrower glob is not matching an empty set |

Every gate is scoped to `docs/adr/` or a named file and piped to `wc -l`, so the BSD-grep
`^./` exclusion trap does not apply.

**Model-identifier check (T-10-05).** `JUDGE_MODEL` and `MODEL` as written in ADR-0005 were
re-read from source before commit: `evals/graders.py:28` is
`JUDGE_MODEL = os.environ.get("EVAL_JUDGE_MODEL", "claude-opus-5")` and
`src/research_agent/graph.py:38` is `MODEL = "claude-sonnet-5"`. Both match the record
verbatim.

## Deviations from Plan

None — plan executed exactly as written, including Task 4, which was added to the plan after
its prose objective was drafted (the objective still says "the remaining three records"; the
`<tasks>` block, `must_haves` and `files_modified` all carry four). No Rule 1/2/3 auto-fix
was needed, no architectural question arose, nothing was installed.

## Threat register

| Threat | Disposition | How this plan discharged it |
|--------|-------------|------------------------------|
| T-10-05 model identifiers spoofed | mitigated | Identifiers copied from `.planning/intel/decisions.md:266-267` and re-verified directly against `evals/graders.py:28` and `graph.py:38`; no new claim about `evals/` behaviour introduced |
| T-10-06 premature supersession | mitigated | 0003 gated at 0 occurrences of `Superseded by`, 0006 at 0 of `Superseded`; all four records `Accepted`, with Phases 17/16/12 named as *expected* only |
| T-10-07 scope creep into other decisions | mitigated | ADR-0004 contains 0 occurrences of `DEC-15`; each record cites exactly one DEC id (or, for 0006, one phase) |
| T-10-08 vacuous grep gate | mitigated | Four falsifiability probes run and tabulated above; every gate scoped and piped to `wc -l` |
| T-10-SC package installs | accepted | Nothing installed — documentation only |

No new threat flags. ADR-0006 *describes* an auth path but introduces none; no network
surface, no schema, no code change.

## Known Stubs

None. All four files are complete records.

## For the next plan

- **10-04 (DESIGN.md forward-links) is now unblocked in both directions.** ADR-0002's
  forward link to `0005-opus-5-eval-judge.md` resolves as of this plan. The DESIGN.md
  passages to link from are: § The graph line 17 (→ 0003), § Data and backends line 48
  (→ 0004), § Testing line 70 (→ 0005). ADR-0006 has no DESIGN.md passage to link from — do
  not invent one to give it a symmetrical backlink.
- **`docs/adr/README.md` was not touched by this plan and still needs no edit.** Its six
  index rows all resolve to files on disk now.
- The `000[1-5]` gates in VALIDATION deliberately exclude 0006. Do not widen them to
  `000[1-6]` — 0006 has no DESIGN.md citation by design, and widening would make the
  citation gate fail correctly-written work.

## Self-Check: PASSED

- `docs/adr/0003-followups-reuse-critic-no-prior-research.md` — FOUND
- `docs/adr/0004-sessions-in-sqlite-not-langgraph-checkpointer.md` — FOUND
- `docs/adr/0005-opus-5-eval-judge.md` — FOUND
- `docs/adr/0006-separate-sessions-token-fails-closed.md` — FOUND
- Commit `b1d15e8` — FOUND
- Commit `3a7fb73` — FOUND
- Commit `dc444cd` — FOUND
- Commit `544ff3a` — FOUND
