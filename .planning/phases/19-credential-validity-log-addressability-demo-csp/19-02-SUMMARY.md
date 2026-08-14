---
phase: 19-credential-validity-log-addressability-demo-csp
plan: 02
subsystem: service
tags: [csp, security-headers, demo-page, hash-derivation, zero-edit-budget, keyless-suite]

# Dependency graph
requires:
  - phase: 19-credential-validity-log-addressability-demo-csp
    plan: "ui-spec"
    provides: "the seven-directive contract, the page inventory (1 script / 1 style / 0 handlers / 0 style attrs / 0 external resources), the two reference hashes, and the zero-edit change budget"
  - phase: 19-credential-validity-log-addressability-demo-csp
    plan: "01"
    provides: "the branch this rebases on; `src/research_agent/static/index.html` confirmed at zero modifications entering wave 2"
  - phase: 12-identity-and-the-demo-page
    plan: "static gates"
    provides: "`_demo_page()` (locates the file via `service.DEMO_PAGE`) and `_MarkupTags`, the walk this plan extended rather than duplicated"
provides:
  - "src/research_agent/csp.py — DIRECTIVES (the single place the directive set is written down), inline_blocks(), sha256_source(), policy() with an lru_cache and a loud raise on any block count but one"
  - "GET / (text/html) carries the derived seven-directive policy; every other response carries none"
  - "the measured fact that a Starlette http middleware attaching the header globally does NOT clobber the SSE caching headers — so the absence test, not the SSE test, is what enforces P-06"
  - "tests/test_service.py — six gates: header shape, independent derivation, both block counts, attribute absence, attachment scope, SSE caching headers"
affects: [19-03, 22]

# Tech tracking
tech-stack:
  added: []  # stdlib only: re, hashlib, base64, functools
  patterns:
    - "Derive a security header from the artifact it protects, never freeze it as a literal. A frozen hash lets the SERVED policy disagree with the SHIPPED page — the live demo blocked in every browser while the suite stays green."
    - "A test that computes both sides of a comparison with the implementation's own helpers asserts that a function equals itself. Recompute independently or the gate is decorative."
    - "Count a tag in both the form the parser sees and the form an editor might write. `<script>` and `<script\\b` must agree, or an attribute added to the tag makes the block invisible to the extraction and absent from the policy."
    - "An absence assertion needs the requests it asserts over to have succeeded. Assert the 200s first, or the gate passes on a 404."

key-files:
  created:
    - src/research_agent/csp.py
  modified:
    - src/research_agent/service.py
    - tests/test_service.py
    - .planning/phases/19-credential-validity-log-addressability-demo-csp/19-VALIDATION.md

key-decisions:
  - "The plan's Task 1 mutation asked for a red that is 'a missing-header failure, not an error'. Run as written against the first draft of the test it produced `KeyError: 'content-security-policy'` out of httpx's header mapping — the right cause surfaced as the wrong kind of failure. A membership assertion was added ahead of the lookup so the gate reds as `AssertionError: the demo page carries no CSP`, and the mutation was re-run to confirm. The plan asked for a property the test as first written did not have."
  - "The middleware mutation reds exactly as named on all three requests — and the SSE caching-header test stayed GREEN under it. Starlette's `@app.middleware(\"http\")` set the CSP without disturbing `Cache-Control`/`X-Accel-Buffering`. So P-06 is enforced by the absence test alone; the SSE test is a pin on a promise nothing previously asserted, not a tripwire for this mutation. The plan's framing (middleware 'could disturb the SSE responses' headers') is a hazard about mechanism reach, not an observed clobber, and is recorded as such."
  - "The derivation gate and the shape gate red on disjoint mutations, which is what makes both worth having: the hand-maintained-literal mutation reds only the derivation test (the tracer's test still saw `script-src 'sha256-`), and the dropped-header mutation reds only the tracer's. Neither subsumes the other."
  - "The block-count gate counts `<script>` AND `<script\\b`. The plan asked only for 'exactly one script block'. Counting the bare form alone would pass at 1-and-1 while `<script defer>` sat in the file invisible to `csp.inline_blocks` — a second block whose hash the policy silently omits, which is the exact failure `policy()`'s raise exists to prevent and the count gate is supposed to catch first."
  - "The new tests sit BELOW the static-file gate section rather than inside it, as the plan directed. That section's own header states it needs no client, no server and no browser; half of these drive the real app to read a real response header. They reuse `_demo_page()` and `_MarkupTags` from it, which is what the plan actually wanted — the file the service serves, never a fixture copy."

# Metrics
duration: 35min
completed: 2026-08-14
status: complete

actuals:
  tokens: 4856     # chars/4 over the realized src+tests diff (19,425 chars)
  tasks: 3
  commits: 4
---

# Phase 19 Plan 02: The demo page's CSP Summary

**One-liner:** The demo page now ships a seven-directive hash-based Content-Security-Policy derived from the page's own bytes on every request — so the served header cannot disagree with the shipped file — attached at exactly one call site, with six gates that red on the three edits derivation cannot follow and on any attempt to widen the attachment, and the page itself unchanged by a single byte.

## Measured baselines and deltas

| Gate | Before (entering wave 2) | After | Delta |
|------|--------------------------|-------|-------|
| Full suite, keyless (`ANTHROPIC_API_KEY="" VOYAGE_API_KEY="" .venv/bin/pytest`) | 760 passed / 67 skipped | **766 passed / 67 skipped**, exit 0 | **+6 passed, +0 skipped** |
| `tests/test_service.py` | 139 passed | 145 passed | +6 (every new test lives here) |
| Offline evals (`ANTHROPIC_API_KEY="" .venv/bin/python -m evals`) | 41/41, exit 0 | **41/41 (100% vs 90% required), exit 0** | unchanged |
| `.venv/bin/ruff check .` and `.venv/bin/ruff check src tests evals` | clean | clean | — (no error introduced at any point in this wave) |
| Suite warnings | 2 | 2 | unchanged — both pre-existing (starlette `httpx` deprecation, chromadb `asyncio.iscoroutinefunction`) |
| `src/research_agent/static/index.html` | 0 modifications | **0 modifications** | **±0 lines — measured, quoted below** |

### The +6, test by test

The plan claimed "roughly six tests" and asked for the real number. The measured delta is **exactly 6**, and the plan's named set is also exactly six — no test was added beyond the plan, none deleted, none skipped.

| # | Test | Task |
|---|------|------|
| 1 | `test_demo_page_is_served_with_a_hash_based_csp` | 1 |
| 2 | `test_csp_hashes_are_derived_from_the_page_not_hand_maintained` | 2 |
| 3 | `test_demo_page_has_exactly_one_script_block_and_one_style_block` | 2 |
| 4 | `test_demo_page_has_no_inline_handlers_or_style_attributes` | 2 |
| 5 | `test_csp_header_is_absent_from_the_json_index_and_the_streams` | 3 |
| 6 | `test_sse_responses_keep_their_caching_headers` | 3 |

## The change budget, quoted

```
$ git diff --stat "$(git merge-base main HEAD)" HEAD -- src/research_agent/static/index.html
$ git status --porcelain -- src/research_agent/static/index.html
$
```

Both print **nothing**. The merge-base is `cf660c2`. The file does not appear anywhere in the branch's full diffstat. It was edited exactly once during this wave — as mutation 2b, `onclick=""` on the input — and restored with `git checkout --` and confirmed clean before the commit that followed. A budget nobody measured is a budget nobody kept; this one was measured twice, on both axes the plan named.

**No checkpoint was needed.** The UI-SPEC's premise held exactly: the page has no inline handlers to convert, no style attributes to hoist and no external resources to inline, so nothing in the directive set forced an edit.

## What shipped

### Task 1 — the tracer: `2c72bc5` (red), `2cde3a0` (green)

RED first: `ImportError: cannot import name 'csp' from 'research_agent'`.

GREEN added `src/research_agent/csp.py`, a pure module with no FastAPI import so the route and its tests share it without a running app:

- `DIRECTIVES` — the UI-SPEC's seven, in order, with `{script}`/`{style}` slots. The one place the set is written down; the route sends it and every test reads it from here. Two copies of a security header is the defect this arrangement prevents.
- `inline_blocks(html)` — two non-greedy `re.S` patterns over the bare tags, with a docstring naming what would break them (an attribute on either tag) and what happens then (`policy()` raises).
- `sha256_source(text)` — SHA-256 over the exact UTF-8 bytes between the tags, base64'd. That is what a CSP element hash is defined over.
- `policy(path)` — `lru_cache`'d on the path, so the file is read on the first request that needs it and never at import time (DEC-18 intact). Raises `ValueError` naming both counts on anything but one-and-one, rather than serving a one-hash-for-two-blocks policy — which is silently wrong in the worst way: half the page dead in every browser, nothing wrong server-side.

The module docstring records where each of the seven directives comes from and why both absent-by-design families are absent (`img-src`/`font-src`/`frame-src`/`media-src`/`object-src` covered by `default-src 'none'`; `'unsafe-inline'`/`'unsafe-hashes'` because the first makes the policy decorative and the second licenses handlers and style attributes the page does not have).

`service.py`'s `index()` gained the `headers=` kwarg on its `text/html` `FileResponse` and a comment naming P-06 — the only attachment point, with middleware named as the wrong mechanism and the test that catches it named by name.

The served policy, printed against the real file:

```
default-src 'none'; script-src 'sha256-9r9Cu4iNyd4zpe8otNho5Q8WPI2YgqJmBM8l+2k7JnU='; style-src 'sha256-GjzXfxwdkdCrrRaX7wyDbcp+YGb15dhyT6JSLzaDWMg='; connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'
```

Both hashes reproduce 19-UI-SPEC's reference literals **byte-identically** — a third independent derivation after the researcher's and the checker's.

Per the tracer contract, the slice's own gate was re-run end to end (both automated verifies green, mutation red) before any expansion task.

### Task 2 — the derivation invariant and the counts: `a24c7e9`

Three gates, all reading the real file through `_demo_page()`; no fixture copy anywhere, because a fixture is a copy that can be right while the shipped page is wrong.

The derivation gate recomputes both digests inline with `re`/`hashlib`/`base64` and deliberately never calls `csp.inline_blocks` or `csp.sha256_source` — running the implementation down both sides would assert only that a function equals itself. It also asserts the served string carries neither `unsafe-inline` nor `unsafe-hashes`, which is an assertion about what a browser is told rather than a grep over source, leaving `csp.py`'s docstring free to discuss both.

`_MarkupTags` now records the `attrs` it was always handed and always dropped, so the attribute gate reuses the walk that already visits every start tag instead of opening a third parser over the same file.

All three passed on their first run — which under house discipline makes them the suspect, not the evidence — so both mutations were run before any of them was trusted.

### Task 3 — attachment scope, the SSE headers, the budget: `2a1dec5`

The absence gate asserts the header reaches none of the JSON index, `/research/stream` or `/sessions/{id}/ask/stream` — after asserting all three returned 200, because an absence assertion that passes on a request which 404'd is worth nothing.

The SSE gate pins `Cache-Control: no-cache` and `X-Accel-Buffering: no` on both stream routes. The UI-SPEC lists these as must-not-change and nothing asserted them before this phase, so "the CSP work did not disturb them" had been resting on reading the code.

19-VALIDATION's three `REQ-demo-csp-header` rows were filled with measured evidence, including the honest result of the middleware mutation described below. The Task IDs, Plan and Wave columns were left as planned — every gate landed exactly where the plan put it.

## Mutation probes — each observed red, then reverted

| # | Mutation | Observed red |
|---|----------|--------------|
| 1 | `headers=` kwarg dropped from `index()`'s `FileResponse` | `AssertionError: the demo page carries no CSP` (after the test was strengthened — see below) |
| 2a | `csp.policy`'s computed script source replaced with a one-character-off literal | `assert "script-src 'sha256-…JnU='" in "…JnV='…"`, with both policies printed |
| 2b | `onclick=""` added to the page's `<input id="q">` | `AssertionError: assert [('input', 'onclick')] == []` |
| 3 | Attachment moved into an `@app.middleware("http")` setting the header on every response | `AssertionError: the CSP escaped its one call site onto: ['json index', 'research stream', 'ask stream']` |

Four mutations for four named ones. Two of them corrected something.

### Mutation 1 reds for the right cause in the wrong shape — until the test was fixed

The plan is specific: the header test "must go red with a missing-header failure, **not an error**." Run as written against the first draft, it produced `KeyError: 'content-security-policy'` — raised by httpx's header mapping at the lookup line. The cause was right; the shape was not, and a `KeyError` in a security gate reads as a broken test rather than a missing control.

A membership assertion was added ahead of the lookup (`assert "content-security-policy" in response.headers, "the demo page carries no CSP"`) and the mutation re-run, producing the named `AssertionError`. **The plan asked for a property the test as first written did not have** — the mutation is what exposed the difference, which is the argument for running them.

### Mutation 3 reds as named, and disproves the reason the plan gave for fearing it

The absence test went red on all three requests exactly as predicted. But under the same middleware, `test_sse_responses_keep_their_caching_headers` **stayed green**: Starlette's `@app.middleware("http")` added the CSP without disturbing `Cache-Control` or `X-Accel-Buffering`.

That matters for how the two tests should be read. The plan (and the UI-SPEC) motivate P-06 partly as protecting the SSE headers from a broad mechanism; the measurement says the mechanism reaches those responses but did not damage them. So:

- The **absence test** is what enforces P-06. It is the only gate that reds on a global attachment.
- The **SSE test** is a pin on a promise nothing previously asserted — worth having on its own terms, not as a tripwire for this mutation.

Recorded rather than smoothed over, because "middleware would break the SSE headers" is a claim this wave had the chance to check and found weaker than stated. The reach is real; the damage was not observed. The narrower design is still right — it is what makes "absent everywhere else" a testable claim at all — but for the reason the absence test measures, not the one the prose assumed.

### Mutations 2a and 3 also show the gates do not subsume each other

Under 2a (hand-maintained hash) the tracer's shape test stayed green — it only ever asserted `script-src 'sha256-`. Under mutation 1 (dropped header) the derivation test also reds, but for the missing header rather than the digits. Shape and digits are gated separately and neither covers the other, which is the division of labour the plan intended and the mutations confirm.

## Deviations from plan

### [Rule 2 — missing gate strength] The header test gained a membership assertion

Described above. The plan's own mutation criterion ("a missing-header failure, not an error") was not satisfiable by the test as first written. **Commit:** `2cde3a0`.

### [Rule 2 — missing gate strength] The block-count gate counts two tag forms, not one

The plan asked for "exactly one script block and exactly one style block". Counting only the bare `<script>` form would pass at one-and-one while a `<script defer>` block sat in the file — invisible to `csp.inline_blocks`, so its hash would be silently absent from the policy and that block dead in every browser. The gate now asserts `<script\b` and `<script>` counts agree at one apiece (same for `style`), which is the gate the shape claim actually needs. **Commit:** `a24c7e9`.

### [placement] The new tests sit below the static-gate section, not inside it

The plan says to add them "in the static-gate section". That section's own header states it needs "no client, no server and no browser"; three of the six new tests drive the real app to read a real response header. They live in a new, labelled section immediately below it and reuse `_demo_page()` and `_MarkupTags` — which is the substance of what the plan wanted (the real file, never a fixture) without falsifying a section header. **Commit:** `2c72bc5`, `a24c7e9`, `2a1dec5`.

### [Rule 1 — plan anchors] Three of the plan's four line anchors had drifted

Checked, since the plan's arithmetic is a claim rather than a fact:

| Anchor as written | Actual | Note |
|-------------------|--------|------|
| `service.py:52` — `DEMO_PAGE` | `:52` | correct |
| `service.py:402-412` — `index()` | `:402-412` | correct |
| `service.py:986-995` — `_sse_response()` | **`:1205-1215`** | `:986` is the `return _sse_response(...)` **call site** in `ask_stream`, not the definition |
| `test_service.py:2425-2445` — the static gates and `_demo_page()` | **`:2763-2770`** | |
| `test_service.py:2443-2500` — `_FirstPaintText` / `_MarkupTags` | **`:2773-2817`** | |

The two test-file anchors drifted by ~330 lines because wave 1 inserted its credential block above them; the plan was written before that wave ran. No anchor pointed at the wrong *thing* once found, and nothing was built on a stale one.

### [Rule 1 — plan claim] `_MarkupTags` did not already carry attributes

The plan says `_MarkupTags` "already walks every tag with its attributes". It walks every tag and its `handle_starttag` is *handed* `attrs` — and drops them on the floor. The parser was extended to record them, which is the plan's actual intent (reuse the walk, do not open a third parser), but the claim as written was not true of the code. **Commit:** `a24c7e9`.

### [not a deviation, stated to be explicit] Nothing outside the plan's file list was touched

`git show --stat` across all four commits lists exactly four files: `src/research_agent/csp.py`, `src/research_agent/service.py`, `tests/test_service.py`, and `19-VALIDATION.md`. README's Limitations bullets (Phase 22), the `run_finished` log line and the doc pass (wave 3), wave 1's credential probe, and `src/research_agent/static/index.html` are all unmodified.

## Acceptance criteria, measured

| # | Criterion | Result |
|---|-----------|--------|
| 1 | The exact seven-directive policy, two derived sha256 sources, no `unsafe-` source | ✅ Directive **names** asserted equal to `csp.DIRECTIVES` in order on the served header; `unsafe-inline` and `unsafe-hashes` both asserted absent from the served string |
| 2 | Hashes match an independent recomputation over the shipped file | ✅ Recomputed inline with `re`/`hashlib`/`base64`, never through the implementation's helpers; both match the UI-SPEC references byte-identically |
| 3 | Counts 1 and 1, zero handlers, zero style attributes, asserted by tests | ✅ Both tag forms counted; zero `on*`, zero `style=`, zero `javascript:` values, with a positive control so an empty walk cannot pass |
| 4 | No CSP on the JSON index or either SSE route; both SSE caching headers asserted unchanged | ✅ Three 200s asserted before the three absences; `Cache-Control: no-cache` and `X-Accel-Buffering: no` pinned on both streams |
| 5 | `index.html` has zero edits, measured by git | ✅ Both git commands print nothing; the file is absent from the branch diffstat |

## Threat register — dispositions discharged

| Threat | Disposition | How |
|--------|-------------|-----|
| T-19-06 Tampering (injected inline script) | mitigate | `default-src 'none'` + hash-only `script-src`; absence of both `unsafe-` families asserted on the served string. An injected script has no matching hash |
| T-19-07 Information disclosure (exfiltration) | mitigate | `connect-src 'self'`, `form-action 'self'`, `base-uri 'none'` — all three pinned by the directive-names assertion |
| T-19-08 Spoofing (clickjacking) | mitigate | `frame-ancestors 'none'`, pinned by the same assertion |
| T-19-09 Tampering (policy drift) | mitigate | Runtime derivation makes hash drift structurally impossible (mutation 2a reds a hand-maintained literal); the count and attribute gates catch the three shape changes derivation cannot follow (mutation 2b); `policy()` raises rather than serving a one-hash-for-two-blocks policy |
| T-19-10 DoS (broad mechanism disturbing SSE headers) | mitigate | P-06 confines attachment to one call site; the absence test plus mutation 3 enforce it. **Refined by measurement:** the middleware mechanism reaches those responses but did not damage their headers — the enforcement is the absence gate, not an observed clobber |
| T-19-SC Package installs | accept | Zero installs. `re`, `hashlib`, `base64`, `functools` — stdlib only |

## What wave 3 inherits

- `service.py` has one new import (`csp`) and an eleven-line `index()` branch. Wave 3's `run_finished` work is elsewhere in the file.
- `tests/test_service.py` has a new labelled CSP section at the end (145 tests in the file now), and `_MarkupTags` gained an `attributes` list — additive; its existing `census()` use at the first-paint gate is unchanged.
- The zero-edit budget on `index.html` is **still intact** for anything wave 3 might be tempted to touch.
- 19-VALIDATION's two remaining `pending` rows are both 19-03's.

## Deferred, recorded rather than silent

- **The live page under the header.** Browser CSP enforcement cannot run in pytest and the deploy is manual, so UI-SPEC acceptance checks 1–7 (header present via `curl -sI`; page identical light and dark; full demo flow; periphery; cookie still minted; drift guard; `/health` fields) belong to phase close. This is 19-VALIDATION's Manual-Only row, and the checker's hedge applies: check 2 reads "zero violations **attributable to page resources**", so a browser-initiated favicon probe cannot cosmetically fail it.
- **README's Limitations bullets** stay exactly as written — Phase 22 owns them.
- **The `/health` doc surface** remains wave 3's.

## Self-Check: PASSED

- `src/research_agent/csp.py` — present (created). `src/research_agent/service.py`, `tests/test_service.py`, `19-VALIDATION.md` — present and modified on this branch.
- Commits `2c72bc5`, `2cde3a0`, `a24c7e9`, `2a1dec5` — all present in `git log`.
- No stubs, no TODO/FIXME, no skipped tests introduced. Every `<verify>` command in the plan was run; no gate is unrun.
- `src/research_agent/static/index.html`: **zero modifications**, confirmed by both git commands quoted above.
