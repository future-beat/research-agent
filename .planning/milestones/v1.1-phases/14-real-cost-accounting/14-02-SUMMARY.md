---
phase: 14-real-cost-accounting
plan: 02
subsystem: cost-accounting
tags: [voyage, embeddings, contextvar-meter, schema-migration, settle, gate-discipline]

# Dependency graph
requires:
  - phase: 14-real-cost-accounting
    plan: 01
    provides: "multipliers at CallUsage.cost_usd — the choke point this wave proves downstream-complete"
  - phase: 13-embedding-model-migration
    plan: 03
    provides: "VOYAGE_PRICES / voyage_price_for, and the live finding that Voyage reported 0 tokens for a valid embedding"
  - phase: 12-identity-and-ownership
    provides: "the two in-repo live-table migration idioms (sessions.py:92 PG, sessions.py:239 SQLite PRAGMA probe)"
provides:
  - "usage.embedding_meter() / report_embedding() / record_embedding() — the out-of-band path from the Voyage seam to a run's usage dict"
  - "VoyageEmbedder._report — total_tokens captured instead of discarded, on both embed methods"
  - "researcher_node's meter: the only node that embeds is the only node that meters"
  - "RunRecord.embedding_tokens / embedding_requests / embedding_cost_usd, plus a live-table migration in BOTH backends"
  - "the end-to-end proof that settled spend is multiplied cost, applied exactly once"
affects: [14-03, VALIDATION rows 14-02.T1 (x2), 14-02.T2, 14-02.T3]

# Tech tracking
tech-stack:
  added: []  # no packages installed this phase
  patterns:
    - "A number the seam receives but its contract cannot return travels out of band to a contextvar meter, rather than widening a protocol that four implementations satisfy and three would immediately discard the number"
    - "Set-and-read inside one function frame is what makes contextvar attribution safe under a thread pool; the isolation is structural rather than asserted"
    - "A migration test must open a table that PREDATES the columns and has a row in it, and assert their absence first — a migration test against a fresh table proves creation and stays green with the migration deleted"
    - "Provider telemetry that looks anomalous is recorded as reported: `pricing_unknown` means 'no price for this MODEL', and spending it on a 0-token reading would discredit a whole run's cost figure over a fraction of a cent"

key-files:
  created: []
  modified:
    - src/research_agent/usage.py
    - src/research_agent/memory.py
    - src/research_agent/graph.py
    - src/research_agent/metrics.py
    - tests/test_usage.py
    - tests/test_memory_stores.py
    - tests/test_graph_smoke.py
    - tests/test_metrics.py
    - tests/test_service.py
    - README.md

key-decisions:
  - "`record_embedding` applies NEITHER multiplier, and that is pinned by an assertion rather than by the comment next to it: the same call under COST_DISCOUNT_FACTOR=0.5 and INFERENCE_GEO_MULTIPLIER=2.0 returns the identical number. A discount negotiated with Anthropic and a Claude data-residency surcharge have nothing to say about a different vendor's bill."
  - "Embedding tokens stay out of TOKEN_FIELDS and out of total_tokens(). A Voyage token is priced ~30x below a Claude input token and is not interchangeable with one; summing them yields a number that means nothing. The dollars, unlike the tokens, do combine."
  - "The seam reads `getattr(response, 'total_tokens', 0)` rather than the attribute directly — migrate.py:467's idiom. report_embedding is a no-op without a meter, but the attribute read is not, and an AttributeError halfway through an already-billed run is the wrong way to discover a client stub."
  - "The reporting lives in a `_report` helper on VoyageEmbedder rather than inline twice. Two call sites, one rule; the docstring is the place the out-of-band decision is written down, next to the code it explains."
  - "The e2e gate's geo arm asserts `((C0 - fee) * 1.1 + fee) * 0.5`, NOT the plan's `C0 * 0.5 * 1.1` — see Deviations. The plan's formula is false under 14-01's landed semantics, and asserting it would have failed a correct implementation."
  - "The PG migration test leaves the table migrated. That IS the post-phase state; a teardown that re-dropped the columns would leave every following test running against a database this phase supposedly already migrated."

# Metrics
duration: 32min
completed: 2026-08-09
---

# Phase 14 Plan 02: Voyage into the accounting, and a table that can take it Summary

**One-liner:** The `total_tokens` the embedder wrapper has been receiving and dropping since Phase 2 now travels out of band through a contextvar meter into the run's usage dict, is priced against the effective-dated Voyage table and folded — unmultiplied, exactly once — into the same `cost_usd` the caps and `/metrics` already read; the three new `RunRecord` columns migrate onto tables that already exist in both backends, proven against genuinely old ones; and a three-run integration gate shows the settled spend in the runs table is the multiplied cost with no second arithmetic site anywhere downstream.

## What was built

### Task 1 — the meter (commit `f610132`)

**`usage.py`.** `EmbeddingMeter` (mutable dataclass: `model`, `total_tokens`, `requests`), a `_EMBEDDING_METER` ContextVar defaulting to `None`, `embedding_meter()` as a `@contextmanager` that sets a fresh meter and resets the token in `finally`, and `report_embedding(model, total_tokens)` which returns silently when nothing is metering. That no-op is the load-bearing part of the design: the REPL demo, `migrate.py` and every test holding a fake embedder are untouched *by construction* rather than by being remembered.

`record_embedding(totals, model, tokens, requests=1, on=None)` mirrors `record()` line for line, including the `.get(..., 0)` reads. Two deliberate asymmetries, both written into the docstring where the arithmetic is:

* **No multipliers.** Voyage is a different vendor on a different rate card.
* **Zero tokens is not an error.** It prices to $0.00 through the normal path. `pricing_unknown` stays reserved for a model with no price on file — including `voyage-4`, which is exactly SC-4 reaching Voyage.

`new_usage()` gains `embedding_tokens`, `embedding_requests`, `embedding_cost_usd`. `TOKEN_FIELDS` and `total_tokens()` are unchanged.

**`memory.py`.** Both `VoyageEmbedder.embed_documents` and `embed_query` bind the response, call `self._report(response)`, and return what they always returned. `from research_agent import db, usage` is a safe top-level import — `usage` imports nothing from `memory`.

**`graph.py`.** `researcher_node` opens the meter before `store.query` and closes it after `store.add`, with the model call carried along in between; after the block, a `requests > 0` guard folds via `record_embedding`. `call_model` is untouched.

**Tests:** three in `test_memory_stores.py` (the seam, the no-meter path, the 0-token reading), six in `test_usage.py`, two in `test_graph_smoke.py` — the wiring gate that only a run can make, plus its complement (a store that never embeds records no `$0.00` Voyage line item, which is also what keeps every other test in that file unchanged).

### Task 2 — the migration (commit `1b4a63b`)

Three `RunRecord` fields before `duration_ms`; `from_state` reads them with the existing idiom. Both `CREATE TABLE` blocks gain the columns for a fresh database, and then — because `CREATE TABLE IF NOT EXISTS` does nothing to a table that already exists, while `record()` names every field on every INSERT — both backends migrate:

* `POSTGRES_SCHEMA` appends three `ALTER TABLE runs ADD COLUMN IF NOT EXISTS`, inside `ensure_schema`'s advisory lock, with the comment saying why both Fly machines can race it.
* `SQLiteMetricsStore.__init__` calls `_add_embedding_columns()`, which probes `PRAGMA table_info(runs)` and adds what is missing — SQLite has no `ADD COLUMN IF NOT EXISTS`.

Both tests open a table that **predates** the columns **and has a row in it**, and assert the columns are absent before opening the store. The SQLite arm hand-builds the pre-Phase-14 `CREATE TABLE` from a written-out constant (a constant derived from the current schema would silently stop being an old table); the PG arm drops the three columns from the live local table after seeding a row.

### Task 3 — the end-to-end gate (commit `ebfe11f`)

`test_settle_sees_multiplied_cost`: three real runs through the app, compared as ratios against an unmultiplied baseline so no price constant is hand-copied and the September rate change cannot rot it.

| Run | Environment | Asserted |
|-----|-------------|----------|
| A | both multipliers deleted | `C0 > 0`; `S0 == C0` — the settled row *is* the reported cost |
| B | `COST_DISCOUNT_FACTOR=0.5` | `C1 == C0 × 0.5`; `S1 == C1` |
| C | discount 0.5 **and** every response reporting `inference_geo="us"` | `C2 == ((C0 − fee) × 1.1 + fee) × 0.5`; `S2 == C2`; `C2 > C1` |

**`DEMO_DAILY_USD_CAP` is monkeypatched to `100.00`.** The plan's own review caught this: `make_client` ships `0`, under which `reserve_or_429` returns before reserving, and "the reservation is gone after completion" is trivially true of a reservation that was never made. With the cap live, `reservations.reserved` is asserted non-empty *before* `reservation_ids() == set()` is believed.

### README (commit `d259679`)

Line 209 ended *"...and Voyage embedding spend is still absent from `/metrics` entirely."* This wave falsified it — the dollars are in `cost_usd`, which `/metrics` sums. Rewritten to say what changed, what it is worth (~$0.0002 of a ~$0.15 run: *a whole provider is no longer missing*, not *the number moved*), and to keep the telemetry caveat attached. **Line 204's list-price limitation is deliberately untouched** — it belongs to 14-03, per the standing instruction.

## Gate discipline: six mutations, six red by the intended route

Sixteen vacuous gates across seven phases, the most recent being this phase's own additive-payload selector that collected zero tests. So **every** selector was run under `--collect-only` before being trusted:

| Selector | Collected |
|----------|-----------|
| T1's verify `-k` (six clauses, three files) | **10** — 6 in test_usage.py, 2 in test_memory_stores.py, 2 in test_graph_smoke.py |
| `-k "runrecord_schema_migrates or from_state"` (armed) | **5** — 2 new migration arms, `from_state_reads_embedding_usage`, and the 2 pre-existing `from_state` tests |
| `-k settle_sees_multiplied_cost` | **1** |
| VALIDATION row 7's `pytest tests/ -k runrecord_schema_migrates` | **2** — both arms, so the required substring is present on the PG one |
| VALIDATION rows 5, 6, 8 (`voyage_tokens_captured`, `zero_token_response_honest`, `settle_sees_multiplied_cost`) | **1 each**, none zero |

Baselines measured on this tree **before any code was written**: suite plain **539 passed / 63 skipped**, armed **601 passed / 1 skipped**; `report_embedding|embedding_meter|record_embedding` anywhere in `src/` → **0**; `embedding_tokens` anywhere in `src/` → **0**; `grep -c "ADD COLUMN IF NOT EXISTS embedding" metrics.py` → **0**; `grep -c "PRAGMA table_info(runs)" metrics.py` → **0**.

| # | Mutation | Result | Observed failure |
|---|----------|--------|------------------|
| E | Drop both `self._report(response)` calls — the wrapper discards again | **RED** | `test_voyage_tokens_captured_at_the_seam`: `assert 0 == 50` on `meter.total_tokens`. The graph wiring test stayed green, correctly: it reports through a fake store, not through the wrapper. |
| F | Remove the fold into `cost_usd`, keep `embedding_cost_usd` | **RED** | `test_embedding_cost_folds_into_cost_usd_once`: `assert 0.0 == 0.06 ± 6.0e-08`, on the `cost_usd` assertion specifically |
| G | Delete the `record_embedding` fold from `researcher_node` | **RED** | `test_the_researcher_meters_the_embeddings_it_causes`: `assert 0 == 2` on `embedding_requests` |
| G′ | The other half — meter constructed but never entered (`with` replaced by a bare `EmbeddingMeter()`), fold left in place | **RED** | same test, same assertion: `assert 0 == 2`. Both halves of the wiring are load-bearing and both are covered. |
| H | Comment out the SQLite `PRAGMA table_info(runs)` probe | **RED** | `sqlite3.OperationalError: table runs has no column named embedding_tokens` — from the INSERT, which is the intended route |
| I | Drop the three `ADD COLUMN IF NOT EXISTS` from `POSTGRES_SCHEMA`, run the PG arm from the dropped-column state | **RED** | `psycopg.errors.UndefinedColumn: column "embedding_tokens" of relation "runs" does not exist` |
| J | Multiply `cost_usd` by `cost_discount_factor()` a second time inside `RunRecord.from_state` | **RED** | `test_settle_sees_multiplied_cost`: `assert 0.008 == 0.016 ± 1.6e-08` — settled spend at 0.25 of baseline against a response still reporting 0.5. The exact Phase-12-lesson failure the gate exists for. |
| O | Make `record_embedding` flag `pricing_unknown` when `tokens == 0` | **RED** | `test_zero_token_response_honest`: `assert True is False`, on the `pricing_unknown` assertion itself |

Every mutation went red on a **value assertion or a database error naming an embedding column** — none on an import or a collection error. Each was reverted immediately and the affected file re-verified green.

**One process note, recorded because it nearly cost work.** Mutation E was reverted with `git checkout -- src/research_agent/memory.py` while the wave's own changes to that file were still **uncommitted**, which discarded them along with the mutation. Caught immediately by the two tests that went red on the revert, and re-applied. Every mutation after that one was taken and reverted through a scratchpad copy of the file instead. `git checkout` is only a safe revert when the thing you are reverting *to* is committed.

## Verification

| Check | Baseline | After |
|-------|----------|-------|
| Full suite, plain | 539 passed / 63 skipped | **553 passed / 64 skipped** |
| Full suite, armed (`DATABASE_URL` → local PG :54329) | 601 passed / 1 skipped | **616 passed / 1 skipped** |
| `grep -rln "report_embedding" src/research_agent/` | 0 files | **exactly `memory.py` and `usage.py`** (graph.py references `embedding_meter`/`record_embedding`, as specified) |
| `grep -c "ADD COLUMN IF NOT EXISTS embedding" src/research_agent/metrics.py` | 0 | **3** |
| `grep -c "PRAGMA table_info(runs)" src/research_agent/metrics.py` | 0 | **1** |
| `limits.py` / cap defaults / `preview_cost_usd` | — | **untouched** — `git diff` over the whole wave shows no change to `limits.py` or `service.py` at all |
| Deletions anywhere in `src/` across this wave | — | **only the re-indentation of `researcher_node`'s body** into the `with` block |
| Existing test assertions edited | — | **none.** The single `-` line in the whole tests diff is `test_metrics.py`'s import line, rewritten to add two names |
| e2e gate offline with `ANTHROPIC_API_KEY=""` | — | **passes** |
| `ruff check src tests` | clean | clean |

**Delta fully explained.** Plain +14 passed / +1 skipped; armed +15 passed / −0 skipped. The fifteen new tests: six in `test_usage.py`, three in `test_memory_stores.py`, two in `test_graph_smoke.py`, three in `test_metrics.py`, one in `test_service.py`. Fourteen of them run in both arms; the fifteenth is the PG migration arm.

**The one new skip, justified:** `test_runrecord_schema_migrates_a_column_dropped_pg_table` is gated `skipif(not HAS_POSTGRES)` with the suite's standard reason string. VALIDATION classifies row 7 as *integration (real PG)*, and the plan asked for the PG idiom to be proven against a real column-dropped table rather than a mock. It runs, and passes, in the armed arm — which is where the claim is actually made. No other skip changed state.

## Deviations from Plan

### Departures from the plan's written approach

- **T3 step 4's geo formula is wrong, and was not implemented as written.** The plan asks for `C1 == C0 * 0.5 * 1.1`. That identity does not hold under what 14-01 actually landed: the geo multiplier is scoped to the four token classes and deliberately skips the `$10/1k` web-search fee (14-01's `test_the_web_search_fee_is_discounted_but_not_geo_multiplied` pins exactly that). The fake researcher call bills two searches, so the run's cost is `$0.012` of tokens plus `$0.020` of fee, and the plan's formula predicts `0.0176` where a correct implementation produces `0.0166`. Asserting it would have failed working code. The geo arm was kept — it is the preferred variant — with the fee split out of `C0` using `usage_accounting.WEB_SEARCH_USD_PER_REQUEST` and the run's own reported search count, so no price constant is hand-copied and the assertion still reds under both "geo applied to the fee too" and "geo not applied at all". The fallback the plan offered was *"if the fake is closed to extension"*, which is not the reason here, so it is named rather than quietly taken.
- **Mutation G was run in two halves.** The plan's wording ("comment out the meter with-block") and its acceptance criterion (drop the fold) describe two different edits. Both were taken; both red on the same assertion. A single meter with-block and a single fold are two independent ways to forget the wiring, and the gate catches each.
- **`metrics_store()` helper added to `test_service.py`,** mirroring the existing `limits_store()` accessor, rather than reaching into `dependency_overrides` inline three times. Additive; no existing test touched.
- **`test_service.py` imports `test_graph_smoke` as a module** (in addition to the existing `from test_graph_smoke import FakeClient`), so `monkeypatch.setattr` can set `Usage.inference_geo` as a class attribute for one run and have it removed at teardown. The fake was open to extension, so the preferred geo variant was reachable.
- **Two tests beyond the plan's list** were added where the plan's own claims had an untested complement: `test_a_run_whose_store_never_embeds_records_no_embedding_spend` (the zero-request guard, which is also why every other graph test is unchanged) and `test_record_embedding_survives_a_usage_dict_from_before_this_phase` (Pitfall 7 stated as a test rather than as a comment on a `.get`).
- **`EMBEDDING_COLUMNS` is a module constant** in `metrics.py` rather than a list inline in the constructor: the SQLite DDL is written once and the test reads the *names* from it, so a fourth column cannot be added to the dataclass and forgotten in the probe.

### Threat model outcomes

| Threat ID | Disposition | Outcome |
|-----------|-------------|---------|
| T-14-05 | mitigate | **Closed.** Both idioms landed, both proven against a table that predates the columns and has a row in it, both with an explicit non-vacuity assertion that the columns were absent first. Mutations H and I show each backend's migration is individually load-bearing. |
| T-14-06 | mitigate | **Closed.** The fold happens once, inside `record_embedding`; mutation F shows removing it is caught, mutation J shows a second downstream multiplication is caught end to end. The no-multiplier rule is pinned by an identical-under-`0.5`-and-`2.0` assertion, not by the comment. |
| T-14-07 | mitigate | **Closed.** 0 tokens → 0 dollars → `pricing_unknown` untouched, at the fold (`test_zero_token_response_honest`) and at the seam (`test_a_zero_token_report_is_still_a_request` — the call still counts as a request). Mutation O reds the first on its own assertion. |
| T-14-08 | mitigate | **Closed.** `test_meter_isolation_across_contexts` covers two `copy_context()` runs, two real threads held simultaneously inside their own meters by a barrier, and the no-meter no-op — plus that the outer context is left clean afterwards. |
| T-14-SC | accept | No packages installed. `pyproject.toml` untouched. |

**New threat surface: none.** No endpoint, no auth path, no new file. The one new external input is `response.total_tokens` from Voyage, read defensively, used only as a multiplicand against a table-resolved rate, and bounded in effect: an absurd value inflates a cost figure, which makes the caps bind *sooner*. `record_embedding` never mutates the price table.

## Known Stubs

None.

Two pieces of **deliberately-not-yet** behaviour, stated rather than hidden:

- **`/metrics` has no embedding breakdown.** The dollars are inside `cost.total_usd` (they ride `cost_usd`), and the columns exist on every row, but `_SUM_COLUMNS` and `_summarise` do not yet report `embedding_tokens` / `embedding_usd`. That is 14-03.T2's row in VALIDATION, and the README sentence written this wave was worded to claim only what is true today.
- **No test exercises a real Voyage response.** The seam is tested through a fake client exposing `.embeddings` and `.total_tokens`, which is the shape RESEARCH verified against `voyageai 0.5.0`. A live call would cost money and need a key; the 0-token case that motivates the honesty rule was already observed live in Phase 13 and is recorded there.

## Deferred Issues

- **A run whose recall is skipped meters one embed, not two.** All four store backends early-return before embedding when the caller's store is empty, so a first-ever run for a visitor bills one `embed_documents` and no `embed_query`. This is correct and is what the `requests > 0` guard exists for, but it means `embedding_requests` is 1 or 2 per research run and never a fixed number — worth knowing before anyone builds an alert on it.
- **Follow-up runs record zero embedding spend**, because the responder path never touches the store. Also correct, also worth stating: a session's turns will show embedding cost on turn 1 and none after.
- **The `inference_geo` field is still not persisted** (carried over from 14-01): the runs table gained embedding columns this wave but no geo column, so "we multiplied by 1.1" remains true and "we can show you which runs" remains unanswerable.

## Commits

| Commit | Type | Summary |
|--------|------|---------|
| `f610132` | feat | The embedding tokens the seam used to drop |
| `1b4a63b` | feat | Migrate the runs table, not just create it |
| `ebfe11f` | test | Settle sees the multiplied cost, applied exactly once |
| `d259679` | docs | A whole provider is no longer missing from the cost report |

## Self-Check: PASSED

- `src/research_agent/usage.py`, `memory.py`, `graph.py`, `metrics.py` — all FOUND (modified)
- `tests/test_usage.py`, `test_memory_stores.py`, `test_graph_smoke.py`, `test_metrics.py`, `test_service.py` — all FOUND (modified)
- `README.md` — FOUND (modified)
- `.planning/phases/14-real-cost-accounting/14-02-SUMMARY.md` — FOUND (created)
- Commits `f610132`, `1b4a63b`, `ebfe11f`, `d259679` — all resolve in `git log`
- Working tree clean apart from this summary and the state files it updates
