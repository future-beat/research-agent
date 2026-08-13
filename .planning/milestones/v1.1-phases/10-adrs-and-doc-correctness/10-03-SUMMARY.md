---
phase: 10-adrs-and-doc-correctness
plan: 03
subsystem: docs
tags: [documentation, deploy, ci, branch-protection, pricing, correctness]

# Dependency graph
requires:
  - "Phase 10.5's Fly release v4 — the direct push whose bypass notice is the evidence quoted in the new text"
  - "src/research_agent/usage.py:55-80 — the two contiguous price windows the README must not contradict"
provides:
  - "docs/OPERATIONS.md § Fly.io — a deploy paragraph that matches reality: manual releases, named evidence, honest gating"
  - "README.md § Limitations — a cost bullet that names /pricing as the live rate source and dates both windows"
  - "SC-3 satisfied, and the README half of SC-6"
affects: [10-04 fixes the DESIGN.md rate figures this README deliberately does not duplicate]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Deploy provenance stated with a checkable command (fly releases -a research-agent) rather than an assertion"
    - "Rates named by window and date, never by figure, outside the single document that owns them"
key-files:
  created:
    - .planning/phases/10-adrs-and-doc-correctness/10-03-SUMMARY.md
  modified:
    - docs/OPERATIONS.md
    - README.md

key-decisions:
  - "The replacement is corrected in BOTH directions. The old text was wrong that pushes auto-deploy; a replacement saying only 'PRs are gated' would have been wrong the opposite way. The new paragraph states that main carries two required checks under strict: true AND that enforce_admins is false, so an admin's direct push succeeds with a recorded bypass notice and CI runs only after the fact."
  - "The bypass claim is anchored to observed evidence, not to a settings read alone: the Phase 10.5 push to main on 2026-08-04 reported 'Bypassed rule violations for refs/heads/main: 2 of 2 required status checks are expected', quoted verbatim alongside the gh api protection endpoint that was checked."
  - "No settings change is recommended in the doc. Whether to turn enforce_admins on is an operator decision; a docs plan that editorialises about it invites a reader to treat the doc as the source of that policy."
  - "The drift consequence is stated explicitly — merging to main ships nothing until someone runs the command — because that is the failure mode the false text actively caused."
  - "README quotes no dollar figures. The rates live in docs/DESIGN.md (plan 10-04); duplicating them here would create a second copy to keep in sync past 2026-09-01. The bullet names windows and ISO dates only."

patterns-established:
  - "Self-referential gate failure caught before commit: the first draft of the OPERATIONS paragraph itself contained the phrase 'GitHub integration' (in a negation), so the zero-occurrence gate correctly failed on corrected prose. Rewritten to 'Fly is not wired to this repository' rather than weakening the gate."

requirements-completed: []  # REQ-adr-promotion is phase-scoped; 10-04/05 remain

# Metrics
duration-minutes: 9
completed: 2026-08-05
tasks-completed: 2
files-changed: 2
---

# Phase 10 Plan 03: Deploy and pricing correctness Summary

Replaced `docs/OPERATIONS.md`'s false auto-deploy claim with the verified truth — manual `fly deploy`, `enforce_admins: false`, a bypassable `main` — and pointed `README.md`'s cost limitation at `/pricing` instead of leaving list prices sounding permanent.

## What Was Built

**Task 1 — `docs/OPERATIONS.md` deploy paragraph** (commit `3a0f76d`)

The three-line claim that "deploys currently run through Fly's GitHub integration … a direct push that fails tests still deploys" is gone. In its place, in the same position under the "New files from Fly.io Launch" blockquote:

- **Deploys are manual.** Fly is not wired to the repository; there is no deploy job in CI; nothing ships on push, merge, or tag.
- The command is named (`fly deploy -a research-agent`) and so is the evidence (`fly releases -a research-agent` attributes every release to the owner's personal account, not a machine token).
- The consequence that replaces the old one: nothing can deploy a failing tree, but merging to `main` ships nothing either, so `main` and the deployed release can drift silently.
- Gating stated honestly: two required checks (`lint · tests · evals`, `image build · container smoke test`) under `strict: true`, but `enforce_admins` is `false`, so an admin's direct push succeeds with a recorded bypass notice. The Phase 10.5 push is quoted as the live observation. The checks gate pull requests, not every path to `main`.

**Task 2 — `README.md` cost limitation** (commit `0c5f35b`)

The "**Cost is computed from list prices**" bullet keeps its original point (no enterprise discounts, no `inference_geo` multiplier, `/metrics` tracks the shape of the bill) and gains: list prices are effective-dated, the introductory window runs through `2026-08-31`, the standard window applies from `2026-09-01`, and `/pricing` reports whichever window accounting is using today.

## Deviations from Plan

None — plan executed as written. One in-flight correction worth recording, though it is not a deviation: the first draft of the OPERATIONS replacement opened "There is no Fly GitHub integration and no deploy job in CI", which is true prose but tripped the plan's own `grep -rn 'GitHub integration' docs README.md | wc -l == 0` gate. Per the plan's instruction, the prose was rewritten ("Fly is not wired to this repository") rather than the gate weakened.

## Verification

| Gate | Result |
|---|---|
| `grep -rn 'GitHub integration' docs README.md \| wc -l` | 0 |
| `grep -c 'Deploys are manual' docs/OPERATIONS.md` | 1 |
| `grep -c 'fly deploy -a research-agent'` / `'fly releases -a research-agent'` | 3 / 1 |
| `grep -c 'enforce_admins'` / `grep -ci 'bypass'` | 1 / 2 |
| `grep -c 'lint · tests · evals' docs/OPERATIONS.md` | 1 |
| Neighbours survive: `New files from Fly.io Launch` / `min_machines_running` / `SESSIONS_TOKEN` | 1 / 1 / 5 |
| `grep -c '/pricing' README.md`, `grep 'list prices' README.md \| grep -c '/pricing'` | 2 / 1 |
| `grep -c '2026-08-31'` / `'2026-09-01'` in README | 1 / 1 |
| `grep -nE '2/\$10\|3/\$15' README.md \| wc -l` | 0 |
| README neighbours: rate-limit limitation / CI badge | 1 / 1 |
| `.venv/bin/pytest` (bare, so `-q` is not doubled) | **388 passed, 28 skipped** |
| `.venv/bin/ruff check .` | All checks passed |
| `git status --porcelain src/ tests/ evals/ \| wc -l` | 0 |

## Threat Register Outcome

| ID | Disposition | Outcome |
|---|---|---|
| T-10-09 | mitigated | `fly releases -a research-agent` named in-file as the checkable deploy provenance |
| T-10-10 | mitigated | All five neighbour survival gates pass; diff is 19 insertions / 3 deletions in OPERATIONS and 1 line in README |
| T-10-11 | mitigated | Zero rate figures in README; rates remain solely in `docs/DESIGN.md` for plan 10-04 |
| T-10-12 | mitigated | Every gate names `docs README.md` explicitly and counts with `wc -l`, so BSD grep's missing `./` prefix cannot make it vacuous — proven by the gate actually failing on the first draft |
| T-10-SC | accepted | Nothing installed; documentation only |

## Known Stubs

None.

## Threat Flags

None — no network, auth, file-access, or schema surface touched.

## For Next Phase

- **Plan 10-04 owns the rate figures.** README now defers to `docs/DESIGN.md` for numbers; 10-04 must make that document's `$2/$10` → `$3/$15` window text correct, or the deferral points at stale data.
- **`docs/OPERATIONS.md` § CI line 104 was deliberately not edited.** "`main` is protected: both checks must pass before a pull request can merge" is accurate as written (it says *pull request*), and the new deploy paragraph links to that section for the bypass caveat rather than duplicating it.
- **`enforce_admins: false` is now documented, not resolved.** Whether to enable it is an operator decision left open on purpose.

## Self-Check: PASSED

Both modified files and the SUMMARY exist on disk; both task commits (`3a0f76d`, `0c5f35b`) resolve in `git log`.
