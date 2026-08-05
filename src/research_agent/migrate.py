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

That one is a subcommand; the bare invocation above stays exactly what it was,
so nothing documented in OPERATIONS.md changes. One migration tool, not three.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

from research_agent import db
from research_agent.memory import (
    PGVECTOR_TABLE,
    STORE_PATH,
    VECTOR_DIMENSIONS,
    PgVectorMemoryStore,
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


def _main_embeddings(argv: list[str]) -> int:
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
    args = parser.parse_args(argv)

    if not db.postgres_configured():
        print("error: DATABASE_URL is not set — nothing to migrate.", file=sys.stderr)
        return 2
    return copy_embeddings(args.from_table, args.to_table, dry_run=args.dry_run)


def main(argv: list[str] | None = None) -> int:
    """Dispatch on the first token, then hand off.

    A top-level argparse subparser set would have made the documented bare
    invocation -- `python -m research_agent.migrate --dry-run` -- into an error
    about a missing subcommand, which is a compatibility break dressed up as
    tidiness. So `embeddings` is claimed by name and everything else is the
    legacy parser, unchanged.
    """
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "embeddings":
        return _main_embeddings(argv[1:])
    return _main_stores(argv)


def _main_stores(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "subcommands:\n"
            "  embeddings copy --from OLD --to NEW    move a pgvector corpus to a new\n"
            "                                         table, same vectors, non-destructive\n"
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
