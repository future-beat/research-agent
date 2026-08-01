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

SQLite is the right size here: one file, no server to run, survives a restart,
and fine for the request rate a single agent container can serve. Point
SESSION_DB_PATH at a mounted volume so it outlives the container.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass

_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
SESSION_DB_PATH = os.environ.get("SESSION_DB_PATH", os.path.join(_MODULE_DIR, "sessions.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT PRIMARY KEY,
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL,
    task        TEXT NOT NULL,
    turns       INTEGER NOT NULL DEFAULT 1,
    state       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS sessions_updated_at ON sessions (updated_at DESC);
"""


@dataclass(frozen=True)
class Session:
    id: str
    created_at: float
    updated_at: float
    task: str
    turns: int
    state: dict

    def summary(self) -> dict:
        """What a listing shows -- deliberately without the state blob, which
        contains the full report and every research note."""
        return {
            "session_id": self.id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "task": self.task,
            "turns": self.turns,
            "topic_type": self.state.get("topic_type", ""),
            "approved": bool(self.state.get("approved")),
        }


class SessionStore:
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
            self._conn.executescript(SCHEMA)
            # WAL lets a reader (GET /sessions) proceed while a run is being
            # written. Not available for in-memory databases.
            if path != ":memory:":
                self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.commit()

    # -- writes ------------------------------------------------------------

    def create(self, task: str, state: dict, session_id: str | None = None) -> str:
        """Record a completed research run as a new session."""
        session_id = session_id or uuid.uuid4().hex
        now = time.time()
        with self._lock:
            self._conn.execute(
                "INSERT INTO sessions (id, created_at, updated_at, task, turns, state) "
                "VALUES (?, ?, ?, ?, 1, ?)",
                (session_id, now, now, task, json.dumps(state)),
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
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
        return self._row_to_session(row) if row else None

    def list(self, limit: int = 50) -> list[Session]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?", (limit,)
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
        )
