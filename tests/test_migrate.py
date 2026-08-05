"""The legacy SQLite/JSON -> Postgres migration, exercised for the first time.

`research_agent.migrate` shipped in Phase 9 and was never covered by a test.
It then survived two phases that changed the database underneath it: Phase 11
repooled every connection and Phase 12 added `owner` to both schemas. The tool
kept importing and kept running, which is exactly why nobody noticed that it
had stopped carrying half the columns.

These tests need a real Postgres (the same one the store contract uses) and
skip without one. They write to a dedicated notes table and to uuid-keyed
session rows so a parallel run cannot collide with anything, and they drop
what they created.
"""

import json
import sqlite3
import time
import uuid

import pytest
from test_memory_stores import FakeEmbedder

from research_agent import db
from research_agent.metrics import RunRecord, SQLiteMetricsStore
from research_agent.migrate import main, migrate_notes, migrate_runs, migrate_sessions
from research_agent.sessions import SQLiteSessionStore

HAS_POSTGRES = db.postgres_configured()

# Never the contract suite's `contract_test_notes`: these tests insert rows
# with hand-picked owners and timestamps, and sharing a table with the
# behavioural suite would make each one's fixtures the other's noise.
LEGACY_NOTES_TABLE = "migration_test_notes_legacy"
FAKE_DIMENSIONS = len(FakeEmbedder.VOCAB)

# Fixed, distinct, and nonzero: an assertion that the migrated created_at is
# the *source's* is only meaningful if the source value could not plausibly be
# now(). These are hours apart and in the past.
_NOW = time.time()
NOTE_ENTRIES = [
    {"text": "chroma retry", "owner": "alice", "created_at": _NOW - 3600.0},
    # Same text, different owner: two legitimate rows under Phase 12 scoping,
    # and the row a text-only dedup key would silently drop.
    {"text": "chroma retry", "owner": "bob", "created_at": _NOW - 7200.0},
    {"text": "voyage supervisor", "owner": "alice", "created_at": _NOW - 10800.0},
    {"text": "langgraph", "owner": "", "created_at": _NOW - 14400.0},
]


@pytest.fixture
def notes_json(tmp_path):
    """A JSON note store in the shape `JSONMemoryStore` writes."""
    embedder = FakeEmbedder()
    entries = [
        {**entry, "embedding": embedder.embed_documents([entry["text"]])[0]}
        for entry in NOTE_ENTRIES
    ]
    path = tmp_path / "agent_memory_store.json"
    path.write_text(json.dumps(entries))
    return str(path)


@pytest.fixture
def legacy_table():
    """A clean 5-dimensional notes table, dropped again afterwards.

    Dropped rather than truncated on setup too: a previous run of this file
    could have left a table of a different width behind, and `CREATE TABLE IF
    NOT EXISTS` would then quietly keep the wrong one.
    """
    handle = db.Database()
    handle.execute(f"DROP TABLE IF EXISTS {LEGACY_NOTES_TABLE}")
    try:
        yield LEGACY_NOTES_TABLE
    finally:
        handle.execute(f"DROP TABLE IF EXISTS {LEGACY_NOTES_TABLE}")
        handle.close()


def _migrated_notes(table):
    handle = db.Database()
    try:
        # extract(epoch ...) comes back as a Decimal; float() here so the
        # assertions read as ordinary numeric comparisons.
        return [
            {**row, "created_at": float(row["created_at"])}
            for row in handle.fetchall(
                f"SELECT text, owner, extract(epoch FROM created_at) AS created_at "
                f"FROM {table} ORDER BY owner, text"
            )
        ]
    finally:
        handle.close()


@pytest.mark.skipif(not HAS_POSTGRES, reason="DATABASE_URL is not set")
def test_migrate_preserves_owner_and_created_at(notes_json, legacy_table):
    """Every note arrives owned by whoever wrote it, with its original clock.

    The bug this pins was live: inserting only `(text, embedding)` let the
    column defaults fill in `owner=''` -- which matches no caller, since a real
    identity is a 32-hex uuid -- and `created_at=now()`, restarting the 7-day
    TTL on data that was already most of the way through it.
    """
    copied, skipped = migrate_notes(
        notes_json, dry_run=False, table=legacy_table, dimensions=FAKE_DIMENSIONS
    )
    assert (copied, skipped) == (len(NOTE_ENTRIES), 0)

    rows = _migrated_notes(legacy_table)
    assert len(rows) == len(NOTE_ENTRIES)

    # Asserted before the per-row comparison because it is the failure mode by
    # name: nothing is orphaned beyond the one entry that arrived unowned.
    orphaned = [r for r in rows if r["owner"] == ""]
    assert len(orphaned) == 1, f"{len(orphaned)} notes migrated to owner='' (belonging to nobody)"
    assert orphaned[0]["text"] == "langgraph"

    # And nothing was stamped now(): the newest migrated note is an hour old.
    assert max(r["created_at"] for r in rows) < time.time() - 60

    # Per-row field equality, not a row count: a count is green even when
    # every row landed on the wrong owner at the wrong time.
    expected = sorted(
        ((e["owner"], e["text"], e["created_at"]) for e in NOTE_ENTRIES),
        key=lambda t: (t[0], t[1]),
    )
    actual = [(r["owner"], r["text"], r["created_at"]) for r in rows]
    for (exp_owner, exp_text, exp_epoch), (got_owner, got_text, got_epoch) in zip(
        expected, actual, strict=True
    ):
        assert got_owner == exp_owner
        assert got_text == exp_text
        assert got_epoch == pytest.approx(exp_epoch, abs=1e-3)

    # Owner-aware dedup: the same text under two owners is two rows.
    same_text = [r for r in rows if r["text"] == "chroma retry"]
    assert {r["owner"] for r in same_text} == {"alice", "bob"}

    # That last assertion is necessary but not sufficient, and being explicit
    # about why: on a first pass into an empty table the dedup set is empty, so
    # a text-only key inserts both rows too and the assertion above is green
    # against a broken key. The key only bites on a re-run. So: delete bob's
    # copy and migrate again. Owner-aware, exactly that row returns; keyed on
    # text alone, alice's identical text is "already present" and bob's note is
    # skipped forever -- one owner's data made permanently unrecoverable by
    # another owner having written the same sentence.
    handle = db.Database()
    try:
        handle.execute(f"DELETE FROM {legacy_table} WHERE owner = 'bob'")
        assert migrate_notes(
            notes_json, dry_run=False, table=legacy_table, dimensions=FAKE_DIMENSIONS
        ) == (1, len(NOTE_ENTRIES) - 1)
        restored = handle.fetchone(
            f"SELECT text FROM {legacy_table} WHERE owner = 'bob'"
        )
        assert restored is not None and restored["text"] == "chroma retry"
    finally:
        handle.close()


@pytest.mark.skipif(not HAS_POSTGRES, reason="DATABASE_URL is not set")
def test_migrate_legacy_roundtrip(tmp_path, notes_json, legacy_table, capsys):
    """SQLite + JSON in, Postgres out, with the fields intact and re-runnable."""
    sessions_db = str(tmp_path / "sessions.db")
    metrics_db = str(tmp_path / "metrics.db")

    # uuid ids: the sessions table is shared with every other Postgres-gated
    # test and with any parallel CI job, so these rows must be unmistakably
    # ours to assert on and to delete.
    live_ids = [uuid.uuid4().hex, uuid.uuid4().hex]
    expired_id = uuid.uuid4().hex
    run_id = f"migrate-roundtrip-{uuid.uuid4().hex}"

    source = SQLiteSessionStore(sessions_db)
    source.create("why does chroma retry?", {"answer": "a"}, session_id=live_ids[0], owner="alice")
    source.create("what does voyage cost?", {"answer": "b"}, session_id=live_ids[1], owner="bob")
    # A second turn on one of them, so `turns` carries something other than
    # the value create() would have stamped by itself.
    source.append_turn(live_ids[0], {"answer": "a2"})
    source.create("ancient question", {"answer": "c"}, session_id=expired_id, owner="alice")
    expected_sessions = {s.id: s for s in source.list(limit=100)}
    source.close()

    # Age the third session past the TTL by writing the sqlite file directly:
    # going through the store would sweep it instead.
    conn = sqlite3.connect(sessions_db)
    conn.execute(
        "UPDATE sessions SET updated_at = ?, created_at = ? WHERE id = ?",
        (time.time() - 90 * 86400, time.time() - 90 * 86400, expired_id),
    )
    conn.commit()
    conn.close()

    metrics = SQLiteMetricsStore(metrics_db)
    metrics.record(RunRecord(run_id=run_id, mode="deep", status="completed", cost_usd=0.42))
    metrics.close()

    handle = db.Database()
    try:
        # The same three calls main() makes, in the same order -- explicit
        # here only because the notes table is 5-dimensional and main() reads
        # VECTOR_DIMENSIONS at import.
        assert migrate_sessions(sessions_db, dry_run=False) == (2, 0)
        assert migrate_runs(metrics_db, dry_run=False) == (1, 0)
        assert migrate_notes(
            notes_json, dry_run=False, table=legacy_table, dimensions=FAKE_DIMENSIONS
        ) == (len(NOTE_ENTRIES), 0)

        # The expired session is not resurrected -- and says so.
        assert "1 expired session(s) not migrated" in capsys.readouterr().out
        assert handle.fetchone("SELECT id FROM sessions WHERE id = %s", (expired_id,)) is None

        for session_id in live_ids:
            expected = expected_sessions[session_id]
            row = handle.fetchone(
                "SELECT owner, created_at, updated_at, turns, task FROM sessions WHERE id = %s",
                (session_id,),
            )
            assert row is not None
            assert row["owner"] == expected.owner
            assert row["created_at"] == pytest.approx(expected.created_at, abs=1e-6)
            assert row["updated_at"] == pytest.approx(expected.updated_at, abs=1e-6)
            assert row["turns"] == expected.turns
            assert row["task"] == expected.task
        assert expected_sessions[live_ids[0]].turns == 2  # the append_turn above

        row = handle.fetchone("SELECT cost_usd FROM runs WHERE run_id = %s", (run_id,))
        assert row is not None and float(row["cost_usd"]) == pytest.approx(0.42)

        notes_count = handle.fetchone(f"SELECT count(*) AS n FROM {legacy_table}")["n"]
        assert notes_count == len(NOTE_ENTRIES)

        # Re-runnable: a second pass copies nothing and duplicates nothing.
        assert migrate_sessions(sessions_db, dry_run=False) == (0, 2)
        assert migrate_runs(metrics_db, dry_run=False) == (0, 1)
        assert migrate_notes(
            notes_json, dry_run=False, table=legacy_table, dimensions=FAKE_DIMENSIONS
        ) == (0, len(NOTE_ENTRIES))
        assert handle.fetchone(f"SELECT count(*) AS n FROM {legacy_table}")["n"] == notes_count

        # The documented bare invocation still works. --notes points nowhere on
        # purpose: main() reads the production VECTOR_DIMENSIONS, and this
        # assertion is about the CLI surface, not the vector width.
        capsys.readouterr()
        rc = main(
            [
                "--dry-run",
                "--sessions-db",
                sessions_db,
                "--metrics-db",
                metrics_db,
                "--notes",
                str(tmp_path / "no-such-notes.json"),
            ]
        )
        out = capsys.readouterr().out
        assert rc == 0
        assert "DRY RUN — nothing will be written" in out
        assert "1 expired session(s) not migrated" in out
    finally:
        handle.execute(
            "DELETE FROM sessions WHERE id = ANY(%s)", (live_ids + [expired_id],)
        )
        handle.execute("DELETE FROM runs WHERE run_id = %s", (run_id,))
        handle.close()
