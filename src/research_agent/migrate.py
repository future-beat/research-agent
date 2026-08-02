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

Re-runnable: sessions and runs already present are skipped, so an interrupted
migration can simply be run again.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from research_agent import db
from research_agent.memory import (
    PGVECTOR_TABLE,
    STORE_PATH,
    VECTOR_DIMENSIONS,
    PgVectorMemoryStore,
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
        for session in source.list(limit=10**9):
            if target.get(session.id) is not None:
                skipped += 1
                continue
            if not dry_run:
                target.create(session.task, session.state, session_id=session.id)
                # create() stamps a fresh timestamp and turns=1; restore what
                # actually happened, or every migrated thread looks brand new
                # and one turn long.
                target.db.execute(
                    "UPDATE sessions SET created_at = %s, updated_at = %s, turns = %s "
                    "WHERE id = %s",
                    (session.created_at, session.updated_at, session.turns, session.id),
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


def migrate_notes(source_path: str, dry_run: bool) -> tuple[int, int]:
    if not os.path.exists(source_path):
        print(f"  notes: no store at {source_path}, nothing to do")
        return 0, 0

    with open(source_path) as f:
        entries = json.load(f)
    if not entries:
        return 0, 0

    width = len(entries[0]["embedding"])
    if width != VECTOR_DIMENSIONS:
        raise SystemExit(
            f"Stored notes are {width}-dimensional but VECTOR_DIMENSIONS is "
            f"{VECTOR_DIMENSIONS}. Set VECTOR_DIMENSIONS={width} so the pgvector "
            f"column matches the embeddings you already have."
        )

    target = PgVectorMemoryStore(table=PGVECTOR_TABLE, dimensions=width)
    copied = skipped = 0
    try:
        existing = {
            r["text"] for r in target.db.fetchall(f"SELECT text FROM {PGVECTOR_TABLE}")
        }
        for entry in entries:
            if entry["text"] in existing:
                skipped += 1
                continue
            if not dry_run:
                target.db.execute(
                    f"INSERT INTO {PGVECTOR_TABLE} (text, embedding) VALUES (%s, %s::vector)",
                    (entry["text"], PgVectorMemoryStore._literal(entry["embedding"])),
                )
            copied += 1
    finally:
        target.close()
    return copied, skipped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
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
