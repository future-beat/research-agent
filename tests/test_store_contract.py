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

import contextlib
import threading
import time

import psycopg
import pytest
from test_memory_stores import FakeEmbedder

from research_agent import db
from research_agent import memory as vm
from research_agent import metrics as metrics_module
from research_agent import sessions as sessions_module
from research_agent.memory import (
    ChromaMemoryStore,
    InMemoryStore,
    JSONMemoryStore,
    PgVectorMemoryStore,
)
from research_agent.metrics import (
    COMPLETED,
    FAILED,
    PostgresMetricsStore,
    RunRecord,
    SQLiteMetricsStore,
)
from research_agent.sessions import PostgresSessionStore, SQLiteSessionStore, _describe_dsn

HAS_POSTGRES = db.postgres_configured()
BACKENDS = ["sqlite", "postgres"]

# The fake embedder is 5-dimensional; the pgvector column has to match, and a
# dedicated table keeps the contract run from colliding with real notes.
FAKE_DIMENSIONS = len(FakeEmbedder.VOCAB)
CONTRACT_NOTES_TABLE = "contract_test_notes"


def _skip_without_postgres(backend: str) -> None:
    if backend == "postgres" and not HAS_POSTGRES:
        pytest.skip("DATABASE_URL is not set")


def _dsn_tagged(application_name: str, **params: str) -> str:
    """DATABASE_URL carrying an application_name, and any other libpq params.

    Two jobs. It lets a test find its own backends in pg_stat_activity, which
    is how the reconnect test kills only what it owns on a shared CI server.
    And it makes the DSN test-unique, which matters because db._pool_for
    caches one pool per DSN with the pool settings read at *construction*: a
    test that varies PG_POOL_TIMEOUT and shares a DSN would silently be handed
    a pool built at someone else's setting.
    """
    parts = {"application_name": application_name, **params}
    base = db.database_url()
    separator = "&" if "?" in base else "?"
    return base + separator + "&".join(f"{k}={v}" for k, v in parts.items())


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


@pytest.fixture(params=["json", "memory", "chroma", "pgvector"])
def notes(request, tmp_path):
    embedder = FakeEmbedder()
    if request.param == "pgvector":
        if not HAS_POSTGRES:
            pytest.skip("DATABASE_URL is not set")
        store = PgVectorMemoryStore(
            embedder=embedder, table=CONTRACT_NOTES_TABLE, dimensions=FAKE_DIMENSIONS
        )
        store.db.execute(f"TRUNCATE {CONTRACT_NOTES_TABLE}")
    elif request.param == "chroma":
        # CI installs the dev extra, which composes chroma -- so this arm
        # COLLECTS and runs there. The guard is only for a local checkout
        # without the extra; it must never gate on HAS_POSTGRES.
        try:
            import chromadb  # noqa: F401
        except ImportError:
            pytest.skip("chromadb not installed")
        store = ChromaMemoryStore(
            path=str(tmp_path / "chroma"), collection=CONTRACT_NOTES_TABLE, embedder=embedder
        )
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


# -- ownership and expiry (Phase 12) ---------------------------------------
#
# These run on BOTH session backends deliberately. The two stores compute the
# expiry cutoff from different clocks -- Python's for SQLite, the database's own
# for Postgres -- and the whole point of deriving expiry that way is that the
# *observable* behaviour is identical. A test that only ran on SQLite would
# leave the multi-machine backend, the one that actually serves the deployment,
# unproven.


def _rewind(sessions, session_id: str, seconds: float) -> None:
    """Drag a session's last-write time `seconds` into the past.

    Reaching past the store's API on purpose: the alternative is sleeping for
    seven days. `updated_at` is a plain epoch column on both backends, so this
    produces exactly the row an idle week produces.
    """
    if isinstance(sessions, PostgresSessionStore):
        sessions.db.execute(
            "UPDATE sessions SET updated_at = updated_at - %s WHERE id = %s",
            (seconds, session_id),
        )
    else:
        with sessions._lock:
            sessions._conn.execute(
                "UPDATE sessions SET updated_at = updated_at - ? WHERE id = ?",
                (seconds, session_id),
            )
            sessions._conn.commit()


def test_expiry_lazy_and_reads_do_not_renew(sessions, monkeypatch):
    """Idle past the TTL stops resolving; a read does not push the line back.

    Both halves matter and only together. Expiry alone is satisfiable by a
    store whose reads renew `updated_at`, which is the failure mode that makes
    "7 days after last activity" mean "7 days after last glance" and leaves the
    table growing forever. So the renewal half is asserted on a LIVE session
    before the expiry half is asserted on an idle one.
    """
    monkeypatch.setenv("SESSION_TTL_DAYS", "7")

    live = sessions.create("live one", finished_state(), owner="alice")
    before = sessions.get(live).updated_at
    for _ in range(3):
        assert sessions.get(live) is not None
        assert sessions.list(owner="alice")
    assert sessions.get(live).updated_at == before, "a read renewed updated_at"

    # Eight days idle: past the seven-day line, still physically present.
    _rewind(sessions, live, 8 * 86400)
    assert sessions.count() == 1, "the row is still there; only the filter should hide it"
    assert sessions.get(live) is None
    assert sessions.list() == []
    assert sessions.list(owner="alice") == []

    # The TTL is a knob, not a constant: widen it and the same row is live
    # again, which proves the filter is reading the setting rather than a
    # hardcoded seven.
    monkeypatch.setenv("SESSION_TTL_DAYS", "30")
    assert sessions.get(live) is not None


def test_sweep_deletes_expired(sessions, monkeypatch):
    """A create() bounds the table: the expired row is gone, not merely hidden.

    Asserted on count(), which is unfiltered -- against get()/list() a lazy
    filter alone would look identical to a sweep, and only one of them keeps
    the store from growing without limit.
    """
    monkeypatch.setenv("SESSION_TTL_DAYS", "7")

    stale = sessions.create("old", finished_state(), owner="alice")
    orphan = sessions.create("pre-phase-12", finished_state())  # owner='' by default
    _rewind(sessions, stale, 8 * 86400)
    _rewind(sessions, orphan, 8 * 86400)
    assert sessions.count() == 2  # non-vacuity: there is something to sweep

    fresh = sessions.create("new", finished_state(), owner="bob")

    assert sessions.count() == 1, "the sweep on create() did not remove the expired rows"
    assert [s.id for s in sessions.list()] == [fresh]
    assert sessions.get(stale) is None
    assert sessions.get(orphan) is None


def test_list_scopes_to_an_owner_and_none_is_unscoped(sessions):
    """The data path behind the dual-mode listing.

    `owner=None` is the operator's unscoped view, a string is one caller's.
    Exact match, never "empty means all": the pre-Phase-12 rows carry owner=''
    and must resolve for nobody.
    """
    mine = sessions.create("mine", finished_state(), owner="alice")
    theirs = sessions.create("theirs", finished_state(), owner="bob")
    orphan = sessions.create("orphaned", finished_state())

    assert [s.id for s in sessions.list(owner="alice")] == [mine]
    assert [s.id for s in sessions.list(owner="bob")] == [theirs]
    assert sorted(s.id for s in sessions.list()) == sorted([mine, theirs, orphan])

    # owner='' is a real owner value, not a wildcard.
    assert [s.id for s in sessions.list(owner="")] == [orphan]
    assert sessions.list(owner="carol") == []


def test_owner_round_trips_and_defaults_to_empty(sessions):
    """A session remembers who minted it, and a caller-less create is claimed
    by nobody rather than by everybody."""
    owned = sessions.get(sessions.create("q", finished_state(), owner="alice"))
    assert owned.owner == "alice"
    assert owned.summary()["owner"] == "alice"

    assert sessions.get(sessions.create("q", finished_state())).owner == ""


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


def test_metrics_includes_embedding_spend(runs):
    """Voyage spend has its own line in the cost section, in both backends.

    This lives here rather than in test_metrics.py because that file has one
    SQLite fixture and no backend parameterisation: the aggregate arrives
    from Postgres as a Decimal, so a SQLite-only assertion would leave the
    coercion that keeps /metrics JSON-serialisable entirely untested.

    The third record carries the pre-phase shape -- zeros for all three
    columns, the way every row written before this phase reads -- so the sum
    is over a mixed table rather than a table where every row is new.
    """
    runs.record(run_record(embedding_tokens=25, embedding_requests=1,
                           embedding_cost_usd=0.0000015))
    runs.record(run_record(embedding_tokens=50, embedding_requests=2,
                           embedding_cost_usd=0.000003))
    runs.record(run_record())

    cost = runs.summary()["cost"]
    assert cost["embedding_tokens"] == 75
    assert cost["embedding_requests"] == 3
    assert cost["embedding_usd"] == round(0.0000045, 6)
    # Plain numbers, not Decimal -- the /metrics response is JSON.
    assert isinstance(cost["embedding_tokens"], int)
    assert isinstance(cost["embedding_usd"], float)


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


# -- note ownership and expiry (Phase 12) ----------------------------------
#
# These two run on all FOUR note backends, which is the whole of SC-5: the
# roadmap promises notes behave identically across json, memory, chroma and
# pgvector, and four hand-written filters agreeing is exactly the kind of
# thing that quietly stops being true. Three of the arms need no server; the
# pgvector arm skips without DATABASE_URL and runs in CI, where the multi-
# machine backend is the one actually serving the deployment.


def test_note_scoping(notes):
    """A note is recalled for its owner and for nobody else.

    This is the prompt-injection fix, asserted at the store. Notes are read
    back into a researcher prompt whose output the critic then reviews, so a
    note one visitor caused to be written could steer another visitor's
    report. All three notes here embed IDENTICALLY -- the extra word is
    outside the fake embedder's vocabulary -- so similarity cannot be what
    separates them. Drop the owner filter from any backend and a query for
    one owner returns all three.
    """
    notes.add("langgraph supervisor alice-note", owner="alice")
    notes.add("langgraph supervisor bob-note", owner="bob")
    notes.add("langgraph supervisor orphan-note")  # owner='' by default

    # Both directions, per arm: mine comes back, theirs does not.
    assert notes.query("langgraph supervisor", owner="alice") == [
        "langgraph supervisor alice-note"
    ]
    assert notes.query("langgraph supervisor", owner="bob") == ["langgraph supervisor bob-note"]

    # owner='' is a real, exact owner value and never a wildcard. If it meant
    # "all", every pre-Phase-12 note would still leak into every run and the
    # REPL's own notes would be readable by the service.
    assert notes.query("langgraph supervisor", owner="") == [
        "langgraph supervisor orphan-note"
    ]

    # And an identity that wrote nothing recalls nothing, rather than
    # inheriting the communal store.
    assert notes.query("langgraph supervisor", owner="carol") == []


def test_note_ttl(notes, monkeypatch):
    """Past the TTL a note stops being recalled, and the next add sweeps it.

    The age is produced by moving the line rather than the note: NOTE_TTL_DAYS
    is read per call on every backend, so setting it to 0 puts an existing note
    on the far side of the cutoff without reaching into four different storage
    layouts to forge a timestamp. It also proves the backends read the setting
    rather than a hardcoded seven.

    Both halves are needed and neither implies the other. The filter is what
    makes expiry immediate; the sweep is what stops the store growing forever,
    and against query() alone a lazy filter looks exactly like a sweep. So the
    sweep is asserted on len(), which is unfiltered on all four backends --
    and then on the note staying gone once the TTL is widened back out, which
    a merely-hidden note would not.
    """
    monkeypatch.setenv("NOTE_TTL_DAYS", "7")
    notes.add("langgraph supervisor", owner="alice")
    # Non-vacuity: it is genuinely recallable before the line moves, so a
    # backend that returned [] for unrelated reasons cannot pass the next half.
    assert notes.query("langgraph supervisor", owner="alice") == ["langgraph supervisor"]

    monkeypatch.setenv("NOTE_TTL_DAYS", "0")
    assert notes.query("langgraph supervisor", owner="alice") == []
    assert len(notes) == 1, "the note should still be present, only filtered out"

    notes.add("chroma voyage", owner="alice")
    assert len(notes) == 1, "add() did not sweep the expired note"

    monkeypatch.setenv("NOTE_TTL_DAYS", "7")
    assert notes.query("langgraph supervisor", owner="alice") == [], (
        "widening the TTL brought the note back; it was hidden, not swept"
    )
    assert notes.query("chroma voyage", owner="alice") == ["chroma voyage"]


# -- the per-owner note cap (Phase 20) -------------------------------------
#
# The second bound. Expiry answers "how long", the cap answers "how many", and
# both have to mean the same thing on all four backends or the swappability
# claim is prose. These run on the same four arms for the same reason the two
# above do.


def _owned(notes, owner: str) -> set[str]:
    """Every one of `owner`'s recallable notes, as a set.

    Membership, never order: the notes these cases write all share one
    vocabulary word and differ only in an out-of-vocabulary suffix, so they
    embed IDENTICALLY under FakeEmbedder and similarity cannot rank them.
    That is deliberate -- WHICH notes survive an eviction is the claim, and the
    order of score-tied results is backend-defined and out of scope.
    """
    return set(notes.query("langgraph", top_k=50, min_similarity=0.0, owner=owner))


def test_note_cap_evicts_the_oldest_first(notes, monkeypatch):
    """One owner past the cap loses their oldest note, physically, everywhere.

    Asserted on len(), which is unfiltered on all four backends: against
    query() alone an eviction is indistinguishable from a filter, and only one
    of them bounds the store.

    Determinism here is not free. Four adds in a tight loop collide on
    created_at by construction -- 200 rapid time.time() calls on this machine
    produced 14 distinct values -- so "the oldest" cannot be decided by the
    clock. Each backend breaks the tie with its own insertion-ordered key
    (list index, an explicit seq, BIGSERIAL id), which is what makes all four
    arms agree on the same survivors rather than agreeing by luck.
    """
    monkeypatch.setenv("NOTE_CAP_PER_OWNER", "3")
    for n in (1, 2, 3):
        notes.add(f"langgraph note-{n}", owner="alice")

    # Non-vacuity: all three are genuinely recallable first, so a backend
    # returning [] for unrelated reasons cannot pass the eviction half below.
    assert _owned(notes, "alice") == {"langgraph note-1", "langgraph note-2",
                                      "langgraph note-3"}

    notes.add("langgraph note-4", owner="alice")

    assert len(notes) == 3, "the cap did not physically evict; len() is unfiltered"
    assert _owned(notes, "alice") == {"langgraph note-2", "langgraph note-3",
                                      "langgraph note-4"}


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


# --------------------------------------------------------------------------
# Pinned Postgres backends fail closed
#
# A PROPERTY TEST, NOT A PROGRESS GATE. These pass against today's tree,
# because the pins are env-driven and db.database_url() has always raised.
# They are here so the property is asserted rather than assumed, since the
# production topology now depends on it.
#
# What they do not prove is that the pins are actually SET in production.
# That gate is the stateless arm of test_local_store_paths_live_under_the_mount
# in tests/test_deploy_config.py, written in plan 11-03 and armed by 11-05.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("pin, value, factory", [
    ("SESSION_BACKEND", "postgres", sessions_module.get_session_store),
    ("METRICS_BACKEND", "postgres", metrics_module.get_metrics_store),
    ("VECTOR_STORE", "pgvector", lambda: vm.get_memory_store(embedder=FakeEmbedder())),
])
def test_a_pinned_postgres_backend_fails_closed_without_a_dsn(pin, value, factory, monkeypatch):
    """Pinning is the defence, and it has to fail loudly to be one.

    A machine with no mount and no DATABASE_URL must refuse to start, not
    quietly fall back. See the negative below for what it would fall back to.
    """
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv(pin, value)

    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        factory()


def test_unpinned_backends_default_to_container_local_storage(monkeypatch, tmp_path):
    """The negative that motivates the three above, kept in the file so the
    reason survives.

    With nothing pinned and no DSN, the defaults are per-container: SQLite
    files whose path defaults to the *module directory* -- and SESSION_DB_PATH
    is read at import time, so even the env var is not a late escape -- plus a
    JSON note store. Two mount-less machines would each boot happily on their
    own private copy: the per-machine split-brain this phase exists to end,
    now with data that vanishes on restart.

    Nothing raises, which is exactly the problem. It is why production pins
    the backends rather than trusting the DSN to be present.

    Constructed at explicit temp paths rather than through the factories, so
    asserting "this boots" does not drop a stray sessions.db next to the
    source -- the very default being complained about.
    """
    monkeypatch.delenv("DATABASE_URL", raising=False)
    for pin in ("SESSION_BACKEND", "METRICS_BACKEND", "VECTOR_STORE"):
        monkeypatch.delenv(pin, raising=False)

    assert sessions_module.default_backend() == "sqlite"
    assert metrics_module.default_backend() == "sqlite"
    assert vm.default_backend() == "json"

    stores = [
        SQLiteSessionStore(str(tmp_path / "sessions.db")),
        SQLiteMetricsStore(str(tmp_path / "metrics.db")),
        JSONMemoryStore(path=str(tmp_path / "notes.json"), embedder=FakeEmbedder()),
    ]
    for store in stores:
        store.close()


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
    first request after a quiet night fails.

    The kill is now server-side. This used to reach through the store into
    the private connection attribute the pool replaced and close it -- and
    closing a connection from the client was always the weaker simulation,
    because it fails at *checkout*, where a retry was never in doubt.
    Reaching for a private attribute is also how a test ends up broken by a
    refactor that broke nothing. `pg_terminate_backend` is what a managed
    provider actually does: the connection sits in the pool still looking
    live, the checkout succeeds, and the statement is where it dies. That is
    the case the read-level retry in db._read exists for.

    Scoped by application_name and excluding our own pid, so this cannot
    disturb anything else sharing the CI server.
    """
    marker = "ra_reconnect_test"
    store = PostgresSessionStore(dsn=_dsn_tagged(marker))
    killer = db.Database(_dsn_tagged("ra_reconnect_killer"))
    try:
        store.db.execute("TRUNCATE sessions")
        store.create("before", finished_state())

        killed = killer.fetchall(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE pid <> pg_backend_pid() AND application_name = %s",
            (marker,),
        )
        assert killed, "nothing was terminated; the kill would prove nothing"

        assert store.count() == 1  # must reconnect rather than raise
    finally:
        store.close()
        killer.close()


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


# --------------------------------------------------------------------------
# Booting when the database is not there
# --------------------------------------------------------------------------

UNREACHABLE_DSN = "postgresql://agent:sup3rsecret@10.255.255.1:5432/agent"


@pytest.fixture
def fast_timeout(monkeypatch):
    monkeypatch.setenv("PG_CONNECT_TIMEOUT", "1")


@pytest.mark.parametrize("factory", [
    lambda: PostgresSessionStore(dsn=UNREACHABLE_DSN),
    lambda: PostgresMetricsStore(dsn=UNREACHABLE_DSN),
])
def test_a_store_constructs_even_when_postgres_is_unreachable(factory, fast_timeout):
    """Schema DDL used to run in __init__, so an unavailable database stopped
    the *process from starting* -- and a health endpoint that reports degraded
    dependencies is worthless if the process never boots.

    Worse with a provider that pauses idle instances: the app could not start,
    so it never connected, so nothing ever woke the database. A deadlock that
    a restart could not break.
    """
    store = factory()
    try:
        assert store.db.schema_applied is False  # deferred, not skipped
    finally:
        store.close()


def test_a_deferred_schema_is_retried_on_first_use(fast_timeout):
    """Deferring must not mean forgetting: the block has to be applied the
    moment the database becomes reachable, or the service comes up degraded
    and stays that way."""
    store = PostgresSessionStore(dsn=UNREACHABLE_DSN)
    try:
        assert store.db._schema_sql is not None
        # Asserted on the exception TYPE, not on its message. This previously
        # pattern-matched the word "connect" case-insensitively out of the
        # error text, which under the pool depends on the exact wording of
        # psycopg_pool's PoolTimeout -- "couldn't get a connection after N.NN
        # sec". It happens to contain the substring, but a third-party error
        # string is not a contract, and a reworded release would turn this
        # green over an assertion that no longer checks anything. PoolTimeout
        # subclasses OperationalError, and "the failure is operational, not a
        # SQL error" is the property that actually matters. Deliberate
        # replacement -- please do not restore the string match.
        with pytest.raises(psycopg.OperationalError):
            store.count()  # still down: surfaces, rather than pretending
        assert store.db.schema_applied is False
    finally:
        store.close()


@pytest.mark.skipif(not HAS_POSTGRES, reason="DATABASE_URL is not set")
def test_the_schema_lands_on_first_use_against_a_real_server():
    store = PostgresSessionStore()
    try:
        assert store.db.schema_applied is True  # applied eagerly when reachable
        store.count()
    finally:
        store.close()


# --------------------------------------------------------------------------
# What only a real server can prove
#
# Everything below needs Postgres and skips without it. That is not a hole:
# these are precisely the claims a fake cannot support, and CI runs them with
# REQUIRE_POSTGRES=1, where a skip here would be caught by
# test_postgres_really_ran_when_ci_said_it_would.
# --------------------------------------------------------------------------


@pytest.mark.skipif(not HAS_POSTGRES, reason="DATABASE_URL is not set")
def test_advisory_lock_is_exclusive_across_connections():
    """The falsifying gate for db._apply_schema's single-connection invariant.

    Greps for `pg_advisory_lock` prove nothing here, and neither does the
    concurrent-init test below: the schema block is written with
    CREATE ... IF NOT EXISTS and tolerates duplicate-object errors, so it
    succeeds with the lock removed entirely. The only thing that shows the
    lock is real is a SECOND connection being refused it.

    The unlock's return value matters just as much, and the third assertion
    reproduces the split-across-checkouts failure directly: unlocking from a
    connection that does not hold the lock returns False. That is exactly what
    db._apply_schema would produce the moment its lock, DDL and unlock stopped
    sharing one cursor() call, since every cursor() call is a separate
    checkout and pg_advisory_lock is session-scoped. The result is a lock that
    serialises nothing AND leaks, held forever on a connection already handed
    back to the pool -- and _apply_schema raises on exactly this False.

    To be precise about the division of labour: this test proves the primitive
    behaves per-connection, which is *why* the single-connection invariant is
    required. The test that fails if _apply_schema itself is split is
    test_schema_lock_single_connection in tests/test_db.py, which counts the
    checkouts.
    """
    holder = db.Database(_dsn_tagged("ra_lock_holder"))
    rival = db.Database(_dsn_tagged("ra_lock_rival"))
    try:
        with holder.cursor() as held:
            held.execute("SELECT pg_advisory_lock(%s)", (db.SCHEMA_LOCK_KEY,))
            held.fetchone()

            with rival.cursor() as other:
                other.execute("SELECT pg_try_advisory_lock(%s)", (db.SCHEMA_LOCK_KEY,))
                assert other.fetchone()[0] is False, "a second connection took a held lock"

                # The split-across-checkouts signature, reproduced: an unlock
                # from a connection that does not hold the lock is a no-op
                # that reports itself as one.
                other.execute("SELECT pg_advisory_unlock(%s)", (db.SCHEMA_LOCK_KEY,))
                assert other.fetchone()[0] is False, "unlocked a lock held elsewhere"

            held.execute("SELECT pg_advisory_unlock(%s)", (db.SCHEMA_LOCK_KEY,))
            assert held.fetchone()[0] is True, "the unlock ran on a connection without the lock"

        # And now that it is genuinely released, the rival can have it.
        with rival.cursor() as other:
            other.execute("SELECT pg_try_advisory_lock(%s)", (db.SCHEMA_LOCK_KEY,))
            assert other.fetchone()[0] is True
            other.execute("SELECT pg_advisory_unlock(%s)", (db.SCHEMA_LOCK_KEY,))
            assert other.fetchone()[0] is True
    finally:
        holder.close()
        rival.close()


@pytest.mark.skipif(not HAS_POSTGRES, reason="DATABASE_URL is not set")
def test_concurrent_schema_init_from_two_processes_both_succeed():
    """A REGRESSION TEST, NOT A LOCK TEST.

    Be honest about what this can show: CREATE ... IF NOT EXISTS plus
    _apply_schema's duplicate-object tolerance satisfies it with the advisory
    lock absent entirely. test_advisory_lock_is_exclusive_across_connections
    above is the test that actually proves the lock.

    It still earns its place, because it is the race the phase creates: two
    machines booting simultaneously against an *empty* database, which
    `fly deploy` across two machines plus a start-clean Postgres together
    guarantee. Before this phase only one process ever ran the lazy schema
    path, so the race was structurally impossible to hit.
    """
    table = "contract_concurrent_init"
    schema = f"CREATE TABLE IF NOT EXISTS {table} (id BIGSERIAL PRIMARY KEY, note TEXT)"
    admin = db.Database(_dsn_tagged("ra_init_admin"))
    handles = [db.Database(_dsn_tagged(f"ra_init_{i}")) for i in range(2)]
    barrier = threading.Barrier(len(handles))
    failures: list[BaseException] = []

    def race(handle) -> None:
        handle._schema_sql = schema
        barrier.wait(timeout=10)
        try:
            handle._apply_schema()
        except BaseException as exc:  # noqa: BLE001 - recorded, then asserted on
            failures.append(exc)

    try:
        admin.execute(f"DROP TABLE IF EXISTS {table}")  # start genuinely empty
        threads = [threading.Thread(target=race, args=(h,)) for h in handles]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

        assert failures == [], f"concurrent schema init raised: {failures}"
        assert all(handle.schema_applied for handle in handles)
        assert admin.fetchone(
            "SELECT to_regclass(%s) AS present", (table,)
        )["present"] is not None
    finally:
        with contextlib.suppress(Exception):
            admin.execute(f"DROP TABLE IF EXISTS {table}")
        admin.close()
        for handle in handles:
            handle.close()


@pytest.mark.skipif(not HAS_POSTGRES, reason="DATABASE_URL is not set")
def test_statement_timeout_bounds_a_slow_query(monkeypatch):
    """The falsifying gate for the server-side half of the post-checkout bound.

    Without the `options="-c statement_timeout=..."` connect kwarg this waits
    the full five seconds and fails. PG_POOL_TIMEOUT cannot help: the checkout
    already succeeded, and its budget was spent before the statement started.

    What it does NOT cover, so nobody reads it as more than it is: a peer that
    stops answering entirely, where the server-side cancellation never reaches
    the client because nothing is reaching the client. That case is bounded by
    /health's per-probe wall clock, in tests/test_service.py.
    """
    monkeypatch.setenv("PG_STATEMENT_TIMEOUT", "500")
    handle = db.Database(_dsn_tagged("ra_stmt_timeout"))
    try:
        started = time.perf_counter()
        with pytest.raises(psycopg.errors.QueryCanceled):
            handle.fetchone("SELECT pg_sleep(5)")
        elapsed = time.perf_counter() - started
        assert elapsed < 2.0, f"pg_sleep(5) ran for {elapsed:.2f}s against a 500ms timeout"
    finally:
        handle.close()
        # This test varies a pool setting, and _pool_for caches per DSN with
        # the setting read at construction. Leaving the pool registered would
        # hand a 500ms-statement-timeout pool to whoever asks for this DSN next.
        db.close_all_pools()


@pytest.mark.skipif(not HAS_POSTGRES, reason="DATABASE_URL is not set")
def test_pgvector_search_path_lets_an_unqualified_cast_resolve():
    """Supabase installs pgvector into the `extensions` schema, not `public`.

    memory.py writes `vector(N)` column types and `%s::vector` casts
    unqualified, which do not resolve on the default search_path -- so the
    pool's `configure` callback sets one. CI's stock pgvector/pgvector:pg16
    image has no `extensions` schema at all, and Postgres tolerates a missing
    schema in search_path, so this has to pass in both worlds.

    Asserted twice on purpose: that the setting took (the callback ran on a
    pooled connection, which nothing had ever exercised against a server) and
    that a real cast resolves, because a setting being set is not the claim.
    """
    handle = db.Database(_dsn_tagged("ra_search_path"))
    store = PgVectorMemoryStore(
        embedder=FakeEmbedder(), table=CONTRACT_NOTES_TABLE, dimensions=FAKE_DIMENSIONS
    )
    try:
        search_path = handle.fetchone("SHOW search_path")["search_path"]
        assert "extensions" in search_path, search_path

        store.db.execute(f"TRUNCATE {CONTRACT_NOTES_TABLE}")
        store.add("langgraph models agents as an explicit state graph")
        assert store.query("langgraph") == [
            "langgraph models agents as an explicit state graph"
        ]
    finally:
        store.close()
        handle.close()


@pytest.mark.skipif(not HAS_POSTGRES, reason="DATABASE_URL is not set")
def test_a_session_written_on_one_instance_resolves_on_a_cross_instance_read():
    """The mechanism the whole phase rests on, isolated.

    A follow-up used to 404 when it landed on the machine that had not served
    the original run, because each machine held its own SQLite file. Here the
    write and the read go through separately constructed stores on separate
    pools -- separate connections to one database.

    What it does NOT prove: that Fly's proxy actually routes two requests to
    two machines. A second machine adds a network boundary and a routing
    decision; it does not add a new code path. The routing half is verified
    live against the deployed app in plan 11-05.
    """
    writer = PostgresSessionStore(dsn=_dsn_tagged("ra_instance_a"))
    reader = PostgresSessionStore(dsn=_dsn_tagged("ra_instance_b"))
    try:
        writer.db.execute("TRUNCATE sessions")
        session_id = writer.create("cross-instance question", finished_state())

        resolved = reader.get(session_id)

        assert resolved is not None, "the second instance could not see the session"
        assert resolved.task == "cross-instance question"
        assert reader.count() == 1
    finally:
        writer.close()
        reader.close()


@pytest.mark.skipif(not HAS_POSTGRES, reason="DATABASE_URL is not set")
def test_concurrent_reads_run_past_the_pool_max_size(monkeypatch):
    """The reversal REQ-connection-pool exists for, measured.

    fly.toml allows 16 in-flight requests per machine; two machines make 32
    against one database. Before this phase every one of them queued behind a
    single lock-guarded connection. Twelve threads against a max_size of five
    is comfortably more than the pool holds, so this exercises queueing rather
    than merely parallelism -- and none of them may time out.
    """
    monkeypatch.setenv("PG_POOL_MIN_SIZE", "1")
    monkeypatch.setenv("PG_POOL_MAX_SIZE", "5")
    monkeypatch.setenv("PG_POOL_TIMEOUT", "10")
    workers = 12
    assert workers >= 2 * 5

    store = PostgresSessionStore(dsn=_dsn_tagged("ra_concurrent"))
    barrier = threading.Barrier(workers, timeout=30)
    counts: list[int] = []
    failures: list[BaseException] = []

    def read() -> None:
        try:
            barrier.wait()
            counts.append(store.count())
        except BaseException as exc:  # noqa: BLE001 - recorded, then asserted on
            failures.append(exc)

    try:
        store.db.execute("TRUNCATE sessions")
        store.create("concurrent", finished_state())
        threads = [threading.Thread(target=read) for _ in range(workers)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=60)

        assert failures == [], f"concurrent reads raised: {failures}"
        assert counts == [1] * workers
    finally:
        store.close()
        db.close_all_pools()  # this test varies pool sizing; see above
