"""
Eval CLI.

    python -m evals                        offline: free, deterministic, CI-safe
    python -m evals --live                 real API + judge graders (costs money)
    python -m evals --report out.json      write the report artifact
    python -m evals --case followup-admits-a-gap --case revision-then-approval

Exits non-zero when the pass rate falls below `--min-pass-rate`, so CI can
fail on a regression without anyone reading the output.

Offline runs also replay whatever recordings are committed under
`evals/fixtures/`, automatically -- the command does not change, and neither
does the fact that it needs no key. The two legs are gated differently on
purpose: the behavioural cases are governed by the pass rate, while ANY red or
errored replay case exits non-zero on its own. A committed fixture was
known-good when it was recorded, so a replay red is a real regression, and a
rate that averages it away with twelve greens is a gate that cannot fire.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import pathlib
import sys

# The agent logs one JSON line per model call. That is what you want in a
# container and the opposite of what you want here, where it buries the
# per-case verdicts. Set before importing the agent, since the logger is
# configured at import; an explicit LOG_LEVEL still wins.
os.environ.setdefault("LOG_LEVEL", "WARNING")

from evals import fixtures  # noqa: E402 - the module, so FIXTURES_DIR stays overridable
from evals import graders as G  # noqa: E402
from evals.dataset import by_id, select  # noqa: E402
from evals.harness import (  # noqa: E402
    CaseResult,
    live_memory_factory,
    offline_client_factory,
    offline_memory_factory,
    replay_case,
    run_suite,
    summarise,
)

GREEN, RED, DIM, BOLD, RESET = "\033[32m", "\033[31m", "\033[2m", "\033[1m", "\033[0m"

# What an offline run could honestly say before any recording existed, and what
# it still says on a checkout with no fixtures. Kept verbatim rather than
# reworded, because a suite that grades nothing about answers must not hint
# that it does.
ORIGINAL_CAVEAT = (
    "offline mode grades the pipeline, not the model — "
    "run with --live to measure answer quality"
)


def _colour(text: str, code: str, enabled: bool) -> str:
    return f"{code}{text}{RESET}" if enabled else text


# --------------------------------------------------------------------------
# The replay leg
# --------------------------------------------------------------------------


def _replay_fixtures(paths: list[pathlib.Path], on_result) -> tuple[list[CaseResult], list[dict]]:
    """Grade every committed recording. Exactly one CaseResult per path.

    "Exactly one" is the contract the caller checks: a fixture that produces
    no result at all is invisible to the all-must-pass rule, because there is
    no red to see. Both ways a fixture can fail to become a graded case --
    unreadable file, and a `case_id` the dataset no longer has -- become an
    errored CaseResult here rather than an exception, so they arrive as
    verdicts instead of tracebacks.
    """
    results: list[CaseResult] = []
    loaded: list[dict] = []

    for path in paths:
        try:
            fixture = fixtures.load_fixture(path)
        except fixtures.FixtureError as exc:
            results.append(
                CaseResult(
                    case_id=f"{path.stem}@recorded",
                    why="a committed fixture is CI's pass/fail input; one that cannot be "
                        "read grades nothing while looking like it graded something",
                    error=str(exc),
                )
            )
            on_result(results[-1])
            continue

        case_id = fixture["case_id"]
        try:
            case = by_id(case_id)
        except KeyError:
            # Plausible rather than exotic: Phase 17 keeps fixtures as
            # before-evidence for cases it retires or rewrites. `by_id` raises,
            # and an unhandled raise here would end the run with a traceback
            # instead of a verdict naming the file.
            results.append(
                CaseResult(
                    case_id=f"{case_id}@recorded",
                    why="a recording whose case left the dataset grades nothing",
                    error=f"{path}: recorded case_id {case_id!r} is not in the golden "
                          "dataset -- delete the fixture or restore the case",
                )
            )
            on_result(results[-1])
            continue

        loaded.append(fixture)
        results.append(replay_case(case, fixture))
        on_result(results[-1])

    return results, loaded


def _parsed(recorded_at: str) -> datetime.datetime | None:
    try:
        moment = datetime.datetime.fromisoformat(recorded_at)
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=datetime.UTC)


_FAR_FUTURE = datetime.datetime.max.replace(tzinfo=datetime.UTC)


def _oldest(loaded: list[dict]) -> dict:
    return min(loaded, key=lambda f: _parsed(f["recorded_at"]) or _FAR_FUTURE)


def _fixture_metadata(loaded: list[dict]) -> dict:
    """What the report says about the recordings it graded.

    Zeros and None when nothing was recorded yet, and present either way: a
    reader of the JSON must be able to tell "no fixtures" from "this field was
    never written".
    """
    return {
        "count": len(loaded),
        "models": sorted({f["models"]["pipeline"] for f in loaded}),
        "recorded_at_oldest": _oldest(loaded)["recorded_at"] if loaded else None,
        "git_shas": sorted({f["git_sha"] for f in loaded}),
    }


def _caveat(loaded: list[dict]) -> str:
    """The one line a reader takes away from a green offline run.

    With recordings it must say two things that are both true and easy to
    conflate: the answers graded are real, and they are old. Age is computed
    here, at print time, and lives only here and in the report -- never in a
    grade, because a verdict that changes with the calendar is not a verdict.
    """
    if not loaded:
        return ORIGINAL_CAVEAT

    oldest = _oldest(loaded)
    recorded_at = oldest["recorded_at"]
    moment = _parsed(recorded_at)
    date = moment.date().isoformat() if moment else recorded_at
    when = (
        f"{max((datetime.datetime.now(datetime.UTC) - moment).days, 0)} days ago"
        if moment
        else "age unknown"
    )
    model = "+".join(sorted({f["models"]["pipeline"] for f in loaded}))
    sha = "+".join(sorted({f["git_sha"] for f in loaded}))

    return (
        f"offline mode grades the pipeline, plus answers recorded {date} on {model} "
        f"({sha}, {when}) — that grades what the pipeline said then, not what the "
        "current model would say; run with --live to measure that"
    )


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

    behavioural: list[CaseResult] = []

    def collect(result) -> None:
        behavioural.append(result)
        announce(result)

    report = run_suite(
        cases,
        client_factory=client_factory,
        memory_factory=memory_factory,
        judge=judge,
        mode=mode,
        min_pass_rate=args.min_pass_rate,
        on_result=collect,
    )

    # Replay is automatic, and offline-only: the fixtures are committed files,
    # so grading them needs no key and the CI command does not change.
    matched: list[pathlib.Path] = []
    replay_results: list[CaseResult] = []
    loaded_fixtures: list[dict] = []
    if mode == "offline":
        matched = fixtures.fixture_paths()
        if args.cases:
            # A selected case with no recording is simply not replayed. CI has
            # to pass on a checkout where nothing has been recorded yet.
            wanted = set(args.cases)
            matched = [p for p in matched if p.stem in wanted]
        if matched and not args.quiet:
            print(f"\n  replaying {len(matched)} recorded case(s)")
        replay_results, loaded_fixtures = _replay_fixtures(matched, announce)

        if replay_results:
            # Replay shares the report and the pass-rate denominator with the
            # behavioural leg; the exit rule below is what keeps it from being
            # absorbed by it.
            report["cases"] += [r.as_dict() for r in replay_results]
            report["summary"] = summarise(behavioural + replay_results, args.min_pass_rate)
        report["fixtures"] = _fixture_metadata(loaded_fixtures)

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
        print(_colour("  " + _caveat(loaded_fixtures), DIM, colour))

    # THE EXIT RULE. `summarise`'s `ok` is a pass rate and nothing else: an
    # errored case does not move it, and one red among twelve greens is 92.3%,
    # comfortably over the 90% floor. Left there, every hard replay gate would
    # be decorative -- a model mismatch, a hand-edited verdict, an unreadable
    # or orphaned fixture would each print FAIL and exit 0. So the replay leg
    # is all-must-pass on its own, and the behavioural leg stays rate-governed.
    replay_failures = [r for r in replay_results if r.error or not r.passed]
    if replay_failures:
        print(
            _colour(
                f"\n  {len(replay_failures)} recorded case(s) failed replay:", RED, colour
            )
        )
        for result in replay_failures:
            reason = result.error or "; ".join(
                f"{g.grader}: {g.detail}" for g in result.failures
            )
            print(f"    {_colour(result.case_id, RED, colour)}: {reason}")
        print(
            _colour(
                "  replay is all-must-pass: a committed fixture was known-good "
                "at record time",
                DIM,
                colour,
            )
        )

    # The vacuous-replay guard, and it is not made redundant by the rule above:
    # a fixture that is silently skipped produces no CaseResult at all, so
    # there is no red for all-must-pass to see. Zero fixtures on disk is legal
    # (nothing has been recorded yet); fixtures that should have been graded
    # and weren't is a broken selector, not a green build.
    ungraded = len(matched) - len(replay_results)
    if ungraded:
        print(
            f"error: {ungraded} of {len(matched)} committed fixture(s) were never "
            "graded -- a replay leg that skips its own input reports quality nobody "
            "measured",
            file=sys.stderr,
        )

    if args.report:
        with open(args.report, "w") as f:
            json.dump(report, f, indent=2)
        print(_colour(f"  report written to {args.report}", DIM, colour))

    return 0 if summary["ok"] and not replay_failures and not ungraded else 1


if __name__ == "__main__":
    raise SystemExit(main())
