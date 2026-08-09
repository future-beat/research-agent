---
phase: 15
slug: answer-quality-evals
status: draft
nyquist_compliant: false
wave_0_complete: false
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
| 15-01-T2 | 15-01 | 1 | The recorder seam (`capture_state` in `run_case`) captures the fixture schema: per-turn final state + metadata (recorded_at, model, git sha, judge verdicts, measured cost) — proven against a FAKE client, no network | unit | `pytest tests/ -k recorder_captures_schema` | ⬜ pending |
| 15-01-T1 | 15-01 | 1 | The recorder REFUSES to write a fixture whose live judge verdict failed | unit | `pytest tests/ -k recorder_refuses_failed_judge` | ⬜ pending |
| 15-01-T1 | 15-01 | 1 | Fixture round-trip: serialize → deserialize → identical state dict (JSON-safe by construction) | unit | `pytest tests/ -k fixture_roundtrip` | ⬜ pending |
| 15-02-T1+T2 | 15-02 | 2 | Quality graders are pure `(case, state) -> Grade` over recorded state: grounding, coverage, structure, forced-stop honesty — each with a synthetic fixture that PASSES and one that FAILS (no grader that cannot fail) | unit | `pytest tests/ -k quality_grader` | ⬜ pending |
| 15-02-T2 | 15-02 | 2 | Grader claim boundaries documented: what each rubric CANNOT catch is stated in its docstring (feeds ADR-0009's claim boundary) | source assertion | `pytest tests/ -k claim_boundary` + `grep -c "Cannot catch:" evals/graders.py` ≥ 5 (baseline 0) | ⬜ pending |
| 15-03-T2 | 15-03 | 3 | Replay is AUTOMATIC in offline mode: `python -m evals` with fixtures present grades them keyless; CI command unchanged | integration (offline) | `ANTHROPIC_API_KEY="" .venv/bin/python -m evals` exits 0 | ⬜ pending |
| 15-03-T1 | 15-03 | 3 | Model-mismatch HARD gate: `fixture.model != graph.MODEL` fails replay deterministically; age prints but never gates (calendar determinism) | unit | `pytest tests/ -k model_mismatch_gates` | ⬜ pending |
| 15-03-T2 | 15-03 | 3 | The caveat rewrite (SC-4): prints recording date/model/sha/age; still states recorded ≠ current-model behaviour; exact wording asserted | unit | `pytest tests/ -k caveat_wording` | ⬜ pending |
| 15-04-T2+T3 | 15-04 | 4 | Dataset grows 12 → 40 across the taxonomy; every case states what it exists to catch; `no_prior_research` cases exist (baseline 0); adversarial cases use `seeded_notes` | unit | `pytest tests/ -k dataset_taxonomy` | ⬜ pending |
| 15-05-T1+T2 | 15-05 | 5 | Cost preview for the record run via `price_for()` — never hardcoded; preview prints before any spend; `--yes` idiom | unit | `pytest tests/ -k record_preview` | ⬜ pending |
| 15-06-T1 | 15-06 | 6 | ADR-0009: `Accepted` + `Source:` (baseline 8 ADRs → 9); states what the suite may now claim and what it may not; DEC-20's caveat principle carried forward | grep gate | `grep -c "0009" docs/adr/README.md` ≥ 2 (baseline 0); Status/Source/cannot-catch greps in the ADR (baseline: file absent) | ⬜ pending |
| 15-06-T1 | 15-06 | 6 | README limitation rewritten honestly; CI workflow still keyless (`ANTHROPIC_API_KEY=""` present in ci.yml — baseline 1, must stay) | grep gate | `grep -c "twelve live cases are a smoke test" README.md` = 0 (baseline 1); `grep -c 'ANTHROPIC_API_KEY: ""' .github/workflows/ci.yml` ≥ 1 (baseline 1, zero diffs to ci.yml) | ⬜ pending |
| 15-06-T2 | 15-06 | 6 | CALIBRATION: one real recorded case (operator-approved spend ~$0.25) — the recorder's first live execution; fixture committed; replay grades it keyless | manual + offline | see Manual-Only | ⬜ pending |
| 15-06-T3 | 15-06 | 6 | The FULL 40-case record run (~$10–16) — operator decision; may be deferred past the phase without blocking it, stated honestly | manual | see Manual-Only | ⬜ pending |

---

## Manual-Only Verifications

| Behavior | Why Manual | Instructions |
|----------|------------|--------------|
| Calibration recording | First live execution of the recorder; real spend (~1 case ≈ $0.25) | Record one case with preview shown; verify the fixture's schema, judge verdict, cost fields against reality; commit it; run keyless replay |
| Full benchmark recording | ~$10–16 of deliberate spend | Operator decides at execution time. The phase is honest if this is deferred: the machinery is proven by the calibration case, and the dataset is ready — record when wanted. VALIDATION must state which happened. |

---

## Validation Sign-Off

- [ ] Every gate: `--collect-only` verified, baseline stated, mutation red or honest green
- [ ] Offline evals keyless and green with fixtures present
- [ ] Suite green plain and armed; new skips justified
- [ ] `nyquist_compliant: true` set

**Approval:** pending
