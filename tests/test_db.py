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

import time
from contextlib import contextmanager

import psycopg
import psycopg_pool
import pytest

from research_agent import db


@pytest.fixture(autouse=True)
def dispose_pools():
    """Nothing may outlive its test.

    Refcounted close() self-cleans only if every test closes in a `finally`,
    which is convention rather than enforcement -- this is the enforcement.
    It matters because _pool_for caches per DSN with pool_timeout() read at
    *construction*: a pool left registered at the 2.0 default would be handed
    to a later test that set PG_POOL_TIMEOUT=0.5, making its assertion take
    2.0s and fail for an entirely unrelated reason. It also stops background
    reconnect workers accumulating across the session.
    """
    yield
    db.close_all_pools()


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


# --------------------------------------------------------------------------
# Retry narrowing
# --------------------------------------------------------------------------


def test_pool_timeout_not_retried_is_an_operational_error():
    """The reason the exclusion exists, written down as a test.

    PoolTimeout and PoolClosed subclass OperationalError, so the pre-existing
    `except OperationalError: retry once` arm would catch a checkout timeout
    and wait a second one. If psycopg ever changes this inheritance, this test
    fails and the exclusion can be revisited deliberately.
    """
    assert issubclass(psycopg_pool.PoolTimeout, psycopg.OperationalError)
    assert issubclass(psycopg_pool.PoolClosed, psycopg.OperationalError)


def test_pool_timeout_not_retried_costs_one_timeout_not_two(clean_env, monkeypatch):
    """The behavioural half: measure it.

    The bound is deliberately below 2x the configured checkout timeout, so a
    reintroduced retry FAILS this test rather than merely making it slower.
    """
    monkeypatch.setenv("PG_CONNECT_TIMEOUT", "1")
    monkeypatch.setenv("PG_POOL_TIMEOUT", "0.5")
    monkeypatch.setenv("PG_POOL_MIN_SIZE", "0")
    handle = db.Database(_unique_dsn("timing"))
    try:
        started = time.perf_counter()
        with pytest.raises(psycopg_pool.PoolTimeout), handle.cursor() as cur:
            cur.execute("SELECT 1")
        elapsed = time.perf_counter() - started
    finally:
        handle.close()
    assert elapsed < 1.0, f"a checkout timeout cost {elapsed:.2f}s; 0.5s was configured"


# --------------------------------------------------------------------------
# Fakes for the retry and advisory-lock paths
#
# A real server would prove more, but not this: the point is which connection
# each statement landed on, and a pool hands connections out invisibly.
# --------------------------------------------------------------------------


class FakeCursor:
    def __init__(self, conn, unlock_result=True):
        self.conn = conn
        self._unlock_result = unlock_result
        self._last = None

    def execute(self, sql, params=None):
        self.conn.statements.append(sql)
        self._last = sql

    def fetchone(self):
        if self._last and "pg_advisory_unlock" in self._last:
            return (self._unlock_result,)
        return None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeConnection:
    def __init__(self, unlock_result=True):
        self.statements = []
        self._unlock_result = unlock_result

    def cursor(self, row_factory=None):
        return FakeCursor(self, unlock_result=self._unlock_result)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakePool:
    """Hands out a fresh connection per checkout, recording every one.

    `raises` is a list of exceptions (or None) applied to successive
    checkouts, which is how the retry-once contract gets exercised without a
    server that can be knocked over.
    """

    def __init__(self, raises=(), unlock_result=True):
        self.raises = list(raises)
        self.handed_out = []
        self._unlock_result = unlock_result

    @contextmanager
    def connection(self):
        if self.raises:
            failure = self.raises.pop(0)
            if failure is not None:
                raise failure
        conn = FakeConnection(unlock_result=self._unlock_result)
        self.handed_out.append(conn)
        yield conn


@pytest.fixture
def faked(monkeypatch):
    """A Database whose pool is whatever the test hands it, with no registry
    entry and no real socket anywhere."""

    def build(pool):
        monkeypatch.setattr(db, "_pool_for", lambda dsn: pool)
        return db.Database("postgresql://fake/fake")

    return build


def test_reconnect_retries_a_dropped_connection_exactly_once(faked):
    """Managed Postgres closes idle connections. The first request after a
    quiet night must reconnect rather than fail -- a contract that has to
    survive the port to a pool."""
    pool = FakePool(raises=[psycopg.OperationalError("server closed the connection")])
    handle = faked(pool)
    with handle.cursor() as cur:
        cur.execute("SELECT 1")
    assert len(pool.handed_out) == 1  # the failed checkout handed out nothing
    assert pool.handed_out[0].statements == ["SELECT 1"]


def test_reconnect_gives_up_after_one_attempt(faked):
    pool = FakePool(raises=[
        psycopg.OperationalError("gone"),
        psycopg.OperationalError("still gone"),
    ])
    handle = faked(pool)
    with pytest.raises(psycopg.OperationalError), handle.cursor() as cur:
        cur.execute("SELECT 1")


def test_reconnect_does_not_retry_a_sql_error(faked):
    """A genuine SQL error must surface immediately rather than run twice --
    the write in it would land twice too."""
    pool = FakePool(raises=[psycopg.ProgrammingError("syntax error")])
    handle = faked(pool)
    with pytest.raises(psycopg.ProgrammingError), handle.cursor() as cur:
        cur.execute("SELECT nonsense")
    assert pool.handed_out == []  # not retried


def test_reconnect_does_not_swallow_a_caller_error(faked):
    """KeyError from sessions.append_turn is the live example: raised inside
    the caller's `with` body, it is not a connection error and must propagate
    untouched rather than being retried."""
    pool = FakePool()
    handle = faked(pool)
    with pytest.raises(KeyError), handle.cursor():
        raise KeyError("turn")
    assert len(pool.handed_out) == 1


# --------------------------------------------------------------------------
# A connection that dies mid-statement
#
# The pool changed *where* a dropped connection surfaces. The old single
# connection failed at entry, when `_conn.cursor()` touched a socket the
# provider had closed. A pool hands out a connection that still looks live and
# the failure lands one line later, on cur.execute -- inside the caller's
# `with` body, which is the one place a generator context manager cannot
# retry from. These are the local, serverless half of the CI-only
# pg_terminate_backend test in tests/test_store_contract.py.
# --------------------------------------------------------------------------


class DeadOnFirstExecuteCursor(FakeCursor):
    """Fails the first execute anywhere in the process, then behaves.

    Models a connection killed server-side while it sat idle in the pool:
    checkout succeeds, the statement is where it dies.
    """

    failures_left = 0

    def execute(self, sql, params=None):
        if type(self).failures_left > 0:
            type(self).failures_left -= 1
            raise psycopg.OperationalError("server closed the connection unexpectedly")
        return super().execute(sql, params)

    def fetchone(self):
        return {"n": 1}

    def fetchall(self):
        return [{"n": 1}]


class DeadOnFirstExecuteConnection(FakeConnection):
    def cursor(self, row_factory=None):
        return DeadOnFirstExecuteCursor(self)


class DeadOnFirstExecutePool(FakePool):
    @contextmanager
    def connection(self):
        conn = DeadOnFirstExecuteConnection()
        self.handed_out.append(conn)
        yield conn


@pytest.fixture
def dies_mid_statement():
    """One scripted mid-statement death, reset either way."""
    DeadOnFirstExecuteCursor.failures_left = 1
    yield
    DeadOnFirstExecuteCursor.failures_left = 0


def test_a_read_retries_a_connection_that_dies_mid_statement(faked, dies_mid_statement):
    """The behaviour test_the_connection_recovers_from_being_dropped asserts
    against a real server, provable here without one.

    Before the read-level retry this raised
    `RuntimeError: generator didn't stop after throw()` -- contextlib refusing
    a second yield -- which both failed the call AND destroyed the real error.
    """
    handle = faked(DeadOnFirstExecutePool())
    handle._schema_applied = True

    assert handle.fetchone("SELECT COUNT(*) AS n FROM sessions") == {"n": 1}


def test_a_read_retry_gives_up_after_one_attempt(faked):
    """Retrying forever against a database that is genuinely gone would turn
    an outage into a hang, which is the opposite of this phase's point."""
    DeadOnFirstExecuteCursor.failures_left = 2
    try:
        handle = faked(DeadOnFirstExecutePool())
        handle._schema_applied = True
        with pytest.raises(psycopg.OperationalError):
            handle.fetchall("SELECT 1")
    finally:
        DeadOnFirstExecuteCursor.failures_left = 0


def test_a_write_is_not_retried_mid_statement(faked, dies_mid_statement):
    """Deliberate asymmetry, not an oversight.

    A write that failed with a connection error may already have committed --
    the client cannot distinguish "never arrived" from "committed, response
    lost" -- so retrying it is at-least-once. What the caller must get is the
    real OperationalError rather than a RuntimeError about generators.
    """
    handle = faked(DeadOnFirstExecutePool())
    handle._schema_applied = True

    with pytest.raises(psycopg.OperationalError):
        handle.execute("INSERT INTO runs (id) VALUES (1)")


# --------------------------------------------------------------------------
# The advisory lock lives on ONE connection
# --------------------------------------------------------------------------


def test_schema_lock_single_connection(faked):
    """pg_advisory_lock is SESSION-scoped, so under a pool it is scoped to the
    checked-out connection. Split the block across two cursor() calls and the
    unlock lands on a different connection: the lock serialises nothing and
    leaks on a connection already returned to the pool.

    This is the cheap unit-level half of the invariant; the real-server half
    is plan 11-02's two-connection exclusivity test.
    """
    pool = FakePool()
    handle = faked(pool)
    handle.ensure_schema("CREATE TABLE IF NOT EXISTS t (id int)")

    assert handle.schema_applied is True
    assert len(pool.handed_out) == 1, "the whole block must run on ONE checkout"
    statements = pool.handed_out[0].statements
    assert "SELECT pg_advisory_lock(%s)" in statements
    assert "CREATE TABLE IF NOT EXISTS t (id int)" in statements
    assert "SELECT pg_advisory_unlock(%s)" in statements
    assert statements.index("SELECT pg_advisory_lock(%s)") == 0
    assert statements.index("SELECT pg_advisory_unlock(%s)") == len(statements) - 1


def test_schema_lock_single_connection_raises_when_the_unlock_returns_false(faked):
    """False from pg_advisory_unlock means the lock was never held on this
    connection -- which is exactly the signature of the invariant breaking.
    Swallowing it would leave a leaked lock looking like success."""
    pool = FakePool(unlock_result=False)
    handle = faked(pool)
    handle._schema_sql = "CREATE TABLE IF NOT EXISTS t (id int)"
    with pytest.raises(RuntimeError, match="single-connection invariant"):
        handle._apply_schema()
    assert handle.schema_applied is False


def test_ensure_schema_still_suppresses_a_broken_invariant(faked):
    """ensure_schema's contract does not change: it registers, tries once, and
    suppresses. A broken invariant costs a deferred retry, not a crash -- but
    it is no longer silent, because _apply_schema raises."""
    pool = FakePool(unlock_result=False)
    handle = faked(pool)
    handle.ensure_schema("CREATE TABLE IF NOT EXISTS t (id int)")
    assert handle.schema_applied is False
