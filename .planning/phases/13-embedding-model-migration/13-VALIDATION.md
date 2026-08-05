---
phase: 13
slug: embedding-model-migration
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-06
---

# Phase 13 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

A tooling phase: two migration commands, a golden recall harness, a repaired legacy tool, and
one ADR. Almost everything is testable against the local Postgres; exactly one claim is
live-only (a real Voyage re-embed against Supabase scratch tables).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (`pyproject.toml`); `pythonpath = [".", "src", "tests"]`; no `conftest.py` |
| **Full suite** | `.venv/bin/pytest` (bare — `addopts = "-q"`; a second `-q` hides the count line entirely) |
| **Real Postgres** | local PG17 + pgvector on :54329 (`postgresql://postgres@localhost:54329/postgres`); CI provides one |
| **Fake embedder** | deterministic 5-dim, in `tests/test_memory_stores.py` — the golden harness runs on it locally |

**Measured baselines entering this phase (2026-08-06):**
- Suite: plain **527 passed / 47 skipped**; armed **573 passed / 1 skipped**
- `migrate.py` test coverage: **zero** (grep for `migrate` under tests/ → imports only)
- `PGVECTOR_TABLE` / `VECTOR_DIMENSIONS` env vars: exist in `memory.py` today (cutover surface)
- `VOYAGE_PRICES` in `usage.py`: **0 occurrences** (to be created)
- `docs/adr/` records: **7** (0008 to be created)

**THIRTEEN vacuous gates across five phases.** Every gate below needs a measured baseline AND
a mutation observed red before it is trusted. Phase 12 proved baselines alone are not enough.

---

## Per-Task Verification Map

Task IDs assigned by the planner; drop no row; never rewrite a Criterion or Automated Command
after its gate has run.

| Task ID | Plan | Wave | Criterion | Test Type | Automated Command | Status |
|---------|------|------|-----------|-----------|-------------------|--------|
| TBD | TBD | 1 | `migrate.py` legacy path REPAIRED: notes migrate with `owner` and `created_at` preserved (not orphaned to `''` / TTL-restarted); sessions keep `owner` | integration (real PG) | `pytest tests/ -k migrate_preserves_owner` | ⬜ pending |
| TBD | TBD | 1 | The repaired legacy path is PROVEN: SQLite→Postgres round trip with row counts and field equality asserted | integration (real PG) | `pytest tests/ -k migrate_legacy_roundtrip` | ⬜ pending |
| TBD | TBD | 2 | Golden recall set: deterministic, checked in, includes owner-scoped queries, tie-free by construction | unit | `pytest tests/ -k golden_set` | ⬜ pending |
| TBD | TBD | 2 | Copy-only migration: server-side `INSERT..SELECT`; SQL join proves `embedding::text` equality keyed on `(text, owner, created_at)` with join-count == row-count | integration (real PG) | `pytest tests/ -k copy_fidelity` | ⬜ pending |
| TBD | TBD | 2 | Copy-only recall: golden-query results IDENTICAL under exact scan (`SET LOCAL enable_indexscan = off`) — SC-5's infrastructure half | integration (real PG) | `pytest tests/ -k copy_recall_identical` | ⬜ pending |
| TBD | TBD | 2 | Index sanity separate from fidelity: HNSW on the new table returns the same result SET at this corpus size (honest set-equality, not order) | integration (real PG) | `pytest tests/ -k index_sanity` | ⬜ pending |
| TBD | TBD | 3 | Re-embed path: batches through the embedder seam into a new table at the new dimension; owner/created_at carried | integration (real PG, fake embedder) | `pytest tests/ -k reembed_carries_tenancy` | ⬜ pending |
| TBD | TBD | 3 | Cost preview: exact token count via `count_tokens`, priced from effective-dated `VOYAGE_PRICES` in `usage.py`; `pricing_unknown` fails loud, never zero | unit | `pytest tests/ -k voyage_pricing` | ⬜ pending |
| TBD | TBD | 3 | Preview always prints; **`--yes` required to spend** — no flag combination silently embeds | unit | `pytest tests/ -k preview_requires_yes` | ⬜ pending |
| TBD | TBD | 3 | Dimension ceiling: re-embed refuses `output_dimension > 2000` loudly (pgvector HNSW limit vs voyage-3.5's 2048) | unit | `pytest tests/ -k dimension_ceiling` | ⬜ pending |
| TBD | TBD | 3 | SC-4: the loud dimension check on recall STILL fires — no silent coercion crept in | unit | `pytest tests/ -k dimension_check_still_loud` | ⬜ pending |
| TBD | TBD | 4 | Cutover: `PGVECTOR_TABLE` flip is the whole cutover; old table survives; pointing back is rollback — proven both directions | integration (real PG) | `pytest tests/ -k cutover_reversible` | ⬜ pending |
| TBD | TBD | 4 | ADR-0008 exists, `Accepted`, `Source:` line (not `Promoted from:`), records what survives of DEC-10 and what supersedes it; index row added | grep gate | baselines: 7 ADRs today, `Source:` count in 0008 == 1 | ⬜ pending |
| TBD | TBD | 4 | README: the "Changing embedding model means a new pgvector table" limitation rewritten honestly (the path exists now; the check is still loud) | grep gate | baseline: current phrase present today at 1 occurrence | ⬜ pending |
| TBD | TBD | 5 | LIVE: one real Voyage re-embed against Supabase scratch tables — created, migrated, verified, dropped; cost preview shown before spend; actual cost recorded | manual | see Manual-Only Verifications | ⬜ pending |

---

## Wave 0 Requirements

- [ ] Local Postgres on :54329 running (`pg_ctl` from the scratchpad instance; `LC_ALL` set)
- [ ] No new packages — voyageai 0.5.0 already pinned; `count_tokens` verified present
- [ ] Golden set fixture checked in, deterministic, tie-free

---

## Manual-Only Verifications

| Behavior | Why Manual | Instructions |
|----------|------------|--------------|
| Live re-embed demonstration | Needs real Voyage spend (~cents) and the prod-shaped Supabase | Scratch source table seeded with a handful of owner-scoped notes → preview printed (record it) → `--yes` → verify tenancy + recall on the scratch target → drop both scratch tables → record actual billed tokens vs preview |
| First `count_tokens` call fetches the HF tokenizer (network) | One-time cache behaviour | Note the fetch in the demo log; confirm subsequent calls are offline |

The live demo does NOT touch the production notes table. No production model flip in this
phase — that is an operator decision the tooling now makes possible.

---

## Validation Sign-Off

- [ ] Every gate has a measured baseline AND a recorded mutation observed red
- [ ] Suite green plain and armed; every new skip justified
- [ ] The live demo ran once, scratch tables dropped, preview-vs-actual recorded
- [ ] `nyquist_compliant: true` set

**Approval:** pending
