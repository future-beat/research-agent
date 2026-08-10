"""
Eval CLI.

    python -m evals                        offline: free, deterministic, CI-safe
    python -m evals --live                 real API + judge graders (costs money)
    python -m evals --report out.json      write the report artifact
    python -m evals --case followup-admits-a-gap --case revision-then-approval
    python -m evals --record               price the recording and refuse to spend
    python -m evals --record --yes         record fixtures for real (costs money)

`--record` implies `--live` and is the only command here that spends money on
purpose. It always prints a cost preview computed from the live rate tables,
and without `--yes` it stops there and exits 2 without ever constructing an API
client. `--force` writes a fixture whose own grades failed, stamped
`forced: true`, for the operator who wants a known-bad recording pinned.

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
    record_suite,
    replay_case,
    run_suite,
    summarise,
)
from research_agent import graph, usage  # noqa: E402

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


# --------------------------------------------------------------------------
# The record cost preview
#
# Recording is the one act in this repo that spends real money on purpose, so
# the quote an operator sees before spending it must come from the same tables
# the invoice will. Nothing here is a dollar literal: every figure is tokens
# (named constants, below) run through `usage.CallUsage.cost_usd`, which is the
# one place in the service where tokens become dollars, and which resolves the
# rate through `usage.price_for` for the day the preview runs. The Sonnet 5
# introductory window closes on 2026-08-31; the morning after, this preview
# quotes 50% more without anybody editing this file.
# --------------------------------------------------------------------------

# What one turn is ASSUMED to cost in tokens when the case has never been
# recorded. These are estimates, and they are named constants precisely so the
# one-case calibration run can correct them by editing seven numbers rather
# than an arithmetic expression. A research "turn" is every model call the
# graph makes for it -- classifier, researcher, writer, critic and any
# revision -- not one call.
#
# CALIBRATED 2026-08-10 against the first real recording (`technical-figures`,
# fixture git_sha 225b06b): 4 calls, 0 revisions, 71,333 input / 5,000 output
# tokens and 5 web searches, costing a measured $0.2427 against a quote of
# $0.1800 for the pipeline half -- a 35% UNDER-quote, hidden inside a total
# that looked conservative only because the judge assumption was generous. The
# correction rule applied here is "raise what the measurement exceeded, keep
# what it did not", so the quote stays an upper bound for the topology that was
# measured rather than becoming a point estimate fitted to a single run.
#
# What is still uncalibrated, and stated rather than implied: the FOLLOW-UP
# constants (the calibration case has no follow-ups) and both JUDGE constants
# (the judge holds its own client, so its tokens never reach a run's usage
# totals and this recording measured none of them). And the measured turn took
# the CHEAPEST path the graph has -- a case whose critic sends the draft back
# adds a writer and a critic call that no number here anticipates.
#
# One more assumption the quote makes, named here because Phase 16 falsified
# it: the whole pipeline turn is priced as a single synthetic call at
# `graph.MODEL`, so every model call in it -- classifier, researcher, writer
# and CRITIC -- is quoted at the writer's rate. Since Phase 16 the critic runs
# on `graph.critic_model()`, and production pins `CRITIC_MODEL=claude-opus-5`
# (the cutover, fly.toml [env]), which is 2.5x the writer's Sonnet rate. So
# against the deployed configuration this preview UNDER-quotes -- by the
# critic's share of the turn, not by the whole difference. A record run is made
# from an operator shell, so the size of that gap is whatever that shell sets
# CRITIC_MODEL to, which is why the correction is not a constant. Left as a
# note rather than a second `_call_cost` line: splitting the turn per node is a
# re-calibration, and the honest input for it is the deferred full record run's
# measurements, not another estimate. This is the follow-up to the 35%
# under-quote Phase 15 corrected above -- same failure mode, stated before it
# surprises anyone.
#
# Phase 17 changed the topology rather than the numbers: a follow-up whose
# notes cannot answer it now routes to the researcher, so an `expect_research`
# follow-up turn is priced with the RESEARCH constants and its web searches,
# not the follow-up ones. The follow-up constants below therefore cover only
# notes-sufficient turns from here on. Both classes remain UNMEASURED -- the
# research constants were calibrated against a research turn, not against a
# follow-up that reaches, and a reaching follow-up carries the session's
# transcript on top of what it finds, so if it is wrong it is wrong low. The
# deferred full record run is what would fix that; quoting the cheap class for
# the expensive one is the 35% lesson above, repeated knowingly, which is why
# it is corrected before any record run rather than after one.
ASSUMED_RESEARCH_INPUT_TOKENS = 72_000  # measured 71,333
ASSUMED_RESEARCH_OUTPUT_TOKENS = 8_000  # measured 5,000 -- kept, as headroom
ASSUMED_FOLLOWUP_INPUT_TOKENS = 6_000  # unmeasured
ASSUMED_FOLLOWUP_OUTPUT_TOKENS = 2_000  # unmeasured
ASSUMED_JUDGE_INPUT_TOKENS = 4_000  # unmeasured
ASSUMED_JUDGE_OUTPUT_TOKENS = 1_500  # unmeasured
WEB_SEARCHES_PER_RESEARCH_TURN = 5  # measured 5
# A follow-up turn is judged once (`harness._grade_followup` appends
# `judge_followup_honesty` and nothing else). The research turn's count is read
# off `G.JUDGE_GRADERS` rather than written down, so adding a judge grader
# re-prices the run instead of quietly making the quote too low.
JUDGE_CALLS_PER_FOLLOWUP_TURN = 1

UPPER_BOUND_NOTE = (
    "estimate — treat as an upper bound; run a one-case calibration first"
)


def _call_cost(model: str, day: datetime.date, unpriced: set[str], **tokens: int) -> float:
    """Price one assumed call, or record that this model has no price on file.

    `price_for` raises for a model the table does not list, and `EVAL_JUDGE_MODEL`
    is an env var an operator can point anywhere. A traceback instead of a quote
    would be the worst of both: no preview, and no idea why.
    """
    try:
        return usage.CallUsage(**tokens).cost_usd(model, day)
    except usage.UnknownModelPricing:
        unpriced.add(model)
        return 0.0


def _assumed_pipeline_cost(case, day: datetime.date, unpriced: set[str]) -> float:
    total = _call_cost(
        graph.MODEL,
        day,
        unpriced,
        input_tokens=ASSUMED_RESEARCH_INPUT_TOKENS,
        output_tokens=ASSUMED_RESEARCH_OUTPUT_TOKENS,
        web_search_requests=WEB_SEARCHES_PER_RESEARCH_TURN,
    )
    for followup in case.followups:
        # A follow-up that reaches for new information runs a research pass:
        # same searches, same context. Pricing it at the follow-up constants
        # would quote pennies for a turn that costs a research run.
        if followup.expect_research:
            total += _call_cost(
                graph.MODEL,
                day,
                unpriced,
                input_tokens=ASSUMED_RESEARCH_INPUT_TOKENS,
                output_tokens=ASSUMED_RESEARCH_OUTPUT_TOKENS,
                web_search_requests=WEB_SEARCHES_PER_RESEARCH_TURN,
            )
            continue
        total += _call_cost(
            graph.MODEL,
            day,
            unpriced,
            input_tokens=ASSUMED_FOLLOWUP_INPUT_TOKENS,
            output_tokens=ASSUMED_FOLLOWUP_OUTPUT_TOKENS,
        )
    return total


def _judge_calls_for(case) -> int:
    return len(G.JUDGE_GRADERS) + JUDGE_CALLS_PER_FOLLOWUP_TURN * len(case.followups)


def _assumed_judge_cost(calls: int, day: datetime.date, unpriced: set[str]) -> float:
    return calls * _call_cost(
        G.JUDGE_MODEL,
        day,
        unpriced,
        input_tokens=ASSUMED_JUDGE_INPUT_TOKENS,
        output_tokens=ASSUMED_JUDGE_OUTPUT_TOKENS,
    )


def _rate_line(model: str, day: datetime.date) -> str:
    try:
        price = usage.price_for(model, day)
    except usage.UnknownModelPricing:
        return f"{model} UNPRICED"
    return f"{model} ${price.input:g}/${price.output:g} per MTok"


def record_preview(
    cases, fixtures_by_case_id: dict, *, on: datetime.date | None = None
) -> tuple[str, float]:
    """What recording `cases` is expected to cost, and why that number.

    Two bases, and each line says which one it used. A case that has been
    recorded before is quoted from its fixture's MEASURED `pipeline_cost_usd`,
    which beats any assumption. A case that has not is quoted from the assumed
    token constants above. Judge spend is assumed either way: it never lands in
    a run's `usage` totals (the judge holds its own client), so a fixture's
    `pipeline_cost_usd` is the pipeline and nothing else -- adding the judge's
    calls back is the difference between a quote and an under-quote.

    Returns the printable text and the total, and prices nothing at zero
    silently: a model with no rate on file is named, and the closing line then
    says the total is a floor rather than an upper bound.
    """
    day = on or datetime.datetime.now(datetime.UTC).date()
    unpriced: set[str] = set()

    lines: list[tuple[str, float, str]] = []
    total = 0.0
    measured_cases = 0
    followup_turns = 0
    judge_calls = 0

    for case in cases:
        calls = _judge_calls_for(case)
        judge_calls += calls
        followup_turns += len(case.followups)
        judged = _assumed_judge_cost(calls, day, unpriced)

        fixture = fixtures_by_case_id.get(case.id)
        recorded_cost = fixture.get("pipeline_cost_usd") if fixture else None
        if isinstance(recorded_cost, (int, float)) and not isinstance(recorded_cost, bool):
            pipeline = float(recorded_cost)
            when = str(fixture.get("recorded_at") or "")[:10] or "date unknown"
            basis = f"measured pipeline ${pipeline:.4f} (fixture {when}) + assumed judge"
            measured_cases += 1
        else:
            pipeline = _assumed_pipeline_cost(case, day, unpriced)
            basis = f"assumed tokens at {day.isoformat()} rates"

        lines.append((case.id, pipeline + judged, basis))
        total += pipeline + judged

    width = max((len(case_id) for case_id, _, _ in lines), default=0)
    assumed_cases = len(lines) - measured_cases
    dominant = "measured fixture costs" if measured_cases > assumed_cases else "assumed tokens"

    text = ["cost preview"]
    text.append(
        f"  recording      {len(lines)} case(s), {followup_turns} follow-up turn(s), "
        f"{judge_calls} judge call(s)"
    )
    text.append(
        f"  rates          {_rate_line(graph.MODEL, day)} · "
        f"{_rate_line(G.JUDGE_MODEL, day)} · "
        f"web search ${usage.WEB_SEARCH_USD_PER_REQUEST:g}/request (resolved for "
        f"{day.isoformat()})"
    )
    text.append("")
    for case_id, amount, basis in lines:
        text.append(f"  {case_id.ljust(width)}  ${amount:.4f}  {basis}")
    text.append("")
    text.append(f"  total          ${total:.4f}")
    text.append(
        f"  basis          {measured_cases} measured, {assumed_cases} assumed "
        f"— {dominant} dominate this quote"
    )

    if unpriced:
        text.append(
            f"  UNPRICED       {', '.join(sorted(unpriced))} — no rate on file for "
            f"{day.isoformat()}; the total above EXCLUDES those calls and is a FLOOR, "
            "not an upper bound"
        )
    else:
        text.append(f"  {UPPER_BOUND_NOTE}")

    return "\n".join(text) + "\n", total


def _existing_fixtures() -> dict[str, dict]:
    """Recordings already on disk, keyed by case, for the measured basis.

    An unreadable fixture is not the preview's problem to solve: it falls back
    to the assumed basis for that case rather than denying the operator a quote.
    The replay leg is where a broken fixture is a red.
    """
    found: dict[str, dict] = {}
    for path in fixtures.fixture_paths():
        try:
            fixture = fixtures.load_fixture(path)
        except fixtures.FixtureError:
            continue
        found[fixture["case_id"]] = fixture
    return found


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
    parser.add_argument(
        "--record",
        action="store_true",
        help="record live runs as committed fixtures (implies --live, costs money)",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="required by --record before anything is spent",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="record a fixture even when its own grades failed (stamps forced: true)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.force and not args.record:
        # Not a warning: on its own it reads like "force the run", and the one
        # thing it forces is committing a recording the graders rejected.
        parser.error(
            "--force only means anything with --record: it commits a fixture whose "
            "own grades failed"
        )
    colour = sys.stdout.isatty()

    try:
        cases = select(args.cases)
    except KeyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    estimate = 0.0
    if args.record:
        # The preview is built BEFORE any client exists, and that order is the
        # property worth testing: a refusal that constructs the client first
        # has already read a key and is one edit away from spending. It also
        # always prints -- a preview an operator cannot rely on seeing is the
        # same as no preview.
        preview, estimate = record_preview(cases, _existing_fixtures())
        print(preview)
        if not args.yes:
            print(
                f"error: --yes is required to spend. {len(cases)} case(s) would be "
                "recorded at the estimate above; nothing was run, and no API client "
                "was built.",
                file=sys.stderr,
            )
            return 2

    judge = None
    if args.live or args.record:
        # Imported lazily so the offline path never needs an API key.
        import anthropic

        client = anthropic.Anthropic()
        judge = G.Judge(client)
        client_factory = lambda case: client  # noqa: E731 - one live client for all cases
        # Per-case InMemoryStore with real embeddings, never the persistent
        # store: Pitfall 5, and `record_suite` asserts the property rather
        # than trusting this line.
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

    def announce_recording(outcome) -> None:
        if args.quiet:
            return
        if outcome.written:
            mark = _colour("REC ", GREEN, colour)
            forced = "" if outcome.result.passed else _colour("  (forced, known-bad)", RED, colour)
            print(
                f"  {mark}  {outcome.case_id}  ${outcome.cost_usd:.4f}  "
                f"-> {outcome.path}{forced}"
            )
        else:
            print(f"  {_colour('SKIP', RED, colour)}  {outcome.case_id}  ${outcome.cost_usd:.4f}")
            print(f"        {_colour(outcome.refusal, RED, colour)}")

    mode = "record" if args.record else ("live" if args.live else "offline")
    if not args.quiet:
        print(f"{_colour('Research agent evals', BOLD, colour)}  ({mode}, {len(cases)} cases)\n")

    behavioural: list[CaseResult] = []

    def collect(result) -> None:
        behavioural.append(result)
        announce(result)

    if args.record:
        # Recording IS the suite run -- one drive of the graph per case, graded
        # and then written. Running `run_suite` as well would double the bill
        # for the same forty answers.
        report = record_suite(
            cases,
            client_factory=client_factory,
            memory_factory=memory_factory,
            judge=judge,
            force=args.force,
            min_pass_rate=args.min_pass_rate,
            on_outcome=announce_recording,
        )
    else:
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

    # THE EXIT RULE. `summarise`'s `ok` is a pass rate and nothing else: an
    # errored case does not move it, and one red among twelve greens is 92.3%,
    # comfortably over the 90% floor. Left there, every hard replay gate would
    # be decorative -- a model mismatch, a hand-edited verdict, an unreadable
    # or orphaned fixture would each print FAIL and exit 0. So the replay leg
    # is all-must-pass on its own, and the behavioural leg stays rate-governed.
    replay_failures = [r for r in replay_results if r.error or not r.passed]

    # The vacuous-replay guard, and it is not made redundant by the rule above:
    # a fixture that is silently skipped produces no CaseResult at all, so
    # there is no red for all-must-pass to see. Zero fixtures on disk is legal
    # (nothing has been recorded yet); fixtures that should have been graded
    # and weren't is a broken selector, not a green build.
    ungraded = len(matched) - len(replay_results)

    # A refused recording is the writer working, not a rate to average: forty
    # cases with one refusal is 97.5%, comfortably over any floor, and would
    # exit 0 having committed a recording set that is quietly one case short.
    recordings = report.get("recordings", [])
    refused = [r for r in recordings if not r["written"]]

    # The headline verdict is the exit code, not the pass rate. A run that
    # prints PASS at the top and exits 1 teaches people to read neither.
    ok = summary["ok"] and not replay_failures and not ungraded and not refused
    verdict = _colour("PASS", GREEN, colour) if ok else _colour("FAIL", RED, colour)
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

    if args.record:
        written = [r for r in recordings if r["written"]]
        # The calibration line. The measured figure is the PIPELINE's spend --
        # the judge holds its own client and its calls never reach a run's
        # usage totals -- so the two numbers are not the same quantity, and
        # saying which is which is the difference between calibrating the
        # preview and misreading it.
        print(
            f"  recorded {len(written)}/{len(recordings)} case(s) · "
            f"previewed ${estimate:.4f} · measured pipeline "
            f"${summary['cost_usd']:.4f} + {report['judge_calls']} judge call(s), "
            "which bill separately and are not metered here"
        )
        if refused:
            print(
                _colour(
                    f"\n  {len(refused)} case(s) were NOT recorded:", RED, colour
                )
            )
            for entry in refused:
                print(f"    {_colour(entry['case_id'], RED, colour)}: {entry['refusal']}")
            print(
                _colour(
                    "  a committed fixture is one the graders and the judge approved; "
                    "re-run those cases, or --force to pin them known-bad",
                    DIM,
                    colour,
                )
            )

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

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
