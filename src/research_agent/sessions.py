"""
Durable conversation sessions.

The REPL could keep the last run in a local variable. A service can't: the
follow-up arrives as a separate HTTP request, probably on a different worker,
possibly after a redeploy. So the final AgentState of every run is written to
SQLite, keyed by session id, and `/sessions/{id}/ask` loads it back.

This stores *completed* runs, not mid-run checkpoints. A crash halfway through
a run loses that run -- the caller retries. Resuming a half-finished graph is
what LangGraph's checkpointer is for, and it is a different feature with a
different failure model; conflating the two would buy resumability nobody
asked for at the cost of a schema tied to LangGraph internals.

Two backends behind one interface:

    SESSION_BACKEND=sqlite    one file, no server, survives a restart. Right
                              for a single container; point SESSION_DB_PATH at
                              a mounted volume so it outlives it.
    SESSION_BACKEND=postgres  shared state, so any machine can serve any
                              follow-up. This is what makes running more than
                              one machine possible at all -- with SQLite on a
                              per-machine volume, a follow-up routed to the
                              wrong host 404s on a session that exists.

Defaults to postgres when DATABASE_URL is set, sqlite otherwise.

Since Phase 12 a session also carries the identity that created it and expires
seven days after its last *write*. Both are store-level facts rather than
service-level ones so that neither can be forgotten by a new caller: a listing
cannot accidentally be unscoped, and an expired session cannot accidentally
still resolve.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass

from research_agent import db

_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
SESSION_DB_PATH = os.environ.get("SESSION_DB_PATH", os.path.join(_MODULE_DIR, "sessions.db"))

SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT PRIMARY KEY,
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL,
    task        TEXT NOT NULL,
    turns       INTEGER NOT NULL DEFAULT 1,
    state       TEXT NOT NULL,
    owner       TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS sessions_updated_at ON sessions (updated_at DESC);
"""

# Created after the owner migration below, never in the block above: a database
# written before Phase 12 already has the table, so `CREATE TABLE IF NOT EXISTS`
# is a no-op there and an index over `owner` would run against a column that
# does not exist yet.
SQLITE_OWNER_INDEX = (
    "CREATE INDEX IF NOT EXISTS sessions_owner ON sessions (owner, updated_at DESC)"
)

# JSONB, not TEXT: the state blob is genuinely a document, and JSONB lets a
# future query reach into it (e.g. every session whose run was unapproved)
# without a migration.
#
# The two trailing statements are the Phase 12 ownership migration. They are
# idempotent and they run inside the same advisory-locked lazy DDL block as the
# CREATE, so the live table migrates on the first post-deploy request with both
# machines serialised -- no migration script, no downtime. Rows written before
# Phase 12 land on owner='', which matches no caller (identities are 32-hex
# uuids), so they resolve for nobody and age out on the TTL below.
POSTGRES_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT PRIMARY KEY,
    created_at  DOUBLE PRECISION NOT NULL,
    updated_at  DOUBLE PRECISION NOT NULL,
    task        TEXT NOT NULL,
    turns       INTEGER NOT NULL DEFAULT 1,
    state       JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS sessions_updated_at ON sessions (updated_at DESC);
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS owner TEXT NOT NULL DEFAULT '';
CREATE INDEX IF NOT EXISTS sessions_owner ON sessions (owner, updated_at DESC);
"""

SESSION_TTL_DAYS_DEFAULT = 7.0


def session_ttl_seconds() -> float:
    """How long a session survives its last *write*, in seconds.

    Seven days by default: this is a public demo, not a product, so the store
    stays small and self-cleaning and a returning visitor loses week-old history.

    Read per call rather than cached in a module constant, the same convention
    the rest of the codebase uses for env-driven knobs -- tests flip it with
    monkeypatch.setenv between cases.
    """
    raw = os.environ.get("SESSION_TTL_DAYS", "").strip()
    try:
        days = float(raw) if raw else SESSION_TTL_DAYS_DEFAULT
    except ValueError:
        days = SESSION_TTL_DAYS_DEFAULT
    return max(days, 0.0) * 86400.0


@dataclass(frozen=True)
class Session:
    id: str
    created_at: float
    updated_at: float
    task: str
    turns: int
    state: dict
    owner: str = ""

    def summary(self) -> dict:
        """What a listing shows -- deliberately without the state blob, which
        contains the full report and every research note."""
        return {
            "session_id": self.id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "task": self.task,
            "turns": self.turns,
            "owner": self.owner,
            "topic_type": self.state.get("topic_type", ""),
            "approved": bool(self.state.get("approved")),
        }


class SessionStore(ABC):
    """The contract every backend implements, and the whole of what the
    service depends on. `tests/test_store_contract.py` runs the same suite
    against each implementation, so "swappable" is a tested claim rather
    than an aspiration.

    Two properties every backend owes since Phase 12:

    **Ownership.** A session records the identity that minted it. `list(owner=)`
    scopes to one owner; `owner=None` is the unscoped operator view. The store
    does not decide *who may see what* -- that is the service's `_require` --
    it only makes the question answerable.

    **Derived expiry.** A session is live iff `updated_at > now - SESSION_TTL_DAYS`.
    There is deliberately no expiry column: a second timestamp is a second
    thing to keep in sync, and `append_turn` already renews `updated_at` for free.
    ACTIVITY MEANS WRITES. `get()` and `list()` must never touch `updated_at` --
    if a read renewed it, listing your own sessions would keep them alive forever
    and "7 days after last activity" would quietly become "7 days after last
    glance", which is a store that never shrinks.
    """

    #: Human-readable location, shown by /health. Never a credential --
    #: a DSN carries a password, so Postgres reports host and database only.
    path: str

    @abstractmethod
    def create(self, task: str, state: dict, session_id: str | None = None, owner: str = "") -> str:
        """Record a completed research run as a new session. Returns its id.

        Also sweeps expired sessions: a create is rare (one per completed run)
        and already expensive, the DELETE is idempotent, and two machines
        sweeping concurrently is harmless -- which a background timer per
        machine is not."""

    @abstractmethod
    def append_turn(self, session_id: str, state: dict) -> None:
        """Record a follow-up as the session's new latest state.
        Raises KeyError if the session does not exist."""

    @abstractmethod
    def get(self, session_id: str) -> Session | None:
        """The session, or None if it is missing OR expired -- the caller must
        not be able to tell those apart."""

    @abstractmethod
    def list(self, limit: int = 50, owner: str | None = None) -> list[Session]:
        """Live sessions, newest write first. `owner=None` is unscoped."""

    @abstractmethod
    def delete(self, session_id: str) -> bool:
        """True if a session was removed, False if there was nothing to remove."""

    @abstractmethod
    def count(self) -> int: ...

    @abstractmethod
    def close(self) -> None: ...


class SQLiteSessionStore(SessionStore):
    """Thread-safe SQLite-backed session storage.

    One connection guarded by a lock rather than a pool: writes are tiny and
    infrequent (one per completed run, which takes tens of seconds), so the
    lock is never the bottleneck, and it sidesteps SQLite's writer contention
    entirely.
    """

    def __init__(self, path: str = SESSION_DB_PATH):
        self.path = path
        if path != ":memory:":
            parent = os.path.dirname(os.path.abspath(path))
            os.makedirs(parent, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(SQLITE_SCHEMA)
            self._add_owner_column()
            self._conn.execute(SQLITE_OWNER_INDEX)
            # WAL lets a reader (GET /sessions) proceed while a run is being
            # written. Not available for in-memory databases.
            if path != ":memory:":
                self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.commit()

    def _add_owner_column(self) -> None:
        """The SQLite half of the Phase 12 ownership migration.

        SQLite has no `ADD COLUMN IF NOT EXISTS`, so the column list is probed
        first. Idempotent, and cheap enough to run on every construction -- a
        local checkout's `sessions.db` predates the column, and failing to
        migrate it would 500 every read rather than merely losing history.

        Caller holds the lock.
        """
        columns = {row["name"] for row in self._conn.execute("PRAGMA table_info(sessions)")}
        if "owner" not in columns:
            self._conn.execute("ALTER TABLE sessions ADD COLUMN owner TEXT NOT NULL DEFAULT ''")

    # -- writes ------------------------------------------------------------

    def create(self, task: str, state: dict, session_id: str | None = None, owner: str = "") -> str:
        """Record a completed research run as a new session.

        Single-machine backend by construction, so `time.time()` is the one
        clock there is; the Postgres store compares against the database's own
        clock instead. The contract suite pins identical observable behaviour.
        """
        session_id = session_id or uuid.uuid4().hex
        now = time.time()
        with self._lock:
            self._conn.execute(
                "INSERT INTO sessions (id, created_at, updated_at, task, turns, state, owner) "
                "VALUES (?, ?, ?, ?, 1, ?, ?)",
                (session_id, now, now, task, json.dumps(state), owner),
            )
            # Opportunistic sweep, on the rare expensive event rather than on a
            # timer. Same statement on both backends.
            self._conn.execute(
                "DELETE FROM sessions WHERE updated_at <= ?", (now - session_ttl_seconds(),)
            )
            self._conn.commit()
        return session_id

    def append_turn(self, session_id: str, state: dict) -> None:
        """Record a follow-up answer as the session's new latest state.

        Only the latest state is kept: it already carries the whole thread in
        `conversation`, so keeping every turn as its own row would store the
        same history a second time in a shape nothing reads.
        """
        with self._lock:
            cursor = self._conn.execute(
                "UPDATE sessions SET state = ?, updated_at = ?, turns = turns + 1 "
                "WHERE id = ?",
                (json.dumps(state), time.time(), session_id),
            )
            self._conn.commit()
        if cursor.rowcount == 0:
            raise KeyError(session_id)

    def delete(self, session_id: str) -> bool:
        with self._lock:
            cursor = self._conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            self._conn.commit()
        return cursor.rowcount > 0

    # -- reads -------------------------------------------------------------

    def get(self, session_id: str) -> Session | None:
        """No UPDATE here, and there must never be one: see the ABC docstring."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM sessions WHERE id = ? AND updated_at > ?",
                (session_id, time.time() - session_ttl_seconds()),
            ).fetchone()
        return self._row_to_session(row) if row else None

    def list(self, limit: int = 50, owner: str | None = None) -> list[Session]:
        clause = "" if owner is None else " AND owner = ?"
        params: tuple = (time.time() - session_ttl_seconds(),)
        if owner is not None:
            params += (owner,)
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM sessions WHERE updated_at > ?" + clause
                + " ORDER BY updated_at DESC LIMIT ?",
                params + (limit,),
            ).fetchall()
        return [self._row_to_session(row) for row in rows]

    def count(self) -> int:
        with self._lock:
            return self._conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    @staticmethod
    def _row_to_session(row: sqlite3.Row) -> Session:
        return Session(
            id=row["id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            task=row["task"],
            turns=row["turns"],
            state=json.loads(row["state"]),
            owner=row["owner"],
        )


class PostgresSessionStore(SessionStore):
    """Shared session storage, so any machine can serve any follow-up.

    This is the piece that makes horizontal scaling possible. With SQLite on a
    per-machine volume, two machines hold two independent databases and a
    follow-up routed to the wrong one 404s on a session that demonstrably
    exists. Here the state lives in one place and the machines are stateless.
    """

    def __init__(self, dsn: str | None = None, database: db.Database | None = None):
        self.db = database or db.Database(dsn)
        self.path = _describe_dsn(self.db.dsn)
        self.db.ensure_schema(POSTGRES_SCHEMA)

    # -- writes ------------------------------------------------------------

    def create(self, task: str, state: dict, session_id: str | None = None, owner: str = "") -> str:
        session_id = session_id or uuid.uuid4().hex
        now = time.time()
        self.db.execute(
            "INSERT INTO sessions (id, created_at, updated_at, task, turns, state, owner) "
            "VALUES (%s, %s, %s, %s, 1, %s, %s)",
            (session_id, now, now, task, json.dumps(state), owner),
        )
        # Opportunistic sweep against the DATABASE's clock, so two machines
        # agree on the cutoff even if their own clocks do not. Idempotent:
        # concurrent sweeps just delete the same already-gone rows.
        self.db.execute(
            "DELETE FROM sessions WHERE updated_at <= EXTRACT(EPOCH FROM now()) - %s",
            (session_ttl_seconds(),),
        )
        return session_id

    def append_turn(self, session_id: str, state: dict) -> None:
        with self.db.cursor() as cur:
            cur.execute(
                "UPDATE sessions SET state = %s, updated_at = %s, turns = turns + 1 "
                "WHERE id = %s",
                (json.dumps(state), time.time(), session_id),
            )
            if cur.rowcount == 0:
                raise KeyError(session_id)

    def delete(self, session_id: str) -> bool:
        with self.db.cursor() as cur:
            cur.execute("DELETE FROM sessions WHERE id = %s", (session_id,))
            return cur.rowcount > 0

    # -- reads -------------------------------------------------------------

    def get(self, session_id: str) -> Session | None:
        """Expiry is evaluated against `now()` INSIDE the database.

        Both machines therefore read the same cutoff from the same clock. A
        `time.time()` cutoff computed in Python would make expiry mean something
        slightly different on each machine -- the class of bug this store exists
        to remove. And still no UPDATE: reads never renew.
        """
        row = self.db.fetchone(
            "SELECT * FROM sessions "
            "WHERE id = %s AND updated_at > EXTRACT(EPOCH FROM now()) - %s",
            (session_id, session_ttl_seconds()),
        )
        return self._row_to_session(row) if row else None

    def list(self, limit: int = 50, owner: str | None = None) -> list[Session]:
        clause = "" if owner is None else " AND owner = %s"
        params: tuple = (session_ttl_seconds(),)
        if owner is not None:
            params += (owner,)
        rows = self.db.fetchall(
            "SELECT * FROM sessions WHERE updated_at > EXTRACT(EPOCH FROM now()) - %s" + clause
            + " ORDER BY updated_at DESC LIMIT %s",
            params + (limit,),
        )
        return [self._row_to_session(row) for row in rows]

    def count(self) -> int:
        return self.db.fetchone("SELECT COUNT(*) AS n FROM sessions")["n"]

    def close(self) -> None:
        self.db.close()

    @staticmethod
    def _row_to_session(row: dict) -> Session:
        state = row["state"]
        return Session(
            id=row["id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            task=row["task"],
            turns=row["turns"],
            # JSONB comes back already decoded; a TEXT column would not. Accept
            # both so the same code survives a column-type change.
            state=state if isinstance(state, dict) else json.loads(state),
            owner=row["owner"],
        )


def _describe_dsn(dsn: str) -> str:
    """host/database, with any password stripped.

    This string is returned by /health, so it must never be able to leak a
    credential -- a DSN carries one in the netloc.
    """
    from urllib.parse import urlparse

    try:
        parsed = urlparse(dsn)
        host = parsed.hostname or "?"
        name = (parsed.path or "/").lstrip("/") or "?"
        return f"postgres://{host}/{name}"
    except ValueError:
        return "postgres://(unparseable dsn)"


BACKENDS = {"sqlite": SQLiteSessionStore, "postgres": PostgresSessionStore}


def default_backend() -> str:
    """Postgres when a DSN is configured, SQLite otherwise.

    Defaulting on DATABASE_URL rather than requiring SESSION_BACKEND means a
    deploy that provisions a database gets shared sessions without a second
    setting to forget -- and forgetting it is how you end up with two machines
    quietly serving from two different databases.
    """
    return os.environ.get("SESSION_BACKEND", "").strip().lower() or (
        "postgres" if db.postgres_configured() else "sqlite"
    )


def get_session_store(backend: str | None = None) -> SessionStore:
    name = (backend or default_backend()).strip().lower()
    try:
        cls = BACKENDS[name]
    except KeyError:
        raise ValueError(
            f"Unknown SESSION_BACKEND {name!r}. Choose one of: {', '.join(sorted(BACKENDS))}."
        ) from None
    return cls()
