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

A threading-and-honesty phase: one env var, four call sites, a fixture-gate extension, and an
ADR that re-derives a decision instead of inheriting it. Almost everything is fake-driven;
the optional live demonstration (one run with a cheap critic) is the only spend.

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
| TBD | TBD | 1 | Per-node cost attribution: a run with critic=opus-5 (undated row) yields critic calls priced at $5/$25 and writer calls at Sonnet's window rate; Phase 14's multipliers apply once, at the choke point | unit | `pytest tests/ -k per_node_attribution` | ⬜ pending |
| TBD | TBD | 2 | Reservation stays flat $0.20 with a DOCUMENTED threshold: the OPERATIONS note states the Opus-critic typical (~$0.18), the 3-call worst case (~$0.28, by design outside the estimate), and that the Sept-1 boundary alone lifts typical runs past $0.20 | grep gate + prose review | baselines: 0 occurrences today | ⬜ pending |
| TBD | TBD | 2 | Fixture models map gains `critic`; `build_fixture` writes it; `grade_fixture_current` compares it with **backfill semantics** (`models.get("critic") or models["pipeline"]`) — the existing fixture stays green with CRITIC_MODEL unset and goes stale the moment it is set | unit | `pytest tests/ -k fixture_critic_gate` | ⬜ pending |
| TBD | TBD | 2 | Record-mode stderr warning when `judge.model == critic_model()` — fires on collision, silent otherwise | unit | `pytest tests/ -k judge_critic_collision_warning` | ⬜ pending |
| TBD | TBD | 3 | ADR-0010: `Accepted`, supersedes ADR-0005 (status-line edit only on 0005); "different job" stands alone; independence = judge ≠ writer's model with judge-vs-critic recorded as a known limit; "stronger" demoted to preference; structured-verdict half carried forward; ADR-0002 untouched | grep gate | baselines: 9 ADRs → 10; 0005 status line; 0002 zero diffs | ⬜ pending |
| TBD | TBD | 3 | Stale prose fixed everywhere it lives: graders.py:13-17, DESIGN.md:74 (one-line forward ref), the harness docstring + its content-pinning test (test_evals.py:1655) updated TOGETHER | unit + grep | the pinning test passes with the new wording | ⬜ pending |
| TBD | TBD | 3 | README: whole-file pass; the "critic shares the writer's model" limitation **DELETED** (not rewritten); facts living only in deleted prose grepped for and relocated first; Status list gains the phase 16 entry | grep gate | baseline: limitation present → absent; residual one-liner allowed | ⬜ pending |
| TBD | TBD | 4 | LIVE (optional, cheap): one run with `CRITIC_MODEL=claude-haiku-4-5` against the live service or locally with real keys — per-node attribution visible in the run's usage; record-or-defer stated | manual | see Manual-Only | ⬜ pending |

---

## Manual-Only Verifications

| Behavior | Why Manual | Instructions |
|----------|------------|--------------|
| Independent critic demonstrated | One paid run (~$0.15–0.25 with a haiku critic) | Set `CRITIC_MODEL=claude-haiku-4-5` locally with real keys, run one question, verify the usage record prices critic calls at haiku rates and writer calls at Sonnet rates; unset and confirm byte-identical-to-today behaviour returns. May be deferred; state which happened. |
| Production flip | Operator decision | NOT this phase's to make. `CRITIC_MODEL` unset in production keeps today's behaviour exactly. |

---

## Validation Sign-Off

- [ ] Every gate: `--collect-only` verified, baseline stated, mutation red or honest green
- [ ] Suite green plain and armed; offline evals 41/41 keyless with CRITIC_MODEL unset
- [ ] `nyquist_compliant: true` set

**Approval:** pending
