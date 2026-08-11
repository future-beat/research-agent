---
phase: 14
slug: real-cost-accounting
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-08-06
reconciled: 2026-08-11
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
| 14-01.T1 | 14-01 | 1 | Multipliers apply at the ONE choke point (`CallUsage.cost_usd`); no second call site. Discount 0.9 × geo 1.1 compose; both default neutral | unit | **4 collected** with the sibling clauses. Probe A (delete `* cost_discount_factor()` from `cost_usd`'s return) → **RED** on the composition test and on the boundary test | ✅ done |
| 14-01.T1 | 14-01 | 1 | Hybrid geo: the multiplier applies ONLY when the response's `usage.inference_geo` says it ran in a billed geo; env sets the rate, the response decides applicability | unit | Probe B (`_geo_factor` returns the multiplier unconditionally) → **RED** on exactly the unmultiplied-response assertion it was aimed at. This row's premise was **falsified by research and improved**: `inference_geo` really is response-observed, so the env var sets only the *rate* and the response decides applicability | ✅ done |
| 14-01.T1 | 14-01 | 1 | `pricing_unknown` unchanged: unpriced model fails loud, never zero, WITH multipliers configured | unit | Probe C (unknown-geo `raise` → `return 1.0`) → **RED**: the `"eu"` call got silently billed, which is the whole failure mode | ✅ done |
| 14-01.T2 | 14-01 | 1 | SC-3: multiplied cost resolves correctly across the 2026-08-31→09-01 boundary; fixed run dates, never today() | unit | **6 collected.** `grep -c "date.today()\|datetime.now()"` in `test_usage.py` / `test_service.py` = **0 / 0**, before and after — the boundary tests use fixed run dates. Probe D (`preview_cost_usd` multiplies) → **RED** | ✅ done |
| 14-02.T1 | 14-02 | 2 | Voyage `total_tokens` captured at the seam (no longer discarded); per-run embedding cost enters the run record | unit | **1 collected**, non-zero. Baselines first: `embedding_tokens` anywhere in `src/` → **0** before the wave | ✅ done |
| 14-02.T1 | 14-02 | 2 | Telemetry honesty: a 0-token Voyage response is recorded as 0 tokens / $0 WITHOUT tripping pricing_unknown, and the docs field says "approximation" | unit | **1 collected.** A 0-token response records 0 tokens / $0 without tripping `pricing_unknown`, and the docs field says *approximation* | ✅ done |
| 14-02.T2 | 14-02 | 2 | RunRecord schema migration: new fields survive `asdict()` INSERTs on a LIVE (pre-existing) table — both PG and SQLite idioms | integration (real PG) | **2 collected** — both arms, PG and SQLite. Probe H (comment out the SQLite `PRAGMA table_info(runs)` probe) → **RED** with `table runs has no column named embedding_tokens`, raised from the INSERT, which is the intended route. `EMBEDDING_COLUMNS` is a module constant so the test reads the names from the DDL — a fourth column cannot be added to the dataclass and forgotten in the probe | ✅ done |
| 14-02.T3 | 14-02 | 2 | Reservation settle sees MULTIPLIED cost (the choke point is upstream of settle) | integration (real PG) | **1 collected.** Written as ratios against an unmultiplied baseline rather than hand-copied prices, so it survives the 2026-08-31 window close. Both failure modes red by construction: double-applying downstream gives 0.25, reading a pre-multiplier number gives 1.0 | ✅ done |
| 14-03.T1 | 14-03 | 3 | `/pricing` additive: `windows.next` nullable across the boundary; multipliers section; Voyage rows; unpriced model → 501 | unit | **2 collected.** Both halves of the 501 gate observed — the same probe returned **501** where the baseline returned a payload | ✅ done |
| 14-03.T2 | 14-03 | 3 | `/metrics` carries embedding spend; totals = model + search + embedding | unit | **2 collected** — both backend params | ✅ done |
| 14-03.T2 | 14-03 | 3 | Demo page badge / RunResponse unchanged in shape (additive only — Phase 12 rollout constraint) | unit | **1 collected** — and this selector **collected zero at plan time**; it now names a real test. Additive only, per the Phase 12 rollout constraint | ✅ done |
| 14-03.T3 | 14-03 | 3 | README "Cost is computed from list prices" rewritten honestly: approximation, telemetry caveat, what is still NOT included | grep gate + prose review | `"Cost is computed from list prices"` **1 → 0**; `telemetry` (case-insensitive) **0 → 1**. The bullet states *approximation, not the invoice* in its first four words and names what is still excluded rather than gesturing at "some things". **Deliberately not mutation-tested**, with the reason recorded: a `>= 1` grep proves nothing when the baseline is not zero, so these gates are baseline-anchored instead | ✅ done |
| 14-03.T3 | 14-03 | 3 | OPERATIONS documents both env vars, the hybrid geo semantics, and the ~1.33 under-reservation threshold as a docs note | grep gate | `COST_DISCOUNT_FACTOR` / `INFERENCE_GEO_MULTIPLIER` / `1.33` in OPERATIONS **0 / 0 / 0 → present**, in a new section stating the hybrid geo semantics as a difference in kind. **Corrected 2026-08-11:** the ~1.33 under-reservation threshold this row records was arithmetic over a $0.15 run against a $0.20 reservation; the v1.1 audit's W2 replaced both figures with the measured $0.21–0.32 band and a $0.30 reservation. The section survives, its numbers do not | ✅ done |

---

## Manual-Only Verifications

| Behavior | Why Manual | Instructions |
|----------|------------|--------------|
| Live smoke after deploy (if this phase deploys) | The hybrid geo path needs one real API response carrying `usage.inference_geo` | **DONE 2026-08-10, Fly release v10** — the booked smoke was carried out by Phase 16's cutover, the next deploy after this phase merged, exactly as planned. `/metrics` → `embedding_usd: 5.3e-05`, **non-zero**: Voyage embedding spend counted in production for the first time, a whole provider no longer missing from the bill. `/pricing` carried `multipliers` (`cost_discount_factor: 1.0`, `inference_geo_multiplier: 1.1` with the honest per-response note), both `windows`, and the embedding rows. Recorded in `16-04-SUMMARY.md`. |

---

## Validation Sign-Off

- [x] Every gate: measured baseline AND recorded mutation (red, or honest green with reason) — every code gate probed; the two docs gates honestly green with the recorded reason (a `>= 1` grep proves nothing off a non-zero baseline, so they are baseline-anchored instead)
- [x] Suite green plain and armed; new skips justified — **529 → 563** plain and **591 → 627** armed across three waves; every delta explained per wave, the two new skips accounted for
- [x] `nyquist_compliant: true` set

**Approval:** reconciled 2026-08-11 during the v1.1 milestone audit closure. The evidence was in the
wave SUMMARYs at execution time; this file was never flipped, which is the audit's P1 finding.

Worth recording: **this phase's own CONTEXT premise was falsified by research, and the design got
better for it.** The plan assumed the geo multiplier was an env-only declaration like the discount.
It is not — the API response reports `usage.inference_geo`, so the env var sets the rate and the
response decides whether it applies at all. An env-only flag would have disagreed with the invoice
in one direction or the other the moment a workspace `default_inference_geo` moved.

**No new ADR, stated rather than left as an absence:** this phase extends DEC-12 rather than
reversing it, so the supersession convention has nothing to apply to.
