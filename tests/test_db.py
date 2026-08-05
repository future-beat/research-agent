"""
The pooled Postgres layer.

`db.py` is the phase's main risk surface and had no test module of its own --
it was covered only indirectly, through the store contract suite, and only when
a real server was configured. These tests need no server: they exercise the
configuration readers, the per-DSN pool registry, the disposal refcount and the
retry narrowing against fakes, plus one deliberately unreachable DSN for the
timing claim.

Following the repo convention: no conftest.py, fakes live here in the owning
module, `monkeypatch.setenv` for the env cases.
"""

import pytest

from research_agent import db

# --------------------------------------------------------------------------
# Config readers
# --------------------------------------------------------------------------

POOL_VARS = [
    "PG_POOL_MIN_SIZE",
    "PG_POOL_MAX_SIZE",
    "PG_POOL_TIMEOUT",
    "PG_STATEMENT_TIMEOUT",
    "PG_TCP_USER_TIMEOUT",
    "PG_CONNECT_TIMEOUT",
]


@pytest.fixture
def clean_env(monkeypatch):
    """A developer with PG_* exported must not change what the defaults are."""
    for name in POOL_VARS:
        monkeypatch.delenv(name, raising=False)


def test_pool_sizing_configurable_defaults(clean_env):
    assert db.pool_min_size() == 1
    assert db.pool_max_size() == 5
    assert db.pool_timeout() == 2.0


def test_pool_sizing_configurable_from_the_environment(clean_env, monkeypatch):
    monkeypatch.setenv("PG_POOL_MIN_SIZE", "2")
    monkeypatch.setenv("PG_POOL_MAX_SIZE", "12")
    monkeypatch.setenv("PG_POOL_TIMEOUT", "0.5")
    assert db.pool_min_size() == 2
    assert db.pool_max_size() == 12
    assert db.pool_timeout() == 0.5


def test_pool_sizing_configurable_survives_nonsense(clean_env, monkeypatch):
    """A typo in a Fly secret must not stop the process booting."""
    for name in POOL_VARS:
        monkeypatch.setenv(name, "banana")
    assert db.pool_min_size() == 1
    assert db.pool_max_size() == 5
    assert db.pool_timeout() == 2.0
    assert db.statement_timeout_ms() == 10000
    assert db.tcp_user_timeout_ms() == 2000


def test_pool_sizing_configurable_max_is_clamped_up_to_min(clean_env, monkeypatch):
    """psycopg raises when max_size < min_size, so the forgiving reading of a
    typo is to clamp rather than to refuse to start."""
    monkeypatch.setenv("PG_POOL_MIN_SIZE", "4")
    monkeypatch.setenv("PG_POOL_MAX_SIZE", "2")
    assert db.pool_max_size() == 4


def test_pool_sizing_configurable_has_floors(clean_env, monkeypatch):
    monkeypatch.setenv("PG_POOL_MIN_SIZE", "-3")
    monkeypatch.setenv("PG_POOL_TIMEOUT", "0")
    assert db.pool_min_size() == 0
    assert db.pool_timeout() == 0.1


def test_connection_bounds_defaults(clean_env):
    assert db.statement_timeout_ms() == 10000
    assert db.tcp_user_timeout_ms() == 2000


def test_connection_bounds_are_configurable(clean_env, monkeypatch):
    monkeypatch.setenv("PG_STATEMENT_TIMEOUT", "0")
    monkeypatch.setenv("PG_TCP_USER_TIMEOUT", "0")
    # 0 keeps libpq's own meaning -- "no bound" -- rather than an invented one.
    assert db.statement_timeout_ms() == 0
    assert db.tcp_user_timeout_ms() == 0


# --------------------------------------------------------------------------
# Connection-level bounds
#
# PG_POOL_TIMEOUT bounds a checkout. These bound what happens after one.
# --------------------------------------------------------------------------


def test_connection_bounds_reach_the_connection(clean_env):
    kwargs = db._connect_kwargs()
    assert kwargs["autocommit"] is True
    assert kwargs["connect_timeout"] == 3
    assert kwargs["options"] == "-c statement_timeout=10000"
    assert kwargs["tcp_user_timeout"] == 2000
    assert kwargs["keepalives"] == 1
    assert kwargs["keepalives_idle"] == 10
    assert kwargs["keepalives_interval"] == 3
    assert kwargs["keepalives_count"] == 2


def test_prepare_threshold_disabled(clean_env):
    """psycopg's default of 5 means server-side prepared statements start on
    the SIXTH execution -- so the breakage lands in production, not in a smoke
    test. It must be off unconditionally, whatever endpoint is configured."""
    assert db._connect_kwargs()["prepare_threshold"] is None


def test_connection_bounds_are_omitted_when_set_to_zero(clean_env, monkeypatch):
    """0 means "no bound" in libpq. Passing `-c statement_timeout=0` would also
    work, but omitting the flag keeps the server's own default authoritative."""
    monkeypatch.setenv("PG_STATEMENT_TIMEOUT", "0")
    monkeypatch.setenv("PG_TCP_USER_TIMEOUT", "0")
    kwargs = db._connect_kwargs()
    assert "options" not in kwargs
    assert "tcp_user_timeout" not in kwargs


def test_connection_bounds_do_not_include_a_checkout_liveness_check(cold_pool):
    """RESEARCH suggested check=ConnectionPool.check_connection; this module
    deliberately drops it. The check is itself a round trip performed *during*
    checkout, and the pool's `timeout` does not interrupt one in flight -- so
    against a partitioned database it adds an unbounded cost to every checkout,
    on the exact endpoint whose budget this phase is closing."""
    assert "check" not in db._connect_kwargs()
    dsn = _unique_dsn("nocheck")
    handle = db.Database(dsn)
    try:
        assert handle._pool._check is None
    finally:
        handle.close()


# --------------------------------------------------------------------------
# The shared per-DSN pool
# --------------------------------------------------------------------------

# 10.255.255.1 is a blackhole address: connections hang rather than being
# refused, which is the failure shape a paused managed instance produces.
UNREACHABLE_HOST = "10.255.255.1"


def _unique_dsn(name: str) -> str:
    """A DSN nothing else in the suite shares.

    The registry caches a pool per DSN with pool_timeout() read *at
    construction*, so a pool another test left registered at the 2.0 default
    would silently serve this test and make a PG_POOL_TIMEOUT=0.5 assertion
    take 2.0s -- failing for an unrelated reason.
    """
    return f"postgresql://agent:pw@{UNREACHABLE_HOST}:5432/{name}"


@pytest.fixture
def cold_pool(clean_env, monkeypatch):
    """min_size=0, so opening a pool starts no background connect attempts.

    These tests are about the registry, not about warm connections, and a
    warm-up against a blackhole address costs PG_CONNECT_TIMEOUT per pool at
    disposal time -- seconds of suite runtime for nothing.
    """
    monkeypatch.setenv("PG_POOL_MIN_SIZE", "0")


def test_single_shared_pool_per_dsn(cold_pool):
    """Each store builds its own Database. Three pools per machine would
    triple the warm-connection floor across the fleet for no benefit."""
    dsn = _unique_dsn("shared")
    first, second = db.Database(dsn), db.Database(dsn)
    try:
        assert first._pool is second._pool
    finally:
        first.close()
        second.close()


def test_single_shared_pool_is_not_shared_across_dsns(cold_pool):
    one, two = db.Database(_unique_dsn("one")), db.Database(_unique_dsn("two"))
    try:
        assert one._pool is not two._pool
    finally:
        one.close()
        two.close()


def test_no_ddl_at_construction_against_an_unreachable_database(cold_pool):
    """SC-4. Construction must perform no I/O that can raise: a database that
    is down must leave the service booting degraded, not refusing to boot."""
    handle = db.Database(_unique_dsn("noddl"))
    try:
        assert handle.schema_applied is False
    finally:
        handle.close()


def test_no_ddl_at_construction_when_a_schema_is_registered(cold_pool):
    """ensure_schema registers and tries; unreachable means deferred, not
    failed, and certainly not raised."""
    handle = db.Database(_unique_dsn("noddlschema"))
    try:
        handle.ensure_schema("CREATE TABLE IF NOT EXISTS nope (id int)")
        assert handle._schema_sql is not None
        assert handle.schema_applied is False
    finally:
        handle.close()


# --------------------------------------------------------------------------
# Disposal
# --------------------------------------------------------------------------


def test_pool_disposal_waits_for_the_last_holder(cold_pool):
    """service.lifespan closes sessions and metrics and never closes the
    memory store's Database. A close() that disposed the shared pool would
    break the holders that remain -- and a ConnectionPool cannot be reopened."""
    dsn = _unique_dsn("disposal")
    first, second = db.Database(dsn), db.Database(dsn)
    try:
        first.close()
        assert second._pool.closed is False
        assert dsn in db._pools
    finally:
        second.close()
    assert dsn not in db._pools
    assert second._pool.closed is True


def test_pool_disposal_is_idempotent(cold_pool):
    """The contract suite closes a store after every parametrised case, and
    some paths close twice. A double decrement would pull the pool out from
    under a holder that still has a claim."""
    dsn = _unique_dsn("doubleclose")
    first, second = db.Database(dsn), db.Database(dsn)
    try:
        first.close()
        first.close()
        assert second._pool.closed is False
    finally:
        second.close()


def test_pool_disposal_clears_the_registry(cold_pool):
    handle = db.Database(_unique_dsn("clearall"))
    db.close_all_pools()
    assert db._pools == {}
    assert db._pool_claims == {}
    assert handle._pool.closed is True
    handle.close()  # must not explode on an already-disposed pool
