"""
The demo page's Content-Security-Policy, derived from the page itself.

The page was written as one self-contained file so that "a strict CSP can then
allow nothing external" (its own head comment). This module is the payoff: it
reads that file, hashes its two inline blocks, and returns the policy string the
`text/html` branch of `GET /` sends. Nothing about the page moves to earn it --
there are no inline handlers to convert and no style attributes to hoist.

WHY DERIVED RATHER THAN FROZEN (19-02 P-05). The alternative is a pair of
`sha256-` literals plus a test asserting the file still hashes to them. That
design lets the SERVED header disagree with the SHIPPED page -- a stale literal
means the live demo's script is blocked in every browser while the suite is
green. It also reds on a benign CSS tweak, and a gate that cries wolf gets
silenced by whoever is updating the literal for the fourth time. Deriving at
request time makes disagreement structurally impossible: both sides come from
the same bytes.

What derivation cannot follow is a change to the policy's SHAPE, so the tests
carry that half: a second inline block, a first `onclick=`, a first `style=`
attribute each need a policy this module would not write, and each fails a gate
in tests/test_service.py.

THE DIRECTIVE SET, and why each one is here (19-UI-SPEC "The CSP Contract"):

    default-src 'none'      the page loads nothing external by design; every
                            capability below is opted into explicitly
    script-src  'sha256-'   the single inline <script> block, by element hash
    style-src   'sha256-'   the single inline <style> block, by element hash.
                            The dark-mode @media lives inside that same element,
                            so dark mode costs no second source
    connect-src 'self'      the page's four fetch call sites (/research/stream,
                            /sessions/{id}/ask/stream, /demo, /sessions[/{id}]),
                            all same-origin. The SSE streams are ordinary fetch
                            responses -- hand-parsed over ReadableStream because
                            EventSource cannot POST -- so they need connect-src
                            and no special directive
    base-uri 'none'         no <base> exists; forbid injecting one to relocate
                            every relative URL on the page
    form-action 'self'      the form's submit is preventDefault'ed, but if JS
                            ever failed the fallback GET is same-origin
    frame-ancestors 'none'  nothing embeds the demo; free clickjacking hardening,
                            invisible to page behaviour

DELIBERATELY ABSENT, both families:

  - `img-src` / `font-src` / `frame-src` / `media-src` / `object-src`. The page
    has zero images, zero webfonts (system stacks only) and embeds nothing;
    `default-src 'none'` already covers them. Naming a directive for a
    capability nothing uses is granting it.
  - `'unsafe-inline'` and `'unsafe-hashes'`. The first makes the whole policy
    decorative: it permits exactly the injected inline script the hashes exist
    to exclude. The second is only needed for inline event handlers and style
    attributes, of which the page has zero. Admitting either would be admitting
    a capability nothing asked for -- and their absence is asserted against the
    SERVED string, not against this docstring.
"""

from __future__ import annotations

import base64
import functools
import hashlib
import re

# The one place the directive set is written down. The route sends this, and the
# tests read it from here rather than restating it -- two copies of a security
# header is the defect this arrangement exists to prevent. The two `{}` slots
# take a bare `sha256-...` source; the surrounding quotes are CSP's, required
# around hash sources.
DIRECTIVES: tuple[str, ...] = (
    "default-src 'none'",
    "script-src '{script}'",
    "style-src '{style}'",
    "connect-src 'self'",
    "base-uri 'none'",
    "form-action 'self'",
    "frame-ancestors 'none'",
)


def inline_blocks(html: str) -> tuple[list[str], list[str]]:
    """The bodies of every bare `<script>` and `<style>` element, in order.

    A plain non-greedy regex is the right size for this file: both tags are
    attribute-free, and the page has exactly one of each (asserted by
    tests/test_service.py, not assumed here). What would change that is an
    attribute on either tag -- `<script defer>` would not match these patterns,
    and the block would silently vanish from the count. `policy()` raises on any
    count other than one rather than serving a policy missing a hash, so that
    edit surfaces as a loud failure rather than a blocked page.
    """
    return (
        re.findall(r"<script>(.*?)</script>", html, re.S),
        re.findall(r"<style>(.*?)</style>", html, re.S),
    )


def sha256_source(text: str) -> str:
    """A CSP `sha256-` source for one inline block.

    The digest is over the exact UTF-8 bytes BETWEEN the tags -- not including
    the tags, not re-serialised, not whitespace-normalised. That is what a CSP
    element hash is defined over, and why the string handed here must come from
    the file rather than from a DOM or a template render.
    """
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return "sha256-" + base64.b64encode(digest).decode("ascii")


@functools.lru_cache(maxsize=4)
def policy(path: str) -> str:
    """The full policy string for the page at `path`.

    Cached on the path, so the file is read once per process -- on the first
    request that needs it, never at import time (DEC-18: nothing is constructed
    at import). Tests that edit the page mid-run call `policy.cache_clear()`.

    Raises ValueError, naming the counts, if the page does not have exactly one
    script block and one style block. A policy carrying one hash for two blocks
    is silently wrong in the worst way -- half the page dead in every browser,
    nothing wrong server-side -- so this fails loudly instead of serving it.
    """
    with open(path, encoding="utf-8") as handle:
        html = handle.read()

    scripts, styles = inline_blocks(html)
    if len(scripts) != 1 or len(styles) != 1:
        raise ValueError(
            f"{path} has {len(scripts)} inline script block(s) and {len(styles)} inline "
            "style block(s); the hash-based policy is defined for exactly one of each. "
            "Adding a block means adding its hash -- see 19-UI-SPEC's derivation invariant."
        )

    return "; ".join(
        directive.format(
            script=sha256_source(scripts[0]),
            style=sha256_source(styles[0]),
        )
        for directive in DIRECTIVES
    )
