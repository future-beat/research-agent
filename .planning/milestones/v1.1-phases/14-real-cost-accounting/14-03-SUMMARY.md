---
phase: 14-real-cost-accounting
plan: 03
subsystem: cost-accounting
tags: [pricing-endpoint, metrics, effective-dating, additive-payload, docs, gate-discipline]

# Dependency graph
requires:
  - phase: 14-real-cost-accounting
    plan: 01
    provides: "cost_discount_factor() / inference_geo_multiplier() — the values this wave DISPLAYS and never multiplies"
  - phase: 14-real-cost-accounting
    plan: 02
    provides: "RunRecord.embedding_* columns and the migration that makes SUM over them legal on a live table"
  - phase: 13-embedding-model-migration
    plan: 03
    provides: "VOYAGE_PRICES / voyage_price_for — the /pricing embedding row, and the 501 arm's second provider"
  - phase: 12-identity-and-ownership
    provides: "the additive-payload rollout constraint this wave finally turned into a test"
provides:
  - "usage.window_for(model, on) / usage.next_window(model, on) — window resolution, not just rate resolution, at fixed dates"
  - "/pricing: multipliers in effect, current + nullable next window, the Voyage row with the telemetry caveat, and a 501 arm covering both providers"
  - "/metrics cost.embedding_tokens / embedding_requests / embedding_usd, contract-identical across SQLite and Postgres"
  - "test_payload_additive_for_deployed_consumers — the Phase-12 rollout constraint as a gate that has been observed to bite"
  - "README's honest cost limitation, OPERATIONS' two env rows + the ~1.33 threshold note, and the ships-with-next-deploy record"
affects: [phase-16 critic pricing row, VALIDATION rows 14-03.T1/T2/T3]

# Tech tracking
tech-stack:
  added: []  # no packages installed this phase
  patterns:
    - "A payload field that is only ever non-null until a known date is a time bomb with a date on it: `windows.next` is nullable from the day it ships, pinned by a helper test at the far side of the boundary"
    - "Date logic lives in a unit-testable helper so the endpoint can keep calling today() while no assertion ever does"
    - "A both-backends claim belongs in the file that has a both-backends fixture; asserting it under a single-backend fixture tests the shape and never the coercion that makes the other half true"
    - "An additive-payload gate is written as explicit name sets, not a snapshot — a snapshot that gets regenerated when it fails proves nothing"

key-files:
  created: []
  modified:
    - src/research_agent/usage.py
    - src/research_agent/service.py
    - src/research_agent/metrics.py
    - src/research_agent/limits.py
    - README.md
    - docs/OPERATIONS.md
    - tests/test_usage.py
    - tests/test_service.py
    - tests/test_store_contract.py

key-decisions:
  - "`price_for` now delegates to `window_for` rather than keeping a second resolution loop. Same exception, same message, one place where 'which window covers this day' is decided — two loops is how a rate and its dates drift apart."
  - "`test_metrics_includes_embedding_spend` lives in tests/test_store_contract.py, not tests/test_metrics.py as the plan's files list said. test_metrics.py has one SQLite fixture and no backend parameterisation; the plan's own verify command would have collected it under a SQLite-only fixture and left the Postgres Decimal coercion — the thing that keeps /metrics from 500ing — entirely untested."
  - "The embedding aggregates are APPENDED to the cost dict, never interleaved, and the comment says why: the demo page is deployed separately from the service, so an old consumer talks to a new service for a window of time."
  - "No new ADR. This phase is a pure extension of DEC-12, not a reversal of it — nothing recorded was overturned, so `docs/adr/README.md`'s supersession convention has nothing to apply to. Stated here rather than left as an absence."
  - "Ships with the NEXT deploy. No cutover invented for a change that moves no number at neutral defaults; written into OPERATIONS so the choice is discoverable by an operator rather than only by a reader of this file."

# Metrics
duration: 21min
completed: 2026-08-09
---

# Phase 14 Plan 03: Say what the number is Summary

**One-liner:** `/pricing` now answers the question an operator actually has 25 days before a
price change — which window, what comes next (nullable from day one), which multipliers are in
effect, and what the embeddings cost — while `/metrics` breaks out the Voyage spend it has been
silently carrying inside `total_usd`; both payloads are additive, and that constraint is now a
test that has been watched to fail rather than a promise in a plan.

## What was built

### Task 1 — window helpers and the additive `/pricing` payload (commit `c91a2a5`)

**`usage.window_for(model, on)`** returns the covering `PriceWindow` — the rate *and* its dates —
and **`price_for` now delegates to it**, so there is one resolution loop rather than two that can
drift. `next_window(model, on)` returns the earliest window whose `since` is strictly after `on`,
or `None`.

`None` is the ordinary case and is treated as such everywhere: `claude-opus-5` and
`claude-haiku-4-5` have one undated window each and will never have a next, and `claude-sonnet-5`
stops having one on 2026-09-01. A payload field that is only ever a dict until a known date is a
time bomb with the date written on it, so `windows.next` is nullable from the first day it ships
and two helper tests pin it at `date(2026, 9, 1)` and `date(2030, 1, 1)`.

**`/pricing` gains three keys and loses none:**

| Key | Contents |
|-----|----------|
| `multipliers` | `cost_discount_factor`, `inference_geo_multiplier`, and the note that applicability comes from each response's `usage.inference_geo` |
| `windows` | `current` and `next` (nullable), each `{since, until, usd_per_mtok{4 rates}}` with dates as ISO strings or null |
| `embedding` | `model`, `usd_per_mtok`, and the telemetry caveat verbatim in spirit — *an approximation of the invoice, not the invoice* |

The 501 arm now covers **both providers**: `voyage_price_for` sits inside the same
`try/except UnknownModelPricing` as `price_for`, so an unpriced embedding model is as loud as an
unpriced LLM. `memory.EMBEDDING_MODEL` is read as a module attribute at request time, which is
what makes the 501 test reachable by `monkeypatch.setattr` and what makes an operator's restart
take effect.

**Six helper tests, every date written out**, and two endpoint tests that assert *shape* or
membership — never which window is current. The suite reads identically on 2026-08-31 and the
morning after.

### Task 2 — `/metrics` embedding aggregates, both backends (commit `e38d661`)

Three aggregates in the three places aggregates are declared: `_SUM_COLUMNS` (shared SQL),
`_summarise`'s cost dict (shared shape), and `PostgresMetricsStore.summary`'s coercion — where
`embedding_tokens`/`embedding_requests` join the int tuple and `embedding_cost_usd` joins
`cost_usd` in a small float loop. Without the last one a `Decimal` reaches a JSON response and
500s it.

The keys are appended, not interleaved, and `embedding_usd` is a **breakdown of** `total_usd`
rather than an addition to it — the dollars have ridden `cost_usd` since the previous wave.

`test_metrics_includes_embedding_spend` records two runs with embedding spend plus one
**pre-phase-shaped row** (zeros), so the sum is over a mixed table rather than one where every row
is new, and asserts 75 tokens / 3 requests / `round(0.0000045, 6)` in both backends **plus** that
the values are plain `int`/`float`.

`test_payload_additive_for_deployed_consumers` writes out the eight pre-phase cost keys and the
fifteen pre-phase `RunResponse` fields as explicit sets. A snapshot would have been regenerated
the moment it failed; a written-out set is a claim about *these particular names*.

### Task 3 — the docs (commit `e73e13b`)

**README line 204**, false since wave 1, rewritten in the order the plan asked: what the number
now includes (both multipliers at one choke point, with the geo one's applicability read off the
response; Voyage spend at ~$0.0002 of a ~$0.15 run — *a whole provider is no longer missing*, not
*the number moved*), the telemetry caveat with the live Phase 13 numbers attached to it (40
counted, 25 reported, 0 for a one-word document that embedded fine), and what is still **not**
included: invoice reconciliation, the geo rate on the web-search fee, Voyage's free-allowance
tiers, the 1h cache-write rate. The effective-dating sentence and the read-`/pricing`-not-a-document
pointer are kept, and the pointer is now stronger (`/pricing` shows the next window too).

**OPERATIONS** gains both variables in the env table and a new section, *The two cost multipliers,
and what they do to the caps*: the hybrid geo semantics stated as a difference in kind (you declare
a contract fact the API cannot report; you configure only the *rate* of a fact it does report), the
clamp and the fail-open reasoning behind it, the quantified reservation note (~$0.15 against $0.20
→ under-reservation needs a combined multiplier above ~**1.33**, unreachable at 1.1 with any
discount ≤ 1.0; a discount below 1.0 makes the estimate *more* conservative, so it is a note and
not a resize), that `AGENT_MAX_RUN_COST_USD` now bounds multiplied cost — the cap bounding spend
rather than calls — and the deployment posture.

**`limits.py`** carries the same threshold in `reserved_run_usd`'s docstring, next to the default
it justifies. The diff is **+7 lines, 0 deletions, docstring only**; `tests/test_limits.py` is
51 passed / 4 skipped, unchanged.

## Gate discipline: five mutations, five red by the intended route

Sixteen vacuous gates across seven phases — the most recent being this plan's own additive-payload
selector, which collected **zero** tests while its verify command reported green. So every selector
was run under `--collect-only` **before** being trusted:

| Selector | Collected |
|----------|-----------|
| T1 verify `-k "window or pricing_payload or pricing_501"` (2 files) | **10** — 8 in test_usage.py (6 new + 2 pre-existing matching `window`), 2 in test_service.py |
| VALIDATION row 9 `pytest tests/ -k "pricing_payload or pricing_501"` | **2** |
| `-k "metrics_includes_embedding_spend or payload_additive"` over `tests/` | **3** armed (1 service + 2 backend params), **2 + 1 skipped** plain |
| VALIDATION row 10 `-k metrics_includes_embedding_spend` | **2** (both backend params) |
| VALIDATION row 11 `-k payload_additive` | **1** — the selector that collected zero at plan time now names a real test |

**Baselines measured on this tree before any code was written:** suite plain **553 passed / 64
skipped**, armed **616 passed / 1 skipped**; `next_window` in `src/` → **0**; README
`"Cost is computed from list prices"` → **1**; README `telemetry` (case-insensitive) → **0**;
OPERATIONS `COST_DISCOUNT_FACTOR` / `INFERENCE_GEO_MULTIPLIER` / `1.33` → **0 / 0 / 0**;
`date.today()|datetime.now()` in `tests/test_usage.py` and `tests/test_service.py` → **0 / 0**;
`cost_discount_factor()|inference_geo_multiplier()` in `src/` → **exactly `usage.py`**.

| # | Mutation | Result | Observed failure |
|---|----------|--------|------------------|
| K | `next_window` returns the CURRENT window | **RED** | `test_next_window_is_the_september_window_before_the_boundary`: `assert None == datetime.date(2026, 9, 1)` — the `since` assertion itself. Plus both None-pins: `assert PriceWindow(since=2026-09-01…) is None` and `AssertionError: claude-opus-5`. |
| N | `voyage_price_for` moved OUTSIDE the try/except (the 501 arm deleted) | **RED** | `test_pricing_501_when_the_embedding_model_is_unpriced`: `research_agent.usage.UnknownModelPricing: No Voyage embedding price for 'voyage-4'…` — see the note below |
| L | `embedding_cost_usd` removed from `_SUM_COLUMNS` | **RED** | `test_metrics_includes_embedding_spend` **both params**: `KeyError: 'embedding_cost_usd'` raised inside `_summarise` |
| L′ | `_SUM_COLUMNS` left intact; the `"embedding_usd"` key removed from `_summarise` | **RED** | `KeyError: 'embedding_usd'` at the store-contract assertion (both params) **and** `test_payload_additive_for_deployed_consumers` on its set difference: `Extra items in the left set: 'embedding_usd'` |
| M | `"total_usd"` renamed to `"total"` in `_summarise` | **RED** | `test_payload_additive_for_deployed_consumers`: `Extra items in the left set: 'total_usd'` — the additive gate biting on exactly the rename it exists for |

**Mutation N, recorded honestly.** It went red by the exception escaping `pricing()` rather than by
the status-code assertion, because `TestClient` defaults to `raise_server_exceptions=True` and
re-raises before a status is ever observed. That is not an unrelated crash — it is
`UnknownModelPricing` raised from the `voyage_price_for` line that the mutation moved, naming
`voyage-4` — but it is not the route the plan specified either, so the status route was confirmed
separately: with the mutation still applied and the exception swallowed
(`TestClient(app, raise_server_exceptions=False)`), `GET /pricing` returned **500**; reverted, the
same probe returned **501**. Both halves of the gate are therefore observed.

**Mutation L is caught broadly, L′ sharply.** Removing the SUM column reds every metrics test,
because `_summarise` KeyErrors before any assertion runs — true evidence that the column is
load-bearing, but not evidence that *this* test is the thing guarding the new keys. L′ was added
for that: it leaves every pre-existing metrics test green and reds only the two gates written this
wave.

**Every mutation was reverted from a scratchpad copy of the file**, never with `git checkout --`.
That is 14-02's lesson (which cost that wave its uncommitted `memory.py` edits) applied rather than
re-learned; `grep -c MUTATION` on each file confirmed 0 after each revert, and the post-revert
selector run was green before the next mutation was taken.

### The two prose gates: honest green, with the reason

The README and OPERATIONS greps were **not** mutation-tested, deliberately, and this is the reason
rather than an omission: for a content-presence gate on prose, *the gate is the content change
itself*. Deleting the sentence to watch the grep go red is a tautology — it tests `grep`, not the
document. What makes them non-vacuous instead is that **every one had a measured zero-or-known
baseline on this tree before the edit**: `Cost is computed from list prices` 1 → **0**;
`COST_DISCOUNT_FACTOR` 0 → **3**; `INFERENCE_GEO_MULTIPLIER` 0 → **2**; `1.33` 0 → **1**;
`telemetry` in README 0 → **1**. The `>= 1` form proves nothing when the baseline is not zero
(11-03's lesson); here each baseline was measured and each was zero.

The substantive check on the prose is a review against CONTEXT's honesty constraint, recorded here:
the README bullet states **approximation, not the invoice** in its first four words; carries the
telemetry caveat **with the 0-token example**; and lists four specific exclusions rather than
gesturing at "some things". OPERATIONS states the hybrid geo semantics as a difference in kind and
not as a restatement of the variable name.

## Verification

| Check | Baseline | After |
|-------|----------|-------|
| Full suite, plain | 553 passed / 64 skipped | **563 passed / 65 skipped** |
| Full suite, armed (`DATABASE_URL` → local PG :54329) | 616 passed / 1 skipped | **627 passed / 1 skipped** |
| `grep -rln "cost_discount_factor()\|inference_geo_multiplier()" src/research_agent/` | `usage.py` | **exactly `usage.py` + `service.py`** — as 14-01 predicted |
| Those call results in `service.py` | n/a | **lines 921–922 only, both as dict values in the returned payload** — no arithmetic expression anywhere; confirmed on the diff |
| `grep -c "date.today()\|datetime.now()"` in `tests/test_usage.py` / `tests/test_service.py` | 0 / 0 | **0 / 0** |
| `test_pricing_endpoint_reports_todays_rates` (pre-phase endpoint test) | green | **green, unmodified** |
| `test_cost_and_tokens_are_summed` (pre-phase metrics baseline gate) | green | **green, unmodified** |
| `git diff --stat src/research_agent/limits.py` | — | **+7, −0** — docstring only |
| `pytest tests/test_limits.py` | 51 passed / 4 skipped | **51 passed / 4 skipped** |
| `ruff check src tests` | clean | **clean** |

**Delta fully explained: plain +10 passed / +1 skipped; armed +11 passed / ±0 skipped.** The eleven
new test items are six window helpers in `test_usage.py`, three endpoint tests in `test_service.py`
(`pricing_payload`, `pricing_501`, `payload_additive`), and `test_metrics_includes_embedding_spend`
in **both** backend parameterisations.

**The one new skip, justified:** `test_metrics_includes_embedding_spend[postgres]` skips without
`DATABASE_URL` through `test_store_contract.py`'s own `_skip_without_postgres(request.param)` — the
file-wide idiom every parameterised backend test already uses. It runs and passes in the armed arm,
which is where the both-backends claim is actually made. No pre-existing test changed state, and no
existing assertion was edited: the only `-` lines in the whole tests diff are the import line in
`test_service.py` (one name added) and the line the new store-contract test was inserted above.

`ruff format --check` reports this tree unformatted, as it has all phase: `pyproject.toml:75` says
*"Deliberately not `ruff format`"*. `ruff check` is the repo's gate and it is clean.

## Deviations from Plan

### Departures from the plan's written approach

- **`test_metrics_includes_embedding_spend` is in `tests/test_store_contract.py`, not
  `tests/test_metrics.py`.** The plan's `<files>` list and verify command point at
  `test_metrics.py` while its own action text points at the store-contract idiom; those two cannot
  both be satisfied. `test_metrics.py` has a single SQLite `store` fixture and no parameterisation,
  so following the file list would have landed a SQLite-only assertion and left the Postgres
  `Decimal` coercion — the half that keeps `/metrics` from 500ing on the first recorded run —
  untested. The test went where the parameterised `runs` fixture is. **Consequence for the gate:**
  the plan's verify command (`pytest tests/test_metrics.py tests/test_service.py -k …`) would have
  collected only `payload_additive` and reported green while the embedding assertion ran nowhere —
  the seventeenth vacuous gate, avoided by `--collect-only` rather than by luck. The command was
  widened to `tests/`, which is also the form VALIDATION row 10 already specifies.
- **Mutation L was supplemented with L′.** The plan predicted `test_metrics_includes_embedding_spend`
  would red "with a KeyError/missing-key on `embedding_usd`". It reds with a `KeyError` on
  `embedding_cost_usd`, one step earlier and in `_summarise`, which also reds every other metrics
  test. L′ (drop only the payload key) produces the predicted failure and reds nothing else.
- **`price_for` delegates to `window_for`** rather than the two coexisting. Not in the plan; the
  alternative is two copies of "which window covers this day", which is how a rate and its dates
  stop agreeing.
- **The endpoint gained a `_window_payload` serialiser at module level**, as the plan's "small local
  serialiser keeps the endpoint thin" allowed, placed above `pricing()` rather than nested inside it
  so it is readable next to the payload it shapes.
- **`test_pricing_payload_carries_multipliers_windows_and_embedding` asserts key *sets* on
  `usd_per_mtok`**, not just presence — `set(...) == {four names}` also catches a rate class being
  dropped, which a `<=` containment check would not.

### Not done, deliberately

- **No new ADR.** CONTEXT says this phase is *"not a reversal — a pure extension of DEC-12"*, and
  nothing recorded was overturned: `pricing_unknown` still fails loud and never zero, effective
  dating still resolves by run date, list prices are still list prices. `docs/adr/README.md`'s
  supersession convention has nothing to apply to. Stated rather than left silent.
- **No live-deploy checkpoint.** This ships with the **next deploy**; recorded in OPERATIONS' new
  deployment paragraph and echoed here, which is what VALIDATION's manual row means by "record
  which". At neutral defaults (both variables unset, responses reporting no billed geo) the deployed
  numbers do not move, so there is nothing to sequence, and the schema migration is idempotent under
  the advisory lock `ensure_schema` already holds.
- **No guardrail change.** `DEMO_RESERVED_RUN_USD`, `DEMO_DAILY_USD_CAP` and
  `AGENT_MAX_RUN_COST_USD` keep their defaults; the ~1.33 threshold is a docs note, per the settled
  decision. `limits.py`'s only change is a docstring.

## Threat model outcomes

| Threat ID | Disposition | Outcome |
|-----------|-------------|---------|
| T-14-09 | mitigate | **Closed.** `test_payload_additive_for_deployed_consumers` names all eight pre-phase cost keys and all fifteen pre-phase `RunResponse` fields explicitly. Mutation M (rename `total_usd`) and L′ both red it. The gate that collected zero tests at plan time now collects one and has been watched to fail. |
| T-14-10 | mitigate | **Closed.** `grep -rln` returns exactly `usage.py` + `service.py`, and in `service.py` both call results appear only as dict values inside the returned payload (lines 921–922, confirmed on the diff). The behavioural guarantee remains 14-02's e2e ratio gate, which is unchanged and green. |
| T-14-11 | mitigate | **Closed.** `windows.next` is nullable from day one; `next_window` returns `None` at `date(2026, 9, 1)`, at `date(2030, 1, 1)` and for both undated models, and the endpoint test accepts `None` or a dict without asserting which. No assertion anywhere in the two touched test files consults today's date. |
| T-14-12 | mitigate | **Closed.** The telemetry phrasing appears in three places that a reader can reach independently: the `/pricing` `embedding.note` field, the README bullet (with the 0-token example), and OPERATIONS' multipliers section. None of them claims invoice parity; the README says *approximation, not the invoice* in its first four words. |
| T-14-SC | accept | No packages installed. `pyproject.toml` untouched. |

**New threat surface: none.** `/pricing` was already public and unauthenticated; the three new keys
expose published rates, two operator-set numbers and one model name — no secrets, no per-caller
data, nothing derived from user input. The `/metrics` additions are sums over a column that already
existed. No new endpoint, no auth path, no schema change, no new file.

## Known Stubs

None.

One piece of **untested-by-construction** behaviour, stated rather than hidden: no test asserts what
`windows.next` contains *today*, on purpose — that is the whole point of T-14-11, and the price of
it is that the current-vs-next arrangement in the live payload is verified by the helper tests at
fixed dates plus a shape check, never end to end at today's date. The first post-deploy `GET
/pricing` is where a human sees the two windows side by side.

## Deferred Issues

- **`inference_geo` is still not persisted** (carried from 14-01 and 14-02). `/pricing` now reports
  the configured *rate*, and the runs table still has no geo column, so "we multiplied by 1.1"
  remains true and "we can show you which runs" remains unanswerable.
- **`embedding_usd` rounds at 6 decimal places**, which is the shape `total_usd` already had. A
  single run's Voyage spend (~$0.0000015) therefore reports as `$0.000002`, and a handful of runs
  round to something coarse relative to the underlying figure. Correct for a dollar field and
  consistent with the rest of the payload; worth knowing before anyone reads `embedding_usd` as
  precise at low volume.
- **The 1h cache-write rate remains unmodelled** (carried from 14-01). It is now named in README's
  "still not included" list, which was the docs pass 14-01 suggested; no code change.

## Commits

| Commit | Type | Summary |
|--------|------|---------|
| `c91a2a5` | feat | /pricing says which window, what comes next, and what it embeds with |
| `e38d661` | feat | /metrics breaks out the embedding spend it was already counting |
| `e73e13b` | docs | Say which number this is, and which one it still is not |

## Self-Check: PASSED

- `src/research_agent/usage.py`, `service.py`, `metrics.py`, `limits.py` — all FOUND (modified)
- `tests/test_usage.py`, `tests/test_service.py`, `tests/test_store_contract.py` — all FOUND (modified)
- `README.md`, `docs/OPERATIONS.md` — FOUND (modified)
- `.planning/phases/14-real-cost-accounting/14-03-SUMMARY.md` — FOUND (created)
- Commits `c91a2a5`, `e38d661`, `e73e13b` — all resolve in `git log`
- Working tree clean apart from this summary and the state files it updates
