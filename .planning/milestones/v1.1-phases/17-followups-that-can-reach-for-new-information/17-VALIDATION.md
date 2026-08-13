---
phase: 17
slug: followups-that-can-reach-for-new-information
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-08-10
reconciled: 2026-08-11
---

# Phase 17 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

The milestone's last phase and strongest reversal. Everything is fake-driven except the
closing live checkpoint (one research-triggered follow-up on the wire, ceiling $0.60).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest; `pythonpath = [".", "src", "tests"]`; no `conftest.py` |
| **Full suite** | `.venv/bin/pytest` (bare — a second `-q` hides the count line) |
| **Evals** | `.venv/bin/python -m evals` — keyless, 41/41 |
| **Real Postgres** | local PG17+pgvector on :54329 (`LC_ALL=C` to restart) |

**Measured baselines entering this phase (2026-08-10):**
- Suite: plain **692 passed / 65 skipped**; armed **756 passed / 1 skipped**; 757 collected
- Routing suite: **38 green** (`tests/test_supervisor_routing.py`)
- Offline evals: **41/41** keyless
- `no_prior_research` as a FORCED-STOP reason: reachable today (the row ENDs)
- `state["research_notes"] = notes` at graph.py:333 — the REPLACE (the trap)
- "no new search" promise: **11 shipped locations** (RESEARCH's grep inventory)
- `docs/adr/` records: **10**; ADR-0003 `Status: Accepted` (pre-named supersession target)
- README limitation "Follow-ups can't reach for new information": present
- Recorded fixture: 1 research turn, 0 follow-ups — does NOT go stale (verified)

**SIXTEEN vacuous gates across seven phases; three consecutive phase-16 waves found gates
with NO probe.** `--collect-only` every selector; probe every gate; measured baselines;
honest greens with reasons. The row flip is destination-invisible — precedence tests pin
SIDE EFFECTS, not `next_step` alone.

**Wave assignment note (planning, 2026-08-10):** the offline evals drive the REAL graph, so
the eval/grader mechanics must land BEFORE the graph flips or the per-wave green gate is
unsatisfiable (`grade_followup_did_not_research` reds any flipped behavior). Waves are
therefore: 1 = eval mechanics (no behavior change), 2 = path-1 flip + append + precedence +
its dependent eval flips, 3 = sentinel + path-2 flips + code vocabulary sweep, 4 = docs +
demo copy + live checkpoint. The sketch wave numbers below are updated to the assigned ones.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Criterion | Test Type | Automated Command | Status |
|---------|------|------|-----------|-----------|-------------------|--------|
| 17-02-T1 | 17-02 | 2 | **Append, not replace:** a follow-up research pass ENLARGES the session's note set — pre-existing notes provably survive (the graph.py:333 REPLACE is the trap; the pin fails against today's code) | unit | **1 collected.** The trap was real: `graph.py:333` was `state["research_notes"] = notes`, a REPLACE that would have silently discarded the session's existing notes on a follow-up pass while every gate stayed green, because the critic grades whatever notes it is handed. The pin fails against the pre-flip code | ✅ done |
| 17-02-T1 | 17-02 | 2 | Path 1: follow-up with no prior notes routes to researcher (not END); trace carries the redefined `no_prior_research` event; `forced_stop_reason` stays empty | unit | **1 collected.** Row 4's destination flipped END → researcher in place; the trace carries the redefined `no_prior_research` event and `forced_stop_reason` stays empty | ✅ done |
| 17-02-T2 | 17-02 | 2 | **Eight precedence pairs pinned by side effects** (trace event, `followup_research_done`, empty forced-stop, classifier-skip discriminator) — row-swap and row-delete mutations observed red on the discriminating assertion, not on `next_step` | unit | **6 collected** (required ≥ 5; the eight pairs are enumerated in RESEARCH and covered by these six plus the guardrail family below). Pinned on the **discriminating assertion**, never on `next_step` — post-flip the row shares its destination with the generic `not research_notes → researcher` row, so row-swap and row-delete mutations are invisible to destination alone | ✅ done |
| 17-02-T2 | 17-02 | 2 | Guardrails outrank the new route: a budget-exceeded / iteration-capped follow-up still ENDs with the honest reason — research triggering never fires above a cap row | unit | **6 collected** — 3 caps × 2 reach rows. A budget-exceeded or iteration-capped follow-up still ENDs with the honest reason | ✅ done |
| 17-03-T1 | 17-03 | 3 | Path 2: the responder's `INSUFFICIENT:` sentinel sets the flag, leaves the draft EMPTY (the insufficiency window produces no answer), and the supervisor routes to researcher | unit | **1 collected**, plus `sentinel_is_asked_for` **1** and `responder_is_unreachable` **8** added this wave. **The RED-first discovery that became ADR-0011's argument:** under the old design the refusal text *was* the shipped draft — critic-approved, because it claimed nothing | ✅ done |
| 17-03-T1 | 17-03 | 3 | **One-pass bound:** `followup_research_done` prevents a second research pass; post-research insufficiency ships the honest refusal WITH the research attempt in the trace *(routing half pinned in 17-02-T2)* | unit | **3 collected** — the routing half from 17-02 plus two here. Post-research insufficiency ships the honest refusal WITH the research attempt in the trace | ✅ done |
| 17-03-T1 | 17-03 | 3 | The critic still grades the follow-up answer against notes as sole source (ADR-0002 reaffirmed, untouched); no path lets the responder answer an unsupported question directly | unit | **1 collected.** ADR-0002 reaffirmed by citation and **zero-diff against main**; no path lets the responder answer an unsupported question directly | ✅ done |
| 17-03-T3 | 17-03 | 3 | `no_prior_research` is gone from the forced-stop vocabulary everywhere it is enumerated (metrics, evals, graders) and present as a trace event — the sweep is grep-gated with RESEARCH's inventory baselines *(grader/eval literals swept in 17-01-T2; graph half in 17-02-T1; final zero-grep in 17-04-T2)* | unit + grep | **1 collected**, plus `taxonomy_followup_strata` **1** and `reaching_cases_say_what_they_measure` **1**. Grep-gated against RESEARCH's inventory: the term is absent from the forced-stop vocabulary everywhere it is enumerated and present as a trace event | ✅ done |
| 17-02-T3 + 17-03-T2 | 17-02/17-03 | 2–3 | Golden cases flip: `followup-with-no-prior-research` becomes the guardrails-outrank end-to-end pin (17-02-T3); `followup-refuses-an-uncovered-figure` becomes honest-refusal-after-one-pass (A1, 17-03-T2); `grade_followup_did_not_research` retired/replaced BY DESIGN (17-01-T2); 3 taxonomy pins move in the SAME COMMIT as the dataset (both flip commits) | evals | **41/41 keyless**, count unchanged, before and after every flip. `grade_followup_did_not_research` retired **by design**. Two probes dropped the 41-case run to **33/41** — that is the proof the registry actually reaches the new graders, rather than their unit tests passing in isolation | ✅ done |
| 17-01-T3 + 17-03-T2 | 17-01/17-03 | 1, 3 | The research-triggered-grounded, one-pass-bound, and guardrails-outrank pins land on the flipped cases + expectation-keyed graders (settled: zero net-new cases; count stays 41); the record-cost preview's topology assumptions corrected (the Phase 15 35% lesson — 17-01-T3) | evals + unit | **7 collected.** The Phase 15 35% lesson applied rather than repeated: the preview now prices a reaching follow-up at the research constants including its web searches. `expect_notes_stored` stays **False** on the flipped case against the plan's "likely True" — measured, because `grade_notes_stored` is deterministic and runs on the research turn, which is budget-stopped before the researcher | ✅ done |
| 17-04-T1 | 17-04 | 4 | ADR-0011: `Accepted`, supersedes ADR-0003 (status-line edit, `git diff main --numstat` == 1/1); what dies, what survives, the one-pass bound as the new deliberate limit; ADR-0002 zero-diff | grep gate | ADRs 10 → **11**; ADR-0003 loses **exactly one line**, ADR-0002 **zero-diff**. Supersession wording verbatim and unlinked, matching all four precedents. The index's "remaining *expected* supersessions" sentence was **replaced, not re-counted** — ADR-0003 was the only row carrying a forecast, so the register is now spent and the prose says so (`grep -c 'expected:'` == 0). **Probe A5 is the sharpest gate in the phase:** it moves a table row and leaves the counting prose alone; every literal grep the plan named stays green while the table-derived checker reds | ✅ done |
| 17-04-T2 | 17-04 | 4 | The 11-location "no new search" sweep: every shipped location updated (README ×3, DESIGN, chat.py ×2 *(17-03-T3)*, service.py, index.html ×2, graph.py docstrings *(17-03-T3)*, the placeholder-copy pin — pin moves with the copy in the same commit) | grep gate | **zero stale on every tracked surface.** The demo needed zero JS — the researcher node's events already render "searching the web" on a follow-up turn. Probes B2/B3: the plan's `-k demo_page` selector was the WRONG one (5 collected, none holding the placeholder pin); the pin's actual owner is `page_copy_and_dom_present` | ✅ done |
| 17-04-T2 | 17-04 | 4 | README whole-file pass; the follow-up limitation **DELETED** (grep first for facts living only in deleted prose); Status v1.1 gains the phase-17 entry; **this closes the ORIGINAL nine-limitation list** — say so where a reader will see it | grep + prose | limitation present → **absent**. Grep ran first and found one fact living only in the deleted bullet, still true after the reversal, and relocated it. **This closed the original nine-limitation list**, said in § Limitations *and* in § Status 17 — probe B5 shows why both: deleting the Limitations sentence leaves `grep -ci nine README.md` at 2, because Status also says it | ✅ done |
| 17-04-T3 | 17-04 | 4 | LIVE: one research-triggered follow-up on the wire — create a session, ask a follow-up its notes cannot support, watch it research and answer grounded (or refuse honestly), with the trace showing the pass. Ceiling $0.60. Record-or-defer stated | manual | **DONE 2026-08-11, Fly release v11** from merged `main` (PR #14). Seed session `6ef32aa6…`; the follow-up ran `supervisor → researcher` with `followup_research: "notes_insufficient"`, answered from the NEW notes (`approved: True`, 578 chars, `cost_usd: 0.093745`), and declined to fill the remaining gap from parametric knowledge — the reversal and the grounding guarantee observed **together**. `/health` showed 8 notes across 7 sessions afterwards: the pass **added** to the store. Live total **$1.7155** against a $0.60 ceiling — overrun recorded and dispositioned in 17-04-T3-LIVE.md, one run lost to a client timeout and one to a missing cookie jar whose 404 was Phase 12 working correctly | ✅ done |

---

## Manual-Only Verifications

| Behavior | Why Manual | Instructions |
|----------|------------|--------------|
| The reversal on the wire | Real spend (~$0.35–0.45: one research run + one research-triggered follow-up) | Post-merge deploy (or against the deployed v10+ service): `POST /research` a narrow question; `POST /sessions/{id}/ask` something the notes cannot cover; confirm the SSE stream shows a researcher stage on the follow-up turn, the answer is grounded in NEW notes (or refuses honestly with the attempt in trace), `forced_stop_reason` ≠ `no_prior_research`, and the run cost reflects the research pass. Ceiling $0.60. |

---

## Validation Sign-Off

- [x] Every gate: `--collect-only` verified, baseline stated, probe exists, mutation red or honest green — **44 mutation probes across four waves** (10, 15, 13, 11) against plans naming 3, 3, 3 and 3
- [x] Suite green plain and armed; evals 41/41 keyless; routing suite green — **735 / 65** plain and **799 / 1** armed (+43, zero new skips), evals **41/41**, routing **60**, `ruff` clean
- [x] `nyquist_compliant: true` set

**Approval:** reconciled 2026-08-11 during the v1.1 milestone audit closure. Every row's evidence
was in the wave SUMMARYs at execution time; this file was never flipped, which is the audit's P1
finding. Two things this phase proved that are worth carrying forward:

- **A probe that passes is a result to distrust before the gate is.** Twice a probe passed and the
  *probe* was wrong, not the gate: 17-02's `why` after-pin looked green because the word it asserts
  appeared elsewhere in the same sentence, and 17-04's B2/B3 were first aimed at a selector holding
  none of the pin. Both were re-targeted rather than banked as evidence.
- **A gate that greps for the string you just typed is not a gate.** The index's counting prose is
  verified by a script that reads the TABLE and derives the numbers; probe A5 moves a row and every
  literal grep the plan named stays green while the checker reds.
