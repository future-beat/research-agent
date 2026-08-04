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

Task IDs assigned by the planner (`{plan}-T{n}`). Every row maps to a real task; no row may be
dropped, and no Criterion or Automated Command may be rewritten after the gate has been run.
**Phase base commit for all regression diffs: `715e9aa`.**

| Task ID | Plan | Wave | Requirement | Criterion | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------|-----------|-------------------|--------|
| 10-02-T3 | 10-02 | 1 | REQ-adr-promotion | SC-1: five ADRs exist, numbered `0001`–`0005` | file gate | `ls docs/adr/000[1-5]-*.md \| wc -l` returns 5 | ⬜ pending |
| 10-02-T3 | 10-02 | 1 | REQ-adr-promotion | SC-1: every ADR carries an explicit `Status` field | grep gate | `grep -L '^\*\*Status:\*\* Accepted' docs/adr/000[1-5]-*.md \| wc -l` returns 0 | ⬜ pending |
| 10-01-T1 | 10-01 | 1 | REQ-adr-promotion | SC-1: Nygard sections present in every ADR | grep gate | `for f in docs/adr/000[1-5]-*.md; do grep -q '^## Context' "$f" && grep -q '^## Decision' "$f" && grep -q '^## Consequences' "$f" \|\| echo "MISSING $f"; done` prints nothing | ⬜ pending |
| 10-02-T3 | 10-02 | 1 | REQ-adr-promotion | SC-1: the five subjects are covered — deterministic routing, separate critic, `no_prior_research` follow-ups, Opus 5 judge, SQLite over checkpointer | grep gate | `for t in deterministic critic no_prior_research checkpointer judge; do [ "$(grep -il "$t" docs/adr/000[1-5]-*.md \| wc -l \| tr -d ' ')" -ge 1 ] \|\| echo "UNCOVERED $t"; done` prints nothing | ⬜ pending |
| 10-02-T3 | 10-02 | 1 | REQ-adr-promotion | SC-2: each ADR names the `docs/DESIGN.md` passage it was promoted from | grep gate | `grep -L 'DESIGN.md' docs/adr/000[1-5]-*.md \| wc -l` returns 0 | ⬜ pending |
| 10-04-T3 | 10-04 | 2 | REQ-adr-promotion | SC-2: `docs/DESIGN.md` points forward to all five | grep gate | `grep -o 'adr/000[1-5]-[a-z0-9-]*\.md' docs/DESIGN.md \| sort -u \| wc -l` returns 5, and each path resolves under `docs/` | ⬜ pending |
| 10-01-T1 | 10-01 | 1 | REQ-adr-promotion | Supersession works: the format documents how a later reversal marks a record superseded | grep gate | `grep -c 'Superseded by ADR-' docs/adr/README.md` returns ≥ 1 | ⬜ pending |
| 10-03-T1 | 10-03 | 1 | REQ-adr-promotion | SC-3: no doc claims deploys run through Fly's GitHub integration | grep gate | `grep -rn 'GitHub integration' docs README.md \| wc -l` returns 0 | ⬜ pending |
| 10-03-T1 | 10-03 | 1 | REQ-adr-promotion | SC-3: `docs/OPERATIONS.md` states deploys are manual | grep gate | `grep -c 'Deploys are manual' docs/OPERATIONS.md` ≥ 1 and `grep -c 'fly deploy -a research-agent' docs/OPERATIONS.md` ≥ 1 and `grep -c 'fly releases -a research-agent' docs/OPERATIONS.md` ≥ 1 | ⬜ pending |
| 10-03-T1 | 10-03 | 1 | REQ-adr-promotion | SC-3 (added 2026-08-04): the doc states a direct push to `main` bypasses the required checks, not merely that PRs are gated. `enforce_admins` is `false`, verified via the GitHub API and observed live on the Phase 10.5 push | grep gate | `grep -c 'enforce_admins' docs/OPERATIONS.md` ≥ 1 AND `grep -ci 'bypass' docs/OPERATIONS.md` ≥ 1. NOT `grep -i 'direct push'` — that phrase is already in the false paragraph and would pass vacuously | ⬜ pending |
| 10-02-T4 | 10-02 | 1 | REQ-adr-promotion | ADR-0006 records the Phase 10.5 auth decisions and states that `DEMO_TOKEN` must never be set in production | file + grep gate | `test -f docs/adr/0006-separate-sessions-token-fails-closed.md` and `grep -c 'DEMO_TOKEN' …` ≥ 1 and `grep -c 'Phase 12' …` ≥ 1 | ⬜ pending |
| 10-02-T4 | 10-02 | 1 | REQ-adr-promotion | ADR-0006 is not a DESIGN.md promotion and does not pollute the `000[1-5]` gates | grep gate | `grep -c 'Promoted from' docs/adr/0006-*.md` returns 0; `ls docs/adr/000[1-5]-*.md \| wc -l` still returns 5 | ⬜ pending |
| 10-04-T1 | 10-04 | 2 | REQ-adr-promotion | SC-4: `docs/DESIGN.md` names four backends | grep gate | `grep -c 'three implementations' docs/DESIGN.md` returns 0; `grep 'four implementations' docs/DESIGN.md \| grep -c 'pgvector'` returns 1 | ⬜ pending |
| 10-04-T2, 10-03-T2 | 10-04, 10-03 | 2 | REQ-adr-promotion | SC-6: no doc quotes a Sonnet 5 rate as permanent | grep gate | `grep -rn '2/\$10' docs README.md \| grep -v '3/\$15' \| wc -l` returns 0; `grep -c '2026-09-01' docs/DESIGN.md` ≥ 1; `grep 'list prices' README.md \| grep -c '/pricing'` ≥ 1 | ⬜ pending |
| 10-05-T2 | 10-05 | 3 | REQ-adr-promotion | SC-5 **re-verify only** — already satisfied by the v4 cutover | manual | see Manual-Only Verifications | ⬜ pending |
| 10-05-T1 | 10-05 | 3 | REQ-adr-promotion | Regression: no production code touched | source gate | `git diff --quiet 715e9aa -- src/` exits 0 | ⬜ pending |
| 10-05-T1 | 10-05 | 3 | REQ-adr-promotion | Regression: suite unchanged | test | `.venv/bin/pytest 2>&1 \| tail -3 \| grep -c '388 passed, 28 skipped'` returns 1 | ⬜ pending |

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
