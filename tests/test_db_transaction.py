"""
Database.transaction(): a real transaction on a pool that is autocommit=True.

Wave 2's spend-cap reservation is check-then-write under
`pg_advisory_xact_lock`, and a transaction-scoped lock needs a transaction to
hang on -- which an autocommit pool does not otherwise have. These tests prove
the three properties the reservation will lean on, each against a real server:

  * a clean exit COMMITS (the reserved row is visible afterwards),
  * a raising body ROLLS BACK (the row is gone, not half-written),
  * the advisory lock taken inside is genuinely transaction-scoped -- held
    against a rival while the block is open, free the moment it closes,
    with nothing having called an unlock.

Postgres-gated like the rest of the contract file; CI runs with
REQUIRE_POSTGRES=1 where a skip here would be caught by
test_postgres_really_ran_when_ci_said_it_would.
"""

import pytest

from research_agent import db

HAS_POSTGRES = db.postgres_configured()

needs_postgres = pytest.mark.skipif(not HAS_POSTGRES, reason="DATABASE_URL is not set")

# A dedicated table, TRUNCATEd per test, so the transaction runs cannot collide
# with production tables or with a parallel contract run.
TABLE = "contract_test_transactions"


def test_the_cap_lock_key_is_not_the_schema_lock_key():
    """Deliberately not Postgres-gated: the property is arithmetic.

    A shared key would serialise cap accounting against schema DDL -- two
    things with nothing to coordinate. This fails loudly the moment an edit
    collapses the constants.
    """
    assert db.CAP_LOCK_KEY != db.SCHEMA_LOCK_KEY


@pytest.fixture
def handle():
    handle = db.Database()
    handle.execute(
        f"CREATE TABLE IF NOT EXISTS {TABLE} (id BIGSERIAL PRIMARY KEY, note TEXT NOT NULL)"
    )
    handle.execute(f"TRUNCATE {TABLE}")
    yield handle
    handle.close()


def _count(handle) -> int:
    return handle.fetchone(f"SELECT COUNT(*) AS n FROM {TABLE}")["n"]


@needs_postgres
def test_a_clean_exit_commits(handle):
    with handle.transaction() as cur:
        cur.execute(f"INSERT INTO {TABLE} (note) VALUES ('kept')")

    assert _count(handle) == 1


@needs_postgres
def test_a_raising_body_rolls_back(handle):
    class Boom(RuntimeError):
        pass

    with pytest.raises(Boom), handle.transaction() as cur:
        cur.execute(f"INSERT INTO {TABLE} (note) VALUES ('discarded')")
        # Visible from inside the open transaction -- so the absence
        # afterwards is a rollback, not an insert that never ran.
        cur.execute(f"SELECT COUNT(*) FROM {TABLE}")
        assert cur.fetchone()[0] == 1
        raise Boom("the body failed after writing")

    assert _count(handle) == 0


@needs_postgres
def test_the_advisory_lock_is_transaction_scoped(handle):
    """The property Wave 2 stakes its correctness on, both halves falsifiable.

    While the block is open, a rival connection must be REFUSED the lock --
    without that assertion, a transaction() that silently stopped opening a
    transaction would still go green, because pg_advisory_xact_lock on
    autocommit degenerates to a lock held for one statement. And after the
    block, a second, separate transaction must take the lock without blocking
    and without anyone having called an unlock: transaction scope IS the
    release mechanism.
    """
    rival = db.Database()
    try:
        with handle.transaction() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(%s)", (db.CAP_LOCK_KEY,))
            cur.fetchone()

            # The rival's try-lock runs in its own (implicit) transaction on a
            # different pooled connection -- the holder's is still checked out.
            refused = rival.fetchone(
                "SELECT pg_try_advisory_xact_lock(%s) AS taken", (db.CAP_LOCK_KEY,)
            )
            assert refused["taken"] is False, "a rival took a lock the open transaction holds"

        # No unlock was ever issued; COMMIT is what released it. try_ rather
        # than the blocking form, so a leak fails fast instead of hanging the
        # suite until the statement timeout.
        with rival.transaction() as cur:
            cur.execute("SELECT pg_try_advisory_xact_lock(%s)", (db.CAP_LOCK_KEY,))
            assert cur.fetchone()[0] is True, "the lock outlived the transaction that took it"
    finally:
        rival.close()
