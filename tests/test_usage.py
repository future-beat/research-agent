"""
Cost accounting. Rates are asserted against the published price table, so a
mistake here shows up as a failing test rather than as a wrong invoice.
"""

from datetime import date

import pytest

import usage as usage_accounting
from usage import CallUsage, new_usage, price_for, record, total_tokens


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
