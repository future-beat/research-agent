"""
Fixtures: recorded runs, committed to git, graded free forever after.

A fixture is one JSON file per golden case holding the *final AgentState of
every turn* of a real, paid, live run -- plus the metadata needed to say
honestly when and on what models those answers were produced. Recording is a
deliberate operator act; grading a recording is free, deterministic and
keyless, which is what lets answer quality gate every push without billing
every push.

Two properties do the load-bearing work here.

**The writer refuses a failing recording.** If any grade in the run failed --
deterministic or judge -- `write_fixture` raises rather than writing. A
fixture in this repo is therefore, by construction, a run the graders and the
judge approved, so replay asserting those verdicts still hold is a real gate
rather than a restatement of whatever was recorded. `force=True` exists for
the operator who genuinely wants a known-bad recording committed, and it
stamps `forced: true` into the file so nobody has to guess later.

**The loader refuses a malformed fixture.** A truncated, hand-edited, or
schema-drifted file raises `FixtureError` naming the offending key. The
failure mode this prevents is the expensive one: a fixture that loads as a
half-empty dict, grades vacuously green, and reports quality nobody measured.

`models` is a MAP (`{"pipeline": ..., "judge": ...}`), not a single model
string, and that is deliberate. Phase 16 makes the critic's model
configurable independently of `graph.MODEL`; with a flat string, a recording
made before that change would keep matching afterwards and go stale
invisibly. A map takes new roles (`"critic"`, any future per-node entry)
without a schema bump, and the staleness gate compares whatever roles the
graph actually exposes.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - import cycle avoidance, not behaviour
    from evals.harness import CaseResult

# Read through the module attribute rather than binding it at import time, so
# tests (and any future relocation) can point the whole layer somewhere else.
FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"

SCHEMA_VERSION = 1

# The roles every fixture must name. More may be present -- Phase 16 adds
# per-node entries -- but a fixture that cannot say which model wrote the
# answer, or which judged it, cannot be checked for staleness at all.
REQUIRED_MODEL_ROLES = ("pipeline", "judge")

_REQUIRED_KEYS: dict[str, type | tuple[type, ...]] = {
    "schema_version": int,
    "case_id": str,
    "recorded_at": str,
    "models": dict,
    "git_sha": str,
    "pipeline_cost_usd": (int, float),
    "turns": list,
}

# A research turn's state runs a few tens of KB. The warning is a nudge to
# look; the hard limit is because a megabyte-scale draft is a bug in the
# pipeline worth seeing, not a fixture worth committing.
WARN_BYTES = 100_000
MAX_BYTES = 250_000


class FixtureError(ValueError):
    """Raised on any validation failure.

    Always raised instead of returning a partial fixture: a half-loaded
    recording would grade against whatever happened to survive, which reports
    a confident wrong number.
    """


def git_sha() -> str:
    """The commit a recording was made at, or `"unknown"`.

    Metadata, never a gate -- so a recording made from a tarball, a detached
    worktree, or a machine without git still records, and simply says it does
    not know which commit it came from.
    """
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return "unknown"
    return completed.stdout.strip() or "unknown"


def build_fixture(
    case_id: str,
    result: CaseResult,
    *,
    models: dict,
    recorded_at: str | None = None,
) -> dict:
    """Turn a captured `CaseResult` into the fixture dict.

    `result` must come from `run_case(..., capture_state=True)`; a turn with
    no state is a recording that captured nothing, which is a bug worth
    raising on rather than committing an empty file.

    `models` maps role -> model name and must contain at least `"pipeline"`
    (`graph.MODEL` at record time) and `"judge"`. Extra roles are kept
    verbatim.
    """
    if not isinstance(models, dict):
        raise FixtureError(
            f"models must be a dict of role -> model name, got {type(models).__name__}"
        )
    missing = [role for role in REQUIRED_MODEL_ROLES if not models.get(role)]
    if missing:
        raise FixtureError(
            f"models is missing required role(s) {missing} for case {case_id!r} "
            f"(got {sorted(models)})"
        )

    turns = []
    for turn in result.turns:
        if turn.state is None:
            raise FixtureError(
                f"turn {turn.label!r} of case {case_id!r} captured no state -- "
                "record with run_case(..., capture_state=True)"
            )
        turns.append(
            {
                "label": turn.label,
                "state": turn.state,
                "judge": [g.as_dict() for g in turn.grades if g.judged],
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "case_id": case_id,
        # Same idiom as run_suite's `generated_at`, so report and fixture
        # timestamps are directly comparable.
        "recorded_at": recorded_at or time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "models": dict(models),
        "git_sha": git_sha(),
        "pipeline_cost_usd": round(result.cost_usd, 6),
        "turns": turns,
    }


def write_fixture(
    fixture: dict,
    result: CaseResult,
    *,
    force: bool = False,
    directory: pathlib.Path | None = None,
) -> pathlib.Path:
    """Write a fixture, refusing anything the recording itself failed.

    The refusal is the point: replay later asserts the recorded judge
    verdicts passed, and that assertion only means something if a committed
    fixture could never have been recorded red in the first place.
    """
    if not force:
        _refuse_failing(fixture.get("case_id", "?"), result)
    else:
        fixture = {**fixture, "forced": True}

    encoded = json.dumps(fixture, indent=2)  # never minified: diffs are the review surface
    size = len(encoded.encode("utf-8"))
    if size > MAX_BYTES:
        raise FixtureError(
            f"fixture for {fixture.get('case_id', '?')!r} is {size} bytes, over the "
            f"{MAX_BYTES}-byte limit -- a runaway draft is a bug worth seeing, not a "
            "recording worth committing"
        )
    if size > WARN_BYTES:
        print(
            f"warning: fixture for {fixture.get('case_id', '?')!r} is {size} bytes "
            f"(over {WARN_BYTES})",
            file=sys.stderr,
        )

    target_dir = FIXTURES_DIR if directory is None else pathlib.Path(directory)
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"{fixture['case_id']}.json"
    path.write_text(encoded + "\n")
    return path


def _refuse_failing(case_id: str, result: CaseResult) -> None:
    if result.error:
        raise FixtureError(
            f"refusing to record {case_id!r}: the run errored ({result.error}). "
            "Pass force=True to record it anyway."
        )
    failed = [g.grader for g in result.failures]
    if failed:
        raise FixtureError(
            f"refusing to record {case_id!r}: {', '.join(failed)} failed. "
            "A committed fixture is one the graders and the judge approved; "
            "pass force=True to record it anyway (it will be stamped forced)."
        )


def load_fixture(path: pathlib.Path | str) -> dict:
    """Read and validate one fixture, or raise naming what is wrong.

    Validation is deliberately total rather than best-effort. The threat is
    not a hostile file, it is a plausible one: a truncated write, a botched
    manual edit, or a schema that moved on -- each of which would otherwise
    grade green against missing data.
    """
    path = pathlib.Path(path)
    try:
        raw = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise FixtureError(f"{path}: not valid JSON ({exc})") from exc
    except OSError as exc:
        raise FixtureError(f"{path}: cannot be read ({exc})") from exc

    if not isinstance(raw, dict):
        raise FixtureError(f"{path}: expected a JSON object, got {type(raw).__name__}")

    version = raw.get("schema_version")
    if version != SCHEMA_VERSION:
        raise FixtureError(
            f"{path}: schema_version is {version!r}, this code reads {SCHEMA_VERSION} "
            "-- re-record rather than guessing at the difference"
        )

    for key, expected in _REQUIRED_KEYS.items():
        if key not in raw:
            raise FixtureError(f"{path}: missing required key {key!r}")
        if not isinstance(raw[key], expected) or isinstance(raw[key], bool):
            raise FixtureError(
                f"{path}: key {key!r} should be {_type_name(expected)}, "
                f"got {type(raw[key]).__name__}"
            )

    _validate_models(path, raw["models"])

    if not raw["turns"]:
        raise FixtureError(f"{path}: key 'turns' is empty -- a fixture with no turns "
                           "would grade vacuously green")
    for index, turn in enumerate(raw["turns"]):
        if not isinstance(turn, dict):
            raise FixtureError(f"{path}: turn {index} should be an object")
        for key, expected in (("label", str), ("state", dict), ("judge", list)):
            if key not in turn:
                raise FixtureError(f"{path}: turn {index} is missing required key {key!r}")
            if not isinstance(turn[key], expected):
                raise FixtureError(
                    f"{path}: turn {index} key {key!r} should be {expected.__name__}, "
                    f"got {type(turn[key]).__name__}"
                )

    return raw


def _validate_models(path: pathlib.Path, models: dict) -> None:
    if not models:
        raise FixtureError(f"{path}: key 'models' is empty -- a recording that cannot "
                           "name its models cannot be checked for staleness")
    for role, name in models.items():
        if not isinstance(role, str) or not isinstance(name, str):
            raise FixtureError(
                f"{path}: key 'models' must map str -> str, got {role!r} -> {name!r}"
            )
    missing = [role for role in REQUIRED_MODEL_ROLES if not models.get(role)]
    if missing:
        raise FixtureError(f"{path}: key 'models' is missing required role(s) {missing}")


def _type_name(expected: type | tuple[type, ...]) -> str:
    if isinstance(expected, tuple):
        return " or ".join(t.__name__ for t in expected)
    return expected.__name__


def fixture_paths(directory: pathlib.Path | None = None) -> list[pathlib.Path]:
    """Every recorded fixture, sorted.

    An absent directory is the pre-recording state of the repo, not an error:
    replay simply has nothing to grade yet, and says so.
    """
    target_dir = FIXTURES_DIR if directory is None else pathlib.Path(directory)
    if not target_dir.is_dir():
        return []
    return sorted(target_dir.glob("*.json"))
