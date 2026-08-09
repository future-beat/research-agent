---
phase: 14
slug: real-cost-accounting
status: planned
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-06
---

# Phase 14 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

Almost entirely unit-testable by design — the researcher confirmed no network-dependent tests
and no new dependencies. The one schema change (RunRecord fields) needs the real-Postgres arm.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest; `pythonpath = [".", "src", "tests"]`; no `conftest.py` |
| **Full suite** | `.venv/bin/pytest` (bare — a second `-q` hides the count line) |
| **Real Postgres** | local PG17+pgvector on :54329 (running); CI provides one |

**Measured baselines entering this phase (2026-08-06):**
- Suite: plain **529 passed / 63 skipped**; armed **591 passed / 1 skipped**
- `COST_DISCOUNT_FACTOR` / `INFERENCE_GEO_MULTIPLIER` anywhere in src: **0**
- `total_tokens` in the embedder wrapper path: received and **discarded** today
- `/pricing` payload fields: current shape only (no `windows.next`, no multipliers section)
- Fixed-date Sonnet boundary tests in test_usage.py: **4** (SC-3 half-done)
- README "Cost is computed from list prices" limitation: present at 1 occurrence

**FIFTEEN vacuous gates across six phases.** Every gate: measured baseline AND mutation
observed red — or honestly reported green with the reason. A mutation that goes red by an
unrelated route is a false positive for the gate it was meant to test.

---

## Per-Task Verification Map

*(Task IDs assigned at planning, 2026-08-09. Wave column reflects the final 3-wave plan
shape: the two docs rows drafted as wave 4 landed in plan 14-03 wave 3 — no row dropped.)*

| Task ID | Plan | Wave | Criterion | Test Type | Automated Command | Status |
|---------|------|------|-----------|-----------|-------------------|--------|
| 14-01.T1 | 14-01 | 1 | Multipliers apply at the ONE choke point (`CallUsage.cost_usd`); no second call site. Discount 0.9 × geo 1.1 compose; both default neutral | unit | `pytest tests/ -k multiplier_choke_point` | ⬜ pending |
| 14-01.T1 | 14-01 | 1 | Hybrid geo: the multiplier applies ONLY when the response's `usage.inference_geo` says it ran in a billed geo; env sets the rate, the response decides applicability | unit | `pytest tests/ -k geo_applies_by_response` | ⬜ pending |
| 14-01.T1 | 14-01 | 1 | `pricing_unknown` unchanged: unpriced model fails loud, never zero, WITH multipliers configured | unit | `pytest tests/ -k pricing_unknown_survives_multipliers` | ⬜ pending |
| 14-01.T2 | 14-01 | 1 | SC-3: multiplied cost resolves correctly across the 2026-08-31→09-01 boundary; fixed run dates, never today() | unit | `pytest tests/ -k boundary_with_multipliers` | ⬜ pending |
| 14-02.T1 | 14-02 | 2 | Voyage `total_tokens` captured at the seam (no longer discarded); per-run embedding cost enters the run record | unit | `pytest tests/ -k voyage_tokens_captured` | ⬜ pending |
| 14-02.T1 | 14-02 | 2 | Telemetry honesty: a 0-token Voyage response is recorded as 0 tokens / $0 WITHOUT tripping pricing_unknown, and the docs field says "approximation" | unit | `pytest tests/ -k zero_token_response_honest` | ⬜ pending |
| 14-02.T2 | 14-02 | 2 | RunRecord schema migration: new fields survive `asdict()` INSERTs on a LIVE (pre-existing) table — both PG and SQLite idioms | integration (real PG) | `pytest tests/ -k runrecord_schema_migrates` | ⬜ pending |
| 14-02.T3 | 14-02 | 2 | Reservation settle sees MULTIPLIED cost (the choke point is upstream of settle) | integration (real PG) | `pytest tests/ -k settle_sees_multiplied_cost` | ⬜ pending |
| 14-03.T1 | 14-03 | 3 | `/pricing` additive: `windows.next` nullable across the boundary; multipliers section; Voyage rows; unpriced model → 501 | unit | `pytest tests/ -k "pricing_payload or pricing_501"` | ⬜ pending |
| 14-03.T2 | 14-03 | 3 | `/metrics` carries embedding spend; totals = model + search + embedding | unit | `pytest tests/ -k metrics_includes_embedding_spend` | ⬜ pending |
| 14-03.T2 | 14-03 | 3 | Demo page badge / RunResponse unchanged in shape (additive only — Phase 12 rollout constraint) | unit | `pytest tests/ -k payload_additive` | ⬜ pending |
| 14-03.T3 | 14-03 | 3 | README "Cost is computed from list prices" rewritten honestly: approximation, telemetry caveat, what is still NOT included | grep gate (baseline 1 → 0 old phrase) + prose review | ⬜ pending |
| 14-03.T3 | 14-03 | 3 | OPERATIONS documents both env vars, the hybrid geo semantics, and the ~1.33 under-reservation threshold as a docs note | grep gate (baselines 0 today) | ⬜ pending |

---

## Manual-Only Verifications

| Behavior | Why Manual | Instructions |
|----------|------------|--------------|
| Live smoke after deploy (if this phase deploys) | The hybrid geo path needs one real API response carrying `usage.inference_geo` | One demo run; confirm `/metrics` shows embedding spend and cost math unchanged at neutral defaults. DECIDED at planning: this phase **ships with the next deploy** rather than its own — the smoke happens then (recorded in OPERATIONS by 14-03.T3). |

---

## Validation Sign-Off

- [ ] Every gate: measured baseline AND recorded mutation (red, or honest green with reason)
- [ ] Suite green plain and armed; new skips justified
- [ ] `nyquist_compliant: true` set

**Approval:** pending
