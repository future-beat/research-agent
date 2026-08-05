"""
Guardrails for a publicly reachable demo.

Every research request spends real money -- roughly $0.15 at current rates --
and the endpoints are unauthenticated by default so the URL can be shared.
Three independent limits, checked in the order they get cheaper to fail:

    DEMO_TOKEN               off by default. When set, write endpoints need
                             an X-Demo-Token header. This is the only one
                             that actually closes the service; the other two
                             bound the damage while it stays open.

    SESSIONS_TOKEN           the credential for the session read/delete tree
                             (/sessions and friends), sent in the same
                             X-Demo-Token header. Unlike DEMO_TOKEN it fails
                             closed: with nothing configured those endpoints
                             refuse everyone. DEMO_TOKEN is accepted as a
                             fallback value, so setting it protects the
                             session tree too -- but setting it in production
                             also closes the demo, which is why the sessions
                             credential is a separate variable.

    DEMO_RATE_LIMIT_PER_HOUR per client IP, sliding window (default 10).
                             Stops one person or one crawler monopolising it.

    DEMO_DAILY_USD_CAP       rolling 24h spend across every client (default
                             $5). The backstop: rate limits are per IP and a
                             botnet has many, but the bill is global.

The per-run cap in the supervisor bounds a single runaway run. It does
nothing about volume -- a thousand well-behaved runs is still a thousand
runs. That is what the daily cap is for.

Not every read is the same. Ops reads (/health, /metrics, /pricing, /memory,
the demo page) are never gated: they cost nothing, expose aggregates rather
than content, and are how you diagnose a service that is refusing work.
Session reads hand back other people's research, so they are gated -- see
SESSIONS_TOKEN above.
"""

from __future__ import annotations

import contextlib
import hmac
import logging
import os
import threading
import time
from abc import ABC, abstractmethod
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from research_agent import db

log = logging.getLogger("research_agent.limits")

DAY_SECONDS = 24 * 60 * 60
HOUR_SECONDS = 60 * 60

#: How long a reservation counts against the cap before it is treated as
#: abandoned. A run takes tens of seconds and the per-run cap bounds the rest;
#: nothing legitimate is still going after fifteen minutes. Without this a
#: process killed mid-run (a Fly machine restart, an OOM) leaves a row that
#: silently shrinks the demo's budget for the life of the database.
RESERVATION_STALE_SECONDS = 900


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ[name])
    except (KeyError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ[name])
    except (KeyError, ValueError):
        return default


def demo_token() -> str:
    return os.environ.get("DEMO_TOKEN", "").strip()


def rate_limit_per_hour() -> int:
    """Requests per client IP per hour. 0 disables."""
    return _env_int("DEMO_RATE_LIMIT_PER_HOUR", 10)


def daily_cap_usd() -> float:
    """Rolling 24h spend ceiling across all clients. 0 disables."""
    return _env_float("DEMO_DAILY_USD_CAP", 5.00)


def client_ip(request: Request) -> str:
    """The caller's address, preferring headers that can't be forged.

    `Fly-Client-IP` is set by Fly's proxy and overwritten on every inbound
    request, so a client cannot inject it. `X-Forwarded-For` can be set by
    anyone talking to an unproxied origin, which would turn the rate limiter
    into a formality -- so it is only consulted when TRUST_FORWARDED_FOR is
    explicitly on, for deployments behind a different proxy.
    """
    fly = request.headers.get("fly-client-ip")
    if fly:
        return fly.strip()

    if os.environ.get("TRUST_FORWARDED_FOR", "").strip().lower() in ("1", "true", "yes"):
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()

    return request.client.host if request.client else "unknown"


class RateLimiter:
    """Fixed-capacity sliding window per key, in memory.

    Per process, so two machines each allow the full quota. That is a real
    limitation and the daily spend cap is what covers it -- this exists to
    stop one client hammering one machine, not to be the last line.
    """

    #: Sweep expired keys every N checks. Keys go quiet and never come back,
    #: so without this the dict grows for the life of the process -- slowly,
    #: but on a public endpoint that is an unbounded leak.
    SWEEP_EVERY = 500

    def __init__(self, limit: int, window_seconds: int = HOUR_SECONDS):
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()
        self._checks = 0

    def check(self, key: str, now: float | None = None) -> tuple[bool, int]:
        """Record a hit. Returns (allowed, seconds_until_retry)."""
        if self.limit <= 0:
            return True, 0

        now = time.time() if now is None else now
        with self._lock:
            self._checks += 1
            if self._checks % self.SWEEP_EVERY == 0:
                self._sweep(now)

            hits = self._hits[key]
            cutoff = now - self.window
            while hits and hits[0] <= cutoff:
                hits.popleft()

            if len(hits) >= self.limit:
                # The oldest hit is the one that has to age out.
                return False, max(1, int(hits[0] + self.window - now) + 1)

            hits.append(now)
            return True, 0

    def _sweep(self, now: float) -> None:
        """Drop keys with no hits left inside the window. Caller holds the lock."""
        cutoff = now - self.window
        for key in [k for k, hits in self._hits.items() if not hits or hits[-1] <= cutoff]:
            del self._hits[key]

    def tracked_keys(self) -> int:
        with self._lock:
            return len(self._hits)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


# One limiter per process, sized on first use so the env var is read after
# the app has loaded its configuration.
_limiter: RateLimiter | None = None
_limiter_lock = threading.Lock()


def limiter() -> RateLimiter:
    global _limiter
    with _limiter_lock:
        if _limiter is None or _limiter.limit != rate_limit_per_hour():
            _limiter = RateLimiter(rate_limit_per_hour())
        return _limiter


def reset_limiter() -> None:
    """Drop all recorded hits. For tests, and for an operator who has just
    raised the limit and doesn't want to wait out the old window."""
    global _limiter
    with _limiter_lock:
        _limiter = None


# --------------------------------------------------------------------------
# The limits store: rate window + spend reservations, memory or Postgres
# --------------------------------------------------------------------------
#
# Both pieces of state used to live in this process. Two machines therefore
# enforced two of everything: each allowed the full hourly quota, and each
# counted only the spend its own requests recorded. The store seam is the same
# one SessionStore and MetricsStore use -- an ABC, a memory backend for the
# fast test path and SQLite/JSON deployments, a Postgres backend for the fleet,
# and a get_*_store() that defaults on DATABASE_URL.
#
# The two halves have deliberately different strictness, and confusing them is
# the expensive mistake:
#
#   check_rate  is a FAIRNESS tool. It stops one caller monopolising the demo.
#               A small overshoot under concurrency costs nothing, so it is one
#               statement and one round trip.
#
#   reserve     is a MONEY tool. It is the bound on the invoice, so it must be
#               race-free: check-and-insert inside one transaction holding
#               pg_advisory_xact_lock. A single conditional INSERT is NOT
#               race-free under READ COMMITTED -- two concurrent guards each
#               evaluate the WHERE against a snapshot that excludes the other's
#               uncommitted row, and both pass.


class LimitsStore(ABC):
    """Where the rate window and the in-flight spend reservations live."""

    @abstractmethod
    def check_rate(self, identity: str, limit: int, window: int) -> tuple[bool, int]:
        """Record a hit for `identity`. Returns (allowed, seconds_until_retry)."""

    @abstractmethod
    def reserve(
        self, run_id: str, identity: str, est_usd: float, cap: float, spent_24h: float
    ) -> bool:
        """Claim `est_usd` of the daily cap for a run that is about to start.

        True iff `spent_24h + <live reservations> + est_usd <= cap`, in which
        case the reservation is recorded. A cap of 0 disables the check and
        records nothing.
        """

    @abstractmethod
    def settle(self, run_id: str) -> None:
        """Release a reservation. Idempotent: the run's real cost has landed in
        the metrics table by now, so the estimate must stop counting."""

    @abstractmethod
    def reservation_ids(self) -> set[str]:
        """The run_ids currently holding a reservation. For tests and /demo."""

    def close(self) -> None:
        """Release any backend resources.

        Concrete rather than abstract: the memory backend has nothing to
        release, and forcing every backend to write an empty override is how
        you end up with a close() that exists and does nothing by accident
        rather than on purpose.
        """
        return None


class InMemoryLimits(LimitsStore):
    """Per-process limits. Correct on one machine, and honest about that.

    Kept for the SQLite/JSON deployment shape and for the test path, which
    should not need a database to exercise the reserve/settle contract. On two
    machines this enforces two windows and two budgets -- which is exactly the
    defect PostgresLimits exists to fix, so nothing here should be mistaken for
    the production path.
    """

    def __init__(self):
        self._limiter: RateLimiter | None = None
        self._reservations: dict[str, tuple[str, float, float]] = {}
        self._lock = threading.Lock()

    def check_rate(self, identity: str, limit: int, window: int) -> tuple[bool, int]:
        with self._lock:
            if (
                self._limiter is None
                or self._limiter.limit != limit
                or self._limiter.window != window
            ):
                self._limiter = RateLimiter(limit, window)
            limiter = self._limiter
        return limiter.check(identity)

    def reserve(
        self, run_id: str, identity: str, est_usd: float, cap: float, spent_24h: float
    ) -> bool:
        if cap <= 0:
            return True
        now = time.time()
        cutoff = now - RESERVATION_STALE_SECONDS
        with self._lock:
            for stale in [k for k, (_, _, at) in self._reservations.items() if at < cutoff]:
                del self._reservations[stale]
            reserved = sum(est for _, est, _ in self._reservations.values())
            if spent_24h + reserved + est_usd > cap:
                return False
            self._reservations[run_id] = (identity, est_usd, now)
            return True

    def settle(self, run_id: str) -> None:
        with self._lock:
            self._reservations.pop(run_id, None)

    def reservation_ids(self) -> set[str]:
        with self._lock:
            return set(self._reservations)


POSTGRES_SCHEMA = """
CREATE TABLE IF NOT EXISTS rate_hits (
    identity   TEXT NOT NULL,
    ts         DOUBLE PRECISION NOT NULL
);
CREATE INDEX IF NOT EXISTS rate_hits_identity_ts ON rate_hits (identity, ts DESC);
CREATE TABLE IF NOT EXISTS run_reservations (
    run_id     TEXT PRIMARY KEY,
    identity   TEXT NOT NULL,
    est_usd    DOUBLE PRECISION NOT NULL,
    created_at DOUBLE PRECISION NOT NULL
);
CREATE INDEX IF NOT EXISTS run_reservations_created_at ON run_reservations (created_at DESC);
"""

# One statement, one round trip: the row is inserted only if the identity is
# under its limit, and RETURNING tells us which happened. The residual race --
# two concurrent inserts both passing the subquery -- bounds the overshoot at
# the number of simultaneous requests, which for a fairness tool is a fine
# trade for not taking a lock on every request. The cap, where a race costs
# money, does NOT get this treatment. See `reserve`.
_RATE_SQL = """
INSERT INTO rate_hits (identity, ts)
SELECT %(identity)s, %(now)s
WHERE (
    SELECT COUNT(*) FROM rate_hits
    WHERE identity = %(identity)s AND ts > %(cutoff)s
) < %(limit)s
RETURNING ts
"""

# The money statement. Everything that makes it safe is in the transaction
# around it (see `reserve`): this text alone would race.
_RESERVE_SQL = """
INSERT INTO run_reservations (run_id, identity, est_usd, created_at)
SELECT %(run_id)s, %(identity)s, %(est)s, %(now)s
WHERE (
    %(spent)s
    + COALESCE((SELECT SUM(est_usd) FROM run_reservations WHERE created_at >= %(cutoff)s), 0)
    + %(est)s
) <= %(cap)s
RETURNING run_id
"""


class PostgresLimits(LimitsStore):
    """One rate window and one budget for the whole fleet."""

    #: Purge expired rows every Nth call rather than on every one. The
    #: in-memory limiter's SWEEP_EVERY is the precedent and the reason is the
    #: same: rows accumulate for every visitor who ever showed up, and a DELETE
    #: on the hot path to reclaim a handful of rows is a bad trade.
    SWEEP_EVERY = 500

    def __init__(self, dsn: str | None = None, database: db.Database | None = None):
        self.db = database or db.Database(dsn)
        self.db.ensure_schema(POSTGRES_SCHEMA)
        self._checks = 0
        self._checks_lock = threading.Lock()

    def _due_for_sweep(self) -> bool:
        with self._checks_lock:
            self._checks += 1
            return self._checks % self.SWEEP_EVERY == 0

    def check_rate(self, identity: str, limit: int, window: int) -> tuple[bool, int]:
        if limit <= 0:
            return True, 0
        now = time.time()
        cutoff = now - window
        row = self.db.fetchone(
            _RATE_SQL,
            {"identity": identity, "now": now, "cutoff": cutoff, "limit": limit},
        )
        if self._due_for_sweep():
            with contextlib.suppress(Exception):  # housekeeping never fails a request
                self.db.execute("DELETE FROM rate_hits WHERE ts < %s", (cutoff,))
        if row is not None:
            return True, 0

        # Refused: the oldest hit still inside the window is the one that has
        # to age out before this caller gets another turn.
        oldest = self.db.fetchone(
            "SELECT MIN(ts) AS ts FROM rate_hits WHERE identity = %s AND ts > %s",
            (identity, cutoff),
        )
        first = (oldest or {}).get("ts") or now
        return False, max(1, int(first + window - now) + 1)

    def reserve(
        self, run_id: str, identity: str, est_usd: float, cap: float, spent_24h: float
    ) -> bool:
        """Check-and-insert, serialised across every machine.

        `pg_advisory_xact_lock` rather than the session-scoped variant: the
        lock is released at COMMIT *or* ROLLBACK, so a caller that dies
        mid-reservation cannot leave it held on a connection already handed
        back to the pool. CAP_LOCK_KEY is deliberately not SCHEMA_LOCK_KEY --
        sharing one key would serialise cap accounting against schema DDL.
        """
        if cap <= 0:
            return True
        from psycopg.rows import dict_row

        now = time.time()
        params = {
            "run_id": run_id,
            "identity": identity,
            "est": est_usd,
            "now": now,
            "cutoff": now - RESERVATION_STALE_SECONDS,
            "spent": spent_24h,
            "cap": cap,
        }
        with self.db.transaction(row_factory=dict_row) as cur:
            cur.execute("SELECT pg_advisory_xact_lock(%s)", (db.CAP_LOCK_KEY,))
            cur.execute(_RESERVE_SQL, params)
            return cur.fetchone() is not None

    def settle(self, run_id: str) -> None:
        self.db.execute("DELETE FROM run_reservations WHERE run_id = %s", (run_id,))
        if self._due_for_sweep():
            with contextlib.suppress(Exception):
                self.db.execute(
                    "DELETE FROM run_reservations WHERE created_at < %s",
                    (time.time() - RESERVATION_STALE_SECONDS,),
                )

    def reservation_ids(self) -> set[str]:
        rows = self.db.fetchall("SELECT run_id FROM run_reservations")
        return {row["run_id"] for row in rows}

    def close(self) -> None:
        self.db.close()


BACKENDS = {"memory": InMemoryLimits, "postgres": PostgresLimits}


def default_backend() -> str:
    """Postgres when a DSN is configured, per-process memory otherwise.

    Follows sessions and metrics rather than inventing a rule: a deploy that
    provisions a database gets fleet-wide limits without a second setting to
    forget, and forgetting it is how you end up with two machines quietly
    enforcing two budgets.
    """
    return os.environ.get("LIMITS_BACKEND", "").strip().lower() or (
        "postgres" if db.postgres_configured() else "memory"
    )


def get_limits_store(backend: str | None = None) -> LimitsStore:
    name = (backend or default_backend()).strip().lower()
    try:
        cls = BACKENDS[name]
    except KeyError:
        raise ValueError(
            f"Unknown LIMITS_BACKEND {name!r}. Choose one of: {', '.join(sorted(BACKENDS))}."
        ) from None
    return cls()


def check_token(request: Request) -> None:
    token = demo_token()
    if not token:
        return
    supplied = request.headers.get("x-demo-token", "")
    # Constant-time-ish: compare full strings rather than short-circuiting on
    # the first differing byte. Not a serious timing target, but free.
    if not supplied or not hmac.compare_digest(supplied, token):
        raise HTTPException(401, "A valid X-Demo-Token header is required.")


def sessions_token() -> str:
    """The credential for the session read/delete endpoints.

    Separate from DEMO_TOKEN because the two protect different things. The
    demo page sends no auth header, so setting DEMO_TOKEN in production would
    401 every anonymous visitor on POST /research/stream and kill the public
    demo -- which is the whole point of deploying this. SESSIONS_TOKEN closes
    the session tree without touching the demo.

    DEMO_TOKEN is still honoured as a fallback, which is what makes "setting
    DEMO_TOKEN protects the session endpoints" true rather than quietly false.

    Read per call, not cached in a module constant: tests flip it with
    monkeypatch.setenv between cases.
    """
    return os.environ.get("SESSIONS_TOKEN", "").strip() or demo_token()


def require_sessions_token(request: Request) -> None:
    """Session-endpoint credential check. Fails closed.

    Deliberately not check_token. That one returns early when no token is
    configured, which is right for the demo write path and was exactly what
    left every stored report world-readable on the deployed service: the
    control was present in the code and inert in production. Here an unset
    credential means nobody passes, so forgetting the secret cannot silently
    reopen the hole.

    403 when nothing is configured (no one can pass), 401 when a credential
    exists and the caller's is missing or wrong.
    """
    token = sessions_token()
    if not token:
        raise HTTPException(403, "Session endpoints are closed: no SESSIONS_TOKEN is set.")

    supplied = request.headers.get("x-demo-token", "")
    if not supplied or not hmac.compare_digest(supplied, token):
        raise HTTPException(401, "A valid X-Demo-Token header is required.")


def check_rate_limit(request: Request) -> None:
    allowed, retry_after = limiter().check(client_ip(request))
    if not allowed:
        raise HTTPException(
            429,
            f"Rate limit exceeded: {rate_limit_per_hour()} requests per hour. "
            f"Try again in {retry_after}s.",
            headers={"Retry-After": str(retry_after)},
        )


def check_daily_cap(metrics) -> None:
    cap = daily_cap_usd()
    if cap <= 0:
        return
    spent = metrics.spend_since(time.time() - DAY_SECONDS)
    if spent >= cap:
        raise HTTPException(
            429,
            f"This demo has spent its daily budget (${spent:.2f} of ${cap:.2f} "
            f"in the last 24h). Read-only endpoints still work.",
            headers={"Retry-After": str(HOUR_SECONDS)},
        )


def enforce(request: Request, metrics) -> None:
    """Every gate, cheapest first.

    Token before rate limit so an unauthorised caller can't consume another
    client's quota; rate limit before the spend query so a flood costs no
    database round trips.
    """
    check_token(request)
    check_rate_limit(request)
    check_daily_cap(metrics)


def status(metrics) -> dict:
    """What the demo page shows, and what /health reports."""
    cap = daily_cap_usd()
    spent = metrics.spend_since(time.time() - DAY_SECONDS) if cap > 0 else 0.0
    return {
        "token_required": bool(demo_token()),
        "rate_limit_per_hour": rate_limit_per_hour() or None,
        "daily_cap_usd": cap or None,
        "spent_24h_usd": round(spent, 4) if cap > 0 else None,
        "budget_exhausted": bool(cap > 0 and spent >= cap),
    }
