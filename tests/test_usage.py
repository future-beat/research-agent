"""
Cost accounting. Rates are asserted against the published price table, so a
mistake here shows up as a failing test rather than as a wrong invoice.
"""

import contextvars
import threading
from datetime import date

import pytest

from research_agent import usage as usage_accounting
from research_agent.usage import CallUsage, new_usage, price_for, record, total_tokens


class FakeServerToolUse:
    def __init__(self, web_search_requests=0, web_fetch_requests=0):
        self.web_search_requests = web_search_requests
        self.web_fetch_requests = web_fetch_requests


class FakeUsage:
    def __init__(self, **fields):
        self.input_tokens = fields.get("input_tokens", 0)
        self.output_tokens = fields.get("output_tokens", 0)
        self.cache_read_input_tokens = fields.get("cache_read_input_tokens")
        self.cache_creation_input_tokens = fields.get("cache_creation_input_tokens")
        self.server_tool_use = fields.get("server_tool_use")
        # Deliberately *not* defaulted: this fake stands in for both a current
        # SDK response, which carries `inference_geo`, and an older one that
        # does not. Only the callers that pass it get the attribute at all.
        if "inference_geo" in fields:
            self.inference_geo = fields["inference_geo"]


class FakeResponse:
    def __init__(self, usage=None):
        self.usage = usage


# --------------------------------------------------------------------------
# The price table
# --------------------------------------------------------------------------


def test_sonnet_5_introductory_pricing_applies_before_september():
    price = price_for("claude-sonnet-5", date(2026, 8, 31))
    assert (price.input, price.output) == (2.0, 10.0)


def test_sonnet_5_standard_pricing_applies_from_september():
    """The introductory window closes 2026-08-31. A single hardcoded rate
    would under-report by a third from the next morning onwards."""
    price = price_for("claude-sonnet-5", date(2026, 9, 1))
    assert (price.input, price.output) == (3.0, 15.0)


def test_the_two_sonnet_windows_do_not_overlap_or_leave_a_gap():
    for day in (date(2026, 1, 1), date(2026, 8, 31), date(2026, 9, 1), date(2030, 1, 1)):
        matches = [w for w in usage_accounting.PRICES["claude-sonnet-5"] if w.covers(day)]
        assert len(matches) == 1, day


def test_cache_rates_are_multiples_of_the_input_rate():
    """Cache writes are 1.25x base input and reads 0.1x. Encoding them as
    absolute numbers is easy to get wrong, so pin the relationship."""
    for model in usage_accounting.PRICES:
        for window in usage_accounting.PRICES[model]:
            p = window.price
            assert p.cache_write_5m == pytest.approx(p.input * 1.25)
            assert p.cache_read == pytest.approx(p.input * 0.1)


def test_unknown_model_raises_rather_than_costing_zero():
    with pytest.raises(usage_accounting.UnknownModelPricing):
        price_for("gpt-nonexistent")


def test_price_defaults_to_today():
    assert price_for("claude-opus-5").input == 5.0


# --------------------------------------------------------------------------
# Which window, and what comes after it
# --------------------------------------------------------------------------
#
# `/pricing` reports dates, not just rates, so the resolution has to be
# askable for the window itself. Every date below is written out: a helper
# whose tests consulted today's date would be a helper whose tests change
# meaning on 2026-09-01, which is the exact day this code exists for.


def test_window_for_resolves_the_same_boundary_price_for_does():
    assert usage_accounting.window_for("claude-sonnet-5", date(2026, 8, 31)).price.input == 2.0
    assert usage_accounting.window_for("claude-sonnet-5", date(2026, 9, 1)).price.input == 3.0


def test_window_for_carries_the_dates_the_rate_alone_cannot():
    august = usage_accounting.window_for("claude-sonnet-5", date(2026, 8, 31))
    september = usage_accounting.window_for("claude-sonnet-5", date(2026, 9, 1))

    assert (august.since, august.until) == (None, date(2026, 8, 31))
    assert (september.since, september.until) == (date(2026, 9, 1), None)


def test_window_for_raises_on_an_unpriced_model():
    with pytest.raises(usage_accounting.UnknownModelPricing):
        usage_accounting.window_for("gpt-nonexistent", date(2026, 8, 9))


def test_next_window_is_the_september_window_before_the_boundary():
    """The operator-facing half: the step is visible before it is charged."""
    upcoming = usage_accounting.next_window("claude-sonnet-5", date(2026, 8, 9))

    assert upcoming is not None
    assert upcoming.since == date(2026, 9, 1)
    assert upcoming.price.input == 3.0


def test_next_window_is_none_once_the_boundary_has_passed():
    """The time bomb, defused by a test. From 2026-09-01 there is no next
    window, so any consumer that assumed a dict would start crashing on a
    date nobody chose -- `next` is nullable from the day it ships."""
    assert usage_accounting.next_window("claude-sonnet-5", date(2026, 9, 1)) is None
    assert usage_accounting.next_window("claude-sonnet-5", date(2030, 1, 1)) is None


def test_next_window_is_none_for_models_with_one_undated_window():
    for model in ("claude-opus-5", "claude-haiku-4-5"):
        assert usage_accounting.next_window(model, date(2026, 8, 9)) is None, model


# --------------------------------------------------------------------------
# Reading the usage object
# --------------------------------------------------------------------------


def test_extracts_every_field_the_sdk_reports():
    call = CallUsage.from_response(FakeResponse(FakeUsage(
        input_tokens=100,
        output_tokens=50,
        cache_read_input_tokens=200,
        cache_creation_input_tokens=300,
        server_tool_use=FakeServerToolUse(web_search_requests=3, web_fetch_requests=1),
    )))

    assert call.input_tokens == 100
    assert call.output_tokens == 50
    assert call.cache_read_input_tokens == 200
    assert call.cache_creation_input_tokens == 300
    assert call.web_search_requests == 3
    assert call.web_fetch_requests == 1


def test_absent_cache_and_tool_fields_read_as_zero():
    """The SDK leaves these None when nothing was cached and no server tool
    ran -- arithmetic on None would crash the run over bookkeeping."""
    call = CallUsage.from_response(FakeResponse(FakeUsage(input_tokens=10, output_tokens=5)))
    assert call.cache_read_input_tokens == 0
    assert call.web_search_requests == 0


def test_a_response_without_usage_is_all_zeroes():
    assert CallUsage.from_response(FakeResponse(None)) == CallUsage()


# --------------------------------------------------------------------------
# Cost
# --------------------------------------------------------------------------


def test_cost_of_a_plain_call():
    call = CallUsage(input_tokens=1_000_000, output_tokens=1_000_000)
    assert call.cost_usd("claude-sonnet-5", date(2026, 8, 1)) == pytest.approx(12.0)


def test_cached_tokens_are_priced_separately_from_fresh_input():
    call = CallUsage(cache_read_input_tokens=1_000_000)
    assert call.cost_usd("claude-sonnet-5", date(2026, 8, 1)) == pytest.approx(0.20)


def test_web_searches_are_billed_per_search_on_top_of_tokens():
    call = CallUsage(web_search_requests=1000)
    assert call.cost_usd("claude-sonnet-5", date(2026, 8, 1)) == pytest.approx(10.0)


def test_web_fetches_cost_nothing_beyond_their_tokens():
    call = CallUsage(web_fetch_requests=500)
    assert call.cost_usd("claude-sonnet-5", date(2026, 8, 1)) == 0.0


def test_the_same_call_costs_more_after_the_intro_window_closes():
    call = CallUsage(input_tokens=1_000_000, output_tokens=1_000_000)
    before = call.cost_usd("claude-sonnet-5", date(2026, 8, 31))
    after = call.cost_usd("claude-sonnet-5", date(2026, 9, 1))
    assert after == pytest.approx(before * 1.5)


# --------------------------------------------------------------------------
# Accumulation across a run
# --------------------------------------------------------------------------


def test_a_fresh_run_has_spent_nothing():
    totals = new_usage()
    assert totals["cost_usd"] == 0.0
    assert totals["calls"] == 0
    assert totals["pricing_unknown"] is False


def test_calls_accumulate():
    totals = new_usage()
    for _ in range(3):
        record(totals, CallUsage(input_tokens=1000, output_tokens=100), "claude-sonnet-5",
               date(2026, 8, 1))

    assert totals["calls"] == 3
    assert totals["input_tokens"] == 3000
    assert totals["output_tokens"] == 300
    assert totals["cost_usd"] == pytest.approx(3 * (1000 * 2.0 + 100 * 10.0) / 1_000_000)


def test_record_returns_the_cost_of_that_call_alone():
    totals = new_usage()
    record(totals, CallUsage(input_tokens=1_000_000), "claude-sonnet-5", date(2026, 8, 1))
    second = record(totals, CallUsage(input_tokens=1_000_000), "claude-sonnet-5", date(2026, 8, 1))
    assert second == pytest.approx(2.0)
    assert totals["cost_usd"] == pytest.approx(4.0)


def test_an_unpriced_model_counts_tokens_and_flags_the_gap():
    """Cost becomes a floor, not a total -- and says so, rather than
    reporting a confident zero that would disable the budget guardrail
    without anyone noticing."""
    totals = new_usage()
    cost = record(totals, CallUsage(input_tokens=5000, output_tokens=100), "some-new-model")

    assert cost == 0.0
    assert totals["cost_usd"] == 0.0
    assert totals["input_tokens"] == 5000  # tokens still counted
    assert totals["pricing_unknown"] is True


def test_total_tokens_sums_cached_and_uncached():
    totals = new_usage()
    record(
        totals,
        CallUsage(
            input_tokens=10, output_tokens=20,
            cache_read_input_tokens=30, cache_creation_input_tokens=40,
        ),
        "claude-sonnet-5",
        date(2026, 8, 1),
    )
    assert total_tokens(totals) == 100


# --------------------------------------------------------------------------
# Budget configuration
# --------------------------------------------------------------------------


def test_budget_defaults_to_one_dollar(monkeypatch):
    monkeypatch.delenv("AGENT_MAX_RUN_COST_USD", raising=False)
    assert usage_accounting.max_run_cost_usd() == 1.00


def test_budget_reads_the_environment(monkeypatch):
    monkeypatch.setenv("AGENT_MAX_RUN_COST_USD", "0.25")
    assert usage_accounting.max_run_cost_usd() == 0.25


def test_an_unparseable_budget_falls_back_to_the_default(monkeypatch):
    """A typo in an env var should not silently remove the spend cap."""
    monkeypatch.setenv("AGENT_MAX_RUN_COST_USD", "twenty pence")
    assert usage_accounting.max_run_cost_usd() == 1.00


# --------------------------------------------------------------------------
# Multipliers: list price is not the invoice
# --------------------------------------------------------------------------
#
# Two things move a real bill away from the rate card: a negotiated discount,
# which the API never reports, and the data-residency multiplier, which it
# does. Both are applied in `CallUsage.cost_usd` and nowhere else, so these
# tests are the whole contract -- everything downstream (the per-run cap, the
# run record, /metrics, the daily-cap reserve math, the API payload) reads the
# number this one function returns.
#
# Every date below is written out. Nothing here may consult today's date: the
# Sonnet 5 boundary is 2026-08-31, and a suite that goes red on 2026-09-01
# because it assumed a window would still be current is a suite that has to be
# edited to stay honest.

FIXED_AUGUST = date(2026, 8, 1)
A_MILLION_INPUT_TOKENS_AT_LIST = 2.0  # claude-sonnet-5, introductory window


def test_multiplier_choke_point_composes_discount_and_geo(monkeypatch):
    """Discount and geo compose multiplicatively at the single site.

    Read as arithmetic: a million input tokens at the introductory $2/MTok,
    billed 1.1x because the response said inference ran in the US, then 0.9x
    because this deployment negotiated ten percent off.
    """
    monkeypatch.setenv("COST_DISCOUNT_FACTOR", "0.9")
    monkeypatch.setenv("INFERENCE_GEO_MULTIPLIER", "1.1")

    call = CallUsage(input_tokens=1_000_000, inference_geo="us")
    assert call.cost_usd("claude-sonnet-5", FIXED_AUGUST) == pytest.approx(2.0 * 1.1 * 0.9)


def test_unset_multipliers_change_nothing_for_the_deployed_service(monkeypatch):
    """The neutral half of the same contract.

    With no env set and a response that reports no geo -- which is every call
    this service makes today -- cost is exactly what it was before this phase
    existed. The feature is opt-in or it is a silent repricing of a live
    service.
    """
    monkeypatch.delenv("COST_DISCOUNT_FACTOR", raising=False)
    monkeypatch.delenv("INFERENCE_GEO_MULTIPLIER", raising=False)

    call = CallUsage(input_tokens=1_000_000)
    assert call.cost_usd("claude-sonnet-5", FIXED_AUGUST) == A_MILLION_INPUT_TOKENS_AT_LIST


def test_geo_applies_by_response_not_by_env(monkeypatch):
    """The env sets the rate; the response decides whether it applies.

    A workspace can carry `default_inference_geo: "us"`, so a request that
    never asked for a geo can still be billed at the US rate -- and equally, an
    operator who sets the multiplier on a globally-routed deployment would
    otherwise inflate every number. Configuration cannot know; the response
    does, so the response is what is believed.
    """
    monkeypatch.setenv("INFERENCE_GEO_MULTIPLIER", "1.1")
    monkeypatch.delenv("COST_DISCOUNT_FACTOR", raising=False)

    def cost(geo):
        return CallUsage(input_tokens=1_000_000, inference_geo=geo).cost_usd(
            "claude-sonnet-5", FIXED_AUGUST
        )

    # Configured at 1.1x, but these calls did not run in a billed geo.
    assert cost("") == pytest.approx(2.0)
    assert cost("global") == pytest.approx(2.0)
    # This one did.
    assert cost("us") == pytest.approx(2.0 * 1.1)

    # And applicability is read off the response, with the file's defensive
    # idiom: a usage object that never heard of the field means "not billed",
    # not an AttributeError halfway through a run.
    reported = CallUsage.from_response(
        FakeResponse(FakeUsage(input_tokens=10, inference_geo="us"))
    )
    assert reported.inference_geo == "us"
    silent = CallUsage.from_response(FakeResponse(FakeUsage(input_tokens=10)))
    assert silent.inference_geo == ""


def test_pricing_unknown_survives_multipliers(monkeypatch):
    """Configured multipliers do not turn a missing price into a number.

    Two ways to be unpriced now: an unlisted model, and a listed model that
    reports a geo nobody has a rate for. Both take the same route -- tokens
    counted, cost left a floor, the gap flagged -- because a guessed 1.0x is
    exactly the confident zero DEC-12 exists to forbid.
    """
    monkeypatch.setenv("COST_DISCOUNT_FACTOR", "0.9")
    monkeypatch.setenv("INFERENCE_GEO_MULTIPLIER", "1.1")

    totals = new_usage()
    cost = record(
        totals, CallUsage(input_tokens=5000, output_tokens=100), "some-new-model", FIXED_AUGUST
    )
    assert cost == 0.0
    assert totals["cost_usd"] == 0.0
    assert totals["input_tokens"] == 5000
    assert totals["pricing_unknown"] is True

    # A priced model, but the response says it ran somewhere with no published
    # adjustment. Guessing 1.0 here would under-report a real bill.
    totals = new_usage()
    cost = record(
        totals,
        CallUsage(input_tokens=5000, output_tokens=100, inference_geo="eu"),
        "claude-sonnet-5",
        FIXED_AUGUST,
    )
    assert cost == 0.0
    assert totals["cost_usd"] == 0.0
    assert totals["input_tokens"] == 5000
    assert totals["pricing_unknown"] is True


def test_the_web_search_fee_is_discounted_but_not_geo_multiplied(monkeypatch):
    """The two multipliers have different bases, and it is not an oversight.

    The published 1.1x is scoped to token pricing categories, and a per-search
    fee is not one. A negotiated discount is applied to the invoice, which
    includes the fee. So the fee takes the discount and skips the geo.
    """
    monkeypatch.setenv("COST_DISCOUNT_FACTOR", "0.9")
    monkeypatch.setenv("INFERENCE_GEO_MULTIPLIER", "1.1")

    call = CallUsage(web_search_requests=1000, inference_geo="us")
    assert call.cost_usd("claude-sonnet-5", FIXED_AUGUST) == pytest.approx(10.0 * 0.9)


def test_boundary_with_multipliers(monkeypatch):
    """Multipliers compose with effective-dating; they do not replace it.

    The same call across the Sonnet 5 introductory boundary still costs
    exactly 1.5x more on the far side, and each side is still halved by the
    discount. A multiplier applied to a stale rate, or a rate resolved after
    the multiplier had already flattened it, would break one of these two
    assertions and not the other.
    """
    monkeypatch.setenv("COST_DISCOUNT_FACTOR", "0.5")

    call = CallUsage(input_tokens=1_000_000, output_tokens=1_000_000)
    before = call.cost_usd("claude-sonnet-5", date(2026, 8, 31))  # $2/$10
    after = call.cost_usd("claude-sonnet-5", date(2026, 9, 1))  # $3/$15

    assert before == pytest.approx(12.0 * 0.5)
    assert after == pytest.approx(before * 1.5)


def test_a_zero_discount_factor_falls_back_to_neutral(monkeypatch):
    """`COST_DISCOUNT_FACTOR=0` is the fail-open door this clamp closes.

    It is the obvious way to type "no discount", and honouring it would report
    every run at $0.00 -- which the per-run cap and the daily cap would read as
    a service that never spends anything.
    """
    monkeypatch.setenv("COST_DISCOUNT_FACTOR", "0")
    assert usage_accounting.cost_discount_factor() == 1.0
    # And the guardrails still see a real number, not a free run.
    call = CallUsage(input_tokens=1_000_000)
    assert call.cost_usd("claude-sonnet-5", FIXED_AUGUST) == pytest.approx(2.0)


def test_an_unparseable_discount_factor_falls_back_to_neutral(monkeypatch):
    monkeypatch.setenv("COST_DISCOUNT_FACTOR", "ten percent")
    assert usage_accounting.cost_discount_factor() == 1.0


def test_a_nonpositive_geo_multiplier_falls_back_to_the_published_rate(monkeypatch):
    """Unset and nonsense both mean the published 1.1x.

    The default is the *rate*, not blanket applicability -- it costs nothing
    until a response reports a call actually ran in a billed geo.
    """
    monkeypatch.setenv("INFERENCE_GEO_MULTIPLIER", "-1")
    assert usage_accounting.inference_geo_multiplier() == 1.1

    monkeypatch.delenv("INFERENCE_GEO_MULTIPLIER", raising=False)
    assert usage_accounting.inference_geo_multiplier() == 1.1


# --------------------------------------------------------------------------
# Embedding spend: the second provider on the invoice
# --------------------------------------------------------------------------
#
# Voyage's list price for voyage-3.5 is $0.06/MTok, so a million tokens is
# exactly six cents -- every expectation below is that rate read forwards, and
# `on=` is always written out for the same reason it is everywhere else here.

A_MILLION_EMBEDDING_TOKENS_AT_LIST = 0.06  # voyage-3.5


def test_zero_token_response_honest():
    """A 0-token embedding is telemetry, not a pricing failure.

    Phase 13's live re-embed watched Voyage report `total_tokens == 0` for a
    one-word document while returning a perfectly good 1024-dimension vector.
    Treating that as `pricing_unknown` would flag the entire run's cost as a
    floor -- discrediting a $0.15 figure over a provider's rounding of a
    fraction of a cent. It records as what it is: zero tokens, zero dollars.
    """
    totals = new_usage()
    totals["cost_usd"] = 0.25  # a run that has already made some model calls

    cost = usage_accounting.record_embedding(
        totals, "voyage-3.5", 0, requests=1, on=FIXED_AUGUST
    )

    assert cost == 0.0
    assert totals["embedding_tokens"] == 0
    assert totals["embedding_requests"] == 1  # the call happened, and is counted
    assert totals["embedding_cost_usd"] == 0.0
    assert totals["cost_usd"] == 0.25  # untouched
    assert totals["pricing_unknown"] is False


def test_an_unpriced_voyage_model_flags_pricing_unknown():
    """SC-4 reaches Voyage too: an unlisted model is never costed at zero.

    voyage-4 exists and this service has no rate on file for it. The tokens
    are still counted -- they were still spent -- but the dollars are declared
    missing rather than guessed, exactly as an unlisted Claude model is.
    """
    totals = new_usage()

    cost = usage_accounting.record_embedding(
        totals, "voyage-4", 1_000_000, on=FIXED_AUGUST
    )

    assert cost == 0.0
    assert totals["embedding_tokens"] == 1_000_000
    assert totals["embedding_requests"] == 1
    assert totals["embedding_cost_usd"] == 0.0
    assert totals["cost_usd"] == 0.0
    assert totals["pricing_unknown"] is True


def test_embedding_cost_folds_into_cost_usd_once(monkeypatch):
    """The fold, and the multiplier that must not follow it.

    `cost_usd` is the one number the caps, /metrics, spend_since and the API
    payload all read, so embedding spend has to land there or the accounting
    surface is complete everywhere except where anyone looks. It lands there
    exactly once, and it lands *unmultiplied*: the discount is an Anthropic
    discount and the geo rate is a Claude surcharge, and neither has anything
    to say about a different vendor's bill.
    """
    monkeypatch.delenv("COST_DISCOUNT_FACTOR", raising=False)
    monkeypatch.delenv("INFERENCE_GEO_MULTIPLIER", raising=False)

    totals = new_usage()
    cost = usage_accounting.record_embedding(
        totals, "voyage-3.5", 1_000_000, on=FIXED_AUGUST
    )

    assert cost == pytest.approx(A_MILLION_EMBEDDING_TOKENS_AT_LIST)
    assert totals["embedding_cost_usd"] == pytest.approx(A_MILLION_EMBEDDING_TOKENS_AT_LIST)
    assert totals["cost_usd"] == pytest.approx(A_MILLION_EMBEDDING_TOKENS_AT_LIST)

    # The same call under a doubly non-neutral environment: identical numbers.
    monkeypatch.setenv("COST_DISCOUNT_FACTOR", "0.5")
    monkeypatch.setenv("INFERENCE_GEO_MULTIPLIER", "2.0")

    discounted = new_usage()
    assert usage_accounting.record_embedding(
        discounted, "voyage-3.5", 1_000_000, on=FIXED_AUGUST
    ) == pytest.approx(A_MILLION_EMBEDDING_TOKENS_AT_LIST)
    assert discounted["cost_usd"] == pytest.approx(totals["cost_usd"])
    assert discounted["embedding_cost_usd"] == pytest.approx(totals["embedding_cost_usd"])


def test_embedding_tokens_stay_out_of_the_claude_token_sum():
    """Different provider, different unit. Summing them means nothing.

    `total_tokens()` answers "how many tokens did Claude bill for", which is
    the number the token-shaped parts of /metrics report. A Voyage token is
    priced 30x lower and is not interchangeable with one.
    """
    totals = new_usage()
    record(totals, CallUsage(input_tokens=1000, output_tokens=100), "claude-sonnet-5",
           FIXED_AUGUST)
    usage_accounting.record_embedding(totals, "voyage-3.5", 5000, on=FIXED_AUGUST)

    assert total_tokens(totals) == 1100
    assert totals["embedding_tokens"] == 5000
    # The dollars, unlike the tokens, do combine.
    assert totals["cost_usd"] > totals["embedding_cost_usd"] > 0


def test_record_embedding_survives_a_usage_dict_from_before_this_phase():
    """A follow-up on a session persisted last week arrives with none of these
    keys, and must not KeyError its way to a 500."""
    old = {"calls": 2, "cost_usd": 0.1, "pricing_unknown": False}

    usage_accounting.record_embedding(old, "voyage-3.5", 1_000_000, on=FIXED_AUGUST)

    assert old["embedding_tokens"] == 1_000_000
    assert old["embedding_requests"] == 1
    assert old["cost_usd"] == pytest.approx(0.1 + A_MILLION_EMBEDDING_TOKENS_AT_LIST)


def test_meter_isolation_across_contexts():
    """Two runs metering at once must not read each other's tokens.

    The service runs graph nodes in a thread pool and the memory store is a
    module global, so "which run was this embedding for" cannot be answered by
    anything hanging off the embedder. A contextvar answers it structurally:
    a copied context sees its own meter or none at all.
    """
    def metered(tokens: int) -> tuple[int, int]:
        with usage_accounting.embedding_meter() as meter:
            usage_accounting.report_embedding("voyage-3.5", tokens)
            return meter.total_tokens, meter.requests

    assert contextvars.copy_context().run(metered, 25) == (25, 1)
    assert contextvars.copy_context().run(metered, 4000) == (4000, 1)

    # Concurrently, on the threads the service actually uses: each thread
    # starts from an empty context, and both are inside their own meter at the
    # same moment thanks to the barrier.
    both_inside = threading.Barrier(2, timeout=10)
    seen: dict[str, tuple[int, int]] = {}

    def work(name: str, tokens: int) -> None:
        with usage_accounting.embedding_meter() as meter:
            usage_accounting.report_embedding("voyage-3.5", tokens)
            both_inside.wait()
            seen[name] = (meter.total_tokens, meter.requests)

    threads = [
        threading.Thread(target=work, args=("a", 25)),
        threading.Thread(target=work, args=("b", 4000)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert seen == {"a": (25, 1), "b": (4000, 1)}

    # And outside every meter, reporting is a no-op rather than an error --
    # the REPL demo, the migration CLI and every fake-embedder test go through
    # this path on every embed.
    usage_accounting.report_embedding("voyage-3.5", 999)
    with usage_accounting.embedding_meter() as after:
        assert (after.total_tokens, after.requests, after.model) == (0, 0, "")
