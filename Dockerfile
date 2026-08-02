# syntax=docker/dockerfile:1
#
# Two stages so the runtime image carries no compiler and no build cache.
# It installs the [service] extra, not [dev]: the tests and the eval suite
# are CI's job, not the shipped image's.

# --------------------------------------------------------------------------
# Builder
# --------------------------------------------------------------------------
FROM python:3.14-slim AS builder

# numpy and friends publish manylinux wheels, so this is usually unused --
# but a source build on a platform without a wheel would otherwise fail the
# image build with a confusing compiler error rather than a slow one.
RUN apt-get update \
    && apt-get install --no-install-recommends -y build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copied on their own so a source-only change doesn't invalidate the layer
# that took two minutes to build.
# Copied before the source so a code change doesn't invalidate the layer that
# took two minutes to build.
COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir '.[service]'

# --------------------------------------------------------------------------
# Runtime
# --------------------------------------------------------------------------
FROM python:3.14-slim

LABEL org.opencontainers.image.title="research-agent" \
      org.opencontainers.image.description="Supervisor-routed research pipeline with fact-checked reports" \
      org.opencontainers.image.licenses="MIT"

# A fixed high UID rather than the next free one, so a mounted volume's
# ownership survives a rebuild.
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin agent

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
# Application modules only. tests/ and evals/ are excluded by .dockerignore;
# they belong in CI, and shipping them would put the eval dataset's scripted
# model output inside the production image.
# The demo page. One self-contained file, so this is the whole frontend.

# Both SQLite databases and the vector store live here. Mount a volume at
# /data or every run's memory dies with the container.
RUN mkdir -p /data && chown agent:agent /data
VOLUME ["/data"]

ENV SESSION_DB_PATH=/data/sessions.db \
    METRICS_DB_PATH=/data/metrics.db \
    VECTOR_STORE_PATH=/data/agent_memory_store.json \
    CHROMA_PATH=/data/chroma_store \
    LOG_FORMAT=json

USER agent
EXPOSE 8000

# /health deliberately never calls Claude or Voyage, so this measures whether
# *we* are up rather than whether a third party is. A liveness probe that
# fails during someone else's outage restarts a container that was fine.
# Uses urllib because the slim image has no curl and adding one to run a
# healthcheck is a whole extra package in every layer.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"

CMD ["uvicorn", "research_agent.service:app", "--host", "0.0.0.0", "--port", "8000"]
