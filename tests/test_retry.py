"""
Retry tests. `sleep` and `rng` are injected, so the whole file runs in
milliseconds and asserts on exact delays rather than approximate ones.
"""

import anthropic
import httpx
import pytest

from research_agent.retry import call_with_retry, compute_delay, is_retryable, retry_node


def status_error(code: int, headers: dict | None = None) -> anthropic.APIStatusError:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(code, headers=headers or {}, request=request)
    cls = {429: anthropic.RateLimitError, 500: anthropic.InternalServerError}.get(
        code, anthropic.APIStatusError
    )
    return cls(f"http {code}", response=response, body=None)


def connection_error() -> anthropic.APIConnectionError:
    return anthropic.APIConnectionError(
        request=httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    )


class Recorder:
    """Stands in for time.sleep and records what it was asked to wait."""

    def __init__(self):
        self.slept: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.slept.append(seconds)


def flaky(failures: int, exc_factory=lambda: status_error(429)):
    """A callable that fails `failures` times, then returns "ok"."""
    calls = {"n": 0}

    def call():
        calls["n"] += 1
        if calls["n"] <= failures:
            raise exc_factory()
        return "ok"

    call.calls = calls
    return call


# --------------------------------------------------------------------------
# Which failures are worth retrying
# --------------------------------------------------------------------------


@pytest.mark.parametrize("code", [408, 429, 500, 502, 503, 529])
def test_transient_statuses_are_retryable(code):
    assert is_retryable(status_error(code))


@pytest.mark.parametrize("code", [400, 401, 403, 404, 422])
def test_client_errors_are_not_retryable(code):
    """A bad key or a malformed request will fail identically forever."""
    assert not is_retryable(status_error(code))


def test_connection_errors_are_retryable():
    assert is_retryable(connection_error())


def test_unrelated_exceptions_are_not_retryable():
    assert not is_retryable(ValueError("bug in our own code"))


# --------------------------------------------------------------------------
# Backoff shape
# --------------------------------------------------------------------------


def test_backoff_grows_exponentially():
    delays = [
        compute_delay(n, base_delay=1.0, max_delay=100.0, rng=lambda: 1.0) for n in (1, 2, 3, 4)
    ]
    assert delays == [1.0, 2.0, 4.0, 8.0]


def test_jitter_spans_half_the_delay():
    lo = compute_delay(3, base_delay=1.0, max_delay=100.0, rng=lambda: 0.0)
    hi = compute_delay(3, base_delay=1.0, max_delay=100.0, rng=lambda: 1.0)
    assert (lo, hi) == (2.0, 4.0)  # half fixed, half random


def test_delay_is_capped():
    assert compute_delay(20, base_delay=1.0, max_delay=30.0, rng=lambda: 1.0) == 30.0


def test_retry_after_header_wins_when_it_asks_for_longer():
    exc = status_error(429, {"retry-after": "12"})
    assert compute_delay(1, exc, base_delay=1.0, max_delay=60.0, rng=lambda: 1.0) == 12.0


def test_retry_after_is_ignored_when_our_own_backoff_is_longer():
    exc = status_error(429, {"retry-after": "1"})
    assert compute_delay(5, exc, base_delay=1.0, max_delay=60.0, rng=lambda: 1.0) == 16.0


def test_retry_after_still_respects_the_ceiling():
    exc = status_error(429, {"retry-after": "9999"})
    assert compute_delay(1, exc, base_delay=1.0, max_delay=30.0, rng=lambda: 1.0) == 30.0


def test_http_date_retry_after_falls_back_to_our_backoff():
    exc = status_error(429, {"retry-after": "Wed, 21 Oct 2026 07:28:00 GMT"})
    assert compute_delay(1, exc, base_delay=2.0, max_delay=60.0, rng=lambda: 1.0) == 2.0


# --------------------------------------------------------------------------
# The retry loop
# --------------------------------------------------------------------------


def test_succeeds_without_sleeping_when_nothing_fails():
    sleep = Recorder()
    assert call_with_retry(lambda: "ok", sleep=sleep) == "ok"
    assert sleep.slept == []


def test_recovers_after_transient_failures():
    sleep = Recorder()
    call = flaky(2)
    assert call_with_retry(call, sleep=sleep, base_delay=1.0, rng=lambda: 1.0) == "ok"
    assert call.calls["n"] == 3
    assert sleep.slept == [1.0, 2.0]


def test_gives_up_after_the_budget_and_reraises_the_real_error():
    """Callers keep seeing genuine anthropic exceptions, so existing
    error handling in chat.py still works once retries are exhausted."""
    sleep = Recorder()
    call = flaky(99)
    with pytest.raises(anthropic.RateLimitError):
        call_with_retry(call, max_attempts=3, sleep=sleep, rng=lambda: 1.0)
    assert call.calls["n"] == 3
    assert len(sleep.slept) == 2  # no pointless sleep after the final attempt


def test_non_retryable_failures_raise_immediately():
    sleep = Recorder()
    call = flaky(99, lambda: status_error(401))
    with pytest.raises(anthropic.APIStatusError):
        call_with_retry(call, max_attempts=5, sleep=sleep)
    assert call.calls["n"] == 1
    assert sleep.slept == []


def test_max_attempts_of_one_means_no_retries():
    call = flaky(1)
    with pytest.raises(anthropic.RateLimitError):
        call_with_retry(call, max_attempts=1, sleep=Recorder())
    assert call.calls["n"] == 1


def test_keyboard_interrupt_is_not_swallowed():
    def call():
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        call_with_retry(call, sleep=Recorder())


# --------------------------------------------------------------------------
# The node decorator
# --------------------------------------------------------------------------


def test_retry_node_reruns_the_node_and_returns_its_state():
    attempts = {"n": 0}

    @retry_node("researcher", sleep=Recorder(), rng=lambda: 1.0, base_delay=0.0)
    def node(state):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise status_error(529)
        state["research_notes"] = "found it"
        return state

    result = node({"trace": []})
    assert result["research_notes"] == "found it"
    assert attempts["n"] == 3


def test_retry_node_records_every_attempt_in_the_trace():
    """A run that was slow because the API pushed back should say so in
    /trace rather than looking like an unexplained stall."""
    attempts = {"n": 0}

    @retry_node("critic", sleep=Recorder(), rng=lambda: 1.0, base_delay=1.0)
    def node(state):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise status_error(429)
        return state

    trace = node({"trace": []})["trace"]
    assert trace == [
        {"node": "critic", "event": "retry", "attempt": 1,
         "backoff_seconds": 1.0, "error": "RateLimitError"},
        {"node": "critic", "event": "retry", "attempt": 2,
         "backoff_seconds": 2.0, "error": "RateLimitError"},
    ]


def test_retry_node_is_transparent_when_nothing_fails():
    @retry_node("writer", sleep=Recorder())
    def node(state):
        state["draft"] = "d"
        return state

    assert node({"trace": []}) == {"trace": [], "draft": "d"}
