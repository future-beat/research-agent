#!/usr/bin/env python3
"""
Copy an existing SQLite/JSON deployment into Postgres.

Switching backends does not move data -- each store owns its own. If you have
already been running on a volume, this carries the sessions, the run history,
and the accumulated notes across, so the switch doesn't look like amnesia.

    DATABASE_URL=postgresql://... python -m research_agent.migrate --dry-run
    DATABASE_URL=postgresql://... python -m research_agent.migrate

Notes are copied with their *existing* embeddings rather than re-embedded:
it's free, it's exact, and re-embedding would silently change recall
behaviour at the same moment you're changing infrastructure -- so if recall
did get worse you'd have two suspects instead of none.

Ownership and expiry travel with the data: notes and sessions keep their
`owner` and their original `created_at`, so nothing arrives belonging to
nobody or with its TTL clock restarted. Sessions that had already expired at
the source are not resurrected, and the count of them is printed rather than
left to be discovered.

Re-runnable: sessions and runs already present are skipped, so an interrupted
migration can simply be run again.

There is a second surface here, for moving an existing pgvector corpus to a
new table:

    python -m research_agent.migrate embeddings copy --from OLD --to NEW [--dry-run]
    python -m research_agent.migrate embeddings re-embed --from OLD --to NEW \
        --model voyage-3.5 [--dimensions 1024] [--dry-run] [--yes]

Two commands and never one, because they change different variables. `copy`
moves the corpus with its existing vectors: recall is provably unchanged, and
the infrastructure is the only thing that moved. `re-embed` puts the same
texts through a new model at a new width: recall may change, and because
`copy` proves the other half, whatever changed is attributable to the model.

`re-embed` costs money, so it prints a cost preview on every invocation and
requires `--yes` before it embeds anything.

These are subcommands; the bare invocation above stays exactly what it was, so
nothing documented in OPERATIONS.md changes. One migration tool, not three.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable, Sequence
from datetime import date, datetime, timezone

from research_agent import db, usage
from research_agent.memory import (
    PGVECTOR_TABLE,
    STORE_PATH,
    VECTOR_DIMENSIONS,
    Embedder,
    PgVectorMemoryStore,
    VoyageEmbedder,
    validate_table_name,
)
from research_agent.metrics import METRICS_DB_PATH, PostgresMetricsStore, SQLiteMetricsStore
from research_agent.sessions import SESSION_DB_PATH, PostgresSessionStore, SQLiteSessionStore


def migrate_sessions(source_path: str, dry_run: bool) -> tuple[int, int]:
    if not os.path.exists(source_path):
        print(f"  sessions: no database at {source_path}, nothing to do")
        return 0, 0

    source = SQLiteSessionStore(source_path)
    target = PostgresSessionStore()
    copied = skipped = 0
    try:
        # No limit: list() defaults to 50, which would quietly migrate a
        # fraction of a busy deployment and look like success.
        sessions = source.list(limit=10**9)
        # list() applies the TTL filter, so expired sessions are not carried
        # across. That is the right call -- a migration should not resurrect
        # data the service had already stopped serving -- but silent omission
        # is indistinguishable from data loss, so state it. count() reads the
        # raw table, unfiltered; the difference is exactly what the TTL ate.
        expired = source.count() - len(sessions)
        if expired > 0:
            print(f"  sessions: {expired} expired session(s) not migrated")
        for session in sessions:
            if target.get(session.id) is not None:
                skipped += 1
                continue
            if not dry_run:
                target.create(
                    session.task, session.state, session_id=session.id, owner=session.owner
                )
                # create() stamps a fresh timestamp and turns=1; restore what
                # actually happened, or every migrated thread looks brand new
                # and one turn long. owner is set by create() above and set
                # again here on purpose: the UPDATE is what proves it survived
                # the trip, and it costs nothing in a statement already run.
                target.db.execute(
                    "UPDATE sessions SET created_at = %s, updated_at = %s, turns = %s, "
                    "owner = %s WHERE id = %s",
                    (
                        session.created_at,
                        session.updated_at,
                        session.turns,
                        session.owner,
                        session.id,
                    ),
                )
            copied += 1
    finally:
        source.close()
        target.close()
    return copied, skipped


def migrate_runs(source_path: str, dry_run: bool) -> tuple[int, int]:
    if not os.path.exists(source_path):
        print(f"  runs: no database at {source_path}, nothing to do")
        return 0, 0

    source = SQLiteMetricsStore(source_path)
    target = PostgresMetricsStore()
    copied = skipped = 0
    try:
        with source._lock:
            rows = [dict(r) for r in source._conn.execute("SELECT * FROM runs ORDER BY id")]

        existing = {
            (r["run_id"], r["created_at"])
            for r in target.db.fetchall("SELECT run_id, created_at FROM runs")
        }
        for row in rows:
            row.pop("id", None)  # let Postgres assign its own
            if (row["run_id"], row["created_at"]) in existing:
                skipped += 1
                continue
            row["approved"] = bool(row["approved"])
            if not dry_run:
                columns = ", ".join(row)
                placeholders = ", ".join(f"%({name})s" for name in row)
                target.db.execute(f"INSERT INTO runs ({columns}) VALUES ({placeholders})", row)
            copied += 1
    finally:
        source.close()
        target.close()
    return copied, skipped


def migrate_notes(
    source_path: str,
    dry_run: bool,
    table: str = PGVECTOR_TABLE,
    dimensions: int = VECTOR_DIMENSIONS,
) -> tuple[int, int]:
    """Copy the JSON note store into a pgvector table.

    `table` and `dimensions` are parameters rather than the module constants
    read at import time, so a test can point this at a 5-dimensional scratch
    table without monkeypatching a name this module already bound.
    """
    if not os.path.exists(source_path):
        print(f"  notes: no store at {source_path}, nothing to do")
        return 0, 0

    with open(source_path) as f:
        entries = json.load(f)
    if not entries:
        return 0, 0

    width = len(entries[0]["embedding"])
    if width != dimensions:
        raise SystemExit(
            f"Stored notes are {width}-dimensional but VECTOR_DIMENSIONS is "
            f"{dimensions}. Set VECTOR_DIMENSIONS={width} so the pgvector "
            f"column matches the embeddings you already have."
        )

    target = PgVectorMemoryStore(table=table, dimensions=width)
    copied = skipped = 0
    try:
        # Dedup on (text, owner, created_at), never text alone: under Phase 12
        # scoping the same note text under two owners is two legitimate rows,
        # and a text-only key would migrate the first and silently drop the
        # second. The timestamp half of the key is compared as a datetime
        # rather than as an epoch float: timestamptz keeps microseconds, and a
        # ~1.8e9 epoch with six decimals is already past float64's exact range,
        # so an epoch comparison could fail to recognise the row it just wrote.
        existing = {
            (r["text"], r["owner"], r["created_at"])
            for r in target.db.fetchall(f"SELECT text, owner, created_at FROM {table}")
        }
        for entry in entries:
            owner = entry.get("owner", "")
            # A missing or zero created_at means a pre-Phase-12 entry, which
            # migrates as epoch 0 -- already expired under the note TTL. That
            # mirrors what the store itself does with those entries (they read
            # as 0 and are swept), rather than resurrecting them with a fresh
            # timestamp.
            created_at = datetime.fromtimestamp(
                float(entry.get("created_at", 0.0)), tz=timezone.utc
            )
            if (entry["text"], owner, created_at) in existing:
                skipped += 1
                continue
            if not dry_run:
                target.db.execute(
                    f"INSERT INTO {table} (text, embedding, owner, created_at) "
                    f"VALUES (%s, %s::vector, %s, %s)",
                    (
                        entry["text"],
                        PgVectorMemoryStore._literal(entry["embedding"]),
                        owner,
                        created_at,
                    ),
                )
            copied += 1
    finally:
        target.close()
    return copied, skipped


# --------------------------------------------------------------------------
# embeddings copy -- move a pgvector corpus to another table, same vectors
# --------------------------------------------------------------------------


def _table_exists(database: db.Database, table: str) -> bool:
    """Whether `table` is visible on the current search_path.

    Asked before anything else touches the name so a typo produces a sentence
    instead of an UndefinedTable traceback -- and so --dry-run can report on a
    target that does not exist yet without creating it.
    """
    return database.fetchone("SELECT to_regclass(%s) AS oid", (table,))["oid"] is not None


def _count(database: db.Database, table: str) -> int:
    return database.fetchone(f"SELECT count(*) AS n FROM {table}")["n"]


# The re-runnability key, and the fidelity join key, and they must be the same
# thing: a row the copy decided it had already written is exactly a row the
# fidelity check must be able to match. `id` is BIGSERIAL and deliberately not
# copied, so it cannot serve.
_KEY = "(text, owner, created_at)"

# One skip clause, used by the copy and by the --dry-run count, so the number
# a dry run promises is produced by the same predicate the real run applies.
_NOT_EXISTS = """
    NOT EXISTS (
        SELECT 1 FROM {target} n
        WHERE n.text = o.text AND n.owner = o.owner AND n.created_at = o.created_at
    )
"""

# The copy itself. Server-side, so the embeddings are moved by Postgres as
# pgvector values and never become Python floats on the way -- the difference
# between "byte-identical by construction" and "byte-identical if repr() round
# trips". All four meaningful columns travel: `owner` because a note that
# arrives owned by nobody has silently lost its tenancy, and `created_at`
# because a note stamped now() has silently had its 7-day TTL restarted (and
# because it is half the join key everything below is measured on). `id` is
# BIGSERIAL and deliberately left behind.
_COPY_SQL = f"""
    INSERT INTO {{target}} (text, embedding, owner, created_at)
    SELECT o.text, o.embedding, o.owner, o.created_at FROM {{source}} o
    WHERE {_NOT_EXISTS}
"""

_PENDING_SQL = f"""
    SELECT count(*) AS n FROM {{source}} o
    WHERE {_NOT_EXISTS}
"""


def copy_embeddings(
    from_table: str,
    to_table: str,
    dry_run: bool = False,
    database: db.Database | None = None,
) -> int:
    """Copy one pgvector notes table into another. Returns an exit code.

    The vectors never enter this process. `INSERT INTO ... SELECT` happens
    inside the server, so the new table's embeddings are the old table's bytes
    rather than a reconstruction of them -- byte-identical by construction
    instead of byte-identical if the float formatting round-trips. That matters
    because the whole point of this command is to change the infrastructure
    variable and *nothing else*, so that a later re-embedding's effect on
    recall is attributable to the model.

    Non-destructive and idempotent. It issues no statement of any kind against
    `--from`; a second run copies the rows it did not already write, keyed on
    (text, owner, created_at); nothing is ever dropped or renamed. Cutover is a
    config change (PGVECTOR_TABLE) and rollback is pointing it back, which only
    works while the old table is still there.
    """
    validate_table_name(from_table)
    validate_table_name(to_table)
    if from_table == to_table:
        print(f"error: --from and --to are both {from_table!r}.", file=sys.stderr)
        return 2

    handle = database or db.Database()
    owns_handle = database is None
    target_store = None
    try:
        if not _table_exists(handle, from_table):
            print(f"error: source table {from_table!r} does not exist.", file=sys.stderr)
            return 2
        source_count = _count(handle, from_table)
        if source_count == 0:
            # Refused rather than reported as a successful no-op: a copy of
            # nothing satisfies every fidelity check there is and proves
            # nothing about the migration, which is the opposite of what an
            # operator running this is asking for.
            print(f"error: source table {from_table!r} is empty, nothing to copy.", file=sys.stderr)
            return 2
        dimensions = int(
            handle.fetchone(f"SELECT vector_dims(embedding) AS d FROM {from_table} LIMIT 1")["d"]
        )

        if dry_run:
            # Deliberately no DDL here. Creating the target would be a write,
            # and a --dry-run that writes is not one. If the target does not
            # exist yet, every source row is pending by definition.
            pending = (
                _fetch_pending(handle, from_table, to_table)
                if _table_exists(handle, to_table)
                else source_count
            )
            print("DRY RUN — nothing will be written\n")
            print(f"  source     {from_table} ({source_count} row(s), vector({dimensions}))")
            print(f"  target     {to_table}")
            print(f"  to copy    {pending} row(s)")
            print("\nRe-run without --dry-run to apply. It is safe to run more than once.")
            return 0

        # The target's DDL goes through the store, so the new table is the
        # production schema -- same columns, same HNSW index, same
        # advisory-locked ensure_schema -- rather than a second CREATE TABLE
        # that has to be kept in step with the first. Its own Database on the
        # same DSN: a Database applies at most one schema block in its life.
        target_store = PgVectorMemoryStore(
            table=to_table, dimensions=dimensions, database=db.Database(dsn=handle.dsn)
        )
        target_db = target_store.db
        before = _count(target_db, to_table)  # also forces the deferred DDL

        with target_db.cursor() as cur:
            cur.execute(_COPY_SQL.format(source=from_table, target=to_table))
            copied = cur.rowcount

        target_count = _count(handle, to_table)
        unmatched = handle.fetchone(
            f"SELECT count(*) AS n FROM {from_table} o "
            f"LEFT JOIN {to_table} n USING {_KEY} WHERE n.text IS NULL"
        )["n"]
        joined = handle.fetchone(
            f"SELECT count(*) AS n FROM {from_table} o JOIN {to_table} n USING {_KEY}"
        )["n"]
        byte_diff = handle.fetchone(
            f"SELECT count(*) AS n FROM {from_table} o JOIN {to_table} n USING {_KEY} "
            f"WHERE o.embedding::text IS DISTINCT FROM n.embedding::text"
        )["n"]

        print(f"copied {copied} row(s) into {to_table} ({before} already present)\n")
        print("fidelity")
        print(f"  rows         {source_count} in {from_table}, {target_count} in {to_table}")
        print(f"  matched      {joined} of {source_count} on {_KEY}")
        print(f"  unmatched    {unmatched}")
        print(f"  byte-differing embeddings  {byte_diff}")

        failures = []
        if target_count != source_count:
            failures.append(f"row counts differ: {source_count} vs {target_count}")
        if unmatched:
            failures.append(f"{unmatched} source row(s) have no counterpart in {to_table}")
        if joined != source_count:
            # More joined rows than source rows means the key is not a key --
            # a duplicate (text, owner, created_at) fans the join out and every
            # other number above is then measured over the wrong row set.
            failures.append(
                f"{joined} joined row(s) for {source_count} source row(s): "
                f"{_KEY} is not unique, so the fidelity numbers cannot be trusted"
            )
        if byte_diff:
            failures.append(f"{byte_diff} embedding(s) differ byte-for-byte")
        if failures:
            print("\nFIDELITY FAILED:", file=sys.stderr)
            for failure in failures:
                print(f"  {failure}", file=sys.stderr)
            return 1

        print(f"\n{from_table} is untouched. Cut over with PGVECTOR_TABLE={to_table}.")
        return 0
    finally:
        if target_store is not None:
            target_store.close()
        if owns_handle:
            handle.close()


def _fetch_pending(database: db.Database, from_table: str, to_table: str) -> int:
    return database.fetchone(_PENDING_SQL.format(source=from_table, target=to_table))["n"]


# --------------------------------------------------------------------------
# embeddings re-embed -- the same texts, a new model, a new width
# --------------------------------------------------------------------------
#
# The opposite operation to `copy`, and separate from it on purpose. `copy`
# changes the infrastructure and provably nothing else; this changes the model
# and provably nothing else. Recall MAY move here -- that is the entire point,
# and it is only attributable to the model because the other command exists to
# prove the infrastructure half moves nothing.
#
# This one spends money, so it has two gates `copy` does not need: a cost
# preview that always prints, and `--yes`.

# pgvector's HNSW index supports the `vector` type up to 2,000 dimensions.
# voyage-3.5 will happily emit 2,048, which produces a table that cannot be
# indexed -- so the ceiling is enforced here, before any DDL and before any
# spend, rather than discovered when CREATE INDEX fails. `halfvec` reaches
# 4,000 and is the documented path past this, but nothing here builds halfvec
# columns and pretending otherwise would be worse than the refusal.
HNSW_MAX_DIMENSIONS = 2000

# The voyage-3.5 family's default width, and therefore this flag's default.
# There is deliberately no table of per-model defaults: it would be a second
# copy of Voyage's documentation, silently wrong the day a model changes, and
# the operator who wants a non-default width can say which one they want.
DEFAULT_OUTPUT_DIMENSIONS = 1024

# Well under Voyage's per-request limits (1,000 texts and 320K tokens for
# voyage-3.5), so a batch is bounded by this number rather than by an API
# error nobody wants to discover mid-corpus.
DEFAULT_BATCH_SIZE = 128


class _ReembedEmbedder(VoyageEmbedder):
    """A VoyageEmbedder that also remembers what it was billed for.

    The `Embedder` seam returns vectors and nothing else, which is right for
    the four stores that use it -- none of them has any business knowing about
    tokens. But the reconciliation line this command prints ("we predicted X,
    Voyage counted Y") needs the number the response carries, so it is read
    here, in the one caller that wants it, rather than by widening a protocol
    four backends implement.
    """

    def __init__(self, model: str, output_dimension: int | None = None):
        super().__init__(model=model, output_dimension=output_dimension)
        self.total_tokens = 0

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        response = self.client.embed(
            list(texts),
            model=self.model,
            input_type="document",
            output_dimension=self.output_dimension,
        )
        self.total_tokens += int(getattr(response, "total_tokens", 0) or 0)
        return response.embeddings


def _default_embedder_factory(model: str, output_dimension: int | None) -> Embedder:
    return _ReembedEmbedder(model=model, output_dimension=output_dimension)


def _default_token_counter(texts: Sequence[str], model: str) -> int:
    """Voyage's own tokenizer, run locally. Exact, and costs nothing.

    Imported and constructed here rather than at module scope because the
    first call downloads the model's tokenizer from the Hugging Face hub. That
    is fine for an operator running a migration and wrong for a unit test,
    which is why this is injectable and why every test injects instead.
    """
    import voyageai

    return int(voyageai.Client().count_tokens(list(texts), model=model))


def reembed_notes(
    from_table: str,
    to_table: str,
    model: str,
    dimensions: int = DEFAULT_OUTPUT_DIMENSIONS,
    batch_size: int = DEFAULT_BATCH_SIZE,
    dry_run: bool = False,
    yes: bool = False,
    database: db.Database | None = None,
    token_counter: Callable[[Sequence[str], str], int] | None = None,
    embedder_factory: Callable[[str, int | None], Embedder] | None = None,
    on: date | None = None,
) -> int:
    """Re-embed one pgvector notes table into another. Returns an exit code.

    Every text is read from `--from`, embedded again with `--model` at
    `--dimensions`, and written to `--to` carrying its original `owner` and
    `created_at` -- the first because a note that arrives owned by nobody has
    silently lost its tenancy, the second because a note stamped `now()` has
    silently had its 7-day TTL restarted and because it is half the key that
    makes this re-runnable.

    Spending is gated twice over. The cost preview prints on every invocation,
    before anything is embedded; `--yes` is then required to proceed, and there
    is no flag combination that reaches the embedder without it. An unpriced
    model refuses rather than quoting $0.00, and a width the HNSW index cannot
    take refuses before any DDL runs.

    `token_counter` and `embedder_factory` are injection points rather than
    module state to monkeypatch: the real counter downloads a tokenizer on
    first use and the real embedder bills, so tests supply their own and the
    zero-spend claims can be asserted by counting calls on a fake.
    """
    validate_table_name(from_table)
    validate_table_name(to_table)
    if from_table == to_table:
        print(f"error: --from and --to are both {from_table!r}.", file=sys.stderr)
        return 2

    # Before the DDL and before the spend, in that order of importance.
    if dimensions > HNSW_MAX_DIMENSIONS:
        print(
            f"error: --dimensions {dimensions} exceeds pgvector's HNSW limit of "
            f"{HNSW_MAX_DIMENSIONS} for the `vector` type, so {to_table} could be "
            f"created but never indexed.\n"
            f"  voyage-3.5 does offer 2048 -- that is exactly why this refuses "
            f"rather than finding out at CREATE INDEX.\n"
            f"  pgvector's `halfvec` reaches 4000 dimensions and is the documented "
            f"way past this; this tool does not build halfvec columns.\n"
            f"  Supported targets: 256, 512, 1024.",
            file=sys.stderr,
        )
        return 2
    if dimensions < 1:
        print(f"error: --dimensions {dimensions} is not a vector width.", file=sys.stderr)
        return 2

    # Resolved first, before the tokenizer is touched and long before anything
    # is embedded: an unlisted model must cost nothing to discover. DEC-12 --
    # the run never proceeds at $0.00.
    try:
        rate = usage.voyage_price_for(model, on)
    except usage.UnknownModelPricing as exc:
        print(f"error: {exc}", file=sys.stderr)
        print(
            "  Refusing to embed at an unknown price. Add the rate to "
            "usage.VOYAGE_PRICES if the model is real.",
            file=sys.stderr,
        )
        return 2

    counter = token_counter or _default_token_counter
    make_embedder = embedder_factory or _default_embedder_factory

    handle = database or db.Database()
    owns_handle = database is None
    target_store = None
    try:
        if not _table_exists(handle, from_table):
            print(f"error: source table {from_table!r} does not exist.", file=sys.stderr)
            return 2
        rows = handle.fetchall(
            f"SELECT text, owner, created_at FROM {from_table} ORDER BY created_at"
        )
        if not rows:
            print(
                f"error: source table {from_table!r} is empty, nothing to re-embed.",
                file=sys.stderr,
            )
            return 2

        # Resume-on-interrupt, keyed the way everything else in this file is
        # keyed. created_at stays a datetime on both sides: timestamptz keeps
        # microseconds and an epoch float cannot represent them exactly at
        # 1.8e9, so an epoch key would fail to recognise rows it just wrote.
        existing: set[tuple] = set()
        if _table_exists(handle, to_table):
            existing = {
                (r["text"], r["owner"], r["created_at"])
                for r in handle.fetchall(f"SELECT text, owner, created_at FROM {to_table}")
            }
        pending = [r for r in rows if (r["text"], r["owner"], r["created_at"]) not in existing]

        texts = [r["text"] for r in pending]
        predicted_tokens = counter(texts, model) if texts else 0
        estimated = usage.preview_cost_usd(predicted_tokens, model, on)

        # ALWAYS, and always before anything is embedded. A preview that only
        # printed on some paths would be a preview an operator could not rely
        # on seeing, which is the same as not having one.
        print("cost preview")
        print(f"  model        {model} at {dimensions} dimensions")
        print(f"  source       {from_table} ({len(rows)} row(s))")
        print(f"  to embed     {len(pending)} note(s), {predicted_tokens} token(s)")
        print(
            f"  rate         ${rate:g} per million tokens "
            f"(verified {usage.VOYAGE_PRICES_VERIFIED.isoformat()})"
        )
        print(f"  estimated    ${estimated:.6f}")
        print(
            "\n  List price, and an UPPER BOUND. Voyage bills its own token count, not\n"
            "  this one: measured 2026-08-09, the local tokenizer counted 40 tokens for\n"
            "  a corpus the API's own response reported as 25. The voyage-4 family's\n"
            "  free-token allowance is not modelled here either.\n"
        )

        if dry_run:
            # Dry run wins over --yes. The two flags contradict each other and
            # the safe reading is the one that spends nothing.
            print(f"DRY RUN — nothing will be written to {to_table}.")
            print("Re-run with --yes to embed. It is safe to run more than once.")
            return 0

        if not yes:
            print(
                f"error: --yes is required to spend. {len(pending)} note(s) would be sent "
                f"to {model} at the rate above; nothing was embedded.",
                file=sys.stderr,
            )
            return 2

        if not pending:
            print(f"{to_table} already holds every row in {from_table}. Nothing to do.")
            return 0

        # Only a non-default width is requested explicitly, so an ordinary
        # 1024-dimensional run sends exactly the request every other caller in
        # this codebase sends. If a model's own default were ever something
        # other than 1024, this would ask for the wrong width -- and the store's
        # dimension check below would say so loudly, which is the point of
        # routing every vector through it.
        requested = dimensions if dimensions != DEFAULT_OUTPUT_DIMENSIONS else None
        embedder = make_embedder(model, requested)
        # The target's DDL goes through the store, so the new table is the
        # production schema at the new width. Its own Database on the same DSN:
        # a Database applies at most one schema block in its life.
        target_store = PgVectorMemoryStore(
            table=to_table,
            dimensions=dimensions,
            embedder=embedder,
            database=db.Database(dsn=handle.dsn),
        )

        written = 0
        for start in range(0, len(pending), batch_size):
            batch = pending[start : start + batch_size]
            vectors = embedder.embed_documents([r["text"] for r in batch])
            for row, vector in zip(batch, vectors, strict=True):
                # The store's own check, called on the store, never a second
                # width comparison written here. SC-4 asks that the loud check
                # still fires in the migration path -- a copy of it in this
                # file could drift from the one production uses, and the whole
                # failure mode being guarded against is a silent coercion.
                target_store._check_dimensions(vector)
                target_store.db.execute(
                    f"INSERT INTO {to_table} (text, embedding, owner, created_at) "
                    f"VALUES (%s, %s::vector, %s, %s)",
                    (
                        row["text"],
                        PgVectorMemoryStore._literal(vector),
                        row["owner"],
                        row["created_at"],
                    ),
                )
                written += 1
            print(f"  embedded {written} of {len(pending)} note(s)")

        actual_tokens = getattr(embedder, "total_tokens", None)
        print(f"\nre-embedded {written} note(s) into {to_table} at vector({dimensions}).")
        print(f"  predicted    {predicted_tokens} token(s) (local tokenizer)")
        # `is not None`, not truthiness: the response's count can legitimately
        # be 0 (see below), and a 0 that fell through to "not reported" would
        # be a missing receipt reported as a missing feature.
        if actual_tokens is not None:
            print(f"  reported     {actual_tokens} token(s) (Voyage's response.total_tokens)")
            print(f"  at that rate ${usage.preview_cost_usd(actual_tokens, model, on):.6f}")
            if actual_tokens != predicted_tokens:
                # Measured 2026-08-09 against the live API: 12 notes the local
                # tokenizer counted at 40 tokens came back reported as 25, and
                # a single one-word document came back as 0 -- which no
                # request that returns an embedding can actually have cost.
                # So neither number is an invoice: the local count is the
                # honest upper bound and this one is what the response said.
                # Voyage's dashboard is the only authority on what was billed.
                print(
                    f"  the two disagree by {predicted_tokens - actual_tokens:+d} token(s). "
                    f"Neither is an invoice -- check Voyage's usage dashboard for that."
                )
        else:
            # The fake-embedder path, and any client that stopped reporting it.
            print("  reported     not reported by this embedder")
        print(
            f"\n{from_table} is untouched. Cut over with PGVECTOR_TABLE={to_table} "
            f"and VECTOR_DIMENSIONS={dimensions}; roll back by pointing them back."
        )
        return 0
    finally:
        if target_store is not None:
            target_store.close()
        if owns_handle:
            handle.close()


def _main_embeddings(
    argv: list[str],
    token_counter: Callable[[Sequence[str], str], int] | None = None,
    embedder_factory: Callable[[str, int | None], Embedder] | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m research_agent.migrate embeddings",
        description="Move an existing pgvector notes corpus to another table.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    copy = sub.add_parser(
        "copy",
        help="copy a corpus to a new table with its existing vectors (recall unchanged)",
        description=copy_embeddings.__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    copy.add_argument("--from", dest="from_table", required=True, help="source table")
    copy.add_argument("--to", dest="to_table", required=True, help="target table")
    copy.add_argument("--dry-run", action="store_true", help="report without writing")

    reembed = sub.add_parser(
        "re-embed",
        help="embed a corpus again with a new model/width (recall may change; costs money)",
        description=reembed_notes.__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    reembed.add_argument("--from", dest="from_table", required=True, help="source table")
    reembed.add_argument("--to", dest="to_table", required=True, help="target table")
    reembed.add_argument(
        "--model", required=True, help="Voyage embedding model, e.g. voyage-3.5"
    )
    reembed.add_argument(
        "--dimensions",
        type=int,
        default=DEFAULT_OUTPUT_DIMENSIONS,
        help=(
            f"target vector width (default {DEFAULT_OUTPUT_DIMENSIONS}, the voyage-3.5 "
            f"family's own default). Say so explicitly for anything else; "
            f"above {HNSW_MAX_DIMENSIONS} is refused because HNSW cannot index it."
        ),
    )
    reembed.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    reembed.add_argument("--dry-run", action="store_true", help="preview and stop")
    reembed.add_argument("--yes", action="store_true", help="required to actually spend")
    args = parser.parse_args(argv)

    if not db.postgres_configured():
        print("error: DATABASE_URL is not set — nothing to migrate.", file=sys.stderr)
        return 2
    if args.command == "re-embed":
        return reembed_notes(
            args.from_table,
            args.to_table,
            model=args.model,
            dimensions=args.dimensions,
            batch_size=args.batch_size,
            dry_run=args.dry_run,
            yes=args.yes,
            token_counter=token_counter,
            embedder_factory=embedder_factory,
        )
    return copy_embeddings(args.from_table, args.to_table, dry_run=args.dry_run)


def main(
    argv: list[str] | None = None,
    *,
    token_counter: Callable[[Sequence[str], str], int] | None = None,
    embedder_factory: Callable[[str, int | None], Embedder] | None = None,
) -> int:
    """Dispatch on the first token, then hand off.

    A top-level argparse subparser set would have made the documented bare
    invocation -- `python -m research_agent.migrate --dry-run` -- into an error
    about a missing subcommand, which is a compatibility break dressed up as
    tidiness. So `embeddings` is claimed by name and everything else is the
    legacy parser, unchanged.

    `token_counter` and `embedder_factory` travel through to `re-embed`. They
    are keyword-only and default to the real thing, so the CLI is unaffected;
    they exist so a test can assert "this invocation embedded nothing" by
    counting calls on a fake rather than by reading the code and hoping.
    """
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "embeddings":
        return _main_embeddings(
            argv[1:], token_counter=token_counter, embedder_factory=embedder_factory
        )
    return _main_stores(argv)


def _main_stores(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "subcommands:\n"
            "  embeddings copy --from OLD --to NEW    move a pgvector corpus to a new\n"
            "                                         table, same vectors, non-destructive\n"
            "  embeddings re-embed --from OLD --to NEW --model M\n"
            "                                         embed the same texts again with a\n"
            "                                         new model/width; previews the cost\n"
            "                                         and needs --yes to spend\n"
        ),
    )
    parser.add_argument("--dry-run", action="store_true", help="report without writing")
    parser.add_argument("--sessions-db", default=SESSION_DB_PATH)
    parser.add_argument("--metrics-db", default=METRICS_DB_PATH)
    parser.add_argument("--notes", default=STORE_PATH)
    args = parser.parse_args(argv)

    if not db.postgres_configured():
        print("error: DATABASE_URL is not set — nothing to migrate into.", file=sys.stderr)
        return 2

    label = "DRY RUN — nothing will be written" if args.dry_run else "migrating"
    print(f"{label}\n")

    total = 0
    for name, fn, source in (
        ("sessions", migrate_sessions, args.sessions_db),
        ("runs", migrate_runs, args.metrics_db),
        ("notes", migrate_notes, args.notes),
    ):
        copied, skipped = fn(source, args.dry_run)
        total += copied
        note = f" ({skipped} already present)" if skipped else ""
        print(f"  {name:9} {copied} to copy{note}")

    print(f"\n{total} record(s) {'would be' if args.dry_run else ''} copied.")
    if args.dry_run:
        print("Re-run without --dry-run to apply. It is safe to run more than once.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
