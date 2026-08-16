# ADR-0013 — The classifier runs on its own model, and its default is the upgrade rather than a neutral

**Status:** Accepted
**Source:** Phase 21.5 (2026-08-16), `REQ-classifier-model`

## Context

The classifier is the first model call a research run makes and the cheapest one it will
ever make: one prompt, twenty output tokens, thinking disabled. It emits one word. That
word is not cosmetic — `state["topic_type"]` selects the researcher's strategy from
`RESEARCH_STRATEGY` and the critic's rubric from `CRITIC_RUBRIC`, so a wrong label
mis-aims both halves of the pipeline for the rest of the run, quietly and with every
guardrail still green.

Until this record the classifier ran on `graph.MODEL` — the writer's model,
`claude-sonnet-5` — because it had never been asked to run on anything else. Phase 16 had
already built the seam that makes a per-node model possible: `call_model(state, node, *,
model=None)` resolves one name and uses it at four sites, and `critic_model()` is the
accessor that feeds it. Nothing new had to be invented here; the only question was what to
feed it and what the default should be.

**The measurement.** On 2026-08-15 a two-model probe ran the shipped classifier prompt over
every golden case carrying an `expect_topic_type` — 38 cases, both models, identical prompt
and identical call kwargs, one variable — and scored each model's resolved label against
the dataset:

| Model | Correct | Fixes | Regressions |
|-------|---------|-------|-------------|
| `claude-sonnet-5` | 29/38 | — | — |
| `claude-opus-5` | 34/38 | 5 | 0 |

**The repeat, 2026-08-16 — this is the number that governs.** The n=1 caveat below was
answered rather than left standing: the committed probe re-ran against the corrected
labels and the shape held.

| Model | Correct | Fixes | Regressions |
|-------|---------|-------|-------------|
| `claude-sonnet-5` | **32/38** | — | — |
| `claude-opus-5` | **37/38** | 5 | **0** |

Measured $0.0459 against a $0.0439 quote; report archived at
`.planning/phases/21.5-classifier-on-opus-5/classifier-probe-report.json`. The absolute
counts moved because three labels were corrected first (below) — which is exactly why the
trust criterion was written as a shape rather than a score. The single remaining miss is
`chatty-label-falls-back`, the one case that could not be relabelled; 37/38 is the honest
figure, not a rounding.

Cost delta: roughly +$0.0005 a run (~140 input, ~5 output tokens), against a measured
$0.21–0.32 per run — about 0.2%, two orders of magnitude below the critic's share. The
project owner proposed the upgrade before the probe existed and the probe agreed with him;
the orchestrator's initial scepticism was wrong and is recorded as such in the ROADMAP.

**n=1, and what was done about it.** Classification is not pinned deterministic and the
first probe ran each case once, so this record was written on evidence it did not yet
trust. The trust criterion was a shape, not a score: Opus ≥ Sonnet **and** zero
regressions, with a failure to hold being a checkpoint back to the owner with the new
numbers — never a silent proceed, never a silent abort. The repeat ran on 2026-08-16
(`evals/classifier_probe.py`, committed by this phase), the shape held, and the table
above carries both measurements rather than quietly replacing the weaker one.

**Four cases where both models disagreed with the dataset.** Two independent models reading
the same label as wrong is evidence about the *dataset*, and the phase resolved all four
deliberately. Three were relabelled to `technical` with reasoning recorded in the case's
own `why` or beside its fields. The fourth, `chatty-label-falls-back`, was left exactly as
written: its offline leg needs `general` unconditionally, because its scripted off-menu
label exists to fire the fallback, while its live leg reads a Kalman filter as technical on
any competent model. Those two legs cannot both be satisfied and no model choice changes
that, so the divergence is documented in the case rather than chased. It is also one of
exactly three cases holding the off-menu-general floor in
`test_dataset_taxonomy_per_stratum_minimums`, at zero spare — relabelling it drops that
list from three to two, observed as a red under mutation. The `general` stratum moved 11 → 8
against a floor of 7.

## Decision

**The classifier runs on `claude-opus-5`, resolved through a `classifier_model()` accessor
whose default is that model DIRECTLY — not `graph.MODEL`.**

```python
def classifier_model() -> str:
    return os.environ.get("CLASSIFIER_MODEL", "").strip() or "claude-opus-5"
```

`classifier_node` passes `model=classifier_model()` to `call_model`, and nothing else about
the call changes: same `max_tokens=20`, same disabled thinking, same effort. The prompt
moved to a module constant `CLASSIFIER_PROMPT_TEMPLATE`, verified byte-identical when
formatted, so that the probe can import the shipped prompt rather than copy it. **One
variable.** No prompt improvement rides along in this record; that was offered and
deliberately declined as scope creep, because a measurement whose prompt also moved would
have measured nothing.

Pricing needed no work: `usage.PRICES` has carried a `claude-opus-5` row since the critic
moved there, and `call_model` passes the resolved name into `record()`, which prices by
that string. An unpriced classifier flips `pricing_unknown` (DEC-12), which is tested.

### The two deliberate asymmetries with ADR-0010's precedent

A reader who knows `CRITIC_MODEL` will expect this record to mirror it, and in two places
it deliberately does not. Both departures are load-bearing, and neither is an oversight.

**(a) The default's polarity is inverted.** `critic_model()` reads an absent `CRITIC_MODEL`
as the writer's model. That neutrality was correct for Phase 16: the capability was
genuinely opt-in, shipping it was meant to change nothing until an operator acted, and
`fly.toml` carried the whole flip.

That precondition does not hold here. **This requirement IS the opt-in**, already made by
the project owner at milestone level and confirmed by measurement — there is no
"ship the capability, decide later" step to protect. A neutral default would mean every
shell that had not exported the variable ran the classifier on Sonnet: CI, a fresh
checkout, and above all the operator's own shell during a record run. Phase 21's record run
refused six-to-eight cases on their `topic_type` grader for precisely that reason. A
`MODEL`-defaulted knob would have reproduced that failure *inside the phase built to fix
it*, after the money was spent. A default that depends on remembering to override it is not
a default.

The knob still exists, for the downgrade direction only: an Opus outage, a deprecation, an
operator deliberately re-measuring the old behaviour. There is no validation past
strip-or-default, for `critic_model()`'s stated reason — pointing the node at any real
model is the feature, and an unpriced name is `pricing_unknown`'s problem, not a
whitelist's.

**(b) There is deliberately no staleness gate for the classifier role.**
`record_case_to_fixture` writes `models.classifier` as a fourth, extra role;
`REQUIRED_MODEL_ROLES` stays `("pipeline", "judge")`; and `grade_fixture_current` gains
**no** classifier comparison. The role is provenance and nothing more.

This is the direct consequence of (a), and it is the one place a reader is most likely to
assume a bug. The critic's staleness comparison is safe in CI *because* its default is
neutral: `critic_model() == graph.MODEL` wherever nobody set the variable, so only a
deliberate override sees staleness. Under a non-neutral default that safety evaporates.

The phase demonstrated the cascade rather than arguing it. A classifier comparison was
added temporarily, in the obvious symmetric shape (`models.get("classifier") or pipeline`,
against `classifier_model()`), and measured in a keyless shell:

```
fixtures on disk: 19
fixture_current RED: 19
carrying a 'classifier' key: 0
budget-cap-is-labelled.json: the CLASSIFIER was recorded on 'claude-sonnet-5' but this
  tree runs it on 'claude-opus-5' (CLASSIFIER_MODEL) -- the recording describes a
  pipeline that no longer exists; re-record
```

The offline evals fell from 59/59 to 40/59 — exactly the nineteen replay legs. Every one of
those recordings is a true record of what the pipeline said on the day it was made, and
none of them is in this phase's re-record scope. The mutation was reverted; the observation
is this record's evidence. `grade_fixture_current`'s docstring now separates the judge's
uncompared role from the classifier's, because the two are uncompared for different
reasons, and a future reader who conflates them will "restore consistency" and find out at
CI's expense.

### The `fly.toml` line, and why its test fails in the opposite direction

`fly.toml [env]` carries `CLASSIFIER_MODEL = 'claude-opus-5'` beside `CRITIC_MODEL`, so the
per-node model stance is readable in one place. **Deleting it changes nothing** — the code
default is the same model — which is the exact inverse of `CRITIC_MODEL`, where deletion
fails open and silently reverts the deployed critic.

So `tests/test_deploy_config.py` pins the VALUE while treating absence as legal:
`env.get("CLASSIFIER_MODEL") in (None, "claude-opus-5")`. Absence is provably a no-op and a
test that reds on a harmless edit gets deleted by whoever hits it. Drift is the real risk:
the knob is honoured live, so a line here naming a different model moves the deployed
classifier off the measured choice with every check in the repository still green. Fly's
tooling has rewritten that file twice.

## Consequences

### Accepted

- **Every environment classifies on Opus 5 with no configuration**, including CI, a fresh
  checkout, and the operator's shell during a paid record run. That is the point.
- **The offline suite cannot see this change, by construction, and that is stated rather
  than implied.** `ScriptedClient` returns each case's authored `topic_label` without
  calling a model, so a green keyless suite says nothing about classification quality. What
  the keyless gates prove is *structural*: the accessor's default, the threading to all four
  naming sites, the misbilling discriminator, and the provenance field. The quality claim
  rests on the probe, which is paid.
- **About +$0.0005 per run**, ~0.2% of a measured run. No cost reservation, quote or
  estimate moves meaningfully; `evals/__main__.py`'s single-model preview now under-quotes
  the classifier's share as well as the critic's, and says so.
- **Fixtures recorded from this record forward name their classifier; the nineteen recorded
  before it do not, and never will.** Absence means pre-21.5, exactly as an absent `critic`
  key means pre-16. No fixture file was edited by this phase.
- **Three golden cases carry different labels than they did.** `general-defines-a-term`,
  `followup-with-no-prior-research` and `injection-tries-to-force-approval` moved
  `general → technical` in `expect_topic_type`/`topic_label` lockstep — one field alone
  would break the offline leg, since a stale `general` in `topic_label` is a valid strategy
  key that never falls back. The `general` stratum sits at 8 against a floor of 7, one
  spare, and the reasoning for each is in the case.
- **This record supersedes nothing.** ADR-0010's surviving position — the critic runs on a
  more capable model than the writer it gates — is untouched and unrelated; this record
  adds a second per-node model, it does not reopen the first. The judge stays on
  `claude-opus-4-8` per ADR-0012, and moving it was never in scope: the critic already runs
  Opus 5, so a judge move here would undo Phase 18.

### Rejected alternatives

- **A neutral `MODEL` default, mirroring `CRITIC_MODEL` exactly.** The consistent-looking
  option, and the one that would have re-broken the phase's own re-record. Rejected on the
  precondition, not on taste: Phase 16's neutrality protected an opt-in that had not been
  made yet, and this one has been.
- **A code-level change with no knob at all.** Simpler, and it removes the emergency
  downgrade. Rejected because an Opus outage or deprecation should be survivable by an
  operator setting a variable, not by a deploy.
- **A classifier staleness comparison in `grade_fixture_current`.** Rejected on the
  measured nineteen-red cascade above, not on preference. It would have turned CI red for
  nineteen recordings this phase has no budget to re-record and no reason to distrust.
- **Making `classifier` a required model role.** Rejected for a harder failure than
  staleness: the loader raises before any grader runs, so the nineteen fixtures would stop
  *loading*. The critic has lived as an extra role since Phase 16 for the same reason.
- **Relabelling `chatty-label-falls-back` along with the other three.** Rejected: its
  offline and live legs want different answers by construction, and it holds a stratum
  floor at zero spare. Documented in the case instead.
- **Improving the classifier prompt while it was open.** Tempting and out of scope. One
  variable per measurement; the prompt's relocation to a constant is byte-identical and the
  test suite pins the substring both scripted clients dispatch on.
