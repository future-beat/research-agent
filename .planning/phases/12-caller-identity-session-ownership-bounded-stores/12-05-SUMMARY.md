---
phase: 12-caller-identity-session-ownership-bounded-stores
plan: 05
subsystem: memory
tags: [note-scoping, prompt-injection, ttl, contract-suite, chroma, pgvector, structural-gate]

# Dependency graph
requires:
  - phase: 12-caller-identity-session-ownership-bounded-stores
    plan: 01
    provides: "The four-arm notes fixture -- chromadb reaching CI through the composed dev extra is what makes SC-5's fourth arm a real test rather than a promise"
  - phase: 12-caller-identity-session-ownership-bounded-stores
    plan: 04
    provides: "caller_identity() as the one place an identity is read, the owner already resolved in all four run-starting handlers, and the extended route-guard walker this wave regression-tests"
provides:
  - "MemoryStore.add(text, owner='') / query(..., owner='') across json, memory, chroma and pgvector, with exact-match owner semantics (owner='' is a real value, never a wildcard)"
  - "NOTE_TTL_DAYS (default 7): lazy filter in query() plus opportunistic sweep in add(), identical on all four backends"
  - "pgvector research_notes.owner, migrated by ADD COLUMN IF NOT EXISTS inside the existing advisory-locked lazy DDL; created_at was already there"
  - "AgentState['owner'], initial_state(task, owner='') and followup_state(previous, question, owner='') with carry-forward"
  - "researcher_node scoping BOTH recall and write to state['owner'] -- the cross-visitor prompt-injection fix"
  - "tests/test_store_contract.py note_scoping + note_ttl over all four note arms (SC-5 made literally true)"
  - "A behavioural cross-visitor gate over /research AND /research/stream, plus a structural gate that every run construction carries an owner"
affects: [12-06, SC-5, REQ-store-lifecycle-and-ownership]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Move the line, not the note: a TTL test sets NOTE_TTL_DAYS=0 rather than forging a timestamp in four different storage layouts -- and proves the backends read the setting rather than a hardcoded seven"
    - "Post-filter the TTL in Python on every backend, including chroma where a metadata $gt exists: one implementation of the comparison per store is what keeps four backends observably identical"
    - "Sweep asserted on len(), which is unfiltered everywhere -- against query() alone a lazy filter is indistinguishable from a sweep, and only one of them bounds the store"
    - "A structural gate reads the parsed CALL, not the handler source: three of four handlers pass owner= to something else as well, so a substring gate stays green when the thing it guards is deleted"

key-files:
  created: []
  modified:
    - src/research_agent/memory.py
    - src/research_agent/graph.py
    - src/research_agent/service.py
    - tests/test_store_contract.py
    - tests/test_service.py
    - tests/test_supervisor_routing.py
    - README.md
    - docs/OPERATIONS.md
    - .env.example

key-decisions:
  - "owner='' is an exact value on every backend, never 'empty means all'. The two orphaned notes therefore match nobody the moment the code ships, and are physically collected by the TTL rather than by a migration script."
  - "No dedup, as RESEARCH recommended and CONTEXT ratified: it is one unique index in pgvector and four hand-rolled approximations elsewhere, which is exactly the 'backends quietly disagree' failure SC-5's suite exists to prevent. The TTL is the bound."
  - "TTL evaluated by the database on pgvector (now() in the predicate) and by Python on the other three -- the same split the session store made, for the same reason: two machines must not disagree about what has expired."
  - "Chroma ids became uuids. Once a sweep can shrink the collection, count() is no longer monotonic, so the old f'note-{count}-{hash(text)}' could reproduce a live id -- and chroma treats a repeated id as an upsert, silently overwriting a note instead of adding one."
  - "The service passes limits.caller_identity(request), not request.state.identity as the plan's gate spelled it. 12-03 established caller_identity() as the single place an identity is read (it also carries the never-fall-back-to-client_ip reasoning); reaching around it would reinstate a second reader."
  - "The behavioural injection gate is parametrized over /research AND /research/stream because the demo page uses the streaming route -- with only the blocking route covered, deleting the stream route's owner stayed green."

# Metrics
duration: 41min
completed: 2026-08-05
---

# Phase 12 Plan 05: Note scoping, the 7-day note TTL, and the injection fix Summary

**One-liner:** Notes stopped being communal — every backend now recalls only the caller's notes and forgets them after seven days, identically, proven by a four-arm behavioural suite in which the chroma arm collects and passes — and the identity threaded from the cookie through `AgentState` into `researcher_node` closes the path by which one visitor's text reached another visitor's critic.

## What was built

### Task 1 — owner and a 7-day TTL on all four note backends (commit 27e46bc)

- **The ABC changed shape**: `add(text, owner="")` and `query(..., owner="")`. The default keeps the REPL, the `__main__` demo and the eval harness compiling; the service always passes a real identity. The `MemoryStore` docstring now states the two properties every backend must implement *identically*, because that is the whole content of SC-5 and it is not visible from any one implementation.
- **Owner matching is exact.** `owner=""` retrieves only `owner=""` notes. Pre-Phase-12 rows carry the empty owner, identities are 32-hex uuids, so those notes belong to nobody from the moment this ships — claim-by-nobody-and-expire, as RESEARCH recommended, with no migration script.
- **`NOTE_TTL_DAYS`** (default 7, matching `SESSION_TTL_DAYS`) is read per call. A lazy filter in `query()` makes expiry immediate; an opportunistic sweep in `add()` is what stops the store growing forever. Notes are write-once, so `created_at` *is* last activity and the "after creation" / "after inactivity" distinction that sessions had to be careful about does not arise here.
- **Per backend.** `_BruteForceStore` entries gain `owner` and `created_at` keys — legacy JSON entries have neither, read as `owner=""` and `created_at=0`, and are collected by the next write. Chroma carries both in `metadatas`, filters owner with `where={"owner": owner}` and the TTL in Python. pgvector gets `ALTER TABLE ... ADD COLUMN IF NOT EXISTS owner TEXT NOT NULL DEFAULT ''` plus an owner index appended to the existing advisory-locked lazy DDL, so both machines can run it and only one does; `created_at` was already there and is **not** re-added.
- **The TTL interval is a bound parameter, not interpolated**, even though it comes from an environment variable rather than from a caller. This class already validates the one thing it does interpolate (the table name) for exactly that reason.
- **Two contract tests over all four arms.** `test_note_scoping` writes three notes with *identical* embeddings — the distinguishing word is outside the fake embedder's vocabulary — so similarity cannot be what separates them; drop the owner filter anywhere and a single-owner query returns all three. It asserts both directions per arm, plus `owner=""` isolation and that an identity which wrote nothing recalls nothing. `test_note_ttl` produces age by moving the line rather than the note (`NOTE_TTL_DAYS=0`), which needs no reach into four storage layouts and additionally proves each backend reads the setting rather than a hardcoded seven; it separates filter from sweep by asserting on unfiltered `len()` and then on the note *staying gone* once the TTL is widened back out.

### Task 2 — the owner threaded from the cookie to the note store (commit bb9e80f)

- `AgentState` gains `owner`; `initial_state(task, owner="")` and `followup_state(previous, question, owner="")` carry it. A follow-up belongs to whoever is asking and falls back to the previous turn's owner when nobody is named, which keeps REPL chaining working. `previous` is read with `.get` because pre-Phase-12 state blobs are live rows with no owner key.
- `researcher_node` scopes **both** ends: `store.query(..., owner=state["owner"])` and `store.add(..., owner=state["owner"])`. The comment at that line states the attack rather than the mechanism, because the mechanism is obvious and the reason is not: recalled notes are pasted verbatim into the researcher prompt, the researcher's output becomes the draft, and the critic reviews that draft — so text one visitor caused to be written was untrusted input on another visitor's path to `APPROVED`.
- All four run-starting handlers pass the identity they already resolve for the session owner and the spend reservation. In `/research` and `/research/stream` the `owner = limits.caller_identity(request)` line moved above the state construction.
- **Gates.** A unit assertion in `tests/test_supervisor_routing.py` (which owns the state constructors) covers the default, the explicit owner, the follow-up carry-forward and the legacy-blob path. A behavioural test in `tests/test_service.py` runs three real runs — Alice twice, Bob once, same question, one shared note store — and asserts Alice recalls her own note, Bob recalls nothing, and `len(graph.memory()) == 3`, so Bob's zero is isolation rather than an empty backend. A structural test asserts every `initial_state`/`followup_state` **call** carries an owner.

### Task 3 — the walker and the metrics invariant, re-verified (no code change)

Everything this task asks for already exists and passes after the owner threading; the plan named it a regression gate, not new production code, and adding a fifth assertion that restates a green one would be noise. What was done instead was to mutate all four:

- `len(/sessions routes) >= 6`, still 6, and it trips when the walker stops recursing.
- Every session-group route carries `require_session_access`, **and** `sessions_router.dependencies` is asserted directly — 12-04's finding, still red under the router-level deletion.
- Ask routes carry `guard` and not the session dependency — red when the dependency is attached.
- No session route acquires the spend cap. Note that the plan's wording (`check_daily_cap`) names a function 12-03 retired; the live assertion is stronger, covering both ways the cap can now be acquired (the `guard` dependency and an in-handler `reserve_or_429`), and it is red when `guard` is attached to a read.
- The cross-backend byte-identical metrics assertion passes unchanged under Postgres.

## Verification record

| Gate | Baseline (measured on this tree, 2026-08-05) | Result |
|------|---------------------------------------------|--------|
| `note_scoping` collected arms | 0 (test absent); `notes` fixture params 4 since 12-01 | **4** — json, memory, **chroma**, pgvector |
| `note_scoping` / `note_ttl`, armed | — | **8 passed** (2 tests × 4 arms) |
| same, plain | — | 6 passed, **2 skipped** — the two pgvector arms, `DATABASE_URL is not set` |
| `grep -c "def add" memory.py` | 4 | **4**, every one now carrying `owner` |
| `grep -c "ADD COLUMN IF NOT EXISTS owner" memory.py` | 0 | **1** |
| `grep -c "ADD COLUMN IF NOT EXISTS created_at" memory.py` | 0 | **0** — it already exists, as the interface note said |
| `grep -c "owner=state\[.owner.\]" graph.py` | 0 | **2** — query and add |
| `/sessions` route objects in the walker | 6 | **6**, floor still `>= 6` |
| existing note contract tests (recall/order/top_k/floor/describe) | green on 4 arms | green on 4 arms |
| `pytest tests/test_store_contract.py` armed | — | **100 passed** |
| Full suite, plain | 506 passed / 45 skipped | **516 passed / 47 skipped** |
| Full suite, armed (`:54329`) | 550 passed / 1 skipped | **562 passed / 1 skipped** |
| ruff | clean | clean |

**Delta fully explained.** Collected 551 → **563**, +12 in both arms.

- Task 1: 2 contract tests × 4 arms = 8. Plain **+6 passed / +2 skipped**; armed **+8 passed**.
- Task 2: 1 state unit test + 1 behavioural test × 2 route params + 1 structural test = **+4 passed** in both arms.
- Plain +10 = 6 + 4 ✓. Armed +12 = 8 + 4 ✓.

**The two new plain skips are named and justified**: they are the pgvector arms of `note_scoping` and `note_ttl`, skipping on `DATABASE_URL is not set`. They are not a coverage gap — both run green under the armed run and in CI, which is where the backend that actually serves the deployment gets proven, and a green plain run was never evidence that pgvector's owner column and server-side TTL work. The chroma arm is deliberately **not** in this list: it collects and passes in both runs, which is the difference between SC-5 being true and SC-5 being claimed.

## Falsification checks

Every gate this plan touches was mutated and observed. Seventeen mutations, all reverted; `diff` confirmed the tree byte-identical after each batch.

| Mutation | Expected red | Observed |
|----------|--------------|----------|
| Drop the owner filter from `_BruteForceStore.query` | `note_scoping[json,memory]` | 2 failed |
| Drop the TTL filter from `_BruteForceStore.query` | `note_ttl[json,memory]` | 2 failed |
| Drop the sweep from `_BruteForceStore.add` | `note_ttl[json,memory]` | 2 failed |
| Drop `where={"owner": ...}` from chroma query | `note_scoping[chroma]` | 1 failed |
| Drop the chroma TTL post-filter | `note_ttl[chroma]` | 1 failed |
| Drop the chroma sweep | `note_ttl[chroma]` | 1 failed |
| Drop `AND owner = %s` from pgvector | `note_scoping[pgvector]` | 1 failed |
| Drop the pgvector TTL predicate | `note_ttl[pgvector]` | 1 failed |
| Drop the pgvector sweep DELETE | `note_ttl[pgvector]` | 1 failed |
| `researcher_node` recall unscoped | injection gate | 2 failed |
| `researcher_node` write unscoped | injection gate | 2 failed |
| `AgentState`/`initial_state` lose the owner key | state + injection gates | 3 failed |
| `followup_state` drops the carry-forward | state gate | 1 failed |
| `/research` drops `owner=` | injection + structural | 2 failed |
| `/research/stream` drops `owner=` | injection + structural | **initially GREEN** — gate extended, then 2 failed |
| `ask` / `ask_stream` drop `owner=` | structural | 1 failed each |
| Delete `sessions_router.dependencies` | walker | 1 failed |
| Attach the session dep to an ask route | walker | 1 failed |
| Attach `guard` to a session read | cap tripwire | 1 failed |
| Walker stops recursing into included routers | non-vacuity floor | 3 failed |
| SQLite-only dialect drift in `summary()` | metrics byte-identical | 1 failed |

Two mutations that did **not** go red, recorded because a mutation that stays green is either a hole or a badly chosen mutation and the difference matters:

- *Renaming a key inside the shared `_summarise` helper* left the metrics byte-identical assertion green. This is correct behaviour, not a hole: the gate compares two backends, and a change that hits both equally is outside what "the two dialects have not drifted apart" can claim. The falsifying mutation is a change to **one** backend's SQL, which is red above.
- *Adding an unread column to the SQLite `totals` query* likewise stayed green, because `_summarise` reads named keys. Same reasoning.

## Deviations from Plan

**1. [Rule 2 — Missing critical control] The injection gate was vacuous against the route the demo actually uses**

- **Found during:** Task 2, falsification pass.
- **Issue:** the plan's end-to-end test, written over `/research` only, stayed **green** when `owner=` was deleted from `/research/stream` — the route the demo page calls. This project's eleventh vacuous gate.
- **Fix:** the behavioural test is parametrized over both routes (the streaming arm reads the trace from the final SSE `result` event), and a structural gate was added covering all four run-starting routes including the two ask routes, which no note test can reach because a follow-up never runs the researcher.
- **Second-order finding:** the obvious form of that structural gate — "the handler source contains `owner=`" — is *also* vacuous, because three of the four handlers pass `owner=owner` to `store.create` or `reserve_or_429` as well. It is written against the parsed state-construction call with balanced parentheses instead, and both mutations are red.
- **Files modified:** tests/test_service.py. **Commit:** bb9e80f

**2. [Rule 1 — Bug] Chroma note ids could collide once a sweep can shrink the collection**

- **Found during:** Task 1.
- **Issue:** ids were `f"note-{count}-{hash(text)}"`. `count()` was monotonic before this wave; with a TTL sweep it is not, so the same text added after an eviction can reproduce a live id — and chroma treats a repeated id as an upsert, silently overwriting a note instead of adding one.
- **Fix:** `uuid.uuid4().hex`, with the reason at the line.
- **Commit:** 27e46bc

**3. [Deliberate] The service passes `caller_identity(request)`, not `request.state.identity`**

- The plan's acceptance gate greps for `owner=request.state.identity`. 12-03 established `limits.caller_identity()` as the single place an identity is read, and it carries reasoning the raw attribute does not (never fall back to `client_ip`; fall back to one shared bucket instead). Reaching around it would create a second reader with different fallback behaviour. The four handlers already had the value in a local `owner`, so the change is `initial_state(question, owner=owner)`. The gate's *intent* — the identity becomes the note owner at the run boundary — is asserted behaviourally and structurally, and both are mutated red.

**4. [Scope] Task 3 produced no code change, and one of its criteria names a retired function**

- All four route-guard assertions and the metrics invariant already exist, pass, and mutate red. The plan's escape hatch ("add an explicit assertion if one is only implicitly covered") did not fire. Separately, its "no session route carries `check_daily_cap`" wording names a function 12-03 removed; the live assertion covers both current ways to acquire the cap and is strictly stronger, so it was left alone rather than rewritten toward a name that no longer exists.

**5. [Rule 1 — Falsified docs] README, OPERATIONS and .env.example**

- README's "Notes grow without bound … every visitor's notes share one store" was false in both halves by the end of Task 1; `NOTE_TTL_DAYS` was undocumented. Also corrected: the opening paragraph's "480 tests", stale since 12-01 updated the Tests section but not the intro. Test count 551 → 563 in both places. **Commit:** 8a8582e
- **Deliberately untouched:** README's "The public demo is rate-limited, not authenticated" bullet. Wave 5 owns it.

**6. [Testing] `tests/test_supervisor_routing.py` is outside the plan's `files_modified`**

- The state-dict assertion the plan asks for belongs with the other `initial_state`/`followup_state` tests, not in the API test file. Putting it in `test_service.py` to respect the file list would have separated it from every test of the same functions.

## A trap worth recording

`addopts = "-q"` is already in `pyproject.toml`, so passing `-q` on the command line makes it **doubly** quiet and pytest prints no `N passed` summary line at all. A run that looks like it produced no result has in fact produced every result except the one you were reading for. Run `.venv/bin/pytest` with no `-q`.

## Requirements

`REQ-store-lifecycle-and-ownership` stays **Pending**, and this is now a deliberate hand-off rather than an incomplete sentence. Both halves of its text are delivered in code — sessions in 12-04, notes here, note behaviour consistent across all four backends and proven by the shared suite. It is 12-06 that carries this requirement in its frontmatter, alongside `REQ-demo-authentication` on which it explicitly depends, and that dependency is only demonstrable at the deployed cutover. Marking it complete here would close it ahead of the thing it is declared to depend on.

## Threat Flags

None. Every row of the plan's register is implemented and gated:

| Threat | Where it is closed |
|--------|--------------------|
| T-12-05-01 cross-tenant note injection | owner scoping in every backend's add/query (9 mutations red) plus the end-to-end A-not-B test over both research routes |
| T-12-05-02 `owner=""` treated as "all" | exact match everywhere; `note_scoping` asserts `owner=""` isolation and that an identity which wrote nothing recalls nothing, on all four arms |
| T-12-05-03 notes immortal and communal | 7-day TTL, lazy filter plus sweep, asserted on unfiltered `len()` and on the note staying gone when the TTL widens |
| T-12-05-04 owner threading drops a guard or moves metrics | four walker assertions and the byte-identical metrics assertion, all mutated red |

No new security surface was introduced: no route, no schema at a trust boundary beyond the `owner` column, and the one new SQL predicate is parameter-bound.

## Self-Check: PASSED

- `src/research_agent/memory.py`, `graph.py`, `service.py`, `tests/test_store_contract.py`, `tests/test_service.py`, `tests/test_supervisor_routing.py`, `README.md`, `docs/OPERATIONS.md`, `.env.example` all exist and are modified as claimed
- Commits `27e46bc`, `bb9e80f`, `8a8582e` all present on `gsd/phase-12-caller-identity`
