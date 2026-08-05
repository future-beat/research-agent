"""
Shared Postgres connection handling.

All three stores -- sessions, metrics, notes -- need the same thing: a
connection that survives being idle. A long-lived Postgres connection through
a managed provider's proxy *will* be closed out from under you, usually
overnight, and the failure surfaces as the next request dying with
"server closed the connection unexpectedly". So `cursor()` retries a failed
checkout once, and reads retry the whole statement once -- because under a
pool the dead connection is handed out looking healthy and only dies on the
statement, which is a place a context manager cannot retry from. Writes get
the checkout retry only: a retried write is at-least-once. See `cursor()` and
`_read()`.

**A pool, where this module used to hold one connection behind a lock.** That
earlier choice was defensible while one machine ran: a research run occupies a
worker for tens of seconds, database calls take milliseconds, so serialising
them cost nothing measurable. The machine count rising is what reverses it.
`fly.toml` sets `hard_limit = 16`, and two machines means up to **32 in-flight
requests against one database** -- where before this phase they would all have
queued behind a single serialised connection, and now across a ~5 ms network
hop to an external provider rather than a local socket. /health, /ready,
/metrics, /sessions and every run boundary contend on that one connection.
The pool is justified by the machine count, not by taste.

One pool per DSN, shared by every `Database` on it. Each store builds its own
`Database`, so a naive port would give three pools per machine and triple the
warm-connection floor across the fleet. `close()` releases this Database's
claim; the pool is disposed when the last claim goes.

psycopg and psycopg_pool are imported lazily: a deployment on SQLite and a JSON
store should not need a Postgres driver installed to start up.

    DATABASE_URL=postgresql://user:pass@host:5432/dbname?sslmode=require
    PG_CONNECT_TIMEOUT=3        seconds before one libpq connect attempt gives up
    PG_POOL_MIN_SIZE=1          warm connections held open
    PG_POOL_MAX_SIZE=5          ceiling; 2 machines x 5 = 10 of Nano's 60
    PG_POOL_TIMEOUT=2.0         seconds a caller waits for a checkout
    PG_STATEMENT_TIMEOUT=10000  ms a server-side statement may run (0 = no bound)
    PG_TCP_USER_TIMEOUT=2000    ms of unACKed data before the socket is dropped

The timeouts are three different things and confusing them is how a health
check ends up unbounded:

  * `PG_CONNECT_TIMEOUT` bounds **one libpq connect attempt**, now made by a
    pool background worker rather than by the request thread. It says nothing
    about how long a caller waits.
  * `PG_POOL_TIMEOUT` bounds **how long a caller waits for a checkout**. This
    is the number a /health probe actually feels.
  * `PG_STATEMENT_TIMEOUT` and `PG_TCP_USER_TIMEOUT` bound what happens
    **after a connection is in hand** -- a slow server and a peer that has
    stopped ACKing, respectively. Neither of the first two applies there.

The residual, named rather than hidden: a peer that keeps the socket alive and
simply never answers is bounded by none of them. That is why /health carries
its own wall-clock deadline per probe (plan 11-02) instead of trusting libpq.

The connect timeout matters more than it looks. /health probes the database,
and a provider that has paused an idle instance will accept the TCP connection
and then say nothing -- without a bound, the health check hangs until Fly's own
timeout fires and the machine gets restarted for a fault a restart cannot fix.
"""

from __future__ import annotations

import contextlib
import os
import threading
from contextlib import contextmanager

# zlib.crc32(b"research_agent.schema"). ONE key for all three schema blocks,
# not one per store, so sessions, metrics and notes serialise against each
# other too. The SESSION-level lock/unlock pair, deliberately not the
# transaction-scoped variant: under autocommit=True there is no transaction for
# a transaction-scoped lock to hang on.
SCHEMA_LOCK_KEY = 3895545195


def connect_timeout() -> int:
    try:
        return max(1, int(os.environ.get("PG_CONNECT_TIMEOUT", "3")))
    except ValueError:
        return 3


# -- pool sizing -----------------------------------------------------------
#
# The numbers, and why they are these numbers:
#   max_size=5   fleet worst case is 2 machines x 5 = 10 of Supabase Nano's 60
#                connections (~17%), leaving room to raise it later without
#                changing tier. fly.toml's hard_limit = 16 means up to 32
#                in-flight requests fleet-wide; each store call is a few ms, so
#                a queue of 16 drains well inside the checkout timeout.
#   min_size=1   one warm, TLS-established connection so the first request
#                after a quiet spell does not pay a handshake.
#   timeout=2.0  what a *caller* waits for a checkout. Three sequential /health
#                store probes therefore cost ~6s in the ordinary unreachable
#                case -- with the hard ceiling coming from plan 11-02's
#                per-probe deadline, not from this number.


def pool_min_size() -> int:
    """PG_POOL_MIN_SIZE -- warm connections kept open. Default 1, floor 0."""
    try:
        return max(0, int(os.environ.get("PG_POOL_MIN_SIZE", "1")))
    except ValueError:
        return 1


def pool_max_size() -> int:
    """PG_POOL_MAX_SIZE -- ceiling on connections. Default 5, floor 1.

    Never below `pool_min_size()`: a pool asked for more warm connections than
    it is allowed to hold is a configuration error, and psycopg raises on it.
    Clamping up is the forgiving reading of a typo.
    """
    try:
        configured = max(1, int(os.environ.get("PG_POOL_MAX_SIZE", "5")))
    except ValueError:
        configured = 5
    return max(configured, pool_min_size())


def pool_timeout() -> float:
    """PG_POOL_TIMEOUT -- how long a caller waits for a checkout. Default 2.0s."""
    try:
        return max(0.1, float(os.environ.get("PG_POOL_TIMEOUT", "2.0")))
    except ValueError:
        return 2.0


# The next two exist because PG_POOL_TIMEOUT bounds a *checkout*, not a
# *statement*. Once a connection is in hand the pool timeout is spent and
# irrelevant, and PG_CONNECT_TIMEOUT never applied to an established connection
# at all -- so a query on a connection whose peer has gone away blocks on a
# socket with nothing bounding it.
#   statement_timeout   bounds the server-alive-but-slow case.
#   tcp_user_timeout    plus keepalives bound the peer-stopped-ACKing case.
# What they do NOT fix, stated rather than hidden: a peer that keeps the socket
# alive and simply never answers is bounded by none of them. That is why plan
# 11-02 puts a wall-clock deadline around each /health probe.


def statement_timeout_ms() -> int:
    """PG_STATEMENT_TIMEOUT -- server-side statement bound, ms. Default 10000.

    Floor 0, and 0 carries libpq's own meaning of "no bound" rather than an
    invented one.
    """
    try:
        return max(0, int(os.environ.get("PG_STATEMENT_TIMEOUT", "10000")))
    except ValueError:
        return 10000


def tcp_user_timeout_ms() -> int:
    """PG_TCP_USER_TIMEOUT -- unACKed-data bound, ms. Default 2000, floor 0
    (0 meaning "kernel default", again libpq's semantic)."""
    try:
        return max(0, int(os.environ.get("PG_TCP_USER_TIMEOUT", "2000")))
    except ValueError:
        return 2000


def database_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Postgres-backed stores need it, e.g. "
            "postgresql://user:pass@host:5432/dbname"
        )
    return url


def _psycopg():
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover - depends on env
        raise ImportError(
            "The Postgres backends need psycopg. Install it with "
            "`pip install 'psycopg[binary]'`, or use the SQLite/JSON backends."
        ) from exc
    return psycopg


def _psycopg_pool():
    try:
        import psycopg_pool
    except ImportError as exc:  # pragma: no cover - depends on env
        raise ImportError(
            "The Postgres backends need psycopg-pool. Install it with "
            "`pip install psycopg-pool`, or use the SQLite/JSON backends."
        ) from exc
    return psycopg_pool


# -- the pool registry -----------------------------------------------------
#
# One pool per DSN, shared. `_pool_claims` counts the Databases holding each
# pool so that `close()` can be a claim release rather than a disposal: the
# service lifespan closes the sessions and metrics stores but never the memory
# store, and the contract suite closes a store after every parametrised case.
# A close() that disposed a shared pool would break the holders that remain --
# and a ConnectionPool cannot be reopened once closed.

_pools: dict = {}
_pool_claims: dict = {}
_pools_lock = threading.Lock()


def _connect_kwargs() -> dict:
    """libpq settings applied to every connection the pool opens."""
    kwargs = {
        # autocommit: every store here does single-statement writes, and an
        # implicit transaction left open by an idle connection holds locks
        # and pins vacuum for as long as the process lives.
        "autocommit": True,
        "connect_timeout": connect_timeout(),
        # NOT optional. psycopg's default is 5, so server-side prepared
        # statements begin on the *sixth* execution of a query -- meaning the
        # breakage appears in production rather than in a smoke test, and only
        # once traffic warms a connection up. Behind a transaction-mode pooler
        # the prepared statement may not exist on whichever server session the
        # next execution lands on. Disabling it unconditionally makes the
        # choice of pooler endpoint stop being load-bearing.
        "prepare_threshold": None,
        # Keepalives plus tcp_user_timeout are the bound on a peer that has
        # stopped ACKing: without them a query on a connection whose peer went
        # away blocks on a socket with nothing to interrupt it.
        "keepalives": 1,
        "keepalives_idle": 10,
        "keepalives_interval": 3,
        "keepalives_count": 2,
    }
    statement_ms = statement_timeout_ms()
    if statement_ms:
        # Bounds the server-alive-but-slow case. It also bounds the advisory
        # lock wait in _apply_schema, because SELECT pg_advisory_lock(...) is
        # itself a statement -- that is desirable, not accidental: a loser that
        # waits out the timeout raises QueryCanceled, ensure_schema suppresses
        # it, and the schema block is retried on first use. Do not "fix" it.
        kwargs["options"] = f"-c statement_timeout={statement_ms}"
    tcp_ms = tcp_user_timeout_ms()
    if tcp_ms:
        kwargs["tcp_user_timeout"] = tcp_ms
    return kwargs


def _configure(conn) -> None:
    """Runs once per connection the pool opens.

    Supabase installs pgvector into the `extensions` schema, not `public`, so
    memory.py's unqualified `vector(N)` column types and `%s::vector` casts
    depend on `extensions` being on the search_path.

    This is insurance, not a fix for an observed break. Verified against the
    live Supabase project on 2026-08-05: its default search_path ALREADY
    contains `extensions`, and the casts resolve with this callback removed.
    The callback stays because depending on a provider's default is a silent
    dependency -- if Supabase changed it, or the project moved to a Postgres
    that puts the extension elsewhere, the failure would be an unqualified-type
    error at first use rather than anything obviously about search_path. Being
    explicit costs one statement per connection.

    Harmless on CI's stock pgvector/pgvector:pg16 image, where `extensions`
    does not exist -- Postgres tolerates missing schemas in search_path.
    """
    conn.execute("SET search_path TO public, extensions")


def _pool_for(dsn: str):
    """The shared pool for `dsn`, building it on first use. Claims a share."""
    psycopg_pool = _psycopg_pool()

    with _pools_lock:
        pool = _pools.get(dsn)
        if pool is None:
            pool = psycopg_pool.ConnectionPool(
                dsn,
                min_size=pool_min_size(),
                max_size=pool_max_size(),
                timeout=pool_timeout(),
                max_lifetime=1800,   # 30 min, comfortably under any proxy idle cull
                max_idle=300,
                kwargs=_connect_kwargs(),
                configure=_configure,
                # open=True does NOT connect synchronously and does NOT raise
                # when the database is down -- clients block and then fail with
                # PoolTimeout. That is what keeps Database.__init__ free of I/O
                # that can raise. Deliberately nothing here blocks until the
                # pool is warm: blocking is the boot-blocks-on-database
                # behaviour this codebase removed on purpose, and
                # test_store_contract.py exists to defend that.
                open=True,
                name="research-agent",
                # Deliberately NO `check=` liveness callback, which RESEARCH
                # suggested. Such a check is itself a server
                # round trip performed *during* checkout, and the pool's
                # `timeout` does not interrupt an in-flight check -- so against
                # a partitioned database it becomes an unbounded addition to
                # every caller's wait, on the exact endpoint (/health) whose
                # budget this phase is closing. Staleness is already covered by
                # the retry-once arm in cursor(), which is the pre-existing
                # contract. A silently dropped parameter reads as an oversight,
                # so the reason lives here.
            )
            _pools[dsn] = pool
            _pool_claims[dsn] = 0
        _pool_claims[dsn] += 1
        return pool


def _release_pool(dsn: str) -> None:
    """Drop one claim; dispose the pool when the last holder lets go."""
    with _pools_lock:
        if dsn not in _pools:
            return
        _pool_claims[dsn] -= 1
        if _pool_claims[dsn] > 0:
            return
        pool = _pools.pop(dsn)
        _pool_claims.pop(dsn, None)
    with contextlib.suppress(Exception):  # disposal is best effort
        pool.close()


# SQLSTATEs that mean "this connection is gone", as opposed to "the server
# answered and said no". Class 08 is connection_exception; 57P01/02/03 are the
# operator-intervention codes a managed provider sends when it terminates a
# backend, restarts, or is starting up.
#
# The distinction is the whole point and it is easy to get wrong in both
# directions. psycopg.OperationalError is far too broad: QueryCanceled (57014),
# which is how PG_STATEMENT_TIMEOUT surfaces, subclasses it -- and re-running a
# statement the server just killed for taking too long doubles the very bound
# that killed it. But "has a SQLSTATE at all" is too narrow the other way:
# pg_terminate_backend arrives as AdminShutdown (57P01), a server-reported
# error whose connection is nevertheless gone. Measured against a real server;
# an earlier sqlstate-is-None rule failed exactly there.
_CONNECTION_LOST_SQLSTATES = frozenset({"57P01", "57P02", "57P03"})


def _connection_was_lost(exc) -> bool:
    """Whether this error means the connection died, rather than the server
    having answered with a complaint about the statement."""
    sqlstate = getattr(exc, "sqlstate", None)
    if sqlstate is None:
        return True  # client-side: the socket failed before any reply
    return sqlstate.startswith("08") or sqlstate in _CONNECTION_LOST_SQLSTATES


def close_all_pools() -> None:
    """Dispose every registered pool. For the service lifespan's `finally`,
    and for tests, which must not leak background reconnect workers between
    cases."""
    with _pools_lock:
        pools = list(_pools.values())
        _pools.clear()
        _pool_claims.clear()
    for pool in pools:
        with contextlib.suppress(Exception):
            pool.close()


class Database:
    """A reconnecting Postgres handle over a shared per-DSN connection pool."""

    def __init__(self, dsn: str | None = None):
        self.dsn = dsn or database_url()
        self._pool = _pool_for(self.dsn)
        self._released = False
        self._schema_sql: str | None = None
        self._schema_applied = False

    # -- connection ------------------------------------------------------

    @contextmanager
    def cursor(self, row_factory=None):
        """A cursor, reconnecting once if the *checkout* fails.

        The retry is deliberately limited to one attempt and to connection
        errors: a genuine SQL error must surface immediately rather than be
        run twice, and a non-database exception raised inside the caller's
        `with` body -- KeyError from sessions.append_turn is the live example
        -- must propagate untouched.

        WHAT THIS CANNOT DO, and why the read helpers below exist. A generator
        context manager gets one yield. An exception raised inside the
        *caller's* body arrives here via `gen.throw`, and yielding a second
        time in response to it is not a retry -- contextlib rejects it with
        `RuntimeError: generator didn't stop after throw()`, destroying the
        real error on the way. That matters more under a pool than it did
        before: the old single connection failed at *entry*, when
        `self._conn.cursor()` touched a socket the provider had closed, so the
        rebuild landed in the right place. A pool hands out a connection that
        looks live and the failure surfaces one line later, inside the body,
        on `cur.execute`. So this only ever retries a checkout, and the retry
        that covers a connection dying mid-statement lives in `fetchone` /
        `fetchall`, which own the whole statement and can honestly re-run it.
        """
        psycopg = _psycopg()
        psycopg_pool = _psycopg_pool()
        with contextlib.ExitStack() as stack:
            try:
                conn = stack.enter_context(self._pool.connection())
            except (psycopg_pool.PoolTimeout, psycopg_pool.PoolClosed):
                # Both SUBCLASS psycopg.OperationalError, so this arm has to
                # come first: without it the arm below would retry a checkout
                # timeout and double the worst-case wait on an unreachable
                # database -- straight through the Fly health-check budget.
                # The wait has already happened; a second one buys nothing.
                raise
            except (psycopg.OperationalError, psycopg.InterfaceError):
                # Stale or dropped at checkout. One fresh connection, once.
                conn = stack.enter_context(self._pool.connection())
            yield stack.enter_context(conn.cursor(row_factory=row_factory))

    def _read(self, sql: str, params, many: bool):
        """Run a read, retrying the whole statement once on a dead connection.

        The case this covers is the one the pool created: a connection sitting
        in the pool when the server hung up on it -- `pg_terminate_backend`, a
        provider's overnight idle cull, a failover -- still looks live to
        libpq, so the checkout succeeds and `cur.execute` is where it dies.
        `cursor()` structurally cannot retry that (see its docstring). Here we
        can, because a read owns its whole statement: re-running it is free of
        side effects, and psycopg_pool discards a connection it finds broken
        on return, so the second attempt gets a fresh one.

        Only errors that mean the connection is *gone* are retried -- see
        `_connection_was_lost`. A server that answered with a complaint about
        the statement is alive, and re-running the statement would just wait
        out the same bound twice.

        WRITES ARE DELIBERATELY NOT GIVEN THIS. A statement that failed with a
        connection error may or may not have committed server-side -- the
        client cannot tell the difference between "never arrived" and
        "committed, response lost". Retrying a read costs nothing; retrying an
        INSERT is at-least-once, which for metrics.record means a duplicated
        run in the fleet's numbers and for sessions.create means a
        UniqueViolation dressed up as a write failure. So `execute` keeps only
        the checkout-level retry and surfaces the OperationalError itself,
        which is at least the true error rather than a RuntimeError about
        generators. A caller that wants at-least-once can ask for it.
        """
        from psycopg.rows import dict_row

        psycopg = _psycopg()
        psycopg_pool = _psycopg_pool()
        self._apply_schema()
        attempts = 2
        for attempt in range(1, attempts + 1):
            try:
                with self.cursor(row_factory=dict_row) as cur:
                    cur.execute(sql, params)
                    return cur.fetchall() if many else cur.fetchone()
            except (psycopg_pool.PoolTimeout, psycopg_pool.PoolClosed):
                raise  # the wait already happened; see cursor()
            except (psycopg.OperationalError, psycopg.InterfaceError) as exc:
                if not _connection_was_lost(exc):
                    raise
                if attempt == attempts:
                    raise
                # Whatever killed this connection almost certainly killed every
                # other idle connection in the pool -- a provider terminating
                # backends, a failover, a restart all take the lot. Without
                # this the retry just draws the next corpse: measured against a
                # real server, pg_terminate_backend left two dead connections
                # and a bare retry-once still failed. check() tests each idle
                # connection and replaces the broken ones, so one retry is
                # enough however many the pool was holding.
                #
                # This is NOT the `check=` checkout callback that _pool_for
                # deliberately omits. That one costs a server round trip on
                # every checkout, including /health's, which is the objection.
                # This runs only after a connection has already been found
                # dead, where the round trip is the cheapest thing available.
                with contextlib.suppress(Exception):
                    self._pool.check()
        return None  # pragma: no cover - the loop either returns or raises

    # -- schema ----------------------------------------------------------

    def ensure_schema(self, sql: str) -> None:
        """Register a schema block and try to apply it now.

        Deliberately does not raise if the database is unreachable. Running
        DDL from a store's constructor meant an unavailable Postgres stopped
        the *process from starting*, so a health endpoint that reports
        degraded dependencies never got the chance to report anything. Worse
        with a provider that pauses idle instances: the app could not boot, so
        it never connected, so nothing ever woke the database.

        The block is retried on first use instead, which lets the service come
        up degraded and heal itself the moment the database answers.
        """
        self._schema_sql = sql
        with contextlib.suppress(Exception):  # deferred to first use on purpose
            self._apply_schema()

    def _apply_schema(self) -> None:
        """Apply the registered schema block, serialised across processes.

        THE INVARIANT: the lock, the DDL and the unlock all run inside ONE
        `cursor()` block, because every `cursor()` call is a separate pool
        checkout and `pg_advisory_lock` is *session*-scoped -- which under a
        pool means per checked-out connection. Split across two checkouts this
        serialises nothing AND leaks: the unlock lands on a different
        connection, returns false, and the lock stays held on a connection
        already handed back to the pool. With max_size=5 that is the likely
        outcome, not the unlucky one -- from code that greps clean.

        Why now: CREATE TABLE / INDEX / EXTENSION IF NOT EXISTS is not atomic
        against a concurrent creator, and this is the first phase in which two
        processes ever run the lazy schema path simultaneously against an
        *empty* database -- which `fly deploy` across two machines and a
        start-clean database together guarantee.
        """
        if self._schema_applied or self._schema_sql is None:
            return
        psycopg = _psycopg()
        # Belt and braces behind the lock: a duplicate object means somebody
        # else already applied this block, which is success, not failure. Note
        # that this tolerance is exactly why a string-only gate on
        # pg_advisory_lock cannot prove the lock works -- the real gate is the
        # two-connection exclusivity test in plan 11-02.
        already_applied = (
            psycopg.errors.DuplicateTable,
            psycopg.errors.DuplicateObject,
            psycopg.errors.UniqueViolation,
        )
        # psycopg sends a multi-statement block as one command, which is what
        # we want: schema setup is all-or-nothing.
        with self.cursor() as cur:
            cur.execute("SELECT pg_advisory_lock(%s)", (SCHEMA_LOCK_KEY,))
            try:
                with contextlib.suppress(*already_applied):
                    cur.execute(self._schema_sql)
            finally:
                cur.execute("SELECT pg_advisory_unlock(%s)", (SCHEMA_LOCK_KEY,))
                row = cur.fetchone()
                released = bool(row and row[0])
                if not released:
                    raise RuntimeError(
                        "pg_advisory_unlock returned false: the schema lock was not held on "
                        "this connection, so the lock/DDL/unlock single-connection invariant "
                        "is broken and the DDL was not serialised"
                    )
        self._schema_applied = True

    @property
    def schema_applied(self) -> bool:
        return self._schema_applied

    # -- statements ------------------------------------------------------

    def execute(self, sql: str, params=None) -> None:
        self._apply_schema()
        with self.cursor() as cur:
            cur.execute(sql, params)

    def fetchone(self, sql: str, params=None):
        return self._read(sql, params, many=False)

    def fetchall(self, sql: str, params=None) -> list:
        return self._read(sql, params, many=True)

    def close(self) -> None:
        """Release this Database's claim on the shared pool.

        Idempotent on purpose: a second close() must not decrement twice and
        pull the pool out from under the holders that remain.
        """
        if self._released:
            return
        self._released = True
        _release_pool(self.dsn)


def postgres_configured() -> bool:
    """Whether a Postgres DSN is available. Used to pick a default backend
    and to skip the Postgres contract tests when there's no server."""
    return bool(os.environ.get("DATABASE_URL", "").strip())
