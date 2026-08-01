"""Run metrics: recording, aggregation, and the rate/denominator edge cases
that make a dashboard lie."""

import pytest

from metrics import COMPLETED, FAILED, MetricsStore, RunRecord, _percentile
from research_agent import initial_state


@pytest.fixture
def store(tmp_path):
    s = MetricsStore(str(tmp_path / "metrics.db"))
    yield s
    s.close()


def run(**overrides) -> RunRecord:
    base = {
        "run_id": "r1",
        "mode": "research",
        "status": COMPLETED,
        "approved": True,
        "cost_usd": 0.10,
        "duration_ms": 1000.0,
    }
    base.update(overrides)
    return RunRecord(**base)


# --------------------------------------------------------------------------
# Building a record from a finished run
# --------------------------------------------------------------------------


def test_from_state_pulls_the_run_apart():
    state = initial_state("why?")
    state.update(
        {
            "mode": "research",
            "topic_type": "technical",
            "approved": True,
            "revision_count": 1,
            "iteration": 7,
            "usage": {
                "calls": 4,
                "input_tokens": 100,
                "output_tokens": 50,
                "cache_read_input_tokens": 25,
                "cache_creation_input_tokens": 10,
                "web_search_requests": 3,
                "cost_usd": 0.42,
            },
            "trace": [
                {"node": "critic", "event": "retry", "attempt": 1},
                {"node": "critic", "approved": True},
            ],
        }
    )

    record = RunRecord.from_state(state, session_id="s1", duration_ms=1234.5)

    assert record.run_id == state["run_id"]
    assert record.session_id == "s1"
    assert record.status == COMPLETED
    assert record.topic_type == "technical"
    assert record.approved is True
    assert (record.revisions, record.iterations) == (1, 7)
    assert record.retries == 1  # only the retry entry, not the verdict entry
    assert record.calls == 4
    assert record.web_searches == 3
    assert record.cost_usd == 0.42
    assert record.duration_ms == 1234.5


def test_from_state_survives_a_run_that_never_started():
    """A run that failed in its first node has empty usage and an empty
    trace; it still has to produce a valid row."""
    record = RunRecord.from_state(initial_state("why?"))
    assert record.calls == 0
    assert record.cost_usd == 0.0
    assert record.retries == 0


# --------------------------------------------------------------------------
# Aggregation
# --------------------------------------------------------------------------


def test_empty_store_reports_zeroes_and_null_rates(store):
    """Rates are null, not zero: with no runs there is no approval rate, and
    a dashboard rendering 0% would be reporting a failure that didn't happen."""
    summary = store.summary()

    assert summary["runs"]["total"] == 0
    assert summary["runs"]["failure_rate"] is None
    assert summary["quality"]["approval_rate"] is None
    assert summary["quality"]["avg_revisions"] is None
    assert summary["cost"]["avg_usd_per_run"] is None
    assert summary["latency_ms"] == {"p50": 0.0, "p95": 0.0, "max": 0.0}


def test_counts_split_by_mode_and_status(store):
    store.record(run(mode="research"))
    store.record(run(mode="followup"))
    store.record(run(mode="research", status=FAILED, approved=False,
                     error_type="RateLimitError"))

    runs = store.summary()["runs"]
    assert runs["total"] == 3
    assert runs["completed"] == 2
    assert runs["failed"] == 1
    assert runs["research"] == 2
    assert runs["followup"] == 1
    assert runs["failure_rate"] == 0.3333  # rates are rounded to 4 dp


def test_approval_rate_is_over_completed_runs_not_all_runs(store):
    """A run that never finished was never judged by the critic. Counting it
    against the approval rate would blame the critic for an outage."""
    store.record(run(approved=True))
    store.record(run(approved=False))
    store.record(run(status=FAILED, approved=False, error_type="APIConnectionError"))

    quality = store.summary()["quality"]
    assert quality["approved"] == 1
    assert quality["approval_rate"] == 0.5  # 1 of 2 completed, not 1 of 3


def test_forced_stops_are_broken_out_by_reason(store):
    store.record(run(forced_stop_reason="max_revisions_exceeded"))
    store.record(run(forced_stop_reason="max_revisions_exceeded"))
    store.record(run(forced_stop_reason="budget_exceeded"))
    store.record(run())

    quality = store.summary()["quality"]
    assert quality["forced_stops"] == 3
    assert quality["forced_stop_reasons"] == {
        "max_revisions_exceeded": 2,
        "budget_exceeded": 1,
    }


def test_errors_are_broken_out_by_type(store):
    store.record(run(status=FAILED, error_type="RateLimitError"))
    store.record(run(status=FAILED, error_type="RateLimitError"))
    store.record(run(status=FAILED, error_type="APIConnectionError"))

    assert store.summary()["reliability"]["errors"] == {
        "RateLimitError": 2,
        "APIConnectionError": 1,
    }


def test_cost_and_tokens_are_summed(store):
    store.record(run(cost_usd=0.10, input_tokens=100, output_tokens=10, web_searches=2, calls=4))
    store.record(run(cost_usd=0.30, input_tokens=200, output_tokens=20, web_searches=1, calls=4))

    cost = store.summary()["cost"]
    assert cost["total_usd"] == pytest.approx(0.40)
    assert cost["avg_usd_per_run"] == pytest.approx(0.20)
    assert cost["input_tokens"] == 300
    assert cost["web_searches"] == 3
    assert cost["model_calls"] == 8


def test_average_cost_is_over_every_run_including_failures(store):
    """A failed run still burned tokens before it died -- excluding it would
    understate what the service actually costs to operate."""
    store.record(run(cost_usd=0.10))
    store.record(run(status=FAILED, cost_usd=0.30, error_type="RateLimitError"))

    assert store.summary()["cost"]["avg_usd_per_run"] == pytest.approx(0.20)


def test_retries_are_summed(store):
    store.record(run(retries=2))
    store.record(run(retries=3))
    assert store.summary()["reliability"]["retries"] == 5


def test_latency_percentiles_cover_completed_runs(store):
    for ms in (100, 200, 300, 400, 500, 600, 700, 800, 900, 1000):
        store.record(run(duration_ms=float(ms)))

    latency = store.summary()["latency_ms"]
    assert latency["p50"] == 500.0
    assert latency["p95"] == 1000.0
    assert latency["max"] == 1000.0


def test_failed_runs_are_excluded_from_latency(store):
    """Time-to-failure is not time-to-report; mixing them makes a fast
    outage look like a latency improvement."""
    store.record(run(duration_ms=1000.0))
    store.record(run(status=FAILED, duration_ms=1.0, error_type="RateLimitError"))

    assert store.summary()["latency_ms"]["p50"] == 1000.0


@pytest.mark.parametrize(
    "values, fraction, expected",
    [
        ([], 0.5, 0.0),
        ([42.0], 0.95, 42.0),
        ([1.0, 2.0], 0.5, 1.0),
        ([1.0, 2.0, 3.0, 4.0], 1.0, 4.0),
    ],
)
def test_percentile_edges(values, fraction, expected):
    assert _percentile(values, fraction) == expected


# --------------------------------------------------------------------------
# Storage
# --------------------------------------------------------------------------


def test_records_survive_reopening(tmp_path):
    path = str(tmp_path / "metrics.db")
    first = MetricsStore(path)
    first.record(run())
    first.close()

    reopened = MetricsStore(path)
    try:
        assert reopened.count() == 1
    finally:
        reopened.close()


def test_concurrent_writes_do_not_lose_runs(store):
    import threading

    errors = []

    def write():
        try:
            for _ in range(10):
                store.record(run())
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=write) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert store.count() == 40
