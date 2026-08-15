---
phase: 20-note-count-bound
plan: 01
subsystem: memory
tags: [note-cap, eviction, four-backend-contract, tie-break, env-knob, keyless-suite]

# Dependency graph
requires:
  - phase: 20-note-count-bound
    plan: "research"
    provides: "the measured clock-collision hazard (14 unique time.time() values per 200 calls), the per-backend eviction mechanics, the Postgres DELETE-subquery shape, and the caller audit this plan re-measured rather than trusted"
  - phase: 12-owner-scoping-and-ttl
    plan: "*"
    provides: "owner as an exact-match bucket ('' is nobody, never a wildcard) and the unconditional TTL sweep inside add() — the two things the cap composes with and must not regress"
  - phase: 13-pgvector-migration
    plan: "*"
    provides: "the local arming DSN at :54329 and CONTRACT_NOTES_TABLE, without which the pgvector eviction SQL would be written but not exercised"
provides:
  - "memory.NOTE_CAP_PER_OWNER_DEFAULT = 100 and memory.note_cap_per_owner() — read per call, <= 0 or unparseable clamps to the default"
  - "cap eviction inside all four add() implementations, owner-scoped, oldest-first, in the fixed order sweep -> insert -> evict"
  - "ChromaMemoryStore metadata now carries an integer `seq`; _sweep() returns (survivors as (id, metadata) pairs, next_seq) instead of None"
  - "tests/test_store_contract.py — _age_notes() and _collide_notes(), the four-backend timestamp forcers, plus _owned() and _ReorderedGet"
  - "four shared cap contract cases, the chroma reordered-get gate, the knob clamp unit tests, and the migration/seed bypass pin"
  - "the measured fact that the 4-arm collision case CANNOT catch a chroma created_at tie-break regression — chromadb 1.4.1's cooperative get() order hides it, which is why the stubbed gate exists"
affects: [20-02, 21, 22]

# Tech tracking
tech-stack:
  added: []  # zero packages; 20-RESEARCH's Package Legitimacy Audit is N/A and stays N/A — no line added to pyproject.toml
  patterns:
    - "A bound enforced at a seam is only a bound for callers who use the seam. Two bulk writers here deliberately do not, so the bypass is pinned as a gate rather than left as folklore three files apart."
    - "When a test forces a condition (a timestamp collision), verify the forcing worked before trusting the assertion that depends on it. Measured 3 distinct stamps before and 1 after, on every arm."
    - "A shared cross-backend suite proves parity only for behaviour the backends' own implementations expose. Where one backend passes by a vendor's undocumented good manners, the shared suite is structurally blind and needs a stubbed single-backend gate beside it."
    - "Clamp direction is a per-knob argument, not a house style. NOTE_TTL_DAYS=0 is meaningful and floors; NOTE_CAP_PER_OWNER=0 is a silent off-switch and falls back."

key-files:
  created: []
  modified:
    - src/research_agent/memory.py
    - tests/test_store_contract.py
    - tests/test_memory_stores.py

key-decisions:
  - "The 4-arm collision case does NOT catch the chroma tie-break regression, and this was measured rather than hoped. Under mutation (c) — chroma sorting the eviction by created_at instead of seq — test_note_cap_tie_break_is_deterministic_when_created_at_collides[chroma] stayed GREEN, because real chromadb 1.4.1 returns get() results in insertion order, so the created_at sort coincides with the seq sort. Only the stubbed reordered-get gate went red. That vacuity is the entire justification for P-06's separate gate, and it is now a measurement in this file rather than a prediction in the plan."
  - "The plan-checker's W1 correction is load-bearing and was verified, not assumed. The reordered-get gate pins time.time via monkeypatch.setattr(vm, 'time', SimpleNamespace(time=...)) — patching memory.py's module reference rather than the global time module, so chromadb's own internals keep a real clock. With the clock pinned, mutation (c) reds deterministically with survivors {note-1, note-3} instead of {note-2, note-3}. Without the pin, the created_at sort would have ordered identically to seq and the gate would have passed over a broken tie-break."
  - "Mutation (b) — gating the brute-force sweep on the cap — reds the pre-existing test_note_ttl on both brute-force arms as well as the new composition case. Reported rather than quietly enjoyed: it means the composition case is not the sole gate for that particular mutant. What the composition case adds is coverage at a NON-DEFAULT cap (test_note_ttl never sets NOTE_CAP_PER_OWNER, so it only ever runs at 100) and with one expired note among live ones rather than everything expired at once."
  - "chroma's _sweep() changed return type from None to tuple[list[tuple[str, dict]], int]. This is not a seam change — _sweep is private, has exactly one caller (add()), and appears in no test. The survivors are carried out as (id, metadata) pairs specifically so the eviction never issues a second get(): a re-fetch would put get()'s undocumented return order back on the critical path, which is the one thing seq exists to avoid."
  - "next_seq is a max over ALL survivors, not over this owner's survivors — one global monotonic counter rather than one per owner. Ordering within an owner is what the eviction needs, and a global max preserves it while needing no per-owner bookkeeping. Legacy rows without seq read 0, which is correct (they genuinely are the oldest) and transient (the 7-day TTL retires them)."
  - "The eviction's pgvector DELETE deliberately inherits the file's existing non-atomicity rather than fixing it. sweep, insert and evict are three separately autocommitted statements, exactly as sweep and insert already were since Phase 12. T-20-04 records the acceptance; fixing it would mean wrapping every backend's sweep in a transaction, which is out of scope and would have arrived as an unreviewed change to shipped behaviour."

# Metrics
duration: 55min
completed: 2026-08-14
status: complete

actuals:
  tokens: 7781     # chars/4 over the realized src+tests diff (31,124 chars)
  tasks: 3
  commits: 3
---

# Phase 20 Plan 01: The per-owner note cap Summary

**One-liner:** Notes gained their second bound — `NOTE_CAP_PER_OWNER`, default 100, enforced oldest-first inside every `add()` and written four separate times, one per backend — with the "byte-identical across json, memory, chroma and pgvector" claim carried by four shared contract cases plus one stubbed gate for the property the shared suite structurally cannot see.

## Measured baselines and deltas

| Gate | Before | After | Delta |
|------|--------|-------|-------|
| Full suite, keyless (`ANTHROPIC_API_KEY="" VOYAGE_API_KEY="" .venv/bin/pytest`) | 773 passed / 67 skipped | **796 passed / 71 skipped**, exit 0 | **+23 passed, +4 skipped** — reconciled item by item below |
| Collected items, keyless | 840 | 867 | +27 added, **0 removed**, 0 renamed |
| `tests/test_store_contract.py`, armed at `:54329` | 101 passed / 1 skipped | **118 passed / 1 skipped** | +17 (13 keyless-capable items + the 4 pgvector arms now running for real) |
| `tests/test_store_contract.py` + `tests/test_memory_stores.py`, keyless | — | 114 passed / 45 skipped | — |
| Offline evals (`.venv/bin/python -m evals --min-pass-rate 0.9`) | 41/41, exit 0 | **41/41 (100% vs 90% required), real `$?` of 0** | unchanged |
| `.venv/bin/ruff check .` and `.venv/bin/ruff check src tests evals` | clean | clean | — (no error introduced at any point in the wave) |

The one remaining skip in the armed contract file is `test_postgres_really_ran_when_ci_said_it_would`, which is `REQUIRE_POSTGRES`-gated and skips locally by design. All four new pgvector arms run armed.

### The +23 and +4, reconciled

The plan claimed "roughly 19 new keyless passes and 4 new pgvector skips, projecting roughly 792 / 71". **The skip claim is exactly right. The pass claim is low by four, and the projection is corrected to the measured 796 / 71.** The gap is not a surprise test: it is that the clamp case was written as six parametrized values rather than the three the plan's arithmetic assumed, and the knob's default and per-call reads got their own functions rather than being folded in.

Reconciliation is not by arithmetic but by `--collect-only` id diff against the branch point (`ccbc7b2`), which reports 27 added and **zero removed or renamed**:

| # | Test | Arms | Keyless | Task |
|---|------|------|---------|------|
| 1 | `test_note_cap_evicts_the_oldest_first` | json, memory, chroma, pgvector | 3 pass + 1 skip | 1 |
| 2 | `test_note_cap_never_crosses_owners` | json, memory, chroma, pgvector | 3 pass + 1 skip | 2 |
| 3 | `test_note_cap_and_ttl_compose_sweep_first` | json, memory, chroma, pgvector | 3 pass + 1 skip | 2 |
| 4 | `test_note_cap_tie_break_is_deterministic_when_created_at_collides` | json, memory, chroma, pgvector | 3 pass + 1 skip | 2 |
| 5 | `test_chroma_cap_eviction_survives_a_reordered_get` | chroma only (import-guarded) | 1 pass | 2 |
| 6 | `test_note_cap_defaults_when_unset` | — | 1 pass | 1 |
| 7 | `test_note_cap_reads_a_valid_override` | — | 1 pass | 1 |
| 8 | `test_a_useless_note_cap_falls_back_to_the_default` | `[0] [-5] [banana] [] [   ] [3.5]` | 6 pass | 1 |
| 9 | `test_note_cap_is_read_per_call` | — | 1 pass | 1 |
| 10 | `test_migration_and_seed_paths_bypass_add_by_design` | — | 1 pass | 3 |

13 contract-file passes + 10 unit passes = **23**. 4 pgvector arms = **4 skips**. 840 + 27 = 867 collected; 867 − 71 = 796. Both sides close exactly.

## What shipped

### Task 1 — the tracer: `81c0bd2`

RED first, and observed: 12 failures before any implementation existed — the three keyless arms of the cap case (`AssertionError: the cap did not physically evict; len() is unfiltered`, `assert 4 == 3`) and all nine knob items (`AttributeError: module 'research_agent.memory' has no attribute 'note_cap_per_owner'`). Then, in `memory.py`:

- `NOTE_CAP_PER_OWNER_DEFAULT = 100` and `note_cap_per_owner()`, read per call. The docstring states P-01's argument in full: why this is `cost_discount_factor()`'s clamp and not `note_ttl_seconds()`'s floor-at-zero, and that an operator who wants no cap does not set the variable.
- `_BruteForceStore.add()` — under the existing lock, after the append: enumerate this owner's indices, drop the excess head. A comment states why no timestamp is consulted — `entries` only grows by append and shrinks by order-preserving filters, so index order **is** insertion order and the tie-break is free by construction.
- `ChromaMemoryStore` — `_sweep()` now returns survivors as `(id, metadata)` pairs plus `next_seq` (a max over survivors' `seq`, absent reading 0, +1). `add()` writes `seq` into metadata and evicts by sorting this owner's survivors-plus-the-new-note on integer `seq`, deleting the excess lowest in one `delete(ids=...)`.
- `PgVectorMemoryStore.add()` — one further `db.execute`: `DELETE ... WHERE id IN (SELECT id ... WHERE owner = %s ORDER BY created_at DESC, id DESC OFFSET %s)`. Owner and cap bound; the only interpolation is the `validate_table_name`-checked `self.table`. It ran against a real server on the first try — 20-RESEARCH Pitfall 4's MySQL-shaped first draft was avoided rather than discovered.

The tracer's own gate was re-run end to end before Task 2 began, per the tracer contract: keyless 3 passed / 1 skipped, armed 4 passed.

### Task 2 — the invariants: `85381e7`

Test-only. **`memory.py` was not modified in this task** — the three properties and the stubbed gate all passed against Task 1's code on their first run, so no defect was found in the eviction blocks and none was fixed. Under this project's discipline that makes the tests suspects, not evidence, which is what the four mutations below are for.

The helpers first: `_age_notes()` and `_collide_notes()`, `_rewind`'s four-backend siblings, each branching per backend (pgvector `UPDATE`, chroma `get`+`update`, brute force under `_lock` then `_persist()`), with the same docstring honesty about reaching past the API on purpose.

### Task 3 — blast radius and the plan gate: `eec66fa`

The caller inventory was **re-measured**, and it matches the plan exactly. `grep -rn "store\.add(" src evals`:

```
src/research_agent/graph.py:368:        store.add(f"[{state['task']}] {notes}", owner=state["owner"])
src/research_agent/recall_golden.py:187:    Deliberately NOT through `store.add()`. That method stamps `created_at`
evals/harness.py:300:            store.add(note, owner="")
```

One production caller; one docstring; one per-case eval seed. `migrate.py` does not appear. A broader `\.add\(` sweep found one surface the plan's list omits: `memory.py:784-785`, the module's own `__main__` demo, which adds two notes to a throwaway JSON store — under any cap and not a `store.add(` token, so nothing follows from it, but recorded rather than silently dropped. `evals/dataset.py`'s two note-seeding cases carry **one** note each, per-case fresh store, so 20-RESEARCH Open Question 2 stays theoretical.

The pin asserts migrate's source contains no `store.add` at all, that `recall_golden`'s source contains it exactly once, **and** that `recall_golden.seed.__doc__` contains it — so the single mention is pinned as the docstring recording the bypass rather than as a call. A bare absence check against `recall_golden` would have been red on day one against entirely correct code.

## Mutation probes — each observed red, then reverted

| # | Task | Mutation | Observed red |
|---|------|----------|--------------|
| 1a | 1 | Chroma eviction block commented out | `test_note_cap_evicts_the_oldest_first[chroma]` only: `the cap did not physically evict`, `assert 4 == 3`. **json and memory stayed green** |
| 1b | 1 | `note_cap_per_owner()` returns the parsed int without the `> 0` clamp | `[0]` and `[-5]` red: `assert -5 == 100`. The other four params stayed green |
| 2a | 2 | Owner filter dropped from the brute-force eviction | `test_note_cap_never_crosses_owners[json]` and `[memory]`, on the bob assertion exactly: `assert set() == {'langgraph bob-1'}` |
| 2b | 2 | Brute-force sweep gated on the owner being at/over cap | `test_note_cap_and_ttl_compose_sweep_first[json]` and `[memory]`: `add() did not sweep the expired note when the owner was under cap`, `assert 3 == 2`. **Also** reds pre-existing `test_note_ttl` on both arms |
| 2c | 2 | Chroma eviction sorts by `created_at` instead of `seq` | `test_chroma_cap_eviction_survives_a_reordered_get` only: survivors `{note-1, note-3}` where `{note-2, note-3}` was required. **The 4-arm collision case stayed GREEN on the chroma arm** |
| 3a | 3 | A comment carrying the `store.add(` token appended to `migrate.py` | `a migration write path now goes through add()`, `assert 'store.add' not in '#!/usr/bin/...pears here\n'` |
| 3b | 3 | A second `store.add(` mention appended to `recall_golden.py` (extra, not in the plan) | `recall_golden should mention store.add exactly once`, `assert 2 == 1` |

Seven mutations for the six the plan named. `memory.py` was byte-restored from a pre-mutation copy after each; `grep -c MUTATION src/research_agent/memory.py` reads 0 and both test files are green at every commit.

### Mutation 2c is the finding, not a formality

The plan asked for the chroma collision-arm outcome to be recorded honestly either way. It stayed **green**.

Under 2c the eviction sorts `owned` by `created_at`. In the 4-arm collision case the survivors reach that sort in chromadb 1.4.1's real `get()` order — which is insertion order — and Python's sort is stable, so with all three timestamps forced identical the list stays `[note-1, note-2, note-3, note-4]` and the correct note is deleted anyway. The backend passes by the vendor's good manners.

In the stubbed gate the same survivors arrive reversed, so the stable sort leaves `[note-2, note-1, note-3]` and `note-2` is deleted. That is the red, and it is only available because `get()` was made to lie **and** the clock was pinned. Either alone would have left the gate green over a broken tie-break:

- Without the reordering, `get()` returns insertion order and any sort agrees with `seq`.
- Without the pinned clock (the plan-checker's W1), `created_at` would have been genuinely increasing and would have re-sorted the reversed list back into insertion order — a green produced by clock granularity rather than by correctness.

W1 was verified rather than trusted: the gate really does replace `memory.py`'s `time` reference for the duration of the three adds, and 2c really does red because of it.

## The collision forcing is non-vacuous, and that was measured

A case that asserts "deterministic under a timestamp collision" is worthless if the collision never happened. `_collide_notes()` was run standalone against all four live backends, counting distinct `created_at` values before and after:

```
memory    distinct before=3 after=1 collided=True
json      distinct before=3 after=1 collided=True
chroma    distinct before=3 after=1 collided=True
pgvector  distinct before=3 after=1 collided=True
```

Worth noting against 20-RESEARCH Pitfall 1: `before=3` on every arm. Three sequential `add()` calls through a real store are slow enough (embedding, a chroma write, a Postgres round trip) that the clock **does** separate them here, unlike the 14-unique-values-per-200-calls figure measured in a tight `time.time()` loop. The collision is therefore genuinely manufactured rather than incidentally reproduced — which is the right way round: the hazard is real at speed, and the test does not depend on hitting it by luck.

## DEC-08 seam evidence, measured

| Claim | Measurement |
|-------|-------------|
| The production caller needed zero changes | `git diff ccbc7b2 HEAD -- src/research_agent/graph.py` is **0 lines** |
| The four abstract signatures are character-identical | `git diff` over `memory.py` contains **no `+` or `-` line matching `def (add\|query\|__len__\|describe)\(`**; the signature lines and `query()`'s four parameter lines are byte-for-byte the base's, only shifted (ABC `add` 202→239, `query` 211→257, `__len__` 222→268, `describe` 226→272) |
| The pre-existing seam tests pass untouched | `test_every_backend_implements_the_contract` and `test_the_graph_only_uses_the_abstract_interface` green at zero edits — their being unmodified IS the evidence |
| The pre-existing note section passes untouched | `test_note_scoping` and `test_note_ttl` green on all four arms at zero edits (and `test_note_ttl` proved its own worth by redding under mutation 2b) |

Per P-04, `add()` still returns `None` on all four backends. Nothing about eviction crosses the seam.

## Docstring re-derivation, and the grep behind it

`grep -n -iE "bound|only|sole|dedup|forever" src/research_agent/memory.py` was run after implementation to find prose this task falsifies. Three places were re-derived:

1. The `MemoryStore` ABC's **"Two properties every backend must implement identically"** → three, with the cap bullet naming the owner scoping, the at-`add()`-time enforcement, and the storage-native tie-break with the reason it is not `created_at`.
2. The ABC's closing paragraph, which ruled out dedup and ended **"The TTL is the bound."** → the dedup refusal is kept verbatim in substance (still true, still in REQUIREMENTS' Out of Scope) and the closing sentence becomes "Expiry and the count cap are the two bounds; there is no third, and no semantic one."
3. Two "keeps the store from growing forever" claims that the cap now shares credit for — the ABC's TTL bullet (now "stops an abandoned identity's notes outliving them") and `_BruteForceStore.add()`'s sweep comment (now states the sweep is unconditional and runs BEFORE the cap check, and that folding them would leave low-volume owners unswept).

`add()`'s abstract docstring gained the three-step order and P-04's "returns nothing about eviction, and why".

No other module makes an expiry-is-the-only-bound claim in code. **`README.md`'s Limitations bullet was not touched** — it is Phase 22's, and its claim is now knowingly false, which is the deliberate transient 20-CONTEXT called for and 20-02 will state.

## Deviations from plan

### [none of Rules 1–4 fired]

No bug, missing critical functionality, blocker or architectural question arose. The plan's Task 2 explicitly invited a defect fix in Task 1's eviction blocks if the invariants revealed one; none did, and `memory.py` is untouched by commits 2 and 3.

### [scope, additive] One extra mutation was run

Mutation 3b (a second `store.add(` mention appended to `recall_golden.py`) is not in the plan. The plan named only the migrate half. The `count == 1` half of the pin was the more delicate assertion of the two, so it was falsified too rather than trusted. Cost: one command.

### [measurement, corrected] The plan's pass arithmetic was low by four

Claimed ≈19 new keyless passes and a projected 792 / 71. Measured **+23 and 796 / 71**. The skip figure (+4) was exactly right. Not corrected by bending tests toward the claim — the clamp case genuinely covers six inputs (`0`, `-5`, `banana`, empty, whitespace-only, `3.5`), each a distinct way an operator's env var goes wrong, and `3.5` in particular pins that a float-looking cap takes the `ValueError` path rather than truncating silently.

### [honest reporting] Mutation 2b is caught by an older test too

Recorded above in key-decisions and the mutation table. The composition case is not the sole gate for the fold-the-sweep-into-the-cap mutant; `test_note_ttl` catches that specific shape as well. The composition case remains the one that holds at a non-default cap and with a mixed live/expired set, which is where `test_note_ttl` cannot reach.

### [not a deviation, stated to be explicit] Nothing outside the wave's three files was touched

`git diff --stat ccbc7b2 HEAD -- src tests` lists exactly `src/research_agent/memory.py`, `tests/test_memory_stores.py` and `tests/test_store_contract.py`. `README.md`, `docs/OPERATIONS.md` and `docs/DESIGN.md` are unmodified — all three are plan 20-02's, in a separate wave. No semantic dedup, no change to recall, the relevance floor or TTL semantics, and no line added to `pyproject.toml`.

## Acceptance criteria, measured

| # | Criterion | Result |
|---|-----------|--------|
| 1 | All four backends enforce the per-owner cap oldest-first at `add()` time, byte-identical on the shared fixture | ✅ four contract cases × four arms; pgvector armed at `:54329`, not merely skipped |
| 2 | Eviction never crosses owners; `''` is its own bucket; the sweep stays unconditional and first | ✅ isolation case with the victim's row deliberately globally-oldest (mutation 2a red); composition case under-cap the whole way (mutation 2b red) |
| 3 | Tie-breaks are storage-native and deterministic under measured collisions, chroma included under a lying `get()` | ✅ collision forcing verified 3→1 distinct on every arm; the stubbed gate red under mutation 2c where the shared suite is blind |
| 4 | The knob clamps per P-01 and reads per call; DEC-08 seam untouched; the bypass pinned | ✅ 10 unit items, mutation 1b red; empty `graph.py` diff and character-identical signatures; pin red under mutations 3a and 3b |
| 5 | Full keyless suite green with reconciled arithmetic; armed contract file green; ruff clean; evals 41/41; every named mutation observed red | ✅ 796/71 reconciled to a zero-removal id diff; 118/1 armed; both ruff invocations clean; 41/41 exit 0; 7 mutations red and reverted |

## Threat register — dispositions discharged

| Threat | Disposition | How |
|--------|-------------|-----|
| T-20-01 Cross-owner eviction | mitigate | Owner-exact predicate in all four eviction blocks; `''` treated as a bucket. Pinned by `test_note_cap_never_crosses_owners` with bob's note written FIRST so it is globally oldest — mutation 2a reds on precisely that assertion |
| T-20-02 `NOTE_CAP_PER_OWNER=0` read literally | mitigate | `<= 0` or unparseable → 100, `cost_discount_factor()`'s clamp. Six-input unit case; mutation 1b reds `[0]` and `[-5]` |
| T-20-03 SQL injection via the table name in the new DELETE | mitigate | Pre-existing `validate_table_name()` in `__init__`; the eviction adds no interpolated value beyond `self.table`, with owner and cap bound. `test_a_bad_pgvector_table_name_is_rejected` unchanged and green |
| T-20-04 Concurrent `add()` racing the eviction | accept | Unchanged exposure: three separately autocommitted statements, the same non-atomicity the Phase 12 sweep has always had relative to the insert. Stated in a comment at the SQL rather than silently inherited |
| T-20-SC Package-manager installs | accept | N/A held: zero packages installed, `pyproject.toml` unmodified |

## What Wave 2 and the verifier need

- **The knob's exact contract for the OPERATIONS row:** `NOTE_CAP_PER_OWNER`, integer, default **100**, read per call. Unset, empty, whitespace-only, non-integer, zero and negative all read as 100 — an operator who wants no cap does not set it. Sits immediately after `NOTE_TTL_DAYS` in the Configuration table.
- **The README bullet is now knowingly false** and was deliberately left alone (Phase 22 owns it). `grep -c` on it is 1 before and 1 after this wave.
- **Anything DESIGN says about note lifecycle needs the whole-file treatment** — notes are bounded by expiry AND count as of this commit, and eviction is a write-path crossing of the owner-isolation boundary that previously only `query()` crossed.
- **One sentence worth carrying into the docs** (20-RESEARCH Open Question 2): the cap applies to eval-seeded notes too, since `evals/harness.py` seeds through `store.add()`. Today's dataset seeds at most one note per case into a per-case fresh store, so it is unreachable — but a future large-corpus case would be silently truncated at 100.
- **Live behaviour is a guarantee, not an observable change.** Production holds 8 notes across 7 sessions; the eviction path is unreachable at today's volumes, and 20-VALIDATION's Manual-Only row is discharged by saying exactly that rather than by a live check that cannot exist.
- **The one property the shared suite cannot see** is now documented in code and measured here: if `chromadb` is ever unpinned from 1.4.1, `test_chroma_cap_eviction_survives_a_reordered_get` is the test that still means something and the 4-arm collision case is the one that will keep passing regardless.

## Self-Check: PASSED

- `src/research_agent/memory.py` — FOUND, contains `note_cap_per_owner` and zero `MUTATION` markers
- `tests/test_store_contract.py` — FOUND, contains all four cap cases plus the reordered-get gate
- `tests/test_memory_stores.py` — FOUND, contains the knob cases plus the bypass pin
- `81c0bd2` — FOUND in `git log`
- `85381e7` — FOUND in `git log`
- `eec66fa` — FOUND in `git log`
