"""
Token and cost accounting.

The iteration and revision caps bound how many model calls a run makes. They
say nothing about what those calls cost -- a capped run can still be an
expensive one. This module turns each response's `usage` object into dollars
so the supervisor can bound spend as well as call count, and so `/metrics` can
report what the service actually costs to run.

Prices are effective-dated. Claude Sonnet 5 is on introductory pricing
($2/$10 per MTok) through 2026-08-31 and moves to $3/$15 on 2026-09-01, so a
single hardcoded rate would silently under-report by a third the moment that
window closes. `price_for()` resolves the rate for a date, defaulting to today.

Rates: https://platform.claude.com/docs/en/about-claude/pricing
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime, timezone

# Web search bills per search on top of tokens. Failed searches are not billed,
# and the API only counts successful ones, so this needs no error handling.
WEB_SEARCH_USD_PER_REQUEST = 10.0 / 1000
# Web fetch has no per-request charge -- fetched content is billed as input
# tokens, which the usage object already reports. Tracked but never priced.

_PER_MTOK = 1_000_000


@dataclass(frozen=True)
class Price:
    """USD per million tokens, by token class."""

    input: float
    output: float
    cache_write_5m: float
    cache_read: float


@dataclass(frozen=True)
class PriceWindow:
    """A price and the date range it applies to. `until` is inclusive.

    The payload is deliberately not pinned to `Price`: `covers()` is a date
    comparison and never inspects it, so Voyage's flat USD/MTok float reuses
    this window rather than being padded into a four-field dataclass whose
    other three fields would be meaningless. One effective-dating idiom, two
    shapes of price.
    """

    price: Price | float
    since: date | None = None
    until: date | None = None

    def covers(self, day: date) -> bool:
        return (self.since is None or day >= self.since) and (
            self.until is None or day <= self.until
        )


# Only the models this service might plausibly run. Adding one means adding a
# row here -- an unpriced model is reported honestly rather than costed at zero.
PRICES: dict[str, list[PriceWindow]] = {
    "claude-sonnet-5": [
        PriceWindow(
            Price(input=2.0, output=10.0, cache_write_5m=2.50, cache_read=0.20),
            until=date(2026, 8, 31),  # introductory pricing
        ),
        PriceWindow(
            Price(input=3.0, output=15.0, cache_write_5m=3.75, cache_read=0.30),
            since=date(2026, 9, 1),
        ),
    ],
    "claude-opus-5": [
        PriceWindow(Price(input=5.0, output=25.0, cache_write_5m=6.25, cache_read=0.50)),
    ],
    "claude-haiku-4-5": [
        PriceWindow(Price(input=1.0, output=5.0, cache_write_5m=1.25, cache_read=0.10)),
    ],
}


# Voyage embedding models, priced flat in USD per million tokens -- the
# embedding endpoint has no output tokens, no cache classes, and no per-request
# charge, so the four-field Price above has nothing to say about it. The window
# type is shared anyway; see PriceWindow's docstring.
#
# Rates verified 2026-08-06 against https://docs.voyageai.com/docs/pricing.
# Voyage publishes no dated windows, so each rate opens an unbounded one from
# verification; a future change closes it with `until=`, exactly the way the
# Sonnet 5 introductory boundary is recorded above. Adding a model means adding
# a row: an absent one raises rather than costing a run at zero.
#
# The voyage-4 family is deliberately absent until something here can target
# it. It also carries a 200M-token free allowance that this table does not
# model, which is why the cost preview says out loud that it quotes list price.
VOYAGE_PRICES_VERIFIED = date(2026, 8, 6)

VOYAGE_PRICES: dict[str, list[PriceWindow]] = {
    "voyage-3.5": [PriceWindow(0.06)],
    "voyage-3.5-lite": [PriceWindow(0.02)],
    "voyage-3-large": [PriceWindow(0.18)],
}


class UnknownModelPricing(LookupError):
    """No price on file for this model on this date."""


def price_for(model: str, on: date | None = None) -> Price:
    day = on or datetime.now(timezone.utc).date()
    for window in PRICES.get(model, ()):
        if window.covers(day):
            return window.price
    raise UnknownModelPricing(f"No price for {model!r} on {day.isoformat()}.")


def voyage_price_for(model: str, on: date | None = None) -> float:
    """USD per million tokens for a Voyage embedding model.

    Same resolution loop as `price_for`, same exception, and for the same
    reason: an unlisted model must be an error and never a zero. A re-embedding
    run is the one place in this service where a wrong price is not a reporting
    inaccuracy but a spending decision made on a false number, so the caller is
    made to handle the absence rather than shown $0.00.
    """
    day = on or datetime.now(timezone.utc).date()
    for window in VOYAGE_PRICES.get(model, ()):
        if window.covers(day):
            return float(window.price)
    raise UnknownModelPricing(
        f"No Voyage embedding price for {model!r} on {day.isoformat()}. "
        f"Priced models: {', '.join(sorted(VOYAGE_PRICES))}."
    )


def preview_cost_usd(total_tokens: int, model: str, on: date | None = None) -> float:
    """What embedding `total_tokens` tokens with `model` will cost, at list price.

    Pure arithmetic and nothing else. Counting the tokens is the caller's job
    precisely so this stays unit-testable: Voyage's `count_tokens` fetches a
    tokenizer from the Hugging Face hub on its first call, and a cost function
    that needed the network to compute a multiplication would be untestable
    offline for no reason.
    """
    return total_tokens * voyage_price_for(model, on) / _PER_MTOK


# --------------------------------------------------------------------------
# Per-call extraction
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class CallUsage:
    """One model call's usage. Field names mirror the SDK's `usage` object.

    `input_tokens` is the *uncached remainder* -- cached tokens are reported
    separately and billed at different rates, so the three must be summed to
    get the prompt size.
    """

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    web_search_requests: int = 0
    web_fetch_requests: int = 0

    @classmethod
    def from_response(cls, response) -> CallUsage:
        usage = getattr(response, "usage", None)
        if usage is None:
            return cls()

        server_tools = getattr(usage, "server_tool_use", None)

        def field(obj, name: str) -> int:
            return int(getattr(obj, name, None) or 0)

        return cls(
            input_tokens=field(usage, "input_tokens"),
            output_tokens=field(usage, "output_tokens"),
            cache_read_input_tokens=field(usage, "cache_read_input_tokens"),
            cache_creation_input_tokens=field(usage, "cache_creation_input_tokens"),
            web_search_requests=field(server_tools, "web_search_requests"),
            web_fetch_requests=field(server_tools, "web_fetch_requests"),
        )

    def cost_usd(self, model: str, on: date | None = None) -> float:
        p = price_for(model, on)
        return (
            self.input_tokens * p.input
            + self.output_tokens * p.output
            + self.cache_read_input_tokens * p.cache_read
            + self.cache_creation_input_tokens * p.cache_write_5m
        ) / _PER_MTOK + self.web_search_requests * WEB_SEARCH_USD_PER_REQUEST


# --------------------------------------------------------------------------
# Per-run accumulation
# --------------------------------------------------------------------------

# Kept as a plain dict rather than a dataclass because it lives in AgentState,
# which is persisted to SQLite as JSON between a run and its follow-ups.
TOKEN_FIELDS = (
    "input_tokens",
    "output_tokens",
    "cache_read_input_tokens",
    "cache_creation_input_tokens",
    "web_search_requests",
    "web_fetch_requests",
)


def new_usage() -> dict:
    totals = dict.fromkeys(TOKEN_FIELDS, 0)
    totals["calls"] = 0
    totals["cost_usd"] = 0.0
    # True once a call is made against a model with no price on file: its
    # tokens are counted but its cost is not, so `cost_usd` is a floor rather
    # than a total. Surfaced rather than silently costing the call at zero.
    totals["pricing_unknown"] = False
    return totals


def record(totals: dict, call: CallUsage, model: str, on: date | None = None) -> float:
    """Fold one call into a run's totals. Returns that call's cost."""
    for field in TOKEN_FIELDS:
        totals[field] = totals.get(field, 0) + getattr(call, field)
    totals["calls"] = totals.get("calls", 0) + 1

    try:
        cost = call.cost_usd(model, on)
    except UnknownModelPricing:
        totals["pricing_unknown"] = True
        return 0.0

    totals["cost_usd"] = round(totals.get("cost_usd", 0.0) + cost, 10)
    return cost


def total_tokens(totals: dict) -> int:
    """Every token billed, cached or not."""
    return sum(
        totals.get(field, 0)
        for field in (
            "input_tokens",
            "output_tokens",
            "cache_read_input_tokens",
            "cache_creation_input_tokens",
        )
    )


def max_run_cost_usd() -> float:
    """Per-run spend cap. Zero or negative disables it."""
    try:
        return float(os.environ.get("AGENT_MAX_RUN_COST_USD", "1.00"))
    except ValueError:
        return 1.00
