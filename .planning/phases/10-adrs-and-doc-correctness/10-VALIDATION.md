---
phase: 10
slug: adrs-and-doc-correctness
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-04
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

**This is a documentation phase.** It changes no production code and no runtime behaviour, so
verification is **grep gates over documents plus one live re-verification**, not test sampling.
The existing suite is a regression guard here, not the evidence: it must stay at exactly its
current numbers, because a docs phase that moves the test count has touched something it
shouldn't have.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (config in `pyproject.toml`, `[tool.pytest.ini_options]`) |
| **Config file** | `pyproject.toml` — `pythonpath = [".", "src", "tests"]`; no `conftest.py` |
| **Quick run command** | `.venv/bin/pytest` (bare — `addopts = "-q"` makes `-q` into `-qq` and hides counts) |
| **Full suite command** | `.venv/bin/pytest` |
| **Estimated runtime** | ~10 seconds |

**Regression baseline that must NOT change: 388 passed, 28 skipped.** Any deviation means this
phase touched code, which is out of scope.

---

## Sampling Rate

- **After every task commit:** the task's own grep gate
- **After every plan wave:** `.venv/bin/pytest` (expect 388/28 unchanged) plus `ruff check .`
- **Before `/gsd:verify-work`:** all grep gates green, suite unchanged, SC-5 re-verified live
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

Task IDs are assigned by the planner. Every row must map to a real task; no row may be dropped.

| Task ID | Plan | Wave | Requirement | Criterion | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------|-----------|-------------------|--------|
| TBD | TBD | 1 | REQ-adr-promotion | SC-1: five ADRs exist, numbered `0001`–`0005` | file gate | `ls docs/adr/*.md \| wc -l` returns 5 | ⬜ pending |
| TBD | TBD | 1 | REQ-adr-promotion | SC-1: every ADR carries an explicit `Status` field | grep gate | `grep -L '^## Status\|^\*\*Status' docs/adr/*.md` returns nothing | ⬜ pending |
| TBD | TBD | 1 | REQ-adr-promotion | SC-1: Nygard sections present in every ADR | grep gate | each of `docs/adr/*.md` contains `Context`, `Decision`, `Consequences` | ⬜ pending |
| TBD | TBD | 1 | REQ-adr-promotion | SC-1: the five subjects are covered — deterministic routing, separate critic, `no_prior_research` follow-ups, Opus 5 judge, SQLite over checkpointer | grep gate | one ADR each matches `deterministic`, `critic`, `no_prior_research`, `judge`, `checkpointer` | ⬜ pending |
| TBD | TBD | 2 | REQ-adr-promotion | SC-2: each ADR names the `docs/DESIGN.md` passage it was promoted from | grep gate | every `docs/adr/*.md` contains `DESIGN.md` | ⬜ pending |
| TBD | TBD | 2 | REQ-adr-promotion | SC-2: `docs/DESIGN.md` points forward to all five | grep gate | `grep -c 'docs/adr/\|ADR-000' docs/DESIGN.md` returns ≥ 5 | ⬜ pending |
| TBD | TBD | 2 | REQ-adr-promotion | Supersession works: the format documents how a later reversal marks a record superseded | grep gate | `grep -rl 'Superseded' docs/adr/` returns ≥ 1 (the convention, in a template or README) | ⬜ pending |
| TBD | TBD | 3 | REQ-adr-promotion | SC-3: no doc claims deploys run through Fly's GitHub integration | grep gate | `grep -rn 'GitHub integration' docs/ README.md` returns 0 | ⬜ pending |
| TBD | TBD | 3 | REQ-adr-promotion | SC-3: `docs/OPERATIONS.md` states deploys are manual | grep gate | `grep -c 'fly deploy -a research-agent' docs/OPERATIONS.md` returns ≥ 1 and the surrounding prose says manual | ⬜ pending |
| TBD | TBD | 3 | REQ-adr-promotion | SC-4: `docs/DESIGN.md` names four backends | grep gate | `grep -c 'three implementations' docs/DESIGN.md` returns 0; `pgvector` appears in the same paragraph | ⬜ pending |
| TBD | TBD | 3 | REQ-adr-promotion | SC-6: no doc quotes a Sonnet 5 rate as permanent | grep gate | any doc mentioning `$2/$10` also mentions `$3/$15` and `2026-09-01`; `/pricing` named as the live source | ⬜ pending |
| TBD | TBD | 4 | REQ-adr-promotion | SC-5 **re-verify only** — already satisfied by the v4 cutover | manual | see Manual-Only Verifications | ⬜ pending |
| TBD | TBD | 4 | REQ-adr-promotion | Regression: no production code touched | source gate | `git diff --quiet <phase-base> -- src/` exits 0 | ⬜ pending |
| TBD | TBD | 4 | REQ-adr-promotion | Regression: suite unchanged | test | `.venv/bin/pytest` → exactly 388 passed, 28 skipped | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers this phase — no test framework work needed. The grep gates above
are the verification, and they run against files this phase creates.

One caution carried from Phase 10.5: **BSD `grep -rn … .` on macOS emits paths without the
`./` prefix**, so a filter written as `grep -v '^./.planning'` never matches. Write exclusions
as `grep -v '^\.planning'` or scope the search to `docs/ README.md` directly.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| SC-5: deployed release matches `main` | REQ-adr-promotion | Needs the live host and the Fly CLI | 1. `fly releases -a research-agent` → v4 or later, healthy 2. `curl` `/`, `/health`, `/demo`, `/metrics` → all 200 3. `git rev-list --count origin/main..main` → 0. **Re-verify only — do not redeploy.** The Phase 10.5 cutover already satisfied this; the job is to record evidence, and to raise it as a finding if it has since drifted. |

---

## Validation Sign-Off

- [ ] Every criterion above has a runnable gate
- [ ] All five ADRs exist with `Status` and Nygard sections
- [ ] `git diff --quiet <phase-base> -- src/` exits 0 — no production code touched
- [ ] `.venv/bin/pytest` still reports exactly 388 passed, 28 skipped
- [ ] `ruff check .` clean
- [ ] SC-5 re-verified against the live host and the result recorded
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
