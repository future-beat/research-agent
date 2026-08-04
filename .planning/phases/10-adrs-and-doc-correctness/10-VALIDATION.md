---
phase: 10
slug: adrs-and-doc-correctness
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-08-04
executed: 2026-08-05
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
| 10-02-T3 | 10-02 | 1 | REQ-adr-promotion | SC-1: five ADRs exist, numbered `0001`–`0005` | file gate | `ls docs/adr/000[1-5]-*.md \| wc -l` returns 5 | ✅ green |
| 10-02-T3 | 10-02 | 1 | REQ-adr-promotion | SC-1: every ADR carries an explicit `Status` field | grep gate | `grep -L '^\*\*Status:\*\* Accepted' docs/adr/000[1-5]-*.md \| wc -l` returns 0 | ✅ green |
| 10-01-T1 | 10-01 | 1 | REQ-adr-promotion | SC-1: Nygard sections present in every ADR | grep gate | `for f in docs/adr/000[1-5]-*.md; do grep -q '^## Context' "$f" && grep -q '^## Decision' "$f" && grep -q '^## Consequences' "$f" \|\| echo "MISSING $f"; done` prints nothing | ✅ green |
| 10-02-T3 | 10-02 | 1 | REQ-adr-promotion | SC-1: the five subjects are covered — deterministic routing, separate critic, `no_prior_research` follow-ups, Opus 5 judge, SQLite over checkpointer | grep gate | `for t in deterministic critic no_prior_research checkpointer judge; do [ "$(grep -il "$t" docs/adr/000[1-5]-*.md \| wc -l \| tr -d ' ')" -ge 1 ] \|\| echo "UNCOVERED $t"; done` prints nothing | ✅ green |
| 10-02-T3 | 10-02 | 1 | REQ-adr-promotion | SC-2: each ADR names the `docs/DESIGN.md` passage it was promoted from | grep gate | `grep -L 'DESIGN.md' docs/adr/000[1-5]-*.md \| wc -l` returns 0 | ✅ green |
| 10-04-T3 | 10-04 | 2 | REQ-adr-promotion | SC-2: `docs/DESIGN.md` points forward to all five | grep gate | `grep -o 'adr/000[1-5]-[a-z0-9-]*\.md' docs/DESIGN.md \| sort -u \| wc -l` returns 5, and each path resolves under `docs/` | ✅ green |
| 10-01-T1 | 10-01 | 1 | REQ-adr-promotion | Supersession works: the format documents how a later reversal marks a record superseded | grep gate | `grep -c 'Superseded by ADR-' docs/adr/README.md` returns ≥ 1 | ✅ green |
| 10-03-T1 | 10-03 | 1 | REQ-adr-promotion | SC-3: no doc claims deploys run through Fly's GitHub integration | grep gate | `grep -rn 'GitHub integration' docs README.md \| wc -l` returns 0 | ✅ green |
| 10-03-T1 | 10-03 | 1 | REQ-adr-promotion | SC-3: `docs/OPERATIONS.md` states deploys are manual | grep gate | `grep -c 'Deploys are manual' docs/OPERATIONS.md` ≥ 1 and `grep -c 'fly deploy -a research-agent' docs/OPERATIONS.md` ≥ 1 and `grep -c 'fly releases -a research-agent' docs/OPERATIONS.md` ≥ 1 | ✅ green |
| 10-03-T1 | 10-03 | 1 | REQ-adr-promotion | SC-3 (added 2026-08-04): the doc states a direct push to `main` bypasses the required checks, not merely that PRs are gated. `enforce_admins` is `false`, verified via the GitHub API and observed live on the Phase 10.5 push | grep gate | `grep -c 'enforce_admins' docs/OPERATIONS.md` ≥ 1 AND `grep -ci 'bypass' docs/OPERATIONS.md` ≥ 1. NOT `grep -i 'direct push'` — that phrase is already in the false paragraph and would pass vacuously | ✅ green |
| 10-02-T4 | 10-02 | 1 | REQ-adr-promotion | ADR-0006 records the Phase 10.5 auth decisions and states that `DEMO_TOKEN` must never be set in production | file + grep gate | `test -f docs/adr/0006-separate-sessions-token-fails-closed.md` and `grep -c 'DEMO_TOKEN' …` ≥ 1 and `grep -c 'Phase 12' …` ≥ 1 | ✅ green |
| 10-02-T4 | 10-02 | 1 | REQ-adr-promotion | ADR-0006 is not a DESIGN.md promotion and does not pollute the `000[1-5]` gates | grep gate | `grep -c 'Promoted from' docs/adr/0006-*.md` returns 0; `ls docs/adr/000[1-5]-*.md \| wc -l` still returns 5 | ✅ green |
| 10-04-T1 | 10-04 | 2 | REQ-adr-promotion | SC-4: `docs/DESIGN.md` names four backends | grep gate | `grep -c 'three implementations' docs/DESIGN.md` returns 0; `grep 'four implementations' docs/DESIGN.md \| grep -c 'pgvector'` returns 1 | ✅ green |
| 10-04-T2, 10-03-T2 | 10-04, 10-03 | 2 | REQ-adr-promotion | SC-6: no doc quotes a Sonnet 5 rate as permanent | grep gate | `grep -rn '2/\$10' docs README.md \| grep -v '3/\$15' \| wc -l` returns 0; `grep -c '2026-09-01' docs/DESIGN.md` ≥ 1; `grep 'list prices' README.md \| grep -c '/pricing'` ≥ 1 | ✅ green |
| 10-05-T2 | 10-05 | 3 | REQ-adr-promotion | SC-5 **re-verify only** — already satisfied by the v4 cutover | manual | see Manual-Only Verifications | ❌ red |
| 10-05-T1 | 10-05 | 3 | REQ-adr-promotion | Regression: no production code touched | source gate | `git diff --quiet 715e9aa -- src/` exits 0 | ✅ green |
| 10-05-T1 | 10-05 | 3 | REQ-adr-promotion | Regression: suite unchanged | test | `.venv/bin/pytest 2>&1 \| tail -3 \| grep -c '388 passed, 28 skipped'` returns 1 | ✅ green |

*Status legend: ✅ green · ❌ red · ⚠️ flaky · ⬜ not yet run (none remain — every row was executed 2026-08-05)*

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

## Execution Record

Executed 2026-08-05 from the repo root on macOS (BSD grep), against phase base commit `715e9aa`.
Every command below was run as written in the Automated Command column; no Criterion and no
command was edited after being run.

### ADR set (SC-1, SC-2)

| Gate | Literal output | Expected |
|------|----------------|----------|
| `ls docs/adr/000[1-5]-*.md \| wc -l` | `5` | 5 |
| `grep -L '^\*\*Status:\*\* Accepted' docs/adr/000[1-5]-*.md \| wc -l` | `0` | 0 |
| Nygard section loop over the five | *(printed nothing)* | nothing |
| Subject-token loop (`deterministic critic no_prior_research checkpointer judge`) | *(printed nothing)* | nothing |
| `grep -L 'DESIGN.md' docs/adr/000[1-5]-*.md \| wc -l` | `0` | 0 |
| `grep -o 'adr/000[1-5]-[a-z0-9-]*\.md' docs/DESIGN.md \| sort -u \| wc -l` | `5` | 5 |
| each extracted link resolved with `test -f docs/$p` | *(no `DANGLING` lines)* | all resolve |
| `grep -c 'Superseded by ADR-' docs/adr/README.md` | `1` | ≥ 1 |

ADR-0006, verified separately because it is a Phase 10.5 record and not a `docs/DESIGN.md`
promotion — the `000[1-5]` globs exclude it deliberately and were **not** widened to `000[1-6]`:

| Gate | Literal output | Expected |
|------|----------------|----------|
| `test -f docs/adr/0006-separate-sessions-token-fails-closed.md` | exit 0 | exists |
| `grep -c '^\*\*Status:\*\* Accepted' docs/adr/0006-…md` | `1` | 1 |
| `grep -c 'DEMO_TOKEN' docs/adr/0006-…md` | `6` | ≥ 1 |
| `grep -c 'Phase 12' docs/adr/0006-…md` | `1` | ≥ 1 |
| `grep -c 'Promoted from' docs/adr/0006-*.md` | `0` | 0 |

### Doc corrections (SC-3, SC-4, SC-6)

| Gate | Literal output | Expected |
|------|----------------|----------|
| `grep -rn 'GitHub integration' docs README.md \| wc -l` | `0` | 0 |
| `grep -c 'Deploys are manual' docs/OPERATIONS.md` | `1` | ≥ 1 |
| `grep -c 'fly deploy -a research-agent' docs/OPERATIONS.md` | `3` | ≥ 1 |
| `grep -c 'fly releases -a research-agent' docs/OPERATIONS.md` | `1` | ≥ 1 |
| `grep -c 'enforce_admins' docs/OPERATIONS.md` | `1` | ≥ 1 |
| `grep -ci 'bypass' docs/OPERATIONS.md` | `2` | ≥ 1 |
| `grep -c 'three implementations' docs/DESIGN.md` | `0` | 0 |
| `grep 'four implementations' docs/DESIGN.md \| grep -c 'pgvector'` | `1` | 1 |
| `grep -rn '2/\$10' docs README.md \| grep -v '3/\$15' \| wc -l` | `0` | 0 |
| `grep -c '2026-09-01' docs/DESIGN.md` | `1` | ≥ 1 |
| `grep 'list prices' README.md \| grep -c '/pricing'` | `1` | ≥ 1 |
| `grep -c '/pricing' docs/DESIGN.md` | `1` | ≥ 1 |
| `grep -c '/pricing' README.md` | `2` | ≥ 1 |

### Regression

| Gate | Literal output | Expected |
|------|----------------|----------|
| `git diff --quiet 715e9aa -- src/` | exit `0` | exit 0 |
| `git diff --stat 715e9aa -- src/ tests/ evals/ pyproject.toml` | *(no output)* | empty |
| `.venv/bin/pytest` (bare) | `388 passed, 28 skipped, 1 warning in 8.51s` | `388 passed, 28 skipped` |
| `.venv/bin/ruff check .` | `All checks passed!` — exit 0 | exit 0 |

`ruff` is not on `PATH` in this shell; the venv binary `.venv/bin/ruff` was used, matching the
`.venv/bin/pytest` convention already recorded in § Test Infrastructure.

### Non-vacuity control

A gate battery that has never been observed failing has not been tested. Four controls were run,
each exercising the **shape** of a gate above against input that must make it fail:

| Control | Gate shape probed | Literal output | Verdict |
|---------|-------------------|----------------|---------|
| `grep -rn 'fly deploy' docs README.md \| wc -l` | the zero-occurrence search used for `GitHub integration` | `3` | non-zero — the search can match, so the `0` above is a real absence |
| `ls docs/adr/009[1-5]-*.md \| wc -l` | the ADR file count | `0` (`no matches found`) | the counter can return 0, so `5` is a real count |
| `test -f docs/adr/0009-nope.md` | the forward-link resolver | non-zero exit → `DANGLING detected correctly` | a fabricated path fails, so the resolved five are real files |
| `grep -L '^\*\*Status:\*\* Accepted'` against a scratch file with no status line | the `Status` gate | `1` | the gate reports missing files, so `0` is a real all-pass |

### SC-5 — re-verified, NOT redeployed

Checked **2026-08-05**. No `fly deploy`, no `fly secrets set`, no mutating Fly subcommand and no
`git push` was run at any point in this plan. All Fly access was read-only.

`fly releases -a research-agent`, verbatim:

```
 VERSION │ STATUS   │ DESCRIPTION │ USER                       │ DATE
 v4      │ complete │ Release     │ hessam.abbaszadi@gmail.com │ 5h6m ago
 v3      │ complete │ Release     │ hessam.abbaszadi@gmail.com │ Aug 2 2026 12:28
 v2      │ complete │ Release     │ hessam.abbaszadi@gmail.com │ Aug 1 2026 17:08
 v1      │ complete │ Release     │ hessam.abbaszadi@gmail.com │ Aug 1 2026 16:52
```

Current release is **v4, `complete`**, attributed to the owner's personal account — which is also
the standing evidence behind the `docs/OPERATIONS.md` deploy correction in plan 10-03: every
release is a human running `fly deploy`, not a machine token.

`curl -s -o /dev/null -w '%{http_code}' https://research-agent.fly.dev<path>`:

```
/        200
/health  200
/demo    200
/metrics 200
```

| Check | Literal output | Expected | Verdict |
|-------|----------------|----------|---------|
| `fly releases -a research-agent` | v4, `complete` | v4 or later, healthy | ✅ |
| four HTTP probes | `200 200 200 200` | all 200 | ✅ |
| `git rev-list --count origin/main..main` | `21` | `0` | ❌ **red** |
| `git diff --quiet 715e9aa -- src/` | exit `0` | exit 0 | ✅ |

**Finding — SC-5 step 3 is red: `main` is 21 commits ahead of `origin/main`.**

Recorded as red rather than reworded. The command was run after `git fetch origin`, so the count
is against a current remote, not a stale tracking ref. The detail:

- `origin/main` is at `804b873` *(docs(10.5): close the phase — v4 shipped and verified live)*.
- `main` is at `238d479` *(docs(10-04): complete the DESIGN.md corrections and ADR forward-links)*.
- All 21 commits in between are Phase 10 documentation, **including the phase base `715e9aa`
  itself**, which is also unpushed.
- `git diff --name-only origin/main..main -- src/ tests/ evals/ pyproject.toml Dockerfile fly.toml`
  returns **0 files**. The divergence touches only `.planning/`, `docs/`, `docs/adr/` and
  `README.md`.

**Consequence for the deployed image: none.** The code on `origin/main`, the code on `main` and
the code in Fly release v4 are byte-identical, which is what `git diff --quiet 715e9aa -- src/`
exiting 0 independently confirms. ROADMAP § Phase 10 success criterion 5 as written — *"the
deployed release matches `main` … and `/`, `/health`, `/demo`, `/metrics` still return 200"* — is
therefore substantively satisfied. What failed is the validation document's step 3, the proxy
check that nothing is unpushed.

**Why it was not fixed here:** the only remedy is `git push`, which plan 10-05 is not authorised
to run and which is out of scope for a read-only gate battery. Per the phase's own rule, drift is
a finding for the human, not something a docs phase resolves on its own initiative. Pushing the
21 documentation commits turns this row green with no deploy and no code change.

---

## Validation Sign-Off

- [x] Every criterion above has a runnable gate
- [x] All five ADRs exist with `Status` and Nygard sections
- [x] `git diff --quiet <phase-base> -- src/` exits 0 — no production code touched
- [x] `.venv/bin/pytest` still reports exactly 388 passed, 28 skipped
- [x] `ruff check .` clean
- [ ] SC-5 re-verified against the live host and the result recorded — **evidence recorded, but step 3 (`origin/main..main` → 0) came back `21`; see the finding above**
- [x] Frontmatter marks the phase Nyquist-compliant

**Approval:** pending — SC-5 step 3 is red: `main` is 21 documentation-only commits ahead of
`origin/main`. Release v4 is healthy, all four endpoints return 200, and no deployable file
differs. Resolve by pushing `main`; no redeploy is required.
