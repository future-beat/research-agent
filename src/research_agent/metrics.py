"""
Run-level metrics.

One row per run attempt -- succeeded or failed -- so `/metrics` can answer the
questions you actually get asked in production: how often does the critic
approve, how often does a guardrail fire, what does a run cost, how long does
it take, and how much of that time was spent being retried.

Rows are written where sessions are, not where the report is: a run that
failed opens no session but still belongs in the denominator of every rate
here. Counting only successes would make an outage look like a quiet day.

Two backends, matching sessions. SQLite shares the sessions file by default
so a container mounts one volume; Postgres shares the database, which is what
lets /metrics aggregate across every machine instead of reporting whichever
one the request happened to land on.
"""

from __future__ import annotations

import math
import os
import sqlite3
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field

from research_agent import db
from research_agent.sessions import SESSION_DB_PATH, _describe_dsn

METRICS_DB_PATH = os.environ.get("METRICS_DB_PATH", SESSION_DB_PATH)

SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id                  TEXT    NOT NULL,
    session_id              TEXT,
    mode                    TEXT    NOT NULL,
    status                  TEXT    NOT NULL,
    topic_type              TEXT    NOT NULL DEFAULT '',
    approved                INTEGER NOT NULL DEFAULT 0,
    forced_stop_reason      TEXT    NOT NULL DEFAULT '',
    error_type              TEXT    NOT NULL DEFAULT '',
    revisions               INTEGER NOT NULL DEFAULT 0,
    iterations              INTEGER NOT NULL DEFAULT 0,
    retries                 INTEGER NOT NULL DEFAULT 0,
    calls                   INTEGER NOT NULL DEFAULT 0,
    input_tokens            INTEGER NOT NULL DEFAULT 0,
    output_tokens           INTEGER NOT NULL DEFAULT 0,
    cache_read_tokens       INTEGER NOT NULL DEFAULT 0,
    cache_creation_tokens   INTEGER NOT NULL DEFAULT 0,
    web_searches            INTEGER NOT NULL DEFAULT 0,
    cost_usd                REAL    NOT NULL DEFAULT 0.0,
    duration_ms             REAL    NOT NULL DEFAULT 0.0,
    created_at              REAL    NOT NULL
);
CREATE INDEX IF NOT EXISTS runs_created_at ON runs (created_at DESC);
CREATE INDEX IF NOT EXISTS runs_status ON runs (status);
"""

POSTGRES_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id                      BIGSERIAL PRIMARY KEY,
    run_id                  TEXT    NOT NULL,
    session_id              TEXT,
    mode                    TEXT    NOT NULL,
    status                  TEXT    NOT NULL,
    topic_type              TEXT    NOT NULL DEFAULT '',
    approved                BOOLEAN NOT NULL DEFAULT FALSE,
    forced_stop_reason      TEXT    NOT NULL DEFAULT '',
    error_type              TEXT    NOT NULL DEFAULT '',
    revisions               INTEGER NOT NULL DEFAULT 0,
    iterations              INTEGER NOT NULL DEFAULT 0,
    retries                 INTEGER NOT NULL DEFAULT 0,
    calls                   INTEGER NOT NULL DEFAULT 0,
    input_tokens            BIGINT  NOT NULL DEFAULT 0,
    output_tokens           BIGINT  NOT NULL DEFAULT 0,
    cache_read_tokens       BIGINT  NOT NULL DEFAULT 0,
    cache_creation_tokens   BIGINT  NOT NULL DEFAULT 0,
    web_searches            BIGINT  NOT NULL DEFAULT 0,
    cost_usd                DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    duration_ms             DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    created_at              DOUBLE PRECISION NOT NULL
);
CREATE INDEX IF NOT EXISTS runs_created_at ON runs (created_at DESC);
CREATE INDEX IF NOT EXISTS runs_status ON runs (status);
"""

COMPLETED = "completed"
FAILED = "failed"


@dataclass
class RunRecord:
    run_id: str
    mode: str
    status: str
    session_id: str = ""
    topic_type: str = ""
    approved: bool = False
    forced_stop_reason: str = ""
    error_type: str = ""
    revisions: int = 0
    iterations: int = 0
    retries: int = 0
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    web_searches: int = 0
    cost_usd: float = 0.0
    duration_ms: float = 0.0
    created_at: float = field(default_factory=time.time)

    @classmethod
    def from_state(
        cls, state: dict, *, session_id: str = "", duration_ms: float = 0.0
    ) -> RunRecord:
        usage = state.get("usage") or {}
        trace = state.get("trace") or []
        return cls(
            run_id=state.get("run_id", ""),
            mode=state.get("mode", ""),
            status=COMPLETED,
            session_id=session_id,
            topic_type=state.get("topic_type", ""),
            approved=bool(state.get("approved")),
            forced_stop_reason=state.get("forced_stop_reason", ""),
            revisions=state.get("revision_count", 0),
            iterations=state.get("iteration", 0),
            retries=sum(1 for entry in trace if entry.get("event") == "retry"),
            calls=usage.get("calls", 0),
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            cache_read_tokens=usage.get("cache_read_input_tokens", 0),
            cache_creation_tokens=usage.get("cache_creation_input_tokens", 0),
            web_searches=usage.get("web_search_requests", 0),
            cost_usd=usage.get("cost_usd", 0.0),
            duration_ms=duration_ms,
        )


def _percentile(sorted_values: list[float], fraction: float) -> float:
    """Nearest-rank percentile: the smallest value at or above `fraction` of
    the sample. Exact, and honest about small samples -- an interpolated p95
    over four runs invents precision that isn't there.

    `math.ceil`, not `round`: Python rounds halves to even, so a p50 over two
    runs would land on the second value instead of the first.
    """
    if not sorted_values:
        return 0.0
    rank = math.ceil(fraction * len(sorted_values))
    return sorted_values[min(max(rank, 1), len(sorted_values)) - 1]


def _summarise(totals: dict, stops: list, errors: list, durations: list) -> dict:
    """Turn raw aggregates into the /metrics payload.

    Shared by every backend on purpose: the SQL to compute the aggregates
    differs by engine (SQLite sums booleans, Postgres uses COUNT FILTER), but
    the shape and the rounding must not. The contract tests assert both
    backends produce identical output for identical input.
    """
    total = totals["total"] or 0
    completed = totals["completed"] or 0

    def rate(numerator: int, denominator: int) -> float | None:
        # None, not 0.0 -- "no runs yet" and "nothing was approved" are
        # different facts, and a dashboard should not conflate them.
        return round(numerator / denominator, 4) if denominator else None

    return {
        "runs": {
            "total": total,
            "completed": completed,
            "failed": totals["failed"] or 0,
            "research": totals["research"] or 0,
            "followup": totals["followup"] or 0,
            "failure_rate": rate(totals["failed"] or 0, total),
        },
        "quality": {
            "approved": totals["approved"] or 0,
            "approval_rate": rate(totals["approved"] or 0, completed),
            "forced_stops": totals["forced_stops"] or 0,
            "forced_stop_reasons": {row["reason"]: row["n"] for row in stops},
            "avg_revisions": round((totals["revisions"] or 0) / completed, 3)
            if completed
            else None,
        },
        "cost": {
            "total_usd": round(totals["cost_usd"] or 0.0, 6),
            "avg_usd_per_run": round((totals["cost_usd"] or 0.0) / total, 6)
            if total
            else None,
            "model_calls": totals["calls"] or 0,
            "input_tokens": totals["input_tokens"] or 0,
            "output_tokens": totals["output_tokens"] or 0,
            "cache_read_tokens": totals["cache_read_tokens"] or 0,
            "cache_creation_tokens": totals["cache_creation_tokens"] or 0,
            "web_searches": totals["web_searches"] or 0,
        },
        "latency_ms": {
            "p50": round(_percentile(durations, 0.50), 1),
            "p95": round(_percentile(durations, 0.95), 1),
            "max": round(durations[-1], 1) if durations else 0.0,
        },
        "reliability": {
            "retries": totals["retries"] or 0,
            "errors": {row["type"]: row["n"] for row in errors},
        },
    }


# The aggregate columns, minus the engine-specific conditional counting.
_SUM_COLUMNS = """
    COALESCE(SUM(revisions), 0)             AS revisions,
    COALESCE(SUM(retries), 0)               AS retries,
    COALESCE(SUM(calls), 0)                 AS calls,
    COALESCE(SUM(input_tokens), 0)          AS input_tokens,
    COALESCE(SUM(output_tokens), 0)         AS output_tokens,
    COALESCE(SUM(cache_read_tokens), 0)     AS cache_read_tokens,
    COALESCE(SUM(cache_creation_tokens), 0) AS cache_creation_tokens,
    COALESCE(SUM(web_searches), 0)          AS web_searches,
    COALESCE(SUM(cost_usd), 0.0)            AS cost_usd
"""

_STOPS_SQL = (
    "SELECT forced_stop_reason AS reason, COUNT(*) AS n FROM runs "
    "WHERE forced_stop_reason != '' GROUP BY forced_stop_reason ORDER BY n DESC"
)
_ERRORS_SQL = (
    "SELECT error_type AS type, COUNT(*) AS n FROM runs "
    "WHERE error_type != '' GROUP BY error_type ORDER BY n DESC"
)
_DURATIONS_SQL = "SELECT duration_ms FROM runs WHERE status = 'completed' ORDER BY duration_ms"


class MetricsStore(ABC):
    """What /metrics depends on. Two backends implement it."""

    path: str

    @abstractmethod
    def record(self, run: RunRecord) -> None: ...

    @abstractmethod
    def summary(self) -> dict: ...

    @abstractmethod
    def count(self) -> int: ...

    @abstractmethod
    def spend_since(self, since: float) -> float:
        """Total cost_usd of runs recorded at or after `since` (unix time).

        Read from the runs table rather than kept as a separate counter: a
        counter drifts the moment a process restarts or a second machine
        starts serving, and a spend cap that silently forgets what was spent
        is worse than no cap at all.
        """

    @abstractmethod
    def close(self) -> None: ...


class SQLiteMetricsStore(MetricsStore):
    """Thread-safe SQLite-backed run metrics."""

    def __init__(self, path: str = METRICS_DB_PATH):
        self.path = path
        if path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(SQLITE_SCHEMA)
            if path != ":memory:":
                self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.commit()

    def record(self, run: RunRecord) -> None:
        data = asdict(run)
        data["approved"] = int(data["approved"])
        columns = ", ".join(data)
        placeholders = ", ".join(f":{name}" for name in data)
        with self._lock:
            self._conn.execute(f"INSERT INTO runs ({columns}) VALUES ({placeholders})", data)
            self._conn.commit()

    def summary(self) -> dict:
        # SQLite has no COUNT(*) FILTER, but a boolean expression is 1 or 0,
        # so SUM over it counts matching rows.
        totals_sql = f"""
            SELECT
                COUNT(*)                     AS total,
                SUM(status = 'completed')    AS completed,
                SUM(status = 'failed')       AS failed,
                SUM(mode = 'research')       AS research,
                SUM(mode = 'followup')       AS followup,
                SUM(approved)                AS approved,
                SUM(forced_stop_reason != '') AS forced_stops,
                {_SUM_COLUMNS}
            FROM runs
        """
        with self._lock:
            totals = dict(self._conn.execute(totals_sql).fetchone())
            stops = [dict(r) for r in self._conn.execute(_STOPS_SQL)]
            errors = [dict(r) for r in self._conn.execute(_ERRORS_SQL)]
            durations = [r[0] for r in self._conn.execute(_DURATIONS_SQL)]
        return _summarise(totals, stops, errors, durations)

    def count(self) -> int:
        with self._lock:
            return self._conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]

    def spend_since(self, since: float) -> float:
        with self._lock:
            row = self._conn.execute(
                "SELECT COALESCE(SUM(cost_usd), 0.0) FROM runs WHERE created_at >= ?",
                (since,),
            ).fetchone()
        return float(row[0] or 0.0)

    def close(self) -> None:
        with self._lock:
            self._conn.close()


class PostgresMetricsStore(MetricsStore):
    """Shared run metrics, so /metrics reports the whole fleet.

    With per-machine SQLite, /metrics answers "what did the machine that
    served this request do", which looks like a dashboard and isn't one.
    """

    def __init__(self, dsn: str | None = None, database: db.Database | None = None):
        self.db = database or db.Database(dsn)
        self.path = _describe_dsn(self.db.dsn)
        self.db.ensure_schema(POSTGRES_SCHEMA)

    def record(self, run: RunRecord) -> None:
        data = asdict(run)
        columns = ", ".join(data)
        placeholders = ", ".join(f"%({name})s" for name in data)
        self.db.execute(f"INSERT INTO runs ({columns}) VALUES ({placeholders})", data)

    def summary(self) -> dict:
        totals_sql = f"""
            SELECT
                COUNT(*)                                              AS total,
                COUNT(*) FILTER (WHERE status = 'completed')          AS completed,
                COUNT(*) FILTER (WHERE status = 'failed')             AS failed,
                COUNT(*) FILTER (WHERE mode = 'research')             AS research,
                COUNT(*) FILTER (WHERE mode = 'followup')             AS followup,
                COUNT(*) FILTER (WHERE approved)                      AS approved,
                COUNT(*) FILTER (WHERE forced_stop_reason != '')      AS forced_stops,
                {_SUM_COLUMNS}
            FROM runs
        """
        totals = dict(self.db.fetchone(totals_sql))
        stops = self.db.fetchall(_STOPS_SQL)
        errors = self.db.fetchall(_ERRORS_SQL)
        durations = [r["duration_ms"] for r in self.db.fetchall(_DURATIONS_SQL)]
        # Postgres returns SUM(BIGINT) as Decimal; the JSON response and the
        # tests both expect plain numbers.
        for key in ("revisions", "retries", "calls", "input_tokens", "output_tokens",
                    "cache_read_tokens", "cache_creation_tokens", "web_searches"):
            totals[key] = int(totals[key] or 0)
        totals["cost_usd"] = float(totals["cost_usd"] or 0.0)
        return _summarise(totals, stops, errors, durations)

    def count(self) -> int:
        return self.db.fetchone("SELECT COUNT(*) AS n FROM runs")["n"]

    def spend_since(self, since: float) -> float:
        row = self.db.fetchone(
            "SELECT COALESCE(SUM(cost_usd), 0.0) AS spent FROM runs WHERE created_at >= %s",
            (since,),
        )
        return float(row["spent"] or 0.0)

    def close(self) -> None:
        self.db.close()


BACKENDS = {"sqlite": SQLiteMetricsStore, "postgres": PostgresMetricsStore}


def default_backend() -> str:
    """Follows the session backend by default. Sessions in Postgres and
    metrics in per-machine SQLite would be a confusing half-migration."""
    return os.environ.get("METRICS_BACKEND", "").strip().lower() or (
        "postgres" if db.postgres_configured() else "sqlite"
    )


def get_metrics_store(backend: str | None = None) -> MetricsStore:
    name = (backend or default_backend()).strip().lower()
    try:
        cls = BACKENDS[name]
    except KeyError:
        raise ValueError(
            f"Unknown METRICS_BACKEND {name!r}. Choose one of: {', '.join(sorted(BACKENDS))}."
        ) from None
    return cls()
