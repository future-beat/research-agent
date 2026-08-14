# Phase 19: Credential validity, log addressability, demo CSP - Research

**Researched:** 2026-08-14
**Domain:** FastAPI lifespan/thread-pool probe machinery, Anthropic/Voyage SDK error semantics, LangGraph state schema, hash-based CSP derivation
**Confidence:** HIGH (every load-bearing claim below was verified against this session's reads of the actual source, or an empirical experiment run in this repo's own `.venv`; provider SDK behavior beyond what was directly inspected is CITED to official docs)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**The probe is cached and async, and liveness is untouchable**

- `count_tokens` is the Anthropic validity check — it authenticates and costs $0. Voyage
  gets a micro-embed (cheapest available call; effectively-zero but nonzero cost).
- New fields sit BESIDE the presence booleans, not replacing them: presence and validity
  are different facts and the credentials block should carry both.
- **The deliberate half of the original limitation survives**: Fly's check must never
  transitively call a provider, or a provider outage restarts a healthy container — the
  exact failure the presence-only design was protecting against. A probe failure is
  operator information, never a liveness failure.
- Probe spend is excluded from or attributed in cost accounting **deliberately, stated in
  code** — not silently. (The Voyage micro-embed would otherwise hit the Phase 14
  embedding meter; whichever way it goes, a comment and a test say which.)

**run_finished carries session_id**

- The gap cost a wasted live run in Phase 17 (a completed run was not addressable from the
  logs). Attribution matters more than the field: the fix is in the logging call, not a
  schema change.

**CSP is hash-based, verified, and visually inert**

- `unsafe-inline` is explicitly ruled out — a CSP with it is decorative.
- The header must be verified against the actual page: a test that derives the hashes from
  `static/index.html`'s real inline blocks, so editing the page without updating the policy
  fails a test rather than silently breaking the live demo.
- The UI-SPEC binds the constraint from the other side: the CSP must not change what the
  page looks like or does. If satisfying the CSP forces restructuring the page's JS, that
  surfaces as a checkpoint, not a silent rewrite.

### Claude's Discretion (researcher questions first, then planner)

- Probe cadence/TTL and refresh mechanism. Constraint: the service has no background
  scheduler today, and DEC-18 forbids import-time construction — serve-stale-refresh-async
  on `/health` reads is the likely shape, but the researcher should verify what composes
  with the existing lifespan and pool patterns. **Resolved below — see Finding 1.**
- `/health` field shape (e.g. `anthropic: {present, valid, checked_at}` vs flat keys) — pick
  what reads best beside the existing block; additive only (Phase 12's rollout constraint
  style: no field disappears). **Resolved below — see Finding 2.**
- Where CSP hashes are computed: build-time constant + derivation test, or startup
  derivation. Either is acceptable if the drift-fails-a-test property holds. **Resolved
  below — see Finding 5.**
- Whether `/ready` also surfaces validity (probably not — readiness is stores, and mixing
  provider validity into readiness re-creates the restart hazard one hop away). **Confirmed
  below — see Finding 1.**

### Deferred Ideas (OUT OF SCOPE)

- Note count bound — Phase 20.
- README Limitations rewrite — Phase 22 (the bullet at `README.md:289` stays; this phase
  builds the signal the bullet says is missing but does not delete the bullet).
- Any provider-outage alerting beyond `/health` surfacing (out of milestone scope).

**Also out of this phase, stated in 19-CONTEXT:** deleting any README Limitations bullet;
the note count bound; anything touching the critic, the judge, or eval recording; any
change to what liveness means to Fly.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REQ-health-credential-validity | `/health` reports whether the Anthropic and Voyage keys actually work, via a cached async validity probe (`count_tokens` free for Anthropic, a micro-embed for Voyage), surfaced beside the presence booleans. Liveness never calls a provider. Probe spend excluded/attributed deliberately. | Findings 1–3: concrete cache/refresh shape reusing `_probes()`, exact `count_tokens`/`embed` call shapes and error types, and the embedding-meter mechanics for the spend decision. |
| REQ-run-finished-session-id | `run_finished` log lines carry `session_id`. | Finding 4: verified `session_id` is not known inside `graph.py` at the point the line fires today (for new-session runs it does not exist yet), and an empirical LangGraph experiment proves a schema-avoiding workaround (stuffing an undeclared key into state) cannot work — the fix must live in `service.py`. |
| REQ-demo-csp-header | The demo page ships a hash-based CSP header, verified against the live page, that its inline JS survives. | Finding 5: header-attachment mechanics, confirmed the UI-SPEC's reference hashes are byte-reproducible from the shipped file with a two-line regex+SHA-256 recipe, and the SSE-header non-interaction is structural (different route, different response object). |
</phase_requirements>

## Summary

All three closures are additive surface changes over machinery that already exists and does
not need to be invented — the phase is about composing existing patterns correctly, not
introducing new architecture. The credential probe should reuse the existing `_probes()`
`ThreadPoolExecutor` and the wall-clock-timeout idiom `_probe()` already established for
store checks, but run in **fire-and-forget** mode (`submit()` without `future.result()`) so
`/health` never blocks on a provider — this is the concrete shape of "serve-stale,
refresh-async" the CONTEXT asked the researcher to confirm. `count_tokens` and a one-word
Voyage embed are confirmed free/near-free and each raise a distinguishable exception for
"key is wrong" (`AuthenticationError`, an `APIStatusError`/`VoyageError` subclass carrying a
401) versus "provider is down" (`APIConnectionError`, or a 5xx `APIStatusError`/
`ServerError`).

The `run_finished` / `session_id` requirement has a real structural constraint the CONTEXT
only hinted at: `session_id` is generated by the session store **after** the graph finishes
running for a brand-new research run (`store.create()` mints it inside `on_complete`, called
from `service.py` only once `graph.app.invoke`/`.stream` has returned), so the log line
firing *inside* `graph.py`'s supervisor node structurally cannot see it — not "currently
doesn't", **cannot**, for any run that opens a new session. An empirical test in this
session (LangGraph 1.2.9) confirms LangGraph strips any state key not declared on the
`AgentState` TypedDict when the graph runs, closing off the tempting workaround of quietly
stuffing `session_id` into the state dict without declaring it. The only place a log line
can legitimately carry both `run_id` and `session_id` is `service.py`, after
`on_complete(final_state)` resolves — which is exactly what "the fix is in the logging
call, not a schema change" was telling the planner.

The CSP work is the most de-risked of the three: this session recomputed both inline-block
hashes directly from the shipped `static/index.html` using the two-block regex extraction
the UI-SPEC assumes, and both matched the UI-SPEC's stated reference hashes byte-for-byte.
The header attaches cleanly at the single `FileResponse(...)` call site in `index()` via its
own `headers=` kwarg, and the SSE routes build a completely different `StreamingResponse`
object at a different call site (`_sse_response`), so there is no shared header dict to
accidentally mutate.

**Primary recommendation:** build the credential probe as a second small module-level cache
next to `_probe_executor`, submitted to the same `_probes()` pool but never awaited inside
the request; move (do not merely extend) the `run_finished` log emission for
service-initiated runs into `service.py`'s `_execute`/`_stream` success paths, leaving
`graph.py`'s existing line untouched for the REPL/eval callers that have no session concept
at all; and derive the CSP hashes from `static/index.html` lazily on first request, cached
thereafter, with a from-scratch derivation test that never reads the frozen literals in
UI-SPEC.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Credential validity probe (cache, refresh trigger, TTL) | API / Backend (`service.py`) | — | `/health` is an ops endpoint owned entirely by the service layer; no client-side or DB-tier concern |
| Anthropic `count_tokens` / Voyage micro-embed call | API / Backend (`service.py`, reusing `graph.client()` / `graph.memory().embedder`) | — | These are the same provider clients the graph already lazily constructs (DEC-18); the probe is a second caller of the same seam, not a new integration |
| Cost attribution decision for the Voyage probe call | API / Backend (`usage.py`'s embedding meter) | — | The meter is a contextvar scoped per-call-frame; the probe either opens one (attributed) or doesn't (excluded) — a backend accounting decision, no other tier is involved |
| `run_finished` → `session_id` correlation | API / Backend (`service.py`) | — | `session_id` is a session-store concept created by `service.py`'s `on_complete` callback; `graph.py` (the LangGraph state machine) has no store access and cannot originate it |
| CSP header | API / Backend (`service.py`'s `index()` route) | Browser (enforces the policy) | The header is emitted server-side on one route; the browser is the enforcement tier but requires no code change — the page already satisfies the policy by construction (UI-SPEC) |
| CSP hash derivation (build-time or first-request) | API / Backend (a small `csp.py`-shaped helper reading `static/index.html`) | — | Pure computation over a file already inside the service's own package; no browser or DB involvement |

## Standard Stack

No new external dependency is introduced by this phase. Every capability below is built on
libraries already pinned in `pyproject.toml` and already imported in the modules that need
them.

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `anthropic` | `0.120.0` (pinned, `pyproject.toml:14`) [VERIFIED: pyproject.toml:14, and `python -c "import anthropic; anthropic.__version__"` in this repo's `.venv` this session prints `0.120.0`] | `messages.count_tokens(...)` as the Anthropic validity probe | Already the SDK the graph uses (`graph.py:37,90-94`); no second HTTP client to maintain |
| `voyageai` | `0.5.0` (pinned, `pyproject.toml:15`) [VERIFIED: pyproject.toml:15, and `python -c "import voyageai; voyageai.__version__"` in `.venv` this session prints `0.5.0`] | `Client.embed([...])` as the Voyage validity probe | Already the SDK `VoyageEmbedder` uses (`memory.py:126-149`) |
| stdlib `concurrent.futures.ThreadPoolExecutor` | stdlib | Fire-and-forget credential refresh, reusing `_probes()` (`service.py:479-490`) | Zero new dependency; identical bounding story to the existing store probes |
| stdlib `hashlib` + `base64` | stdlib | SHA-256 hash of the inline `<script>`/`<style>` blocks for the CSP `sha256-…` sources | Exactly what CSP Level 2 hash sources require; confirmed to reproduce the UI-SPEC's stated hashes byte-for-byte this session (see Finding 5) |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `re` (stdlib) | stdlib | Extract the exact bytes between `<script>`/`<style>` tags for hashing | Only two literal tags exist in `static/index.html` (confirmed: `grep` shows exactly one `<style>`…`</style>` pair at lines 17–111 and one `<script>`…`</script>` pair at 147–536, no attributes on either tag) — a plain non-greedy regex is sufficient, no HTML parser needed |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Fire-and-forget on the existing `_probes()` pool | A dedicated second `ThreadPoolExecutor` for credential probes | Isolates credential refreshes from a congested store-probe pool, but adds a second executor to build/shut down in `lifespan`/`_shutdown_probes()` for a benefit that only matters if store probes are already saturating 3 workers — not worth it unless observed in production |
| `count_tokens` for the Anthropic probe | A 1-token `messages.create(max_tokens=1, ...)` call | `count_tokens` is confirmed free and does not share the Messages API's rate limit [CITED: platform.claude.com/docs/en/build-with-claude/token-counting, "Token counting is free to use... Token counting and message creation have separate and independent rate limits"]; a real `create` call would cost money and consume the same budget as production traffic — strictly worse |
| Reading `graph.memory().embedder` for the Voyage probe | Constructing a fresh, independent `VoyageEmbedder()` instance | Reusing `graph.memory().embedder` means the probe validates whichever embedder the running process actually uses (byte-identical semantics across json/memory/chroma/pgvector, matching the note-store contract), and lets tests reuse the exact `FakeEmbedder`/`voyage_embedder()` fixtures the suite already has (`test_memory_stores.py:22-48,232-247`); a fresh instance would need its own key-reading and its own fakes, duplicating the seam for no benefit |

**Installation:** none — no new packages.

**Version verification:** confirmed live against this repo's `.venv` this session (see Core
table); no version bump needed for either SDK.

## Package Legitimacy Audit

Not applicable. This phase installs zero new external packages — `anthropic` and
`voyageai` are pre-existing pinned dependencies (`pyproject.toml:14-15`), already used
elsewhere in the codebase, and no other library is introduced.

## Architecture Patterns

### System Architecture Diagram

```
Credential validity (REQ-health-credential-validity)
======================================================

  GET /health  ──────────────────────────────────────────────┐
       │                                                      │
       ▼                                                      │
  read cached {anthropic,voyage}: {valid, checked_at}         │
  (module-level dict, lock-guarded — mirrors _probe_executor)  │
       │                                                      │
       ├─ stale or cold, and no refresh already in-flight ────┤
       │        │                                             │
       │        ▼                                             │
       │  _probes().submit(refresh_anthropic)  ─┐             │
       │  _probes().submit(refresh_voyage)     ─┤ NOT awaited │
       │        │                                │ here        │
       │        ▼ (on a worker thread, later)    │             │
       │  graph.client().messages.count_tokens(…) │             │
       │  graph.memory().embedder.embed_query(…)  │             │
       │        │                                │             │
       │        ▼                                │             │
       │  AuthenticationError → valid=False       │             │
       │  APIConnectionError/5xx → valid=None*    │             │
       │  success → valid=True                    │             │
       │        │                                │             │
       │        ▼                                │             │
       │  write result + checked_at into cache ◄──┘             │
       │  (done_callback clears the in-flight flag)             │
       │                                                        │
       ▼                                                        ▼
  return CURRENT cache value immediately (never blocks on the future above)
       │
       ▼
  {"credentials": {"anthropic": true, "anthropic_valid": <bool|null>,
                    "anthropic_checked_at": <float|null>, "voyage": ..., ...}}

  * a provider outage is reported honestly as "could not determine" rather
    than folded into the same False a bad key produces — see Finding 3.

Log addressability (REQ-run-finished-session-id)
=================================================

  POST /research(.../stream)  or  POST /sessions/{id}/ask(.../stream)
       │
       ▼
  graph.app.invoke(state) / .stream(state)   ← runs entirely inside graph.py
       │                                          (no SessionStore access here;
       │                                           session_id genuinely does
       │                                           not exist yet for a new run)
       ▼
  final_state returned to service.py
       │
       ▼
  session_id = on_complete(final_state)   ← service.py mints/reuses it via
       │                                     SessionStore.create()/append_turn()
       ▼
  log.info("run finished", extra={..., "session_id": session_id})  ← NEW,
       │                                                              in service.py
       ▼
  metrics.record(...)  →  limits.settle(...)  →  response/SSE result event

CSP (REQ-demo-csp-header)
==========================

  GET /  (Accept: text/html)
       │
       ▼
  index() in service.py           static/index.html on disk
       │                                   │
       │                                   ▼
       │                          hash <script> block, hash <style> block
       │                          (cached after first computation)
       │                                   │
       ▼                                   ▼
  FileResponse(DEMO_PAGE, headers={"Content-Security-Policy": policy_string})
       │
       ▼
  browser enforces: default-src 'none'; script-src 'sha256-…'; style-src
  'sha256-…'; connect-src 'self'; base-uri 'none'; form-action 'self';
  frame-ancestors 'none'

  (POST /research/stream, /ask/stream build a *different* StreamingResponse
   object via _sse_response(), whose own headers={"Cache-Control":...,
   "X-Accel-Buffering":...} dict is untouched by anything above)
```

### Recommended Project Structure

No new files are structurally required — service.py already owns everything this phase
touches. If the planner prefers isolating the CSP derivation as a pure function (recommended
for testability without FastAPI machinery), a small addition:

```
src/research_agent/
├── service.py        # /health credential block, run_finished log call, index()'s
│                      # FileResponse headers= — all three surfaces this phase touches
├── graph.py           # UNCHANGED except possibly a code comment; run_finished's
│                      # existing line stays for REPL/eval callers (see Finding 4)
├── usage.py           # UNCHANGED unless the spend decision is ATTRIBUTED (Finding 3),
│                      # in which case a small addition here folds probe cost somewhere
├── memory.py           # UNCHANGED — VoyageEmbedder and its `.embedder` accessor via
│                        # graph.memory() are reused as-is
└── csp.py             # NEW (optional): pure `policy_header(html_path) -> str` helper,
                        # importable by both service.py and its derivation test without
                        # needing a running app
```

### Pattern 1: Fire-and-forget refresh on the existing probe pool

**What:** Reuse `_probes()` (`service.py:483-490`) for the credential refresh, but never call
`.result()` on the submitted future from the request path — only a `done_callback` writes
the outcome back into a cache dict.

**When to use:** Any check whose *reachability* must never block a liveness-critical
response, but whose *result* is worth caching for the next reader. This is the same shape
`_probe()` already uses for store checks, minus the `future.result(timeout=...)` blocking
call — because unlike a store probe (which /health's contract says must report *this
instant's* reachability, bounded to `HEALTH_PROBE_BUDGET`), a credential's validity does not
change from millisecond to millisecond, so it is legitimate — and required by "liveness never
calls a provider" — to serve a value that is up to one TTL old.

**Example (illustrative — not a literal diff; the planner owns the exact shape):**
```python
# Source: derived from service.py:479-566 (_probes / _probe), read this session
_credential_cache: dict[str, dict] = {}
_credential_cache_lock = threading.Lock()
_credential_inflight: set[str] = set()

def _refresh_credential(name: str, probe_fn) -> None:
    try:
        probe_fn()  # sets valid True/False internally, or raises
        result = {"valid": True, "checked_at": time.time()}
    except _KEY_INVALID_EXCEPTIONS as exc:
        result = {"valid": False, "checked_at": time.time()}
    except Exception:
        # Provider down / timeout / anything else: "could not determine",
        # never collapsed into the same False a bad key produces.
        result = {"valid": None, "checked_at": time.time()}
    with _credential_cache_lock:
        _credential_cache[name] = result
        _credential_inflight.discard(name)

def _credential_status(name: str, present: bool, probe_fn, ttl: float) -> dict:
    if not present:
        return {"valid": None, "checked_at": None}  # never probe an absent key
    with _credential_cache_lock:
        cached = _credential_cache.get(name)
        stale = cached is None or (time.time() - cached["checked_at"]) > ttl
        if stale and name not in _credential_inflight:
            _credential_inflight.add(name)
            _probes().submit(_refresh_credential, name, probe_fn)
    return cached or {"valid": None, "checked_at": None}
```

### Pattern 2: Distinguishing key-invalid from provider-down

**What:** Catch the SDK's authentication-specific exception separately from its
connection/5xx exceptions, so the `/health` payload can report three states, not two:
`true` (works), `false` (key is wrong), `null` (could not determine — provider outage,
timeout, or the key was never probed).

**When to use:** Any external-credential health check where "the key is bad" and "the
provider is unreachable" are operationally different facts an operator needs to
distinguish (the entire point of REQ-health-credential-validity — Phase 11's revoked-key
outage would not have been distinguishable from a Fly-side network blip without this split).

**Confirmed exception shapes (this session, direct package inspection of the pinned
versions):**
```python
# anthropic 0.120.0 — VERIFIED via `python -c "import anthropic; print([e for e in
# dir(anthropic) if 'Error' in e])"` in this repo's .venv this session:
# ['APIConnectionError', 'APIError', 'APIResponseValidationError', 'APIStatusError',
#  'APITimeoutError', 'APIWebhookValidationError', 'AnthropicError', 'AuthenticationError',
#  'BadRequestError', 'ConflictError', 'InternalServerError', 'NotFoundError',
#  'OverloadedError', 'PermissionDeniedError', 'RateLimitError', 'RequestTooLargeError',
#  'RetryableError', 'UnprocessableEntityError', 'WorkloadIdentityError']
#
# MRO confirmed this session:
#   AuthenticationError -> APIStatusError -> APIError -> AnthropicError -> Exception
#   APIConnectionError  -> APIError -> AnthropicError -> Exception
#
# key-invalid:      anthropic.AuthenticationError        (a 401 APIStatusError)
# provider-down:     anthropic.APIConnectionError          (no HTTP response at all)
#                     anthropic.InternalServerError,        (5xx APIStatusError
#                     anthropic.OverloadedError              subclasses)
# rate-limited:      anthropic.RateLimitError               (429 — treat as "could not
#                                                             determine this cycle", not
#                                                             "key is bad")

# voyageai 0.5.0 — VERIFIED via `python -c "import voyageai.error as e; print([x for x in
# dir(e) if 'Error' in x])"` in this repo's .venv this session:
# ['APIError', 'TryAgain', 'Timeout', 'APIConnectionError', 'InvalidRequestError',
#  'MalformedRequestError', 'AuthenticationError', 'RateLimitError', 'ServerError',
#  'ServiceUnavailableError', 'VideoProcessingError', 'VoyageError']
# All inherit VoyageError [VERIFIED: `inspect.getsource(voyageai.error)` this session,
#  read in full — every class listed above is `class X(VoyageError): pass`]
#
# key-invalid:      voyageai.error.AuthenticationError
# provider-down:     voyageai.error.APIConnectionError, ServerError,
#                     ServiceUnavailableError, Timeout, TryAgain
```

Both `anthropic.Anthropic()` and `voyageai.Client()` construct successfully even with an
empty-string or absent API key [VERIFIED: ran `voyageai.Client()` and `anthropic.Anthropic()`
under `VOYAGE_API_KEY=""` / `ANTHROPIC_API_KEY=""` in this repo's `.venv` this session — both
construct without raising, matching the existing `/health` docstring's claim that "the
clients are lazy" (`service.py:608-611`)]. The authentication failure only surfaces on the
first real network call — i.e., exactly where the probe calls `count_tokens`/`embed`, which
is the right place to catch it. This session could not exercise a *live* 401/5xx round trip
(no real credentials in this sandbox, and doing so deliberately for an invalid key is safe
but for a valid one would spend real money against a stranger's account — out of scope for
research). The exception **class** shapes above are VERIFIED by direct inspection; the
claim that an invalid key specifically raises `AuthenticationError` (rather than some other
`APIStatusError` subclass) is standard REST/401 semantics [CITED: general knowledge of both
SDKs' status-code-to-exception mapping, consistent with `APIStatusError`'s role as the base
class for every HTTP-error response] and should be pinned in tests via a **fake** that
raises the named exception directly (see Test Inventory below) rather than a live call,
matching the keyless suite constraint.

### Pattern 3: The exact free/near-free call shapes

**Anthropic (`count_tokens`) — confirmed free and independently rate-limited:**
```python
# Source: https://platform.claude.com/docs/en/build-with-claude/token-counting
# [CITED — fetched this session; official docs]
# "Token counting is free to use but subject to requests per minute rate limits based on
#  your usage tier... Token counting and message creation have separate and independent
#  rate limits. Usage of one does not count against the limits of the other."
# Start tier: 2,000 RPM for count_tokens specifically.

response = graph.client().messages.count_tokens(
    model=graph.MODEL,  # "claude-sonnet-5" -- reuse the production model constant
    messages=[{"role": "user", "content": "ping"}],
)
# response.input_tokens is the count; irrelevant to the probe -- only success/failure
# and the exception type matter. Call signature VERIFIED via
# `inspect.signature(anthropic.Anthropic(api_key='x').messages.count_tokens)` this
# session against the pinned SDK.
```

**Voyage (`embed`) — cheapest real call, cost computed against the pinned price table:**
```python
# Source: memory.py:131-139 (VoyageEmbedder.embed_query), read this session
embedding = graph.memory().embedder.embed_query("ping")
# Reuses whatever embedder the running process already has (VoyageEmbedder in
# production; FakeEmbedder in the keyless test suite via the existing
# make_client fixture -- test_service.py:179).
```
Cost, computed from the pinned rate table [VERIFIED: usage.py:130-134, read this session —
`VOYAGE_PRICES = {"voyage-3.5": [PriceWindow(0.06)], ...}`, i.e. $0.06 per 1,000,000 tokens
for the default model `EMBEDDING_MODEL = os.environ.get("VOYAGE_EMBEDDING_MODEL",
"voyage-3.5")` (memory.py:42)]: a one-word probe string is on the order of 1–3 tokens, so
the call costs **≈ $0.00000006–0.00000018 per probe** — six to seven orders of magnitude
below a cent, matching CONTEXT's "effectively-zero but nonzero" framing exactly.

### Pattern 4: The embedding-meter attribution decision, both ways

**What it is:** `VoyageEmbedder.embed_query`/`embed_documents` unconditionally call
`usage.report_embedding(self.model, total_tokens)` after every real call [VERIFIED:
memory.py:141-149,151-166, read in full this session — the `_report` method's docstring:
`"Hand the billed token count to whoever is metering this scope... out of band to
usage.report_embedding, which is a no-op unless a caller opened a meter."`]. `report_embedding`
itself is a no-op when no `embedding_meter()` context is currently open on the calling
thread's contextvar [VERIFIED: usage.py:462-475, read this session — `"def
report_embedding(...): meter = _EMBEDDING_METER.get(); if meter is None: return"`].

**Option A — EXCLUDED (the structural default, requires zero new code):** call
`graph.memory().embedder.embed_query(...)` from the credential probe *without* opening a
`usage.embedding_meter()` context around it. `report_embedding` fires, finds no active
meter, and returns immediately — the probe's tokens are never folded into any run's
`state["usage"]`, never reach `RunRecord`/the `runs` table, and never affect `/metrics` or
the daily spend cap. The dollar cost is still genuinely incurred at Voyage's account level;
it is simply not attributed to anything inside this application. **This is the natural
outcome of doing nothing extra** — the meter is opt-in per call-frame by design (Phase 14),
so a caller that never opens one is excluded by construction, not by a special case.

**Option B — ATTRIBUTED (requires new plumbing with no obvious home):** wrap the probe call
in `with usage.embedding_meter() as meter: ...`, then decide where `meter.total_tokens` /
the resulting cost goes. There is no existing sink for this: `record_embedding()`
(usage.py:478-521) folds a meter's totals into a **run's** `totals` dict, and there is no
run associated with a background health probe. Attribution would require either (a) a new,
separate running counter (e.g. a `probe_spend_usd` field on `MetricsStore` or a simple
module-level accumulator surfaced on `/metrics`), or (b) writing a synthetic `RunRecord`
with no session — both are new surface area this phase would have to design and test from
scratch, for a total of low-single-digit-cents-per-day of spend even under aggressive
polling.

**Recommendation:** Option A (excluded), stated in a code comment at the probe's call site
(not merely implied by omission) and pinned by a test that asserts `embedding_meter()`
reports zero tokens across a `/health` call that triggers a Voyage probe — the mutation that
would catch a regression is "someone later wraps the probe in a meter without updating the
comment/test", which a test asserting the **absence** of attribution catches directly (see
Test Inventory). If the planner or user prefers Option B, `tests/test_usage.py:657-699`
(`test_meter_isolation_across_contexts` and neighbors) already shows the meter's
comparison idiom to build a symmetric ATTRIBUTED test from.

### Pattern 5: The `run_finished` / `session_id` structural constraint (the load-bearing finding)

**What goes wrong if you try to thread `session_id` through the graph without a schema
change:** `AgentState` is a `TypedDict` [VERIFIED: graph.py:166-192, read this session —
declares `run_id: str`, `owner: str`, `task: str`, `mode: str`, ... `trace: list`; no
`session_id` key] used to build `StateGraph(AgentState)` (`graph.py:660`). This session ran
a minimal reproduction against the pinned LangGraph version:

```python
# VERIFIED empirically this session, against langgraph 1.2.9 (the version installed
# in this repo's .venv, confirmed via `pip show langgraph`):
from typing import TypedDict
from langgraph.graph import StateGraph, END

class S(TypedDict):
    x: int

def node(state):
    return {'x': state['x'] + 1}

g = StateGraph(S)
g.add_node('n', node); g.set_entry_point('n'); g.add_edge('n', END)
app = g.compile()

result = app.invoke({'x': 1, 'extra_undeclared_key': 'hello'})
print(result)
# -> {'x': 2}      *** extra_undeclared_key is GONE ***
```

**This closes off the tempting workaround** of having `service.py` stuff
`state["session_id"] = pregenerated_id` into the dict before calling `graph.app.invoke`
without formally declaring it on `AgentState`: LangGraph silently drops any key not on the
schema. The only two ways to get `session_id` into the log line that fires inside
`graph.py`'s supervisor node are (1) add `session_id: str` to the `AgentState` TypedDict —
which is exactly the "schema change" 19-CONTEXT rules out — or (2) don't log from inside
the graph at all for this purpose.

**The second structural fact:** `session_id` does not exist yet when the graph runs, for two
of the four routes. `store.create(task, state, session_id=None, owner="")` [VERIFIED:
sessions.py:175,251,258,358-359, read this session — SQLite: `"def create(self, task, state,
session_id=None, owner=''): session_id = session_id or uuid.uuid4().hex"`; Postgres:
identical shape at line 358-359] is called **after** `graph.app.invoke`/`.stream` returns,
from inside `_execute`/`_stream`'s `on_complete` closure [VERIFIED: service.py:288-292,
`"final_state = graph.app.invoke(state); ... session_id = on_complete(final_state)"`, and
service.py:337-348 for the streaming path]. For `POST /research` and `POST
/research/stream`, `on_complete` is `lambda state: store.create(question, state,
owner=owner)` [VERIFIED: service.py:702, `"lambda state: store.create(question, state,
owner=owner)"`] — no `session_id=` is passed, so a fresh UUID is minted **only once the run
is already finished**. For `POST /sessions/{session_id}/ask(.../stream)`, `session_id` *is*
already known (it's the path parameter) — but the fix must be uniform across all four
routes, and the uniform, always-correct answer is: log from wherever `session_id` is
actually resolved, which is `service.py`, not `graph.py`.

**Recommended fix:** leave `graph.py`'s existing `run_finished` log call
(`graph.py:634-649`, quoted verbatim below) completely untouched — it continues to serve the
REPL (`chat.py`, which was verified this session to hold no `SessionStore` reference at all
— grep for `session`/`SessionStore` in `chat.py` returns zero hits beyond a docstring
comment) and the eval harness (`recall_golden.py`, `evals/`), neither of which has a session
concept and both of which are explicitly out of this phase's scope ("Not in this phase: ...
anything touching the critic, the judge, or eval recording"). Add a **new** log call in
`service.py`, immediately after `session_id = on_complete(final_state)` resolves in both
`_execute` (service.py:292) and `_stream` (service.py:348), carrying `run_id`, `session_id`,
and the same fields the existing line carries. Recommend a **distinct event name** rather
than reusing `"run_finished"` verbatim for this second call site (see Pitfall 1 below for
why), while still satisfying REQ-run-finished-session-id's literal ask, since the requirement's
own text ties itself to the underlying gap ("so a completed run is addressable from the
logs") rather than to the literal string `event: run_finished` — but this is a naming
choice the planner should make explicitly and record, not silently default.

**Exact current log call, quoted verbatim [VERIFIED: graph.py:634-649, read this session]:**
```python
if state["next_step"] == "done":
    log.info(
        "run finished",
        extra={
            "event": "run_finished",
            "run_id": state.get("run_id", ""),
            "mode": state["mode"],
            "topic_type": state["topic_type"],
            "approved": bool(state["approved"]),
            "forced_stop_reason": state["forced_stop_reason"],
            "iterations": state["iteration"],
            "revisions": state["revision_count"],
            "model_calls": state["usage"]["calls"],
            "cost_usd": round(state["usage"]["cost_usd"], 6),
        },
    )
```
Both `graph.py`'s `log` and `service.py`'s `log` are the *same* logger object
[VERIFIED: observability.py:80-81, `"def get_logger() -> logging.Logger: return
configure_logging()"`, and `configure_logging()` at line 61 does
`logging.getLogger(LOGGER_NAME)` with `LOGGER_NAME = "graph"` (line 28) — both modules call
`log = get_logger()` (graph.py:81, service.py:48), so they resolve to the identical
`logging.Logger` singleton], so moving/adding the emission site to `service.py` changes
nothing about which logger, formatter, or `caplog` fixture picks it up — the existing
pattern in `tests/test_graph_smoke.py:807-818` (`monkeypatch.setattr(graph.log,
"propagate", True)` then `caplog.at_level(..., logger=graph.log.name)`) works identically
whether the `log.info(...)` call physically lives in `graph.py` or `service.py`.

### Pattern 6: CSP header attachment without touching SSE headers

**What:** `FileResponse` accepts a `headers=` kwarg directly [VERIFIED:
`inspect.signature(FileResponse.__init__)` in this repo's `.venv` this session:
`"headers: Mapping[str, str] | None = None"`], so the existing single call site needs only
its arguments extended:

```python
# Source: service.py:402-412, read this session — CURRENT:
@app.get("/", tags=["ops"])
def index(request: Request):
    if "text/html" in request.headers.get("accept", ""):
        return FileResponse(DEMO_PAGE, media_type="text/html")
    return _index_json()

# Illustrative change -- one line at the single call site that matters
# (UI-SPEC: "MUST: the text/html branch of index()"):
    if "text/html" in request.headers.get("accept", ""):
        return FileResponse(DEMO_PAGE, media_type="text/html", headers={
            "Content-Security-Policy": csp_policy(),
        })
```

The SSE routes build a **different** `StreamingResponse` object at a **different** call site
[VERIFIED: service.py:986-995, quoted verbatim: `"return StreamingResponse(_stream(...),
media_type='text/event-stream', headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering':
'no'})"`] — there is no shared headers dict, no middleware, and no base-response class
between `index()` and `_sse_response()` that a CSP addition could accidentally touch. No
test today asserts on `/research/stream`'s or `/ask/stream`'s headers changing, but the
UI-SPEC's own acceptance check (#6 in its list) already requires the two SSE headers to
"stay exactly as they are" — satisfied structurally, not by discipline, because the two
routes never share a response object.

### Anti-Patterns to Avoid

- **Blocking `/health` on the credential probe's `future.result(...)`:** this is precisely
  the restart-loop failure mode `_probe()`'s own docstring spends four paragraphs
  explaining for store probes (service.py:504-542) — reintroducing it for provider calls
  (which are strictly less reliable than a same-region database) would be a regression
  worse than the one this phase is fixing.
- **Adding `session_id` to `AgentState`:** explicitly ruled out by CONTEXT ("the fix is in
  the logging call, not a schema change"), and this session's LangGraph experiment shows
  the alternative workaround (an undeclared dict key) silently fails rather than raising —
  the kind of bug that would pass every existing test and only manifest as `session_id`
  quietly missing from the log, discovered the next time someone needs it during an
  incident (echoing the exact Phase 17 story this REQ exists to prevent).
- **Treating every probe exception the same way:** collapsing `AuthenticationError` and
  `APIConnectionError` into the same `valid: false` throws away the one piece of
  information REQ-health-credential-validity exists to add — the whole point of the
  acceptance story ("the revoked-key outage from Phase 11... would be visible in `/health`
  within one probe TTL") is that a bad key and a provider outage read differently to an
  operator.
- **Reusing `"run_finished"` as the event name at two call sites for one logical run:**
  see Pitfall 1.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Bounding a provider call so `/health` never hangs | A custom `asyncio.wait_for`/signal-based timeout around a sync SDK call | The existing `_probes()` `ThreadPoolExecutor` + fire-and-forget `submit()` (no `.result()` in the request path) | The store-probe machinery already solved "bound a synchronous call safely from a possibly-async-or-sync handler" (`service.py:504-542`'s docstring documents the exact tradeoffs); reinventing it for credentials risks reintroducing the "up to 18s in the cold case" bug that machinery was built to fix |
| Detecting "key is bad" vs "provider is down" | String-matching on exception messages | The SDK's own typed exception hierarchy (`AuthenticationError` vs `APIConnectionError`/5xx `APIStatusError` subclasses for Anthropic; the mirrored `voyageai.error` classes) | Both SDKs already carry this distinction in their exception types (VERIFIED this session); message-string matching is exactly the fragile pattern `_redact()`'s own comments elsewhere in this file already warn against for a different reason (DSN leakage) |
| SHA-256-hashing an HTML fragment for CSP | A third-party CSP-hash-generator library | Stdlib `hashlib.sha256(...).digest()` + `base64.b64encode(...)` | Two stdlib calls reproduce the exact UI-SPEC hashes (VERIFIED this session) — no library adds anything but a dependency |
| Extracting the inline `<script>`/`<style>` blocks | An HTML5 parser (`html.parser`, `BeautifulSoup`) | A plain non-greedy regex (`re.findall(r'<script>(.*?)</script>', html, re.S)`) | The file has exactly one bare `<script>` and one bare `<style>` tag, no attributes, confirmed by direct grep this session — a full parser is defensible but strictly more machinery than the actual shape of the file requires; if the planner prefers robustness against a future attribute being added to the tag, `tests/test_service.py:1866-1895` already imports `html.parser.HTMLParser` for a different check and that pattern is available to reuse |

**Key insight:** every piece of machinery this phase needs — bounded probes, lazy client
construction, a contextvar-scoped cost meter, per-owner store injection for tests — already
exists in this codebase for a sibling purpose. The research risk in this phase was never
"what library solves this" (nothing new is needed) but "which existing seam does this
compose with, and does it actually compose" — which is why this document leans on empirical
verification (running code against the pinned versions) rather than general survey.

## Common Pitfalls

### Pitfall 1: Two log lines both named `run_finished` for one HTTP-initiated run

**What goes wrong:** if the planner keeps `graph.py`'s existing `run_finished` line
unmodified *and* adds a second call in `service.py` using the same `event: "run_finished"`
string, any operator or script counting completed runs via
`jq 'select(.event=="run_finished")' | wc -l` over the log stream would double-count every
service-initiated run (one line from `graph.py` without `session_id`, one from `service.py`
with it) while REPL/eval runs would still produce exactly one. This project's own commit
history in `.planning/STATE.md` records at least eight prior incidents of exactly this
family of bug — a count that silently drifts because two things that look like the same
fact are actually two facts.
**Why it happens:** the natural, minimal-diff instinct is "just add `session_id` to the
`extra=` dict of *a* `run_finished` call" without noticing there would now be two call sites
sharing that event name.
**How to avoid:** give the `service.py`-emitted line a distinct `event` value (e.g.
`"run_addressable"` or `"run_persisted"`), stated explicitly in the plan and in a code
comment, and add a test asserting the two events are mutually exclusive per request (a
service-initiated run produces exactly one of each, never two of the same name).
**Warning signs:** a log-based dashboard or count that looks like it doubled after this
phase ships.

### Pitfall 2: Silently attributing probe spend by accident

**What goes wrong:** if a future refactor moves the credential probe's Voyage call inside
`researcher_node`'s existing `with usage.embedding_meter()` block (e.g. by extracting a
shared helper that both the probe and the researcher call, and forgetting the probe runs
outside that scope), the probe's tokens would suddenly get folded into whichever *user's*
run happens to be executing concurrently on the same thread's contextvar — misattributing
one visitor's health-check cost to another visitor's bill.
**Why it happens:** the meter is a contextvar, not an explicit parameter — it is invisible
at the call site of `embed_query`, so a caller cannot tell by reading `VoyageEmbedder.
embed_query(...)` alone whether it is currently metered.
**How to avoid:** the test recommended in Pattern 4 (assert zero attribution across a
probe-triggering `/health` call) is exactly the regression guard for this; keep it in the
suite regardless of which of Option A/B the planner picks, updated to assert the *chosen*
behavior explicitly.
**Warning signs:** `/metrics`' embedding-cost figures fluctuating with `/health` traffic
rather than with actual research runs.

### Pitfall 3: Probing an absent key

**What goes wrong:** if the probe function is called for a provider whose key is unset (or
empty string, treated as absent per the existing `/health` convention —
[VERIFIED: service.py:1511-1516's test `test_health_treats_an_empty_key_as_absent` pins
this today]), the SDK client still constructs successfully (VERIFIED this session) and the
probe call would raise `AuthenticationError` immediately — which is technically correct but
wastes a probe cycle and, worse, would report `valid: false` for a key that was never
configured, contradicting CONTEXT's explicit requirement: "the no-keys state should read as
`valid: null`/unknown, not false (a missing key is a presence problem, not a validity one)."
**Why it happens:** the presence check (`bool(os.environ.get(...))`) and the validity probe
are conceptually separate, and it's easy to wire the probe to run unconditionally.
**How to avoid:** gate the probe call on presence first — Pattern 1's `_credential_status`
sketch does this (`if not present: return {"valid": None, "checked_at": None}`).
**Warning signs:** the keyless test suite (which runs with `ANTHROPIC_API_KEY=""`
everywhere) would immediately catch this if a test asserts the no-keys shape — which it
must, per CONTEXT's explicit house constraint.

### Pitfall 4: Assuming a TTL that's too short races Fly's own check interval

**What goes wrong:** if `CREDENTIAL_PROBE_TTL`-equivalent defaults too low, `/health` could
attempt a provider probe on nearly every Fly health-check hit, multiplying outbound calls by
however frequently Fly polls — burning the free `count_tokens` rate limit (2,000 RPM on the
Start tier [CITED: platform.claude.com/docs/en/build-with-claude/token-counting]) faster
than intended and (worse for Voyage, which is NOT free) accumulating real, if tiny, spend at
a multiple of the intended rate.
**Why it happens:** `HEALTH_PROBE_BUDGET` (store-probe timeout) and a credential TTL
(refresh interval) are easy to conflate — they answer different questions ("how long may one
probe attempt take" vs "how often do we attempt one at all").
**How to avoid:** follow `health_probe_budget()`'s exact env-var-with-floor pattern
(`service.py:463-472`) for a new, separately-named TTL variable, and default it well above
Fly's health-check interval (documented in `docs/DESIGN.md` as part of the existing
liveness/readiness split) rather than reusing `HEALTH_PROBE_BUDGET`.
**Warning signs:** Voyage or Anthropic dashboard call volume tracking `/health` traffic
1:1 instead of at the TTL's rate.

## Code Examples

See Patterns 1–6 above — every example is drawn directly from this session's reads of the
actual source or from an empirical experiment run against the pinned dependency versions,
not from a generic tutorial. No additional standalone examples are needed.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| `/health` reports credential *presence* only (`bool(os.environ.get(...))`) | This phase adds *validity*, cached and probed asynchronously, beside presence | This phase (v1.2, Phase 19) | The Phase 11 revoked-key outage class becomes visible in `/health` within one probe TTL, without reintroducing the provider-call-in-liveness restart hazard the presence-only design exists to avoid |
| `run_finished` log lines carry only `run_id` | Service-initiated runs additionally get a `session_id`-bearing completion record | This phase | A completed run becomes addressable from `fly logs`/log aggregation by session, closing the exact gap that cost Phase 17 a wasted live run |
| The demo page ships no CSP header | A hash-based `Content-Security-Policy` covering the page's one script and one style block | This phase | Closes a Phase 12-deferred item; the page needed no code change to satisfy it because it was already written as one self-contained file with no inline handlers or style attributes (UI-SPEC, verified this session) |

**Deprecated/outdated:** none — this phase adds capability, it does not retire anything.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | An invalid/revoked Anthropic API key raises `anthropic.AuthenticationError` specifically (rather than some other `APIStatusError` subclass) on a real `count_tokens` call | Pattern 2 | Low — even if the exact subclass differs, `AuthenticationError` is `APIStatusError`'s documented 401 case and the base class `APIStatusError` still distinguishes "provider answered with an error" from `APIConnectionError` ("no answer at all"); worst case the planner catches `APIStatusError` with `status_code == 401` instead of the named class, a one-line change |
| A2 | An invalid/revoked Voyage API key raises `voyageai.error.AuthenticationError` specifically on a real `embed` call | Pattern 2 | Low — same fallback as A1 via the shared `VoyageError` base and an inspectable `http_status` attribute (VERIFIED this session: `VoyageError.__init__` stores `self.http_status`) |
| A3 | A reasonable credential-probe TTL default sits somewhere in the tens-of-seconds-to-minutes range, well above Fly's health-check polling interval | Pitfall 4 | Low — this is a tunable `os.environ`-read default with a documented floor pattern already established (`health_probe_budget()`); wrong by 10x either direction costs at most a rate-limit warning or a slightly stale operator view, never a liveness failure |

**None of the load-bearing structural claims are assumed** — the LangGraph key-dropping
behavior, the exact log call site and fields, the exact hash values, the SDK exception class
lists, the SDK-lazy-construction behavior under an empty key, and the `store.create()`
signature were all verified directly against source or by running code in this repo's own
`.venv` this session.

## Open Questions

1. **Exact `event` name for the new `service.py`-emitted log line**
   - What we know: it must carry `run_id` + `session_id`; reusing `"run_finished"` verbatim
     at a second call site creates a double-count hazard (Pitfall 1).
   - What's unclear: whether the planner/user wants the literal string `run_finished` to be
     the one that gains `session_id` (accepting the graph.py line stays a *different*,
     unnamed-by-REQ event) or a new name entirely.
   - Recommendation: name it explicitly in the plan (e.g. `run_addressable`) and state the
     reasoning in a code comment at both call sites, so a future reader doesn't wonder why
     two "run finished"-shaped log lines exist for one run.

2. **Whether to open a dedicated `ThreadPoolExecutor` for credential probes or share
   `_probes()`**
   - What we know: sharing is simpler and matches "rhyme with existing machinery"; a
     dedicated pool isolates congestion.
   - What's unclear: whether store-probe congestion under real Fly load is severe enough to
     matter (no production evidence gathered in this research pass).
   - Recommendation: share `_probes()` for v1 (default recommendation above); revisit only
     if operational evidence shows contention.

3. **EXCLUDED vs ATTRIBUTED for Voyage probe spend**
   - What we know: EXCLUDED is the zero-new-code default; ATTRIBUTED has no existing sink.
   - What's unclear: whether the user has a preference beyond CONTEXT's "deliberately, stated
     in code" instruction (which mandates the decision be explicit, not which way it goes).
   - Recommendation: EXCLUDED, per Pattern 4's reasoning — flag for a
     `checkpoint:human-verify` or explicit CONTEXT confirmation if the planner disagrees.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `anthropic` SDK | Anthropic validity probe | ✓ (installed in `.venv`) | 0.120.0 [VERIFIED this session] | — |
| `voyageai` SDK | Voyage validity probe | ✓ (installed in `.venv`) | 0.5.0 [VERIFIED this session] | — |
| `ANTHROPIC_API_KEY` | Anthropic probe to actually succeed | ✗ in this dev/research sandbox (access to read `.env` was denied by the sandbox's own permission system, consistent with the keyless-suite convention; no key was read or used) | — | Keyless suite: probe must be exercised via fakes in tests, never a live call; production carries the key via `fly secrets` |
| `VOYAGE_API_KEY` | Voyage probe to actually succeed | ✗ in this dev/research sandbox (same reasoning as above) | — | Same as above |
| LangGraph | The empirical experiment in Finding/Pattern 5 | ✓ | 1.2.9 [VERIFIED this session via `pip show langgraph`] | — |

**Missing dependencies with no fallback:** none — the two missing items (real API keys) are
*supposed* to be missing in this environment; the keyless suite is the documented, correct
posture for dev/test/research, and this research deliberately did not attempt to read or use
real credentials.

**Missing dependencies with fallback:** both provider keys — fallback is fakes in tests
(see Test Inventory) and real Fly secrets in production.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest [confirmed via existing `tests/*.py` files this session] |
| Config file | `pyproject.toml` (pytest section not separately inspected this session — existing suite convention: `pythonpath = [".", "src", "tests"]` per `test_service.py:81`'s comment) |
| Quick run command | `pytest tests/test_service.py -k health -q` (credential-validity work), `pytest tests/test_service.py -k demo -q` (CSP work) |
| Full suite command | `pytest -q` (keyless: `ANTHROPIC_API_KEY="" VOYAGE_API_KEY="" pytest -q`, per house convention) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REQ-health-credential-validity | No-keys state reports `valid: null`, never `false` | unit | `pytest tests/test_service.py -k credential_valid_null -x` | ❌ Wave 0 (new test in `test_service.py`, alongside existing `test_health_treats_an_empty_key_as_absent` at line 1511) |
| REQ-health-credential-validity | A valid-looking key (faked success) reports `valid: true` with a `checked_at` timestamp | unit | `pytest tests/test_service.py -k credential_valid_true -x` | ❌ Wave 0 |
| REQ-health-credential-validity | A bad key (faked `AuthenticationError`) reports `valid: false`, distinct from a provider outage | unit | `pytest tests/test_service.py -k credential_invalid_key -x` | ❌ Wave 0 |
| REQ-health-credential-validity | A provider outage (faked `APIConnectionError`/5xx) reports `valid: null`/some "could not determine" state, distinct from `false` | unit | `pytest tests/test_service.py -k credential_provider_down -x` | ❌ Wave 0 |
| REQ-health-credential-validity | `/health` never blocks on a live provider call (liveness untouched) | unit | `pytest tests/test_service.py -k liveness_never_calls_provider -x` | ❌ Wave 0 — the mutation probe: make the fake probe raise/hang and assert `/health` still returns 200 promptly |
| REQ-health-credential-validity | Probe spend excluded (or attributed) from the embedding meter, matching the chosen design | unit | `pytest tests/test_usage.py -k probe_spend -x` or `pytest tests/test_service.py -k probe_spend -x` | ❌ Wave 0 |
| REQ-health-credential-validity | Cache is genuinely reused within TTL (a second `/health` call within the TTL does not re-probe) | unit | `pytest tests/test_service.py -k credential_cache_reused -x` | ❌ Wave 0 |
| REQ-health-credential-validity | `/ready` is untouched by this phase (still only reports stores) | unit | `pytest tests/test_service.py -k ready -q` (existing tests should stay green unmodified — a non-vacuity check that `/ready`'s JSON keys don't gain a credentials block) | ❌ Wave 0 for the explicit negative assertion; existing `/ready` tests already exist |
| REQ-run-finished-session-id | A completed `/research` (new session) run's log line carries the session_id the response reports | unit (caplog) | `pytest tests/test_service.py -k run_finished_session_id -x` | ❌ Wave 0 |
| REQ-run-finished-session-id | A completed `/sessions/{id}/ask` (existing session) run's log line carries the same session_id as the path parameter | unit (caplog) | `pytest tests/test_service.py -k run_finished_followup_session_id -x` | ❌ Wave 0 |
| REQ-run-finished-session-id | The two events (`graph.py`'s and `service.py`'s) are not the same `event` string, or if they are, exactly one fires per run | unit (caplog) | `pytest tests/test_service.py -k run_finished_no_double_count -x` | ❌ Wave 0 |
| REQ-demo-csp-header | `/` (text/html) response carries a `Content-Security-Policy` header with both `sha256-` sources and no `unsafe-inline` | unit | `pytest tests/test_service.py -k csp_header_present -x` | ❌ Wave 0 |
| REQ-demo-csp-header | The header's hashes are derived fresh from `static/index.html`, not hand-copied — a mutated byte in the script block fails the test | unit (drift guard, the load-bearing one per CONTEXT) | `pytest tests/test_service.py -k csp_derivation -x` or a new `tests/test_csp.py` | ❌ Wave 0 |
| REQ-demo-csp-header | Exactly one `<script>` and one `<style>` block, zero inline handlers, zero `style=` attributes | unit | `pytest tests/test_service.py -k csp_counts -x` | ❌ Wave 0 |
| REQ-demo-csp-header | SSE routes' `Cache-Control`/`X-Accel-Buffering` headers are unaffected | unit | `pytest tests/test_service.py -k sse_headers_unchanged -x` (may already be implicitly covered; add an explicit assertion) | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** the relevant `-k` filtered run above (sub-second to a few seconds).
- **Per wave merge:** `pytest -q` keyless, full suite.
- **Phase gate:** full suite green before `/gsd-verify-work`, plus the manual acceptance
  checks already enumerated in `19-UI-SPEC.md` (curl for the header, a live browser check
  in both light/dark for zero console CSP violations).

### Wave 0 Gaps

- [ ] `tests/test_service.py` — new tests for all `/health` credential-validity cases above;
      extend the existing `make_client`/`FakeClient` fixtures (see below) rather than
      building new ones.
- [ ] `tests/test_service.py` (or new `tests/test_csp.py`) — the CSP derivation and header
      tests.
- [ ] `graph.log` fakes: `FakeClient` (test_graph_smoke.py:54-93, reused by
      test_service.py:22,177) needs a `.messages.count_tokens(...)` method addable without
      disturbing its existing `.create(...)` behavior — it can be configured to return a
      stub `input_tokens` value or raise a named exception.
- [ ] Voyage probe fakes: `FakeVoyageClient`/`voyage_embedder()` (test_memory_stores.py:
      232-247) already supports exactly this shape — `embedder._client = FakeVoyageClient(...)`
      set directly, bypassing the lazy `voyageai.Client()` construction, keyless-safe by
      construction. A raising variant (`FakeVoyageClient.embed` raising
      `voyageai.error.AuthenticationError`/`APIConnectionError`) needs to be added.
- [ ] No new test *framework* install needed — pytest and its existing fixtures cover
      everything.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | This phase does not touch caller authentication (identity cookie, session ownership) |
| V3 Session Management | no (adjacent) | `session_id` is logged, not altered; no session lifecycle change |
| V4 Access Control | no | `/health` remains an open ops endpoint by existing design (`guard`'s own docstring: "Ops reads... stay open on purpose", service.py:169-172) — unchanged by this phase |
| V5 Input Validation | n/a | No new user-controlled input surface is introduced |
| V6 Cryptography | no | No cryptographic material is introduced; the CSP hash is a content-integrity check, not a secret |
| V14 Configuration (CSP is ASVS's security-headers area) | yes | Hash-based `script-src`/`style-src`, `default-src 'none'`, `base-uri 'none'`, `frame-ancestors 'none'` — exactly what ASVS's security-headers guidance recommends over `'unsafe-inline'` |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Credential leakage via `/health` | Information Disclosure | Already mitigated by the existing presence-not-value convention (`bool(os.environ.get(...))`); this phase's validity fields must follow the same rule — never echo the key, never echo the raw exception message from the SDK (which could, in principle, echo request headers back — the existing `_redact()` helper (service.py:453-460) strips URL credentials from store-probe error text; the credential probe's error text should be similarly capped/redacted rather than passed through raw, since an SDK error message is not guaranteed never to include request metadata) |
| CSP bypass via `unsafe-inline` | Tampering (XSS via injected inline script) | Explicitly ruled out by CONTEXT and by the hash-based design; the drift-fails-a-test property is the actual enforcement mechanism — a header that silently stops matching the page is as bad as no header |
| Log-line credential/PII leakage | Information Disclosure | `session_id` is an opaque UUID, not PII; adding it to logs carries no new leakage risk beyond what already exists for `run_id` |
| Restart-loop DoS via a flapping provider | Denial of Service (self-inflicted) | This is the exact hazard CONTEXT names explicitly ("Fly's check must never transitively call a provider") — mitigated structurally by keeping the credential probe entirely off the `/ready`/liveness path, per Finding 1's cache-and-fire-and-forget design |

## Sources

### Primary (HIGH confidence — direct source reads and empirical verification this session)

- `service.py` (995 lines, read in full/relevant sections this session) — lifespan, probe
  executor, `/health`, `/ready`, `index()`, `_execute`/`_stream`, `_sse_response`
- `graph.py` (relevant sections read this session) — `AgentState`, `initial_state`,
  `followup_state`, `client()`/`memory()` lazy singletons, the `run_finished` log call
- `observability.py` (read in full this session) — logger singleton, JSON formatter, span
- `identity.py` (read in full this session) — middleware header-append pattern
- `usage.py` (relevant sections read this session) — `VOYAGE_PRICES`, embedding meter
- `memory.py` (relevant sections read this session) — `VoyageEmbedder`, `.embedder` accessor
- `sessions.py` (relevant sections read this session) — `store.create()` signature
- `tests/test_service.py`, `tests/test_graph_smoke.py`, `tests/test_memory_stores.py`,
  `tests/test_observability.py`, `tests/test_usage.py` (relevant sections read this session)
  — existing fixture and fake patterns
- `README.md:289`, `docs/OPERATIONS.md:1-45` (read this session) — the doc surfaces this
  phase's own CONTEXT flags for a possible (non-required) touch
- Empirical: `python -c` experiments run in this repo's `.venv` this session against the
  pinned `anthropic==0.120.0`, `voyageai==0.5.0`, `langgraph==1.2.9` — SDK signatures,
  exception hierarchies, lazy-construction behavior under empty keys, and the
  undeclared-state-key-drop behavior
- `19-UI-SPEC.md`, `19-CONTEXT.md`, `.planning/REQUIREMENTS.md`, `.planning/STATE.md`
  (all read this session)

### Secondary (MEDIUM confidence — official documentation, fetched/searched this session)

- https://platform.claude.com/docs/en/build-with-claude/token-counting — fetched this
  session; confirms `count_tokens` is free and independently rate-limited from the Messages
  API, gives the exact Python call shape and response shape (`{"input_tokens": N}`)

### Tertiary (LOW confidence — general web search, not independently re-verified against a primary source)

- WebSearch results on Voyage's `AuthenticationError` semantics (mirrored via DeepWiki, not
  Voyage's own docs) — the exception **class existing** in the installed package is VERIFIED
  (primary), but its exact trigger condition on a live bad-key call is not independently
  confirmed beyond standard REST 401 semantics; see Assumption A2

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependency, every capability composes with code read
  directly this session
- Architecture (probe cache/refresh shape, run_finished fix location): HIGH — the two most
  load-bearing claims (LangGraph drops undeclared keys; the FileResponse `headers=` kwarg
  exists) were verified empirically this session, not assumed
- Pitfalls: HIGH for the double-count and absent-key pitfalls (grounded in direct source
  reads and this project's own documented history of counting bugs in STATE.md); MEDIUM for
  the TTL-vs-Fly-interval pitfall (no live Fly health-check interval value was independently
  re-confirmed this session, though `docs/DESIGN.md` documents the general liveness/
  readiness split)

**Research date:** 2026-08-14
**Valid until:** 30 days (stable internal codebase; the only external-facing fact with any
volatility — Anthropic/Voyage pricing and endpoint behavior — was pinned to dated,
already-effective-dated tables in `usage.py` that this phase does not need to change)
