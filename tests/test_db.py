"""
The pooled Postgres layer.

`db.py` is the phase's main risk surface and had no test module of its own --
it was covered only indirectly, through the store contract suite, and only when
a real server was configured. These tests need no server: they exercise the
configuration readers, the per-DSN pool registry, the disposal refcount and the
retry narrowing against fakes, plus one deliberately unreachable DSN for the
timing claim.

Following the repo convention: no conftest.py, fakes live here in the owning
module, `monkeypatch.setenv` for the env cases.
"""

import pytest

from research_agent import db

# --------------------------------------------------------------------------
# Config readers
# --------------------------------------------------------------------------

POOL_VARS = [
    "PG_POOL_MIN_SIZE",
    "PG_POOL_MAX_SIZE",
    "PG_POOL_TIMEOUT",
    "PG_STATEMENT_TIMEOUT",
    "PG_TCP_USER_TIMEOUT",
    "PG_CONNECT_TIMEOUT",
]


@pytest.fixture
def clean_env(monkeypatch):
    """A developer with PG_* exported must not change what the defaults are."""
    for name in POOL_VARS:
        monkeypatch.delenv(name, raising=False)


def test_pool_sizing_configurable_defaults(clean_env):
    assert db.pool_min_size() == 1
    assert db.pool_max_size() == 5
    assert db.pool_timeout() == 2.0


def test_pool_sizing_configurable_from_the_environment(clean_env, monkeypatch):
    monkeypatch.setenv("PG_POOL_MIN_SIZE", "2")
    monkeypatch.setenv("PG_POOL_MAX_SIZE", "12")
    monkeypatch.setenv("PG_POOL_TIMEOUT", "0.5")
    assert db.pool_min_size() == 2
    assert db.pool_max_size() == 12
    assert db.pool_timeout() == 0.5


def test_pool_sizing_configurable_survives_nonsense(clean_env, monkeypatch):
    """A typo in a Fly secret must not stop the process booting."""
    for name in POOL_VARS:
        monkeypatch.setenv(name, "banana")
    assert db.pool_min_size() == 1
    assert db.pool_max_size() == 5
    assert db.pool_timeout() == 2.0
    assert db.statement_timeout_ms() == 10000
    assert db.tcp_user_timeout_ms() == 2000


def test_pool_sizing_configurable_max_is_clamped_up_to_min(clean_env, monkeypatch):
    """psycopg raises when max_size < min_size, so the forgiving reading of a
    typo is to clamp rather than to refuse to start."""
    monkeypatch.setenv("PG_POOL_MIN_SIZE", "4")
    monkeypatch.setenv("PG_POOL_MAX_SIZE", "2")
    assert db.pool_max_size() == 4


def test_pool_sizing_configurable_has_floors(clean_env, monkeypatch):
    monkeypatch.setenv("PG_POOL_MIN_SIZE", "-3")
    monkeypatch.setenv("PG_POOL_TIMEOUT", "0")
    assert db.pool_min_size() == 0
    assert db.pool_timeout() == 0.1


def test_connection_bounds_defaults(clean_env):
    assert db.statement_timeout_ms() == 10000
    assert db.tcp_user_timeout_ms() == 2000


def test_connection_bounds_are_configurable(clean_env, monkeypatch):
    monkeypatch.setenv("PG_STATEMENT_TIMEOUT", "0")
    monkeypatch.setenv("PG_TCP_USER_TIMEOUT", "0")
    # 0 keeps libpq's own meaning -- "no bound" -- rather than an invented one.
    assert db.statement_timeout_ms() == 0
    assert db.tcp_user_timeout_ms() == 0
