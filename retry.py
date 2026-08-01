"""
Per-node retry with exponential backoff.

A graph node is a whole unit of work -- one API call plus the state updates
around it -- so retrying at the node boundary is the right granularity: a
transient 529 costs one repeated node, not a failed run. The SDK's own
built-in retries cover a single HTTP request; this covers the node.

Retries are *recorded*, not hidden. Every attempt appends an entry to
state["trace"], so /trace shows that a run was slow because the API pushed
back rather than leaving it a mystery.

Tunable from the environment:

    AGENT_MAX_ATTEMPTS      total attempts per node, including the first (4)
    AGENT_RETRY_BASE_DELAY  seconds before the first retry (1.0)
    AGENT_RETRY_MAX_DELAY   ceiling for any single sleep (30.0)
"""

from __future__ import annotations

import functools
import os
import random
import time
from collections.abc import Callable
from typing import TypeVar

import anthropic

T = TypeVar("T")


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ[name])
    except (KeyError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ[name])
    except (KeyError, ValueError):
        return default


MAX_ATTEMPTS = _env_int("AGENT_MAX_ATTEMPTS", 4)
BASE_DELAY = _env_float("AGENT_RETRY_BASE_DELAY", 1.0)
MAX_DELAY = _env_float("AGENT_RETRY_MAX_DELAY", 30.0)

# Statuses worth trying again. Deliberately excludes 400/401/403/404/422:
# those are our bug or our key, and retrying only burns wall-clock time.
RETRYABLE_STATUS = frozenset({408, 409, 425, 429, 500, 502, 503, 504, 529})


def is_retryable(exc: BaseException) -> bool:
    """Whether this failure has any chance of succeeding on a second attempt."""
    if isinstance(exc, (anthropic.APIConnectionError, anthropic.APITimeoutError)):
        return True
    if isinstance(exc, anthropic.RetryableError):
        return True
    if isinstance(exc, anthropic.APIStatusError):
        return exc.status_code in RETRYABLE_STATUS
    return False


def retry_after_seconds(exc: BaseException) -> float | None:
    """The server's own retry-after hint, when it sent one. Honouring it
    matters for 429s: our backoff curve is a guess, the header is not."""
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if not headers:
        return None
    raw = headers.get("retry-after")
    if raw is None:
        return None
    try:
        return max(0.0, float(raw))
    except (TypeError, ValueError):
        return None  # HTTP-date form; fall back to our own backoff


def compute_delay(
    attempt: int,
    exc: BaseException | None = None,
    *,
    base_delay: float = BASE_DELAY,
    max_delay: float = MAX_DELAY,
    rng: Callable[[], float] = random.random,
) -> float:
    """Equal-jitter exponential backoff for `attempt` (1 = first retry).

    Half the delay is fixed and half is random, which keeps the growth curve
    intact while stopping a fleet of workers from retrying in lockstep.
    A server-supplied retry-after wins if it asks us to wait longer.
    """
    exponential = min(max_delay, base_delay * (2 ** (attempt - 1)))
    delay = exponential / 2 + exponential / 2 * rng()

    hinted = retry_after_seconds(exc) if exc is not None else None
    if hinted is not None:
        delay = max(delay, hinted)

    return min(delay, max_delay)


def call_with_retry(
    thunk: Callable[[], T],
    *,
    max_attempts: int = MAX_ATTEMPTS,
    base_delay: float = BASE_DELAY,
    max_delay: float = MAX_DELAY,
    on_retry: Callable[[int, float, BaseException], None] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    rng: Callable[[], float] = random.random,
) -> T:
    """Run `thunk`, retrying retryable failures with backoff.

    Re-raises the last exception once the budget is spent, so callers keep
    seeing real anthropic errors and can handle them as they always did.
    `sleep` and `rng` are injectable so tests run instantly and deterministically.
    """
    attempt = 0
    while True:
        try:
            return thunk()
        except BaseException as exc:  # noqa: BLE001 - re-raised below
            attempt += 1
            if attempt >= max_attempts or not is_retryable(exc):
                raise
            delay = compute_delay(
                attempt, exc, base_delay=base_delay, max_delay=max_delay, rng=rng
            )
            if on_retry:
                on_retry(attempt, delay, exc)
            sleep(delay)


def retry_node(name: str, **retry_kwargs):
    """Decorate a graph node so its whole body is retried on transient errors.

    Nodes overwrite their own state fields rather than accumulating into them,
    so re-running one is safe: the second attempt lands on the same state the
    first one started from. Retry attempts are appended to state["trace"].
    """

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(state):
            def on_retry(attempt: int, delay: float, exc: BaseException) -> None:
                state.setdefault("trace", []).append(
                    {
                        "node": name,
                        "event": "retry",
                        "attempt": attempt,
                        "backoff_seconds": round(delay, 2),
                        "error": type(exc).__name__,
                    }
                )

            return call_with_retry(lambda: fn(state), on_retry=on_retry, **retry_kwargs)

        return wrapper

    return decorator
