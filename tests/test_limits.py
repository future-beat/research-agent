"""
Demo guardrails.

The service is publicly reachable with live API keys, so these are the tests
that stand between a shared URL and someone else's Anthropic bill.
"""

import time

import pytest
from fastapi import HTTPException

from research_agent import limits
from research_agent.limits import RateLimiter


class FakeRequest:
    def __init__(self, headers=None, host="203.0.113.7"):
        self.headers = headers or {}
        self.client = type("C", (), {"host": host})()


class FakeMetrics:
    def __init__(self, spent=0.0):
        self.spent = spent
        self.queries = []

    def spend_since(self, since: float) -> float:
        self.queries.append(since)
        return self.spent


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for var in ("DEMO_TOKEN", "SESSIONS_TOKEN", "DEMO_RATE_LIMIT_PER_HOUR",
                "DEMO_DAILY_USD_CAP", "TRUST_FORWARDED_FOR"):
        monkeypatch.delenv(var, raising=False)
    limits.reset_limiter()
    yield
    limits.reset_limiter()


# --------------------------------------------------------------------------
# Identifying the caller
# --------------------------------------------------------------------------


def test_fly_client_ip_is_preferred():
    """Fly's proxy overwrites this header on every inbound request, so a
    client cannot forge it."""
    request = FakeRequest({"fly-client-ip": "198.51.100.4"}, host="10.0.0.1")
    assert limits.client_ip(request) == "198.51.100.4"


def test_forwarded_for_is_ignored_by_default():
    """Anyone can set X-Forwarded-For against an unproxied origin. Trusting
    it would let a single caller mint unlimited identities and turn the rate
    limiter into decoration."""
    request = FakeRequest({"x-forwarded-for": "1.2.3.4"}, host="10.0.0.1")
    assert limits.client_ip(request) == "10.0.0.1"


def test_forwarded_for_is_used_when_explicitly_trusted(monkeypatch):
    monkeypatch.setenv("TRUST_FORWARDED_FOR", "true")
    request = FakeRequest({"x-forwarded-for": "1.2.3.4, 10.0.0.9"}, host="10.0.0.1")
    assert limits.client_ip(request) == "1.2.3.4"


def test_a_request_with_no_client_still_yields_a_key():
    request = FakeRequest()
    request.client = None
    assert limits.client_ip(request) == "unknown"


# --------------------------------------------------------------------------
# Rate limiting
# --------------------------------------------------------------------------


def test_requests_up_to_the_limit_are_allowed():
    rl = RateLimiter(limit=3, window_seconds=60)
    assert [rl.check("a", 1000 + i)[0] for i in range(3)] == [True, True, True]


def test_the_next_request_is_refused_with_a_retry_hint():
    rl = RateLimiter(limit=3, window_seconds=60)
    for i in range(3):
        rl.check("a", 1000 + i)

    allowed, retry_after = rl.check("a", 1003)
    assert allowed is False
    assert 0 < retry_after <= 61


def test_the_window_slides():
    rl = RateLimiter(limit=2, window_seconds=60)
    rl.check("a", 1000)
    rl.check("a", 1030)
    assert rl.check("a", 1040)[0] is False
    # The first hit ages out at 1060.
    assert rl.check("a", 1061)[0] is True


def test_clients_are_limited_independently():
    rl = RateLimiter(limit=1, window_seconds=60)
    assert rl.check("a", 1000)[0] is True
    assert rl.check("a", 1001)[0] is False
    assert rl.check("b", 1001)[0] is True


def test_a_limit_of_zero_disables_the_check():
    rl = RateLimiter(limit=0)
    assert all(rl.check("a")[0] for _ in range(100))


def test_stale_keys_are_swept():
    """Every visitor becomes a dict key forever otherwise, which on a public
    endpoint is an unbounded leak."""
    rl = RateLimiter(limit=5, window_seconds=60)
    rl.SWEEP_EVERY = 5

    for i in range(4):
        rl.check(f"old{i}", 1000)
    assert rl.tracked_keys() == 4

    for i in range(10):
        rl.check(f"new{i}", 100_000 + i)

    assert rl.tracked_keys() < 14  # the old keys are gone
    assert all(not key.startswith("old") for key in rl._hits)


def test_the_limiter_is_thread_safe():
    import threading

    rl = RateLimiter(limit=1000, window_seconds=3600)
    errors = []

    def hammer():
        try:
            for _ in range(100):
                rl.check("shared")
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=hammer) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert len(rl._hits["shared"]) == 500  # no lost updates


def test_the_shared_limiter_reconfigures_when_the_setting_changes(monkeypatch):
    monkeypatch.setenv("DEMO_RATE_LIMIT_PER_HOUR", "5")
    assert limits.limiter().limit == 5
    monkeypatch.setenv("DEMO_RATE_LIMIT_PER_HOUR", "50")
    assert limits.limiter().limit == 50


# --------------------------------------------------------------------------
# Token
# --------------------------------------------------------------------------


def test_no_token_configured_means_open():
    limits.check_token(FakeRequest())  # must not raise


def test_a_configured_token_is_required(monkeypatch):
    monkeypatch.setenv("DEMO_TOKEN", "s3cret")
    with pytest.raises(HTTPException) as exc:
        limits.check_token(FakeRequest())
    assert exc.value.status_code == 401


def test_a_wrong_token_is_rejected(monkeypatch):
    monkeypatch.setenv("DEMO_TOKEN", "s3cret")
    with pytest.raises(HTTPException):
        limits.check_token(FakeRequest({"x-demo-token": "guess"}))


def test_the_right_token_passes(monkeypatch):
    monkeypatch.setenv("DEMO_TOKEN", "s3cret")
    limits.check_token(FakeRequest({"x-demo-token": "s3cret"}))


# --------------------------------------------------------------------------
# Sessions token
# --------------------------------------------------------------------------


def test_sessions_token_prefers_its_own_variable(monkeypatch):
    monkeypatch.setenv("SESSIONS_TOKEN", "alpha")
    monkeypatch.setenv("DEMO_TOKEN", "beta")
    assert limits.sessions_token() == "alpha"


def test_sessions_token_falls_back_to_demo_token(monkeypatch):
    """What makes "setting DEMO_TOKEN protects the session endpoints" true
    rather than quietly false."""
    monkeypatch.setenv("DEMO_TOKEN", "beta")
    assert limits.sessions_token() == "beta"


def test_require_sessions_token_refuses_when_nothing_is_configured():
    """The whole point of the hotfix: an operator who forgets the secret must
    not silently reopen the leak. Unset means nobody passes, not everybody."""
    with pytest.raises(HTTPException) as exc:
        limits.require_sessions_token(FakeRequest())
    assert exc.value.status_code == 403


@pytest.mark.parametrize("headers", [{}, {"x-demo-token": "wrong"}])
def test_require_sessions_token_rejects_a_missing_or_wrong_header(monkeypatch, headers):
    monkeypatch.setenv("SESSIONS_TOKEN", "alpha")
    with pytest.raises(HTTPException) as exc:
        limits.require_sessions_token(FakeRequest(headers))
    assert exc.value.status_code == 401


def test_require_sessions_token_accepts_the_configured_token(monkeypatch):
    monkeypatch.setenv("SESSIONS_TOKEN", "alpha")
    assert limits.require_sessions_token(FakeRequest({"x-demo-token": "alpha"})) is None


def test_require_sessions_token_accepts_a_demo_token_value(monkeypatch):
    monkeypatch.setenv("DEMO_TOKEN", "beta")
    limits.require_sessions_token(FakeRequest({"x-demo-token": "beta"}))  # must not raise


# --------------------------------------------------------------------------
# Daily spend cap
# --------------------------------------------------------------------------


def test_spending_under_the_cap_is_allowed(monkeypatch):
    monkeypatch.setenv("DEMO_DAILY_USD_CAP", "5.00")
    limits.check_daily_cap(FakeMetrics(spent=4.99))


def test_reaching_the_cap_refuses_new_runs(monkeypatch):
    monkeypatch.setenv("DEMO_DAILY_USD_CAP", "5.00")
    with pytest.raises(HTTPException) as exc:
        limits.check_daily_cap(FakeMetrics(spent=5.00))

    assert exc.value.status_code == 429
    assert "daily budget" in exc.value.detail
    assert "Retry-After" in exc.value.headers


def test_the_cap_asks_about_a_rolling_24h_window(monkeypatch):
    """Calendar days would reset the budget at midnight in whichever timezone
    the server happens to think it is in."""
    monkeypatch.setenv("DEMO_DAILY_USD_CAP", "5.00")
    metrics = FakeMetrics()
    limits.check_daily_cap(metrics)

    asked_about = metrics.queries[0]
    day_ago = time.time() - limits.DAY_SECONDS
    assert day_ago - 5 < asked_about <= day_ago + 5


def test_a_cap_of_zero_disables_it_and_costs_no_query(monkeypatch):
    monkeypatch.setenv("DEMO_DAILY_USD_CAP", "0")
    metrics = FakeMetrics(spent=1000.0)
    limits.check_daily_cap(metrics)
    assert metrics.queries == []


# --------------------------------------------------------------------------
# Order of enforcement
# --------------------------------------------------------------------------


def test_an_unauthorised_caller_cannot_consume_the_rate_limit(monkeypatch):
    """Token first: otherwise anyone can exhaust a legitimate visitor's quota
    without ever being allowed to run anything."""
    monkeypatch.setenv("DEMO_TOKEN", "s3cret")
    monkeypatch.setenv("DEMO_RATE_LIMIT_PER_HOUR", "1")

    for _ in range(5):
        with pytest.raises(HTTPException) as exc:
            limits.enforce(FakeRequest(), FakeMetrics())
        assert exc.value.status_code == 401

    # The quota was never touched, so a valid caller still gets their turn.
    limits.enforce(FakeRequest({"x-demo-token": "s3cret"}), FakeMetrics())


def test_a_rate_limited_caller_costs_no_database_query(monkeypatch):
    """A flood should not turn into a flood of spend queries."""
    monkeypatch.setenv("DEMO_RATE_LIMIT_PER_HOUR", "1")
    monkeypatch.setenv("DEMO_DAILY_USD_CAP", "5.00")
    metrics = FakeMetrics()

    limits.enforce(FakeRequest(), metrics)
    assert len(metrics.queries) == 1

    for _ in range(10):
        with pytest.raises(HTTPException):
            limits.enforce(FakeRequest(), metrics)
    assert len(metrics.queries) == 1  # unchanged


# --------------------------------------------------------------------------
# Reported status
# --------------------------------------------------------------------------


def test_status_reports_the_live_configuration(monkeypatch):
    monkeypatch.setenv("DEMO_RATE_LIMIT_PER_HOUR", "7")
    monkeypatch.setenv("DEMO_DAILY_USD_CAP", "5.00")

    status = limits.status(FakeMetrics(spent=1.2345))

    assert status["rate_limit_per_hour"] == 7
    assert status["daily_cap_usd"] == 5.00
    assert status["spent_24h_usd"] == 1.2345
    assert status["budget_exhausted"] is False
    assert status["token_required"] is False


def test_status_flags_an_exhausted_budget(monkeypatch):
    monkeypatch.setenv("DEMO_DAILY_USD_CAP", "5.00")
    assert limits.status(FakeMetrics(spent=5.01))["budget_exhausted"] is True


def test_status_never_reveals_the_token(monkeypatch):
    """`/demo` is public -- it may say a token is needed, never what it is."""
    monkeypatch.setenv("DEMO_TOKEN", "s3cret")
    assert "s3cret" not in str(limits.status(FakeMetrics()))
    assert limits.status(FakeMetrics())["token_required"] is True
