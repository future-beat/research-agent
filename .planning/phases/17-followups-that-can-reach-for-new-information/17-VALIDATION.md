---
phase: 17
slug: followups-that-can-reach-for-new-information
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-10
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

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Criterion | Test Type | Automated Command | Status |
|---------|------|------|-----------|-----------|-------------------|--------|
| TBD | TBD | 1 | **Append, not replace:** a follow-up research pass ENLARGES the session's note set — pre-existing notes provably survive (the graph.py:333 REPLACE is the trap; the pin fails against today's code) | unit | `pytest tests/ -k notes_append_not_replace` | ⬜ pending |
| TBD | TBD | 1 | Path 1: follow-up with no prior notes routes to researcher (not END); trace carries the redefined `no_prior_research` event; `forced_stop_reason` stays empty | unit | `pytest tests/ -k followup_no_notes_routes_to_researcher` | ⬜ pending |
| TBD | TBD | 1 | **Eight precedence pairs pinned by side effects** (trace event, `followup_research_done`, empty forced-stop, classifier-skip discriminator) — row-swap and row-delete mutations observed red on the discriminating assertion, not on `next_step` | unit | `pytest tests/test_supervisor_routing.py -k precedence` | ⬜ pending |
| TBD | TBD | 1 | Guardrails outrank the new route: a budget-exceeded / iteration-capped follow-up still ENDs with the honest reason — research triggering never fires above a cap row | unit | `pytest tests/ -k guardrails_outrank_followup_research` | ⬜ pending |
| TBD | TBD | 2 | Path 2: the responder's `INSUFFICIENT:` sentinel sets the flag, leaves the draft EMPTY (the insufficiency window produces no answer), and the supervisor routes to researcher | unit | `pytest tests/ -k insufficiency_signal_routes` | ⬜ pending |
| TBD | TBD | 2 | **One-pass bound:** `followup_research_done` prevents a second research pass; post-research insufficiency ships the honest refusal WITH the research attempt in the trace | unit | `pytest tests/ -k one_pass_bound` | ⬜ pending |
| TBD | TBD | 2 | The critic still grades the follow-up answer against notes as sole source (ADR-0002 reaffirmed, untouched); no path lets the responder answer an unsupported question directly | unit | `pytest tests/ -k grounding_survives_followup_research` | ⬜ pending |
| TBD | TBD | 2 | `no_prior_research` is gone from the forced-stop vocabulary everywhere it is enumerated (metrics, evals, graders) and present as a trace event — the sweep is grep-gated with RESEARCH's inventory baselines | unit + grep | `pytest tests/ -k no_prior_research_redefined` | ⬜ pending |
| TBD | TBD | 3 | Golden cases flip: `followup-with-no-prior-research` becomes the guardrails-outrank end-to-end pin; `followup-refuses-an-uncovered-figure` becomes honest-refusal-after-one-pass (A1); `grade_followup_did_not_research` retired/replaced BY DESIGN; 3 taxonomy pins move in the SAME COMMIT as the dataset | evals | `env -u CRITIC_MODEL python -m evals` 41/41 | ⬜ pending |
| TBD | TBD | 3 | New golden cases: research-triggered follow-up grounded answer; the one-pass bound; the record-cost preview's topology assumptions corrected (the Phase 15 35% lesson) | evals + unit | `pytest tests/ -k record_preview` | ⬜ pending |
| TBD | TBD | 4 | ADR-0011: `Accepted`, supersedes ADR-0003 (status-line edit, `git diff main --numstat` == 1/1); what dies, what survives, the one-pass bound as the new deliberate limit; ADR-0002 zero-diff | grep gate | baselines: 10 ADRs → 11 | ⬜ pending |
| TBD | TBD | 4 | The 11-location "no new search" sweep: every shipped location updated (README ×3, DESIGN, chat.py ×2, service.py, index.html ×2, graph.py docstrings, the placeholder-copy pin — pin moves with the copy in the same commit) | grep gate | RESEARCH inventory baselines → 0 stale | ⬜ pending |
| TBD | TBD | 4 | README whole-file pass; the follow-up limitation **DELETED** (grep first for facts living only in deleted prose); Status v1.1 gains the phase-17 entry; **this closes the ORIGINAL nine-limitation list** — say so where a reader will see it | grep + prose | limitation present → absent | ⬜ pending |
| TBD | TBD | 5 | LIVE: one research-triggered follow-up on the wire — create a session, ask a follow-up its notes cannot support, watch it research and answer grounded (or refuse honestly), with the trace showing the pass. Ceiling $0.60. Record-or-defer stated | manual | see Manual-Only | ⬜ pending |

---

## Manual-Only Verifications

| Behavior | Why Manual | Instructions |
|----------|------------|--------------|
| The reversal on the wire | Real spend (~$0.35–0.45: one research run + one research-triggered follow-up) | Post-merge deploy (or against the deployed v10+ service): `POST /research` a narrow question; `POST /sessions/{id}/ask` something the notes cannot cover; confirm the SSE stream shows a researcher stage on the follow-up turn, the answer is grounded in NEW notes (or refuses honestly with the attempt in trace), `forced_stop_reason` ≠ `no_prior_research`, and the run cost reflects the research pass. Ceiling $0.60. |

---

## Validation Sign-Off

- [ ] Every gate: `--collect-only` verified, baseline stated, probe exists, mutation red or honest green
- [ ] Suite green plain and armed; evals 41/41 keyless; routing suite green
- [ ] `nyquist_compliant: true` set

**Approval:** pending
