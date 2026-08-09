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
from datetime import date

import pytest
from test_memory_stores import FakeEmbedder

from research_agent import db, usage
from research_agent import recall_golden as golden
from research_agent.memory import PgVectorMemoryStore
from research_agent.metrics import RunRecord, SQLiteMetricsStore
from research_agent.migrate import main, migrate_notes, migrate_runs, migrate_sessions
from research_agent.sessions import SQLiteSessionStore

HAS_POSTGRES = db.postgres_configured()

# Never the contract suite's `contract_test_notes`: these tests insert rows
# with hand-picked owners and timestamps, and sharing a table with the
# behavioural suite would make each one's fixtures the other's noise.
LEGACY_NOTES_TABLE = "migration_test_notes_legacy"
COPY_SOURCE_TABLE = "migration_test_notes_old"
COPY_TARGET_TABLE = "migration_test_notes_new"
REEMBED_TARGET_TABLE = "migration_test_notes_reembed"
CUTOVER_TARGET_TABLE = "migration_test_notes_cutover"
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


# --------------------------------------------------------------------------
# `embeddings copy`: the same corpus, a new table, and provably the same recall
# --------------------------------------------------------------------------
#
# What makes this hard is what is NOT asserted here. The store searches through
# an HNSW index, which is approximate by design and whose build is not
# guaranteed deterministic, so "recall is byte-identical after the copy" cannot
# honestly be asked of the index -- it would be asking whether an approximation
# agreed with itself twice. The claim is decomposed instead:
#
#   test_copy_fidelity          the vectors are the same bytes (a SQL join)
#   test_copy_recall_identical  the golden queries agree, under EXACT SCAN
#   test_index_sanity           the indexed path agrees as a *set*, separately,
#                               and only at this corpus size
#
# Only the middle one is an equality-of-recall claim, and it never touches the
# index. See recall_golden.py's module docstring.


@pytest.fixture
def handle():
    conn = db.Database()
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def copy_tables(handle):
    """Dedicated old/new tables, dropped before and after (Pitfall 7).

    Dropped on setup as well as teardown: a killed previous run could have left
    a table of a different vector width behind, and the store's
    `CREATE TABLE IF NOT EXISTS` would then quietly keep the wrong one.
    """
    for table in (COPY_SOURCE_TABLE, COPY_TARGET_TABLE):
        handle.execute(f"DROP TABLE IF EXISTS {table}")
    try:
        yield COPY_SOURCE_TABLE, COPY_TARGET_TABLE
    finally:
        for table in (COPY_SOURCE_TABLE, COPY_TARGET_TABLE):
            handle.execute(f"DROP TABLE IF EXISTS {table}")


@pytest.fixture
def seeded(handle, copy_tables):
    """The golden corpus in the source table. Returns (old, new, embedder)."""
    source, target = copy_tables
    embedder = FakeEmbedder()
    golden.seed(handle, source, embedder, FAKE_DIMENSIONS)
    return source, target, embedder


def _owner_texts(owner):
    return {note["text"] for note in golden.GOLDEN_NOTES if note["owner"] == owner}


def _fingerprint(handle, table):
    """Every column that matters, as a comparable set -- embeddings included.

    A row count is green against a table whose contents were replaced, so the
    non-destructive assertions compare this instead.
    """
    return {
        (row["text"], row["owner"], row["created_at"], row["embedding"])
        for row in handle.fetchall(
            f"SELECT text, owner, created_at, embedding::text AS embedding FROM {table}"
        )
    }


@pytest.mark.skipif(not HAS_POSTGRES, reason="DATABASE_URL is not set")
def test_golden_set_tie_free_and_owner_scoped(handle, seeded):
    """The golden set is usable: uniquely ordered, and it can see tenancy.

    Tie-freedom is not a nicety. The production ORDER BY has no tiebreak, so
    two rows at the same distance come back in an arbitrary order and every
    ordered comparison built on them measures the query executor rather than
    the migration. Distinct vocabulary sets do not buy this -- similarity
    depends only on (overlap, size), so {chroma,retry} and {chroma,voyage} sit
    at exactly the same distance from "chroma".
    """
    source, _target, embedder = seeded

    golden.assert_tie_free(handle, source, embedder)

    # Owner isolation. "chroma retry" is stored under BOTH alice and bob, so a
    # copy or a query that lost `owner` merges their neighbourhoods.
    alice = golden.exact_scan_results(handle, source, embedder, "chroma retry", "alice", 3, 0.3)
    bob = golden.exact_scan_results(handle, source, embedder, "chroma retry", "bob", 3, 0.3)
    assert alice and bob
    assert alice != bob
    assert {text for text, _ in alice} <= _owner_texts("alice")
    assert {text for text, _ in bob} <= _owner_texts("bob")
    # The shared text is the only overlap; everything else is one owner's own.
    assert {t for t, _ in alice} & {t for t, _ in bob} == {"chroma retry"}

    # The unowned bucket sees only its own notes...
    unowned = golden.exact_scan_results(handle, source, embedder, "supervisor", "", 3, 0.3)
    assert unowned
    assert {text for text, _ in unowned} <= _owner_texts("")
    # ...and nothing at all for a query whose words nobody unowned ever used.
    assert golden.exact_scan_results(handle, source, embedder, "chroma retry", "", 3, 0.3) == []


@pytest.mark.skipif(not HAS_POSTGRES, reason="DATABASE_URL is not set")
def test_copy_fidelity(handle, seeded, capsys):
    """Same rows, same vectors, same key -- and the source never written to."""
    source, target, _embedder = seeded
    before = _fingerprint(handle, source)
    source_count = len(before)
    assert source_count == len(golden.GOLDEN_NOTES)

    assert main(["embeddings", "copy", "--from", source, "--to", target]) == 0

    counts = handle.fetchone(
        f"SELECT (SELECT count(*) FROM {source}) AS old_n, "
        f"(SELECT count(*) FROM {target}) AS new_n"
    )
    assert (counts["old_n"], counts["new_n"]) == (source_count, source_count)

    # The join that is the actual byte-identity claim. Keyed on
    # (text, owner, created_at) because `id` is BIGSERIAL and not copied.
    joined = handle.fetchone(
        f"SELECT count(*) AS n FROM {source} o "
        f"JOIN {target} n USING (text, owner, created_at)"
    )["n"]
    unmatched = handle.fetchone(
        f"SELECT count(*) AS n FROM {source} o "
        f"LEFT JOIN {target} n USING (text, owner, created_at) WHERE n.text IS NULL"
    )["n"]
    byte_diff = handle.fetchone(
        f"SELECT count(*) AS n FROM {source} o "
        f"JOIN {target} n USING (text, owner, created_at) "
        f"WHERE o.embedding::text IS DISTINCT FROM n.embedding::text"
    )["n"]
    assert unmatched == 0
    assert byte_diff == 0
    # Not implied by the two above: a duplicate key fans the join out, so every
    # number measured over it is measured over the wrong row set (RESEARCH A3).
    assert joined == source_count

    # Idempotent: the second run copies nothing and duplicates nothing.
    assert main(["embeddings", "copy", "--from", source, "--to", target]) == 0
    assert handle.fetchone(f"SELECT count(*) AS n FROM {target}")["n"] == source_count

    # Non-destructive, asserted rather than grepped for: a grep for the absence
    # of DROP is green against a command that DELETEs, TRUNCATEs or UPDATEs.
    # This compares the source's full contents, embeddings included.
    assert _fingerprint(handle, source) == before

    capsys.readouterr()
    assert main(["embeddings", "copy", "--from", source, "--to", target, "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "DRY RUN — nothing will be written" in out
    assert "to copy    0 row(s)" in out
    assert _fingerprint(handle, source) == before
    assert handle.fetchone(f"SELECT count(*) AS n FROM {target}")["n"] == source_count


@pytest.mark.skipif(not HAS_POSTGRES, reason="DATABASE_URL is not set")
def test_copy_recall_identical(handle, seeded):
    """SC-5's copy half: zero golden delta, measured with the index turned off.

    Ordered and score-bearing, because a migration that returned the same notes
    in a different order, or at different similarities, has changed recall.
    """
    source, target, embedder = seeded
    assert main(["embeddings", "copy", "--from", source, "--to", target]) == 0

    old = golden.run_golden(handle, source, embedder)
    new = golden.run_golden(handle, target, embedder)

    # Anti-vacuity: two empty result sets are also "identical". The golden set
    # deliberately contains one query that must return nothing, so this asserts
    # that the others return something before the comparison is trusted.
    answered = [key for key, rows in old.items() if rows]
    assert len(answered) >= len(golden.GOLDEN_QUERIES) - 1
    assert sum(len(rows) for rows in old.values()) >= 12

    assert golden.recall_delta(old, new) == []


class DriftingEmbedder:
    """A fake whose answer to the same query text moves a little every call.

    Standing in for a real embedding API. Every local gate in this phase used a
    bit-deterministic fake, so nothing had ever asked what happens when the
    query side is not stable -- and on 2026-08-09 the live run found out: the
    Supabase source table compared with ITSELF deltaed on 2 of the 8 golden
    queries, same notes, same order, similarities differing in the fourth
    decimal, because `run_golden` embeds each query once per table.

    Documents are delegated unperturbed: a corpus is written once, and it is
    the repeated question, not the stored answer, that drifts. The nudge is
    uniform across components so it moves similarities without reordering
    anything -- which is precisely how the live artefact presented, and is what
    makes it so easy to mistake for a migration having done something.
    """

    def __init__(self, inner=None):
        self.inner = inner if inner is not None else FakeEmbedder()
        self.query_calls = 0

    def embed_documents(self, texts):
        return self.inner.embed_documents(texts)

    def embed_query(self, text):
        self.query_calls += 1
        nudge = 1e-4 * self.query_calls
        return [value + nudge for value in self.inner.embed_query(text)]


@pytest.mark.skipif(not HAS_POSTGRES, reason="DATABASE_URL is not set")
def test_frozen_query_embedder_isolates_the_table(handle, seeded):
    """The query vector is a variable too, and `FrozenQueryEmbedder` pins it.

    `recall_delta(run_golden(old), run_golden(new))` is sold as a comparison of
    two tables. It embeds each golden query twice -- once per run -- so with an
    embedder that is not bit-reproducible it is a comparison of two tables AND
    two query vectors. The control below is a table against ITSELF: any delta
    there is definitionally not the migration.
    """
    source, target, _embedder = seeded
    assert main(["embeddings", "copy", "--from", source, "--to", target]) == 0

    drifting = DriftingEmbedder()
    first = golden.run_golden(handle, source, drifting)
    second = golden.run_golden(handle, source, drifting)

    # Anti-vacuity before anything is concluded: two empty result sets differ
    # from nothing and agree with nothing.
    answered = [key for key, rows in first.items() if rows]
    assert len(answered) >= len(golden.GOLDEN_QUERIES) - 1
    assert sum(len(rows) for rows in first.values()) >= 12

    self_delta = golden.recall_delta(first, second)
    assert self_delta != [], "the control must be dirty, or it is not a control"
    # And it is the scores that moved, not the notes -- measurement noise
    # wearing a migration's clothes, which is why it is worth a named guard.
    for entry in self_delta:
        assert [text for text, _ in entry["old"]] == [text for text, _ in entry["new"]]

    # Frozen, the same embedder answers the same question the same way, so a
    # table compares equal to itself...
    frozen = golden.FrozenQueryEmbedder(DriftingEmbedder())
    assert (
        golden.recall_delta(
            golden.run_golden(handle, source, frozen),
            golden.run_golden(handle, source, frozen),
        )
        == []
    )
    # ...and the copy's zero-delta claim is about the copy, not about luck.
    assert (
        golden.recall_delta(
            golden.run_golden(handle, source, frozen),
            golden.run_golden(handle, target, frozen),
        )
        == []
    )
    # One embed per distinct query text -- not one per query, per table, per run.
    assert frozen.calls == len({spec["query"] for spec in golden.GOLDEN_QUERIES})


@pytest.mark.skipif(not HAS_POSTGRES, reason="DATABASE_URL is not set")
def test_index_sanity(handle, seeded):
    """The indexed path agrees with the exact scan -- as a SET, at this size.

    Deliberately weaker than the test above and deliberately in its own test.
    HNSW is approximate: pgvector's README says it can miss results, and
    `hnsw.ef_search` defaults to 40. This corpus is a dozen rows, far below
    that, so the search effectively explores everything and set-equality is
    what should be expected. It is NOT a general ANN guarantee, it does not
    scale, and it must never be promoted into the equality-of-recall claim --
    which is exactly why the assertion is on sets rather than on order.
    """
    source, target, embedder = seeded
    assert main(["embeddings", "copy", "--from", source, "--to", target]) == 0

    exact = golden.run_golden(handle, target, embedder)
    indexed = golden.run_golden(handle, target, embedder, runner=golden.indexed_results)
    assert set(indexed) == set(exact)
    for key, rows in exact.items():
        assert set(indexed[key]) == set(rows), key


# --------------------------------------------------------------------------
# Voyage pricing: the arithmetic behind the cost preview
# --------------------------------------------------------------------------
#
# No Postgres and no network, on purpose. `preview_cost_usd` takes a token
# count rather than producing one, because Voyage's own `count_tokens` fetches
# a tokenizer from the Hugging Face hub on its first call -- a cost function
# that needed a network round trip to perform one multiplication would be
# untestable offline for no benefit. The counting is injected at the CLI seam
# instead, and tested there with a fake.


def test_voyage_pricing_arithmetic():
    """The published rates, as arithmetic anyone can check by hand."""
    # 0.06 USD per million tokens, so a million tokens is six cents.
    assert usage.preview_cost_usd(1_000_000, "voyage-3.5") == pytest.approx(0.06)
    # Half a million of the lite model at 0.02/Mtok is one cent.
    assert usage.preview_cost_usd(500_000, "voyage-3.5-lite") == pytest.approx(0.01)
    assert usage.voyage_price_for("voyage-3-large") == pytest.approx(0.18)
    # Rates are per million, so the function must be linear in the token count
    # rather than, say, quietly rounding to cents somewhere.
    assert usage.preview_cost_usd(2_500_000, "voyage-3.5") == pytest.approx(0.15)


def test_voyage_pricing_unknown_model_fails_loud():
    """An unpriced model raises. It is never quoted at $0.00.

    DEC-12: pricing that fails loud. This matters more here than anywhere else
    in the service -- everywhere else a missing rate under-reports a cost that
    has already been paid, but a re-embed preview is a number an operator
    decides to spend money on. A silent zero would be an argument for
    proceeding.
    """
    with pytest.raises(usage.UnknownModelPricing) as excinfo:
        usage.voyage_price_for("voyage-99")
    assert "voyage-99" in str(excinfo.value)

    # And the arithmetic wrapper does not swallow it into a free run.
    with pytest.raises(usage.UnknownModelPricing):
        usage.preview_cost_usd(10_000_000, "voyage-99")


def test_preview_cost_stays_list_price_under_non_neutral_env(monkeypatch):
    """The preview says it quotes list price, so it has to keep doing that.

    The cost multipliers are an Anthropic dimension: a negotiated Anthropic
    discount and a data-residency rate published against Claude models. Voyage
    is a different vendor with a different rate card and never offered either.
    Letting them leak in here would put a number in front of an operator who is
    about to spend money, and that number would be lower than the bill.
    """
    monkeypatch.setenv("COST_DISCOUNT_FACTOR", "0.5")
    monkeypatch.setenv("INFERENCE_GEO_MULTIPLIER", "2.0")

    assert usage.preview_cost_usd(
        1_000_000, "voyage-3.5", date(2026, 8, 9)
    ) == pytest.approx(0.06)


# --------------------------------------------------------------------------
# `embeddings re-embed`: new model, new width, same tenancy, gated spend
# --------------------------------------------------------------------------
#
# Nothing below touches the network. The real embedder bills and the real token
# counter downloads a tokenizer on first use, so both are injected through
# `main(..., token_counter=, embedder_factory=)` -- which is also what makes
# "this invocation embedded nothing" an assertion about a counter rather than a
# claim about code someone read.


class NarrowFakeEmbedder(FakeEmbedder):
    """The same deterministic bag-of-words, one vocabulary word narrower.

    Standing in for a model change: same texts, a different width, and
    therefore different vectors -- which is the whole observable difference
    between this command and `copy`.
    """

    VOCAB = FakeEmbedder.VOCAB[:4]


NARROW_DIMENSIONS = len(NarrowFakeEmbedder.VOCAB)


class RecordingEmbedder:
    """A fake that counts what it was asked to embed.

    The spend gate's claim is "zero embed calls", and the only way to assert
    that honestly is to hand the command something that would notice.
    """

    def __init__(self, inner=None):
        self.inner = inner if inner is not None else NarrowFakeEmbedder()
        self.embed_calls = 0
        self.texts_embedded = 0

    def embed_documents(self, texts):
        self.embed_calls += 1
        self.texts_embedded += len(texts)
        return self.inner.embed_documents(texts)

    def embed_query(self, text):
        return self.inner.embed_query(text)


def _word_counter(texts, model):
    """A stand-in for Voyage's tokenizer: deterministic, local, and free."""
    return sum(len(text.split()) for text in texts)


@pytest.fixture
def reembed_tables(handle):
    """Source and re-embed target, dropped before and after (Pitfall 7)."""
    for table in (COPY_SOURCE_TABLE, REEMBED_TARGET_TABLE):
        handle.execute(f"DROP TABLE IF EXISTS {table}")
    try:
        yield COPY_SOURCE_TABLE, REEMBED_TARGET_TABLE
    finally:
        for table in (COPY_SOURCE_TABLE, REEMBED_TARGET_TABLE):
            handle.execute(f"DROP TABLE IF EXISTS {table}")


@pytest.fixture
def reembed_seeded(handle, reembed_tables):
    """The golden corpus at the old width. Returns (source, target)."""
    source, target = reembed_tables
    golden.seed(handle, source, FakeEmbedder(), FAKE_DIMENSIONS)
    return source, target


def _epoch_triples(handle, table):
    return sorted(
        (row["text"], row["owner"], float(row["created_at"]))
        for row in handle.fetchall(
            f"SELECT text, owner, extract(epoch FROM created_at) AS created_at FROM {table}"
        )
    )


def _reembed(
    source,
    target,
    recorder,
    dimensions=NARROW_DIMENSIONS,
    extra=("--yes",),
    model="voyage-3.5",
):
    return main(
        [
            "embeddings",
            "re-embed",
            "--from",
            source,
            "--to",
            target,
            "--model",
            model,
            "--dimensions",
            str(dimensions),
            *extra,
        ],
        token_counter=_word_counter,
        embedder_factory=lambda model, output_dimension: recorder,
    )


@pytest.mark.skipif(not HAS_POSTGRES, reason="DATABASE_URL is not set")
def test_reembed_carries_tenancy(handle, reembed_seeded):
    """New vectors at a new width, and every row still owned by whoever wrote it.

    A re-embed that dropped `owner` would merge alice's and bob's memories into
    one bucket -- the same cross-tenant failure the legacy tool shipped with for
    two phases. One that dropped `created_at` would hand every migrated note a
    fresh 7-day TTL and break the key that makes this re-runnable.
    """
    source, target = reembed_seeded
    recorder = RecordingEmbedder()

    assert _reembed(source, target, recorder) == 0
    assert recorder.texts_embedded == len(golden.GOLDEN_NOTES)

    # The width really moved: this is a model change, not a copy.
    width = handle.fetchone(f"SELECT vector_dims(embedding) AS d FROM {target} LIMIT 1")["d"]
    assert width == NARROW_DIMENSIONS
    assert width != FAKE_DIMENSIONS

    assert handle.fetchone(f"SELECT count(*) AS n FROM {target}")["n"] == len(golden.GOLDEN_NOTES)

    # Anti-vacuity before the comparison: three distinct owners are in play, so
    # "the triples match" is not two empty lists agreeing.
    owners = {row["owner"] for row in handle.fetchall(f"SELECT owner FROM {target}")}
    assert owners == {"alice", "bob", ""}

    # Per-row (text, owner, created_at) equality -- not a count, which is green
    # against a table where every row landed on the wrong owner.
    assert _epoch_triples(handle, target) == _epoch_triples(handle, source)

    # Re-runnable, and asserted on the SECOND pass because that is the only
    # pass where the resume key applies: a first run into an empty table writes
    # everything whatever the key is (13-01's lesson, 13-02's mutation M6).
    assert _reembed(source, target, recorder) == 0
    assert recorder.texts_embedded == len(golden.GOLDEN_NOTES)  # nothing re-embedded
    assert handle.fetchone(f"SELECT count(*) AS n FROM {target}")["n"] == len(golden.GOLDEN_NOTES)


@pytest.mark.skipif(not HAS_POSTGRES, reason="DATABASE_URL is not set")
def test_dimension_check_still_loud_in_migration_path(handle, reembed_seeded):
    """SC-4: the store's own check fires here too, and nothing is coerced.

    The message is asserted rather than the exception type, and asserted on
    the store's exact wording, because the claim is that *the store's* check
    ran -- a private width comparison in migrate.py would raise a ValueError
    too, and would be free to drift from the one production uses.
    """
    source, target = reembed_seeded
    wrong_width = RecordingEmbedder(inner=FakeEmbedder())  # 5 dimensions, into a 4 table

    with pytest.raises(ValueError) as excinfo:
        _reembed(source, target, wrong_width)

    message = str(excinfo.value)
    assert "dimensions but the" in message
    assert "column is vector(" in message
    # It refused rather than truncating, padding, or widening the column.
    assert wrong_width.embed_calls == 1
    assert handle.fetchone(f"SELECT count(*) AS n FROM {target}")["n"] == 0


# --------------------------------------------------------------------------
# The spend gate: preview always, --yes required, loud refusals
# --------------------------------------------------------------------------
#
# Every assertion below about "nothing was spent" is a count on the injected
# embedder, never an inspection of the code. The gate is only worth having if
# it is falsifiable, and "no call reached embed_documents" is the falsifiable
# form of it.


def _exists(handle, table):
    return handle.fetchone("SELECT to_regclass(%s) AS oid", (table,))["oid"] is not None


@pytest.mark.skipif(not HAS_POSTGRES, reason="DATABASE_URL is not set")
def test_preview_requires_yes(handle, reembed_seeded, capsys):
    """The preview prints, and then the command refuses to spend without --yes.

    Both halves matter. An operator who is refused but shown nothing has no
    way to decide; an operator who is shown a number and then charged for it
    without asking has been billed by a preview.
    """
    source, target = reembed_seeded
    recorder = RecordingEmbedder()

    rc = _reembed(source, target, recorder, extra=())
    out = capsys.readouterr()

    assert rc != 0
    # The preview is present, with the two numbers a spending decision needs.
    assert "cost preview" in out.out
    assert "token(s)" in out.out
    assert "$" in out.out
    assert "--yes is required" in out.err
    # And nothing was spent, asserted on the fake rather than on the source.
    assert recorder.embed_calls == 0
    assert recorder.texts_embedded == 0
    # The target was never even created, so no DDL ran either.
    assert not _exists(handle, target)


@pytest.mark.skipif(not HAS_POSTGRES, reason="DATABASE_URL is not set")
def test_preview_prints_before_spend_with_yes(handle, reembed_seeded, capsys):
    """With --yes the preview still prints -- and prints first."""
    source, target = reembed_seeded
    recorder = RecordingEmbedder()

    assert _reembed(source, target, recorder) == 0
    out = capsys.readouterr().out

    assert "cost preview" in out
    assert recorder.texts_embedded == len(golden.GOLDEN_NOTES)
    assert handle.fetchone(f"SELECT count(*) AS n FROM {target}")["n"] == len(golden.GOLDEN_NOTES)
    # Ordering is the claim: a cost shown after the money is spent is a
    # receipt, not a preview.
    assert out.index("cost preview") < out.index("embedded ")


class ZeroTokenEmbedder(RecordingEmbedder):
    """An embedder that DID report its token count, and the count was zero.

    Not a hypothetical. Measured against the live API on 2026-08-09, Voyage's
    `response.total_tokens` came back as 0 for a one-word document it had just
    embedded successfully -- which is also the evidence that the field is not
    an invoice. A truthiness test on that number reads "0" as "this embedder
    does not report tokens" and prints the sentence for the wrong case.
    """

    total_tokens = 0


@pytest.mark.skipif(not HAS_POSTGRES, reason="DATABASE_URL is not set")
def test_zero_reported_tokens_is_a_receipt_not_a_silence(handle, reembed_seeded, capsys):
    """0 reported tokens is a report of zero, not an absence of a report."""
    source, target = reembed_seeded
    recorder = ZeroTokenEmbedder()

    assert _reembed(source, target, recorder) == 0
    out = capsys.readouterr().out

    # Anti-vacuity: the run has to have got as far as the reconciliation block.
    assert recorder.texts_embedded == len(golden.GOLDEN_NOTES)
    assert "reported     0 token(s)" in out
    assert "not reported by this embedder" not in out


@pytest.mark.skipif(not HAS_POSTGRES, reason="DATABASE_URL is not set")
def test_dry_run_never_embeds(handle, reembed_seeded, capsys):
    """--dry-run wins over --yes: contradictory flags resolve to spending nothing."""
    source, target = reembed_seeded
    recorder = RecordingEmbedder()

    assert _reembed(source, target, recorder, extra=("--dry-run", "--yes")) == 0
    out = capsys.readouterr().out

    assert "cost preview" in out
    assert "DRY RUN" in out
    assert recorder.embed_calls == 0
    assert not _exists(handle, target)


@pytest.mark.skipif(not HAS_POSTGRES, reason="DATABASE_URL is not set")
def test_dimension_ceiling(handle, reembed_seeded, capsys):
    """2048 is a real Voyage width and an unindexable pgvector table.

    Refused before any DDL, so the failure is a sentence rather than a table
    that exists and can never be indexed.
    """
    source, target = reembed_seeded
    recorder = RecordingEmbedder()

    rc = _reembed(source, target, recorder, dimensions=2048)
    err = capsys.readouterr().err

    assert rc != 0
    assert "2000" in err
    assert "halfvec" in err
    assert recorder.embed_calls == 0
    assert not _exists(handle, target)


@pytest.mark.skipif(not HAS_POSTGRES, reason="DATABASE_URL is not set")
def test_reembed_unknown_model_refuses(handle, reembed_seeded, capsys):
    """DEC-12: an unpriced model stops the run rather than costing $0.00.

    Note the --yes: this is the invocation that was authorised to spend, and
    it still refuses, because the authorisation was given against a price that
    does not exist.
    """
    source, target = reembed_seeded
    recorder = RecordingEmbedder()

    rc = _reembed(source, target, recorder, model="voyage-99")
    err = capsys.readouterr().err

    assert rc != 0
    assert "voyage-99" in err
    assert "0.00" not in err  # not quoted a price; refused one
    assert recorder.embed_calls == 0
    assert not _exists(handle, target)


# --------------------------------------------------------------------------
# Cutover: the flip is the whole thing, and it goes both ways
# --------------------------------------------------------------------------
#
# SC-3 claims the cutover is explicit and reversible: point the config at the
# new table, restart, and if it was a mistake point it back. In production that
# act is `fly secrets set PGVECTOR_TABLE=<new>` (plus `VECTOR_DIMENSIONS=<N>`
# after a re-embed, since the width moves with the model) followed by a
# restart. `PGVECTOR_TABLE` is read ONCE, at import (memory.py:58), into a
# module constant that becomes `PgVectorMemoryStore.__init__`'s default for
# `table=`. So the env var and the constructor parameter are the same seam,
# entered at different ends, and the constructor is the end a test can hold:
# setting the variable and reimporting the module would leave a second
# `memory` module object alive for the rest of the session and change what
# every other test in the process is talking to (Pitfall 5). What is therefore
# NOT proven here is the process restart itself -- only that both tables serve
# the same corpus and that pointing at either one is a complete, non-destructive
# switch.


@pytest.fixture
def cutover_tables(handle):
    """The live table and the cutover target, dropped before and after."""
    for table in (COPY_SOURCE_TABLE, CUTOVER_TARGET_TABLE):
        handle.execute(f"DROP TABLE IF EXISTS {table}")
    try:
        yield COPY_SOURCE_TABLE, CUTOVER_TARGET_TABLE
    finally:
        for table in (COPY_SOURCE_TABLE, CUTOVER_TARGET_TABLE):
            handle.execute(f"DROP TABLE IF EXISTS {table}")


def _golden_texts_via_store(table, embedder):
    """Every golden query answered by the production store pointed at `table`.

    Its own `db.Database` per construction: a `Database` applies at most one
    schema block in its lifetime, so a shared handle would silently skip the
    store's `ensure_schema` and this would stop being the production path.

    `PgVectorMemoryStore.query()` returns `list[str]` (memory.py:546), not the
    `(text, similarity)` pairs the exact-scan runner produces -- hence the
    texts-only projection on the expected side at the call sites below.
    """
    store = PgVectorMemoryStore(
        table=table,
        dimensions=FAKE_DIMENSIONS,
        embedder=embedder,
        database=db.Database(),
    )
    try:
        return {
            golden.query_key(spec): store.query(
                spec["query"],
                top_k=spec["top_k"],
                min_similarity=spec["min_similarity"],
                owner=spec["owner"],
            )
            for spec in golden.GOLDEN_QUERIES
        }
    finally:
        store.close()


@pytest.mark.skipif(not HAS_POSTGRES, reason="DATABASE_URL is not set")
def test_cutover_reversible(handle, cutover_tables):
    """SC-3: flip forward, flip back, and the old table is untouched throughout.

    Read the comparison carefully, because it proves slightly less than it
    looks like it proves. The expected results come from `exact_scan_results`,
    which turns the index off; `store.query()` is the *indexed* production
    path. So this is an indexed-vs-exact equality, and it is only reasonable
    to demand under exactly the argument `test_index_sanity` makes: this corpus
    is a dozen rows against `hnsw.ef_search = 40`, so the search effectively
    explores everything, and the golden set is tie-free so the order is not the
    executor's choice. At a corpus size where HNSW is doing real approximation
    neither would hold, and this equality would have to weaken to a set
    comparison the way `test_index_sanity`'s does. It is written as an ordered
    equality here because at this size the stronger claim is the true one -- but
    it is a claim about the cutover, not a general ANN guarantee.
    """
    old, new = cutover_tables
    embedder = FakeEmbedder()
    golden.seed(handle, old, embedder, FAKE_DIMENSIONS)

    # Ordered comparison over a tie-bearing corpus measures the query executor,
    # not the cutover. Asserted here rather than assumed from 13-02's test.
    golden.assert_tie_free(handle, old, embedder)

    # The old table's full contents -- embeddings included -- as they stood
    # before anything happened. Every step below re-compares against this, so
    # "the old table survives" is asserted four times rather than once at the
    # end, where a step that dropped and recreated it would still pass.
    before = _fingerprint(handle, old)
    old_count = len(before)
    assert old_count == len(golden.GOLDEN_NOTES)

    expected = {
        key: [text for text, _similarity in rows]
        for key, rows in golden.run_golden(handle, old, embedder).items()
    }
    # Anti-vacuity: two empty result sets are also equal, and the golden set
    # deliberately contains one query that must return nothing.
    assert len([key for key, texts in expected.items() if texts]) >= len(golden.GOLDEN_QUERIES) - 1
    assert sum(len(texts) for texts in expected.values()) >= 12

    assert main(["embeddings", "copy", "--from", old, "--to", new]) == 0
    assert _fingerprint(handle, old) == before

    # Flip forward. The store is constructed against the new table exactly as
    # a restarted process with PGVECTOR_TABLE=<new> would construct it.
    assert _golden_texts_via_store(new, embedder) == expected
    assert _fingerprint(handle, old) == before

    # Flip back -- rollback is pointing back, and nothing else. The store runs
    # the same idempotent ensure_schema production runs at startup against a
    # table that already exists; the fingerprint below is what says that
    # touched no data.
    assert _golden_texts_via_store(old, embedder) == expected
    assert _fingerprint(handle, old) == before

    # And the new table is still there afterwards, so a second flip forward
    # needs no second migration: both tables coexist and the config chooses.
    assert handle.fetchone(f"SELECT count(*) AS n FROM {new}")["n"] == old_count
