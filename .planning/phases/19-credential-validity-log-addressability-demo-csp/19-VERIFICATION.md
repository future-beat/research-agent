---
phase: 19-credential-validity-log-addressability-demo-csp
verified: 2026-08-14T08:10:42Z
status: passed
score: 5/5 roadmap success criteria verified
method: goal-backward — every criterion re-proven from the tree by a mutation or an independent derivation the verifier performed and observed, then reverted
verifier_mutations: 4  # each observed red, each reverted; tree confirmed clean before the first and after the last
verifier_experiments: 3  # CSP hashes re-derived from the file, the ContextVar claim measured directly, a 20-way concurrency smoke against two hanging providers
overrides_applied: 0
re_verification: false

# Gates re-run by the verifier, not read from a SUMMARY
gates:
  full_suite: "772 passed / 67 skipped, exit 0, 28.30s, ANTHROPIC_API_KEY='' VOYAGE_API_KEY=''"
  offline_evals: "PASS 41/41 cases (100% vs 90% required), real $? = 0"
  ruff: "All checks passed! (`.venv/bin/ruff check .`)"
  index_html: "0 modifications — absent from `git diff --stat $(git merge-base main HEAD) HEAD`, and `git status --porcelain` on the path prints nothing"
  working_tree: "clean at start and at end"

# Not gaps. Recorded so the deploy inherits the fact rather than the silence.
human_verification:
  - test: "UI-SPEC acceptance checks 1–7 against the deployed page: header present via curl; page identical light and dark with zero console violations attributable to page resources; full demo flow; periphery; identity cookie still minted; drift guard; /health fields visible"
    expected: "Zero CSP violations attributable to page resources; the demo flow and the cookie behave exactly as before"
    why_human: "Browser CSP enforcement cannot run in pytest, and this project's deploy is manual. The automated half is complete and was re-verified here: the exact served policy, both hashes independently re-derived from the shipped file, index.html at zero edits."
    owner: "19-VALIDATION Manual-Only row 1 — marked OPEN there and in ROADMAP:275-277. Verified present in both."
  - test: "A real provider probe round-trip: /health reads `anthropic_valid: true` and `voyage_valid: true` with a fresh `checked_at` inside one CREDENTIAL_PROBE_TTL"
    expected: "Both providers report valid true against real keys within 300s of the first /health read"
    why_human: "The suite is keyless by invariant; a test that needed a live key would break on forks and rotations. Every branch of the verdict logic is proven against typed fakes — what cannot be proven offline is that a real key round-trips."
    owner: "19-VALIDATION Manual-Only row 2 — marked OPEN there and in ROADMAP:275-277. Verified present in both."

# Non-blocking. None is a roadmap criterion; none is a new user-facing limitation.
warnings:
  - finding: "README's `/health` Limitations bullet is now actively false, and stays that way until Phase 22"
    evidence: "README:289 still reads '`/health` checks that the API keys are *present*, not that they work … What is missing is the other signal' — precisely the signal this phase built. Grep count still 1."
    why_it_counts: "Deliberate, not accidental, and stated in three places the verifier checked independently: 19-CONTEXT:112-115 ('Do not touch the bullet here'), 19-03-SUMMARY:57 and its own section at :390-402 ('between this merge and Phase 22, the portfolio's front door contains one sentence that the code contradicts'), and ROADMAP:144 assigning the section to Phase 22. docs/OPERATIONS.md — the surface an operator actually reads — was corrected in this phase and is accurate."
    fix: "Phase 22 deletes the bullet. Nothing to do here; removing it now would strand that phase."
  - finding: "The three Phase 19 REQ checkboxes are still `- [ ]` in REQUIREMENTS.md"
    evidence: "REQUIREMENTS.md:45, :52, :64 unchecked; the traceability table at :97-99 says 'Implemented … not yet Complete: the phase is unverified'."
    why_it_counts: "This is an honest pending state rather than the silent drift Phase 18's verification found — the rows name verification as the missing step. That step is now done, so the flip is due."
    fix: "Three checkbox flips and three table cells, in the ship or milestone-close commit. Phase 18's identical item was closed the same way (REQUIREMENTS.md:30 now reads `- [x] … verified 2026-08-14`)."
  - finding: "`_stream` catches `Exception`; `_execute` catches `BaseException`"
    evidence: "service.py:413 vs :358. A client disconnect mid-stream raises `GeneratorExit`, which is a `BaseException`, so it reaches neither terminal arm and emits neither `run_finished` nor `run_failed` (and, pre-existing, does not settle its reservation — the staleness cutoff reclaims it)."
    why_it_counts: "The code comment at :355-356 states 'every HTTP-initiated run emits precisely one of the two'. That holds for every run terminating through success or an `Exception`, which is every failure mode the phase set out to make visible. A client that hangs up is not a completed or failed run. The `except Exception` clause is pre-existing and untouched by this phase — it does not appear in `git diff $(git merge-base main HEAD) HEAD -- src/research_agent/service.py`."
    fix: "None required. Recorded so nobody reads the comment as stronger than it is."

# Verifier nits. Neither changes a verdict.
notes:
  - "19-VALIDATION's row for 19-01-T3 records the blocking mutation as reding both ways (deadlock inside the lock, `/health waited 5.01s` outside it). The verifier reproduced only the outside-the-lock form and got the identical message to two decimal places — `/health waited 5.01s on a provider that never answered`. The deadlock claim is about a mutated lock discipline, not the shipped one; the shipped ordering was verified by inspection and by a 20-way concurrency smoke instead."
  - "OPERATIONS' CI line was corrected from '470 tests, 12 offline eval cases' to '772 tests, 41 offline eval cases'. Both numbers were already stale entering the phase (a pre-existing defect), and 19-03-SUMMARY:331-339 says so rather than claiming credit for a regression it did not cause."
---

# Phase 19: Credential validity, log addressability, demo CSP — Verification Report

**Phase Goal:** `/health` reports whether the API keys actually work without touching liveness, a
completed run is addressable from its logs, and the demo page's inline JS survives a real CSP.

**Verified:** 2026-08-14T08:10:42Z
**Status:** passed — 5/5 roadmap success criteria
**Method:** goal-backward. All three SUMMARYs and 19-VALIDATION were read as *claims*. Every
criterion below was re-proven from the tree — four mutations performed, observed red and reverted,
plus three independent derivations. Working tree confirmed clean before the first mutation and
after the last.

---

## Goal Achievement

### Success Criteria (the ROADMAP contract)

| # | Criterion | Status | Evidence the verifier observed |
|---|-----------|--------|--------------------------------|
| 1 | `/health` surfaces credential-validity fields for Anthropic and Voyage beside the presence booleans, backed by a cached async probe | ✅ VERIFIED | `service.py:925-929` emits six flat keys (`{anthropic,voyage}_{valid,checked_at,error}`) from `_CREDENTIAL_PROBES`; the three presence booleans at `:910-920` are computed exactly as before. Probes are `count_tokens` (`:775-787`) and a micro-embed (`:795-815`). Cache + TTL at `:687-694`, `:666-682`. Live read against the app returned all six keys. Presence pinned by name and type at `test_service.py:1512-1514`, so a field that vanished would red |
| 2 | The liveness path Fly reads never calls a provider — a healthy container is not restarted during a provider outage | ✅ VERIFIED | `fly.toml:147-152` points the liveness check at `/health`. `_credential_status` (`:748-772`) submits to `_probes()` and returns the cache; `.result()` appears nowhere on the read path. **Mutation 1** (below) reds. **Concurrency smoke:** 20 simultaneous `/health` calls against *two* providers blocked on an Event — worst latency **0.016s**, all 200, all `valid: null`. No deadlock, no serialization |
| 3 | Probe spend is excluded from or attributed within cost accounting, and the code states which, deliberately | ✅ VERIFIED | Excluded, stated at `service.py:805-814` in a ten-line comment that names its own pinning test. Anthropic's `count_tokens` is free by construction. The Voyage exclusion is structural, and the verifier measured the mechanism directly rather than taking the claim: `_EMBEDDING_METER` is a `ContextVar` (`usage.py:446`), and a ThreadPoolExecutor worker sees `None` for it while an inline report in the same context lands 25 tokens. The gate's positive control genuinely discriminates (`test_service.py:1679-1687`) |
| 4 | `run_finished` log lines carry `session_id`, so a completed run is addressable without cross-referencing | ✅ VERIFIED | `_finished_log` (`service.py:268-298`) carries `session_id` beside `run_id`, emitted from both `_execute:357` and `_stream:409` — the only two terminal paths, covering all four routes. `run_finished` occurs exactly once in the tree outside `.planning/` (grep). All four routes asserted against the id the caller was told (`test_service.py:3318-3398`), exactly-once asserted with a non-vacuity companion (`:3401-3417`), and the failure complement asserted on **both** arms (`:3420-3457`). **Mutations 2 and 3** red |
| 5 | The demo page ships a hash-based CSP (no `unsafe-inline`) and its inline JS still runs | ✅ VERIFIED (automated half; live-page half is a recorded Manual-Only) | Both hashes **re-derived by the verifier** from `static/index.html` and byte-identical to the served header and to 19-UI-SPEC's literals. Served policy carries neither `unsafe-inline` nor `unsafe-hashes`. Seven directives in UI-SPEC order. One call site (`service.py:486-490`); absent from the JSON index (verified live) and both SSE routes (`test_service.py:3211-3233`). `index.html` at **zero** edits. **Mutation 4** reds |

**Score: 5/5.**

---

## Mutations Performed by the Verifier

Each was applied to the tree, run, observed red, and reverted. `git status --porcelain` printed
nothing before the first and after the last.

| # | Criterion | Mutation | Observed red |
|---|-----------|----------|--------------|
| 1 | 2 | `_credential_status` wrapped so the read path waits on the submitted future (`.result(timeout=5)`) **outside** the cache lock — the isolated form 19-01 had to fall back to | `AssertionError: /health waited 5.01s on a provider that never answered` / `assert 5.008578124921769 < 1.0` — to two decimals the message 19-VALIDATION records |
| 2 | 4 | `graph.py`'s terminal event value restored to `"run_finished"`, so two call sites share the name | **Five** tests red, including `test_exactly_one_run_finished_record_per_request`. The log stream shows both lines carrying `"event": "run_finished"` for one run — the silent double-count, made loud |
| 3 | 4 | `_stream`'s failure log line deleted — i.e. the tree rolled back to the state wave 3 *found* | `AssertionError: a failed stream left no trace in the log stream at all` / `assert 0 == 1`. The blocking arm stayed green throughout, which is exactly why the omission survived until this phase |
| 4 | 5 | `headers=` dropped from the demo page's `FileResponse` | `AssertionError: the demo page carries no CSP` — a named failure, not httpx's bare `KeyError`, which is the strengthening wave 2 recorded as a correction |

Mutation 3 is the important one: it re-proves that the *correction* wave 3 made is itself gated,
not merely described. Restoring the pre-phase code reds a test; the claim "a failed stream is now
visible in `fly logs`" is enforced rather than asserted.

---

## Criterion 2 in Detail — the one with a real failure mode

The concern the phase was chartered around is that a provider's outage must never become a
restart loop. Three independent things had to hold, and each was checked separately.

**1. Fire-and-forget is real.** `_credential_status` submits and returns the cache
(`service.py:769-772`). No `.result()`, no `wait()`, no `as_completed` anywhere on the read path.
Mutation 1 confirms a wait is detectable by the suite in under a second of wall clock.

**2. The lock ordering cannot deadlock.** The verifier traced both locks rather than trusting the
wave's note. The order is strictly one-directional:

- `_credential_status` holds `_credential_cache_lock` (`:756`) and, inside it, calls `_probes()`
  which takes `_probe_executor_lock` (`:564`). Order: **cache → executor**.
- `_refresh_credential` runs `probe()` at `:724` with **no lock held**, and takes the cache lock
  only for the assignment (`:738`) and the `finally` pop (`:745`). It never calls `_probes()`.
- `_shutdown_probes` takes the executor lock alone (`:575`) and shuts down outside it.

No path acquires the executor lock and then the cache lock, so there is no cycle. The deadlock
19-01 reported was a property of the *mutation* (a wait held across the cache lock, which the
worker's `finally` then needs) and is unreachable in the shipped code. `ThreadPoolExecutor.submit`
does not block on worker availability — the queue is unbounded — so holding the cache lock across
the submit costs a queue append, not a wait. The comment at `:764-768` states why submit and
registration must share one lock acquisition, and it is correct: splitting them lets the worker
pop a guard that has not been recorded yet, wedging that provider on its last verdict.

**3. Measured, not reasoned.** 20 concurrent `/health` requests with *both* provider probes
blocked on an Event: worst latency 0.016s, every response 200, every `anthropic_valid` `null`.
Under a mutation-1-style wait this is 5s+; under the deadlock discipline it never returns.

The store-probe ceiling is also unaffected. `_probe` bounds each store probe by
`HEALTH_PROBE_BUDGET` with `future.result(timeout=...)`, so even with the pool's three workers all
held by hung credential probes, `/health` still returns at its deadline — availability is what the
deadline bounds, not execution. `docs/OPERATIONS.md` now carries that paragraph, including the
condition under which it would stop being true.

---

## Criterion 3 in Detail — is the exclusion real, and does the control discriminate?

The exclusion claim rests on a mechanism, and a mechanism claim deserves a measurement.

```
meter seen inside pool worker: None
inline report inside meter -> total_tokens: 25
```

A `ContextVar` set in one thread is invisible to a `ThreadPoolExecutor` worker — each worker
starts with an empty context — while an inline report in the setting thread lands. So
`report_embedding` finds no meter from the probe body, by construction rather than by special
case. The wave's stronger-than-planned framing is correct: the probe could not observe a meter
even if the request thread had one open.

The gate's positive control is not vacuous. `test_health_credential_probe_spend_is_excluded_from_the_embedding_meter`
asserts three things inside one meter: that the probe **did** embed
(`assert embedder._client.calls`), that the meter reads 0, and that a direct `embed_query` on the
**same embedder in the same meter** reads 25. A silently-broken embedder fails the first
assertion; a broken accounting seam fails the third. Neither side can pass vacuously.

The deliberateness requirement is met literally: `service.py:805-814` states the choice, states
why (a background probe has no run to attribute to, and inventing one would put a probe on some
visitor's bill), and names the test so the next reader checks the gate instead of trusting the
comment.

---

## Criterion 4 in Detail — exactly one completion event, all four routes

| Route | Terminal path | `session_id` compared against | Gate |
|-------|---------------|-------------------------------|------|
| `POST /research` | `_execute` | the response body's `session_id` | `test_run_finished_carries_the_session_id_for_a_new_session` |
| `POST /research/stream` | `_stream` | the terminal `result` event's `session_id` | `..._on_the_streaming_path` |
| `POST /sessions/{id}/ask` | `_execute` | the path parameter | `..._for_a_followup[ask]` |
| `POST /sessions/{id}/ask/stream` | `_stream` | the path parameter | `..._for_a_followup[ask/stream]` |

Both terminal paths call the same `_finished_log` helper, so the record shape cannot differ by
transport. The exactly-once gate counts (`capture_log.count(...) == 1`) rather than checking
membership, with `graph_finished == 1` beside it so the count cannot pass because nothing ran.
`graph_finished` is asserted to carry **no** `session_id`, which turns a future attempt to thread
the id through `AgentState` — which LangGraph would drop silently — into a red test.

**The failed path emits `run_failed` on both arms.** `_execute:365` and `_stream:437`, sharing
`_failed_log`. Mutation 3 proves the streaming half is gated. This is DEC-13's honesty carried
into the log stream: a failed run already stayed in the metrics denominator on both arms
(`_failed_record` at `:363` and `:420`), and now it leaves a trace in `fly logs` on both too. The
gap this closed was not cosmetic — the demo page runs entirely on the streaming routes, so before
this phase every failed demo run was invisible in the logs while looking fine to the caller and
correct in the metrics table.

---

## Criterion 5 in Detail — the CSP, re-derived rather than compared

The verifier derived both hashes from `src/research_agent/static/index.html` with its own
`re`/`hashlib`/`base64` pass, touching neither `csp.py` nor the test:

```
counts: script=1 style=1
prefix counts: <script=1 <style=1        # so a `<script defer>` could not hide from the count
script hash: sha256-9r9Cu4iNyd4zpe8otNho5Q8WPI2YgqJmBM8l+2k7JnU=
style  hash: sha256-GjzXfxwdkdCrrRaX7wyDbcp+YGb15dhyT6JSLzaDWMg=
on* attrs: []   style= attrs: []   javascript: refs: []   script src: []
```

Both reproduce 19-UI-SPEC's reference literals byte-identically — a fourth independent derivation
after the researcher's, the checker's and the test's. The served header, read off a live
`GET /` with `Accept: text/html`:

```
default-src 'none'; script-src 'sha256-9r9Cu4iNyd4zpe8otNho5Q8WPI2YgqJmBM8l+2k7JnU=';
style-src 'sha256-GjzXfxwdkdCrrRaX7wyDbcp+YGb15dhyT6JSLzaDWMg='; connect-src 'self';
base-uri 'none'; form-action 'self'; frame-ancestors 'none'
```

Seven directives, in the UI-SPEC's order, with the UI-SPEC's values. `unsafe-inline`: absent.
`unsafe-hashes`: absent. The JSON branch of `GET /` returned 200 with **no** CSP header (verified
live, not only in the suite), and `test_csp_header_is_absent_from_the_json_index_and_the_streams`
covers both SSE routes with a 200-first non-vacuity check. `test_sse_responses_keep_their_caching_headers`
pins `Cache-Control: no-cache` and `X-Accel-Buffering: no` on both streams — UI-SPEC must-not-change
item 6, which nothing asserted before this phase.

**Change budget: zero, measured on both axes.** `index.html` does not appear in
`git diff --stat $(git merge-base main HEAD) HEAD` at all, and `git status --porcelain` on the path
prints nothing.

The half that cannot be closed from this repository — the live page in a real browser — is
19-VALIDATION Manual-Only row 1, marked **OPEN**, and is repeated in ROADMAP:275-277. Recorded,
not silent.

---

## Independently Re-Run Gates

| Gate | Command | Result |
|------|---------|--------|
| Full suite, keyless | `ANTHROPIC_API_KEY="" VOYAGE_API_KEY="" .venv/bin/pytest` | **772 passed, 67 skipped**, 2 warnings, 28.30s |
| Offline evals | `ANTHROPIC_API_KEY="" .venv/bin/python -m evals --min-pass-rate 0.9` | **PASS 41/41 (100% vs 90%)**, real `$?` = **0** |
| Lint | `.venv/bin/ruff check .` | All checks passed! |
| Phase subset | `pytest tests/test_service.py -k "credential or csp or run_finished or run_failed or exactly_one"` | 23 passed |
| Zero-edit budget | `git diff --stat <merge-base> HEAD -- .../static/index.html` | empty |
| Working tree | `git status --porcelain` | empty, before and after every mutation |

The 749 → 772 arithmetic closes: +11 (wave 1) +6 (wave 2) +6 (wave 3) = +23.

---

## The Milestone Acceptance Bar — Explicit Ruling

> **No new bullet is born.** (REQUIREMENTS.md:14)

Phase 19 builds the signal; Phase 22 deletes the bullet. The bar's substance — does this
implementation *force* a successor limitation into existence — is answerable now, and the answer
is **no**. Four candidates were considered and each is ruled on rather than waved past.

### 1. The TTL means a verdict can be up to five minutes stale — **an internal property, documented**

`CREDENTIAL_PROBE_TTL` defaults to 300s with a 30s floor. A revoked key therefore surfaces within
one TTL rather than instantly.

This is not a successor to the bullet it replaces. The old bullet's complaint was categorical —
"what is missing is the other signal" — and the signal now exists. A cached health verdict with a
bounded staleness window is the ordinary shape of every cached probe, and the window is smaller
than the operator's own observation loop: Fly polls every 30s, and nobody watches `/health`
continuously. The value is named in `docs/OPERATIONS.md`'s environment table with the floor and
the distinction from `HEALTH_PROBE_BUDGET` spelled out, so an operator who wants a tighter window
has a knob rather than a surprise. **Not a README bullet.**

### 2. The probe reports per-process state; two Fly machines could disagree — **the endpoint's existing contract**

Each machine has its own cache and runs its own probe, so machine A could read `valid: null`
during a transient outage while machine B reads `true`.

`/health` has always been a per-machine endpoint. `_dependencies` probes the stores *from this
process*, `identity_signing` reports *this process's* env, and `machine` (FLY_MACHINE_ID) exists
in the payload precisely so an operator can tell which machine answered — the response already
carries its own disambiguator. Credential validity inherits that contract unchanged; it does not
create it. **Not a new limitation.**

### 3. Voyage probe spend is unattributed by design — **inside an existing surviving bullet**

The micro-embed costs real money at the provider and appears in no run's totals, the runs table,
the daily cap or `/metrics`.

Two reasons this does not birth a bullet. First, magnitude: one embed of the word `ping` per
provider per TTL per machine — roughly 600 tokens a day across the fleet, four hundredths of a
cent. Second and decisively, it falls squarely inside a limitation the milestone has already
declared **cannot close and will get a record instead**: *"Reported cost is an approximation,
never the invoice. Nothing here reads a bill."* A trace of provider-side spend that client-side
accounting does not see is that bullet's exact subject matter, not a new one.

*Recommendation, not a gap:* when Phase 22 writes the cost-approximation-by-design ADR, one
sentence naming the credential probe as a known unattributed source would make the record complete.
The code already states the choice and pins it with a test, which is what criterion 3 asked for.

### 4. The CSP is derived once per process (`lru_cache`) — **immaterial under immutable deploys**

A page edited in place on a running server would serve a stale policy until restart. The page
ships inside the container image and every deploy restarts the process, so the state is
unreachable in production. In development the tests call `policy.cache_clear()`. The alternative —
re-reading the file per request — buys nothing and costs an I/O on the demo's hot path.
**Not a limitation.**

### And one limitation that was retired without ceremony

Before this phase, a failed streaming run left no log record at all. That was an undocumented
defect on the path the demo page actually uses — worse than the bullet the phase was chartered
against, because there was not even a mis-named line to fail to find. It is now gated on both
arms. The phase closed a limitation nobody had written down, and added none.

**Ruling: the bar holds. No successor limitation is born by Phase 19.**

---

## Requirements Coverage

| Requirement | Status | Evidence |
|-------------|--------|----------|
| REQ-health-credential-validity | ✅ SATISFIED (criteria 1–3) | Six validity fields beside unchanged presence booleans; liveness never waits (mutation 1 + 20-way concurrency smoke); exclusion stated in code and pinned by a discriminating test. The live round-trip is Manual-Only row 2, OPEN |
| REQ-run-finished-session-id | ✅ SATISFIED (criterion 4) | `session_id` on `run_finished` across all four routes, exactly once per run, with `run_failed` as its complement on both arms. No Manual-Only dependency; needs no deploy |
| REQ-demo-csp-header | ✅ SATISFIED, automated half (criterion 5) | Seven-directive derived policy, both hashes re-derived by the verifier, no `unsafe-` source, one call site, `index.html` at zero edits. "Verified against the live page" is Manual-Only row 1, OPEN |

The three checkboxes in REQUIREMENTS.md are still `- [ ]`, with the traceability table naming
verification as the missing step. That step is now complete — see warnings.

---

## Anti-Pattern Scan

| Check | Files scanned | Result |
|-------|---------------|--------|
| `TODO` / `FIXME` / `XXX` / `TBD` / `HACK` / `PLACEHOLDER` | `service.py`, `csp.py`, `graph.py`, `test_service.py`, `test_graph_smoke.py` | **none** |
| Stub returns / empty handlers | same | none — every added function has a body that does work |
| Skipped or deleted tests | full suite | none; skips unchanged at 67, all keyless-invariant |
| New suite warnings | full suite | none; 2 warnings, both pre-existing |
| Vacuous assertions | the phase's new gates | none found — the exclusion test carries a positive control, the exactly-once test carries a non-vacuity companion, the header-absence test asserts 200 first, and the attribute walk carries a known-present control |
| Docs claiming a posture the code lacks | `README.md`, `docs/OPERATIONS.md`, `ARCHITECTURE.md` | one, deliberate and assigned — README:289, see warnings |

---

## Gaps Summary

**None.** All five roadmap success criteria are met in the tree, each re-proven by a mutation or
an independent derivation the verifier performed rather than read.

Two items remain open and both are recorded rather than silent — the live-page CSP acceptance and
a real provider probe round-trip, each awaiting the manual deploy, each marked **OPEN** in
19-VALIDATION's Manual-Only table and repeated in the ROADMAP. Neither is blocked on code, and
neither is a criterion this repository can close by itself.

The phase's own record survives adversarial reading. 19-VALIDATION claims thirteen mutations for
the twelve the plans named, with three corrections rather than confirmations; the verifier
reproduced four of them independently and every observed red matched what was written down,
including one message to two decimal places. The three SUMMARYs volunteer their own plans' errors
— a false premise about `_stream`, drifted anchors, an unreachable second red — which is the
opposite of the failure mode this verification exists to catch.

---

## Notes for the Next Phase

- **Phase 22 has two deletions waiting, not one.** README:285 (Phase 18's judge bullet) and
  README:289 (this phase's `/health` bullet) are both now false-on-purpose. Both are recorded in
  their phases' summaries; neither should be discovered.
- **Phase 22's cost-approximation ADR** should name the Voyage credential probe as a known
  unattributed spend source — see the acceptance-bar ruling, item 3.
- **The REQUIREMENTS.md flip is due** for all three Phase 19 requirements.
- **`.planning/codebase/` maps** remain stale in the ways Phase 18 recorded in `deferred-items.md`;
  this phase corrected only the structured-event line in ARCHITECTURE.md.

---

_Verified: 2026-08-14T08:10:42Z_
_Verifier: Claude (gsd-verifier) — 4 mutations performed and reverted, 3 independent derivations, 6 gates re-run_
