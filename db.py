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
"""

from __future__ import annotations

import os
import threading
from contextlib import contextmanager


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


class Database:
    """A reconnecting, lock-guarded Postgres connection."""

    def __init__(self, dsn: str | None = None):
        self.dsn = dsn or database_url()
        self._lock = threading.RLock()
        self._conn = None

    # -- connection ------------------------------------------------------

    def _connect(self):
        psycopg = _psycopg()
        # autocommit: every store here does single-statement writes, and an
        # implicit transaction left open by an idle connection holds locks
        # and pins vacuum for as long as the process lives.
        return psycopg.connect(self.dsn, autocommit=True)

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

    def execute(self, sql: str, params=None) -> None:
        with self.cursor() as cur:
            cur.execute(sql, params)

    def executescript(self, sql: str) -> None:
        """Run a multi-statement schema block. psycopg sends it as one
        command, which is what we want -- schema setup is all-or-nothing."""
        with self.cursor() as cur:
            cur.execute(sql)

    def fetchone(self, sql: str, params=None):
        from psycopg.rows import dict_row

        with self.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, params)
            return cur.fetchone()

    def fetchall(self, sql: str, params=None) -> list:
        from psycopg.rows import dict_row

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
