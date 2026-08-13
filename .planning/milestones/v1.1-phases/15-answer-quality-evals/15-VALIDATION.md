---
phase: 15
slug: answer-quality-evals
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-08-06
---

# Phase 15 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

An evals phase: the recorder seam, deterministic quality graders, replay wiring, the 40-case
dataset, ADR-0009, and the caveat rewrite. Everything is offline-testable except the recording
act itself (real spend, operator decision) — and a small calibration recording is the honest
middle step.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest; `pythonpath = [".", "src", "tests"]`; no `conftest.py` |
| **Full suite** | `.venv/bin/pytest` (bare — a second `-q` hides the count line) |
| **Evals** | `.venv/bin/python -m evals` — keyless, deterministic, `--min-pass-rate 0.9` |
| **Real Postgres** | local PG17+pgvector on :54329 (running); CI provides one |

**Measured baselines entering this phase (2026-08-06):**
- Suite: plain **563 passed / 65 skipped**; armed **627 passed / 1 skipped**
- Offline evals: **12/12** pass, keyless
- Golden cases exercising `no_prior_research`: **0** (confirmed gap)
- Fixture files under `evals/`: **0** (no recordings exist)
- README "Offline evals can't measure answer quality" limitation: present
- `docs/adr/` records: **8** (0009 lands here)

**SIXTEEN vacuous gates across seven phases.** `--collect-only` every selector. Baselines +
mutations observed red (or honest green with the recorded reason). Plans' arithmetic and file
paths have been wrong; trust the code.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Criterion | Test Type | Automated Command | Status |
|---------|------|------|-----------|-----------|-------------------|--------|
| 15-01-T2 | 15-01 | 1 | The recorder seam (`capture_state` in `run_case`) captures the fixture schema: per-turn final state + metadata (recorded_at, models map — pipeline + judge — git sha, judge verdicts, measured cost) — proven against a FAKE client, no network | unit | `pytest tests/ -k recorder_captures_schema` — 1 collected, 1 passed | ✅ done |
| 15-01-T1 | 15-01 | 1 | The recorder REFUSES to write a fixture whose live judge verdict failed | unit | `pytest tests/ -k recorder_refuses_failed_judge` — 1 collected, 1 passed | ✅ done |
| 15-01-T1 | 15-01 | 1 | Fixture round-trip: serialize → deserialize → identical state dict (JSON-safe by construction) | unit | `pytest tests/ -k fixture_roundtrip` — 1 collected, 1 passed | ✅ done |
| 15-02-T1+T2 | 15-02 | 2 | Quality graders are pure `(case, state) -> Grade` over recorded state: grounding, coverage, structure, forced-stop honesty — each with a synthetic fixture that PASSES and one that FAILS (no grader that cannot fail) | unit | `pytest tests/ -k quality_grader` — 26 collected, 26 passed | ✅ done |
| 15-02-T2 | 15-02 | 2 | Grader claim boundaries documented: what each rubric CANNOT catch is stated in its docstring (feeds ADR-0009's claim boundary) | source assertion | `pytest tests/ -k claim_boundary` + `grep -c "Cannot catch:" evals/graders.py` ≥ 5 (baseline 0; measured **6**) — 2 collected, 2 passed | ✅ done |
| 15-03-T2 | 15-03 | 3 | Replay is AUTOMATIC in offline mode: `python -m evals` with fixtures present grades them keyless; CI command unchanged. The replay leg is ALL-MUST-PASS: any failing, errored, broken-file, or orphaned-fixture replay result exits non-zero even when the shared pass rate clears 0.9 (baseline: `summarise` ok is rate-only — 12 green + 1 red replay = 92.3% would exit 0) | integration (offline) | `ANTHROPIC_API_KEY="" .venv/bin/python -m evals` exits 0 (pre-recording) + `pytest tests/ -k "replay or orphaned"` — 13 collected, 13 passed; keyless CLI exits 0 at **41/41** with the recorded case replayed | ✅ done |
| 15-03-T1 | 15-03 | 3 | Model-mismatch HARD gate: `fixture.models.pipeline != graph.MODEL` fails replay deterministically and (via the all-must-pass rule) exits non-zero; the gate's docstring states its own cannot-catch boundary (graph.MODEL only today; per-node models — Phase 16's independent critic — need map+gate extension and re-recording); age prints but never gates (calendar determinism) | unit | `pytest tests/ -k model_mismatch_gates` — 1 collected, 1 passed; and exercised on the REAL committed fixture: flipping its `models.pipeline` to `claude-sonnet-4` makes the keyless CLI exit **1** | ✅ done |
| 15-03-T2 | 15-03 | 3 | The caveat rewrite (SC-4): prints recording date/model/sha/age; still states recorded ≠ current-model behaviour; exact wording asserted | unit | `pytest tests/ -k caveat_wording` — 2 collected, 2 passed; the shipped caveat now prints `recorded 2026-08-10 on claude-sonnet-5 (225b06b, 0 days ago)` | ✅ done |
| 15-04-T2+T3 | 15-04 | 4 | Dataset grows 12 → 40 across the taxonomy; every case states what it exists to catch; `no_prior_research` cases exist (baseline 0); adversarial cases use `seeded_notes` under the heavy-overlap rule; authored reports satisfy their own must_mention/must_not_claim pins (grade_case_pins is replay-only) | unit | `pytest tests/ -k dataset_taxonomy` — 7 collected, 7 passed | ✅ done |
| 15-05-T1+T2 | 15-05 | 5 | Cost preview for the record run via `price_for()` — never hardcoded; preview prints before any spend; `--yes` idiom | unit | `pytest tests/ -k record_preview` — 6 collected, 6 passed | ✅ done |
| 15-06-T1 | 15-06 | 6 | ADR-0009: `Accepted` + `Source:` (baseline 8 ADRs → 9); states what the suite may now claim and what it may not — per-grader cannot-catch column AND the staleness gate's own cannot-catch line; DEC-20's caveat principle carried forward | grep gate | `grep -c "0009" docs/adr/README.md` ≥ 2 (baseline 0); Status/Source greps in the ADR; `grep -ci "cannot catch"` ≥ 2 (baseline: file absent; measured **3**). Measured: `Status: Accepted` 1, `Source:` 1, `0009` in `docs/adr/README.md` **5**, in `docs/DESIGN.md` **1**, ADR records 8 → **9**, `DEC-22` in the ADR **0** | ✅ done |
| 15-06-T1 | 15-06 | 6 | README limitation rewritten honestly; CI workflow still keyless (`ANTHROPIC_API_KEY=""` present in ci.yml — baseline 1, must stay) | grep gate | **the plan's gate was vacuous**: `grep -c "twelve live cases are a smoke test" README.md` measured **0**, not the stated baseline 1 — wave 4 had already removed that clause. Honest replacement, measured: `grep -c "Offline evals can't measure answer quality" README.md` 1 → **0**; `grep -c 'ANTHROPIC_API_KEY: ""' .github/workflows/ci.yml` = **1** and ci.yml has zero diffs across the phase | ✅ done |
| 15-06-T2 | 15-06 | 6 | CALIBRATION: one real recorded case (operator-approved spend ~$0.25) — the recorder's first live execution; fixture committed; replay grades it keyless | manual + offline | **DONE 2026-08-10.** `technical-figures` recorded live: previewed $0.2950, measured pipeline $0.2427, 2 judge calls, both verdicts pass, `git_sha` 225b06b matches HEAD, 10 KB fixture committed. Replays green keyless (41/41, exit 0) | ✅ done |
| 15-06-T3 | 15-06 | 6 | The FULL 40-case record run (~$10–16) — operator decision; may be deferred past the phase without blocking it, stated honestly | manual | **DEFERRED, explicitly.** Not run. The operator did not authorise the ~$16.51 (post-calibration quote; $21.06 from 2026-09-01). The machinery is proven end to end by the calibration case; the dataset is ready; the command is one line. Deferral does not block phase closure — the replay leg grades whatever fixtures exist and 1-of-40 is the honest state | ✅ done |

---

## Manual-Only Verifications

| Behavior | Why Manual | Instructions |
|----------|------------|--------------|
| Calibration recording | First live execution of the recorder; real spend (~1 case ≈ $0.25) | Record one case with preview shown; verify the fixture's schema, judge verdict, cost fields against reality; commit it; run keyless replay |
| Full benchmark recording | ~$10–16 of deliberate spend | Operator decides at execution time. The phase is honest if this is deferred: the machinery is proven by the calibration case, and the dataset is ready — record when wanted. VALIDATION must state which happened. |

---

## Validation Sign-Off

- [x] Every gate: `--collect-only` verified, baseline stated, mutation red or honest green
- [x] Offline evals keyless and green with fixtures present — **41/41, exit 0**, the replay leg live
- [x] Suite green plain and armed — **663 / 65** and **727 / 1**; zero new skips across the phase
- [x] `nyquist_compliant: true` set

**Closing measurements (2026-08-10, wave 6):**

| Quantity | Entering the phase | At close |
|----------|-------------------|----------|
| Suite, plain | 563 passed / 65 skipped | **663 / 65** |
| Suite, armed (local PG :54329) | 627 passed / 1 skipped | **727 / 1** |
| Offline evals | 12/12 keyless | **41/41 keyless** (40 behavioural + 1 replayed recording) |
| Golden cases | 12 | **40** |
| Fixtures committed | 0 | **1** |
| `docs/adr/` records | 8 | **9** |
| Golden cases exercising `no_prior_research` | 0 | **1** |
| `ANTHROPIC_API_KEY: ""` in ci.yml | 1 | **1** (zero workflow diffs) |

**One gate in the plan was vacuous and is recorded as such** (row 15-06-T1, README):
the stated baseline of 1 for `twelve live cases are a smoke test` measured **0**, because
wave 4 had already corrected the case count. The honest gate for the claim itself —
`Offline evals can't measure answer quality`, baseline **1** — is the one that moved to 0.

**Approval:** pending
