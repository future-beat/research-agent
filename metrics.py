"""
Run-level metrics.

One row per run attempt -- succeeded or failed -- so `/metrics` can answer the
questions you actually get asked in production: how often does the critic
approve, how often does a guardrail fire, what does a run cost, how long does
it take, and how much of that time was spent being retried.

Rows are written where sessions are, not where the report is: a run that
failed opens no session but still belongs in the denominator of every rate
here. Counting only successes would make an outage look like a quiet day.

Shares the SQLite file with sessions by default so a container mounts one
volume; point METRICS_DB_PATH elsewhere to split them.
"""

from __future__ import annotations

import math
import os
import sqlite3
import threading
import time
from dataclasses import asdict, dataclass, field

from sessions import SESSION_DB_PATH

METRICS_DB_PATH = os.environ.get("METRICS_DB_PATH", SESSION_DB_PATH)

SCHEMA = """
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
    ) -> "RunRecord":
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


class MetricsStore:
    """Thread-safe SQLite-backed run metrics."""

    def __init__(self, path: str = METRICS_DB_PATH):
        self.path = path
        if path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(SCHEMA)
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
        with self._lock:
            totals = self._conn.execute(
                """
                SELECT
                    COUNT(*)                                          AS total,
                    SUM(status = 'completed')                         AS completed,
                    SUM(status = 'failed')                            AS failed,
                    SUM(mode = 'research')                            AS research,
                    SUM(mode = 'followup')                            AS followup,
                    SUM(approved)                                     AS approved,
                    SUM(forced_stop_reason != '')                     AS forced_stops,
                    COALESCE(SUM(revisions), 0)                       AS revisions,
                    COALESCE(SUM(retries), 0)                         AS retries,
                    COALESCE(SUM(calls), 0)                           AS calls,
                    COALESCE(SUM(input_tokens), 0)                    AS input_tokens,
                    COALESCE(SUM(output_tokens), 0)                   AS output_tokens,
                    COALESCE(SUM(cache_read_tokens), 0)               AS cache_read_tokens,
                    COALESCE(SUM(cache_creation_tokens), 0)           AS cache_creation_tokens,
                    COALESCE(SUM(web_searches), 0)                    AS web_searches,
                    COALESCE(SUM(cost_usd), 0.0)                      AS cost_usd
                FROM runs
                """
            ).fetchone()
            stops = self._conn.execute(
                "SELECT forced_stop_reason AS reason, COUNT(*) AS n FROM runs "
                "WHERE forced_stop_reason != '' GROUP BY reason ORDER BY n DESC"
            ).fetchall()
            errors = self._conn.execute(
                "SELECT error_type AS type, COUNT(*) AS n FROM runs "
                "WHERE error_type != '' GROUP BY type ORDER BY n DESC"
            ).fetchall()
            durations = [
                row[0]
                for row in self._conn.execute(
                    "SELECT duration_ms FROM runs WHERE status = 'completed' "
                    "ORDER BY duration_ms"
                )
            ]

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

    def count(self) -> int:
        with self._lock:
            return self._conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]

    def close(self) -> None:
        with self._lock:
            self._conn.close()
