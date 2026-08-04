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

import hmac
import os
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

DAY_SECONDS = 24 * 60 * 60
HOUR_SECONDS = 60 * 60


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
