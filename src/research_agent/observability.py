"""
Structured logging and tracing.

The execution trace already tells you what happened inside one run. This tells
you what is happening across all of them: one JSON line per model call and per
completed run, keyed by `run_id`, so a slow or expensive run can be found in a
log aggregator rather than by re-reading a transcript.

    LOG_FORMAT=json   one JSON object per line (the default in a container)
    LOG_FORMAT=text   human-readable, for a terminal
    LOG_LEVEL=INFO

OpenTelemetry spans are emitted when `opentelemetry-api` is installed and
OTEL_ENABLED is not false; otherwise `span()` is a no-op context manager.
Tracing is genuinely optional -- a dependency that heavy shouldn't be the price
of running the agent locally, and the no-op keeps the call sites identical.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from contextlib import contextmanager
from typing import Any

LOGGER_NAME = "graph"

# Everything a stdlib LogRecord carries by default. Anything else on the record
# came from an `extra=` argument and is ours, so it belongs in the JSON output.
_STANDARD_RECORD_FIELDS = frozenset(
    logging.LogRecord("", 0, "", 0, "", (), None).__dict__
) | {"message", "asctime", "taskName"}


class JSONFormatter(logging.Formatter):
    """One JSON object per line, with `extra=` fields promoted to top level."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_RECORD_FIELDS and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(force: bool = False) -> logging.Logger:
    """Attach a handler to the agent's logger. Idempotent.

    Configures only our own logger, never the root: a library that reaches up
    and reconfigures root logging breaks whatever application imported it.
    """
    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers and not force:
        return logger

    for handler in list(logger.handlers):
        logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    if os.environ.get("LOG_FORMAT", "json").strip().lower() == "text":
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-5s %(message)s"))
    else:
        handler.setFormatter(JSONFormatter())

    logger.addHandler(handler)
    logger.setLevel(os.environ.get("LOG_LEVEL", "INFO").upper())
    logger.propagate = False  # the handler above is the only one that should fire
    return logger


def get_logger() -> logging.Logger:
    return configure_logging()


# --------------------------------------------------------------------------
# Tracing
# --------------------------------------------------------------------------


def _tracer():
    """The OTel tracer, or None when tracing is unavailable or switched off."""
    if os.environ.get("OTEL_ENABLED", "true").strip().lower() in ("0", "false", "no"):
        return None
    try:
        from opentelemetry import trace  # noqa: PLC0415 - optional dependency
    except ImportError:
        return None
    return trace.get_tracer(LOGGER_NAME)


@contextmanager
def span(name: str, **attributes: Any):
    """Start a span if tracing is available; otherwise do nothing at all.

    Attribute values are coerced to str when they aren't primitives, because
    OTel rejects arbitrary objects and a tracing call should never be the
    thing that fails a run.
    """
    tracer = _tracer()
    if tracer is None:
        yield None
        return

    with tracer.start_as_current_span(name) as current:
        for key, value in attributes.items():
            if value is None:
                continue
            if not isinstance(value, (str, bool, int, float)):
                value = str(value)
            current.set_attribute(key, value)
        yield current
