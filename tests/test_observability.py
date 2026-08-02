"""Structured logging and the optional tracing seam."""

import json
import logging

import pytest

from research_agent import observability
from research_agent.observability import JSONFormatter, configure_logging, span


def record(**extra) -> logging.LogRecord:
    rec = logging.LogRecord(
        name="graph", level=logging.INFO, pathname="x.py", lineno=1,
        msg="model call", args=(), exc_info=None,
    )
    rec.__dict__.update(extra)
    return rec


def test_formatter_emits_one_json_object():
    payload = json.loads(JSONFormatter().format(record()))
    assert payload["message"] == "model call"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "graph"
    assert "ts" in payload


def test_extra_fields_are_promoted_to_top_level():
    """The whole point: a log aggregator can filter on run_id and cost_usd
    without parsing them back out of a message string."""
    payload = json.loads(JSONFormatter().format(
        record(event="model_call", run_id="abc123", node="critic", cost_usd=0.0042)
    ))

    assert payload["event"] == "model_call"
    assert payload["run_id"] == "abc123"
    assert payload["node"] == "critic"
    assert payload["cost_usd"] == 0.0042


def test_stdlib_record_internals_stay_out_of_the_payload():
    payload = json.loads(JSONFormatter().format(record()))
    for noise in ("args", "msg", "pathname", "lineno", "levelno", "exc_info"):
        assert noise not in payload


def test_exceptions_are_serialized():
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        rec = record()
        rec.exc_info = sys.exc_info()

    payload = json.loads(JSONFormatter().format(rec))
    assert "ValueError: boom" in payload["exception"]


def test_unserializable_values_do_not_break_the_line():
    """A log call must never be the thing that fails a run."""
    payload = json.loads(JSONFormatter().format(record(obj=object())))
    assert isinstance(payload["obj"], str)


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def restore_logger():
    logger = logging.getLogger(observability.LOGGER_NAME)
    saved = list(logger.handlers), logger.level, logger.propagate
    yield
    logger.handlers, logger.level, logger.propagate = saved


def test_json_is_the_default_format(monkeypatch):
    monkeypatch.delenv("LOG_FORMAT", raising=False)
    logger = configure_logging(force=True)
    assert isinstance(logger.handlers[0].formatter, JSONFormatter)


def test_text_format_is_opt_in(monkeypatch):
    monkeypatch.setenv("LOG_FORMAT", "text")
    logger = configure_logging(force=True)
    assert not isinstance(logger.handlers[0].formatter, JSONFormatter)


def test_configuring_twice_does_not_stack_handlers():
    """Duplicated handlers mean duplicated log lines, and this module is
    imported from several places."""
    configure_logging(force=True)
    before = len(logging.getLogger(observability.LOGGER_NAME).handlers)
    configure_logging()
    configure_logging()
    assert len(logging.getLogger(observability.LOGGER_NAME).handlers) == before


def test_only_our_own_logger_is_configured(monkeypatch):
    """A library that reconfigures root logging breaks its host application."""
    root_handlers = list(logging.getLogger().handlers)
    configure_logging(force=True)
    assert logging.getLogger().handlers == root_handlers


def test_log_level_reads_the_environment(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "warning")
    assert configure_logging(force=True).level == logging.WARNING


# --------------------------------------------------------------------------
# Tracing
# --------------------------------------------------------------------------


def test_span_is_a_no_op_when_tracing_is_disabled(monkeypatch):
    monkeypatch.setenv("OTEL_ENABLED", "false")
    with span("node.critic", run_id="abc") as current:
        assert current is None


def test_span_is_a_no_op_when_opentelemetry_is_absent(monkeypatch):
    """OTel is optional -- a missing package must not be the reason a run
    fails, and the call sites stay identical either way."""
    monkeypatch.delenv("OTEL_ENABLED", raising=False)
    monkeypatch.setattr(observability, "_tracer", lambda: None)
    with span("node.writer") as current:
        assert current is None


def test_span_sets_attributes_when_a_tracer_exists(monkeypatch):
    class FakeSpan:
        def __init__(self):
            self.attributes = {}

        def set_attribute(self, key, value):
            self.attributes[key] = value

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    fake = FakeSpan()

    class FakeTracer:
        def start_as_current_span(self, name):
            fake.name = name
            return fake

    monkeypatch.setattr(observability, "_tracer", lambda: FakeTracer())

    with span("node.critic", run_id="abc", node="critic", skipped=None, obj=object()):
        pass

    assert fake.name == "node.critic"
    assert fake.attributes["run_id"] == "abc"
    assert "skipped" not in fake.attributes  # None attributes are dropped
    assert isinstance(fake.attributes["obj"], str)  # non-primitives coerced
