# 16-04 — The fly.toml pin, and the cutover

**Status:** Complete
**Plan:** `16-04-PLAN.md` · Wave 4
**Completed:** 2026-08-10

## What shipped

| Task | What | Commit |
|------|------|--------|
| 1 | `CRITIC_MODEL = 'claude-opus-5'` in `fly.toml [env]` + the value pin in `tests/test_deploy_config.py`, same commit | `bafa3ff` |
| 2 | Phase gate battery | — |
| 3 | Checkpoint: operator approved merge + deploy + one paid run | — |
| 4 | The cutover — **Fly release v10** | this file |

## The cutover

**The first deploy since v9 (2026-08-05), carrying phases 13, 14, 15 and 16 together.**
Run from merged `main` after PR #12, never from the branch — deploying unmerged work is the
drift Phase 10 existed to remove.

```
v10  complete  1m6s ago   hessam.abbaszadi@gmail.com
app  846975f2604548  10  syd  started  1 total, 1 passing
app  d8d0320f751618  10  syd  started  1 total, 1 passing
```

`/`, `/health`, `/demo`, `/metrics`, `/pricing` — all 200.

## The phase proven on the wire

One anonymous run (`0fedbc8ea01244d49e3336d0b1a905b9`, technical, approved, 3172 chars,
**$0.209316**). The per-node model attribution, from `fly logs`:

```
classifier   model=claude-sonnet-5   cost=0.000354
researcher   model=claude-sonnet-5   cost=0.173144
writer       model=claude-sonnet-5   cost=0.013910
critic       model=claude-opus-5     cost=0.021855
```

That is the whole phase in four lines. The critic ran on a **different model** and was
**billed at Opus rates** while every other node stayed on Sonnet — which is precisely what
the misbilling discriminator was built to catch, now confirmed against production rather
than a fake. `pricing_unknown` is false.

Cost came in at **$0.2093** against the ~$0.18 estimate and the $0.40 ceiling. The
researcher node dominates ($0.173) — the critic's Opus premium is $0.0219 of the run, so
the flip is a ~12% cost increase, not the doubling a naive reading of $5/$25 vs $3/$15
would suggest. The $0.20 reservation is now marginally under a typical run; the documented
threshold anticipated this and the note in `limits.py` stands, but it is worth watching:
the 2026-09-01 Sonnet boundary will push it further.

## Phase 14's booked smoke, finally run

`docs/OPERATIONS.md` booked this for whenever the next deploy happened. It happened here:

- **`/metrics` → `embedding_usd: 5.3e-05`** — non-zero. Voyage embedding spend is counted
  in production for the first time; a whole provider is no longer missing from the bill.
- **`/pricing`** carries `multipliers` (`cost_discount_factor: 1.0`,
  `inference_geo_multiplier: 1.1` with the honest note that it applies per response
  `usage.inference_geo`), both `windows` (current until `2026-08-31`, `next` present), and
  embedding rows.

Phase 15 ships nothing into the image; phase 13's live leg ran pre-deploy on scratch tables.
Both stated so the record is complete rather than implying they were skipped.

## Still true after the flip

`/demo` reports `token_required: false`, `rate_limit_scope: identity`. A stranger from a
résumé link still reaches a working demo with no signup — criterion 6 of Phase 12, unharmed
by giving the critic a costlier model.

## Known and expected: the fixture is now stale

The recorded eval fixture grades **stale** in any environment that sets `CRITIC_MODEL`,
because its models map has no `critic` entry and backfills to the pipeline model. That is
the Phase 15 gate working exactly as designed — the map was introduced with this phase in
mind. CI is unaffected (it runs keyless with `CRITIC_MODEL` unset). Re-recording stays
deferred to the full 40-case run.

## The pin, and why it asserts a value

Losing `CRITIC_MODEL` fails **open**: the critic reverts to the writer's model, the revision
loop keeps working, `/health` reports ok, Fly's check passes, and the only trace is a
smaller number in the demo's cost line. `fly.toml`'s own header records that Fly's tooling
has rewritten `[env]` twice. And presence alone proves nothing — `CRITIC_MODEL` set to the
writer's model is exactly the arrangement ADR-0010 supersedes.

Both mutations were run before the commit and each reddened **only** the pin: value changed
to `claude-sonnet-5`, and key deleted. Tree restored clean after each.

## Gate battery

| Gate | Result |
|------|--------|
| Plain suite | **692 passed / 65 skipped** |
| Armed (PG :54329) | **756 passed / 1 skipped** |
| Offline evals, keyless | **41/41**, `CRITIC_MODEL` unset |
| `ruff check .` | clean |
| `.github/workflows/ci.yml` | zero diffs vs main |

## What this phase did NOT do

- **No judge flip.** ADR-0010 re-derived the rationale and concluded the judge stays on
  `claude-opus-5` — now sharing the critic's model, recorded as an acceptance rather than
  discovered later.
- **No writer change.** Sonnet, unchanged.
- **No re-record** of the calibration fixture.

---
*Phase: 16-independent-critic-model*
*Cutover: 2026-08-10, Fly release v10*
