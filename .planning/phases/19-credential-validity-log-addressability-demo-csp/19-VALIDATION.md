---
phase: 19
slug: credential-validity-log-addressability-demo-csp
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-08-14
plans_assigned: 2026-08-14
reconciled: 2026-08-14
---

# Phase 19 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest; `pythonpath = [".", "src", "tests"]`; no `conftest.py` |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `.venv/bin/pytest tests/test_service.py tests/test_observability.py tests/test_deploy_config.py` |
| **Full suite command** | `.venv/bin/pytest` (bare — a second `-q` hides the count line) |
| **Estimated runtime** | ~30 seconds full |

**Measured baseline entering this phase (2026-08-14):** 749 passed / 67 skipped keyless;
offline evals 41/41 exit 0; ruff clean.

---

## Plan / Wave Map

The three surfaces are independent in concept but all three edit `src/research_agent/service.py`
and `tests/test_service.py`, so they run sequentially rather than in parallel.

| Plan | Wave | Requirement | Surface |
|------|------|-------------|---------|
| 19-01 | 1 | REQ-health-credential-validity | The cached credential probe and `/health`'s new fields |
| 19-02 | 2 | REQ-demo-csp-header | `csp.py`, the header on `index()`, and the derivation gates |
| 19-03 | 3 | REQ-run-finished-session-id (+ the `/health` doc surface) | The completion log line, the doc pass, the README whole-file pass |

---

## Sampling Rate

- **After every task commit:** Run the quick command
- **After every plan wave:** Run the full suite, keyless
- **Before verification:** Full suite green plain; offline evals 41/41 exit 0
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

*(Rows below are the researched gate set. Task IDs, Plan and Wave were assigned at planning
2026-08-14; the executor fills Status with measured evidence.)*

| Task ID | Plan | Wave | Requirement | Criterion | Test Type | Automated Command / Mutation | Status |
|---------|------|------|-------------|-----------|-----------|------------------------------|--------|
| 19-01-T1, 19-01-T3 | 19-01 | 1 | REQ-health-credential-validity | `/health` carries validity fields beside the presence booleans, additive-only; keyless state reads `valid: null` (unknown), never `false` — a missing key is a presence fact, not a validity fact | unit (fake-driven, keyless) | `pytest tests/test_service.py -k credential`; mutation: delete the presence early-return in `_credential_status` so an absent key gets probed and reads `false` → `test_health_credential_absent_key_reads_null_and_never_probes` reds | ✅ MEASURED 2026-08-14 — six flat keys (`{anthropic,voyage}_{valid,checked_at,error}`) ship beside the three presence booleans, which keep their names, `bool` type and values; the pre-existing whole-dict `==` in `test_health_reports_credential_presence_never_values` became name-by-name, which is the additive property showing up rather than a relaxation. Absent key reads `valid/checked_at/error = null`. Mutation ran: presence gate deleted → `AssertionError: an unconfigured key was sent to a provider`, `assert [1, 1] == []` |
| 19-01-T2 | 19-01 | 1 | REQ-health-credential-validity | Key-invalid and provider-down are distinguished: `AuthenticationError` → invalid; `APIConnectionError`/5xx → unknown-with-error, NOT invalid — a provider outage must never report a key as bad | unit | fakes raising each typed exception; mutation: collapse the two branches in `_refresh_credential` → `test_health_credential_provider_down_reads_null_with_an_error` reds | ✅ MEASURED 2026-08-14 — `voyageai.error.AuthenticationError` → `voyage_valid false`; `voyageai.error.APIConnectionError` → `voyage_valid null` AND `voyage_error "APIConnectionError"`, both asserted since `null` alone cannot separate an outage from an unprobed key. A third test pins that no SDK message text reaches the body. Mutation ran: branches collapsed to `False` → `assert False is None` |
| 19-01-T3 | 19-01 | 1 | REQ-health-credential-validity | The liveness path never calls a provider: probe is fire-and-forget on the existing `_probes()` executor, `/health` serves the cache and never blocks on a provider call | unit + structural | mutation: replace the submit-and-return-cache with `submit(...).result(timeout=5)` → the cold-read assertion and `test_health_never_waits_on_a_hanging_credential_probe` red; a fake provider blocked on an Event must not change `/health` latency | ✅ MEASURED 2026-08-14 — `_credential_status` submits to `_probes()` and returns the cache; `.result()` appears nowhere on the read path. Against a probe blocked on an Event, `/health` returned 200 with `status ok` in well under the 1.0 s bound. Mutation ran twice: blocking OUTSIDE the cache lock → cold read `assert True is None` and `/health waited 5.01s on a provider that never answered`; blocking INSIDE the lock deadlocks against the worker's own `finally` (a louder red for the same cause, and the reason the refined variant was used to isolate the property) |
| 19-01-T1, 19-01-T3 | 19-01 | 1 | REQ-health-credential-validity | Cold cache returns `checked_at: null` rather than blocking; a stale read kicks exactly one refresh (no thundering herd) | unit | mutation: delete the `name not in _credential_inflight` clause → `test_health_credential_single_refresh_while_one_is_in_flight` reds | ✅ MEASURED 2026-08-14 — cold read returns `checked_at: null` and the verdict lands on a later request; three reads against a blocked probe submit exactly one refresh. Cache reuse within the TTL is pinned with a stale-side control (TTL forced to 0 → the probe count rises), so identical timestamps prove reuse rather than a refresh that can never happen. Mutation ran: in-flight clause deleted → `assert [1, 1, 1] == [1]` |
| 19-01-T2 | 19-01 | 1 | REQ-health-credential-validity | Voyage probe spend is EXCLUDED from cost accounting, and the code states so — `report_embedding()` is meterless outside a run context, pinned as a fact not an accident | unit | test asserts a probe leaves an open meter at zero WHILE a direct `embed_query` on the same embedder in the same meter reports non-zero (the non-vacuity control); mutation: run the refresh inline on the request thread → the excluded-spend test reds | ✅ MEASURED 2026-08-14 — probe leaves an open meter at 0 while `embed_query` on the SAME embedder in the SAME meter reports 25; the test also asserts the fake actually embedded, so neither side can pass vacuously. The exclusion is stated in a comment at the `embed_query` call naming this test. Mutation ran: refresh called inline on the metered thread → `assert 25 == 0`, confirming the zero comes from the pool thread's empty context (a `ContextVar` does not cross into a `ThreadPoolExecutor` worker) rather than from a silent embedder |
| 19-03-T1, 19-03-T2 | 19-03 | 3 | REQ-run-finished-session-id | A completed run is addressable from the logs: the service-side emission carries `session_id`, including for brand-new sessions (the id is minted AFTER the graph returns — research finding: LangGraph drops undeclared state keys, so the graph-side site cannot carry it) | unit (caplog) | log-capture tests across all four routes; mutation: emit before `on_complete` resolves → the new-session test reds. Per P-07 the service line is the one NAMED `run_finished`; the graph's terminal line becomes `graph_finished` and is asserted to carry no `session_id` | ✅ MEASURED 2026-08-14 — P-07's premise re-measured first rather than trusted: `run_finished` occurs **exactly once** repo-wide outside `.planning/` (`graph.py:638`), no test/doc/eval/dashboard reading it, so the rename is free as claimed. All four routes covered by six test items (`/research`, `/research/stream`, `/sessions/{id}/ask`, `/sessions/{id}/ask/stream`), each asserting exactly one `run_finished` whose `session_id` matches what the caller was told — the response body's id on the blocking routes, the terminal `result` event's on the streaming ones, the path parameter on both follow-ups. `run_id` asserted non-empty. `graph_finished` asserted present exactly once and asserted to carry **no** `session_id` attribute, which pins the structural fact the whole design rests on: a later attempt to thread the id through `AgentState` fails this test instead of silently doing nothing. `service.log is graph.log` asserted, so "one capture sees both modules" is a pin rather than an assumption. Mutation ran: the emission moved above `session_id = on_complete(final_state)` → `UnboundLocalError: cannot access local variable 'session_id'`. The plan offered two possible reds (NameError **or** mismatched id) and asked which; it is the first, and the second is **unreachable** — `_execute` takes no `session_id` parameter, so before `on_complete` there is no such name on any of the four routes, including the two where the caller knew the id all along |
| 19-03-T2 | 19-03 | 3 | REQ-run-finished-session-id | No double-count: `run_finished` semantics preserved — one completion event per run, not one per call site | unit | mutation (a): restore the graph's old event value so two sites share the name → the exactly-once test reds with a count of 2; mutation (b): move the emission into a `finally` → the failed-run test reds | ✅ MEASURED 2026-08-14 — `test_exactly_one_run_finished_record_per_request` counts 1 on a successful request (with `graph_finished == 1` beside it as non-vacuity, so the count cannot pass because nothing ran). Both mutations ran exactly as named: (a) the graph's event value restored to `run_finished` so two call sites share the name → `assert 2 == 1`, the predicted double-count; (b) the emission hoisted into a `finally` → `AssertionError: a run that failed reported itself finished`, `assert 1 == 0`. Both reverted, suite re-run green. **The plan's premise for (b) was wrong and the RED caught it:** the plan states the failed-run path "already emits `run_failed` (existing, untouched)", which is true of `_execute` and **false of `_stream`**, whose except arm swallows its exception to keep the SSE contract and logged nothing at all. A failed stream recorded its row, settled its reservation, sent the caller an error event, and left no trace in the log stream — and the demo page runs on the streaming routes, so that was every failed demo run. Fixed under Rule 2 (`_failed_log()`, shared by both arms), which is what makes "every HTTP-initiated run emits exactly one of the two" true of both paths rather than of one |
| 19-02-T1, 19-02-T3 | 19-02 | 2 | REQ-demo-csp-header | The demo page response carries the UI-SPEC's exact directive set; SSE and JSON routes carry NO CSP header | unit | header-presence test on `/` FileResponse branch asserting the seven directive names in order + header-absence on the JSON index and both stream routes; mutation: attach via middleware → the absence test reds on all three | ✅ MEASURED 2026-08-14 — `pytest tests/test_service.py -k "csp or sse or stream"` → 25 passed. `GET /` (`Accept: text/html`) carries `default-src 'none'; script-src 'sha256-…'; style-src 'sha256-…'; connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'` — directive NAMES asserted equal to `csp.DIRECTIVES` in order, and the body asserted byte-identical to the file on disk. No CSP on the JSON index or either stream, each of the three checked for a 200 first so an absence cannot pass on a request that never happened. Mutations ran: (a) `headers=` dropped from the FileResponse → `AssertionError: the demo page carries no CSP` (the membership assertion was added precisely so this reds as a named failure rather than as httpx's `KeyError`); (b) attachment moved into an `@app.middleware("http")` → `AssertionError: the CSP escaped its one call site onto: ['json index', 'research stream', 'ask stream']`. Recorded honestly: under (b) the SSE caching-header test stayed GREEN — Starlette's middleware added the header without disturbing `Cache-Control`/`X-Accel-Buffering`, so the absence test is the load-bearing gate on P-06 and the SSE test is a pin, not a tripwire for this mutation |
| 19-02-T2 | 19-02 | 2 | REQ-demo-csp-header | The derivation invariant: hashes in the policy are DERIVED from `static/index.html`'s real blocks by a test that also asserts block counts (1 script / 1 style) and zero inline-handler/`style=` attributes | unit | mutation: hand-maintain one hash as a literal in `csp.py` → the derivation test reds; add an `onclick=` to the page → the handler-count test reds. **Mutation refined at planning (P-05):** the originally-researched byte-edit mutation cannot red under runtime derivation, because a byte edit moves both sides of a derivation together — that is the design working, not a gap. The two mutations above replace it and test the same property more directly | ✅ MEASURED 2026-08-14 — `test_csp_hashes_are_derived_from_the_page_not_hand_maintained` recomputes both digests inline with `re`/`hashlib`/`base64` over `service.DEMO_PAGE` and never calls `csp.inline_blocks` or `csp.sha256_source`, so neither side of the comparison is the implementation. Both reproduce 19-UI-SPEC's reference literals byte-identically (`sha256-9r9Cu4iNyd4zpe8otNho5Q8WPI2YgqJmBM8l+2k7JnU=` script, `sha256-GjzXfxwdkdCrrRaX7wyDbcp+YGb15dhyT6JSLzaDWMg=` style) — a third independent derivation after the researcher's and the checker's. Served policy contains neither `unsafe-inline` nor `unsafe-hashes`. Counts measured 1 script / 1 style in BOTH the bare-tag form and the `<script`-prefix form, so `<script defer>` (invisible to the extraction) reds too; zero `on*`, zero `style=`, zero `javascript:` attribute values, with a positive control (`("input", "id", "q")`) so an empty walk cannot pass. Both P-05 mutations ran: (a) script source replaced with a one-character-off literal → `assert "script-src 'sha256-…JnU='" in "…JnV='…"`, and notably the Task-1 shape test stayed green, which is the intended division of labour (shape vs digits); (b) `onclick=""` added to the page's input → `assert [('input', 'onclick')] == []`. Both reverted; the page restored via `git checkout --` and confirmed clean |
| 19-02-T3 | 19-02 | 2 | REQ-demo-csp-header | index.html changes ZERO lines this phase (UI-SPEC change budget); the live page renders and streams identically | structural + manual | `git diff --stat "$(git merge-base main HEAD)" HEAD -- src/research_agent/static/index.html` prints nothing, and `git status --porcelain` on the same path prints nothing; manual acceptance per UI-SPEC checks (zero violations attributable to page resources) | ✅ MEASURED 2026-08-14 (automated half) — `git diff --stat cf660c2 HEAD -- src/research_agent/static/index.html` printed **nothing**; `git status --porcelain -- src/research_agent/static/index.html` printed **nothing**. The file does not appear in the branch's full diffstat at all. It was edited exactly once during the wave, as mutation (b) above, and restored before the commit that followed. Budget kept at zero, measured rather than remembered. **Manual half still pending** — browser CSP enforcement cannot run in pytest and the deploy is manual; UI-SPEC acceptance checks 1–7 belong to phase close (see Manual-Only table) |

---

## Manual-Only Verifications

**Both rows below are OPEN.** Neither can be closed from this repository: this
project's deploy is manual, and both need one. They are stated here rather than
quietly dropped at phase close, because a deferred check that nobody writes down
is a check that silently becomes a claim.

| Behavior | Why Manual | Status | Instructions |
|----------|------------|--------|--------------|
| Live page under CSP: full demo flow with zero page-resource violations | Browser CSP enforcement can't run in pytest | ⏳ **OPEN** — awaiting the first deploy after merge | UI-SPEC acceptance checks 1–7 against the deployed page (curl the header; page identical light and dark; full demo flow; periphery; cookie still minted; drift guard; `/health` fields). Check 2 reads "zero violations **attributable to page resources**" per the UI-checker's hedge, so a browser-initiated favicon probe cannot cosmetically fail it. What the automated side already proves: the exact served header, both hashes independently re-derived from the shipped file, and `index.html` at zero edits |
| A real provider probe round-trip | The suite is keyless by invariant | ⏳ **OPEN** — awaiting the first deploy after merge | `/health` shows `valid: true` with a fresh `checked_at` for both providers within one `CREDENTIAL_PROBE_TTL`. The keyless suite proves every branch of the verdict logic against typed fakes; what it structurally cannot prove is that a real key round-trips, because a suite that needed one would break on forks and rotations |

---

## Validation Sign-Off

- [x] Every gate: measured baseline AND recorded mutation (red, or honest green with reason)
- [x] Suite green plain; keyless invariant intact (`ANTHROPIC_API_KEY=""` throughout)
- [x] Offline evals 41/41 exit 0
- [x] `nyquist_compliant: true` set at reconciliation

**Measured at reconciliation (2026-08-14, end of wave 3):**

| Gate | Entering the phase | At close | Delta |
|------|--------------------|----------|-------|
| Full suite, keyless (`ANTHROPIC_API_KEY="" VOYAGE_API_KEY="" .venv/bin/pytest`) | 749 passed / 67 skipped | **772 passed / 67 skipped**, exit 0 | **+23 passed, +0 skipped** (wave 1 +11, wave 2 +6, wave 3 +6) |
| Offline evals (`ANTHROPIC_API_KEY="" python -m evals --min-pass-rate 0.9`) | 41/41, exit 0 | **41/41 (100% vs 90% required)**, real `$?` = **0** | unchanged |
| `.venv/bin/ruff check .` and `.venv/bin/ruff check src tests evals` | clean | **clean**, both forms | — |
| Suite warnings | 2 | 2 | unchanged; both pre-existing, none added by this phase |
| `src/research_agent/static/index.html` | 0 modifications | **0 modifications** | **±0 — the UI-SPEC change budget, measured on both git axes** |

Thirteen mutations were run across the three waves for the twelve the plans
named. Three of them corrected something rather than confirming it: wave 1's
blocking mutation deadlocks (a real property of the lock discipline, not the
named red, so it was re-run in an isolated form); wave 2's header mutation reds
as a `KeyError` until the test is strengthened to name the failure; and wave 3's
`finally` mutation exposed that the streaming failure arm emitted **no log line
at all**, which the plan had assumed was already there.

**Approval:** the automated contract is reconciled and complete — every row
above carries measured evidence and a recorded mutation. Two Manual-Only rows
remain OPEN and are the phase's only unverified claims; both need the manual
deploy and neither is blocked on code.
