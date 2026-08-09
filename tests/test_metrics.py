"""Run metrics: recording, aggregation, and the rate/denominator edge cases
that make a dashboard lie."""

import sqlite3

import pytest

from research_agent import db
from research_agent.graph import initial_state
from research_agent.metrics import (
    COMPLETED,
    FAILED,
    PostgresMetricsStore,
    RunRecord,
    SQLiteMetricsStore,
    _percentile,
)

HAS_POSTGRES = db.postgres_configured()


@pytest.fixture
def store(tmp_path):
    s = SQLiteMetricsStore(str(tmp_path / "metrics.db"))
    yield s
    s.close()


def run(**overrides) -> RunRecord:
    base = {
        "run_id": "r1",
        "mode": "research",
        "status": COMPLETED,
        "approved": True,
        "cost_usd": 0.10,
        "duration_ms": 1000.0,
    }
    base.update(overrides)
    return RunRecord(**base)


# --------------------------------------------------------------------------
# Building a record from a finished run
# --------------------------------------------------------------------------


def test_from_state_pulls_the_run_apart():
    state = initial_state("why?")
    state.update(
        {
            "mode": "research",
            "topic_type": "technical",
            "approved": True,
            "revision_count": 1,
            "iteration": 7,
            "usage": {
                "calls": 4,
                "input_tokens": 100,
                "output_tokens": 50,
                "cache_read_input_tokens": 25,
                "cache_creation_input_tokens": 10,
                "web_search_requests": 3,
                "cost_usd": 0.42,
            },
            "trace": [
                {"node": "critic", "event": "retry", "attempt": 1},
                {"node": "critic", "approved": True},
            ],
        }
    )

    record = RunRecord.from_state(state, session_id="s1", duration_ms=1234.5)

    assert record.run_id == state["run_id"]
    assert record.session_id == "s1"
    assert record.status == COMPLETED
    assert record.topic_type == "technical"
    assert record.approved is True
    assert (record.revisions, record.iterations) == (1, 7)
    assert record.retries == 1  # only the retry entry, not the verdict entry
    assert record.calls == 4
    assert record.web_searches == 3
    assert record.cost_usd == 0.42
    assert record.duration_ms == 1234.5


def test_from_state_survives_a_run_that_never_started():
    """A run that failed in its first node has empty usage and an empty
    trace; it still has to produce a valid row."""
    record = RunRecord.from_state(initial_state("why?"))
    assert record.calls == 0
    assert record.cost_usd == 0.0
    assert record.retries == 0


def test_from_state_reads_embedding_usage():
    """Embedding spend reaches the row, and its absence reads as zero.

    The second half is the one that matters in production: a follow-up turn is
    built from a state blob persisted into a session, and every session written
    before Phase 14 carries a usage dict with none of these keys.
    """
    state = initial_state("why?")
    state["usage"] = {
        "calls": 4,
        "cost_usd": 0.15,
        "embedding_tokens": 4200,
        "embedding_requests": 2,
        "embedding_cost_usd": 0.000252,
    }
    record = RunRecord.from_state(state)
    assert record.embedding_tokens == 4200
    assert record.embedding_requests == 2
    assert record.embedding_cost_usd == pytest.approx(0.000252)
    # cost_usd already contains the embedding dollars -- the column splits the
    # total out, it does not add to it.
    assert record.cost_usd == 0.15

    pre_phase = initial_state("why?")
    pre_phase["usage"] = {"calls": 4, "cost_usd": 0.15}
    older = RunRecord.from_state(pre_phase)
    assert (older.embedding_tokens, older.embedding_requests) == (0, 0)
    assert older.embedding_cost_usd == 0.0


# --------------------------------------------------------------------------
# Aggregation
# --------------------------------------------------------------------------


def test_empty_store_reports_zeroes_and_null_rates(store):
    """Rates are null, not zero: with no runs there is no approval rate, and
    a dashboard rendering 0% would be reporting a failure that didn't happen."""
    summary = store.summary()

    assert summary["runs"]["total"] == 0
    assert summary["runs"]["failure_rate"] is None
    assert summary["quality"]["approval_rate"] is None
    assert summary["quality"]["avg_revisions"] is None
    assert summary["cost"]["avg_usd_per_run"] is None
    assert summary["latency_ms"] == {"p50": 0.0, "p95": 0.0, "max": 0.0}


def test_counts_split_by_mode_and_status(store):
    store.record(run(mode="research"))
    store.record(run(mode="followup"))
    store.record(run(mode="research", status=FAILED, approved=False,
                     error_type="RateLimitError"))

    runs = store.summary()["runs"]
    assert runs["total"] == 3
    assert runs["completed"] == 2
    assert runs["failed"] == 1
    assert runs["research"] == 2
    assert runs["followup"] == 1
    assert runs["failure_rate"] == 0.3333  # rates are rounded to 4 dp


def test_approval_rate_is_over_completed_runs_not_all_runs(store):
    """A run that never finished was never judged by the critic. Counting it
    against the approval rate would blame the critic for an outage."""
    store.record(run(approved=True))
    store.record(run(approved=False))
    store.record(run(status=FAILED, approved=False, error_type="APIConnectionError"))

    quality = store.summary()["quality"]
    assert quality["approved"] == 1
    assert quality["approval_rate"] == 0.5  # 1 of 2 completed, not 1 of 3


def test_forced_stops_are_broken_out_by_reason(store):
    store.record(run(forced_stop_reason="max_revisions_exceeded"))
    store.record(run(forced_stop_reason="max_revisions_exceeded"))
    store.record(run(forced_stop_reason="budget_exceeded"))
    store.record(run())

    quality = store.summary()["quality"]
    assert quality["forced_stops"] == 3
    assert quality["forced_stop_reasons"] == {
        "max_revisions_exceeded": 2,
        "budget_exceeded": 1,
    }


def test_errors_are_broken_out_by_type(store):
    store.record(run(status=FAILED, error_type="RateLimitError"))
    store.record(run(status=FAILED, error_type="RateLimitError"))
    store.record(run(status=FAILED, error_type="APIConnectionError"))

    assert store.summary()["reliability"]["errors"] == {
        "RateLimitError": 2,
        "APIConnectionError": 1,
    }


def test_cost_and_tokens_are_summed(store):
    store.record(run(cost_usd=0.10, input_tokens=100, output_tokens=10, web_searches=2, calls=4))
    store.record(run(cost_usd=0.30, input_tokens=200, output_tokens=20, web_searches=1, calls=4))

    cost = store.summary()["cost"]
    assert cost["total_usd"] == pytest.approx(0.40)
    assert cost["avg_usd_per_run"] == pytest.approx(0.20)
    assert cost["input_tokens"] == 300
    assert cost["web_searches"] == 3
    assert cost["model_calls"] == 8


def test_average_cost_is_over_every_run_including_failures(store):
    """A failed run still burned tokens before it died -- excluding it would
    understate what the service actually costs to operate."""
    store.record(run(cost_usd=0.10))
    store.record(run(status=FAILED, cost_usd=0.30, error_type="RateLimitError"))

    assert store.summary()["cost"]["avg_usd_per_run"] == pytest.approx(0.20)


def test_retries_are_summed(store):
    store.record(run(retries=2))
    store.record(run(retries=3))
    assert store.summary()["reliability"]["retries"] == 5


def test_latency_percentiles_cover_completed_runs(store):
    for ms in (100, 200, 300, 400, 500, 600, 700, 800, 900, 1000):
        store.record(run(duration_ms=float(ms)))

    latency = store.summary()["latency_ms"]
    assert latency["p50"] == 500.0
    assert latency["p95"] == 1000.0
    assert latency["max"] == 1000.0


def test_failed_runs_are_excluded_from_latency(store):
    """Time-to-failure is not time-to-report; mixing them makes a fast
    outage look like a latency improvement."""
    store.record(run(duration_ms=1000.0))
    store.record(run(status=FAILED, duration_ms=1.0, error_type="RateLimitError"))

    assert store.summary()["latency_ms"]["p50"] == 1000.0


@pytest.mark.parametrize(
    "values, fraction, expected",
    [
        ([], 0.5, 0.0),
        ([42.0], 0.95, 42.0),
        ([1.0, 2.0], 0.5, 1.0),
        ([1.0, 2.0, 3.0, 4.0], 1.0, 4.0),
    ],
)
def test_percentile_edges(values, fraction, expected):
    assert _percentile(values, fraction) == expected


# --------------------------------------------------------------------------
# Storage
# --------------------------------------------------------------------------


def test_records_survive_reopening(tmp_path):
    path = str(tmp_path / "metrics.db")
    first = SQLiteMetricsStore(path)
    first.record(run())
    first.close()

    reopened = SQLiteMetricsStore(path)
    try:
        assert reopened.count() == 1
    finally:
        reopened.close()


# --------------------------------------------------------------------------
# Migrating a table that already exists
# --------------------------------------------------------------------------
#
# `record()` builds its INSERT column list from `asdict(run)`, so every new
# RunRecord field names a column on every write. `CREATE TABLE IF NOT EXISTS`
# does nothing to a table that is already there, which makes a new field a 500
# at the metrics step of the first post-deploy request -- on every request,
# until someone migrates by hand.
#
# Both tests below therefore open a table that PREDATES the columns and has a
# row in it. A migration test against a fresh table proves creation, not
# migration, and would pass with the migration deleted.

# The runs table exactly as it stood before Phase 14, written out rather than
# derived: a constant that tracked the current schema would silently stop being
# an old table the next time the schema moved.
PRE_PHASE_14_RUNS_TABLE = """
CREATE TABLE runs (
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
"""

EMBEDDING_COLUMN_NAMES = ("embedding_tokens", "embedding_requests", "embedding_cost_usd")


def test_runrecord_schema_migrates_a_preexisting_sqlite_file(tmp_path):
    """A local checkout's metrics.db, opened by this phase's code."""
    path = str(tmp_path / "old-metrics.db")
    old = sqlite3.connect(path)
    old.executescript(PRE_PHASE_14_RUNS_TABLE)
    old.execute(
        "INSERT INTO runs (run_id, mode, status, cost_usd, duration_ms, created_at) "
        "VALUES ('before', 'research', 'completed', 0.12, 900.0, 1000.0)"
    )
    old.commit()
    # Non-vacuity: this really is a table without the columns. Without this the
    # test would still pass if the fixture had quietly built the new schema.
    columns = {row[1] for row in old.execute("PRAGMA table_info(runs)")}
    assert not columns & set(EMBEDDING_COLUMN_NAMES), columns
    old.close()

    store = SQLiteMetricsStore(path)
    try:
        store.record(run(run_id="after", embedding_tokens=50, embedding_requests=2,
                         embedding_cost_usd=0.000003, cost_usd=0.20, created_at=2000.0))
        assert store.count() == 2
        # The aggregates and the cap's spend query both read every row,
        # including the one written before the columns existed.
        assert store.summary()["cost"]["total_usd"] == pytest.approx(0.32)
        assert store.spend_since(0.0) == pytest.approx(0.32)
    finally:
        store.close()

    reopened = sqlite3.connect(path)
    try:
        rows = {
            r[0]: (r[1], r[2], r[3])
            for r in reopened.execute(
                "SELECT run_id, embedding_tokens, embedding_requests, embedding_cost_usd "
                "FROM runs"
            )
        }
    finally:
        reopened.close()
    assert rows["after"] == (50, 2, pytest.approx(0.000003))
    # The pre-existing row reads as zero, via the column default -- which is
    # true rather than merely convenient: that run recorded no embedding spend.
    assert rows["before"] == (0, 0, 0.0)


@pytest.mark.skipif(not HAS_POSTGRES, reason="DATABASE_URL is not set")
def test_runrecord_schema_migrates_a_column_dropped_pg_table():
    """The deployed Supabase table, simulated by removing what this phase adds.

    Dropping the columns from a table that already has rows is the closest
    reachable stand-in for the live table, and the store is left in the
    migrated state afterwards on purpose: that IS the post-phase state, and a
    teardown that re-dropped them would leave the next test running against a
    database this phase has supposedly already migrated.
    """
    seeded = PostgresMetricsStore()
    try:
        seeded.record(run(run_id="pg-before", cost_usd=0.12))
    finally:
        seeded.close()

    database = db.Database()
    try:
        database.execute(
            "ALTER TABLE runs "
            "DROP COLUMN IF EXISTS embedding_tokens, "
            "DROP COLUMN IF EXISTS embedding_requests, "
            "DROP COLUMN IF EXISTS embedding_cost_usd"
        )
        # Non-vacuity, again: the table under test is genuinely missing them.
        present = {
            row["column_name"]
            for row in database.fetchall(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'runs'"
            )
        }
        assert not present & set(EMBEDDING_COLUMN_NAMES), present
        assert "cost_usd" in present  # and it is still the runs table
    finally:
        database.close()

    migrated = PostgresMetricsStore()
    try:
        migrated.record(
            run(run_id="pg-after", embedding_tokens=50, embedding_requests=2,
                embedding_cost_usd=0.000003)
        )
        row = migrated.db.fetchone(
            "SELECT embedding_tokens, embedding_requests, embedding_cost_usd "
            "FROM runs WHERE run_id = 'pg-after' ORDER BY id DESC LIMIT 1"
        )
        assert row["embedding_tokens"] == 50
        assert row["embedding_requests"] == 2
        assert row["embedding_cost_usd"] == pytest.approx(0.000003)
        # And the row that predates the migration reads zero rather than null,
        # which is what keeps SUM(embedding_cost_usd) a number.
        before = migrated.db.fetchone(
            "SELECT embedding_tokens, embedding_cost_usd FROM runs "
            "WHERE run_id = 'pg-before' ORDER BY id DESC LIMIT 1"
        )
        assert (before["embedding_tokens"], before["embedding_cost_usd"]) == (0, 0.0)
    finally:
        migrated.close()


def test_concurrent_writes_do_not_lose_runs(store):
    import threading

    errors = []

    def write():
        try:
            for _ in range(10):
                store.record(run())
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=write) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert store.count() == 40
