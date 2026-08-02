"""Session persistence. Uses real SQLite against a temp file -- the whole
point of this layer is that it survives a process, so faking it would test
nothing."""

import pytest

from research_agent.graph import followup_state, initial_state
from research_agent.sessions import SQLiteSessionStore


@pytest.fixture
def store(tmp_path):
    s = SQLiteSessionStore(str(tmp_path / "sessions.db"))
    yield s
    s.close()


def finished_run(task="why is the sky blue?"):
    state = initial_state(task)
    state.update(
        {
            "topic_type": "technical",
            "research_notes": "the notes",
            "draft": "the report",
            "reviewed": True,
            "approved": True,
            "iteration": 7,
        }
    )
    return state


def test_create_then_get_round_trips_the_whole_state(store):
    state = finished_run()
    session_id = store.create("why is the sky blue?", state)

    loaded = store.get(session_id)
    assert loaded.task == "why is the sky blue?"
    assert loaded.turns == 1
    assert loaded.state == state


def test_ids_are_unique(store):
    ids = {store.create("q", finished_run()) for _ in range(20)}
    assert len(ids) == 20


def test_get_unknown_session_returns_none(store):
    assert store.get("nope") is None


def test_state_survives_reopening_the_database(tmp_path):
    path = str(tmp_path / "sessions.db")
    first = SQLiteSessionStore(path)
    session_id = first.create("why is the sky blue?", finished_run())
    first.close()

    reopened = SQLiteSessionStore(path)
    try:
        assert reopened.get(session_id).state["draft"] == "the report"
    finally:
        reopened.close()


def test_append_turn_replaces_state_and_counts_the_turn(store):
    session_id = store.create("why is the sky blue?", finished_run())

    answer = followup_state(finished_run(), "and at sunset?")
    answer["draft"] = "the answer"
    store.append_turn(session_id, answer)

    loaded = store.get(session_id)
    assert loaded.turns == 2
    assert loaded.state["draft"] == "the answer"
    assert loaded.state["mode"] == "followup"
    # The original question stays the session's title; only state advances.
    assert loaded.task == "why is the sky blue?"


def test_append_turn_to_an_unknown_session_raises(store):
    with pytest.raises(KeyError):
        store.append_turn("nope", finished_run())


def test_sessions_are_listed_most_recently_updated_first(store):
    first = store.create("first", finished_run("first"))
    second = store.create("second", finished_run("second"))
    store.append_turn(first, finished_run("first"))  # bumps updated_at

    assert [s.id for s in store.list()] == [first, second]


def test_list_respects_its_limit(store):
    for n in range(5):
        store.create(f"q{n}", finished_run())
    assert len(store.list(limit=3)) == 3


def test_summary_omits_the_state_blob(store):
    """Listings are cheap and shouldn't ship every research note over the
    wire to render a title."""
    session_id = store.create("why is the sky blue?", finished_run())
    summary = store.get(session_id).summary()

    assert summary["session_id"] == session_id
    assert summary["approved"] is True
    assert summary["topic_type"] == "technical"
    assert "state" not in summary
    assert "the report" not in str(summary)


def test_delete_removes_the_session(store):
    session_id = store.create("q", finished_run())
    assert store.delete(session_id) is True
    assert store.get(session_id) is None
    assert store.count() == 0


def test_deleting_an_unknown_session_reports_that_it_did_nothing(store):
    assert store.delete("nope") is False


def test_count_tracks_sessions_not_turns(store):
    session_id = store.create("q", finished_run())
    store.append_turn(session_id, finished_run())
    assert store.count() == 1


def test_store_creates_its_parent_directory(tmp_path):
    """The container mounts a volume and points SESSION_DB_PATH into it;
    the directory may not exist on first boot."""
    path = tmp_path / "data" / "nested" / "sessions.db"
    s = SQLiteSessionStore(str(path))
    try:
        s.create("q", finished_run())
        assert path.exists()
    finally:
        s.close()


def test_concurrent_writes_do_not_lose_sessions(store):
    """FastAPI runs sync endpoints in a thread pool, so two runs really can
    finish at once."""
    import threading

    errors = []

    def write():
        try:
            for _ in range(10):
                store.create("q", finished_run())
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=write) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert store.count() == 40
