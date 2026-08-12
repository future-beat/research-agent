"""
Every Postgres table this service creates denies every role but its owner.

These tables live in `public`, and a managed provider may expose that schema
over an HTTP API whose key is public by design. RLS is then the only thing
between the internet and the data. Supabase's own linter flagged all five on
2026-08-12, and a role holding the grants that provider hands `anon` by default
was measured -- on a local stand-in, against this codebase's real DDL -- reading
session text and identity hashes, and deleting every row of `runs`. That last
one is the sharp end: `spend_since` sums `runs` and is the daily spend cap's
only input, so an emptied table reads as $0 spent and the bill loses its bound.

Two gates, because they fail differently:

  * the STRUCTURAL one runs keyless and catches a new table added to a schema
    constant without RLS -- the regression that would otherwise ship silently,
    since nothing about an unprotected table is visible from the application;
  * the BEHAVIOURAL one needs a real server and proves the DDL actually took,
    which the structural gate cannot see. A statement can be present and wrong.

Why the app enables it rather than a runbook: `migrate.py embeddings re-embed
--to` creates a NEW corpus table on demand. A one-time manual fix protects the
tables that exist when it is run and misses every table created after it.
"""

import inspect
import re

import pytest

from research_agent import db, limits, memory, metrics, sessions

HAS_POSTGRES = db.postgres_configured()

needs_postgres = pytest.mark.skipif(not HAS_POSTGRES, reason="DATABASE_URL is not set")

# Every place this codebase issues Postgres DDL. The pgvector store builds its
# schema in an f-string inside a method rather than a module constant -- its
# table name is configurable -- so it is read from source. Grepping a module's
# own source is an established idiom here (see the Phase 16 pin that `limits.py`
# never grew a `usage` import).
DDL_SOURCES: list[tuple[str, str]] = [
    ("metrics.POSTGRES_SCHEMA", metrics.POSTGRES_SCHEMA),
    ("sessions.POSTGRES_SCHEMA", sessions.POSTGRES_SCHEMA),
    ("limits.POSTGRES_SCHEMA", limits.POSTGRES_SCHEMA),
    (
        "memory.PgVectorMemoryStore._ensure_schema",
        inspect.getsource(memory.PgVectorMemoryStore._ensure_schema),
    ),
]

_CREATE = re.compile(r"CREATE TABLE IF NOT EXISTS\s+(\S+?)\s*\(", re.IGNORECASE)


def _tables_created(ddl: str) -> set[str]:
    return set(_CREATE.findall(ddl))


def test_every_postgres_table_the_app_creates_enables_row_level_security():
    """Discovers tables from the DDL itself, never from a list kept beside it.

    A parallel list is a second source of truth and the copy that drifts is the
    one nobody runs -- so a table added to a schema constant is picked up here
    with no edit to this test. The assertion counts first: a regex that stopped
    matching would otherwise report a clean sweep of zero tables.
    """
    found: set[str] = set()
    for label, ddl in DDL_SOURCES:
        tables = _tables_created(ddl)
        assert tables, f"{label}: no CREATE TABLE matched -- the regex has rotted"
        for table in tables:
            found.add(f"{label}:{table}")
            pattern = re.compile(
                rf"ALTER TABLE\s+{re.escape(table)}\s+ENABLE ROW LEVEL SECURITY",
                re.IGNORECASE,
            )
            assert pattern.search(ddl), (
                f"{label} creates {table} without enabling row level security. "
                f"That table is reachable by anything the database's public API "
                f"role can reach."
            )

    # Five production tables across four DDL sites. A drop here means a table
    # stopped being created, which is as much a surprise as one appearing.
    assert len(found) == 5, f"expected 5 tables across the schemas, found {sorted(found)}"


def test_no_schema_forces_row_level_security_on_the_owner():
    """FORCE would lock the application out of its own tables.

    RLS exempts a table's owner, and the owner is the role in DATABASE_URL
    because it is the role that ran the DDL. That exemption is the whole reason
    enabling RLS is safe with no policies defined. FORCE removes it, and with no
    policy to match, every query returns zero rows -- silently. Sessions would
    simply appear empty rather than erroring, which is the worst way for this to
    fail.
    """
    for label, ddl in DDL_SOURCES:
        assert "FORCE ROW LEVEL SECURITY" not in ddl.upper(), (
            f"{label} uses FORCE ROW LEVEL SECURITY. The application owns these "
            f"tables; FORCE makes it read zero rows with no error raised."
        )


@needs_postgres
def test_the_tables_really_carry_rls_on_a_live_server():
    """The structural gate proves the statement is written, not that it ran.

    `ensure_schema` is advisory-locked and retried, DDL is re-issued on first
    use, and a provider could in principle refuse the ALTER. This reads the
    server's own catalog for the four fixed-name tables after the application
    has built its schema.
    """
    metrics.PostgresMetricsStore()
    sessions.PostgresSessionStore()
    limits.PostgresLimits()

    handle = db.Database()
    try:
        rows = handle.fetchall(
            """
            SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' AND c.relkind = 'r' AND c.relname = ANY(%s)
            """,
            (["runs", "sessions", "rate_hits", "run_reservations"],),
        )
    finally:
        handle.close()
    seen = {r["relname"]: (r["relrowsecurity"], r["relforcerowsecurity"]) for r in rows}
    assert len(seen) == 4, f"expected all four tables, saw {sorted(seen)}"
    assert seen, "none of the expected tables exist -- schema never ran"
    for name, (enabled, forced) in sorted(seen.items()):
        assert enabled, f"{name} exists on the server with RLS OFF"
        assert not forced, f"{name} has FORCE set; the application is locked out"


@needs_postgres
def test_a_freshly_created_corpus_table_is_protected_too():
    """The re-embed hole, pinned.

    `migrate.py embeddings re-embed --to` creates a corpus table whose name did
    not exist when anyone last ran a manual fix. This creates one the same way
    the migration does and reads the catalog back.
    """
    table = "rls_probe_notes"
    store = memory.PgVectorMemoryStore(table=table, dimensions=8)
    store.describe()  # forces the deferred DDL

    handle = db.Database()
    try:
        rows = handle.fetchall(
            "SELECT relrowsecurity FROM pg_class WHERE relname = %s",
            (table,),
        )
        handle.execute(f"DROP TABLE IF EXISTS {table}")
    finally:
        handle.close()
    assert rows, f"{table} was not created"
    assert rows[0]["relrowsecurity"], (
        "a corpus table created after the fact has RLS off -- the re-embed "
        "path reopens the hole every time it runs"
    )
