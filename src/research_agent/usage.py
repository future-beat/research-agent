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

List price is not the invoice, so two multipliers scale the computed number
without ever touching the table: `COST_DISCOUNT_FACTOR` (a negotiated discount,
invisible to the API) and `INFERENCE_GEO_MULTIPLIER` (the data-residency rate,
applied only to calls whose response reports they ran in a billed geo). Both
apply inside `CallUsage.cost_usd` and nowhere else -- every other consumer in
the service reads that one number.

Anthropic is not the only provider on the invoice. Every research run also
embeds -- once to recall, once to store -- and that spend was accounted
nowhere until `record_embedding` folded it in here. Embedding tokens are
counted separately (a different provider's unit) but their dollars land in the
same `cost_usd`, so the caps, `/metrics` and the API payload inherit them
without a single consumer change.

Rates: https://platform.claude.com/docs/en/about-claude/pricing
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
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
# Multipliers: what the list price is not
# --------------------------------------------------------------------------
#
# List prices above are the rate card. Two things move a real invoice away from
# it: a negotiated discount, which the API cannot report because it is applied
# at billing time, and the data-residency multiplier, which the API *can*
# report per call. Both are applied to computed cost and neither mutates the
# table -- effective-dating resolves exactly as it did before.
#
# Both readers read the environment on every call rather than caching at import
# time, the same way `max_run_cost_usd` does, so a process that has its
# configuration changed under it reports the new number.

DEFAULT_COST_DISCOUNT_FACTOR = 1.0
# The published data-residency rate: `inference_geo: "us"` bills 1.1x across
# all token pricing categories for Claude 4.6 and later.
# https://platform.claude.com/docs/en/about-claude/pricing
DEFAULT_INFERENCE_GEO_MULTIPLIER = 1.1


def cost_discount_factor() -> float:
    """Negotiated discount applied to computed cost. Default 1.0 (list price).

    Zero or negative falls back to neutral instead of being honoured. This is
    not tidiness: the budget guardrails read the number this factor scales, so
    `COST_DISCOUNT_FACTOR=0` -- a plausible typo, and a plausible reading of
    "disable the discount" -- would cost every run at $0.00, and a per-run cap
    compared against $0.00 never fires. That is DEC-12's fail-open scenario
    arriving through a new door, so a misconfiguration fails toward reporting
    *more* cost, never less.
    """
    try:
        factor = float(os.environ.get("COST_DISCOUNT_FACTOR", "1.0"))
    except ValueError:
        return DEFAULT_COST_DISCOUNT_FACTOR
    return factor if factor > 0 else DEFAULT_COST_DISCOUNT_FACTOR


def inference_geo_multiplier() -> float:
    """The rate charged when a response reports it ran in a billed geo.

    This configures the *rate* only. Whether it applies to a given call is
    decided by that call's reported `inference_geo` (see
    `CallUsage._geo_factor`), because a workspace default can put a request in
    a billed geo without the code ever asking for it.

    Same clamp as the discount, for the same reason: a non-positive or
    unparseable value would silently under-report a cost already incurred, so
    it falls back to the published rate.
    """
    try:
        factor = float(os.environ.get("INFERENCE_GEO_MULTIPLIER", "1.1"))
    except ValueError:
        return DEFAULT_INFERENCE_GEO_MULTIPLIER
    return factor if factor > 0 else DEFAULT_INFERENCE_GEO_MULTIPLIER


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
    # Where inference actually ran, as *the response reported it* -- not as
    # configuration claims. See `_geo_factor` for why that distinction is the
    # whole point of the field.
    inference_geo: str = ""

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
            # Same defensive read as every field above: absent on older SDKs
            # and on test fakes, which must mean "not geo-billed", not a crash.
            inference_geo=str(getattr(usage, "inference_geo", None) or ""),
        )

    def _geo_factor(self) -> float:
        """The data-residency multiplier this particular call earned.

        Applicability is observed, not configured. A workspace can set
        `default_inference_geo: "us"` in the Console, so a request that never
        sends the parameter can still be billed at the US rate -- an operator
        env flag would then disagree with the invoice in either direction.
        The response says where inference ran; only the *rate* is configuration.

        An unrecognised value (a future `"eu"`) raises rather than being billed
        at 1.0. `record()` turns that into `pricing_unknown`, which is DEC-12's
        fail-loud shape applied to a pricing dimension instead of a model name.
        """
        if self.inference_geo in ("", "global"):
            return 1.0
        if self.inference_geo == "us":
            return inference_geo_multiplier()
        raise UnknownModelPricing(
            f"No price adjustment on file for inference_geo "
            f"{self.inference_geo!r}. Priced geos: '', 'global', 'us'."
        )

    def cost_usd(self, model: str, on: date | None = None) -> float:
        """What this call cost, in USD -- the one place tokens become dollars.

        Both multipliers apply *here* and nowhere else in the service. Every
        consumer of the number (the per-run cap, the run record, `/metrics`,
        `spend_since` and the daily-cap reserve math, the API payload, the
        evals harness, the demo badge) reads it downstream, so a second
        multiplication site anywhere would double-count silently.
        """
        p = price_for(model, on)
        # The published data-residency multiplier is scoped to "token pricing
        # categories", so it multiplies the four token classes only and leaves
        # the per-search fee alone.
        tokens_usd = (
            self.input_tokens * p.input
            + self.output_tokens * p.output
            + self.cache_read_input_tokens * p.cache_read
            + self.cache_creation_input_tokens * p.cache_write_5m
        ) / _PER_MTOK * self._geo_factor()
        # A negotiated discount is applied at invoice time, to the whole
        # Anthropic bill -- so it takes the web-search fee with it.
        return (
            tokens_usd + self.web_search_requests * WEB_SEARCH_USD_PER_REQUEST
        ) * cost_discount_factor()


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
    # Embeddings are a second provider on the same invoice. Their tokens are
    # deliberately NOT in TOKEN_FIELDS and not in `total_tokens()`: a Voyage
    # token and a Claude token are different units at different prices, and
    # summing them would produce a number that means nothing. Their *dollars*
    # are another matter -- those go into `cost_usd` with everything else.
    totals["embedding_tokens"] = 0
    totals["embedding_requests"] = 0
    totals["embedding_cost_usd"] = 0.0
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


# --------------------------------------------------------------------------
# Embedding accounting: the meter and the fold
# --------------------------------------------------------------------------
#
# The embedder seam returns vectors and nothing else, which is right -- four
# store backends implement it and none of them has any business knowing about
# tokens. So the token count travels out of band instead: the wrapper *reports*
# what it was billed for, and whoever is metering picks it up.
#
# A contextvar rather than a counter on the embedder, because `graph.memory()`
# is a module-global store shared by every concurrent run: an attribute on it
# would attribute one visitor's embeddings to another's bill. The meter is
# entered and read inside a single node frame, so set and read happen in one
# context whichever thread LangGraph runs the node on, and concurrent runs are
# isolated by construction rather than by hope.


@dataclass
class EmbeddingMeter:
    """What one metered scope was billed for. Mutable on purpose."""

    model: str = ""
    total_tokens: int = 0
    requests: int = 0


_EMBEDDING_METER: ContextVar[EmbeddingMeter | None] = ContextVar(
    "research_agent_embedding_meter", default=None
)


@contextmanager
def embedding_meter() -> Iterator[EmbeddingMeter]:
    """Collect every embedding billed inside this block."""
    meter = EmbeddingMeter()
    token = _EMBEDDING_METER.set(meter)
    try:
        yield meter
    finally:
        _EMBEDDING_METER.reset(token)


def report_embedding(model: str, total_tokens: int | None) -> None:
    """Tell the active meter what an embed call was billed for.

    A silent no-op when nothing is metering, and that is the whole reason this
    shape was chosen: the REPL demo, the re-embedding migration and every test
    holding a fake embedder keep working untouched, because reporting into
    nowhere costs nothing and raises nothing.
    """
    meter = _EMBEDDING_METER.get()
    if meter is None:
        return
    meter.model = model
    meter.total_tokens += int(total_tokens or 0)
    meter.requests += 1


def record_embedding(
    totals: dict,
    model: str,
    tokens: int,
    requests: int = 1,
    on: date | None = None,
) -> float:
    """Fold a run's embedding spend into its totals. Returns the cost.

    Mirrors `record()`, including the `.get(..., 0)` reads -- a usage dict
    persisted before this existed has none of these keys, and a follow-up on
    an old session must not KeyError its way to a 500.

    Two deliberate asymmetries with `record()`:

    * **No multipliers.** `COST_DISCOUNT_FACTOR` and the `inference_geo` rate
      are Anthropic dimensions -- a negotiated Anthropic discount and a Claude
      data-residency surcharge. Voyage is a different vendor on a different
      rate card, and applying either here would invent a discount nobody
      negotiated.
    * **Zero tokens is not an error.** Voyage's reported count is telemetry,
      not billing truth: Phase 13 watched it report 0 tokens for a one-word
      document while returning a perfectly good embedding. That records as
      $0.00 through the normal priced path. `pricing_unknown` means "this
      service does not know what this MODEL costs", and reusing it for an odd
      token count would discredit the whole cost figure over a rounding
      anomaly at the provider's end.
    """
    counted = int(tokens or 0)
    totals["embedding_tokens"] = totals.get("embedding_tokens", 0) + counted
    totals["embedding_requests"] = totals.get("embedding_requests", 0) + requests

    try:
        rate = voyage_price_for(model, on)
    except UnknownModelPricing:
        # Same contract as an unpriced Claude model: the tokens are counted,
        # the dollars are not, and `cost_usd` is honestly a floor rather than
        # a total. Never silently zero.
        totals["pricing_unknown"] = True
        return 0.0

    cost = counted * rate / _PER_MTOK
    totals["embedding_cost_usd"] = round(totals.get("embedding_cost_usd", 0.0) + cost, 10)
    # And once more into the one number every consumer already reads.
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
