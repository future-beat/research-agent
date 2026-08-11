---
phase: 16
slug: independent-critic-model
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-08-10
reconciled: 2026-08-11
---

# Phase 16 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

A threading-and-honesty phase: one env var, four call sites, a fixture-gate extension, an
ADR that re-derives a decision instead of inheriting it — and, per the USER DECISION
(2026-08-10), the production cutover itself: `CRITIC_MODEL = 'claude-opus-5'` in fly.toml
[env], deployed after the phase PR merges. Almost everything is fake-driven; the live leg
is one post-deploy demo run on the real config (Opus critic), ceiling $0.40.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest; `pythonpath = [".", "src", "tests"]`; no `conftest.py` |
| **Full suite** | `.venv/bin/pytest` (bare — a second `-q` hides the count line) |
| **Evals** | `.venv/bin/python -m evals` — keyless, 41/41 |
| **Real Postgres** | local PG17+pgvector on :54329 (restart with `LC_ALL=C` if down) |

**Measured baselines entering this phase (2026-08-10):**
- Suite: plain **663 passed / 65 skipped**; armed **727 passed / 1 skipped**
- Offline evals: **41/41** keyless
- `CRITIC_MODEL` anywhere in src/: **0** · `critic_model` accessor: **0**
- `CRITIC_MODEL` in fly.toml: **0** (`grep -c CRITIC_MODEL fly.toml`) — the cutover's baseline
- tests/test_deploy_config.py guards pin VALUES on the parsed [env] table
  (POSTGRES_BACKEND_PINS idiom), NOT exhaustive keys — verified at planning: adding a
  CRITIC_MODEL key reds nothing existing
- `call_model` call sites passing a model: **0** (the constant is read inside)
- Fixture models map keys: `{pipeline, judge}` — no `critic` (1 fixture on disk)
- `docs/adr/` records: **9**; ADR-0005 `Status: Accepted` (the pre-named supersession target)
- README limitation "The critic shares the writer's model": present (line ~252)
- PRICES rows: opus-5 and haiku-4-5 exist, UNDATED (safe for exact-cost tests); Sonnet is
  boundary-dated (2026-08-31) and must not appear in exact assertions

**SIXTEEN vacuous gates across seven phases.** `--collect-only` every selector; baselines +
discriminating mutations (or honest green with the recorded reason). Watch for mutations that
go red by an unrelated route.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Criterion | Test Type | Automated Command | Status |
|---------|------|------|-----------|-----------|-------------------|--------|
| 16-01-T1 | 16-01 | 1 | `graph.critic_model()` accessor: unset → `MODEL` (byte-equal); set → the env value. Neutral default proven: with CRITIC_MODEL unset, the API payloads, usage records and logs are byte-identical to today | unit | **5 collected** (baseline 0). Accessor at `graph.py:51`. Neutral default *demonstrated*: full per-call kwargs dicts with the var unset compare equal to a run with it set to `graph.MODEL`, each against a fresh store — so a default path growing an extra kwarg would also red. Probe 3 (cache the accessor at module scope) reds both accessor tests and leaves the two unset/blank tests green | ✅ done |
| 16-01-T1 | 16-01 | 1 | **Four-site threading:** the critic call site's model reaches (a) the API request payload, (b) the tracing span, (c) `record()`/usage attribution, (d) the log line — each asserted separately against a fake capturing all four | unit | **4 collected.** Sites at `graph.py:128` span, `:131` API, `:135` record, `:143` log. Probes 4 and 5 (span, log) each red **exactly one** test; probe 2 (API) reds two payload assertions and leaves cost/span/log green. Under probes 1, 2, 4, 5 **all twenty pre-existing `test_graph_smoke.py` tests stayed green** — RESEARCH Pitfall 3 measured rather than assumed | ✅ done |
| 16-01-T2 | 16-01 | 1 | **The misbilling discriminator:** `CRITIC_MODEL=some-unpriced-name` fires `pricing_unknown` — which can only happen if the threaded name reached `record()`. Every non-critic node still prices as `MODEL` | unit | **3 collected.** Unpriced critic → `pricing_unknown` True with `cost_usd` still > 0 and `calls == 4`; unset → False; the priced/unpriced difference is exactly the critic call. Probe 1 (`record(..., MODEL)`) reds all of it. T-16-01 closed | ✅ done |
| 16-01-T2 | 16-01 | 1 | Per-node cost attribution: a run with critic=opus-5 (undated row) yields critic calls priced at $5/$25 and writer calls at Sonnet's window rate; Phase 14's multipliers apply once, at the choke point. (Haiku's undated row serves the cheap-arithmetic twin — haiku lives in unit tests ONLY; the live leg is Opus, the real config) | unit | **3 collected.** Arithmetic measured as a *difference* between haiku and opus runs — both undated rows, so the $0.0060 gap is fixed forever and Sonnet's 2026-08-31 boundary never enters an exact assertion. Probe 6 (call site stops passing the model) reds all three | ✅ done |
| 16-02-T3 | 16-02 | 2 | Reservation stays flat $0.20 with a DOCUMENTED threshold stated as the ACTUAL production config: Opus-critic typical ≈ $0.18 (the $0.20 estimate stays honest — no resize accompanies the cutover), the 3-call worst case (~$0.28, by design outside the estimate), and the Sept-1 boundary alone lifting typical runs past $0.20 | grep gate + content pin | `reservation_threshold` **2 collected** (baseline 0), because the plan's gate was a grep inside a plan that nothing runs again. `CRITIC_MODEL` mentions: `limits.py` 0 → **1**, OPERATIONS 0 → **6**. Probes 14–15. **Corrected 2026-08-11:** the figures this row pinned ($0.18 typical, $0.28 tail) were estimates the milestone's own live runs later contradicted ($0.2093 on v10, $0.25–0.32 on v11); the v1.1 audit's W2 raised the default to $0.30 and re-pinned the tests on the measured band. The *gate* held — it is what made the stale claim findable | ✅ done |
| 16-02-T1 | 16-02 | 2 | Fixture models map gains `critic`; `build_fixture` writes it; `grade_fixture_current` compares it with **backfill semantics** (`models.get("critic") or models["pipeline"]`) — the existing fixture stays green with CRITIC_MODEL unset and goes stale the moment it is set | unit | **5 collected** (baseline 0). Backfill semantics honest rather than convenient: the one committed fixture was recorded at `225b06b`, when `call_model` had no `model` parameter, so its critic ran on `graph.MODEL` by construction. The sharpest probe: a recorder writing `graph.MODEL` into the critic slot **satisfies the map pin**, because the suite runs with `CRITIC_MODEL` unset and the two strings are then equal — a pin that runs at the neutral default cannot see a mutation producing the neutral default | ✅ done |
| 16-02-T2 | 16-02 | 2 | Record-mode stderr line when `judge.model == critic_model()` — fires on collision, silent otherwise. Worded as STATING A FACT (it WILL fire on the chosen production config: judge and critic both claude-opus-5), naming the shared model and ADR-0010, never implying error | unit | **4 collected** (baseline 0). Worded as a fact — a test forbids "misconfig"/"error"/"invalid". Probe 12 found the gate had none: the line dereferences `judge.model` upstream of the judgeless refusal | ✅ done |
| 16-03-T1 | 16-03 | 3 | ADR-0010: `Accepted`, supersedes ADR-0005 (status-line edit only on 0005); "different job" stands alone; the USER'S critic-stronger-than-writer rationale QUOTED VERBATIM as a new design position; judge==critic recorded as an ACCEPTANCE (verdicts not independent of the critic's family — the honest narrowing of ADR-0005's independence claim); "stronger" for the judge demoted to preference; structured-verdict half carried forward; conclusion: judge stays, critic flips in production (fly.toml, 16-04); ADR-0002 untouched | grep gate | ADRs 9 → **10**; ADR-0005's diff against main **`1 1`** (status line, nothing else); ADR-0002 **zero-diff**; the user's rationale blockquoted verbatim and attributed. The counting prose corrected to **eight of ten / two supersessions** — the plan asked for "nine of ten" *and* "two supersessions", which cannot both hold. Probe A: all four collision tests stay **green** with the record deleted, so a test now holds both halves of the supersession | ✅ done |
| 16-03-T2 | 16-03 | 3 | Stale prose fixed everywhere it lives: graders.py:13-17, DESIGN.md:74 (one-line forward ref), the harness docstring + its content-pinning test (test_evals.py:1655) updated TOGETHER | unit + grep | `graders.py` docstring rewritten (four `__doc__` greps recorded first — no test pins it); `DESIGN.md:74` one line, one hunk. **The grep-invisible one:** the docstring above the `:464` pin still ended "the same limitation the in-graph critic already has" — the dead premise, missed by every grep in the plan, the research and this file; corrected in the same two lines so the assertion stays at `:464` | ✅ done |
| 16-03-T3 | 16-03 | 3 | README: whole-file pass; the "critic shares the writer's model" limitation **DELETED** (not rewritten); facts living only in deleted prose grepped for and relocated first; the residual one-liner states REALITY (critic on a stronger model than the writer; judge shares the critic's model — ADR-0010); Status list gains the phase 16 entry naming the flip | grep gate | limitation present → **absent** (deleted, not rewritten); grep ran first and found the only load-bearing fact surviving independently at `:32`, so nothing needed relocating. The whole-file pass found four things the plan did not name, the sharpest being **`663 tests` at two sites, falsified by this phase's own waves 1–2 → 690**. The `$0.14` transcript figures left alone deliberately: replacing a measurement with an estimate invents a run that never happened | ✅ done |
| 16-04-T1 | 16-04 | 4 | **The fly.toml pin:** `CRITIC_MODEL = 'claude-opus-5'` in [env], commented like the other vars, guarded by a value pin in tests/test_deploy_config.py in the SAME commit (same-commit rule). Mutations: value change reds ONLY the pin; key delete reds ONLY the pin | unit | Commit `bafa3ff`, pin and value in the same commit. **Both mutations run before the commit**, each redding **only** the pin: value → `claude-sonnet-5`, and key deleted; tree restored clean after each. The pin asserts a VALUE because losing the key fails **open** — the critic reverts to the writer's model, `/health` reports ok, Fly's check passes, and the only trace is a smaller number in the demo's cost line | ✅ done |
| 16-04-T4 | 16-04 | 4 | LIVE CUTOVER: the first deploy since v9, from MERGED main, carrying phases 13-16; phase-14's booked smoke passes (non-zero `cost.embedding_usd` in /metrics, /pricing windows + multipliers); one demo run shows critic calls priced at Opus rates ($5/$25) and writer calls at Sonnet's window; pricing_unknown false; /metrics sane; demo still anonymous; ceiling $0.40 | manual | **DONE 2026-08-10, Fly release v10** from merged `main`, carrying phases 13–16. One anonymous run `0fedbc8ea012…`, **$0.2093** against the $0.40 ceiling. `classifier/researcher/writer model=claude-sonnet-5`, `critic model=claude-opus-5 cost=0.021855` — the whole phase in four log lines, `pricing_unknown` false. Phase 14's booked smoke passed here: `/metrics` → `embedding_usd: 5.3e-05`, non-zero for the first time. `/demo` still `token_required: false` | ✅ done |

---

## Manual-Only Verifications

| Behavior | Why Manual | Instructions |
|----------|------------|--------------|
| Independent critic demonstrated on the REAL config | One paid post-deploy run (typical ≈ $0.18 with the Opus critic; ceiling $0.40, never a second paid run) | After the cutover deploy: one short question through the public demo endpoint with NO auth header (that absence is the anonymity check). From `fly logs`, capture the "model call" lines — critic line model=claude-opus-5 with its cost_usd; writer/researcher/classifier lines model=claude-sonnet-5. Usage: pricing_unknown false, total cost recorded. Haiku appears NOWHERE in the live leg — it stays in unit tests (undated-row arithmetic). |
| Production flip — the cutover IS this phase's deliverable | USER DECISION (2026-08-10): "Use Opus as the critic's model since it has to be more capable than the writer's model." Deploys are manual; the deploy must carry only merged work | `CRITIC_MODEL = 'claude-opus-5'` lands in fly.toml [env] (committed configuration, guarded by test_deploy_config.py). Sequence: phase PR merges → `git checkout main && git pull --ff-only` → `fly deploy -a research-agent` → phase-14's booked smoke (OPERATIONS :556-563) → this phase's verification run → SUMMARY records deploy version, evidence lines, total cost. Phases 13/15 have nothing separately booked (13's live leg done 2026-08-09 pre-deploy on scratch tables; 15 ships nothing in the image). |

---

## Validation Sign-Off

- [x] Every gate: `--collect-only` verified, baseline stated, mutation red or honest green — **27 new tests, 21 mutation probes** across three waves (the plans named 3, 2 and 2)
- [x] Suite green plain and armed; offline evals 41/41 keyless with CRITIC_MODEL unset — **691 / 65** plain, **755 / 1** armed, zero new skips across the phase; evals **41/41**, `ruff` clean
- [x] The cutover recorded: deploy version, booked-smoke outcomes, per-node Opus/Sonnet pricing evidence, spend ≤ $0.40 — **v10**, `$0.2093` of a `$0.40` ceiling
- [x] `nyquist_compliant: true` set

**Approval:** reconciled 2026-08-11 during the v1.1 milestone audit closure. Every row's evidence
was in the wave SUMMARYs at execution time; this file was simply never flipped, which is what the
audit's P1 finding is about. Two things are recorded here rather than smoothed over:

- **No RED gate commit exists for waves 1 or 2.** Both carry `tdd="true"` while sequencing
  implementation before tests, so every new test was green on first run. The substitute evidence
  is the probe set, and it is the stronger artefact — a RED commit shows a test failing before
  code exists; a probe shows *which* test fails for *which* line.
- **Two of wave 2's own verify selectors were vacuous** (`-k docstring` collects 0; `-k "record
  and models"` misses the map pin), so the first probe run reported a wrong result. Corrected and
  re-run before any probe was believed. The sixteen-vacuous-gates failure in miniature, inside a
  plan written to prevent it.
