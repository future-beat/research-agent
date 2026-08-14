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

**Measured at wave 2 close (2026-08-14), re-run in this wave rather than carried from
wave 1:** keyless **796 passed / 71 skipped** (+23 / +4, reconciled item by item in
`20-01-SUMMARY.md` against a zero-removal `--collect-only` id diff); `tests/test_store_contract.py`
armed at `:54329` **118 passed / 1 skipped** (was 101 / 1); offline evals **41/41 (100% vs 90%
required)** with a real `$?` of **0**; `ruff check .` and `ruff check src tests evals` both clean.
The +4 skips are the four new pgvector arms, which skip keyless and run armed.

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
| 20-01-T1 | 20-01 | 1 | REQ-note-count-bound | The cap holds as an invariant after every `add()`: writing past `note_cap_per_owner()` evicts oldest-first until the owner's count equals the cap — identical outcome on all four arms | contract (4-arm) | mutation: skip eviction on one backend → that arm reds while the others stay green (proving the arm actually runs the backend it names) | **MET** — `test_note_cap_evicts_the_oldest_first`, 4 arms, keyless 3 passed / 1 skipped and armed at `:54329` 4 passed (`81c0bd2`). Mutation 1a (chroma eviction block commented out): red on `[chroma]` only — `the cap did not physically evict`, `assert 4 == 3` — with `[json]` and `[memory]` staying green, which is the arm-really-runs-its-backend half. RED was observed before the code existed: 12 failures at the tracer's first run |
| 20-01-T2 | 20-01 | 1 | REQ-note-count-bound | Eviction never crosses owners: filling owner A past the cap leaves owner B's notes (and the legacy `""` bucket) untouched, all four arms | contract (4-arm) | mutation: drop the owner predicate from the eviction path → the isolation test reds | **MET** — `test_note_cap_never_crosses_owners`, 4 arms (`85381e7`), written with bob's note added FIRST so it is globally oldest and a cross-owner eviction must take it. Mutation 2a (owner filter dropped from the brute-force eviction): red on `[json]` and `[memory]` at exactly the bob assertion — `assert set() == {'langgraph bob-1'}` |
| 20-01-T2 | 20-01 | 1 | REQ-note-count-bound | Tie-breaking is deterministic and identical when `created_at` collides — the measured hazard: 14 unique `time.time()` values per 200 calls, so a 100-note loop WILL collide. Secondary key per research (list order / BIGSERIAL / explicit `seq` metadata for Chroma) | contract (4-arm) | the eviction-order test writes notes with forced-identical timestamps and asserts which survive, byte-identical across arms; mutation: remove the Chroma `seq` tie-break → the Chroma arm's ordering test reds (or is honestly reported flaky-by-construction and the design revisited) | **MET, via the row's own alternative** — `test_note_cap_tie_break_is_deterministic_when_created_at_collides` runs 4 arms green, and `_collide_notes()` was verified non-vacuous by measurement (distinct `created_at` before=3 → after=1 on **every** arm). But mutation 2c (chroma sorting the eviction by `created_at` instead of `seq`) left the chroma arm **GREEN**: real chromadb 1.4.1 returns `get()` in insertion order, so a stable sort on collided stamps reproduces `seq` order. That is the row's "honestly reported ... and the design revisited" branch, and the revision is `test_chroma_cap_eviction_survives_a_reordered_get` — a stubbed `_ReorderedGet` plus a pinned clock, which reds under 2c with survivors `{note-1, note-3}` where `{note-2, note-3}` was required. The 4-arm suite is structurally blind here; that gate is not |
| 20-01-T2 | 20-01 | 1 | REQ-note-count-bound | Sweep-then-evict composition: the TTL sweep stays UNCONDITIONAL and runs before the cap count — an owner under the cap still gets expired rows physically removed (the existing ttl guarantee must not regress) | contract (4-arm) | the composition case: expired row + full cap + one add → the expired row is gone, the new note is in, exactly cap notes survive; mutation: make the sweep conditional on the cap being hit → the under-cap-ttl test reds | **MET** — `test_note_cap_and_ttl_compose_sweep_first`, 4 arms (`85381e7`). Mutation 2b (brute-force sweep gated on the owner being at/over cap): red on `[json]` and `[memory]` — `add() did not sweep the expired note when the owner was under cap`, `assert 3 == 2`. Reported rather than enjoyed: 2b **also** reds the pre-existing `test_note_ttl` on both arms, so the composition case is not this mutant's sole gate; what it adds is a NON-default cap and a mixed live/expired set, neither of which `test_note_ttl` reaches |
| 20-01-T1 | 20-01 | 1 | REQ-note-count-bound | The knob follows the `cost_discount_factor()` clamp (≤0 or unparseable → default 100), NOT floor-at-zero — a literal cap of 0 would evict the note just written | unit | tests for default / valid override / 0 / negative / garbage; mutation: swap to floor-at-zero → the zero-cap test reds | **MET** — 10 unit items in `tests/test_memory_stores.py` (`81c0bd2`): default-when-unset, valid override, read-per-call, and a six-input clamp case `[0] [-5] [banana] [] [   ] [3.5]` — one per way an operator's env var goes wrong, `3.5` pinning that a float-looking cap takes the `ValueError` path rather than truncating. Mutation 1b (parsed int returned without the `> 0` clamp): `[0]` and `[-5]` red — `assert -5 == 100` — the other four params green |
| 20-01-T3 | 20-01 | 1 | REQ-note-count-bound | The DEC-08 seam is unchanged: `add/query/len/describe` signatures identical; the graph's reach test still passes untouched | structural | the existing seam-reach test stays green with zero edits (honest green — its being untouched IS the evidence) | **MET, as an honest green** — `test_every_backend_implements_the_contract` and `test_the_graph_only_uses_the_abstract_interface` pass at **zero edits**. Backed by two measurements rather than by the pass alone: `git diff ccbc7b2 HEAD -- src/research_agent/graph.py` is **0 lines**, and the `memory.py` diff contains no `+`/`-` line matching `def (add\|query\|__len__\|describe)\(` — the four signatures are byte-for-byte the base's, only shifted. `add()` still returns `None` everywhere |
| 20-01-T3 | 20-01 | 1 | REQ-note-count-bound | Production blast radius stated, not assumed: `researcher_node` is the sole production `add()` caller; migrate.py and recall_golden bypass `add()` by design, so no migration can silently evict — pinned or re-verified, not folklore | structural + grep gate | re-run the caller inventory at execution; if a pin test is cheap (assert migrate.py contains no `store.add`), add it | **MET** — inventory re-measured at execution (`grep -rn "store\.add(" src evals`): one production caller `graph.py:368`, one docstring `recall_golden.py:187`, one per-case eval seed `harness.py:300`; `migrate.py` absent. A broader `\.add\(` sweep additionally found `memory.py:784-785`'s `__main__` demo, recorded rather than dropped. Pinned by `test_migration_and_seed_paths_bypass_add_by_design` (`eec66fa`), which asserts migrate has none, `recall_golden` has exactly one, **and** that the one is inside `seed.__doc__`. Mutations 3a (a `store.add(` comment appended to `migrate.py`) and 3b (a second mention in `recall_golden.py`) both red |
| 20-02-T1+T2 | 20-02 | 2 | REQ-note-count-bound | Doc surfaces: OPERATIONS config table gains the knob; anything DESIGN says about note lifecycle that this falsifies is fixed; README whole-file pass (test counts will stale); README's notes Limitations bullet UNTOUCHED (Phase 22's) | grep gate + prose review | baseline-anchored greps named at planning; bullet grep count 1 before and after | **MET** — `grep -c NOTE_CAP_PER_OWNER docs/OPERATIONS.md` 0 → **1** (the row beside `NOTE_TTL_DAYS`, carrying the clamp and the eval-seeding sentence); `git diff --stat HEAD -- src tests` **0 lines** across both tasks. DESIGN read end to end and left **untouched** — its Memory section argues retrieval and never claims what bounds the store, so the cap falsifies nothing in it; recorded as a judgement. `grep -c "Notes are bounded by expiry alone" README.md` = **1 before and 1 after**, and the whole README diff is two lines: the test counts `773 → 796`, measured by this task's own keyless run. One unplanned falsification found and fixed: `docs/OPERATIONS.md:609`'s CI block also read `773 tests` |

---

## Manual-Only Verifications

| Behavior | Why Manual | Instructions |
|----------|------------|--------------|
| Eviction on the live pgvector table | The armed arm proves the SQL; production carries 8 notes across 7 sessions, far under any cap — eviction is unreachable live at today's volumes | State in the SUMMARY that the live bound is a guarantee, not an observable behaviour change; no live check is possible or needed beyond the armed CI arm |

**Disposition (wave 2):** discharged exactly as the Instructions specify, and stated in
`20-02-SUMMARY.md` rather than performed. Production holds 8 notes across 7 sessions, so no
owner is within two orders of magnitude of the default cap and no `add()` there can reach the
eviction branch — there is no live check to run, and claiming one would be the dishonest
version of this row. The proof is the armed arm: the four pgvector cap cases ran for real
against `:54329` (contract file 118 passed / 1 skipped; the one skip is the `REQUIRE_POSTGRES`
guard, by design), so the DELETE is exercised against a real server rather than skipped.

---

## Validation Sign-Off

- [ ] Every gate: measured baseline AND recorded mutation (red, or honest green with reason)
- [ ] Suite green plain AND the pgvector arm green armed (local :54329 or CI)
- [ ] Offline evals 41/41 exit 0
- [ ] `nyquist_compliant: true` set at reconciliation

**Approval:** pending execution.
