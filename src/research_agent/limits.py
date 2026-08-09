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

    DEMO_RATE_LIMIT_PER_HOUR per caller identity, sliding window (default 10).
                             Stops one person or one crawler monopolising it.
                             Keyed on the signed identity cookie, not on the
                             client address: the address arrived in a header
                             that only Fly's proxy makes unforgeable, and a
                             deployment behind anything else had to opt into
                             trusting it. The identity is signed by us.

    DEMO_DAILY_USD_CAP       rolling 24h spend across every caller (default
                             $5). The backstop, and the reason per-identity
                             fairness is safe to offer at all: identities are
                             free to mint, so nothing about them bounds the
                             bill. This does. It counts in-flight runs as well
                             as finished ones -- see DEMO_RESERVED_RUN_USD.

    DEMO_RESERVED_RUN_USD    what a starting run claims against the cap before
                             it has spent anything (default $0.20, about what
                             a run actually costs). Settled to the real figure
                             when the run finishes. Without it the cap counts
                             only completed runs, so a burst of concurrent
                             runs each sees the same pre-burst total and they
                             all pass -- the cap overshoots by roughly the
                             concurrency.

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
    """Requests per caller identity per hour. 0 disables."""
    return _env_int("DEMO_RATE_LIMIT_PER_HOUR", 10)


def daily_cap_usd() -> float:
    """Rolling 24h spend ceiling across all callers. 0 disables."""
    return _env_float("DEMO_DAILY_USD_CAP", 5.00)


def reserved_run_usd() -> float:
    """What a starting run claims against the cap. Floor 0, default 0.20.

    Sized on observation, not on the per-run hard cap: runs land around $0.15
    and AGENT_MAX_RUN_COST_USD's $1.00 default would let only five run at once
    against a $5 budget -- throttling the demo far below what it actually
    spends. An estimate that is honest keeps the cap a bound rather than a
    queue.

    Phase 14 settles against *multiplied* cost (discount x geo) plus embedding
    spend, and this default survives it unchanged: at ~$0.15 a run, the $0.20
    reservation only under-estimates once the combined multiplier passes about
    1.33, which the published 1.1 cannot reach with any discount at or below
    1.0 -- and a discount below 1.0 makes the reservation more conservative,
    never less. See docs/OPERATIONS.md.
    """
    return max(0.0, _env_float("DEMO_RESERVED_RUN_USD", 0.20))


def caller_identity(request: Request) -> str:
    """The key every per-caller limit uses.

    IdentityMiddleware sets this on every request before any handler runs, so
    the fallback should never fire. It falls back to one SHARED bucket rather
    than to `client_ip` on purpose: a shared bucket is more restrictive than
    the truth, which is the safe direction, whereas falling back to the address
    would quietly reinstate the forgeable key this phase removed -- and it
    would do it exactly when the identity layer was broken, i.e. when nobody
    was looking.
    """
    return getattr(getattr(request, "state", None), "identity", "") or "anonymous"


def client_ip(request: Request) -> str:
    """The caller's address. FOR LOGGING ONLY -- not load-bearing for fairness.

    Kept because an address is genuinely useful in a log line when diagnosing
    abuse. It is deliberately no longer what the rate limiter keys on: see
    `caller_identity`. Do not key any limit on this, and do not reintroduce
    TRUST_FORWARDED_FOR into a decision that costs money -- the header is
    caller-controlled against an unproxied origin, which is what made the old
    rate limiter a formality for anyone who read the code.

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


# The process-global limiter that used to live here is gone. It was the thing
# that made "the rate limit" mean something different on each machine, and a
# module global is not something a request can be pointed away from -- so the
# window now lives in a LimitsStore the service builds at startup and injects,
# which is what lets the fleet share one. RateLimiter itself survives as
# InMemoryLimits' internals.


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
    """The OPERATOR credential for the session tree.

    Separate from DEMO_TOKEN because the two protect different things. The
    demo page sends no auth header, so setting DEMO_TOKEN in production would
    401 every anonymous visitor on POST /research/stream and kill the public
    demo -- which is the whole point of deploying this.

    Its role changed in Phase 12 and the name outlived the change. Before, this
    was *the* credential for reading sessions at all; now every caller reads
    their own sessions through their signed identity, and this token buys the
    one thing identity cannot: the unscoped, cross-owner debugging view.

    DEMO_TOKEN is still honoured as a fallback, which is what makes "setting
    DEMO_TOKEN protects the session endpoints" true rather than quietly false.

    Read per call, not cached in a module constant: tests flip it with
    monkeypatch.setenv between cases.
    """
    return os.environ.get("SESSIONS_TOKEN", "").strip() or demo_token()


def require_session_access(request: Request) -> tuple[str, str | None]:
    """Who is asking about sessions, and in which mode.

    Returns ("operator", None) for a caller presenting the configured
    SESSIONS_TOKEN -- unscoped, every owner's sessions, the debugging view --
    and ("identity", <id>) for everyone else, scoped to their own.

    THE FAIL-CLOSED PROPERTY INVERTED HERE, DELIBERATELY. This used to raise
    403 when no token was configured, so that forgetting the secret could not
    silently reopen the hole that left every stored report world-readable. That
    reasoning was right while the token was the *only* thing standing between a
    stranger and someone else's research. It is no longer the only thing: a
    session now records its owner, and `service._require` refuses anyone else
    with a 404 that is byte-identical to a missing session. So an unset
    SESSIONS_TOKEN closes the OPERATOR view and nothing else -- visitors still
    reach their own sessions, and reach nobody else's, with or without it.

    Which is why this function never raises. Refusal moved from "do you hold
    the shared secret" to "is this yours", and the second question has an answer
    for every caller. ADR-0007 records the reversal.
    """
    token = sessions_token()
    supplied = request.headers.get("x-demo-token", "")
    # Constant-time compare, and only after both sides are known non-empty:
    # an unset token must not be matchable by an unset header.
    if token and supplied and hmac.compare_digest(supplied, token):
        return ("operator", None)
    return ("identity", caller_identity(request))


def check_rate_limit(request: Request, limits_store: LimitsStore) -> None:
    allowed, retry_after = limits_store.check_rate(
        caller_identity(request), rate_limit_per_hour(), HOUR_SECONDS
    )
    if not allowed:
        raise HTTPException(
            429,
            f"Rate limit exceeded: {rate_limit_per_hour()} requests per hour. "
            f"Try again in {retry_after}s.",
            headers={"Retry-After": str(retry_after)},
        )


def enforce(request: Request, metrics, limits_store: LimitsStore) -> None:
    """The gates that can be decided before a run exists, cheapest first.

    Token before rate limit so an unauthorised caller can't consume another
    caller's quota.

    THE SPEND CAP IS DELIBERATELY NOT HERE ANY MORE. It needs a run_id to
    reserve against, which does not exist until the handler has built the run
    state -- so it moved to `reserve_or_429`, called inside each spending
    handler. `metrics` stays in the signature because the caller has it and a
    guard that cannot see spend is a guard one refactor away from needing it
    again; nothing in this function reads it today.
    """
    check_token(request)
    check_rate_limit(request, limits_store)


def reserve_or_429(limits_store: LimitsStore, run_id: str, identity: str, metrics) -> None:
    """Claim this run's estimated cost against the daily cap, or refuse it.

    The refusal is raised synchronously, before any streaming response has been
    started, so a capped caller gets a real 429 rather than a 200 whose body
    turns out to be an error event.
    """
    cap = daily_cap_usd()
    if cap <= 0:
        return  # disabled: no reservation, and no spend query to pay for

    spent = metrics.spend_since(time.time() - DAY_SECONDS)
    if limits_store.reserve(run_id, identity, reserved_run_usd(), cap, spent):
        return

    raise HTTPException(
        429,
        f"This demo has spent its daily budget (${spent:.2f} of ${cap:.2f} "
        f"in the last 24h). Read-only endpoints still work.",
        headers={"Retry-After": str(HOUR_SECONDS)},
    )


def settle(limits_store: LimitsStore, run_id: str) -> None:
    """Release a run's reservation now that its real cost has been recorded.

    Never raises. A settle that fails must not turn a finished run into a 500
    or truncate a stream that already delivered its result -- and the failure
    is survivable, because RESERVATION_STALE_SECONDS stops the orphan counting
    against the cap either way. Logged, so the leak is visible rather than
    merely tolerated.
    """
    try:
        limits_store.settle(run_id)
    except Exception as exc:  # noqa: BLE001 - see the docstring
        log.warning(
            "reservation settle failed",
            extra={"event": "settle_failed", "run_id": run_id, "error": type(exc).__name__},
        )


def status(metrics) -> dict:
    """What the demo page shows, and what /health reports.

    ADDITIVE ONLY. The deployed page is served from the same repo but the
    browser tab that is already open is not, so a renamed or removed key breaks
    a live client for as long as it stays open. New fields go on the end.
    """
    cap = daily_cap_usd()
    spent = metrics.spend_since(time.time() - DAY_SECONDS) if cap > 0 else 0.0
    return {
        "token_required": bool(demo_token()),
        "rate_limit_per_hour": rate_limit_per_hour() or None,
        "daily_cap_usd": cap or None,
        "spent_24h_usd": round(spent, 4) if cap > 0 else None,
        "budget_exhausted": bool(cap > 0 and spent >= cap),
        # -- added Phase 12: what the limits are keyed on, and what a run
        # claims up front. The page copy that uses them lands with the UI wave.
        "rate_limit_scope": "identity",
        "reserved_run_usd": reserved_run_usd() if cap > 0 else None,
    }
