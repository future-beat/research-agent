"""
One suite, every backend.

The claim these phases keep making is that the stores are swappable. That is
only true if the implementations actually agree, and two hand-written SQL
dialects agreeing is exactly the kind of thing that quietly stops being true.
So the behavioural tests live here once and run against each backend.

Postgres tests are skipped unless DATABASE_URL points at a real server; CI
provides one (with pgvector) so the Postgres path is genuinely exercised
rather than merely written.

    docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=pw pgvector/pgvector:pg16
    DATABASE_URL=postgresql://postgres:pw@localhost:5432/postgres pytest
"""

import pytest
from test_memory_stores import FakeEmbedder

import db
import metrics as metrics_module
import sessions as sessions_module
import vector_memory as vm
from metrics import COMPLETED, FAILED, PostgresMetricsStore, RunRecord, SQLiteMetricsStore
from sessions import PostgresSessionStore, SQLiteSessionStore, _describe_dsn
from vector_memory import InMemoryStore, JSONMemoryStore, PgVectorMemoryStore

HAS_POSTGRES = db.postgres_configured()
BACKENDS = ["sqlite", "postgres"]

# The fake embedder is 5-dimensional; the pgvector column has to match, and a
# dedicated table keeps the contract run from colliding with real notes.
FAKE_DIMENSIONS = len(FakeEmbedder.VOCAB)
CONTRACT_NOTES_TABLE = "contract_test_notes"


def _skip_without_postgres(backend: str) -> None:
    if backend == "postgres" and not HAS_POSTGRES:
        pytest.skip("DATABASE_URL is not set")


@pytest.fixture(params=BACKENDS)
def sessions(request, tmp_path):
    _skip_without_postgres(request.param)
    if request.param == "postgres":
        store = PostgresSessionStore()
        store.db.execute("TRUNCATE sessions")
    else:
        store = SQLiteSessionStore(str(tmp_path / "sessions.db"))
    yield store
    store.close()


@pytest.fixture(params=BACKENDS)
def runs(request, tmp_path):
    _skip_without_postgres(request.param)
    if request.param == "postgres":
        store = PostgresMetricsStore()
        store.db.execute("TRUNCATE runs")
    else:
        store = SQLiteMetricsStore(str(tmp_path / "metrics.db"))
    yield store
    store.close()


@pytest.fixture(params=["json", "memory", "pgvector"])
def notes(request, tmp_path):
    embedder = FakeEmbedder()
    if request.param == "pgvector":
        if not HAS_POSTGRES:
            pytest.skip("DATABASE_URL is not set")
        store = PgVectorMemoryStore(
            embedder=embedder, table=CONTRACT_NOTES_TABLE, dimensions=FAKE_DIMENSIONS
        )
        store.db.execute(f"TRUNCATE {CONTRACT_NOTES_TABLE}")
    elif request.param == "json":
        store = JSONMemoryStore(path=str(tmp_path / "notes.json"), embedder=embedder)
    else:
        store = InMemoryStore(embedder=embedder)
    yield store
    store.close()


def finished_state(**overrides) -> dict:
    state = {
        "run_id": "r1",
        "task": "why?",
        "mode": "research",
        "topic_type": "technical",
        "research_notes": "notes",
        "source_report": "",
        "conversation": [],
        "draft": "the report",
        "critic_feedback": "",
        "approved": True,
        "reviewed": True,
        "revision_count": 0,
        "forced_stop_reason": "",
        "next_step": "done",
        "iteration": 7,
        "usage": {"calls": 4, "cost_usd": 0.12},
        "trace": [],
    }
    state.update(overrides)
    return state


def run_record(**overrides) -> RunRecord:
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
# Session store contract
# --------------------------------------------------------------------------


def test_create_then_get_round_trips_the_state(sessions):
    state = finished_state()
    session_id = sessions.create("why?", state)

    loaded = sessions.get(session_id)
    assert loaded.task == "why?"
    assert loaded.turns == 1
    assert loaded.state == state


def test_nested_state_survives_the_round_trip(sessions):
    """The state blob carries lists and dicts. A backend that flattened them
    would break follow-up chaining in a way no schema check would catch."""
    state = finished_state(
        conversation=[{"question": "q1", "answer": "a1"}, {"question": "q2", "answer": "a2"}],
        usage={"calls": 4, "cost_usd": 0.12, "pricing_unknown": False},
    )
    loaded = sessions.get(sessions.create("why?", state))

    assert loaded.state["conversation"][1]["answer"] == "a2"
    assert loaded.state["usage"]["pricing_unknown"] is False


def test_unknown_session_is_none(sessions):
    assert sessions.get("nope") is None


def test_append_turn_replaces_state_and_counts_the_turn(sessions):
    session_id = sessions.create("why?", finished_state())
    sessions.append_turn(session_id, finished_state(mode="followup", draft="the answer"))

    loaded = sessions.get(session_id)
    assert loaded.turns == 2
    assert loaded.state["draft"] == "the answer"
    assert loaded.task == "why?"  # the title stays the original question


def test_append_turn_to_an_unknown_session_raises(sessions):
    with pytest.raises(KeyError):
        sessions.append_turn("nope", finished_state())


def test_sessions_list_newest_updated_first(sessions):
    first = sessions.create("first", finished_state())
    second = sessions.create("second", finished_state())
    sessions.append_turn(first, finished_state())

    assert [s.id for s in sessions.list()] == [first, second]


def test_list_respects_its_limit(sessions):
    for n in range(5):
        sessions.create(f"q{n}", finished_state())
    assert len(sessions.list(limit=3)) == 3


def test_delete_reports_whether_it_removed_anything(sessions):
    session_id = sessions.create("q", finished_state())
    assert sessions.delete(session_id) is True
    assert sessions.delete(session_id) is False
    assert sessions.count() == 0


def test_count_tracks_sessions_not_turns(sessions):
    session_id = sessions.create("q", finished_state())
    sessions.append_turn(session_id, finished_state())
    assert sessions.count() == 1


def test_session_path_never_leaks_a_password(sessions):
    """`path` is returned by /health."""
    assert "password" not in sessions.path
    assert "sup3rsecret" not in sessions.path


# --------------------------------------------------------------------------
# Metrics store contract
# --------------------------------------------------------------------------


def test_empty_metrics_report_null_rates(runs):
    summary = runs.summary()
    assert summary["runs"]["total"] == 0
    assert summary["quality"]["approval_rate"] is None
    assert summary["cost"]["avg_usd_per_run"] is None


def test_metrics_counts_split_by_mode_and_status(runs):
    runs.record(run_record(mode="research"))
    runs.record(run_record(mode="followup"))
    runs.record(run_record(status=FAILED, approved=False, error_type="RateLimitError"))

    summary = runs.summary()["runs"]
    assert (summary["total"], summary["completed"], summary["failed"]) == (3, 2, 1)
    assert (summary["research"], summary["followup"]) == (2, 1)


def test_metrics_approval_rate_is_over_completed_runs(runs):
    runs.record(run_record(approved=True))
    runs.record(run_record(approved=False))
    runs.record(run_record(status=FAILED, approved=False, error_type="APIConnectionError"))

    assert runs.summary()["quality"]["approval_rate"] == 0.5


def test_metrics_group_forced_stops_and_errors(runs):
    runs.record(run_record(forced_stop_reason="budget_exceeded"))
    runs.record(run_record(forced_stop_reason="budget_exceeded"))
    runs.record(run_record(forced_stop_reason="max_revisions_exceeded"))
    runs.record(run_record(status=FAILED, error_type="RateLimitError"))

    summary = runs.summary()
    assert summary["quality"]["forced_stop_reasons"] == {
        "budget_exceeded": 2,
        "max_revisions_exceeded": 1,
    }
    assert summary["reliability"]["errors"] == {"RateLimitError": 1}


def test_metrics_sum_cost_and_tokens_as_plain_numbers(runs):
    """Postgres returns SUM(BIGINT) as Decimal, which is not JSON
    serialisable -- /metrics would 500 on the first recorded run."""
    runs.record(run_record(cost_usd=0.10, input_tokens=100, output_tokens=10, calls=4))
    runs.record(run_record(cost_usd=0.30, input_tokens=200, output_tokens=20, calls=4))

    cost = runs.summary()["cost"]
    assert cost["total_usd"] == pytest.approx(0.40)
    assert cost["input_tokens"] == 300
    assert isinstance(cost["input_tokens"], int)
    assert isinstance(cost["total_usd"], float)


def test_metrics_latency_percentiles_cover_completed_runs_only(runs):
    for ms in (100, 200, 300, 400, 500, 600, 700, 800, 900, 1000):
        runs.record(run_record(duration_ms=float(ms)))
    runs.record(run_record(status=FAILED, duration_ms=1.0, error_type="Boom"))

    latency = runs.summary()["latency_ms"]
    assert (latency["p50"], latency["p95"], latency["max"]) == (500.0, 1000.0, 1000.0)


def test_metrics_summary_is_json_serialisable(runs):
    import json

    runs.record(run_record())
    json.dumps(runs.summary())


@pytest.mark.skipif(not HAS_POSTGRES, reason="DATABASE_URL is not set")
def test_both_metrics_backends_agree_exactly(tmp_path):
    """The strongest form of the swappability claim: identical input in,
    byte-identical summary out. The two aggregation dialects genuinely
    differ, so nothing but this would catch them drifting apart."""
    sqlite_store = SQLiteMetricsStore(str(tmp_path / "m.db"))
    pg_store = PostgresMetricsStore()
    pg_store.db.execute("TRUNCATE runs")

    records = [
        run_record(mode="research", approved=True, cost_usd=0.11, duration_ms=900.0,
                   input_tokens=1000, retries=1),
        run_record(mode="followup", approved=False, cost_usd=0.02, duration_ms=120.0,
                   forced_stop_reason="budget_exceeded"),
        run_record(status=FAILED, approved=False, error_type="RateLimitError",
                   cost_usd=0.05, duration_ms=30.0),
    ]
    for record in records:
        sqlite_store.record(record)
        pg_store.record(record)

    try:
        assert sqlite_store.summary() == pg_store.summary()
    finally:
        sqlite_store.close()
        pg_store.close()


# --------------------------------------------------------------------------
# Memory store contract
# --------------------------------------------------------------------------


def test_empty_memory_returns_nothing(notes):
    assert notes.query("langgraph") == []
    assert len(notes) == 0


def test_notes_are_recalled(notes):
    notes.add("langgraph supervisor pattern")
    assert notes.query("langgraph") == ["langgraph supervisor pattern"]
    assert len(notes) == 1


def test_recall_is_ordered_most_similar_first(notes):
    notes.add("chroma")
    notes.add("langgraph supervisor")
    notes.add("langgraph supervisor retry")

    results = notes.query("langgraph supervisor retry", top_k=3, min_similarity=0.0)
    assert results[0] == "langgraph supervisor retry"


def test_top_k_bounds_the_result_count(notes):
    for text in ("langgraph", "langgraph retry", "langgraph voyage", "langgraph chroma"):
        notes.add(text)
    assert len(notes.query("langgraph", top_k=2, min_similarity=0.0)) == 2


def test_the_relevance_floor_excludes_unrelated_notes(notes):
    """Without the floor, top_k always returns *something* -- and an
    unrelated note leaking into a research prompt is how a report ends up
    grounded in the wrong subject."""
    notes.add("chroma voyage")
    notes.add("langgraph supervisor")

    assert notes.query("langgraph", min_similarity=0.3) == ["langgraph supervisor"]


def test_describe_reports_the_count(notes):
    notes.add("langgraph")
    assert "1 note(s)" in notes.describe()


# --------------------------------------------------------------------------
# Backend selection and Postgres specifics
# --------------------------------------------------------------------------


def test_session_backend_follows_database_url(monkeypatch):
    monkeypatch.delenv("SESSION_BACKEND", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert sessions_module.default_backend() == "sqlite"

    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h/d")
    assert sessions_module.default_backend() == "postgres"


def test_metrics_backend_follows_database_url(monkeypatch):
    """Sessions in Postgres with metrics still on a per-machine disk would be
    a half-migration nobody intended."""
    monkeypatch.delenv("METRICS_BACKEND", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h/d")
    assert metrics_module.default_backend() == "postgres"


def test_memory_backend_follows_database_url(monkeypatch):
    monkeypatch.delenv("VECTOR_STORE", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h/d")
    assert vm.default_backend() == "pgvector"


def test_an_explicit_backend_overrides_the_default(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h/d")
    monkeypatch.setenv("SESSION_BACKEND", "sqlite")
    assert sessions_module.default_backend() == "sqlite"


@pytest.mark.parametrize("factory, kind", [
    (sessions_module.get_session_store, "SESSION_BACKEND"),
    (metrics_module.get_metrics_store, "METRICS_BACKEND"),
])
def test_unknown_backends_fail_loudly(factory, kind):
    with pytest.raises(ValueError, match="postgres"):
        factory("mysql")


def test_dsn_description_strips_the_password():
    described = _describe_dsn("postgresql://user:sup3rsecret@db.example.com:5432/agent")
    assert described == "postgres://db.example.com/agent"
    assert "sup3rsecret" not in described


def test_a_bad_pgvector_table_name_is_rejected():
    """The table name reaches DDL, where parameter binding cannot help."""
    with pytest.raises(ValueError, match="alphanumeric"):
        PgVectorMemoryStore(embedder=FakeEmbedder(), table="notes; DROP TABLE sessions")


@pytest.mark.skipif(not HAS_POSTGRES, reason="DATABASE_URL is not set")
def test_a_dimension_mismatch_is_explained_not_a_type_error():
    """Changing embedding model against an existing table otherwise fails
    somewhere inside an INSERT with a bare Postgres type error."""
    store = PgVectorMemoryStore(
        embedder=FakeEmbedder(), table=CONTRACT_NOTES_TABLE, dimensions=FAKE_DIMENSIONS
    )
    store.dimensions = FAKE_DIMENSIONS + 1  # as if the model changed under us
    try:
        with pytest.raises(ValueError, match="VECTOR_DIMENSIONS"):
            store.add("langgraph")
    finally:
        store.close()


@pytest.mark.skipif(not HAS_POSTGRES, reason="DATABASE_URL is not set")
def test_the_connection_recovers_from_being_dropped():
    """Managed Postgres closes idle connections. Without the reconnect, the
    first request after a quiet night fails."""
    store = PostgresSessionStore()
    try:
        store.create("before", finished_state())
        store.db._conn.close()  # simulate the provider hanging up
        assert store.count() == 1  # must reconnect rather than raise
    finally:
        store.close()


def test_postgres_really_ran_when_ci_said_it_would():
    """A guard against the worst outcome for this whole file: DATABASE_URL
    missing or wrong in CI, every Postgres test silently skipping, and the
    build going green over an entirely untested backend.

    CI sets REQUIRE_POSTGRES=1. Locally it is unset and this test skips.
    """
    import os

    if not os.environ.get("REQUIRE_POSTGRES"):
        pytest.skip("REQUIRE_POSTGRES is not set; Postgres coverage is optional here")

    assert HAS_POSTGRES, "REQUIRE_POSTGRES is set but DATABASE_URL is empty"

    # Reachability, not just configuration -- a DSN pointing at nothing would
    # otherwise let every other Postgres test error rather than skip, which is
    # noisier but no more informative than this one line.
    store = PostgresSessionStore()
    try:
        store.count()
    finally:
        store.close()
