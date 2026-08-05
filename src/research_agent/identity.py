"""
Caller identity without a wall.

Every visitor gets a signed, anonymous identity token in an HttpOnly cookie,
minted silently on their first response. Possession of the token IS the
authentication -- there is no signup, no password, and deliberately no 401
anywhere in this module: a tampered or garbage token verifies as None and the
caller simply gets a fresh identity. An attacker who forges a token gains a
new empty identity, never someone else's.

Token format (LOCKED, 12-CONTEXT Transport):

    v1.<uuid4 hex>.<hmac-sha256 hex over "v1.<id>">

Signed with stdlib `hmac` -- a signing library buys nothing this needs. The
secret
is IDENTITY_SIGNING_SECRET (a Fly app secret, shared by both machines). When
it is unset the module degrades to a per-process random secret: identities
then survive only as long as the process and differ between machines, which
is acceptable because per-identity limits are fairness only -- the global
spend cap remains the bound on the bill either way.

The cookie is minted by IdentityMiddleware, a pure-ASGI middleware rather
than a FastAPI dependency, because `/research/stream`, `/ask/stream` and
`GET /` all return Response objects directly and FastAPI drops
dependency-set cookies on those. The middleware is the one choke point that
covers every response shape, and it appends Set-Cookie at
`http.response.start` -- before any stream body, so an SSE response carries
it too.
"""

from __future__ import annotations

import contextlib
import hashlib
import hmac
import http.cookies
import os
import secrets
import threading
import uuid

from starlette.datastructures import MutableHeaders

from research_agent.observability import get_logger

log = get_logger()

COOKIE_NAME = "ra_id"
#: ~400 days, Chrome's cap. Identity deliberately outlives the 7-day session
#: expiry: a returning visitor keeps who they are; their old sessions are gone.
COOKIE_MAX_AGE = 34560000
TOKEN_VERSION = "v1"

# The per-process fallback secret, generated lazily on first use when
# IDENTITY_SIGNING_SECRET is unset. Cached so identity is at least stable
# within the process -- re-generating per call would re-mint every request.
_ephemeral_secret: bytes | None = None
_ephemeral_lock = threading.Lock()


def _reset_secret_cache() -> None:
    """Drop the cached ephemeral secret. For tests."""
    global _ephemeral_secret
    with _ephemeral_lock:
        _ephemeral_secret = None


def _secret() -> bytes:
    """The signing secret, read from the environment per call (the same
    convention as limits.sessions_token(), for the same monkeypatch reason).

    Unset means degrade, not fail: generate one random per-process secret,
    warn once, and keep serving. The demo stays up; identities just don't
    survive a restart or span machines, and the global cap still bounds
    the bill.
    """
    configured = os.environ.get("IDENTITY_SIGNING_SECRET", "")
    if configured:
        return configured.encode()

    global _ephemeral_secret
    with _ephemeral_lock:
        if _ephemeral_secret is None:
            _ephemeral_secret = secrets.token_hex(32).encode()
            log.warning(
                "IDENTITY_SIGNING_SECRET is unset; using an ephemeral "
                "per-machine identity secret. Identities will not survive a "
                "restart or span machines; the global spend cap remains the "
                "bound.",
                extra={"event": "identity_secret_ephemeral"},
            )
        return _ephemeral_secret


def _sign(ident: str) -> str:
    return hmac.new(
        _secret(), f"{TOKEN_VERSION}.{ident}".encode(), hashlib.sha256
    ).hexdigest()


def mint() -> str:
    """A fresh signed identity token.

    Public on purpose: the middleware is not dependency-overridable, so tests
    that need a fixed identity mint a real token (with a monkeypatched secret)
    and present it as a cookie -- exercising the real verify path.
    """
    ident = uuid.uuid4().hex
    return f"{TOKEN_VERSION}.{ident}.{_sign(ident)}"


def verify(token: str | None) -> str | None:
    """The identity inside a token, or None.

    Never raises: the token is attacker-supplied on every request, so every
    malformed shape -- wrong version, wrong part count, non-alnum id, bad
    signature, None -- is the same answer. The comparison is constant-time
    (compare_digest), mirroring limits.py.
    """
    if not token or not isinstance(token, str):
        return None
    parts = token.split(".")
    if len(parts) != 3:
        return None
    version, ident, sig = parts
    if version != TOKEN_VERSION or not ident or not ident.isalnum():
        return None
    if not hmac.compare_digest(sig, _sign(ident)):
        return None
    return ident


def set_cookie_value(token: str) -> str:
    """The exact Set-Cookie header value, attributes LOCKED by 12-CONTEXT.

    `Secure` is unconditional -- no prod/test fork in a security attribute.
    Tests use base_url="https://testserver" instead. No Domain: host-only
    is tighter.
    """
    return (
        f"{COOKIE_NAME}={token}; Max-Age={COOKIE_MAX_AGE}; Path=/; "
        f"HttpOnly; SameSite=Lax; Secure"
    )


class IdentityMiddleware:
    """Resolve-or-mint the caller's identity for every http request.

    Pure ASGI, mint-on-response, never 401. Always calls the downstream app;
    always sets scope["state"]["identity"] first, so request.state.identity
    is guaranteed for every handler. Appends Set-Cookie at
    http.response.start only when this request minted -- a valid cookie is
    left untouched.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        cookie_header = ""
        for name, value in scope.get("headers", []):
            if name == b"cookie":
                cookie_header = value.decode("latin-1")
                break

        # SimpleCookie rather than a hand-rolled split: cookie headers carry
        # quoting and multiple pairs, and it never raises on garbage input
        # via load() -- it just skips what it cannot parse.
        jar = http.cookies.SimpleCookie()
        with contextlib.suppress(http.cookies.CookieError):  # pragma: no cover
            jar.load(cookie_header)
        morsel = jar.get(COOKIE_NAME)

        minted: str | None = None
        ident = verify(morsel.value if morsel else None)
        if ident is None:
            minted = mint()
            ident = verify(minted)

        scope.setdefault("state", {})["identity"] = ident

        async def send_with_cookie(message):
            if minted and message["type"] == "http.response.start":
                MutableHeaders(scope=message).append(
                    "set-cookie", set_cookie_value(minted)
                )
            await send(message)

        await self.app(scope, receive, send_with_cookie)
