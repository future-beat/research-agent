"""
Shared Postgres connection handling.

All three stores -- sessions, metrics, notes -- need the same thing: a
connection that survives being idle. A long-lived Postgres connection through
a managed provider's proxy *will* be closed out from under you, usually
overnight, and the failure surfaces as the next request dying with
"server closed the connection unexpectedly". So every statement runs through
`cursor()`, which reconnects once and retries before giving up.

One connection guarded by a lock, rather than a pool. A research run occupies
a worker for tens of seconds while database calls take milliseconds, so
serialising them costs nothing measurable -- and it keeps the concurrency
story identical to the SQLite backends it sits alongside.

psycopg is imported lazily: a deployment on SQLite and a JSON store should not
need a Postgres driver installed to start up.

    DATABASE_URL=postgresql://user:pass@host:5432/dbname
    PG_CONNECT_TIMEOUT=3        seconds before a connection attempt gives up

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


class Database:
    """A reconnecting, lock-guarded Postgres connection."""

    def __init__(self, dsn: str | None = None):
        self.dsn = dsn or database_url()
        self._lock = threading.RLock()
        self._conn = None
        self._schema_sql: str | None = None
        self._schema_applied = False

    # -- connection ------------------------------------------------------

    def _connect(self):
        psycopg = _psycopg()
        # autocommit: every store here does single-statement writes, and an
        # implicit transaction left open by an idle connection holds locks
        # and pins vacuum for as long as the process lives.
        return psycopg.connect(self.dsn, autocommit=True, connect_timeout=connect_timeout())

    def _connection(self):
        if self._conn is None or self._conn.closed:
            self._conn = self._connect()
        return self._conn

    @contextmanager
    def cursor(self, row_factory=None):
        """A cursor, reconnecting once if the connection has gone stale.

        The retry is deliberately limited to one attempt and to connection
        errors: a genuine SQL error must surface immediately rather than be
        run twice.
        """
        psycopg = _psycopg()
        with self._lock:
            try:
                conn = self._connection()
                with conn.cursor(row_factory=row_factory) as cur:
                    yield cur
            except (psycopg.OperationalError, psycopg.InterfaceError):
                # Stale or dropped. Rebuild and try exactly once more.
                try:
                    if self._conn is not None:
                        self._conn.close()
                except Exception:  # noqa: BLE001 - already failing; closing is best effort
                    pass
                self._conn = None
                conn = self._connection()
                with conn.cursor(row_factory=row_factory) as cur:
                    yield cur

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
        if self._schema_applied or self._schema_sql is None:
            return
        # psycopg sends a multi-statement block as one command, which is what
        # we want: schema setup is all-or-nothing.
        with self.cursor() as cur:
            cur.execute(self._schema_sql)
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
        from psycopg.rows import dict_row

        self._apply_schema()
        with self.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, params)
            return cur.fetchone()

    def fetchall(self, sql: str, params=None) -> list:
        from psycopg.rows import dict_row

        self._apply_schema()
        with self.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, params)
            return cur.fetchall()

    def close(self) -> None:
        with self._lock:
            if self._conn is not None and not self._conn.closed:
                self._conn.close()
            self._conn = None


def postgres_configured() -> bool:
    """Whether a Postgres DSN is available. Used to pick a default backend
    and to skip the Postgres contract tests when there's no server."""
    return bool(os.environ.get("DATABASE_URL", "").strip())
