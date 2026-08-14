---
phase: 20
slug: note-count-bound
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-14
---

# Phase 20 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest; `pythonpath = [".", "src", "tests"]`; no `conftest.py` |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `.venv/bin/pytest tests/test_store_contract.py tests/test_memory_stores.py` |
| **Full suite command** | `.venv/bin/pytest` (bare) |
| **Estimated runtime** | ~30 seconds full |

**Measured baseline entering this phase (2026-08-14):** 773 passed / 67 skipped keyless
(66 of the skips are the Postgres-gated contract arms — the pgvector eviction arm will
join them and MUST run armed in CI); offline evals 41/41 exit 0; ruff clean.
Baselining this phase found main red: chat.py's import-time `load_dotenv()` leaked real
keys into the test process from `test_graph_smoke` onward. Fixed pre-phase in PR #28
(772 → 773 with the pin test); the keyless property this phase's contract tests rely on
is now structural, not incidental.

---

## Sampling Rate

- **After every task commit:** Run the quick command
- **After every plan wave:** Run the full suite, keyless
- **Before verification:** Full suite green plain; offline evals 41/41 exit 0
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

*(Rows are the researched gate set — the planner assigns Task IDs/Plan/Wave; the executor
fills Status with measured evidence.)*

| Task ID | Plan | Wave | Requirement | Criterion | Test Type | Automated Command / Mutation | Status |
|---------|------|------|-------------|-----------|-----------|------------------------------|--------|
| TBD | TBD | TBD | REQ-note-count-bound | The cap holds as an invariant after every `add()`: writing past `note_cap_per_owner()` evicts oldest-first until the owner's count equals the cap — identical outcome on all four arms | contract (4-arm) | mutation: skip eviction on one backend → that arm reds while the others stay green (proving the arm actually runs the backend it names) | pending |
| TBD | TBD | TBD | REQ-note-count-bound | Eviction never crosses owners: filling owner A past the cap leaves owner B's notes (and the legacy `""` bucket) untouched, all four arms | contract (4-arm) | mutation: drop the owner predicate from the eviction path → the isolation test reds | pending |
| TBD | TBD | TBD | REQ-note-count-bound | Tie-breaking is deterministic and identical when `created_at` collides — the measured hazard: 14 unique `time.time()` values per 200 calls, so a 100-note loop WILL collide. Secondary key per research (list order / BIGSERIAL / explicit `seq` metadata for Chroma) | contract (4-arm) | the eviction-order test writes notes with forced-identical timestamps and asserts which survive, byte-identical across arms; mutation: remove the Chroma `seq` tie-break → the Chroma arm's ordering test reds (or is honestly reported flaky-by-construction and the design revisited) | pending |
| TBD | TBD | TBD | REQ-note-count-bound | Sweep-then-evict composition: the TTL sweep stays UNCONDITIONAL and runs before the cap count — an owner under the cap still gets expired rows physically removed (the existing ttl guarantee must not regress) | contract (4-arm) | the composition case: expired row + full cap + one add → the expired row is gone, the new note is in, exactly cap notes survive; mutation: make the sweep conditional on the cap being hit → the under-cap-ttl test reds | pending |
| TBD | TBD | TBD | REQ-note-count-bound | The knob follows the `cost_discount_factor()` clamp (≤0 or unparseable → default 100), NOT floor-at-zero — a literal cap of 0 would evict the note just written | unit | tests for default / valid override / 0 / negative / garbage; mutation: swap to floor-at-zero → the zero-cap test reds | pending |
| TBD | TBD | TBD | REQ-note-count-bound | The DEC-08 seam is unchanged: `add/query/len/describe` signatures identical; the graph's reach test still passes untouched | structural | the existing seam-reach test stays green with zero edits (honest green — its being untouched IS the evidence) | pending |
| TBD | TBD | TBD | REQ-note-count-bound | Production blast radius stated, not assumed: `researcher_node` is the sole production `add()` caller; migrate.py and recall_golden bypass `add()` by design, so no migration can silently evict — pinned or re-verified, not folklore | structural + grep gate | re-run the caller inventory at execution; if a pin test is cheap (assert migrate.py contains no `store.add`), add it | pending |
| TBD | TBD | TBD | REQ-note-count-bound | Doc surfaces: OPERATIONS config table gains the knob; anything DESIGN says about note lifecycle that this falsifies is fixed; README whole-file pass (test counts will stale); README's notes Limitations bullet UNTOUCHED (Phase 22's) | grep gate + prose review | baseline-anchored greps named at planning; bullet grep count 1 before and after | pending |

---

## Manual-Only Verifications

| Behavior | Why Manual | Instructions |
|----------|------------|--------------|
| Eviction on the live pgvector table | The armed arm proves the SQL; production carries 8 notes across 7 sessions, far under any cap — eviction is unreachable live at today's volumes | State in the SUMMARY that the live bound is a guarantee, not an observable behaviour change; no live check is possible or needed beyond the armed CI arm |

---

## Validation Sign-Off

- [ ] Every gate: measured baseline AND recorded mutation (red, or honest green with reason)
- [ ] Suite green plain AND the pgvector arm green armed (local :54329 or CI)
- [ ] Offline evals 41/41 exit 0
- [ ] `nyquist_compliant: true` set at reconciliation

**Approval:** pending execution.
