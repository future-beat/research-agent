---
phase: 10-adrs-and-doc-correctness
plan: 05
subsystem: docs
tags: [validation, gates, non-vacuity, regression, live-verification, phase-close]

# Dependency graph
requires:
  - "Plans 10-01 and 10-02 — the six ADR files the SC-1/SC-2 gates run against"
  - "Plan 10-03 — the docs/OPERATIONS.md and README.md corrections the SC-3 gates run against"
  - "Plan 10-04 — the docs/DESIGN.md corrections and forward-links the SC-2/SC-4/SC-6 gates run against"
  - "Phase base commit 715e9aa — the regression baseline for every diff"
  - "Fly release v4 (Phase 10.5 cutover, 2026-08-04) — the release SC-5 re-verifies rather than creates"
provides:
  - "10-VALIDATION.md § Execution Record — literal output for every gate, not a judgement about it"
  - "A four-probe non-vacuity control proving the gate shapes can fail"
  - "Recorded SC-5 evidence: release v4 healthy, four endpoints 200, checked 2026-08-05, nothing redeployed"
  - "The open finding that main is 21 documentation-only commits ahead of origin/main"
  - "ROADMAP's Phase 10.5 row reconciled to 5/5 Complete"
affects: [phase-11 planning inherits a pending Phase 10 sign-off that a single push clears]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Every gate recorded with its literal output in a table, so a later reader can audit the pass rather than trust it"
    - "Non-vacuity probed per gate SHAPE (zero-occurrence search, file counter, link resolver, absence gate), not once for the battery"
key-files:
  created:
    - .planning/phases/10-adrs-and-doc-correctness/10-05-SUMMARY.md
  modified:
    - .planning/phases/10-adrs-and-doc-correctness/10-VALIDATION.md
    - .planning/ROADMAP.md
    - .planning/REQUIREMENTS.md
    - .planning/STATE.md

key-decisions:
  - "SC-5 step 3 was recorded ❌ red and the approval left pending, rather than the criterion softened to match what was observed. The remedy is a git push this plan is not authorised to run, so it is a finding for the human — exactly the routing the plan's own threat register (T-10-22) demands."
  - "The red row was NOT treated as cause to redeploy. git diff --name-only origin/main..main over src/ tests/ evals/ pyproject.toml Dockerfile fly.toml returns 0 files, so the deployed v4 image is current; the divergence is documentation. Answering an unpushed-docs finding with fly deploy would have been scope creep into a docs phase (T-10-21)."
  - "ROADMAP's Phase 10.5 row was reconciled to 5/5 Complete because that is unconditionally true — all five 10.5 summaries are on disk and v4 was re-verified healthy this session. Phase 10's own row was moved to 5/5 but deliberately left In Progress, because its validation sign-off is pending."
  - "REQ-adr-promotion was left Pending rather than ticked. Its ADR substance is fully green, but the SC-5 row in the verification map is itself tagged REQ-adr-promotion, so by the contract's own mapping the requirement is not clear. The traceability row now names the single blocker so it can be flipped with one push."
  - "Two prose edits to 10-VALIDATION.md were forced by the task's own verify block and neither weakens a gate: '⬜ pending' left the status legend (nothing is pending, so the key entry was dead), and the sign-off label duplicating 'nyquist_compliant: true' was reworded so the token lives only in the frontmatter that owns it."

patterns-established:
  - "Non-vacuity is now probed per gate shape rather than once per battery — four controls here, against one in earlier plans"
  - "A gate battery records literal command output in a table, so the evidence survives the agent that produced it"

requirements-completed: []  # REQ-adr-promotion held on SC-5 step 3 — see the finding

# Metrics
duration-minutes: 14
completed: 2026-08-05
tasks-completed: 3
files-changed: 4
---

# Phase 10 Plan 05: Phase closeout gate battery Summary

Ran every gate Phase 10 promised, recorded literal output rather than verdicts, proved the gate
shapes can fail, and re-verified the live release without deploying — finding one red row that a
`git push` closes.

## What Was Built

Nothing was built. This plan is a measurement, and its output is the executed contract in
`10-VALIDATION.md`.

**Task 1 — the gate battery** (evidence recorded in `10-VALIDATION.md` § Execution Record)

All seventeen rows of the verification map were run as written on macOS with BSD grep, each
scoped to `docs/`, `README.md` or `docs/adr/` and counted with `wc -l` — never the
`grep -rn … . | grep -v '^./'` shape that has passed vacuously in this repo before.

- **ADR set:** five files matching `000[1-5]-*.md`; zero missing a `**Status:** Accepted` line;
  the Nygard loop printed nothing; the five subject tokens all matched; zero missing a
  `DESIGN.md` citation; `docs/DESIGN.md` links exactly five distinct `adr/000N-*.md` paths and
  every one resolved under `docs/`; `Superseded by ADR-` appears once in `docs/adr/README.md`.
- **ADR-0006 verified separately**, because it is a Phase 10.5 record and not a DESIGN.md
  promotion: it exists, is `Accepted`, mentions `DEMO_TOKEN` six times and `Phase 12` once, and
  carries zero `Promoted from`. The `000[1-5]` globs were **not** widened to `000[1-6]` — doing so
  would have made the DESIGN.md citation gate fail correctly-written work.
- **Doc corrections:** `GitHub integration` at 0 across `docs` and `README.md`;
  `Deploys are manual` present with both `fly deploy -a research-agent` (×3) and
  `fly releases -a research-agent`; `enforce_admins` present and `bypass` twice;
  `three implementations` at 0 with `four implementations` sharing its line with `pgvector`;
  no `$2/$10` occurrence unaccompanied by `$3/$15`; `/pricing` in both `docs/DESIGN.md` and
  `README.md`.
- **Regression:** `git diff --quiet 715e9aa -- src/` exited 0; the widened
  `git diff --stat 715e9aa -- src/ tests/ evals/ pyproject.toml` produced no output; bare
  `.venv/bin/pytest` reported `388 passed, 28 skipped, 1 warning in 8.51s`;
  `.venv/bin/ruff check .` reported `All checks passed!`.

**Task 2 — SC-5 re-verified, not redeployed**

`fly releases -a research-agent` shows **v4, `complete`**, attributed to
`hessam.abbaszadi@gmail.com` — which is also the standing evidence behind plan 10-03's
`docs/OPERATIONS.md` correction that releases come from a human running `fly deploy`, not a
machine token. `/`, `/health`, `/demo` and `/metrics` each returned **200**.
`git diff --quiet 715e9aa -- src/` exited 0.

No `fly deploy`, no `fly secrets set`, no mutating Fly subcommand and no `git push` was run at
any point. All Fly access was read-only.

**Task 3 — the record**

Every row carries `✅ green` or `❌ red`; none is pending. `§ Execution Record` holds the literal
output in four tables plus the SC-5 evidence with its check date, marked re-verified rather than
redeployed. Frontmatter is `status: complete`, `nyquist_compliant: true`.

## Non-Vacuity Control

The plan required proof that the gates can fail. Four controls were run, one per gate *shape*:

| Control | Shape probed | Result |
|---------|--------------|--------|
| `grep -rn 'fly deploy' docs README.md \| wc -l` | the zero-occurrence search used for `GitHub integration` | `3` — non-zero, so the `0` is a real absence |
| `ls docs/adr/009[1-5]-*.md \| wc -l` | the ADR file counter | `0` — the counter can return 0, so `5` is a real count |
| `test -f docs/adr/0009-nope.md` | the forward-link resolver | failed as required, so the resolved five are real files |
| `grep -L '^\*\*Status:\*\* Accepted'` against a scratch file with no status line | the absence gate | `1` — it reports missing files, so `0` is a real all-pass |

## Deviations from Plan

**1. [Rule 3 - Blocking] `ruff` is not on `PATH`**

- **Found during:** Task 1
- **Issue:** `ruff check .` returned `command not found`, which would read as a lint failure.
- **Fix:** Used `.venv/bin/ruff check .`, matching the `.venv/bin/pytest` convention the
  validation document already specifies. Output: `All checks passed!`, exit 0.
- **Recorded in:** `10-VALIDATION.md` § Execution Record → Regression, so a future phase does not
  misread a bare `ruff` failure.

**2. [Rule 3 - Blocking] Task 3's verify block collided with the document's own boilerplate**

- **Found during:** Task 3
- **Issue:** `grep -c '⬜ pending'` returned 1 because the *status legend* contains the token, and
  `grep -c 'nyquist_compliant: true'` returned 2 because the sign-off checklist label quotes the
  frontmatter key. Both are boilerplate, not rows.
- **Fix:** The dead `⬜ pending` key entry was dropped from the legend (nothing is pending), and
  the checklist label was reworded to "Frontmatter marks the phase Nyquist-compliant" so the
  literal token appears once, in the frontmatter that owns it. **No Criterion, no Automated
  Command and no Status was altered.**

## Findings

**SC-5 step 3 is RED — `main` is 21 commits ahead of `origin/main`.**

`git rev-list --count origin/main..main` returned **21**, not 0. The count was taken after
`git fetch origin`, so it is against a current remote and not a stale tracking ref.

- `origin/main` is at `804b873` *(docs(10.5): close the phase — v4 shipped and verified live)*.
- `main` is at `238d479` *(docs(10-04): complete the DESIGN.md corrections and ADR forward-links)*.
- All 21 commits are Phase 10 documentation, **including the phase base `715e9aa` itself**.
- `git diff --name-only origin/main..main -- src/ tests/ evals/ pyproject.toml Dockerfile fly.toml`
  returns **0 files**.

**Consequence for the deployed image: none.** The code in Fly release v4, on `origin/main` and on
`main` is identical — which `git diff --quiet 715e9aa -- src/` exiting 0 independently confirms.
ROADMAP § Phase 10 success criterion 5 as written — *"the deployed release matches `main` … and
`/`, `/health`, `/demo`, `/metrics` still return 200"* — is substantively satisfied. What failed
is the validation document's step 3, the proxy check that nothing is unpushed.

It was recorded red rather than reworded, and **not** answered with a deploy: the remedy is
`git push`, which this plan is not authorised to run. Pushing the 21 documentation commits turns
the row green with no code change and no release.

## Downstream Effects

- **Phase 10 is not signed off.** `10-VALIDATION.md` carries `**Approval:** pending`, ROADMAP
  keeps Phase 10 at `5/5 | In Progress` with the blocker named, and `REQ-adr-promotion` stays
  Pending — its ADR substance is green, but the SC-5 row is tagged to it.
- **ROADMAP's stale Phase 10.5 row was reconciled**, as plans 10-03 and 10-04 both flagged: it now
  reads `5/5 | Complete` with the v4 ship date and this session's live re-verification. The
  `10.5-05-PLAN.md` checkbox was ticked; all five 10.5 summaries are on disk.
- **One push closes the phase.** After it: flip the SC-5 row to ✅, set the approval, mark Phase 10
  Complete, tick `REQ-adr-promotion`.

## Known Stubs

None. This plan created no code and no interface.

## Threat Flags

None. No file created or modified by this plan introduces network, auth, file-access or schema
surface — the changes are four planning documents and one summary.

## Self-Check: PASSED

- `10-VALIDATION.md` — FOUND, `⬜ pending` count 0, `nyquist_compliant: true` count 1,
  `## Execution Record` count 1, nine distinct `10-0[1-5]-T[1-3]` ids preserved
- `git status --porcelain docs README.md src tests evals` returned 0 lines — this plan touched no
  documentation or source file
- `git diff --quiet 715e9aa -- src/` — exit 0
- `.venv/bin/pytest` — `388 passed, 28 skipped`
- Commit `126b97e` — FOUND
