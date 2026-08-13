---
phase: 13
slug: embedding-model-migration
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-08-06
signed_off: 2026-08-09
---

# Phase 13 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

A tooling phase: two migration commands, a golden recall harness, a repaired legacy tool, and
one ADR. Almost everything is testable against the local Postgres; exactly one claim is
live-only (a real Voyage re-embed against Supabase scratch tables). **That live claim was
discharged on 2026-08-09** and, as the vacuous-gate discipline predicts, it did not merely
confirm what the local gates already said — see § Live Demonstration below.

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

**Measured on exit (2026-08-09, all three arms):**

| Arm | Entering wave 5 | On exit | Delta |
|-----|-----------------|---------|-------|
| plain (no `DATABASE_URL`) | 529 passed / 61 skipped | **529 passed / 63 skipped** | +2 skipped, 0 new passes |
| armed (`DATABASE_URL` only) | 589 passed / 1 skipped | **591 passed / 1 skipped** | +2 passed |
| armed + `REQUIRE_POSTGRES=1` | 590 passed / 0 skipped | **592 passed / 0 skipped** | +2 passed |

Collected 590 → 592 in every arm: the two tests wave 5 added and nothing else. No pre-existing
test changed state in any arm. **Both new skips are justified** — `frozen_query_embedder_isolates_the_table`
and `zero_reported_tokens_is_a_receipt_not_a_silence` each seed a real pgvector table and drive
the CLI against it; with the database absent there is nothing left for either to assert.

**THIRTEEN vacuous gates across five phases** entering; **sixteen across six** on exit (13-04
found two of its own verify clauses green under mutations that removed the artefact they
existed to require). Every gate below has a measured baseline AND a mutation observed red.
Phase 12 proved baselines alone are not enough, and Phase 13 proved it twice more.

---

## Per-Task Verification Map

Task IDs assigned by the planner; drop no row; never rewrite a Criterion or Automated Command
after its gate has run. **All commands below were re-run on 2026-08-09 against the final tree**
and the recorded result is that run, not the wave's own.

| Task ID | Plan | Wave | Criterion | Test Type | Automated Command | Status |
|---------|------|------|-----------|-----------|-------------------|--------|
| 13-01.2 | 13-01 | 1 | `migrate.py` legacy path REPAIRED: notes migrate with `owner` and `created_at` preserved (not orphaned to `''` / TTL-restarted); sessions keep `owner` | integration (real PG) | `pytest tests/ -k migrate_preserves_owner` | ✅ done — 1 passed; mutations A, B, C′ red |
| 13-01.2 | 13-01 | 1 | The repaired legacy path is PROVEN: SQLite→Postgres round trip with row counts and field equality asserted | integration (real PG) | `pytest tests/ -k migrate_legacy_roundtrip` | ✅ done — 1 passed; mutations A, B, C′, D, E red |
| 13-02.3 | 13-02 | 2 | Golden recall set (built in 13-02.1): deterministic, checked in, includes owner-scoped queries, tie-free by construction | unit | `pytest tests/ -k golden_set` | ✅ done — 1 passed; mutation M5 red |
| 13-02.3 | 13-02 | 2 | Copy-only migration (built in 13-02.2): server-side `INSERT..SELECT`; SQL join proves `embedding::text` equality keyed on `(text, owner, created_at)` with join-count == row-count | integration (real PG) | `pytest tests/ -k copy_fidelity` | ✅ done — 1 passed; mutations M1, M2, M3, M6 red |
| 13-02.3 | 13-02 | 2 | Copy-only recall: golden-query results IDENTICAL under exact scan (`SET LOCAL enable_indexscan = off`) — SC-5's infrastructure half | integration (real PG) | `pytest tests/ -k copy_recall_identical` | ✅ done — 1 passed; mutations M1, M2′, M4 red. **Also proven live** (13-05.1) |
| 13-02.3 | 13-02 | 2 | Index sanity separate from fidelity: HNSW on the new table returns the same result SET at this corpus size (honest set-equality, not order) | integration (real PG) | `pytest tests/ -k index_sanity` | ✅ done — 1 passed |
| 13-03.2 | 13-03 | 3 | Re-embed path: batches through the embedder seam into a new table at the new dimension; owner/created_at carried | integration (real PG, fake embedder) | `pytest tests/ -k reembed_carries_tenancy` | ✅ done — 1 passed; mutation M1 red. **Also proven live** (13-05.1) |
| 13-03.1 | 13-03 | 3 | Cost preview: exact token count via `count_tokens`, priced from effective-dated `VOYAGE_PRICES` in `usage.py`; `pricing_unknown` fails loud, never zero | unit | `pytest tests/ -k voyage_pricing` | ✅ done — 2 passed; mutations P1, P2 red. **Caveat: see § Live Demonstration — "exact" is wrong** |
| 13-03.3 | 13-03 | 3 | Preview always prints; **`--yes` required to spend** — no flag combination silently embeds | unit | `pytest tests/ -k preview_requires_yes` | ✅ done — 1 passed; mutation M3 red. **Also proven live** (13-05.1) |
| 13-03.3 | 13-03 | 3 | Dimension ceiling: re-embed refuses `output_dimension > 2000` loudly (pgvector HNSW limit vs voyage-3.5's 2048) | unit | `pytest tests/ -k dimension_ceiling` | ✅ done — 1 passed; mutations M4, M4′ red |
| 13-03.2 | 13-03 | 3 | SC-4: the loud dimension check on recall STILL fires — no silent coercion crept in | unit | `pytest tests/ -k dimension_check_still_loud` | ✅ done — 1 passed; mutation M2 red, **with the honest reading recorded in 13-03's summary** (pgvector's column type refuses the width first; the check buys an actionable message, earlier) |
| 13-04.1 | 13-04 | 4 | Cutover: `PGVECTOR_TABLE` flip is the whole cutover; old table survives; pointing back is rollback — proven both directions | integration (real PG) | `pytest tests/ -k cutover_reversible` | ✅ done — 1 passed; mutations C1, C2, C3 red |
| 13-04.2 | 13-04 | 4 | ADR-0008 exists, `Accepted`, `Source:` line (not `Promoted from:`), records what survives of DEC-10 and what supersedes it; index row added | grep gate | baselines: 7 ADRs today, `Source:` count in 0008 == 1 | ✅ done — 8 ADRs, `Source:` 1, `Promoted from` 0, `Status: Accepted` 1; mutation A1 red. **Index clause was vacuous — see below** |
| 13-04.3 | 13-04 | 4 | README: the "Changing embedding model means a new pgvector table" limitation rewritten honestly (the path exists now; the check is still loud) | grep gate | baseline: current phrase present today at 1 occurrence | ✅ done — old phrase 0, `embeddings re-embed` 1 in README and 1 in OPERATIONS; mutations O1, O2 red. **Two clauses were vacuous — see below** |
| 13-05.1 | 13-05 | 5 | LIVE: one real Voyage re-embed against Supabase scratch tables — created, migrated, verified, dropped; cost preview shown before spend; actual cost recorded | manual | see Manual-Only Verifications | ✅ done — 2026-08-09; full transcript in 13-05-SUMMARY.md |
| 13-05.2 | 13-05 | 5 | The query vector is not a free variable: `recall_delta` across two tables must not also be comparing two query embeddings | integration (real PG) | `pytest tests/ -k frozen_query` | ✅ done — 1 passed; mutations F1, F2, F3 red |
| 13-05.2 | 13-05 | 5 | A reported token count of 0 is a receipt of zero, not an absent report | integration (real PG) | `pytest tests/ -k zero_reported` | ✅ done — 1 passed; mutation B1 red |

### Gates that were vacuous, recorded rather than rewritten

The convention is that an Automated Command is never rewritten after its gate has run, so the
three clauses 13-04 caught are recorded here beside the commands rather than replacing them.
All three stronger forms are green on the final tree and were each observed red:

| Original clause | Why it was vacuous | The clause that bites | Mutation |
|-----------------|--------------------|-----------------------|----------|
| `grep -q "0008" docs/adr/README.md` | 0008's own prose mentions the number four times, so deleting the index row leaves it green | `grep -cE '^\| 0008 \| \[0008-…\]\(0008-…\) \|.*\| Accepted \| — \|$'` → **1** | A2 |
| `grep -qi "rollback" docs/OPERATIONS.md` | already green at baseline from an unrelated Phase-11 sentence ("The rollback is untested.") | `grep -c "Rollback is pointing back"` → **1** | O3 |
| *(none — acceptance criterion with no clause)* | "the 'deliberately not exercised' claim is gone" was checked by nothing | `grep -c "not exercised" docs/OPERATIONS.md` → **0** | O4 |

---

## Wave 0 Requirements

- [x] Local Postgres on :54329 running (`pg_ctl` from the scratchpad instance; `LC_ALL` set) — `pg_isready` accepting connections
- [x] No new packages — voyageai 0.5.0 already pinned; `count_tokens` verified present **and now executed for real** (13-05.1)
- [x] Golden set fixture checked in, deterministic, tie-free — `recall_golden.GOLDEN_NOTES`, 12 notes / 8 queries, `assert_tie_free` green under both the fake embedder and, live, under real voyage-3.5 and voyage-3.5-lite

---

## Manual-Only Verifications

| Behavior | Why Manual | Instructions | Outcome |
|----------|------------|--------------|---------|
| Live re-embed demonstration | Needs real Voyage spend (~cents) and the prod-shaped Supabase | Scratch source table seeded with a handful of owner-scoped notes → preview printed (record it) → `--yes` → verify tenancy + recall on the scratch target → drop both scratch tables → record actual billed tokens vs preview | ✅ **Done 2026-08-09.** 12 notes seeded at vector(1024) with real voyage-3.5; copy leg **zero delta**; re-embed to voyage-3.5-lite moved 8/8 golden queries; three scratch tables dropped and `pg_tables LIKE 'migration_demo_%'` returned **0 rows**, confirmed twice (app client and `psql`). Predicted 40 tokens, reported 25. |
| First `count_tokens` call fetches the HF tokenizer (network) | One-time cache behaviour | Note the fetch in the demo log; confirm subsequent calls are offline | ✅ **Done.** Cold cache; call 1 **2.378s**, call 2 **0.439s**, identical counts. Each *model* fetches its own tokenizer (voyage-3.5-lite: 1.314s). |

The live demo did NOT touch the production notes table: no executed command names
`research_notes`, and the only production-adjacent reads were catalog queries against
`pg_tables`. No production model flip in this phase — that is an operator decision the
tooling now makes possible. No `fly secrets` command ran; no `fly deploy` ran.

---

## Live Demonstration — what it found that the local gates could not

The reason this row existed. Four things, all recorded with literal output in 13-05-SUMMARY.md:

1. **Two never-executed functions ran for the first time and both worked** —
   `_default_token_counter` (downloads an HF tokenizer) and `_ReembedEmbedder.embed_documents`
   (needs a real Voyage response). Neither had ever been executed by any test in three waves.
2. **The preview over-predicts, and neither token number is an invoice.** Predicted 40,
   reported 25. A single one-word document reported **0** tokens — which nothing that returns
   an embedding can have cost. The criterion above calls the preview's count "exact"; it is
   not, it is an honest **upper bound**, and the code and docs now say so.
3. **`recall_delta` had a second variable in it.** Comparing the live source table with
   *itself* produced a nonzero delta on 2 of 8 queries: `run_golden` embeds each query once per
   table and the real API is not bit-reproducible. Every local gate used a deterministic fake,
   so nothing had ever asked. Fixed with `FrozenQueryEmbedder` and gated (13-05.2).
4. **The connection defaults do not fit an operator laptop.** `PG_POOL_TIMEOUT=2.0` is tuned
   for the in-region Fly machines; the measured pooler handshake from a laptop was 0.43–5.63s,
   so the documented commands fail intermittently before touching data. Recorded in the runbook.

**SC-5, both halves, live:** copy → **zero** delta; re-embed → 8 of 8 golden queries moved, one
of them changing which notes came back. Tie-freedom was re-asserted against the re-embedded
table under voyage-3.5-lite before the ordered comparison was trusted, and it **passed**, so
the delta is reported as a number rather than as unmeasurable. Because the copy leg is zero by
measurement rather than by assertion, that delta is the model's by construction.

---

## Validation Sign-Off

- [x] Every gate has a measured baseline AND a recorded mutation observed red
- [x] Suite green plain and armed; every new skip justified
- [x] The live demo ran once, scratch tables dropped, preview-vs-actual recorded
- [x] `nyquist_compliant: true` set

**Approval:** signed off 2026-08-09 — all five ROADMAP success criteria hold. SC-1/SC-2/SC-4
(plan 03), SC-3 (plans 02+04), SC-5 (plans 02+03+05: copy half zero-delta both locally and
live, re-embed delta isolated by construction and measured live). Four findings from the live
run are carried into the code, the tests and the runbook rather than into a caveat.
