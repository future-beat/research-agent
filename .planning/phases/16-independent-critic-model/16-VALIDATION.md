---
phase: 16
slug: independent-critic-model
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-10
---

# Phase 16 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

A threading-and-honesty phase: one env var, four call sites, a fixture-gate extension, an
ADR that re-derives a decision instead of inheriting it — and, per the USER DECISION
(2026-08-10), the production cutover itself: `CRITIC_MODEL = 'claude-opus-5'` in fly.toml
[env], deployed after the phase PR merges. Almost everything is fake-driven; the live leg
is one post-deploy demo run on the real config (Opus critic), ceiling $0.40.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest; `pythonpath = [".", "src", "tests"]`; no `conftest.py` |
| **Full suite** | `.venv/bin/pytest` (bare — a second `-q` hides the count line) |
| **Evals** | `.venv/bin/python -m evals` — keyless, 41/41 |
| **Real Postgres** | local PG17+pgvector on :54329 (restart with `LC_ALL=C` if down) |

**Measured baselines entering this phase (2026-08-10):**
- Suite: plain **663 passed / 65 skipped**; armed **727 passed / 1 skipped**
- Offline evals: **41/41** keyless
- `CRITIC_MODEL` anywhere in src/: **0** · `critic_model` accessor: **0**
- `CRITIC_MODEL` in fly.toml: **0** (`grep -c CRITIC_MODEL fly.toml`) — the cutover's baseline
- tests/test_deploy_config.py guards pin VALUES on the parsed [env] table
  (POSTGRES_BACKEND_PINS idiom), NOT exhaustive keys — verified at planning: adding a
  CRITIC_MODEL key reds nothing existing
- `call_model` call sites passing a model: **0** (the constant is read inside)
- Fixture models map keys: `{pipeline, judge}` — no `critic` (1 fixture on disk)
- `docs/adr/` records: **9**; ADR-0005 `Status: Accepted` (the pre-named supersession target)
- README limitation "The critic shares the writer's model": present (line ~252)
- PRICES rows: opus-5 and haiku-4-5 exist, UNDATED (safe for exact-cost tests); Sonnet is
  boundary-dated (2026-08-31) and must not appear in exact assertions

**SIXTEEN vacuous gates across seven phases.** `--collect-only` every selector; baselines +
discriminating mutations (or honest green with the recorded reason). Watch for mutations that
go red by an unrelated route.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Criterion | Test Type | Automated Command | Status |
|---------|------|------|-----------|-----------|-------------------|--------|
| TBD | TBD | 1 | `graph.critic_model()` accessor: unset → `MODEL` (byte-equal); set → the env value. Neutral default proven: with CRITIC_MODEL unset, the API payloads, usage records and logs are byte-identical to today | unit | `pytest tests/ -k critic_model_accessor` | ⬜ pending |
| TBD | TBD | 1 | **Four-site threading:** the critic call site's model reaches (a) the API request payload, (b) the tracing span, (c) `record()`/usage attribution, (d) the log line — each asserted separately against a fake capturing all four | unit | `pytest tests/ -k critic_threading_four_sites` | ⬜ pending |
| TBD | TBD | 1 | **The misbilling discriminator:** `CRITIC_MODEL=some-unpriced-name` fires `pricing_unknown` — which can only happen if the threaded name reached `record()`. Every non-critic node still prices as `MODEL` | unit | `pytest tests/ -k critic_misbilling_discriminator` | ⬜ pending |
| TBD | TBD | 1 | Per-node cost attribution: a run with critic=opus-5 (undated row) yields critic calls priced at $5/$25 and writer calls at Sonnet's window rate; Phase 14's multipliers apply once, at the choke point. (Haiku's undated row serves the cheap-arithmetic twin — haiku lives in unit tests ONLY; the live leg is Opus, the real config) | unit | `pytest tests/ -k per_node_attribution` | ⬜ pending |
| TBD | TBD | 2 | Reservation stays flat $0.20 with a DOCUMENTED threshold stated as the ACTUAL production config: Opus-critic typical ≈ $0.18 (the $0.20 estimate stays honest — no resize accompanies the cutover), the 3-call worst case (~$0.28, by design outside the estimate), and the Sept-1 boundary alone lifting typical runs past $0.20 | grep gate + prose review | baselines: 0 occurrences today | ⬜ pending |
| TBD | TBD | 2 | Fixture models map gains `critic`; `build_fixture` writes it; `grade_fixture_current` compares it with **backfill semantics** (`models.get("critic") or models["pipeline"]`) — the existing fixture stays green with CRITIC_MODEL unset and goes stale the moment it is set | unit | `pytest tests/ -k fixture_critic_gate` | ⬜ pending |
| TBD | TBD | 2 | Record-mode stderr line when `judge.model == critic_model()` — fires on collision, silent otherwise. Worded as STATING A FACT (it WILL fire on the chosen production config: judge and critic both claude-opus-5), naming the shared model and ADR-0010, never implying error | unit | `pytest tests/ -k judge_critic_collision_warning` | ⬜ pending |
| TBD | TBD | 3 | ADR-0010: `Accepted`, supersedes ADR-0005 (status-line edit only on 0005); "different job" stands alone; the USER'S critic-stronger-than-writer rationale QUOTED VERBATIM as a new design position; judge==critic recorded as an ACCEPTANCE (verdicts not independent of the critic's family — the honest narrowing of ADR-0005's independence claim); "stronger" for the judge demoted to preference; structured-verdict half carried forward; conclusion: judge stays, critic flips in production (fly.toml, 16-04); ADR-0002 untouched | grep gate | baselines: 9 ADRs → 10; 0005 status line; 0002 zero diffs; `grep "more capable than the writer" 0010` ≥ 1 | ⬜ pending |
| TBD | TBD | 3 | Stale prose fixed everywhere it lives: graders.py:13-17, DESIGN.md:74 (one-line forward ref), the harness docstring + its content-pinning test (test_evals.py:1655) updated TOGETHER | unit + grep | the pinning test passes with the new wording | ⬜ pending |
| TBD | TBD | 3 | README: whole-file pass; the "critic shares the writer's model" limitation **DELETED** (not rewritten); facts living only in deleted prose grepped for and relocated first; the residual one-liner states REALITY (critic on a stronger model than the writer; judge shares the critic's model — ADR-0010); Status list gains the phase 16 entry naming the flip | grep gate | baseline: limitation present → absent | ⬜ pending |
| TBD | TBD | 4 | **The fly.toml pin:** `CRITIC_MODEL = 'claude-opus-5'` in [env], commented like the other vars, guarded by a value pin in tests/test_deploy_config.py in the SAME commit (same-commit rule). Mutations: value change reds ONLY the pin; key delete reds ONLY the pin | unit | `pytest tests/test_deploy_config.py -k critic_model_pin` | ⬜ pending |
| TBD | TBD | 4 | LIVE CUTOVER: the first deploy since v9, from MERGED main, carrying phases 13-16; phase-14's booked smoke passes (non-zero `cost.embedding_usd` in /metrics, /pricing windows + multipliers); one demo run shows critic calls priced at Opus rates ($5/$25) and writer calls at Sonnet's window; pricing_unknown false; /metrics sane; demo still anonymous; ceiling $0.40 | manual | see Manual-Only | ⬜ pending |

---

## Manual-Only Verifications

| Behavior | Why Manual | Instructions |
|----------|------------|--------------|
| Independent critic demonstrated on the REAL config | One paid post-deploy run (typical ≈ $0.18 with the Opus critic; ceiling $0.40, never a second paid run) | After the cutover deploy: one short question through the public demo endpoint with NO auth header (that absence is the anonymity check). From `fly logs`, capture the "model call" lines — critic line model=claude-opus-5 with its cost_usd; writer/researcher/classifier lines model=claude-sonnet-5. Usage: pricing_unknown false, total cost recorded. Haiku appears NOWHERE in the live leg — it stays in unit tests (undated-row arithmetic). |
| Production flip — the cutover IS this phase's deliverable | USER DECISION (2026-08-10): "Use Opus as the critic's model since it has to be more capable than the writer's model." Deploys are manual; the deploy must carry only merged work | `CRITIC_MODEL = 'claude-opus-5'` lands in fly.toml [env] (committed configuration, guarded by test_deploy_config.py). Sequence: phase PR merges → `git checkout main && git pull --ff-only` → `fly deploy -a research-agent` → phase-14's booked smoke (OPERATIONS :556-563) → this phase's verification run → SUMMARY records deploy version, evidence lines, total cost. Phases 13/15 have nothing separately booked (13's live leg done 2026-08-09 pre-deploy on scratch tables; 15 ships nothing in the image). |

---

## Validation Sign-Off

- [ ] Every gate: `--collect-only` verified, baseline stated, mutation red or honest green
- [ ] Suite green plain and armed; offline evals 41/41 keyless with CRITIC_MODEL unset
- [ ] The cutover recorded: deploy version, booked-smoke outcomes, per-node Opus/Sonnet pricing evidence, spend ≤ $0.40
- [ ] `nyquist_compliant: true` set

**Approval:** pending
