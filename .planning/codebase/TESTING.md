# Testing Patterns

**Analysis Date:** 2026-08-04

## Test Framework

**Runner:**
- pytest 9.1.1 (pinned in the `dev` extra, `pyproject.toml`)
- Config: `pyproject.toml`, `[tool.pytest.ini_options]` — there is no
  `pytest.ini`, `tox.ini`, or `setup.cfg`.

```toml
testpaths = ["tests"]
pythonpath = [".", "src", "tests"]
addopts = "-q"
```

`tests` is on `pythonpath` on purpose: test modules import each other's fakes
(`from test_graph_smoke import FakeClient`). `src` is there so the package
imports without an editable install.

**Assertion Library:**
- Plain `assert`. No `unittest`, no hamcrest, no `assertpy`.

**Mocking:**
- `monkeypatch` (pytest builtin) and hand-written fake classes. `unittest.mock`
  is not used anywhere in `tests/`.

**Run Commands:**
```bash
pytest                                  # all tests, ~18s, no API keys, no network
pytest tests/test_graph_smoke.py        # one module
pytest -k revision                      # by name
pytest -rs                              # show skip reasons
ruff check .                            # lint (same gate CI runs)

# Postgres coverage locally:
docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=pw pgvector/pgvector:pg16
DATABASE_URL=postgresql://postgres:pw@localhost:5432/postgres pytest
```

There is no coverage tool installed and no watch mode configured.

## Current Numbers (verified 2026-08-04)

Measured by running the suite in this tree:

| Environment | Result |
|-------------|--------|
| Local (no `DATABASE_URL`) | **364 passed, 28 skipped**, 1 warning, ~18s |
| CI (Postgres service + `REQUIRE_POSTGRES=1`) | **392 passed, 0 skipped** |

392 tests are collected in both cases. The 28-test delta is entirely
`tests/test_store_contract.py`:

- 27 skip with `DATABASE_URL is not set` — the Postgres/pgvector arms of the
  parametrised backend fixtures plus four `@pytest.mark.skipif` tests.
- 1 skips with `REQUIRE_POSTGRES is not set; Postgres coverage is optional here`
  — the meta-test at `tests/test_store_contract.py:441` that asserts CI is
  actually exercising Postgres rather than silently skipping it.

Offline evals: **12/12 cases pass**, `$0.7000` simulated cost, <0.1s.

Note: `README.md:160` and `docs/OPERATIONS.md:86` both say "364 tests", which
matches the local pass count but understates the 392 collected.

## Test File Organization

**Location:** separate top-level `tests/` directory, outside the package. This
is deliberate — `src/` layout keeps `tests/` and `evals/` out of the built
wheel and the production image (`docs/DESIGN.md:77`, `docs/OPERATIONS.md:176`).

**Naming:** `tests/test_<module>.py`, mirroring `src/research_agent/<module>.py`.

**Structure:**
```
tests/
├── test_deploy_config.py      126 lines   fly.toml / Dockerfile invariants
├── test_evals.py              485         the eval harness itself
├── test_graph_smoke.py        303         end-to-end compiled-graph runs
├── test_limits.py             291         rate limit + daily cost cap
├── test_memory_stores.py      210         vector memory backends
├── test_metrics.py            250         run records
├── test_observability.py      163         JSON logging + spans
├── test_retry.py              220         backoff, classification, retry-after
├── test_service.py            815         FastAPI surface (largest module)
├── test_sessions.py           162         session persistence
├── test_store_contract.py     514         one suite, every backend
├── test_supervisor_routing.py 349         routing table, no graph execution
└── test_usage.py              219         pricing and cost accounting
```

**There is no `conftest.py` anywhere in the repo.** Shared fixtures and fakes
live in the test module that owns them and are imported cross-module by name,
which is what `pythonpath = [..., "tests"]` enables:

- `FakeClient`, `Response`, `Usage`, `Block`, `ServerToolUse` are defined in
  `tests/test_graph_smoke.py:17-85` and imported by `tests/test_service.py:15`.
- `FakeEmbedder` is defined in `tests/test_memory_stores.py` and imported by
  `tests/test_graph_smoke.py:10`, `tests/test_service.py:16`, and
  `tests/test_store_contract.py:18`.

When adding a shared fake, follow this: put it in the module that primarily
tests it and import it elsewhere, rather than introducing a `conftest.py`.

## Faking the Anthropic API

No test in `tests/` makes a network call and none needs an API key. The API is
faked structurally — duck-typed classes that mirror the SDK's response shape —
and installed by monkeypatching the module-level `client()` accessor.

**The fake response tree** (`tests/test_graph_smoke.py:17-45`):

```python
class Block:
    type = "text"
    def __init__(self, text): self.text = text

class Usage:
    """Mirrors the shape of the SDK's usage object closely enough for the
    cost accounting under test -- including the None-valued cache fields the
    real API returns when nothing was cached."""
    def __init__(self, web_search_requests=0):
        self.input_tokens = 1000
        self.output_tokens = 100
        self.cache_read_input_tokens = None
        self.cache_creation_input_tokens = None
        self.server_tool_use = ServerToolUse(web_search_requests)

class Response:
    def __init__(self, text, web_search_requests=0):
        self.content = [Block(text)]
        self.usage = Usage(web_search_requests)
```

The `None`-valued cache fields matter: they reproduce what the real API returns
when nothing was cached, which is where cost accounting would otherwise crash.

**The fake client dispatches on prompt content, not on an argument**
(`tests/test_graph_smoke.py:47-85`). It exposes `.messages` as `self`, so
`client().messages.create(...)` resolves to `FakeClient.create`:

```python
class FakeClient:
    def __init__(self, critic_verdicts=("APPROVED",)):
        self.critic_verdicts = list(critic_verdicts)
        self.calls = []
        self.messages = self

    def create(self, **kwargs):
        prompt = kwargs["messages"][0]["content"]
        if "Respond with exactly one word" in prompt:   node, text = "classifier", "technical"
        elif "Search the web" in prompt:                node, text = "researcher", "FACTS: ..."
        elif "follow-up question" in prompt:            node, text = "responder", "ANSWER: ..."
        elif "Does the" in prompt:                      node = "critic"; text = self.critic_verdicts.pop(0) ...
        else:                                           node, text = "writer", "REPORT: ..."
        self.calls.append((node, prompt))
        return Response(text, web_search_requests=2 if node == "researcher" else 0)

    def nodes_called(self):
        return [node for node, _ in self.calls]
```

Two things to preserve when extending it:
- **`critic_verdicts` is a scripted queue**, consumed one per critic call, so a
  test can pass `("REVISE: ...", "APPROVED")` and watch the revision loop run.
- **`nodes_called()` is the primary routing assertion.** Tests assert on the
  exact node sequence: `assert client.nodes_called() == ["classifier",
  "researcher", "writer", "critic"]` (`tests/test_graph_smoke.py:103`).

**Installation is always via monkeypatch of the accessor, never the SDK:**

```python
monkeypatch.setattr(graph, "client", lambda: client)
```

This works because `src/research_agent/graph.py:58` builds the client lazily
behind `client()`. A change that constructs the client at import time would
break every test here — and CI's offline eval step (which runs with
`ANTHROPIC_API_KEY=""`) is the second guard against that regression.

**The embedder is faked the same way.** `FakeEmbedder` in
`tests/test_memory_stores.py` is a small fixed-vocabulary embedder;
`len(FakeEmbedder.VOCAB)` is 5, and `tests/test_store_contract.py:36` derives
the pgvector column width from it so the real Postgres table matches.

**Real `anthropic` exception types are used** rather than faked — `test_retry.py`
and `test_service.py` both `import anthropic` and construct genuine
`APIStatusError` / `APIConnectionError` instances (with `httpx` for the
response objects) so the retry classification is tested against the real class
hierarchy.

## Fixtures

All fixtures are function-scoped unless noted. Every store-owning fixture
`yield`s and then closes, and the graph fixtures reset global state on teardown.

**The factory-fixture pattern** is the dominant shape: the fixture returns a
`build(...)` callable so a test can script the critic *before* the object under
test is constructed.

`tests/test_graph_smoke.py:88`:
```python
@pytest.fixture
def fake_client(monkeypatch):
    def install(critic_verdicts=("APPROVED",)):
        client = FakeClient(critic_verdicts)
        monkeypatch.setattr(graph, "client", lambda: client)
        graph.set_memory(InMemoryStore(embedder=FakeEmbedder()))
        return client
    yield install
    graph.set_memory(None)   # don't leak a store into other tests
```

`tests/test_service.py:24` (`make_client`) is the heaviest fixture in the suite
and worth reading before adding an API test. It:
- points `SESSION_DB_PATH` / `METRICS_DB_PATH` at `tmp_path` **before** the app
  lifespan runs, so the suite does not drop a stray `sessions.db` next to the source;
- zeroes `DEMO_RATE_LIMIT_PER_HOUR` and `DEMO_DAILY_USD_CAP` and deletes
  `DEMO_TOKEN`, so a test's result never depends on how many requests earlier
  tests made, then calls `limits.reset_limiter()` on both setup and teardown;
- pins `SESSION_BACKEND=sqlite` and `METRICS_BACKEND=sqlite` so an ambient
  `DATABASE_URL` cannot redirect the API tests at Postgres;
- overrides `service.get_sessions` / `service.get_metrics` through
  `app.dependency_overrides`, and clears them on teardown;
- returns `(TestClient, fake)` and closes every client and store it created.

Only the network is faked there — persistence and graph traversal are real.

**Parametrised backend fixtures** drive the contract suite
(`tests/test_store_contract.py:48-86`): `sessions` and `runs` over
`["sqlite", "postgres"]`, `notes` over `["json", "memory", "pgvector"]`. Each
truncates its Postgres table on setup and closes on teardown.

**Autouse fixtures** reset process-global state where a module needs it:
`tests/test_limits.py:33` and `tests/test_observability.py:72`.

**Module-scoped fixtures** are used only for read-only file parsing
(`tests/test_deploy_config.py:22,29` load `fly.toml` and the `Dockerfile` once).

**`tmp_path`** is the standard for every on-disk store. No test writes to the
repo tree.

## Markers and Gating

The suite uses **no custom markers** — there is no `[tool.pytest.ini_options]
markers` list and no `-m` selection anywhere. Gating is done with `skipif` and
runtime `pytest.skip`, keyed on environment.

**Postgres gating** (`tests/test_store_contract.py`):
```python
HAS_POSTGRES = db.postgres_configured()   # bool(DATABASE_URL.strip())

def _skip_without_postgres(backend: str) -> None:
    if backend == "postgres" and not HAS_POSTGRES:
        pytest.skip("DATABASE_URL is not set")

@pytest.mark.skipif(not HAS_POSTGRES, reason="DATABASE_URL is not set")
def test_...
```

Applied at `:280`, `:409`, `:424`, `:507` as `skipif`, and via
`_skip_without_postgres` inside the parametrised fixtures for the rest.

**The skip-detector.** `tests/test_store_contract.py:441` closes the loop that
makes environment-gated skips safe:

```python
def test_postgres_is_actually_exercised_in_ci():
    """CI sets REQUIRE_POSTGRES=1. Locally it is unset and this test skips."""
    if not os.environ.get("REQUIRE_POSTGRES"):
        pytest.skip("REQUIRE_POSTGRES is not set; Postgres coverage is optional here")
    assert HAS_POSTGRES, "REQUIRE_POSTGRES is set but DATABASE_URL is empty"
```

Without it, a broken `DATABASE_URL` in CI would turn 28 tests into skips and the
build would still go green over an untested backend. Any future
environment-gated test should ship with the same kind of guard.

**Deploy-config gating** (`tests/test_deploy_config.py`) skips on absent
infrastructure rather than absent credentials: `:25` "no fly.toml", `:79` and
`:97` skip volume-related assertions when no volume is mounted. These do not
skip in CI, because `fly.toml` is committed.

**Network gating is not needed** — nothing in `tests/` reaches the network, so
there is no `--runslow` / `--integration` style flag.

## Test Types

**Unit:** `test_usage.py`, `test_retry.py`, `test_limits.py`,
`test_observability.py`, `test_metrics.py`, `test_sessions.py`. Pure functions
and single classes, no graph.

**Routing (no execution):** `test_supervisor_routing.py` asserts
`supervisor_node` picks the right `next_step` from hand-built states. Fast, and
does not need a client at all.

**Graph integration:** `test_graph_smoke.py` invokes the *compiled* `graph.app`
with the client stubbed, proving the edges exist and a run terminates. The
module docstring states the split explicitly: "The routing tests prove
supervisor_node picks the right next step; these prove the compiled graph
actually goes there."

**API integration:** `test_service.py` uses `fastapi.testclient.TestClient`
against the real `service.app`, including a hand-rolled SSE parser
(`sse_events()`, `tests/test_service.py:69`) that splits the stream on `\n\n`
and JSON-decodes `data:` lines.

**Contract:** `test_store_contract.py` — one behavioural suite run against every
backend, because "two hand-written SQL dialects agreeing is exactly the kind of
thing that quietly stops being true".

**Config/infrastructure:** `test_deploy_config.py` parses `fly.toml` and the
`Dockerfile` and asserts deployment invariants.

**Meta:** `test_evals.py` tests the eval harness itself — that a grader can
actually fail, that the summary does not round a regression away, and that a
run over zero cases does not report success.

**E2E against the live model:** not in `tests/`. That is `python -m evals --live`.

## evals/ — separate harness, different job

`evals/` is **not** part of the pytest suite (`testpaths = ["tests"]` excludes
it). It is a standalone CLI with its own dataset, graders, and runner.

```
evals/
├── __main__.py    148 lines   argparse CLI, colour output, report writing
├── dataset.py     279         12 golden cases: expectations + offline script
├── graders.py     325         deterministic graders + judge graders
└── harness.py     366         ScriptedClient, HashEmbedder, run_case/run_suite
```

**How it differs from `tests/`:**

| | `tests/` | `evals/` |
|---|---|---|
| Invocation | `pytest` | `python -m evals` |
| Unit | test function | golden *case* (a whole run) |
| Fakes | `FakeClient`, `FakeEmbedder` | `ScriptedClient`, `HashEmbedder` |
| Asserts | `assert` per behaviour | graders returning `Grade` over finished state |
| Failure mode | first assertion | pass *rate* vs `--min-pass-rate` |
| Live mode | none | `--live` hits the real API + judge |
| Output | terminal | terminal + JSON report artifact |

Both drive the **same compiled `graph.app`**, so an eval failure is a real
failure of the shipped graph, not of a parallel reimplementation.

**Invocation:**
```bash
python -m evals                                       # offline, free, deterministic
python -m evals --live                                # real API + judge (costs money)
python -m evals --case followup-admits-a-gap          # one case; repeatable flag
python -m evals --report evals-report.json            # JSON artifact
python -m evals --min-pass-rate 0.9 --quiet           # CI shape
```

Exits non-zero when the pass rate falls below `--min-pass-rate` (default 0.9),
2 on an unknown `--case` id.

**Offline mode** replaces the client with `ScriptedClient`, which replays each
case's authored output, and the embedder with `HashEmbedder` — a 64-dimension
bag-of-words hasher, present so that "offline" does not still hit Voyage on
every note the researcher stores. Like `FakeClient`, `ScriptedClient` identifies
nodes by their *prompt* rather than by an argument, deliberately: "if a node's
prompt is rewritten such that it no longer looks like itself, the eval notices
instead of silently passing" (`evals/harness.py:92`).

`evals/__main__.py:25` sets `os.environ.setdefault("LOG_LEVEL", "WARNING")`
*before* importing the agent, because the logger is configured at import time.
That import order is why `evals/__main__.py` carries a per-file `E402` ignore
in `pyproject.toml`.

**Graders come in two families** (`evals/graders.py`):
- **Deterministic** — pure functions `(case, state) -> Grade`. Free, stable,
  run on every push. Examples: `grade_terminates` (the run must end at the
  supervisor's `done`) and `grade_never_silently_unapproved` (a draft is either
  critic-approved or carries a `forced_stop_reason`), described in the source as
  "the single most important invariant in the system".
- **Judge** — a model grades whether the output is any good. `--live` only.
  `JUDGE_MODEL = os.environ.get("EVAL_JUDGE_MODEL", "claude-opus-5")`
  (`evals/graders.py:29`). The judge is deliberately a *stronger, different*
  model than the pipeline's `claude-sonnet-5`: the in-graph critic shares the
  writer's model, so a judge on that same model "would inherit exactly the blind
  spots it is supposed to find".

**Known gap — offline evals cannot measure answer quality.** The model output is
authored in `evals/dataset.py`, so offline grading covers the pipeline (routing,
both guardrails, follow-up isolation, honesty about unapproved drafts, and the
graders themselves) and says nothing about whether the model is good. The CLI
prints this caveat under every offline run:

> offline mode grades the pipeline, not the model — run with `--live` to measure answer quality

This is tracked as a known limitation (`README.md:201`, `docs/DESIGN.md:68`) and
is being addressed in a later phase. Twelve live cases are a smoke test, not a
benchmark.

The evals have already earned their keep: they found a real bug where
`MAX_ITERATIONS = 8` made the revision cap unreachable in research mode, so a
critic stuck rejecting reported `max_iterations_exceeded` instead of the true
`max_revisions_exceeded`. No unit test caught it, because each cap was correct
in isolation (`docs/DESIGN.md:72`, `src/research_agent/graph.py:39-47`).

## CI

`.github/workflows/ci.yml`. Triggers: push to `**`, pull requests, and
`workflow_dispatch`. Concurrency group per workflow+ref with
`cancel-in-progress: true`.

**Design constraint stated at the top of the file:** every gate runs without API
keys and without network access to the model providers — "a CI suite that needs
a live key is a CI suite that breaks on forks, on key rotation, and on someone
else's outage — and it bills you for every push."

**Job `test` — "lint · tests · evals"** (ubuntu-latest, Python 3.14, pip cache
keyed on `pyproject.toml`):

| Step | Command |
|------|---------|
| Install | `pip install -e '.[dev]'` |
| Lint | `ruff check .` |
| Tests | `pytest -q` |
| Evals (offline) | `python -m evals --report evals-report.json --min-pass-rate 0.9` |
| Upload artifact | `evals-report.json` (`if: always()`) |

Service container: `pgvector/pgvector:pg16` with a `pg_isready` healthcheck —
stock Postgres plus the extension, so the Postgres *and* pgvector backends run
against the real thing. Job env: `DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres`
and `REQUIRE_POSTGRES=1`, which turns a missing or broken DSN into a failure
rather than 28 silent skips.

The eval step overrides `ANTHROPIC_API_KEY=""`, `VOYAGE_API_KEY=""`, and
`DATABASE_URL=""`. The empty keys assert that the graph is importable and the
whole eval suite runnable with no credentials — the guard against a lazily
constructed client becoming eager. The empty `DATABASE_URL` stops the harness's
in-process stores inheriting the job's Postgres for no reason.

**Job `docker` — "image build · container smoke test"**: buildx build with GHA
cache, then `docker run` the image with dummy keys and poll `/health` for up to
60s. Then curls `/metrics`, `/pricing`, and `/openapi.json` — all reachable
without a working key, "because none of them call out to a model provider. If
one ever starts to, this step fails." Finally it waits for Docker's own
`HEALTHCHECK` to report healthy. Container logs are dumped and the container
removed with `if: always()`. Booting the image is the point: a Dockerfile that
builds but whose entrypoint crashes passes a build-only check and fails in
production.

**Branch protection on `main`** (verified against the GitHub API for
`future-beat/research-agent`):
- Required status checks, **strict** (branch must be up to date before merge):
  - `lint · tests · evals`
  - `image build · container smoke test`
- `allow_force_pushes: false`, `allow_deletions: false`
- `enforce_admins: false`, `required_linear_history: false`,
  `required_signatures: false`, `required_conversation_resolution: false`

Both CI jobs gate `main`. Deploys go through Fly's GitHub integration and are
not part of this workflow.

## Common Patterns

**Parametrise over inputs rather than writing near-duplicate tests:**
```python
@pytest.mark.parametrize("code", [408, 429, 500, 502, 503, 529])
def test_retryable_statuses(code): ...

@pytest.mark.parametrize("code", [400, 401, 403, 404, 422])
def test_non_retryable_statuses(code): ...
```
(`tests/test_retry.py:57,62`)

Also at `tests/test_metrics.py:200`, `tests/test_supervisor_routing.py:230`,
`tests/test_service.py:172,267,392`, `tests/test_memory_stores.py:179`, and the
backend fixtures in `tests/test_store_contract.py`.

**Build state with an overridable factory** rather than repeating a 17-key dict:
```python
def finished_state(**overrides) -> dict:
    state = { "run_id": "r1", "task": "why?", ..., "approved": True, ... }
    state.update(overrides)
    return state
```
(`tests/test_store_contract.py:88`; the same shape appears as `run_record()` at
`:110` and as `finished()` in `tests/test_evals.py:31`, which starts from the
real `initial_state()`.)

**Async:** none. There is no `pytest-asyncio` and no `async def` test.
`TestClient` drives the async FastAPI app synchronously, and the SSE endpoint is
consumed as a normal response body.

**Error testing** uses `pytest.raises` for domain errors, and for HTTP it
asserts on status plus payload:
```python
assert response.status_code == 404
assert "No session" in response.json()["detail"]
```

**Teardown is explicit.** Every fixture that constructs a store closes it, and
anything that mutates module-global state resets it — `graph.set_memory(None)`,
`limits.reset_limiter()`, `service.app.dependency_overrides.clear()`. Follow
this; the suite currently has no cross-test leakage and several fixtures carry
comments explaining the specific leak they prevent.

## Known Gaps

- **No coverage measurement.** `pytest-cov` is not installed, no threshold is
  enforced, and CI publishes no coverage report.
- **Offline evals cannot grade answer quality** (see above) — the largest
  deliberate gap, slated for a later phase.
- **Live evals are 12 cases**, described in `README.md:201` as a smoke test
  rather than a benchmark.
- **`_env_float` / `_env_int` are duplicated** between
  `src/research_agent/retry.py` and `src/research_agent/limits.py`, and are
  tested twice.
- **The "364 tests" figure in `README.md:160` and `docs/OPERATIONS.md:86`** is
  the local pass count; 392 are collected and all 392 pass in CI.

---

*Testing analysis: 2026-08-04*
