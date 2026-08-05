"""
Demo guardrails.

The service is publicly reachable with live API keys, so these are the tests
that stand between a shared URL and someone else's Anthropic bill.
"""

import time

import pytest
from fastapi import HTTPException

from research_agent import db, limits
from research_agent.limits import InMemoryLimits, PostgresLimits, RateLimiter

HAS_POSTGRES = db.postgres_configured()


class FakeRequest:
    """A Request stand-in carrying what the guards actually read.

    `state.identity` is set by IdentityMiddleware on every real request, so a
    fake without one would let an identity-keyed limiter be tested against
    something the production path never sees.
    """

    def __init__(self, headers=None, host="203.0.113.7", identity="identity-default"):
        self.headers = headers or {}
        self.client = type("C", (), {"host": host})()
        self.state = type("S", (), {"identity": identity})()


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
                "DEMO_DAILY_USD_CAP", "TRUST_FORWARDED_FOR", "DEMO_RESERVED_RUN_USD",
                "LIMITS_BACKEND"):
        monkeypatch.delenv(var, raising=False)
    yield


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


def test_the_memory_store_reconfigures_when_the_setting_changes():
    """Raising the limit must take effect without a restart -- and without
    carrying the old window's hits into the new one."""
    store = InMemoryLimits()
    assert store.check_rate("a", 1, 60)[0] is True
    assert store.check_rate("a", 1, 60)[0] is False
    assert store.check_rate("a", 5, 60)[0] is True


# --------------------------------------------------------------------------
# The limits store: identity-keyed rate window, reserve/settle
# --------------------------------------------------------------------------


def _dsn_tagged(application_name: str) -> str:
    """DATABASE_URL carrying an application_name, mirroring test_store_contract.

    Two jobs, both load-bearing here: it makes the DSN test-unique, and
    db._pool_for caches one pool per DSN -- so two handles on two tagged DSNs
    are guaranteed two pools and therefore two real connections, which is what
    the two-thread race below needs.
    """
    base = db.database_url()
    separator = "&" if "?" in base else "?"
    return f"{base}{separator}application_name={application_name}"


@pytest.fixture
def pg_limits():
    """A PostgresLimits on a private table state, truncated between cases."""
    store = PostgresLimits(dsn=_dsn_tagged("ra_limits"))
    store.db.execute("TRUNCATE rate_hits")
    store.db.execute("TRUNCATE run_reservations")
    yield store
    store.close()


def test_the_memory_store_rate_limits_per_identity():
    """The whole point of the identity rekey: the key is the identity, so one
    caller's exhaustion is not another's."""
    store = InMemoryLimits()
    assert store.check_rate("identity-a", 1, 60)[0] is True
    assert store.check_rate("identity-a", 1, 60)[0] is False
    assert store.check_rate("identity-b", 1, 60)[0] is True


def test_a_refused_rate_check_reports_a_retry_hint():
    store = InMemoryLimits()
    store.check_rate("a", 1, 60)
    allowed, retry_after = store.check_rate("a", 1, 60)
    assert allowed is False
    assert 0 < retry_after <= 61


def test_a_rate_limit_of_zero_disables_the_check():
    store = InMemoryLimits()
    assert all(store.check_rate("a", 0, 60)[0] for _ in range(50))


def test_a_reservation_within_budget_is_recorded():
    store = InMemoryLimits()
    assert store.reserve("run-1", "id-a", 0.20, cap=5.00, spent_24h=0.0) is True
    assert store.reservation_ids() == {"run-1"}


def test_settle_releases_the_reservation():
    store = InMemoryLimits()
    store.reserve("run-1", "id-a", 0.20, cap=5.00, spent_24h=0.0)
    store.settle("run-1")
    assert store.reservation_ids() == set()
    store.settle("run-1")  # idempotent: a second settle must not raise


def test_a_reservation_over_the_cap_is_refused():
    store = InMemoryLimits()
    assert store.reserve("run-1", "id-a", 0.20, cap=5.00, spent_24h=4.95) is False
    assert store.reservation_ids() == set()


def test_in_flight_reservations_count_against_the_cap():
    """The defect this closes: counting only completed runs let N concurrent
    runs each see the same pre-burst total and all pass."""
    store = InMemoryLimits()
    assert store.reserve("run-1", "id-a", 0.60, cap=1.00, spent_24h=0.0) is True
    assert store.reserve("run-2", "id-b", 0.60, cap=1.00, spent_24h=0.0) is False


def test_a_cap_of_zero_reserves_nothing():
    store = InMemoryLimits()
    assert store.reserve("run-1", "id-a", 0.20, cap=0.0, spent_24h=1000.0) is True
    assert store.reservation_ids() == set()


def test_a_stale_reservation_stops_counting(monkeypatch):
    """A run killed mid-flight must not pin the budget forever."""
    store = InMemoryLimits()
    assert store.reserve("crashed", "id-a", 0.60, cap=1.00, spent_24h=0.0) is True
    # Age it past the cutoff without waiting fifteen minutes.
    identity, est, _ = store._reservations["crashed"]
    long_ago = time.time() - limits.RESERVATION_STALE_SECONDS - 1
    store._reservations["crashed"] = (identity, est, long_ago)

    assert store.reserve("fresh", "id-b", 0.60, cap=1.00, spent_24h=0.0) is True
    assert "crashed" not in store.reservation_ids()  # purged on the way past


def test_the_backend_defaults_on_the_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert limits.default_backend() == "memory"
    monkeypatch.setenv("DATABASE_URL", "postgresql://user@host/db")
    assert limits.default_backend() == "postgres"


def test_an_unknown_backend_is_rejected():
    with pytest.raises(ValueError, match="Unknown LIMITS_BACKEND"):
        limits.get_limits_store("mysql")


@pytest.mark.skipif(not HAS_POSTGRES, reason="DATABASE_URL is not set")
def test_the_postgres_rate_window_persists_across_calls(pg_limits):
    """The state has to be in the database, not in this process: that is the
    entire reason for the backend."""
    assert pg_limits.check_rate("pg-a", 1, 60)[0] is True
    assert pg_limits.check_rate("pg-a", 1, 60)[0] is False
    assert pg_limits.check_rate("pg-b", 1, 60)[0] is True

    # A second store on the same database sees the first one's hits -- which is
    # what "two machines share one window" means.
    other = PostgresLimits(dsn=_dsn_tagged("ra_limits_other"))
    try:
        assert other.check_rate("pg-a", 1, 60)[0] is False
    finally:
        other.close()


@pytest.mark.skipif(not HAS_POSTGRES, reason="DATABASE_URL is not set")
def test_postgres_reservations_round_trip(pg_limits):
    assert pg_limits.reserve("pg-run-1", "id-a", 0.20, cap=5.00, spent_24h=0.0) is True
    assert pg_limits.reservation_ids() == {"pg-run-1"}
    assert pg_limits.reserve("pg-run-2", "id-b", 0.20, cap=5.00, spent_24h=4.95) is False
    pg_limits.settle("pg-run-1")
    assert pg_limits.reservation_ids() == set()


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
    store = InMemoryLimits()
    limits.reserve_or_429(store, "run-1", "id-a", FakeMetrics(spent=4.00))
    assert store.reservation_ids() == {"run-1"}


def test_reaching_the_cap_refuses_new_runs(monkeypatch):
    monkeypatch.setenv("DEMO_DAILY_USD_CAP", "5.00")
    with pytest.raises(HTTPException) as exc:
        limits.reserve_or_429(InMemoryLimits(), "run-1", "id-a", FakeMetrics(spent=5.00))

    assert exc.value.status_code == 429
    assert "daily budget" in exc.value.detail
    assert "Retry-After" in exc.value.headers


def test_reads_survive_the_cap(monkeypatch):
    """The refusal's exact promise. The message tells the caller that reads
    still work, so the sentence is part of the contract and not decoration --
    ADR-0006 keeps `guard` off the session reads to make it true."""
    monkeypatch.setenv("DEMO_DAILY_USD_CAP", "5.00")

    class AlwaysFull(InMemoryLimits):
        def reserve(self, *args, **kwargs):
            return False

    with pytest.raises(HTTPException) as exc:
        limits.reserve_or_429(AlwaysFull(), "run-1", "id-a", FakeMetrics(spent=9.99))

    assert exc.value.status_code == 429
    assert "Read-only endpoints still work." in exc.value.detail


def test_the_reservation_reflects_the_estimate(monkeypatch):
    monkeypatch.setenv("DEMO_DAILY_USD_CAP", "1.00")
    monkeypatch.setenv("DEMO_RESERVED_RUN_USD", "0.60")
    store = InMemoryLimits()

    limits.reserve_or_429(store, "run-1", "id-a", FakeMetrics(spent=0.0))
    with pytest.raises(HTTPException):  # 0.60 + 0.60 > 1.00
        limits.reserve_or_429(store, "run-2", "id-b", FakeMetrics(spent=0.0))


def test_the_cap_asks_about_a_rolling_24h_window(monkeypatch):
    """Calendar days would reset the budget at midnight in whichever timezone
    the server happens to think it is in."""
    monkeypatch.setenv("DEMO_DAILY_USD_CAP", "5.00")
    metrics = FakeMetrics()
    limits.reserve_or_429(InMemoryLimits(), "run-1", "id-a", metrics)

    asked_about = metrics.queries[0]
    day_ago = time.time() - limits.DAY_SECONDS
    assert day_ago - 5 < asked_about <= day_ago + 5


def test_a_cap_of_zero_disables_it_and_costs_no_query(monkeypatch):
    monkeypatch.setenv("DEMO_DAILY_USD_CAP", "0")
    metrics = FakeMetrics(spent=1000.0)
    limits.reserve_or_429(InMemoryLimits(), "run-1", "id-a", metrics)
    assert metrics.queries == []


def test_settle_never_raises():
    """A settle that failed must not turn a finished run into a 500, nor
    truncate a stream that has already delivered its result. The staleness
    cutoff is what makes swallowing it survivable."""

    class Broken(InMemoryLimits):
        def settle(self, run_id):
            raise RuntimeError("database went away")

    limits.settle(Broken(), "run-1")  # must not raise


# --------------------------------------------------------------------------
# Order of enforcement
# --------------------------------------------------------------------------


def test_an_unauthorised_caller_cannot_consume_the_rate_limit(monkeypatch):
    """Token first: otherwise anyone can exhaust a legitimate visitor's quota
    without ever being allowed to run anything."""
    monkeypatch.setenv("DEMO_TOKEN", "s3cret")
    monkeypatch.setenv("DEMO_RATE_LIMIT_PER_HOUR", "1")
    store = InMemoryLimits()

    for _ in range(5):
        with pytest.raises(HTTPException) as exc:
            limits.enforce(FakeRequest(), FakeMetrics(), store)
        assert exc.value.status_code == 401

    # The quota was never touched, so a valid caller still gets their turn.
    limits.enforce(FakeRequest({"x-demo-token": "s3cret"}), FakeMetrics(), store)


def test_the_rate_limit_keys_on_identity_not_the_address(monkeypatch):
    """Two callers behind one address -- a household, an office NAT, a mobile
    carrier -- get independent budgets. Both directions are asserted: A must
    actually be refused, and B must actually be let through, so neither a
    shared window nor a limiter that never fires can pass this."""
    monkeypatch.setenv("DEMO_RATE_LIMIT_PER_HOUR", "1")
    store = InMemoryLimits()
    shared_address = "198.51.100.9"
    a = FakeRequest(host=shared_address, identity="identity-a")
    b = FakeRequest(host=shared_address, identity="identity-b")

    limits.enforce(a, FakeMetrics(), store)
    with pytest.raises(HTTPException) as exc:
        limits.enforce(a, FakeMetrics(), store)
    assert exc.value.status_code == 429

    limits.enforce(b, FakeMetrics(), store)  # untouched by A's exhaustion


def test_enforce_no_longer_applies_the_daily_cap(monkeypatch):
    """The cap moved to the run-start choke point, where a run_id exists to
    reserve against. A guard that still capped would 429 here and cost a spend
    query doing it."""
    monkeypatch.setenv("DEMO_DAILY_USD_CAP", "1.00")
    metrics = FakeMetrics(spent=1000.0)  # far over the cap

    limits.enforce(FakeRequest(), metrics, InMemoryLimits())  # must not raise

    assert metrics.queries == []  # and must not have asked


def test_a_rate_limited_caller_costs_no_database_query(monkeypatch):
    """A flood should not turn into a flood of spend queries."""
    monkeypatch.setenv("DEMO_RATE_LIMIT_PER_HOUR", "1")
    monkeypatch.setenv("DEMO_DAILY_USD_CAP", "5.00")
    metrics = FakeMetrics()
    store = InMemoryLimits()

    limits.enforce(FakeRequest(), metrics, store)
    for _ in range(10):
        with pytest.raises(HTTPException):
            limits.enforce(FakeRequest(), metrics, store)

    assert metrics.queries == []


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


def test_status_keeps_every_key_it_has_ever_reported(monkeypatch):
    """Additive only. The deployed page is redeployed with the service; the
    browser tab already open on it is not, so a renamed key breaks a live
    client for as long as it stays open."""
    monkeypatch.setenv("DEMO_DAILY_USD_CAP", "5.00")
    original = {
        "token_required",
        "rate_limit_per_hour",
        "daily_cap_usd",
        "spent_24h_usd",
        "budget_exhausted",
    }
    assert original <= set(limits.status(FakeMetrics(spent=1.0)))


def test_status_reports_the_new_limit_shape(monkeypatch):
    monkeypatch.setenv("DEMO_DAILY_USD_CAP", "5.00")
    monkeypatch.setenv("DEMO_RESERVED_RUN_USD", "0.25")
    status = limits.status(FakeMetrics(spent=1.0))

    assert status["rate_limit_scope"] == "identity"
    assert status["reserved_run_usd"] == 0.25


def test_status_flags_an_exhausted_budget(monkeypatch):
    monkeypatch.setenv("DEMO_DAILY_USD_CAP", "5.00")
    assert limits.status(FakeMetrics(spent=5.01))["budget_exhausted"] is True


def test_status_never_reveals_the_token(monkeypatch):
    """`/demo` is public -- it may say a token is needed, never what it is."""
    monkeypatch.setenv("DEMO_TOKEN", "s3cret")
    assert "s3cret" not in str(limits.status(FakeMetrics()))
    assert limits.status(FakeMetrics())["token_required"] is True
