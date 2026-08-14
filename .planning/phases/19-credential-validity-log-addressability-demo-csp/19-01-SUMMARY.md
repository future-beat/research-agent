---
phase: 19-credential-validity-log-addressability-demo-csp
plan: 01
subsystem: service
tags: [health, credential-validity, fire-and-forget, provider-outage, cost-exclusion, keyless-suite]

# Dependency graph
requires:
  - phase: 19-credential-validity-log-addressability-demo-csp
    plan: "research"
    provides: "the typed-exception mapping for both SDKs, count_tokens being free and independently rate-limited, and the embedding-meter mechanics P-04 rests on"
  - phase: 11-postgres-and-health
    plan: "01"
    provides: "_probes() and _probe() — the executor this shares (P-03) and the docstring that argues why the credential read path must NOT copy _probe()'s blocking wait"
  - phase: 14-cost-honesty
    plan: "02"
    provides: "usage.embedding_meter / report_embedding — the no-op-outside-a-meter shape that makes the probe's exclusion structural rather than a special case"
provides:
  - "GET /health carries anthropic_valid/_checked_at/_error and the three voyage_* twins beside unchanged presence booleans"
  - "service.credential_probe_ttl() — CREDENTIAL_PROBE_TTL, 300.0s default, 30.0s floor"
  - "service._CREDENTIAL_PROBES — one row per provider (env var, probe, key-invalid predicate); a third provider is a row, not a fourth copy"
  - "service._credential_status / _refresh_credential / _reset_credential_cache — the read path, the pool-thread refresh, and the test-teardown hook"
  - "the measured fact that a ContextVar does not cross into a ThreadPoolExecutor worker, which is what makes the probe's spend excluded by construction"
  - "tests/test_graph_smoke.py FakeClient.count_tokens; tests/test_memory_stores.py FakeVoyageClient(error=...)"
affects: [19-02, 19-03, 22]

# Tech tracking
tech-stack:
  added: []  # zero packages installed; both SDKs pre-existing and pinned (19-RESEARCH § Package Legitimacy Audit: N/A)
  patterns:
    - "A liveness endpoint may LEARN from a provider but must never WAIT on one. The read path serves a cache and submits the refresh; `.result()` anywhere on it converts a third party's outage into our restart loop."
    - "Register the in-flight Future under the SAME lock acquisition as the submit. The worker pops its own guard in a `finally`, so a submit-then-register sequence can have the guard popped before it is recorded — leaving a stale Future that blocks every later refresh forever."
    - "A meter reading zero is also what a broken accounting seam reads. Any exclusion test needs a positive control on the same object inside the same meter, or it is measuring nothing."
    - "An `==` assertion over a payload block turns every additive change into a failure while saying nothing about the property it was written for. Pin by name."

key-files:
  created: []
  modified:
    - src/research_agent/service.py
    - tests/test_service.py
    - tests/test_graph_smoke.py
    - tests/test_memory_stores.py

key-decisions:
  - "The plan's blocking mutation, run as written, reds for the WRONG reason — and the wrong reason is more interesting than the right one. Replacing the submit-and-return-cache with `.result(timeout=5)` inside the cache lock does not merely serialize /health behind a provider: it DEADLOCKS, because the worker's `finally` needs that same lock to pop its own in-flight guard. It reds as a 5s TimeoutError rather than as the cold-read assertion the plan named. The mutation was re-run with the wait moved outside the lock to isolate the property, and then produced the named red (`assert True is None`) plus `/health waited 5.01s`. Both observations are recorded because the deadlock is a real property of the lock discipline this plan introduced, not noise."
  - "The probe's cost exclusion holds because a ContextVar does not propagate into a ThreadPoolExecutor worker — each thread starts with an empty context, so `report_embedding` finds no meter. This is stronger than the plan's framing ('a probe that opens none'): the probe could not observe a meter even if the request thread had one open. Measured directly by the mutation (inline on the metered thread → `assert 25 == 0`)."
  - "A key-invalid verdict also stores the exception class name, not just `valid: false`. The plan specified the error field only for the unknown branch. Storing it for both costs nothing (a class name is not a message) and means an operator reading `valid: false` can see WHICH rejection produced it. No test asserts it is null, so nothing was narrowed."
  - "`_refresh_credential` guards the key-invalid predicate itself in a try/except. `_voyage_key_invalid` imports its SDK inside the function (memory.py's discipline), so a broken install would raise from the predicate rather than the probe — and an unguarded raise there would skip the cache write while the `finally` popped the guard, leaving that provider permanently cold and re-probing on every request. A predicate that cannot load its SDK is a 'could not determine', which is what it now reports."
  - "The presence booleans are computed in `health()` as they always were, and the registry is iterated only for the suffixed keys. Deriving presence from the registry's `env` row instead would have dropped `voyage` from the payload for the length of Task 1 — an additive-only violation living inside the tracer commit, which is exactly the state a bisect lands on."

# Metrics
duration: 30min
completed: 2026-08-14
status: complete

actuals:
  tokens: 8170     # chars/4 over the realized src+tests diff (32,678 chars)
  tasks: 3
  commits: 5
---

# Phase 19 Plan 01: The credential probe Summary

**One-liner:** `/health` now reports whether the Anthropic and Voyage keys actually work — six flat fields beside the unchanged presence booleans, backed by a cached probe the liveness path submits and never waits on, so the Phase 11 revoked-key outage becomes visible within one TTL without putting a provider's outage on the path of the check that restarts the process.

## Measured baselines and deltas

| Gate | Before | After | Delta |
|------|--------|-------|-------|
| Full suite, keyless (`ANTHROPIC_API_KEY="" VOYAGE_API_KEY="" .venv/bin/pytest`) | 749 passed / 67 skipped | **760 passed / 67 skipped**, exit 0 | **+11 passed, +0 skipped** — accounted for test-by-test below |
| `tests/test_service.py` | 128 passed | 139 passed | +11 (every new test lives here) |
| `tests/test_graph_smoke.py` + `tests/test_memory_stores.py` | 74 passed | 74 passed | ±0 — both files gained fake capability, no test |
| Offline evals (`ANTHROPIC_API_KEY="" .venv/bin/python -m evals`) | 41/41, exit 0 | **41/41 (100% vs 90% required), exit 0** | unchanged |
| `.venv/bin/ruff check .` and `.venv/bin/ruff check src tests evals` | clean | clean | — (two errors introduced and fixed inside the wave; see Deviations) |
| Suite warnings | 2 | 2 | unchanged — both pre-existing (starlette `httpx` deprecation, chromadb `asyncio.iscoroutinefunction`); this plan added none |

### The +11, test by test

The plan claimed "roughly eleven tests across the three tasks" and asked for the real number. The measured delta is **exactly 11** — but the plan's own named set is **ten**, and the eleventh is an addition made during Task 3 (see Deviations). The claim landed on the right number for a reason the plan did not state.

| # | Test | Task |
|---|------|------|
| 1 | `test_health_credential_valid_true_after_the_probe_lands` | 1 |
| 2 | `test_health_credential_invalid_key_reads_false` | 2 |
| 3 | `test_health_credential_provider_down_reads_null_with_an_error` | 2 |
| 4 | `test_health_credential_error_never_carries_the_sdk_message` | 2 |
| 5 | `test_health_credential_probe_spend_is_excluded_from_the_embedding_meter` | 2 |
| 6 | `test_health_credential_absent_key_reads_null_and_never_probes` | 3 |
| 7 | `test_health_credential_single_refresh_while_one_is_in_flight` | 3 |
| 8 | `test_health_credential_cache_is_reused_within_the_ttl` | 3 |
| 9 | `test_health_credential_probe_ttl_floors_at_flys_check_interval` | 3 (added — Rule 2) |
| 10 | `test_health_never_waits_on_a_hanging_credential_probe` | 3 |
| 11 | `test_ready_carries_no_credentials_block` | 3 |

No test was deleted and none became skipped. One existing test's assertion **style** changed (`test_health_reports_credential_presence_never_values`), which is covered under Deviations rather than counted here.

## What shipped

### Task 1 — the tracer: `fce3135` (red), `1e1298a` (green)

The RED commit went first and was observed failing with `KeyError: 'anthropic_valid'` plus two teardown errors for the not-yet-existing `_reset_credential_cache`. The GREEN commit added, in `service.py`:

- `credential_probe_ttl()` — `CREDENTIAL_PROBE_TTL`, 300.0s default, floored at 30.0s. The docstring states P-02's distinction: this bounds how OFTEN a provider is asked anything, `HEALTH_PROBE_BUDGET` bounds how LONG one store probe may take.
- `_credential_cache` / `_credential_cache_lock` / `_credential_inflight`, plus `_reset_credential_cache()` for test teardown.
- `_refresh_credential()` — three outcomes, storing only `type(exc).__name__`.
- `_credential_status()` — the read path: presence gate, staleness check, `_probes().submit(...)` with no `.result()`, return the current cache.
- `_probe_anthropic()` / `_anthropic_key_invalid()` and the `_CREDENTIAL_PROBES` registry.
- `health()`'s credentials block, plus a docstring correction: the old sentence claimed /health "deliberately never calls Claude or Voyage", which this plan falsifies. It now says it never *waits* on one and marks that as the weaker, deliberate claim — rather than leaving a true-sounding sentence to quietly go stale.

The tracer's own gate was re-run end to end before any expansion task, per the tracer contract: both automated verifies green, mutation red.

### Task 2 — the Voyage arm: `836c8b5` (red), `59ab6f7` (green)

Four tests red first — and the meter test failed on its **control** (`AssertionError: the probe never embedded anything`) rather than on the zero, which is the correct red for a test whose whole risk is passing vacuously.

`_probe_voyage()` reaches `graph.memory().embedder` and calls `embed_query("ping")` — the production seam, so the test exercises the wrapper that reports tokens rather than a stand-in that doesn't. No embedder configured raises a plain `RuntimeError`, which `_refresh_credential` reads as "could not determine" rather than as a verdict on a key. The P-04 exclusion comment sits directly above the call and names the pinning test, so the next reader checks a gate instead of trusting prose.

Adding the provider was, as designed, **one registry row** — `health()` needed no change.

### Task 3 — the invariants: `368008e`

Six gates. All six passed on their first run, which under house discipline makes them the suspect rather than the evidence — so each was put under the mutation that should red it before being trusted. Every one did (below).

## Mutation probes — each observed red, then reverted

| # | Mutation | Observed red |
|---|----------|--------------|
| 1a | `_credential_status` blocks: `submit(...).result(timeout=5)` **inside** the cache lock | `TimeoutError` after 5s — a deadlock, not the named assertion (see below) |
| 1b | Same block, moved **outside** the lock to isolate the property | `assert True is None` — the cold read returned `true` because /health waited |
| 2a | `_refresh_credential`'s two exception branches collapsed to `valid: False` | `assert False is None` — an outage would report a good key as bad |
| 2b | The refresh called inline on the metered thread instead of via the pool | `assert 25 == 0` — the zero comes from the worker's empty context |
| 3a | The `if not present` early return deleted | `AssertionError: an unconfigured key was sent to a provider`, `assert [1, 1] == []` |
| 3b | The `name not in _credential_inflight` clause deleted | `assert [1, 1, 1] == [1]` — three reads, three probes |
| 3c | Read path blocked (1b), targeted at the liveness gate | `/health waited 5.01s on a provider that never answered` |

Seven mutations run for six named ones: probe 1 was run twice because the plan's version reds for a reason the plan did not predict.

### Probe 1, and why it was run twice

The plan names one mutation for the tracer: replace the submit-and-return-cache with `.result(timeout=5)`, and expect the cold-read assertion to red. Run exactly as written, it reds — as a **5-second `TimeoutError`**, in a different test, for a different reason.

The cause is this plan's own lock discipline. `_credential_status` holds `_credential_cache_lock` across the submit; `_refresh_credential` needs that same lock in its `finally` to pop its in-flight guard. Waiting on the Future while holding the lock the Future's worker must acquire is a deadlock, bounded only by the `timeout=5`.

That is a genuine property worth recording — it is the same coupling that makes the submit-and-register-under-one-lock ordering correct (see key-decisions) — but it confounds the gate. The mutation was re-run with the wait moved outside the lock, which is the change a careless refactor would actually make, and then produced the named red plus the liveness-gate red. Both runs are recorded in 19-VALIDATION row 19-01-T3.

## The cost exclusion is structural, and the measurement says why

19-RESEARCH and P-04 justify the exclusion as "a probe that opens no meter". True, but weaker than what actually holds: `_EMBEDDING_METER` is a `ContextVar`, and a `ThreadPoolExecutor` worker starts with an empty context rather than a copy of the submitter's. The probe body **could not observe** a meter even if the request thread had one open.

Mutation 2b measures exactly this: move the refresh onto the metered thread and the same probe reports 25 tokens into the meter. The zero is produced by the execution context, not by an embedder that stays quiet — which is what the test's positive control asserts from the other side, in the same meter, on the same embedder object.

## Deviations from plan

### [Rule 1 — bug] The pre-existing whole-dict assertion had to change, and its `==` was the defect

`test_health_reports_credential_presence_never_values` asserted `body["credentials"] == {three keys}`. Additive growth failed it (`Left contains 3 more items`, with the three presence items reported identical). It is now pinned name by name, with a comment stating why: an `==` over a block designed to grow turns every additive change into a failure while saying nothing about the property the test exists for — that presence is reported and the value never is. The leak assertion (`"secret-value" not in json.dumps(body)`) is untouched. **Commit:** `1e1298a`.

### [Rule 2 — missing gate] `test_health_credential_probe_ttl_floors_at_flys_check_interval` added

Threat T-19-03's mitigation names "a 30s TTL floor (P-02) so probe volume tracks the TTL rather than request volume", and the plan's five Task 3 tests left the floor itself unpinned — only mentioned in a comment. A register mitigation with no gate is the shape this project keeps finding decorative. The test pins the floor, the `ValueError` fallback, and the default. It is the eleventh test, and the reason the plan's "roughly eleven" claim happens to land exactly. **Commit:** `368008e`.

### [Rule 2 — missing guard] The key-invalid predicate is called inside a try/except

Not in the plan. `_voyage_key_invalid` imports `voyageai.error` inside the function, so a broken SDK install raises from the *predicate*, not the probe — and an unguarded raise there would propagate past the cache write while the `finally` still popped the guard, leaving that provider permanently cold and re-probing on every single request. Exactly the per-request prober P-02's floor exists to prevent, reached by a different road. A predicate that cannot load its SDK now reports "could not determine". **Commit:** `59ab6f7`.

### [Rule 3 — blocking] Two ruff errors introduced and fixed inside the wave

`B007` (unused `spec` in `health()`'s registry loop — resolved by iterating keys, since presence is deliberately read outside the registry) and `I001` (the new `voyageai.error` import's explanatory comment needed a blank line before it). Both fixed before their commits; `ruff check .` and `ruff check src tests evals` are clean.

### [anchors] Every line anchor the plan cited was checked and none had drifted

`service.py:463-501`, `504-565`, `591-639`; `graph.py:86-94`; `memory.py:105-166`; `usage.py:438-475`; `test_service.py:152-213`, `1479-1520`, `1707-1800`; `test_graph_smoke.py:54-93`; `test_memory_stores.py:225-247`. All correct — the first wave in a while where they were.

### [research drift, minor] 19-RESEARCH's `voyageai.error` inventory is not quite the installed one

19-RESEARCH:370 lists `TryAgain` and `Timeout` among `voyageai.error`'s classes. Measured against the pinned `voyageai 0.5.0` in this repo's `.venv`, `dir(voyageai.error)` has neither, and has `ServiceUnavailableError` and `VideoProcessingError` that the research list omits. Immaterial to this plan — both classes it actually depends on (`AuthenticationError`, `APIConnectionError`) are present and were verified this session — but recorded so a later phase does not build on the inventory as written.

### [not a deviation, stated to be explicit] Nothing outside the plan's file list was touched

`README.md` (Limitations bullets — Phase 22), `src/research_agent/static/index.html` (wave 2's zero-edit budget), the CSP, and the `run_finished` log line are all unmodified. `git show --stat` across all five commits lists exactly four files: `service.py`, `test_service.py`, `test_graph_smoke.py`, `test_memory_stores.py`.

## Acceptance criteria, measured

| # | Criterion | Result |
|---|-----------|--------|
| 1 | Six flat keys beside unchanged presence booleans | ✅ `anthropic_valid/_checked_at/_error` + three `voyage_*`; `anthropic`, `voyage`, `identity_signing` keep name, `bool` type and value |
| 2 | Absent → null + zero calls; accepted → true; rejected → false; unreachable → null + class-name error | ✅ four tests, each with its own mutation red |
| 3 | /health prompt against a probe that never finishes; /ready untouched | ✅ 200 + `status ok` well inside the 1.0s bound; `"credentials" not in /ready` |
| 4 | Voyage probe contributes zero to an open meter, against a positive control | ✅ 0 across the probe, 25 for a direct `embed_query` in the same meter on the same embedder |
| 5 | Suite green, ruff clean, every gate red under its own mutation | ✅ 760/67, both ruff invocations clean, 7 mutations observed red and reverted |

## Threat register — dispositions discharged

| Threat | Disposition | How |
|--------|-------------|-----|
| T-19-01 Information disclosure | mitigate | Only `type(exc).__name__` is ever stored; `str(exc)` appears nowhere in the module. Pinned by the secret-shaped-token test against the full response text |
| T-19-02 Self-inflicted DoS via liveness | mitigate | No `.result()` on the read path; never-waits test plus three separate blocking-mutation reds; `/ready` gains nothing |
| T-19-03 Provider rate limit / spend | mitigate | Presence gate (mutation red), one in-flight refresh per provider (mutation red), 30s TTL floor (now gated — see Deviations) |
| T-19-04 Repudiation in cost accounting | mitigate | Excluded by construction, stated in a comment naming its test, pinned with a positive control, and confirmed by mutation |
| T-19-05 Executor thread starvation | accept | Unchanged: shares `_probes()`' three workers, identical exposure to the store probes already there |
| T-19-SC Package installs | accept | No installs; both SDKs pre-existing and pinned |

## What waves 2 and 3 inherit

- `service.py` has a new ~150-line credential section between `_probe()` and `_dependencies()`. Wave 3's `run_finished` work is elsewhere in the file; wave 2's CSP work is on the `index()` route. No overlap, but both will rebase over this.
- `tests/test_service.py` has a new credential block sited just before `test_the_root_url_is_not_a_404`, plus `settle_credential_probes()` and `install_voyage()` helpers either wave may reuse.
- `make_client`'s teardown now calls `service._reset_credential_cache()`. Any new fixture that drives `/health` outside `make_client` must do the same or inherit another test's verdict.
- **Unchanged and load-bearing for wave 2:** `src/research_agent/static/index.html` has zero modifications on this branch, so the zero-edit budget is intact entering wave 2.

## Deferred, recorded rather than silent

- **A real provider round trip.** The suite is keyless by invariant, so `valid: true` against a live key is first observable on the first deploy after merge. This is 19-VALIDATION's Manual-Only row and belongs to phase close, not to this plan.
- **The `/health` doc surface.** `docs/OPERATIONS.md` and any DESIGN text describing `/health`'s credentials block now under-describe it. 19-VALIDATION assigns the doc pass to **19-03**; not touched here.
- **README's Limitations bullet** stays exactly as written — Phase 22 owns it.

## Self-Check: PASSED

- `src/research_agent/service.py`, `tests/test_service.py`, `tests/test_graph_smoke.py`, `tests/test_memory_stores.py` — all present and modified on this branch.
- Commits `fce3135`, `1e1298a`, `836c8b5`, `59ab6f7`, `368008e` — all present in `git log`.
- No stubs, no TODO/FIXME, no skipped tests introduced. Every `<verify>` command in the plan was run; no gate is unrun.
