---
phase: 19
slug: credential-validity-log-addressability-demo-csp
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-14
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

## Sampling Rate

- **After every task commit:** Run the quick command
- **After every plan wave:** Run the full suite, keyless
- **Before verification:** Full suite green plain; offline evals 41/41 exit 0
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

*(Rows below are the researched gate set — the planner assigns Task IDs/Plan/Wave and the
executor fills Status with measured evidence.)*

| Task ID | Plan | Wave | Requirement | Criterion | Test Type | Automated Command / Mutation | Status |
|---------|------|------|-------------|-----------|-----------|------------------------------|--------|
| TBD | TBD | TBD | REQ-health-credential-validity | `/health` carries validity fields beside the presence booleans, additive-only; keyless state reads `valid: null` (unknown), never `false` — a missing key is a presence fact, not a validity fact | unit (fake-driven, keyless) | mutation: make absent-key read `false` → the null-semantics test reds | pending |
| TBD | TBD | TBD | REQ-health-credential-validity | Key-invalid and provider-down are distinguished: `AuthenticationError` → invalid; `APIConnectionError`/5xx → unknown-with-error, NOT invalid — a provider outage must never report a key as bad | unit | fakes raising each typed exception; mutation: collapse the two branches → the outage-is-not-invalid test reds | pending |
| TBD | TBD | TBD | REQ-health-credential-validity | The liveness path never calls a provider: probe is fire-and-forget on the existing `_probes()` executor, `/health` serves the cache and never blocks on a provider call | unit + structural | mutation: make the probe synchronous on the read path → the never-blocks test reds; a fake provider that hangs must not change `/health` latency | pending |
| TBD | TBD | TBD | REQ-health-credential-validity | Cold cache returns `checked_at: null` rather than blocking; a stale read kicks exactly one refresh (no thundering herd) | unit | mutation: remove the in-flight guard → the single-refresh test reds | pending |
| TBD | TBD | TBD | REQ-health-credential-validity | Voyage probe spend is EXCLUDED from cost accounting, and the code states so — `report_embedding()` is meterless outside a run context, pinned as a fact not an accident | unit | test asserts a probe run leaves the embedding meter untouched; the decision comment named in the assertion message | pending |
| TBD | TBD | TBD | REQ-run-finished-session-id | A completed run is addressable from the logs: the service-side emission carries `session_id`, including for brand-new sessions (the id is minted AFTER the graph returns — research finding: LangGraph drops undeclared state keys, so the graph-side site cannot carry it) | unit | log-capture test asserting `session_id` present on both new-session and follow-up paths | pending |
| TBD | TBD | TBD | REQ-run-finished-session-id | No double-count: `run_finished` semantics preserved — one completion event per run, not one per call site | unit | mutation: emit at both sites → the exactly-once test reds | pending |
| TBD | TBD | TBD | REQ-demo-csp-header | The demo page response carries the UI-SPEC's exact directive set; SSE and JSON routes carry NO CSP header | unit | header-presence test on `/` FileResponse branch + header-absence on `/research/stream`; mutation: attach globally → absence test reds | pending |
| TBD | TBD | TBD | REQ-demo-csp-header | The derivation invariant: hashes in the policy are DERIVED from `static/index.html`'s real blocks by a test that also asserts block counts (1 script / 1 style) and zero inline-handler/`style=` attributes | unit | mutation: edit one byte inside the script block → hash test reds; add an `onclick=` → the handler-count test reds | pending |
| TBD | TBD | TBD | REQ-demo-csp-header | index.html changes ZERO lines this phase (UI-SPEC change budget); the live page renders and streams identically | structural + manual | `git diff --stat` on the file at phase close = no entry; manual acceptance per UI-SPEC checks (zero violations attributable to page resources) | pending |

---

## Manual-Only Verifications

| Behavior | Why Manual | Instructions |
|----------|------------|--------------|
| Live page under CSP: full demo flow with zero page-resource violations | Browser CSP enforcement can't run in pytest | UI-SPEC acceptance checks 1–7 against the deployed page after this phase ships (curl the header; run a question; watch SSE; console clean) |
| A real provider probe round-trip | The suite is keyless by invariant | First deploy after merge: `/health` shows `valid: true` + fresh `checked_at` for both providers within one TTL |

---

## Validation Sign-Off

- [ ] Every gate: measured baseline AND recorded mutation (red, or honest green with reason)
- [ ] Suite green plain; keyless invariant intact (`ANTHROPIC_API_KEY=""` throughout)
- [ ] Offline evals 41/41 exit 0
- [ ] `nyquist_compliant: true` set at reconciliation

**Approval:** pending execution.
