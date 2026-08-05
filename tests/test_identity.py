"""
Unit tests for the signed identity token: mint, verify, and the middleware's
raw material. No app, no client -- the API half lives in test_service.py.

The security property under test is falsifiable by construction: a token
minted under secret A must verify under A AND fail under B, in the same test.
A presence gate ("compare_digest appears in the file") proves wiring; this
proves the HMAC actually rejects.
"""

import pytest

from research_agent import identity

SECRET_A = "secret-a-for-identity-tests"
SECRET_B = "secret-b-a-different-one"


@pytest.fixture(autouse=True)
def _fresh_secret_cache():
    """Every test starts and ends with no cached ephemeral secret, so an
    unset-secret test cannot leak its per-process secret into the next case."""
    identity._reset_secret_cache()
    yield
    identity._reset_secret_cache()


# --------------------------------------------------------------------------
# Token shape
# --------------------------------------------------------------------------


def test_mint_produces_the_locked_token_shape(monkeypatch):
    monkeypatch.setenv("IDENTITY_SIGNING_SECRET", SECRET_A)
    token = identity.mint()

    version, ident, sig = token.split(".")
    assert version == identity.TOKEN_VERSION == "v1"
    assert len(ident) == 32 and ident.isalnum()  # uuid4().hex
    assert len(sig) == 64  # hmac-sha256 hexdigest
    assert set(sig) <= set("0123456789abcdef")


def test_each_mint_is_a_fresh_identity(monkeypatch):
    """Same secret, two mints: both verify, but the ids differ (uuid4)."""
    monkeypatch.setenv("IDENTITY_SIGNING_SECRET", SECRET_A)
    first, second = identity.mint(), identity.mint()

    assert identity.verify(first) is not None
    assert identity.verify(second) is not None
    assert identity.verify(first) != identity.verify(second)


# --------------------------------------------------------------------------
# The HMAC actually rejects (falsifiable both ways in one test)
# --------------------------------------------------------------------------


def test_identity_hmac_verifies_under_its_secret_and_rejects_another(monkeypatch):
    monkeypatch.setenv("IDENTITY_SIGNING_SECRET", SECRET_A)
    token = identity.mint()
    ident = identity.verify(token)
    assert ident is not None and len(ident) == 32  # the positive half

    monkeypatch.setenv("IDENTITY_SIGNING_SECRET", SECRET_B)
    assert identity.verify(token) is None  # the negative half, same token


def test_a_tampered_signature_is_rejected(monkeypatch):
    monkeypatch.setenv("IDENTITY_SIGNING_SECRET", SECRET_A)
    token = identity.mint()
    version, ident, sig = token.split(".")

    flipped = sig[:-1] + ("0" if sig[-1] != "0" else "1")
    assert identity.verify(f"{version}.{ident}.{flipped}") is None


def test_a_swapped_id_under_a_real_signature_is_rejected(monkeypatch):
    """An attacker splicing their valid signature onto another id gets None --
    the signature covers the id, not just the version."""
    monkeypatch.setenv("IDENTITY_SIGNING_SECRET", SECRET_A)
    _, _, sig = identity.mint().split(".")
    _, other_id, _ = identity.mint().split(".")

    assert identity.verify(f"v1.{other_id}.{sig}") is None


@pytest.mark.parametrize(
    "garbage",
    [
        "",
        "nope",
        "v1.abc",  # two parts
        "v1.a.b.c",  # four parts
        "v1..",  # empty id and sig
        "v1.not-alnum!.deadbeef",
        None,
    ],
)
def test_invalid_token_reminted_unit_half_garbage_is_none_never_raises(monkeypatch, garbage):
    monkeypatch.setenv("IDENTITY_SIGNING_SECRET", SECRET_A)
    assert identity.verify(garbage) is None  # and it did not raise


def test_invalid_token_reminted_unit_half_wrong_version(monkeypatch):
    """A v2 token with an otherwise-perfect body is not a v1 token."""
    monkeypatch.setenv("IDENTITY_SIGNING_SECRET", SECRET_A)
    _, ident, sig = identity.mint().split(".")
    assert identity.verify(f"v2.{ident}.{sig}") is None


# --------------------------------------------------------------------------
# Degrade when the secret is unset
# --------------------------------------------------------------------------


def test_identity_secret_unset_degrades_to_ephemeral(monkeypatch, caplog):
    """No IDENTITY_SIGNING_SECRET: the module generates one per-process secret,
    warns once, and mint -> verify still round-trips. The demo keeps working;
    the global spend cap remains the bound."""
    monkeypatch.delenv("IDENTITY_SIGNING_SECRET", raising=False)
    identity._reset_secret_cache()

    with caplog.at_level("WARNING"):
        ident = identity.verify(identity.mint())

    assert ident is not None and len(ident) == 32 and ident.isalnum()
    assert any("ephemeral" in r.getMessage().lower() for r in caplog.records)


def test_the_ephemeral_secret_is_stable_within_the_process(monkeypatch):
    """Two mints under the unset-secret degrade verify against the SAME cached
    secret -- otherwise every request would re-mint and identity means nothing."""
    monkeypatch.delenv("IDENTITY_SIGNING_SECRET", raising=False)
    identity._reset_secret_cache()

    first, second = identity.mint(), identity.mint()
    assert identity.verify(first) is not None
    assert identity.verify(second) is not None


def test_the_ephemeral_warning_is_logged_once(monkeypatch, caplog):
    monkeypatch.delenv("IDENTITY_SIGNING_SECRET", raising=False)
    identity._reset_secret_cache()

    with caplog.at_level("WARNING"):
        identity.mint()
        identity.mint()
        identity.verify(identity.mint())

    warnings = [r for r in caplog.records if "ephemeral" in r.getMessage().lower()]
    assert len(warnings) == 1


# --------------------------------------------------------------------------
# The cookie string the middleware will send
# --------------------------------------------------------------------------


def test_set_cookie_value_carries_the_locked_attributes(monkeypatch):
    """The LOCKED contract, verbatim: HttpOnly; SameSite=Lax; Secure;
    Max-Age=34560000; Path=/; no Domain. Asserted attribute by attribute so a
    failure names what drifted."""
    monkeypatch.setenv("IDENTITY_SIGNING_SECRET", SECRET_A)
    token = identity.mint()
    header = identity.set_cookie_value(token)

    assert header.startswith(f"{identity.COOKIE_NAME}={token}")
    assert "HttpOnly" in header
    assert "SameSite=Lax" in header
    assert "Secure" in header
    assert f"Max-Age={identity.COOKIE_MAX_AGE}" in header
    assert identity.COOKIE_MAX_AGE == 34560000
    assert "Path=/" in header
    assert "Domain" not in header
