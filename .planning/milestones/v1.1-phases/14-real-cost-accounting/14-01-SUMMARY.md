---
phase: 14-real-cost-accounting
plan: 01
subsystem: cost-accounting
tags: [pricing, multipliers, inference-geo, discount, fail-loud, gate-discipline]

# Dependency graph
requires:
  - phase: 13-embedding-model-migration
    plan: 03
    provides: "VOYAGE_PRICES / voyage_price_for / preview_cost_usd in usage.py, and the printed promise that the re-embed preview quotes list price"
  - phase: 10-adrs-and-doc-correctness
    provides: "DEC-12 — effective-dated prices, pricing_unknown fails loud and never zero"
provides:
  - "usage.cost_discount_factor() and usage.inference_geo_multiplier() — per-call env readers, non-positive and unparseable clamped to the default"
  - "CallUsage.inference_geo — where inference actually ran, read off the response with the file's defensive getattr idiom"
  - "CallUsage._geo_factor() — hybrid geo: the response decides applicability, the env sets the rate, an unrecognised value raises"
  - "Multiplied CallUsage.cost_usd — the ONE site where tokens become dollars; every consumer inherits it unchanged"
  - "SC-1's arithmetic half, SC-3 under multipliers, SC-4 under multipliers"
affects: [14-02, 14-03, VALIDATION rows 14-01.T1 (x3) and 14-01.T2]

# Tech tracking
tech-stack:
  added: []  # no packages installed this phase (RESEARCH Package Legitimacy Audit: none)
  patterns:
    - "Applicability observed, rate configured: a billing dimension the API reports per call must be read from the response, because a workspace default can put a request in a billed geo with no code change and an env flag would then disagree with the invoice in either direction"
    - "A misconfigured cost factor must fail toward reporting MORE cost, never less — the budget guardrails read the number it scales, so a zero factor is fail-open wearing a new hat"
    - "An unrecognised value in a pricing dimension takes the same UnknownModelPricing route as an unpriced model, rather than a parallel mechanism — record()'s except clause is untouched"

key-files:
  created: []
  modified:
    - src/research_agent/usage.py
    - tests/test_usage.py
    - tests/test_migrate.py

key-decisions:
  - "The two multipliers have different bases and it is written down in the code, not just the plan: geo multiplies the four token classes only (the published 1.1x is scoped to token pricing categories), the discount multiplies the whole call including the $10/1k web-search fee (a negotiated discount is applied to the invoice). Both are RESEARCH assumptions A1/A2, stated in comments where the arithmetic is."
  - "`inference_geo` reads '' when absent rather than defaulting to 'global'. Both cost the same, but '' means 'the response did not say' and 'global' means 'the response said global' — the distinction is free here and matters the moment /pricing reports what it observed (14-03)."
  - "FakeUsage sets `inference_geo` only when a caller passes it, so the same fake stands in for a current SDK response and an older one. A defaulted attribute would have made the absent-field assertion untestable through the fake it is meant to protect."
  - "The clamp is `> 0`, which also catches NaN (`nan > 0` is False) and lets `inf` through. Both directions are the safe one: NaN falls back to neutral, and an absurdly large factor over-reports, which makes the caps bind sooner rather than never."
  - "DEFAULT_INFERENCE_GEO_MULTIPLIER = 1.1 is the *rate*, not blanket applicability. Unset, it costs exactly nothing until a response reports a call ran in a billed geo."

# Metrics
duration: 31min
completed: 2026-08-09
---

# Phase 14 Plan 01: Multiply at the choke point Summary

**One-liner:** `discount × geo` now applies at `CallUsage.cost_usd` and provably nowhere else, with the geo multiplier's *rate* coming from `INFERENCE_GEO_MULTIPLIER` and its *applicability* from the response's own `usage.inference_geo` — so an unrecognised geo fails loud through the existing `pricing_unknown` route, a zero discount falls back to neutral instead of zeroing the budget guardrails, and with both env vars unset the deployed service's cost arithmetic is byte-for-byte what it was.

## What was built

### Task 1 — the field, the readers, the arithmetic (commit `b79d506`)

**`CallUsage.inference_geo: str = ""`**, captured in `from_response` with the idiom the rest of the file already uses:

```python
inference_geo=str(getattr(usage, "inference_geo", None) or ""),
```

`anthropic 0.120.0` declares the field; older SDKs and every existing test fake do not, and absent must mean "not geo-billed" rather than an `AttributeError` halfway through a paid run. `test_a_response_without_usage_is_all_zeroes` — the frozen-dataclass equality test — passes unmodified, because the new field has a default like every other.

**Two env readers**, `cost_discount_factor()` (default 1.0) and `inference_geo_multiplier()` (default 1.1), shaped exactly like `max_run_cost_usd`: read on every call, never cached at import, so `monkeypatch.setenv` works and so a process whose configuration changes under it reports the new number. Both clamp: unparseable **or** ≤ 0 returns the default. The docstrings say why in the terms that matter — the per-run cap and the daily cap are compared against the number this factor scales, so honouring `COST_DISCOUNT_FACTOR=0` would cost every run at $0.00 and silently disarm both.

**`CallUsage._geo_factor()`** resolves the multiplier from `self.inference_geo`: `""` and `"global"` → 1.0; `"us"` → `inference_geo_multiplier()`; anything else raises `UnknownModelPricing` naming the value. That raise is deliberate reuse, not a new mechanism: `record()`'s `except UnknownModelPricing` clause is **unchanged** (verified in the diff — the function is untouched), so a future `"eu"` reaches `pricing_unknown = True` with tokens counted by the same path an unpriced model takes.

**`cost_usd`**, one expression with the assumptions written where the arithmetic is:

```python
tokens_usd = (... four token classes ...) / _PER_MTOK * self._geo_factor()
return (tokens_usd + self.web_search_requests * WEB_SEARCH_USD_PER_REQUEST) * cost_discount_factor()
```

Geo multiplies the token portion only (the published rate is scoped to "token pricing categories" — A1). The discount takes the whole call, fee included (a negotiated discount is applied at invoice time — A2). `price_for`, `voyage_price_for`, `preview_cost_usd`, `PRICES` and `VOYAGE_PRICES` are untouched: list prices stay list prices and effective-dating resolves exactly as before.

Module docstring extended to say that list price is not the invoice, which two multipliers move it away from, and that both apply in one function.

**Five tests** (`test_multiplier_choke_point_composes_discount_and_geo`, `test_unset_multipliers_change_nothing_for_the_deployed_service`, `test_geo_applies_by_response_not_by_env`, `test_pricing_unknown_survives_multipliers`, `test_the_web_search_fee_is_discounted_but_not_geo_multiplied`), every date written out.

### Task 2 — boundary, clamps, preview pin (commit `345439b`)

| Test | What it claims |
|------|----------------|
| `test_boundary_with_multipliers` | at `COST_DISCOUNT_FACTOR=0.5`, the same call costs `12.0 × 0.5` on 2026-08-31 and still exactly `1.5×` that on 2026-09-01 — multipliers compose with effective-dating rather than flattening it, and each half of that is a separate assertion |
| `test_a_zero_discount_factor_falls_back_to_neutral` | `"0"` → factor 1.0, **and** a priced call still costs $2.00 rather than nothing |
| `test_an_unparseable_discount_factor_falls_back_to_neutral` | `"ten percent"` → 1.0 |
| `test_a_nonpositive_geo_multiplier_falls_back_to_the_published_rate` | `"-1"` → 1.1, unset → 1.1 |
| `test_preview_cost_stays_list_price_under_non_neutral_env` (test_migrate.py) | `preview_cost_usd(1_000_000, "voyage-3.5", date(2026, 8, 9)) == 0.06` with discount 0.5 and geo 2.0 set — the Phase 13 printed promise, stated by a test |

`from datetime import date` added to `tests/test_migrate.py` (it had no date import; the preview pin needs a fixed `on` for the same reason everything else here does).

## Gate discipline: four mutations, four red by the intended route

Sixteen vacuous gates across seven phases, the most recent being this phase's own additive-payload gate whose `-k` selector collected **zero** tests while its verify command reported green. So both selectors in this plan were run under `--collect-only` **before** being trusted:

| Selector | Collected |
|----------|-----------|
| `-k "multiplier_choke_point or geo_applies_by_response or pricing_unknown_survives_multipliers or web_search_fee"` | **4** (test_usage.py) |
| `-k "boundary_with_multipliers or falls_back or preview_cost_stays_list_price"` | **6** — 5 in test_usage.py (4 new + the pre-existing `test_an_unparseable_budget_falls_back_to_the_default`, which `falls_back` also matches), 1 in test_migrate.py |

Baselines measured on this tree before any code was written: suite plain **529 passed / 63 skipped**; `cost_discount_factor|inference_geo_multiplier` anywhere in `src/` → **0 files**; `date.today()|datetime.now()` in `tests/test_usage.py` → **0**.

| # | Mutation | Result | Observed failure |
|---|----------|--------|------------------|
| A | Delete `* cost_discount_factor()` from `cost_usd`'s return | **RED** | `test_multiplier_choke_point_composes_discount_and_geo`: `assert 2.2 == 1.9800000000000002 ± 2.0e-06` (test_usage.py:258) and `test_boundary_with_multipliers`: `assert 12.0 == 6.0 ± 6.0e-06` (test_usage.py:374) |
| B | `_geo_factor` returns `inference_geo_multiplier()` unconditionally | **RED** | `test_geo_applies_by_response_not_by_env`: `assert 2.2 == 2.0 ± 2.0e-06` — the `""` call, i.e. the unmultiplied-response assertion, exactly the one it was aimed at |
| C | Replace the unknown-geo `raise` with `return 1.0` | **RED** | `test_pricing_unknown_survives_multipliers`: `assert 0.009899999999999999 == 0.0` — the `"eu"` call got silently billed |
| D | `preview_cost_usd` multiplies by `cost_discount_factor()` | **RED** | `test_preview_cost_stays_list_price_under_non_neutral_env`: `assert 0.03 == 0.06 ± 6.0e-08` |

Every mutation went red on a **cost assertion**, not on an import or collection error, and each was reverted immediately with `git checkout -- src/research_agent/usage.py` (working tree confirmed clean of `src/` changes afterwards; the final tree is byte-identical to commit `b79d506`'s `usage.py`). `ruff check src tests` clean.

**One honest note on A.** It reds two tests, and the second one (`boundary_with_multipliers`) is the more interesting: without the discount term the boundary *ratio* assertion still passes — 18/12 is 1.5 whether or not anything was halved — and only the absolute `before == 12.0 × 0.5` assertion catches it. That is why the boundary test asserts both halves rather than the ratio alone; a ratio test is invariant under exactly the mutation it looks like it should catch.

## Verification

| Check | Baseline | After |
|-------|----------|-------|
| `grep -rln "cost_discount_factor\|inference_geo_multiplier" src/research_agent/` | 0 files | **exactly `src/research_agent/usage.py`** |
| Second multiplication site anywhere downstream | n/a | none — `graph.py:102` calls `from_response` then `record`; `evals/harness.py:168` **sums** turn costs; `service.py:886` reads `max_run_cost_usd`; `limits.settle` deletes a row |
| `grep -c "date.today()\|datetime.now()" tests/test_usage.py` | 0 | **0** |
| `record()`'s `except UnknownModelPricing` clause | present | unchanged — unknown geo arrives through it |
| `CallUsage(input_tokens=1_000_000, inference_geo="us").cost_usd("claude-sonnet-5", date(2026,8,1))` at 0.9 × 1.1 | n/a | `1.9800000000000002` (binary floating point; `pytest.approx(2.0 * 1.1 * 0.9)`) |
| same call, env unset, `inference_geo=""` | 2.0 | **2.0**, exactly — asserted with `==`, not `approx` |
| `pytest tests/test_usage.py` | 22 passed | **31 passed** |
| `pytest tests/test_migrate.py` plain | 2 passed / 16 skipped | **3 passed / 16 skipped** (the new test needs neither Postgres nor the network) |
| Full suite, plain | 529 passed / 63 skipped | **539 passed / 63 skipped** |
| Full suite, armed (`DATABASE_URL` → local PG :54329) | 591 passed / 1 skipped | **601 passed / 1 skipped** |
| `ruff check src tests` | clean | clean |

**Delta fully explained: +10 passed in both arms, +0 skipped in either.** The ten are exactly the nine new tests in `test_usage.py` and the one in `test_migrate.py`; the migrate one raised the plain count without changing the skip count because it is pure arithmetic behind no `HAS_POSTGRES` gate. **Zero new skips, so nothing to justify.** No pre-existing test changed state, and no existing assertion was edited — every change to both test files is an addition, except `FakeUsage.__init__`, which gained a conditional attribute set and no altered behaviour for its existing callers.

`ruff format --check` reports this tree unformatted, as it does for 25 of 32 files: `pyproject.toml:75` says *"Deliberately not `ruff format`"*. `ruff check` is the repo's gate and it is clean.

## Deviations from Plan

### Departures from the plan's written approach

- **The neutral case is its own test**, `test_unset_multipliers_change_nothing_for_the_deployed_service`, rather than a second assertion inside the composition test. The plan asked for it "in the same test module", which it is. Separating it means the mutation evidence is unambiguous — mutation A reds the composed assertion, and a reader can see at a glance that the neutral claim (the one that matters to the live service) is not riding on the same setup.
- **`FakeUsage` sets `inference_geo` conditionally.** The plan's geo test requires a fake *with* the attribute and a fake *without* it; a dataclass-style default would have made the second case unreachable through the fake. This is the only edit to shared test scaffolding, and it is additive.
- **`DEFAULT_COST_DISCOUNT_FACTOR` / `DEFAULT_INFERENCE_GEO_MULTIPLIER` are named constants**, not literals repeated in the parse and the clamp. Three occurrences of `1.1` in one function is how a default and a fallback drift apart.

### README

**Deliberately untouched.** README line 204 — *"Cost is computed from list prices — no enterprise discounts or `inference_geo` multiplier"* — is now falsified by this wave's code, and rewriting it here was explicitly declined: the standing instruction assigns that sentence to plan 14-03, which is also the wave that gives an operator anything to *read* about the multipliers (`/pricing`, `docs/OPERATIONS.md`). Rewriting it now would announce two env vars that nothing yet documents or exposes. **14-03 must not treat that line as still-true prose:** its VALIDATION baseline ("present at 1 occurrence") holds, but its content is wrong as of commit `b79d506`.

## Threat model outcomes

| Threat ID | Disposition | Outcome |
|-----------|-------------|---------|
| T-14-01 | mitigate | **Closed.** `≤ 0` or unparseable → default, in both readers. Three tests, including one asserting a priced call still costs list under `COST_DISCOUNT_FACTOR=0` — the clamp is pinned by the arithmetic it protects, not only by the reader's return value. |
| T-14-02 | mitigate | **Closed.** Applicability comes from `self.inference_geo`, which comes from the response. Mutation B — the exact failure mode, geo applied because configuration said so — observed red. |
| T-14-03 | mitigate | **Closed for this wave.** The factor functions are referenced in `usage.py` and nowhere else in `src/` (baseline 0 files → exactly 1 file). The call graph downstream was re-read: no consumer performs arithmetic on cost beyond summing. The behavioural single-application e2e remains **14-02.T3's**, as planned. |
| T-14-04 | mitigate | **Closed.** `preview_cost_usd` untouched and pinned under a doubly non-neutral env; mutation D red. |
| T-14-SC | accept | No packages installed. `pyproject.toml` untouched. |

New threat surface: none. No endpoint, no auth path, no schema change, no new file. The only new external input is a string field on an Anthropic response, which no caller can influence, and an unrecognised value fails loud rather than being interpreted.

## Known Stubs

None. One piece of **untested-by-construction** behaviour, stated rather than hidden: no test exercises a *real* response carrying `inference_geo`, because this service sends no geo parameter and its workspace is not geo-pinned, so a live call would report `"global"` (or omit the field) and prove only the neutral path — which the fakes already prove. The `"us"` path is exercised through constructed `CallUsage` values and through `from_response` on a fake that carries the attribute. RESEARCH verified the field exists on `anthropic 0.120.0`'s `Usage` model by local inspection; VALIDATION's manual-verification row already books the live confirmation to the next deploy.

## Deferred Issues

- **`inference_geo` is captured per call but not persisted or reported.** Nothing surfaces which geo a run's calls actually ran in — `/pricing` (14-03) reports the configured *rate*, and the run record has no geo column. That is correct scope for this wave; worth naming because "we multiplied by 1.1" and "we can show you why" are different claims, and only the first is true today.
- **The 1h cache-write rate remains unmodelled** (all `cache_creation_input_tokens` are priced at the 5m rate). Pre-existing, out of scope, noted by RESEARCH as worth one line of docs rather than code — 14-03's docs pass is the place if it is wanted.

## Commits

| Commit | Type | Summary |
|--------|------|---------|
| `b79d506` | feat | Multiply at the one place tokens become dollars |
| `345439b` | test | The boundary composes, the clamps hold, the preview stays list price |

## Self-Check: PASSED

- `src/research_agent/usage.py` — FOUND (modified)
- `tests/test_usage.py` — FOUND (modified)
- `tests/test_migrate.py` — FOUND (modified)
- `.planning/phases/14-real-cost-accounting/14-01-SUMMARY.md` — FOUND (created)
- Commits `b79d506`, `345439b` — both resolve in `git log`
- Working tree clean apart from this summary and the state files it updates
