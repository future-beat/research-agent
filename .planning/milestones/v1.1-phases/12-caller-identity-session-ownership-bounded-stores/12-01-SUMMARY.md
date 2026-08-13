---
phase: 12-caller-identity-session-ownership-bounded-stores
plan: 01
subsystem: database
tags: [chromadb, contract-suite, transaction, advisory-lock, spend-cap, pgvector]

# Dependency graph
requires:
  - phase: 11-multi-machine-state-and-pooled-postgres
    provides: "The pooled autocommit db.Database, cursor()'s PoolTimeout-first exception ordering, SCHEMA_LOCK_KEY and the single-connection advisory-lock invariant, the shared contract suite with three note arms"
provides:
  - "chromadb==1.4.1 installed by the dev extra (composed, pin unchanged), so CI collects the chroma arm"
  - "The contract notes fixture parametrized over FOUR arms: json, memory, chroma, pgvector — chroma passes locally, never gated on HAS_POSTGRES"
  - "Database.transaction(): one pooled connection, conn.transaction(), a cursor on that same connection — a real transaction on the autocommit pool"
  - "CAP_LOCK_KEY = zlib.crc32(b'research_agent.spendcap') = 11165997, distinct from SCHEMA_LOCK_KEY (3895545195), exported for Wave 2's cap reservation"
  - "tests/test_db_transaction.py — commit-visible, rollback-absent, and xact-scoped advisory lock held-then-freed, proven against real Postgres"
affects: [12-02, 12-03, 12-04, 12-05, 12-06, SC-5]

# Tech tracking
tech-stack:
  added: []  # chromadb==1.4.1 pre-existing in the chroma extra; dev now composes it — no new package, no pin change
  patterns:
    - "Extras compose extras: dev pulls research-agent[chroma] the same way it pulls [service], so a SQLite/JSON deploy still never installs chromadb"
    - "conn.transaction() on an autocommit pool as the scope for pg_advisory_xact_lock — lock release IS transaction exit, on either path"
    - "PoolTimeout/PoolClosed re-raised before the OperationalError retry arm, mirrored from cursor() into transaction()"

key-files:
  created:
    - tests/test_db_transaction.py
  modified:
    - pyproject.toml
    - tests/test_store_contract.py
    - src/research_agent/db.py
    - README.md

key-decisions:
  - "The chroma fixture arm skips ONLY on a genuinely missing chromadb import ('chromadb not installed'), never on HAS_POSTGRES — CI installs dev, so in CI it collects and runs. Locally it also runs, since the dev extra now installs chromadb."
  - "The lock test's held-half is falsifiable: while the transaction is open, a rival connection's pg_try_advisory_xact_lock must return False. Without that assertion, a transaction() that silently stopped opening a transaction would still go green."
  - "test_the_cap_lock_key_is_not_the_schema_lock_key is deliberately NOT Postgres-gated — the property is arithmetic, and gating it would let a keyless local run miss a collapsed-constants edit."
  - "README test count updated 470 -> 480 and ~10s -> ~25s in the same wave that falsified them, per the per-phase README-freshness deliverable."

# Metrics
duration: 13min
completed: 2026-08-05
---

# Phase 12 Plan 01: Chroma into CI + Database.transaction() Summary

**One-liner:** The contract suite now parametrizes four collecting note arms (chromadb reaches CI via a composed dev extra), and `Database.transaction()` gives Wave 2 a real transaction on the autocommit pool for `pg_advisory_xact_lock` under a dedicated `CAP_LOCK_KEY`.

## What was built

### Task 1 — chroma joins the dev extra and the contract suite (commit 0dbf46f)

- `pyproject.toml`: `dev` now lists `research-agent[chroma]`, mirroring how it already composes `[service]`. The `chromadb==1.4.1` pin is untouched and stays in the `chroma` extra — no new package, no altered pin (`git diff` on the commit shows only the composition line plus a comment).
- `tests/test_store_contract.py`: the `notes` fixture params are `["json", "memory", "chroma", "pgvector"]`. The chroma branch builds `ChromaMemoryStore(path=str(tmp_path / "chroma"), collection=CONTRACT_NOTES_TABLE, embedder=embedder)` with the same 5-dim FakeEmbedder as the other arms — no VOYAGE_API_KEY, no Postgres gate. The fixture's existing `yield`/`close()` shape is preserved.
- Verified: `import chromadb` succeeds after `pip install -e '.[dev]'` (baseline: failed on the pre-edit tree); `test_notes_are_recalled` collects under exactly `[json] [memory] [chroma] [pgvector]`; the chroma arm runs **6 passed** (all note contract tests, including empty/ordered).

### Task 2 — Database.transaction() + CAP_LOCK_KEY (commit ea1bb8f)

- `src/research_agent/db.py`: `transaction()` is a `@contextmanager` that checks out one pooled connection, enters `conn.transaction()` (psycopg opens a real transaction even on an autocommit connection), and yields a cursor bound to that same connection. Commit on clean exit, rollback on raise — which is also what releases any `pg_advisory_xact_lock` taken inside, on either path, before the connection returns to the pool. The checkout mirrors `cursor()`: `PoolTimeout`/`PoolClosed` re-raised in an arm placed before the `OperationalError` retry (they subclass it; the comment cites the doubled-wait reason).
- `CAP_LOCK_KEY = zlib.crc32(b"research_agent.spendcap")` = **11165997**, module-level next to `SCHEMA_LOCK_KEY` (3895545195), with the serialise-cap-against-DDL hazard documented at the definition.
- `tests/test_db_transaction.py` (4 tests): clean-exit commits (row visible after), raising body rolls back (row visible *inside* the open transaction, absent after — so the absence is a rollback, not a no-op insert), and the advisory lock is transaction-scoped both ways — a rival connection is refused it while the block is open and takes it without blocking (try_, not blocking form) in a second transaction afterwards, with no unlock ever issued. Key inequality asserted un-gated.

### README correction (commit 1cd461f)

This wave falsified two README claims: "470 tests" (now 480 collected) and "~10s" (the chroma arm's client startup pushes the full suite to ~24s). Both updated. No other README claim is touched — later waves own their own.

## Verification record

| Gate | Baseline (pre-edit tree) | Result |
|------|--------------------------|--------|
| `import chromadb` after `pip install -e '.[dev]'` | ImportError | chromadb 1.4.1 imports |
| notes fixture arms collected | 3 (json, memory, pgvector) | **4** — chroma present in collection IDs |
| `pytest -k chroma` on the contract file | 0 collected | 6 passed |
| `grep -c "def transaction" src/research_agent/db.py` | 0 | 1 |
| `grep -c "CAP_LOCK_KEY" src/research_agent/db.py` | 0 | 1, and 11165997 ≠ 3895545195 asserted by an un-gated test |
| `pytest tests/test_db_transaction.py` armed (:54329) | file absent | 4 passed |
| same, without DATABASE_URL | — | 1 passed, 3 skipped, reason `DATABASE_URL is not set` |
| Full suite, plain | 436 passed / 34 skipped | **443 passed / 37 skipped** |
| Full suite, armed | 469 passed / 1 skipped | **479 passed / 1 skipped** |
| ruff | clean | clean |

**Skip growth fully explained:** plain +7 passed = 6 chroma-arm tests (chromadb now installed locally, no Postgres needed) + 1 key-inequality test; +3 skipped = the three Postgres-gated transaction tests. Armed +10 passed = the same 6 + all 4 transaction tests. Total collected 470 → 480 in both runs.

## Deviations from Plan

None on substance — plan executed as written. One mechanical adjustment: ruff SIM117 required collapsing the rollback test's nested `with pytest.raises(...)` / `with handle.transaction()` into a single combined `with` statement (behaviour identical).

## Self-Check: PASSED

- tests/test_db_transaction.py exists; pyproject.toml, tests/test_store_contract.py, src/research_agent/db.py, README.md modified as claimed
- Commits 0dbf46f, ea1bb8f, 1cd461f all on `gsd/phase-12-caller-identity`
