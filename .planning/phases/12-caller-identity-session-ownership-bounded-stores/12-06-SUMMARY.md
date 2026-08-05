---
phase: 12-caller-identity-session-ownership-bounded-stores
plan: 06
subsystem: docs-and-ui
tags: [adr, supersession, criterion-6, demo-page, static-gates, mutation-testing]

# Dependency graph
requires:
  - phase: 12-caller-identity-session-ownership-bounded-stores
    plan: 02
    provides: "the signed identity cookie riding every fetch call site for free -- which is why the page needed zero transport changes"
  - phase: 12-caller-identity-session-ownership-bounded-stores
    plan: 03
    provides: "limits.status()'s additive rate_limit_scope/reserved_run_usd fields, and the identity-keyed rate window the reworded #limits line describes"
  - phase: 12-caller-identity-session-ownership-bounded-stores
    plan: 04
    provides: "caller-scoped GET /sessions and the one-404 refusal shape the resume flow's error path assumes"
  - phase: 12-caller-identity-session-ownership-bounded-stores
    plan: 05
    provides: "the note half of REQ-store-lifecycle-and-ownership, and the deferred README limitation line this wave owns"
provides:
  - "ADR-0007, superseding ADR-0006 with an explicit Carried forward section covering all four of 0006's decision parts"
  - "docs/adr/README.md's first real supersession -- both index cells updated, and the 'all six records are Accepted' sentence corrected"
  - "README's 'rate-limited, not authenticated' limitation, rewritten honestly including the free-to-mint fairness ceiling"
  - "/health credentials.identity_signing (presence, never value)"
  - "The identity-aware demo page: footer sentence, two-scope limits line, owned-session list, session resume, and a side-effect-free renderTurnCard()"
  - "Nine static-file criterion-6 gates, including a frozen first-paint text baseline and a frozen markup tag census"
affects: [12-VALIDATION, SC-1, SC-6]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A superseding ADR carries an explicit 'Carried forward' section: the convention forbids editing the overturned record, so the only honest place to say which parts survived is the new one"
    - "Freeze a measured SET, not a count -- adding a font size raises the number of declarations, so a count-based gate stays green for exactly the change it exists to catch"
    - "Freeze the markup's tag census alongside its text: a textless element (empty button, blank-summary disclosure) adds no text run and walks straight past a text-only gate"
    - "Build-and-insert-when-populated rather than declare-and-hide: an element that is not in the document has no empty state to get wrong"
    - "Badge on field PRESENCE (`in` / `typeof`), never truthiness -- truthiness drops a genuine $0 and a genuine zero-revision run along with the absent ones"

key-files:
  created:
    - docs/adr/0007-anonymous-identity-fairness-global-cap.md
  modified:
    - docs/adr/0006-separate-sessions-token-fails-closed.md
    - docs/adr/README.md
    - README.md
    - docs/OPERATIONS.md
    - .env.example
    - src/research_agent/service.py
    - src/research_agent/static/index.html
    - tests/test_service.py

key-decisions:
  - "ADR-0007 supersedes rather than amends, and says what it carries forward. The convention has no 'Amended' status and forbids editing a superseded record's body, so a bare supersession would have silently discarded 0006's parts 3 and 4 -- which are still live and still enforced by a structural walker test."
  - "SESSIONS_TOKEN's carry-forward is recorded as an INVERSION, not a survival. It still exists and still fails closed; what changed is what failing closed costs you (the operator's cross-owner view, not every visitor's access). Writing 'it survives' without that would be true and useless."
  - "The criterion-6 gate asserts the <details> tag is ABSENT from the markup, rather than grepping for the literal `<details id=\"mine\">` the plan specified. The literal cannot exist without either shipping the element in the first-paint DOM -- the exact thing criterion 6 forbids -- or hiding it in a comment, which a comment satisfies. The gate asserts the construction and the absence instead, and both mutations are red."
  - "renderTurnCard() takes no isFollowup-style flag for the stage line: it draws one only when the turn carries its own `question`. A live payload has `task`, not `question`, so the live path (which already drew a stage line before the stream opened) gets none for free."
  - "A resume reads `conversation` when non-empty and falls back to task+latest_answer when it is. A research-only session's single turn lives in the top-level fields; a followed-up session's `conversation` already includes the latest turn, so reading both would render it twice."
  - "refreshSessions() treats non-2xx, a thrown fetch and [] identically -- render nothing, swallow silently. Same posture as refreshLimits()'s catch: the core ask flow must never depend on this feature being reachable."

# Metrics
duration: 68min
completed: 2026-08-05
---

# Phase 12 Plan 06: The reversal recorded, and the page that shows it Summary

**One-liner:** ADR-0007 supersedes ADR-0006 while explicitly carrying forward the three-and-a-half parts of it that survived, the README stopped claiming the demo is "rate-limited, not authenticated", and the demo page gained identity in exactly two muted sentences — with the first-paint constraint that makes the résumé-link demo work now frozen as a machine-checked baseline rather than a thing a human re-eyeballs.

**Tasks 1–3 of 4 executed. Task 4 (the live cutover) was NOT started — see Task 4 below.**

## What was built

### Task 1 — ADR-0007, and the docs that were false (commit `ab54fb5`)

**`docs/adr/0007-anonymous-identity-fairness-global-cap.md`**, a Nygard record with `**Status:** Accepted — supersedes ADR-0006` and a `**Source:** Phase 12` line (not `**Promoted from:**` — there is no `docs/DESIGN.md` passage behind it, exactly as with 0006). Its Context states the three things that had gone wrong with per-IP fairness: the key was forgeable and simultaneously too coarse, it was per-machine on a two-machine fleet so every limit meant double, and communal notes put one visitor's text on another visitor's path to `APPROVED`. Its Decision records the replacement guarantee verbatim from CONTEXT, the documented fairness ceiling (identities are free to mint, so the global cap — not per-identity limits — is what bounds the invoice), the signed-HttpOnly-cookie transport with the CSRF reasoning spelled out (`SameSite=Lax` + JSON-body-only + no CORS middleware), 404-not-403 for foreign sessions, and `TRUST_FORWARDED_FOR` demoted from load-bearing to vestigial.

The part that mattered most is the **`### Carried forward from ADR-0006`** section. The convention forbids editing a superseded record's body, so if the new record does not say what survived, the surviving parts are only discoverable by reading a record stamped "Superseded" and guessing which sentences still apply. All four are named:

- **`SESSIONS_TOKEN` survives as the operator credential**, and its fail-closed property **inverts** rather than disappearing — unset used to mean nobody passes, and now closes only the cross-owner debugging view. Recorded as an inversion, because "it survives" alone would be true and useless.
- **`guard` still does not front the session reads (part 3).** Phase 12 made that decomposition *finer*: the cap left `guard` entirely for an in-handler `reserve_or_429`, and the `DELETE` carries the rate half alone.
- **The router grouping (part 4) is reaffirmed** — only the dependency's name changed, and the structural walker that enforces membership was extended rather than bypassed.
- **`DEMO_TOKEN` must never be set in production**, without qualification.

**ADR-0006:** the status line and nothing else. `git diff` shows 1 insertion, 1 deletion, on line 3.

**`docs/adr/README.md`:** an 0007 row, both records' Status and Superseded-by cells, the "All six records are `Accepted`" sentence corrected (it was about to become false), the `**Source:**` prose widened to cover both odd-ones-out, and a short note telling a reader of a superseded record where to find what survived.

**`README.md`:** the "rate-limited, not authenticated" bullet — deferred by waves 1, 2, 3 and 4 as this wave's to own — was false in both halves by the time it got here. Rewritten to say what the identity is worth (possession of a cookie, not a verified person), what it buys (your own sessions and notes; fairness between visitors instead of one bucket per NAT), what it does not buy (a bound on the bill, because identities are free to mint), and where the record is.

**`/health`** reports `credentials.identity_signing` as a bool, presence never value, with the reason at the line: this is the one credential whose leak is directly exploitable, since it forges any caller's cookie. The existing exact-dict health test carries it and a new test covers the unset case, which is an operator's only signal that a two-machine fleet is minting per-process ephemeral identities.

**`.env.example` and `docs/OPERATIONS.md`:** `IDENTITY_SIGNING_SECRET` documented in both, plus the two claims `deferred-items.md` logged against this wave (see Deviations).

### Task 2 — the identity-aware page (commit `1c79677`)

Five changes to `src/research_agent/static/index.html` and nothing else.

1. **Footer sentence**, verbatim from the copywriting contract, as a bare `<div>` inside `<footer>` above the `.mono` link row. A `<div>` rather than a `<p>` because the UA's default paragraph margin would push the link row down; it inherits `--muted` and `.82rem` from `footer` and needs no CSS rule at all.
2. **`#limits`, reworded** to name both scopes: `10 requests/hour for this browser · $1.23 of $5.00 spent by all visitors in the last 24h`. It reads only fields `/demo` already returned, so the additive-shape rollout constraint holds in both directions — a new page against an old API still populates the line. The `token_required` branch is untouched.
3. **The owned-session list.** A `<details>` built in script, given `id = "mine"`, and inserted before `#out` **only while it has rows** — `syncMine()` puts it in and takes it back out, so an empty list is not a stray disclosure triangle a first-time visitor pays for. `refreshSessions()` fetches `/sessions`, renders up to 10 newest rows as `<button type="button" class="session-row">` with the task's first line (via `textContent`, ellipsised, `flex: 1`) and a muted relative age, and swallows non-2xx, `[]` and thrown fetches identically. Called on load and after every completed run. The CSS uses only existing custom properties and existing sizes; `.session-row`'s `font: inherit` is what keeps the weight ramp at `{600, 700}` without declaring a `400` that would have broken AC7's set equality.
4. **`renderTurnCard(turn, isFollowup)`**, the side-effect-free renderer, and `result()` refactored onto it. Every badge is conditional on its field being *present* — `"approved" in turn`, `typeof turn.cost_usd === "number"` — rather than truthy, so an absent field renders no badge while a genuine `$0` or a genuine zero-revision run still does. A stored turn carries only a question and an answer, so it gets no badges at all; the old `result()` would have given it a fabricated `$0.0000` and `undefined revision(s)` in the same badge styling as a measured fact. `result()`'s side effects (set `session`, set the placeholder, clear the input) stay outside the shared renderer, because a resume renders N turns and those must fire once.
5. **Resume.** Clicking a row (ignored while `busy`) GETs `/sessions/{id}`, appends each stored turn through `renderTurnCard`, sets `session = id`, sets the follow-up placeholder, collapses the list and focuses the input — after which the existing `run()` path posts to `/sessions/{id}/ask/stream` unchanged. 403/404 shows the verbatim "That session has expired" card, removes the row, re-syncs the count and does **not** set `session`; a network failure shows the existing "Could not reach the service" card and leaves the row alone.

**Verified behaviourally, not just by grep.** No jsdom is installed and installing a package is out of bounds here, so a throwaway DOM shim (in the scratchpad, not committed) ran the real script block and asserted 48 properties: that a stored turn fabricates no cost, no revision count and no `undefined`; that a live payload renders exactly the badges it did before; that `cost_usd: 0` still renders; that the list stays out of the document across empty/non-2xx/thrown-fetch and comes back out when it empties again; that a research-only session renders its single turn from `task` + `latest_answer` while a followed-up session renders each turn once rather than the last one twice; that 404 removes the row and updates the count; and that the next submission after a resume posts to `/sessions/abc123/ask/stream`. All passed.

### Task 3 — the criterion-6 gates (commit `d7d06e2`)

Nine static-file tests in `tests/test_service.py`, reading the file through `service.DEMO_PAGE` so moving it cannot leave the gates on a stale copy.

| Test | What it freezes |
|------|-----------------|
| `page_keeps_innerhtml_at_zero` | count `== 0` (measured baseline 0), after a non-vacuity check that the real file was read |
| `page_font_sets_unchanged` | the SETS of `font-size` and `font-weight` literals equal the AC7 baselines; plus the `font:` shorthand set, and that the script sets no styles at all |
| `page_first_paint_has_no_new_interactive_element` | the markup's full tag census |
| `page_first_paint_text_is_frozen` | every visible text run in the served markup, in order |
| `page_copy_and_dom_present` | the verbatim copy, `renderTurnCard`, the constructed-not-declared session list, the new call sites |
| `page_renderer_omits_absent_badges_instead_of_inventing_them` | the presence tests, and the absence of the `\|\| 0` fallback |
| `page_session_list_enters_the_dom_only_when_populated` | the guarded insertion and removal |
| `page_introduces_no_new_colour` | the only literal colour outside `:root` is `#fff` |
| `page_is_self_contained` | no external resource, case-insensitively and wider than the plan's grep |

**The two-delta claim is now measured, not asserted.** `page_first_paint_text_is_frozen` was built by diffing the served markup's text runs against the pre-phase file: the whole phase's markup delta is **exactly one run**, the footer sentence, inserted at index 4. The second permitted delta (the `#limits` line) is not a markup delta at all — `<p id="limits">` ships empty and is filled from `/demo` at runtime — so its copy is asserted separately. That is the closest a static test gets to criterion 6 itself, and it is red for a banner, a prompt, a consent line, an empty-state message or a rendered session list.

## Verification record

| Gate | Baseline (measured on this tree, 2026-08-05) | Result |
|------|----------------------------------------------|--------|
| `grep -c "supersedes ADR-0006" docs/adr/0007-*.md` | file absent | **2** (≥ 1) |
| `grep -c "Superseded by ADR-0007 (Phase 12)" docs/adr/0006-*.md` | 0 | **1** |
| `git diff --stat docs/adr/0006-*.md` | — | **1 insertion, 1 deletion** — the status line only |
| 0007 Nygard headings (`## Context` / `## Decision` / `## Consequences`) | — | **3** |
| `grep -c "^\*\*Source:\*\* Phase 12"` / `grep -c "Promoted from"` in 0007 | — | **1 / 0** |
| `grep -c "SESSIONS_TOKEN\|DEMO_TOKEN" docs/adr/0007-*.md` | — | **5** (≥ 2) |
| `grep -c 0007 docs/adr/README.md` | 0 | **6** |
| `grep -c "rate-limited, not authenticated" README.md` | 1 | **0** — corrected, not appended to |
| `grep -c identity_signing src/research_agent/service.py` | 0 | **1** |
| `grep -c innerHTML .../static/index.html` | 0 | **0** |
| `grep -c renderTurnCard .../index.html` | 0 | **3** |
| `grep -c 'src="http\|href="http\|cdn' .../index.html` | 0 | **0** |
| `grep -c "ask/stream" .../index.html` | 1 | **1** (≥ 1) |
| `fetch(` call sites | 2 | **4** (+`/sessions`, +`/sessions/{id}`) |
| font-size set | `{.78rem,.82rem,.85em,.88em,.9rem,.95rem,1.15rem,1.6rem}` | **identical** |
| font-weight set | `{600, 700}` | **identical** |
| first-paint markup text runs | 11 | **12** — the one added run is the footer sentence |
| `pytest -k health` | 11 passed | **12 passed** |
| `pytest -k page_` | 0 collected | **10 passed** |
| Full suite, plain | 516 passed / 47 skipped | **526 passed / 47 skipped** |
| Full suite, armed (`:54329`) | 562 passed / 1 skipped | **572 passed / 1 skipped** |
| `.venv/bin/ruff check .` | clean | clean |
| Node syntax check on the extracted script block | — | clean |

**Delta fully explained, and there are no new skips.** +10 passed in **both** arms:

- Task 1: **+1** — `test_health_reports_an_unset_signing_secret_as_false`.
- Task 3: **+9** — the nine page gates.

Every new test is a static-file read or an in-memory client call, so none is Postgres-gated. The skip count is unchanged at 47 plain and 1 armed — unlike waves 2, 3 and 4, this wave adds **no** test whose green plain run is weaker evidence than its armed one, and there is nothing to justify.

## Falsification checks

Twenty-five mutations against the criterion-6 gates. Twenty-four red; the tree was confirmed byte-identical after every batch.

| Mutation | Observed |
|----------|----------|
| Introduce one `innerHTML` | RED |
| Add a new `font-size` (`1.05rem`) | RED |
| Add `font-weight: 400` | RED |
| Smuggle a size through the `font:` shorthand | RED |
| Set a size from script (`row.style.fontSize`) instead of CSS | RED |
| Add a consent banner to the markup | RED |
| Reword the footer identity sentence | RED (2 tests) |
| Delete the footer sentence entirely | RED (3 tests) |
| Ship the session list in the markup (empty element on first paint) | RED (3 tests) |
| Add a **textless** interactive element before the first question | RED |
| `result()` stops going through the shared renderer | RED |
| `renderTurnCard` goes back to fabricating a cost | RED |
| The session list is appended unconditionally, even when empty | RED |
| The list is never taken back out when it empties | RED |
| A second, unguarded insertion elsewhere in the file | RED |
| Hardcode a colour in a new rule | RED |
| Drop the `/sessions` call site | RED |
| Drop the resume flow's `GET /sessions/{id}` | RED |
| Reword the expiry error copy | RED |
| Revert the limits copy to the pre-phase wording | RED |
| Pull in an external font from a CDN | RED (3 tests) |
| Remove `identity_signing` from `/health` | RED (2 tests) |
| Report the signing secret's **value** instead of its presence | RED (2 tests) |

**One mutation stayed green, and is recorded as correctly green rather than as a hole:** changing an `--accent` value inside `:root`. AC7 freezes which properties new rules *use*, not the palette's values; a redesign of the palette is a legitimate change and dark mode still works. The falsifying mutation for that gate is **hardcoding** a colour in a new rule, which is red above.

## Deviations from Plan

**1. [Rule 2 — Missing critical control] Three of my own gates were vacuous against the mutations they were written for**

- **Found during:** Task 3, falsification pass — before the tests were committed.
- **Issue:** the plan's three gates, written as specified, all passed under mutations they exist to forbid.
  - *"The session list is appended unconditionally, even when empty"* stayed **green**. This is the core of criterion 6 and nothing checked it: the plan's `<details id="mine">` grep only constrains the markup, and the JS was free to append an empty list.
  - *"`renderTurnCard` goes back to fabricating a cost"* stayed **green** — the single most specific thing the renderer was extracted not to do.
  - *A textless interactive element added before the first question* stayed **green**: an empty `<button>` contributes no text run, so a text-only first-paint gate cannot see it. AC1 forbids it in as many words.
- **Fix:** three added tests — the guarded-insertion assertion, the presence-test assertion on the renderer's body, and a frozen markup **tag census** alongside the frozen text. All three mutations are now red.
- **Files modified:** tests/test_service.py. **Commit:** `d7d06e2`

**2. [Rule 1 — Bug] The fix for the worst of those was itself vacuous — this project's twelfth**

- **Found during:** Task 3, re-running the battery after the fix.
- **Issue:** the first version of `page_session_list_enters_the_dom_only_when_populated` searched the whole of `syncMine()` for `"rows &&"`. The `else if (!rows && mine.parentNode)` branch contains that substring, so the gate passed under the exact mutation it had just been written for.
- **Fix:** it now extracts the insertion and removal **lines** and asserts `if (rows` on the first and `!rows` on the second, plus that the file contains exactly one insertion. Red under three separate mutations (unconditional insert, unconditional remove, a second insertion elsewhere).
- Worth stating plainly: this is the twelfth vacuous gate in this project and the first written by the wave that found it. The lesson is narrower than "mutate your gates" — it is that a substring gate over a *region* is unsafe whenever the region contains a negation of the thing being asserted.

**3. [Deliberate] The `<details id="mine">` gate asserts the tag is ABSENT, not present**

- The plan's T-06-3 asks the test to grep the file for a literal `<details id="mine">`. That literal cannot honestly exist. Putting the element in the markup ships it in the first-paint DOM, which is precisely what the plan's own must-have ("not in the DOM until populated") and criterion 6 forbid — and a mutation confirms it turns three gates red. The only other way to satisfy the grep is a code comment mentioning the tag, which would make the gate green in exactly the state it is meant to forbid.
- The gate therefore asserts the **construction** (`el("details")` bound to `mine.id = "mine"`) **and** that no `<details` tag appears anywhere in the file. That is strictly stronger, and it is why the CSS/JS comments in `index.html` were reworded to avoid the literal — a gate that reads prose can be fooled by prose.

**4. [Rule 1 — Falsified docs] `docs/OPERATIONS.md`, beyond the two items deferred to this wave**

- `deferred-items.md` assigned this wave two claims 12-03 falsified: the "Concurrency and the spend cap interact, and this is not fixed" paragraph, and `DEMO_RATE_LIMIT_PER_HOUR` described as "Requests per visitor IP". Both are corrected, and `DEMO_RESERVED_RUN_USD` (absent entirely) added. The deferred-items entry is marked closed with the commit.
- Two more found in passing and fixed with them: `.env.example` carried the *same* per-visitor-IP error in its comment, and the `TRUST_FORWARDED_FOR` row still read as though it were load-bearing when ADR-0007 demotes it to logging. Both are now correct.
- `IDENTITY_SIGNING_SECRET` was added to the OPERATIONS Fly-secrets snippet with the app-wide reasoning and a pointer to `/health`'s new field. This documents the Task 4 procedure; **nothing was executed against the live service.**

**5. [Mechanical] `tests/test_service.py` gained two stdlib imports**

- `html.parser.HTMLParser` and `collections.Counter`, for the first-paint text and tag gates. No new dependency.

**6. [Recovery] A `git checkout` of my own reverted an uncommitted edit**

- While mutation-testing `/health`, a `git checkout -- src/research_agent/service.py` intended to revert a mutation instead reverted the (uncommitted) `identity_signing` edit, because the mutation script had failed to apply — `python` is not on `PATH` in this environment, only `.venv/bin/python`. Re-applied, and subsequent mutations used a file copy rather than `git checkout`. No commit was affected. Recorded because the same trap is available to any future wave: **never revert a mutation with `git checkout` while the work it sits on is uncommitted.**

## Task 4 — NOT STARTED (deferred by the user)

`T-06-4` is a `checkpoint:human-action` gate covering the live cutover: generate the secret, `fly secrets set IDENTITY_SIGNING_SECRET=…`, `fly deploy`, then verify `/health` reports `identity_signing: true` on **both** machines, that a cookie minted on machine A verifies on machine B (recording both `FLY_MACHINE_ID`s), and that a real cleared-storage/incognito browser reaches the demo with no wall and with the `ra_id` cookie `HttpOnly; Secure; SameSite=Lax` and invisible to `document.cookie`.

**The user explicitly deferred it.** No Fly secret was set, no deploy was run, the live service was not touched, and nothing was pushed. The task is unstarted, not blocked and not failed. Everything automatable ahead of it is done: both suites are green, `ruff` is clean, and the exact commands and verification steps are in the plan's `<how-to-verify>` and now also in `docs/OPERATIONS.md`.

**Consequences for the phase:**

- **Criterion 6 is proven statically, not live.** The two-delta first paint, the innerHTML zero, the frozen font sets and the absent-until-populated session list are all machine-checked against the served file. What is *not* proven is the same thing in a real browser against the deployed service — which is the half Task 4 owns, and the half that would catch, say, a CSP header the file itself cannot know about.
- **Two-machine identity continuity is untested.** `IDENTITY_SIGNING_SECRET` is unset in production, so the fleet is currently minting per-process ephemeral identities: a visitor bounced between machines becomes a new visitor and loses their sessions. `/health` now reports this (`identity_signing: false`), which it could not before.

## Requirements

Both requirements this plan carries stay **Pending**, and that is now the only honest reading rather than a judgement call.

- `REQ-demo-authentication` — waves 1 and 2 each left it Pending with the same reasoning: the requirement's text is only demonstrable on the deployed service. That is Task 4.
- `REQ-store-lifecycle-and-ownership` — delivered in code in both halves (sessions in 12-04, notes in 12-05) and 12-05 handed it here explicitly, noting it depends on `REQ-demo-authentication`. Closing it while the thing it depends on is unproven would mark it complete on a dependency that has not been demonstrated.

Marking either one now would be checking off a deployed-behaviour requirement from a tree that has not been deployed.

## Threat Flags

None. Every row in the plan's register is implemented and gated:

| Threat | Where it is closed |
|--------|--------------------|
| T-12-06-01 an auth wall or visible step kills the résumé-link demo | frozen first-paint text **and** tag census; the session list absent from the document until populated, gated on the insertion line after the region-scoped form proved vacuous. *Live browser check outstanding — Task 4.* |
| T-12-06-02 signing secret leaked via /health or logs | presence-not-value in the credentials block, with a leak assertion in the health test; red under a mutation that reports the value |
| T-12-06-03 untrusted session task text rendered via innerHTML | all new DOM through `el()`/`textContent`; the row's task text explicitly so; `innerHTML == 0` gated and red under one introduction |
| T-12-06-04 per-machine ephemeral secret → cross-machine mint fails | documented in ADR-0007, `.env.example` and OPERATIONS; surfaced at runtime by `/health`'s new field. **The live two-machine verification is Task 4 and is outstanding.** |
| T-12-06-05 ADR left "Accepted" while its central claim is untrue | ADR-0007 supersedes 0006 with carry-forward; 0006's status line flipped, body untouched (1-line diff) |

No new security surface: no route, no schema, no new trust boundary. The page gained two GET call sites to endpoints that already existed and are already owner-scoped.

## Self-Check: PASSED

- `docs/adr/0007-anonymous-identity-fairness-global-cap.md` exists; `docs/adr/0006-separate-sessions-token-fails-closed.md`, `docs/adr/README.md`, `README.md`, `docs/OPERATIONS.md`, `.env.example`, `src/research_agent/service.py`, `src/research_agent/static/index.html` and `tests/test_service.py` all exist and are modified as claimed
- Commits `ab54fb5`, `1c79677`, `d7d06e2` all present on `gsd/phase-12-caller-identity`
- Suites re-run at summary time: 526/47 plain, 572/1 armed, `ruff` clean
