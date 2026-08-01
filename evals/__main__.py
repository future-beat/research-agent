"""
Eval CLI.

    python -m evals                        offline: free, deterministic, CI-safe
    python -m evals --live                 real API + judge graders (costs money)
    python -m evals --report out.json      write the report artifact
    python -m evals --case followup-admits-a-gap --case revision-then-approval

Exits non-zero when the pass rate falls below `--min-pass-rate`, so CI can
fail on a regression without anyone reading the output.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

# The agent logs one JSON line per model call. That is what you want in a
# container and the opposite of what you want here, where it buries the
# per-case verdicts. Set before importing the agent, since the logger is
# configured at import; an explicit LOG_LEVEL still wins.
os.environ.setdefault("LOG_LEVEL", "WARNING")

from evals import graders as G  # noqa: E402
from evals.dataset import select  # noqa: E402
from evals.harness import (  # noqa: E402
    live_memory_factory,
    offline_client_factory,
    offline_memory_factory,
    run_suite,
)

GREEN, RED, DIM, BOLD, RESET = "\033[32m", "\033[31m", "\033[2m", "\033[1m", "\033[0m"


def _colour(text: str, code: str, enabled: bool) -> str:
    return f"{code}{text}{RESET}" if enabled else text


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="evals", description=__doc__)
    parser.add_argument(
        "--live",
        action="store_true",
        help="run against the real API and enable judge graders (costs money)",
    )
    parser.add_argument(
        "--case",
        action="append",
        dest="cases",
        metavar="ID",
        help="run only this case; repeatable",
    )
    parser.add_argument("--report", metavar="PATH", help="write the JSON report here")
    parser.add_argument(
        "--min-pass-rate",
        type=float,
        default=0.9,
        help="exit non-zero below this pass rate (default: 0.9)",
    )
    parser.add_argument("--quiet", action="store_true", help="only print the summary")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    colour = sys.stdout.isatty()

    try:
        cases = select(args.cases)
    except KeyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    judge = None
    if args.live:
        # Imported lazily so the offline path never needs an API key.
        import anthropic

        client = anthropic.Anthropic()
        judge = G.Judge(client)
        client_factory = lambda case: client  # noqa: E731 - one live client for all cases
        memory_factory = live_memory_factory
    else:
        client_factory = offline_client_factory
        memory_factory = offline_memory_factory

    def announce(result) -> None:
        if args.quiet:
            return
        mark = _colour("PASS", GREEN, colour) if result.passed else _colour("FAIL", RED, colour)
        print(f"  {mark}  {result.case_id}")
        if result.error:
            print(f"        {_colour(result.error, RED, colour)}")
        for grade in result.failures:
            print(f"        {_colour(grade.grader, RED, colour)}: {grade.detail}")
            # The dataset says what regressing this costs; a failing eval is
            # the moment that sentence is worth reading.
            print(f"        {_colour('why it matters: ' + result.why, DIM, colour)}")

    mode = "live" if args.live else "offline"
    if not args.quiet:
        print(f"{_colour('Research agent evals', BOLD, colour)}  ({mode}, {len(cases)} cases)\n")

    report = run_suite(
        cases,
        client_factory=client_factory,
        memory_factory=memory_factory,
        judge=judge,
        mode=mode,
        min_pass_rate=args.min_pass_rate,
        on_result=announce,
    )

    summary = report["summary"]
    verdict = (
        _colour("PASS", GREEN, colour) if summary["ok"] else _colour("FAIL", RED, colour)
    )
    print(
        f"\n{verdict}  {summary['passed']}/{summary['cases']} cases "
        f"({summary['pass_rate']:.0%} vs {summary['min_pass_rate']:.0%} required)"
    )
    footer = f"  ${summary['cost_usd']:.4f} · {summary['duration_ms'] / 1000:.1f}s"
    if judge:
        footer += f" · {report['judge_calls']} judge calls"
    print(_colour(footer, DIM, colour))
    if mode == "offline":
        print(
            _colour(
                "  offline mode grades the pipeline, not the model — "
                "run with --live to measure answer quality",
                DIM,
                colour,
            )
        )

    if args.report:
        with open(args.report, "w") as f:
            json.dump(report, f, indent=2)
        print(_colour(f"  report written to {args.report}", DIM, colour))

    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
