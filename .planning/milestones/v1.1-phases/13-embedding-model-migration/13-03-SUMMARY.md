---
phase: 13-embedding-model-migration
plan: 03
subsystem: database
tags: [migration, pgvector, embeddings, pricing, cost-preview, spend-gate, gate-discipline]

# Dependency graph
requires:
  - phase: 13-embedding-model-migration
    plan: 02
    provides: "the `embeddings` subparser set, recall_golden.seed/GOLDEN_NOTES as a 12-note fixture corpus, memory.validate_table_name(), and the dedicated migration_test_notes_* table discipline"
  - phase: 13-embedding-model-migration
    plan: 01
    provides: "a repaired migrate.py that carries owner/created_at, and the (text, owner, created_at) key compared as a datetime rather than an epoch float"
  - phase: 12-caller-identity-session-ownership-bounded-stores
    provides: "owner on the notes schema, the 7-day TTL keyed on created_at, the FakeEmbedder/HAS_POSTGRES test idiom"
provides:
  - "usage.VOYAGE_PRICES — effective-dated Voyage embedding rates in the one pricing home, with voyage_price_for() and preview_cost_usd()"
  - "VoyageEmbedder(output_dimension=) — the seam can now ask for a width"
  - "`python -m research_agent.migrate embeddings re-embed --from OLD --to NEW --model M [--dimensions N] [--batch-size N] [--dry-run] [--yes]`"
  - "main(argv, token_counter=, embedder_factory=) — the injection seam that makes 'nothing was embedded' a counter rather than a code reading"
  - "SC-1, SC-2 and SC-4 mechanically true: tenancy carried, cost previewed before spend, the store's own dimension check firing inside the migration path"
affects: [13-04, 13-05, VALIDATION rows reembed_carries_tenancy / voyage_pricing / preview_requires_yes / dimension_ceiling / dimension_check_still_loud, and 13-04.3 (README) satisfied early]

# Tech tracking
tech-stack:
  added: []  # no packages installed this phase (RESEARCH Package Legitimacy Audit: none)
  patterns:
    - "An injection seam threaded through main() beats monkeypatching module state: it lets the CLI-surface test and the zero-spend assertion be the same test"
    - "A refusal's message needs its own mutation. Mutating the *condition* can go red via an unrelated later failure, leaving the message assertions themselves unfalsified"
    - "pgvector's column type already refuses a width mismatch, so the store's check buys an actionable message and an earlier failure — not the difference between loud and silent"

key-files:
  created: []
  modified:
    - src/research_agent/usage.py
    - src/research_agent/memory.py
    - src/research_agent/migrate.py
    - tests/test_migrate.py
    - README.md

key-decisions:
  - "PriceWindow's payload annotation widened to `Price | float` rather than padding Voyage's flat rate into the four-field Price. covers() is a date comparison and never inspects the payload; the annotation now says what was already true instead of lying about it."
  - "VOYAGE_PRICES_VERIFIED is a module constant, not a date typed into the preview's format string. The preview prints the verification date, and a second hand-typed copy of it is how the two drift."
  - "The price is resolved BEFORE the tokenizer is touched, so an unlisted model costs nothing to discover — no HF download, no Postgres round trip, no embed call."
  - "--dry-run wins over --yes. The two flags contradict each other and the safe reading of a contradiction is the one that spends nothing."
  - "_ReembedEmbedder subclasses VoyageEmbedder to capture the response's total_tokens rather than widening the Embedder protocol. Four backends implement that protocol and none of them has any business knowing about tokens."
  - "--dimensions defaults to 1024 and there is deliberately no per-model default table: that would be a second copy of Voyage's documentation, silently wrong the day a model changes."
  - "The re-embed test asserts idempotence on the SECOND pass, unprompted by the plan. 13-01's mutation E and 13-02's M6 both established that a resume key is only falsifiable once the table is non-empty."

# Metrics
duration: 52min
completed: 2026-08-06
---

# Phase 13 Plan 03: The re-embed path and its money Summary

**One-liner:** `embeddings re-embed` puts an existing corpus through a new model at a new width, carrying every note's owner and original clock, behind a cost preview that always prints, a `--yes` gate proven by counting calls on a fake, and two loud refusals — an unpriced model and a width HNSW cannot index.

## What was built

### Task 1 — `VOYAGE_PRICES` in `usage.py` (commit `c4f5950`)

Beside `PRICES`, in the one pricing home, so Phase 14 finds every rate in one file.

- `VOYAGE_PRICES: dict[str, list[PriceWindow]]` — `voyage-3.5` 0.06, `voyage-3.5-lite` 0.02, `voyage-3-large` 0.18 USD/MTok, each in an unbounded window, verified 2026-08-06 against `docs.voyageai.com/docs/pricing` (URL and date in the comment). Voyage publishes no dated windows, so a future change closes one with `until=` — the Sonnet-5-boundary idiom already in the file.
- `PriceWindow.price` widened to `Price | float`. `covers()` is a date comparison that never inspects the payload, which is precisely why the window is reusable; the annotation now records that rather than contradicting the code. The alternative — padding a flat rate into a four-field dataclass whose other three fields are meaningless — would have made `Price(input=0.06, output=0.0, cache_write_5m=0.0, cache_read=0.0)` a thing someone later reads as a real output price.
- `voyage_price_for()` reuses `UnknownModelPricing` (not redefined) and names both the model and the priced set in its message.
- `preview_cost_usd(total_tokens, model, on=None)` is pure arithmetic. It takes a token count instead of producing one, because Voyage's `count_tokens` downloads a tokenizer from the Hugging Face hub on first call and a multiplication should not need the network to be tested (Pitfall 8).
- `VOYAGE_PRICES_VERIFIED = date(2026, 8, 6)` so the preview prints the verification date from the same place the rates live.

### Task 2 — the seam and the command (commit `9a88ad0`)

**`memory.py`, seam-preserving only.** `VoyageEmbedder.__init__` gains `output_dimension: int | None = None`, passed to `client.embed` in both `embed_documents` and `embed_query`. `None` is voyage's own default, so every existing caller's request is byte-identical to what it sent before. Nothing else in the file changed; `output_dimension` occurs 4 times (baseline 0).

**`migrate.py`, `embeddings re-embed`.** A sibling `sub.add_parser` in the existing `_main_embeddings` parser set, not a new dispatch branch.

1. Table names through `memory.validate_table_name()`; `--from == --to` refused.
2. `--dimensions > 2000` refused **before any DDL and before any spend**, naming pgvector's HNSW ceiling for the `vector` type, voyage-3.5's 2048 option as the reason this is a real mistake rather than a hypothetical one, and `halfvec` as the documented-but-unbuilt path.
3. The price is resolved next, before the tokenizer is touched and long before the database is opened. `UnknownModelPricing` is caught at the command boundary, printed to stderr, exit 2. DEC-12: the run never proceeds at $0.00.
4. Source rows read as `(text, owner, created_at)` ordered by `created_at`; rows already present in the target are skipped on that same key, with `created_at` compared as a **datetime** on both sides — 13-01's lesson, not re-learnt.
5. The preview prints on every invocation: model and width, source row count, notes and tokens to embed, the rate with its verification date, the estimated USD, and an explicit line saying this is list price, that Voyage bills its own count, and that the voyage-4 family's free allowance is not modelled.
6. `--dry-run` stops there and returns 0, creating nothing. Without `--yes`, the preview has already printed and the command exits 2 saying `--yes` is required.
7. Batches of `--batch-size` (default 128, well under Voyage's 1,000-text / 320K-token request limits) go through `embedder.embed_documents`, and **every returned vector goes through the target store's own `_check_dimensions`** — called on the store instance, never reimplemented here (grep: 1 occurrence, baseline 0; no second width comparison exists in the file — the legacy JSON-width `SystemExit` is a different comparison against a different input and stays).
8. Inserts carry `(text, embedding, owner, created_at)`.
9. After the run: predicted vs billed tokens, the billed cost, and the cutover/rollback line naming `PGVECTOR_TABLE` and `VECTOR_DIMENSIONS`.

`token_counter=` and `embedder_factory=` are keyword parameters threaded through `main()` → `_main_embeddings` → `reembed_notes`, defaulting to the real thing. That is what lets the CLI-surface test and the zero-spend assertion be the *same* test: the gate's claim is "no call reached `embed_documents`", and the falsifiable form of that claim is a counter on a fake, not a reading of the code.

### Task 3 — the spend gate's five tests (commit `a7a485a`)

| Test | What it claims |
|------|----------------|
| `test_preview_requires_yes` | exit != 0, the preview (token count and a `$` figure) IS in stdout, `--yes is required` in stderr, zero embed calls, and the target table was never even created |
| `test_preview_prints_before_spend_with_yes` | with `--yes` the preview still prints, rows are inserted, and `cost preview` precedes the first `embedded ` progress line — a cost shown after the money is spent is a receipt |
| `test_dry_run_never_embeds` | `--dry-run --yes` exits 0, embeds nothing, creates nothing |
| `test_dimension_ceiling` | `--dimensions 2048` → exit != 0, stderr names `2000` and `halfvec`, zero embed calls, no target table afterwards |
| `test_reembed_unknown_model_refuses` | `--model voyage-99 --yes` → exit != 0, stderr names the model and quotes no price, zero embed calls |

Plus Task 2's two: `test_reembed_carries_tenancy` (12 golden notes re-embedded from 5 dimensions to 4; `vector_dims` on a row is 4, row count matches, three distinct owners present, per-row `(text, owner, epoch)` equality against the source, and a second pass that re-embeds nothing) and `test_dimension_check_still_loud_in_migration_path` (a 5-dim fake into a `--dimensions 4` run raises the store's ValueError, asserted on its *wording* — `dimensions but the`, `column is vector(` — with zero rows written).

## Gate discipline: eight mutations, all red, two with caveats worth reading

Fifteen vacuous gates across six phases, and the last two were specified by their own plans. Baseline before mutating: **`pytest tests/test_migrate.py` armed = 6 passed** (13-01's and 13-02's), and the seven new tests green.

| # | Mutation | Result | Observed failure |
|---|----------|--------|------------------|
| P1 | `voyage-3.5` rate 0.06 → 0.05 | **RED** | `test_voyage_pricing_arithmetic`: `assert 0.05 == 0.06 ± 6.0e-08` |
| P2 | Delete the `voyage-3.5-lite` row | **RED** | `UnknownModelPricing: No Voyage embedding price for 'voyage-3.5-lite' on 2026-08-06. Priced models: voyage-3-large, voyage-3.5.` |
| M1 | Drop `owner` from the re-embed INSERT column list | **RED** | `test_reembed_carries_tenancy`: `assert {''} == {'', 'alice', 'bob'}` — all twelve notes orphaned |
| M2 | Comment out `target_store._check_dimensions(vector)` | **RED**, but see below | `psycopg.errors.DataException: expected 4 dimensions, not 5` instead of the store's sentence |
| M3 | `--yes` given `default=True` | **RED** | `test_preview_requires_yes`: `assert 0 != 0` — the run proceeded and spent |
| M4 | Ceiling comparison `> 2000` → `>= 2049` | **RED**, but see below | `ValueError: Embedder returned 4 dimensions but the … column is vector(2048)` — red by a different route |
| M4′ | Ceiling intact; `halfvec` removed from its message | **RED** | `test_dimension_ceiling`: `assert 'halfvec' in "error: --dimensions 2048 exceeds …"` |
| M5 | Catch-and-continue on `UnknownModelPricing`, rate 0.0 | **RED** | `test_reembed_unknown_model_refuses`: `assert 0 != 0` — it ran, at $0.00 |

All reverted; each revert verified by re-reading the file against the original text (`restored: True`), `ruff check src tests` clean on the final tree.

**M2 is red, and the reason is not the reason the plan assumed.** Removing the store's check does not produce a silent coercion — it produces `psycopg.errors.DataException: expected 4 dimensions, not 5`, because pgvector's column type refuses the width itself. So the honest statement of what `_check_dimensions` buys in this path is: an **actionable** message (naming the table, the widths, and the fact that an existing table keeps its original width) raised **before** the INSERT, from the same code production uses, rather than a driver-level type error from inside a statement. That is worth having and is what the test pins — it asserts the store's exact wording, which no reimplementation and no database error would satisfy. But "no silent coercion crept in" is true here because of the column type first and the check second, and SC-4 should be read that way rather than as a claim that the check is the only thing standing between the tool and a silently truncated vector.

**M4 went red without falsifying the assertions it was aimed at, which is exactly the failure mode this project keeps finding.** With the ceiling comparison relaxed, the command proceeds to create a `vector(2048)` table and the injected 4-dimensional fake then trips the store's dimension check — so the test raises before reaching `assert "2000" in err` and `assert "halfvec" in err`. Red, but the message assertions were still unproven, and a mutation table that stopped there would have overstated its evidence. **M4′** exists for that: the ceiling check intact, `halfvec` removed from its wording, and the assertion goes red on its own terms. This is the same shape as 13-02's M2/M2′ — the command's later machinery catching a mutation earlier than the gate does — and it is recorded rather than glossed for the same reason.

## Verification

| Check | Baseline | After |
|-------|----------|-------|
| `grep -c "VOYAGE_PRICES" src/research_agent/usage.py` | 0 (and 0 repo-wide) | 4 |
| `grep -c "output_dimension" src/research_agent/memory.py` | 0 | 4 |
| `grep -c "_check_dimensions" src/research_agent/migrate.py` | 0 | 1 |
| Second width comparison for embed output in migrate.py | n/a | none — the legacy JSON `SystemExit` is a different comparison and untouched |
| `voyageai.Client.embed` accepts `output_dimension` in the pinned 0.5.0 | assumed by RESEARCH | **verified by signature inspection** |
| `pytest tests/test_migrate.py -k voyage_pricing` with no `DATABASE_URL`, no `VOYAGE_API_KEY` | tests absent | **2 passed** |
| `pytest tests/test_migrate.py -k "reembed_carries_tenancy or dimension_check_still_loud"` armed | tests absent | **2 passed** |
| `pytest tests/test_migrate.py -k "preview or dry_run or dimension_ceiling or unknown_model"` armed | tests absent | **6 passed** |
| `pytest tests/test_migrate.py` armed | 6 passed | **13 passed** |
| `python -m research_agent.migrate --dry-run` legacy banner | prints, 0 | unchanged (13-01's round-trip test green) |
| `ruff check src tests` | clean | clean |
| Full suite, plain | 527 passed / 53 skipped | **529 passed / 60 skipped** |
| Full suite, armed (`DATABASE_URL` only) | 579 passed / 1 skipped | **588 passed / 1 skipped** |
| Full suite, armed + `REQUIRE_POSTGRES=1` | 580 passed / 0 skipped | **589 passed / 0 skipped** |

**Delta fully explained.** Collected 580 → 589, +9 in both arms: the nine tests this plan adds and nothing else.

- Armed: all nine pass (579 → 588).
- Plain: **+2 passed, +7 skipped** (53 → 60). The two passes are the pricing tests, which take a token count as an argument and touch neither Postgres nor the network — deliberately, since arithmetic that needed a tokenizer download to be tested would be untestable in a gated CI job. The seven skips are the seven Postgres-gated tests, each reporting `DATABASE_URL is not set`. Every one of them asserts rows written to, or refused by, a real pgvector table; none can be simulated.

No pre-existing test changed state in either arm. **The plain run is partial evidence for this plan (the pricing half); the armed run is the evidence for the rest.**

## Deviations from Plan

### Auto-fixed issues

**1. [Rule 2 — Missing critical gate] The ceiling test's message assertions were unfalsified**
- **Found during:** Task 3 mutation M4
- **Issue:** The plan specified one mutation for the ceiling — swap the comparison to `>= 2049`. It goes red, but by tripping the store's dimension check after the table is created, so the test raises before `assert "2000" in err` and `assert "halfvec" in err` ever execute. Those two assertions, which are the substance of "refuses **loudly**, naming halfvec", had no mutation behind them.
- **Fix:** Added M4′ — ceiling intact, `halfvec` removed from the message — and observed the assertion red on its own terms.
- **Files modified:** none (a mutation, not a code change); recorded in the table above.

**2. [Rule 2 — Missing critical assertion] The resume key needed a second pass**
- **Found during:** Task 2
- **Issue:** The plan's tenancy test writes into an empty target, where the skip predicate is vacuous — a first pass inserts everything whatever the key is. 13-01's mutation E and 13-02's M6 both established this, and re-embedding is the one command where a broken resume key costs real money on every re-run.
- **Fix:** `test_reembed_carries_tenancy` runs the command twice and asserts that the second pass embeds nothing new and leaves the row count unchanged.
- **Files modified:** `tests/test_migrate.py`
- **Commit:** `9a88ad0`

**3. [Rule 2 — Anti-vacuity] The tenancy comparison needed a floor**
- **Found during:** Task 2
- **Issue:** `_epoch_triples(target) == _epoch_triples(source)` is green over two empty tables, and green over two tables that both lost `owner`. (It is the second case M1 would have slipped through if the row count assertion had also been the only other check.)
- **Fix:** The test asserts the row count and `owners == {"alice", "bob", ""}` before comparing triples. M1 goes red on the owner-set assertion, one line earlier than the triples.
- **Files modified:** `tests/test_migrate.py`
- **Commit:** `9a88ad0`

### Departures from the plan's written approach

- **The injection parameters were threaded through `main()`**, not only through the subcommand function. The plan asked for `token_counter=`/`embedder_factory=` on the subcommand and separately asked `test_preview_requires_yes` to invoke via `main([...])` while asserting zero embed calls on the injected embedder. Those two requirements are only simultaneously satisfiable if `main()` can carry the injection, so it does — keyword-only, defaulting to the real thing, so the CLI surface is unchanged.
- **`VOYAGE_PRICES_VERIFIED` was added to `usage.py`** (Task 2's commit, not Task 1's) so the preview prints the verification date from the same place the rates live rather than from a second hand-typed date in a format string.
- **`PriceWindow.price` is annotated `Price | float`.** The plan said to reuse the window with a comment noting the payload reuse; the comment is there, and so is a type that matches what the code does.
- **`--model` is required**, with no default. A command that spends money should not have a model it picks for you.

### README

**Rewritten this wave** (commits `7f9ba0a`, `8b2e655`), per the standing instruction — this is the wave that falsifies the sentence, and 13-01 and 13-02 both correctly declined to write it early.

The old bullet said the dimension check "fails loudly but can't migrate for you". It can now. The replacement names both subcommands and why there are two of them (one variable each), states that tenancy and the seven-day clock are carried, that the preview always prints and `--yes` is required, that an unpriced model and a width above 2000 both refuse, that the loud check still fires inside the migration path, and that cutover is `PGVECTOR_TABLE`/`VECTOR_DIMENSIONS` plus a restart with rollback by pointing back. It also states what did *not* change: the column width is still fixed at creation, the preview quotes list price, and **Voyage embedding spend is still absent from `/metrics`** — the preview is an estimate, not accounting (Phase 14).

**Note for wave 4:** VALIDATION row 13-04.3's automated gate is `grep -c "Changing embedding model means a new pgvector table" README.md -eq 0 && grep -q "embeddings re-embed" README.md && …`. The README half is already satisfied (0 and 1 respectively, measured); the `docs/OPERATIONS.md` half of that same gate is untouched and still wave 4's. The baseline recorded in VALIDATION ("current phrase present today at 1 occurrence") was measured before this wave and no longer holds.

`docs/OPERATIONS.md` deliberately untouched: the operator procedure belongs with the cutover story, which 13-04 owns.

## Threat model outcomes

| Threat ID | Disposition | Outcome |
|-----------|-------------|---------|
| T-13-09 | mitigate | **Closed.** The preview prints tokens × verified rate on every invocation, and `test_preview_prints_before_spend_with_yes` asserts it precedes the first progress line. Post-run reconciliation prints predicted vs billed. Caveat below: the *billed* number is only exercised on the live path. |
| T-13-10 | mitigate | **Closed.** Without `--yes`: preview printed, exit 2, `embed_calls == 0`, target table not created. M3 (`--yes` defaulting True) red. |
| T-13-11 | mitigate | **Closed, with the honest reading in the M2 note above.** Every batch routes through the store's own `_check_dimensions`; >2000 refused before DDL. M2 and M4′ red. |
| T-13-12 | mitigate | **Closed.** `(text, embedding, owner, created_at)` in the insert; per-row triple equality against the source. M1 red. |
| T-13-13 | mitigate | **Closed.** `voyage_price_for` raises; the command prints and exits 2 before opening the database. P2 and M5 red. |
| T-13-SC | accept | No packages installed. `pyproject.toml` untouched this plan. |

New threat surface: none. No network endpoint, no auth path, no production schema change — the new table is created by the existing store DDL at the requested width.

## Known Stubs

None. Two pieces of **untested-by-construction** code, which is a different thing and is stated rather than hidden:

- **`_default_token_counter`** — the real `voyageai.Client().count_tokens` wrapper. No test calls it, because the first call downloads a tokenizer from the Hugging Face hub (Pitfall 8) and RESEARCH's guidance is that tokenizer-touching tests are live-only. Every test injects `_word_counter` instead. It is three lines with no branching, and **13-05's live run is the first thing that will execute it.**
- **`_ReembedEmbedder.embed_documents`** and therefore the `billed` reconciliation line — the fake-embedder path prints `billed  not reported by this embedder`, which the tests do exercise. The `total_tokens` sum itself is only reachable through a real Voyage response, i.e. 13-05.

Both are named here so 13-05 knows it is not merely demonstrating the path but executing these two functions for the first time.

## Deferred Issues

- **The re-embed path's recall delta is not measured in this wave.** STATE.md's carry-in note — "wave 3 must re-run `assert_tie_free` against the re-embedded table; a new model re-scores everything and tie-freedom does not travel" — is correct and remains open. This plan's tasks build the mechanism and gate the money; no task asked for a golden comparison across the model change, and inventing one would have been unmandated scope in a wave that already owns three loud refusals. **13-04 or 13-05 should carry it**, and the warning is real: the golden set is tie-free under the 5-dimensional `FakeEmbedder` and there is no reason a 4-dimensional one preserves that, so a `recall_delta` over the re-embedded table must call `assert_tie_free` against *that* table first or it will be measuring the executor.
- Voyage spend is still absent from `/metrics` (Phase 14, per CONTEXT's deferred list). The README now says so.

## Commits

| Commit | Type | Summary |
|--------|------|---------|
| `c4f5950` | feat | Price Voyage embeddings in the one pricing home, fail-loud |
| `9a88ad0` | feat | `embeddings re-embed` — new model, new width, same tenancy |
| `a7a485a` | test | The spend gate, asserted by counting calls on a fake |
| `7f9ba0a` | docs | The embedding-model limitation is no longer true as written |
| `8b2e655` | docs | Name the subcommands in full in the README limitation |

## Self-Check: PASSED

- `src/research_agent/usage.py` — FOUND (modified)
- `src/research_agent/memory.py` — FOUND (modified)
- `src/research_agent/migrate.py` — FOUND (modified)
- `tests/test_migrate.py` — FOUND (modified)
- `README.md` — FOUND (modified)
- Commits `c4f5950`, `9a88ad0`, `a7a485a`, `7f9ba0a`, `8b2e655` — all five resolve in `git log`
- Working tree clean apart from this summary and the state files it updates
