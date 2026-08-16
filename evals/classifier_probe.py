"""Two models, one classifier prompt, every labelled golden case.

The measurement behind Phase 21.5: does `claude-opus-5` classify the golden
dataset better than the writer's model does? It is a paid operator tool, not a
CI gate -- 76 real API calls, about $0.05 -- so it follows `evals/__main__.py`'s
record idiom exactly: the preview is built and printed BEFORE any client
exists, and `--yes` is the only thing that lets a client be built at all.

    python -m evals.classifier_probe             # preview, then refuse (exit 2)
    python -m evals.classifier_probe --yes       # spend

Why this is a module rather than a flag on `evals/__main__.py`: the shape is
different in every respect that matters. It never invokes the graph, never
calls a judge, never writes a fixture, and grades one node's answer against a
dataset label. Folding it into that argparse surface would blur what --record
and --live mean, which are the two flags in this repository that spend money.

Two properties keep the measurement honest, and both are pinned by tests:

  * The prompt is `graph.CLASSIFIER_PROMPT_TEMPLATE` BY IDENTITY, not a copy.
    A copied prompt drifts the moment anyone edits the shipped one, and it
    drifts silently -- the probe would keep reporting a number for a classifier
    that no longer exists.
  * The call kwargs are the classifier's own (max_tokens=20, thinking
    disabled, effort medium), and the answer is resolved the way
    `classifier_node` resolves it -- strip, lower, then fall back to "general"
    for anything off-menu. What is being measured is what the PIPELINE would
    do with the model's answer, not whether the raw string happened to match.

One variable: the model string. Nothing else about the call differs between
the two arms, which is the only reason the difference means anything.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime
import json
import pathlib
import sys

from evals.dataset import GOLDEN
from research_agent import graph
from research_agent import usage as usage_accounting

# The prompt, by identity. Bound here so the probe has one module-level name to
# pin -- `tests/test_evals.py` asserts this `is` graph's own object, because an
# equality check would stay green against a copy, which is the exact failure
# this binding exists to make impossible.
PROMPT_TEMPLATE = graph.CLASSIFIER_PROMPT_TEMPLATE

# The two arms. Literals rather than accessors on purpose: this is a
# measurement of two NAMED models, and reading `classifier_model()` here would
# mean the probe measured whatever the operator's shell happened to say --
# a report that cannot be compared against the one before it.
BASELINE_MODEL = "claude-sonnet-5"  # what the classifier ran on before Phase 21.5
CANDIDATE_MODEL = "claude-opus-5"  # what it runs on now

# The measured per-call shape from the 2026-08-15 run: the formatted prompt is
# ~477 characters and the answer is one word. Used for the PREVIEW only -- the
# report's cost is measured from the responses' own usage, never re-assumed.
ASSUMED_INPUT_TOKENS = 140
ASSUMED_OUTPUT_TOKENS = 5

DEFAULT_REPORT = pathlib.Path(
    ".planning/phases/21.5-classifier-on-opus-5/classifier-probe-report.json"
)


def labelled_cases() -> list:
    """The cases carrying a topic label to be right or wrong about.

    Derived from the dataset every run, never hardcoded: the count is 38
    today, and Phase 21.5's own relabelling moves which VALUES are expected
    without moving which cases are present. A hardcoded denominator would turn
    a dataset edit into a probe that quietly measures a different population.
    """
    return [case for case in GOLDEN if case.expect_topic_type is not None]


def _per_call_usd(model: str) -> float | None:
    """None means the model has no price row -- `pricing_unknown`'s situation,
    reported rather than raised, so a preview for an unpriced model still
    prints instead of ending the run with a traceback."""
    call = usage_accounting.CallUsage(
        input_tokens=ASSUMED_INPUT_TOKENS, output_tokens=ASSUMED_OUTPUT_TOKENS
    )
    try:
        return call.cost_usd(model)
    except usage_accounting.UnknownModelPricing:
        return None


def preview(cases: list) -> tuple[str, float]:
    """The quote, and the estimate it totals to.

    Built from the case list and the price table alone -- no client, no key,
    no network. That ordering is the property `test_the_probe_refuses_to_spend
    _without_yes` proves by making the constructor raise.
    """
    lines = [
        f"classifier probe: {len(cases)} labelled case(s) x 2 models "
        f"= {len(cases) * 2} calls",
        f"  assuming ~{ASSUMED_INPUT_TOKENS} input / ~{ASSUMED_OUTPUT_TOKENS} "
        "output tokens per call (measured 2026-08-15)",
    ]
    total = 0.0
    for model in (BASELINE_MODEL, CANDIDATE_MODEL):
        per_call = _per_call_usd(model)
        if per_call is None:
            lines.append(f"  {model}: UNPRICED -- no price row; cost not estimable")
            continue
        subtotal = per_call * len(cases)
        total += subtotal
        lines.append(f"  {model}: {len(cases)} calls, ${subtotal:.4f}")
    lines.append(f"  estimated total: ${total:.4f}")
    return "\n".join(lines), total


def classify(client, model: str, task: str) -> tuple[str, object]:
    """One classifier call, resolved the way `classifier_node` resolves it.

    The fallback matters as much as the call. An off-menu answer -- chatty
    prose, an empty string, a category nobody defined -- becomes "general" in
    the pipeline, so that is what the probe must score. Scoring the raw string
    would count a model's formatting habits as classification skill.
    """
    response = client.messages.create(
        model=model,
        max_tokens=20,
        thinking={"type": "disabled"},
        output_config={"effort": "medium"},
        messages=[{"role": "user", "content": PROMPT_TEMPLATE.format(task=task)}],
    )
    label = graph._text(response).strip().lower()
    resolved = label if label in graph.RESEARCH_STRATEGY else "general"
    return resolved, response


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m evals.classifier_probe",
        description="compare two models on the shipped classifier prompt (costs money)",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="required before anything is spent; without it this prints the quote and exits",
    )
    parser.add_argument(
        "--report",
        type=pathlib.Path,
        default=DEFAULT_REPORT,
        help=f"where the per-case report JSON is written (default: {DEFAULT_REPORT})",
    )
    args = parser.parse_args(argv)

    cases = labelled_cases()

    # Printed before anything else, and unconditionally: a preview an operator
    # cannot rely on seeing is the same as no preview.
    quote, estimate = preview(cases)
    print(quote)

    if not args.yes:
        print(
            f"error: --yes is required to spend. {len(cases) * 2} call(s) would be made "
            f"at the estimate above (${estimate:.4f}); nothing was run, and no API "
            "client was built.",
            file=sys.stderr,
        )
        return 2

    # Imported and constructed only past the gate, so the refusal path above
    # never reads a key.
    import anthropic

    client = anthropic.Anthropic()

    rows = []
    measured_cost = 0.0
    for case in cases:
        row = {"id": case.id, "expected": case.expect_topic_type}
        for arm, model in (("sonnet", BASELINE_MODEL), ("opus", CANDIDATE_MODEL)):
            resolved, response = classify(client, model, case.task)
            call = usage_accounting.CallUsage.from_response(response)
            # An unpriced arm contributes nothing to the total rather than
            # ending a paid run with a traceback -- the same shape record()
            # takes with pricing_unknown.
            with contextlib.suppress(usage_accounting.UnknownModelPricing):
                measured_cost += call.cost_usd(model)
            row[arm] = resolved
            row[f"{arm}_match"] = resolved == case.expect_topic_type
        rows.append(row)
        print(
            f"  {case.id}: expected {row['expected']} | "
            f"sonnet {row['sonnet']} | opus {row['opus']}"
        )

    sonnet_correct = sum(r["sonnet_match"] for r in rows)
    opus_correct = sum(r["opus_match"] for r in rows)
    # The locked trust criterion's exact referee: a fix is a case Opus got and
    # Sonnet did not; a regression is the reverse. Zero regressions is the
    # clause that cannot be traded against a higher total.
    fixes = [r["id"] for r in rows if r["opus_match"] and not r["sonnet_match"]]
    regressions = [r["id"] for r in rows if r["sonnet_match"] and not r["opus_match"]]

    report = {
        "recorded_on": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "models": [BASELINE_MODEL, CANDIDATE_MODEL],
        "denominator": len(cases),
        "cases": rows,
        "summary": {
            "sonnet_correct": sonnet_correct,
            "opus_correct": opus_correct,
            "fixes": fixes,
            "regressions": regressions,
        },
        "cost_usd": round(measured_cost, 6),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")

    print(
        f"\n{BASELINE_MODEL}: {sonnet_correct}/{len(cases)}  "
        f"{CANDIDATE_MODEL}: {opus_correct}/{len(cases)}"
    )
    print(f"fixes: {len(fixes)} {fixes}")
    print(f"regressions: {len(regressions)} {regressions}")
    print(f"measured cost: ${measured_cost:.4f} (quoted ${estimate:.4f})")
    print(f"report: {args.report}")

    # The shape is machine-checked; the DECISION stays the operator's. A
    # non-zero exit says the measured shape did not hold, which is a checkpoint
    # back to the user with the new numbers -- not an instruction to abort.
    held = opus_correct >= sonnet_correct and not regressions
    if not held:
        print(
            "error: the shape did NOT hold (needs opus >= sonnet AND zero "
            "regressions) -- take these numbers back to the user before trusting "
            "the switch.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
