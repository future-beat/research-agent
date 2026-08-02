# Research-and-Report Agent System

A multi-agent research pipeline built on [LangGraph](https://langchain-ai.github.io/langgraph/) and the Claude API. Give it a question; it classifies the topic, searches the web, drafts a report, fact-checks that draft against its own research notes, and revises until the claims are grounded — with hard guardrails so it always terminates.

Then ask it follow-ups. Follow-ups answer from the notes behind the report you just got — no new search — and go through the same fact-checker the report did.

It remembers. Research notes are embedded with Voyage AI and stored behind a swappable backend, so later runs recall earlier ones and build on them instead of starting cold.

It runs as a service or as a terminal REPL, over the same graph.

**Stack:** Python 3.10+ · LangGraph · Claude Sonnet 5 · Voyage AI embeddings · FastAPI · SQLite · pytest

---

## Roadmap

Built in phases, each one shippable on its own.

**✅ Phase 1 — Core agent loop**
Supervisor pattern on LangGraph: classifier, researcher, writer, critic. Routing is deterministic Python over state, not a model call. Bounded revision and iteration caps, with `forced_stop_reason` surfaced so an unapproved draft can never pass as an approved one. Per-node inference tuning and a full execution trace.

**✅ Phase 2 — Persistent memory**
Voyage embeddings, cosine retrieval with a relevance floor, persisted across runs. Topic-type classification that drives both the researcher's strategy and the critic's rubric. Terminal REPL with streamed progress.

**✅ Phase 3 — Conversation, pluggability, resilience, tests**
Follow-up turns over the previous run's notes, reusing the critic loop. `MemoryStore`/`Embedder` seams with JSON, in-memory, and Chroma backends. Per-node retry with jittered backoff that honours `retry-after`. 95 tests running with no keys and no network.

**✅ Phase 4 — Service surface**
FastAPI over the same graph. Blocking and server-sent-event variants of every run. Sessions persisted to SQLite so follow-ups survive a restart or a different worker. Upstream failures mapped to honest status codes; `/health` that doesn't page you when a third party is down.

**✅ Phase 5 — Observability & cost control**
Per-run token and cost accounting against a date-aware price table, a spend cap that becomes another row in the routing table, structured JSON logs keyed by `run_id`, optional OpenTelemetry spans, and `/metrics` over a runs table that counts failures as well as successes.

**✅ Phase 6 — Evaluation harness**
A twelve-case golden set graded by deterministic checks over finished runs, plus LLM-as-judge grounding checks on a stronger model than the pipeline. Runs free and offline in CI, or live against the real API. JSON report artifact and a threshold exit code. It found a real bug on its first run — see below.

**✅ Phase 7 — Ship it**
Dependencies split so a worker image doesn't ship a web server. Two-stage Dockerfile on a non-root user with a healthcheck, compose file, and a Fly config with a mounted volume. GitHub Actions runs ruff, tests, the offline evals, and a container smoke test — all with no API keys.

**✅ Phase 8 — Stateless: Postgres and pgvector**
Sessions, metrics, and notes all get Postgres backends behind the interfaces that were built for exactly this. Setting `DATABASE_URL` is the entire switch. Notes move to pgvector with an HNSW index, replacing the O(n) scan. One contract suite runs against every backend so "swappable" is tested rather than asserted, with a real Postgres in CI. Plus a migration script, because a deployment that already has data shouldn't have to choose between scaling and remembering. 351 tests.

**✅ Phase 9 — Demo & guardrails** *(this phase)*
A self-contained page at `/` that streams the pipeline live — classify, search, draft, critic rejects, redraft, approve — with the cost and approval badge on the result and chained follow-ups. Plus the guardrails a public URL with live API keys needs: a rolling 24h spend cap read from the metrics table, a per-visitor rate limit, and an optional token. 364 tests.

---

## Demo

```
$ python chat.py
Research agent  --  /help for commands, /exit to quit

task> What are the current approaches to LLM agent memory?
  ... classifying topic -> technical
  ... searching the web (recalled 2 note(s) from memory)
  ... drafting report
  ... fact-checking draft -> revision requested
  ... drafting report (revision 1)
  ... fact-checking draft -> approved

=== REPORT ===

# Current Approaches to LLM Agent Memory
...

  technical topic | 7 supervisor turns | 1/2 revisions | approved

task> /ask which of those handles multi-session recall?
  ... answering from prior notes
  ... fact-checking draft -> approved

=== ANSWER ===
...

  follow-up | 4 supervisor turns | 0/2 revisions | approved
```

The `revision requested` line is the system working as designed: the critic found a claim the research notes didn't support and sent the draft back.

The follow-up skipped the classifier and the researcher entirely — it already had the notes — but not the critic.

---

## Architecture

A **supervisor pattern**. Every worker node returns to a central supervisor, which inspects state and decides what happens next. Control flow is a deterministic function of state — not an LLM's choice.

```mermaid
flowchart TD
    START([task]) --> S{supervisor}
    S --> C[classifier]
    S --> R[researcher]
    S --> W[writer]
    S --> P[responder]
    S --> K[critic]
    S --> E([END])
    C --> S
    R --> S
    W --> S
    P --> S
    K --> S

    style S fill:#4a5568,color:#fff
    style P fill:#4c51bf,color:#fff
    style E fill:#2f855a,color:#fff
```

Every worker returns to the supervisor, which re-reads state and picks the next hop. The routing table *is* `supervisor_node`, in order:

| Supervisor sees | Routes to |
|---|---|
| iteration or revision cap exceeded | END *(sets `forced_stop_reason`)* |
| run cost over budget | END *(sets `budget_exceeded`)* |
| follow-up with no prior notes | END *(sets `no_prior_research`)* |
| `topic_type` unset | classifier |
| no research notes | researcher |
| no draft | **author** |
| draft not yet reviewed | critic |
| critic returned `REVISE` | **author** *(revision)* |
| otherwise — approved | END |

**author** is the writer in research mode and the responder in follow-up mode. That substitution is the *only* thing `mode` changes — the caps, the critic hop, and the revision loop are byte-identical in both. A follow-up starts with `research_notes` and `topic_type` already populated, so the classifier and researcher rows simply never match.

| Node | Role |
|---|---|
| **supervisor** | Routes on state. Enforces iteration and revision caps. |
| **classifier** | Labels the task `technical`, `contested`, `sparse`, or `general`. Runs once. |
| **researcher** | Recalls related notes from the memory store, runs a web search, stores new findings. |
| **writer** | Drafts from research notes only. Re-drafts when the critic pushes back. |
| **responder** | Answers a follow-up from the prior run's notes and report. Never searches. |
| **critic** | Checks every claim against the notes. Returns `APPROVED` or `REVISE: <feedback>`. |

The classifier's label isn't cosmetic — it selects both the researcher's strategy and the critic's rubric:

| Topic type | Researcher does | Critic checks for |
|---|---|---|
| `technical` | Prioritize figures, versions, named sources | Numbers and dates absent from the notes |
| `contested` | Seek multiple viewpoints, note disagreement | Opinions presented as settled fact |
| `sparse` | Broaden search, flag coverage gaps | Overstated confidence where notes flagged a gap |
| `general` | Summarize well-supported facts | Any unsupported claim |

---

## Design decisions

The parts worth reading the code for.

**Routing is a state machine, not a prompt.** `supervisor_node` is plain Python — a chain of `if` statements over `AgentState`. No model call decides what runs next, so the control flow is deterministic, unit-testable, and identical on every run. The LLM does the work; the graph decides the order.

**The critic is a separate node with its own rubric.** Asking one model to draft and self-assess in a single call reliably produces "looks good to me." Splitting the draft and the grounding check into separate calls, with the critic given the research notes as the sole source of truth, catches ungrounded claims the writer introduced.

**Every loop is bounded, and stopping early is reported honestly.** `MAX_REVISIONS` caps the critic↔writer cycle; `MAX_ITERATIONS` caps total supervisor turns as a backstop against any unforeseen cycle. When a cap fires, `forced_stop_reason` propagates to the output so the user knows the report they're reading was never approved — a silent unapproved draft would be worse than no draft.

**Follow-ups reuse the critic instead of bypassing it.** The responder writes into the same `draft` field the writer does, so the critic grades a follow-up answer with the same rubric and the same revision loop — a follow-up can be sent back for revision exactly like a report. Asking a second question about a report you already have shouldn't mean re-searching the web, but it also shouldn't mean a lower standard of grounding. The responder is told that "the research didn't cover that" is a correct answer, and the critic is what makes that stick. A follow-up issued with no prior notes stops with `no_prior_research` rather than quietly answering from the model's own knowledge — the single failure mode this whole pipeline exists to prevent.

**Memory is real retrieval, not a growing prompt.** Notes are embedded with `voyage-3.5` and retrieved by cosine similarity with a relevance floor, so an unrelated past task doesn't leak into the current one. The researcher is explicitly told to prefer information not already covered, which turns memory into a coverage-expander rather than an echo.

**The store and the embedder are separate seams.** `MemoryStore` is an ABC — `add()`, `query()`, `len()`, `describe()` — with three implementations behind a `VECTOR_STORE` env var: JSON (default), in-memory, and Chroma. `Embedder` is a separate protocol, so switching stores never silently switches embedding models; that would invalidate every vector already written. Chroma keeps the same cosine ranking but adds an ANN index and stops loading the entire corpus into the agent process. A test asserts the graph never reaches past those four methods, so the seam can't rot.

**Retries happen at the node boundary, and are recorded.** A graph node is a whole unit of work, so retrying there means a transient 529 costs one repeated node rather than a failed run. `retry.py` retries only what can actually succeed on a second try — connection errors and 408/429/5xx — and raises straight through on 401 or 400, where waiting just burns wall-clock time. Backoff is exponential with equal jitter, and a server's `retry-after` wins when it asks for longer, because our curve is a guess and the header isn't. Every attempt lands in `state["trace"]`, so a slow run explains itself in `/trace` instead of looking like a stall. `sleep` and `rng` are injectable, which is why the retry tests run in milliseconds and assert exact delays.

**Nothing is constructed at import time.** Both API clients are built on first use. Eager construction would make the modules unimportable without a full set of keys — which would mean the routing table, the one genuinely deterministic part of the system, could not be tested at all. The whole suite runs with no keys and no network.

**Sessions store completed runs, not mid-run checkpoints.** A follow-up arrives as a separate request, likely on a different worker, possibly after a redeploy, so the final state of every run goes to SQLite. Deliberately *not* LangGraph's checkpointer: that solves resuming a half-finished graph, a different feature with a different failure model, and adopting it here would buy resumability nobody asked for at the price of a schema coupled to LangGraph internals. A crash mid-run loses that run and the caller retries — which is the honest behaviour when the alternative is resuming into a half-researched report.

**The spend cap is a routing rule, not a wrapper.** The iteration and revision caps bound how many model calls a run makes; they say nothing about what those calls cost, and a capped run can still be an expensive one. Because every node folds its usage into `state["usage"]` before returning, the supervisor can read the running cost on its next hop — so the budget became one more row in the same table, with the same `forced_stop_reason` machinery, rather than a separate mechanism bolted around the graph. It is checked *between* nodes because cost is only knowable after a call returns, which means a run can overshoot by at most one node rather than by an unbounded amount.

**Prices are effective-dated, because one of them expires this month.** Claude Sonnet 5 is on introductory pricing of $2/$10 per MTok through 2026-08-31 and moves to $3/$15 on September 1. A single hardcoded rate would keep reporting confident numbers that are a third too low from that morning on — the worst kind of wrong, because nothing fails. `price_for()` resolves the rate for a date, a test pins both windows, and `/pricing` exposes what accounting is using today so a step in the cost graph has a visible cause. Cache-rate constants are asserted to be the documented 1.25× and 0.1× of base input rather than trusted as typed-in numbers.

**An unpriced model is reported, not costed at zero.** If `MODEL` is changed to something with no row in the price table, tokens are still counted but `cost_usd` becomes a floor and `pricing_unknown` goes true. Silently costing those calls at zero would quietly disable the budget guardrail — a cost control that fails open without saying so is worse than none.

**Failed runs are in the metrics denominator.** A run that died opens no session, but it still burned tokens and still happened. Recording only successes would make an upstream outage look like a quiet day and would flatter every rate on the dashboard. Rates whose denominator is zero return `null` rather than `0.0`, because "no runs yet" and "nothing was approved" are different facts and a dashboard shouldn't conflate them. Latency percentiles cover completed runs only — time-to-failure is not time-to-report, and mixing them makes an outage look like a speed-up.

**One variable moves all three stores.** Sessions, metrics, and notes each default to Postgres when `DATABASE_URL` is present and to local disk when it isn't. Three separate backend flags would have been more configurable and worse: the failure you'd actually hit is setting one and forgetting another, and a deployment with sessions shared across machines but notes still split between them is broken in a way that only shows up as slowly degrading answers. Any of the three can still be pinned explicitly when you genuinely want a mixture.

**"Swappable" is a test, not a claim.** Two hand-written SQL dialects agreeing is exactly the sort of thing that quietly stops being true — SQLite sums booleans where Postgres needs `COUNT(*) FILTER`, and Postgres returns `SUM(BIGINT)` as `Decimal`, which isn't JSON-serialisable and would have 500'd `/metrics` on the first recorded run. So the behavioural tests live in one file and run against every backend, and one test asserts both metrics backends produce *byte-identical* summaries from identical input.

**pgvector replaces the scan, not just the file.** The brute-force stores score every note on every query and pull the whole corpus into the agent process — exact, O(n), and the thing the Limitations section has flagged since Phase 1. HNSW keeps the same cosine ranking and stops doing either. It's also shared, so every machine recalls everything the agent has learned rather than only what it personally wrote.

**Migration copies embeddings rather than re-embedding.** It's free and exact — but the real reason is that re-embedding would change recall behaviour at the same moment you're changing infrastructure. If recall then got worse you'd have two suspects and no way to separate them.

**The image ships what it runs, and nothing else.** `requirements.txt` is the agent alone; the web server lives in `requirements-service.txt`, so a worker or batch job that imports the graph doesn't drag in FastAPI and uvicorn. The image installs the service file, not the dev one, and `.dockerignore` keeps `tests/` and `evals/` out — the eval dataset contains scripted model output, which has no business inside a production image.

**Offline evals grade the pipeline; only `--live` grades the model.** The suite drives the real compiled graph either way, but offline it replaces the API with a scripted client whose output is authored in the dataset. That makes it free, deterministic, and safe to run on every push — and it means it cannot say anything about answer quality, because the answers are ours. What it *can* check is everything around the model: routing, both guardrails, follow-up isolation, and the invariant that an unapproved draft is never returned as if approved. The CLI prints that caveat under every offline run, because a green suite that quietly implies "the model is good" is worse than no suite.

**The judge runs on a different, stronger model than the pipeline.** The in-graph critic shares the writer's model — good enough to catch ungrounded claims, not an independent evaluator, and the README has said so since Phase 1. A judge on that same model would inherit exactly the blind spots it exists to find, so it runs on Opus 5 against Sonnet 5, and returns a structured verdict rather than a text convention: a scoring harness that mis-parses a verdict reports a confident wrong number, which is worse than crashing.

**The evals found a real bug on their first run.** `MAX_ITERATIONS` was 8 and `MAX_REVISIONS` 2, which made the revision cap **unreachable in research mode** — reaching `revision_count > 2` needs supervisor turn 10, so the iteration backstop always fired first. A run where the critic kept rejecting reported `max_iterations_exceeded`, which reads like an internal fault, instead of `max_revisions_exceeded`, which is the truth: the draft never got grounded. Both caps "worked"; they were just the wrong way round. `MAX_ITERATIONS` is now derived from `MAX_REVISIONS` so the backstop stays above the cap, and a test pins the relationship. No unit test caught this, because each cap was correct in isolation — it took running whole scenarios and asserting on *which* guardrail fired.

**Nothing a dependency does should stop the process starting.** The Postgres stores register their schema instead of executing it in `__init__`, and apply it on first use. Running DDL at construction meant an unreachable database stopped the service from *booting*, which made the degraded-dependency reporting in `/health` unreachable by definition. It's worse against a provider that pauses idle instances: the app couldn't boot, so it never connected, so nothing ever woke the database — a deadlock no restart could break. Now it comes up degraded and heals itself the moment the database answers.

**A stream that fails has to say so in-band.** By the time a node dies, the `200` and the headers are long gone. So `_stream` catches everything and emits a terminal `error` event: exactly one terminal event per stream, never both, never neither. Without it a mid-run failure is indistinguishable from a truncated connection, and the client's only options are to guess or to hang.

**Inference settings are tuned per node, not globally.** The classifier emits one word from a fixed set, so it runs with thinking disabled under a 20-token ceiling — no budget spent deliberating a four-way label. The researcher, writer, and critic do genuine reasoning and run with adaptive thinking, letting the model scale its own depth per task. Everything runs at `effort: "medium"`.

**Every run is traceable.** Each node appends to `state["trace"]`, giving a full record of routing decisions, recall counts, draft lengths, and critic verdicts. Inspect it with `/trace` in the REPL.

---

## Quickstart

```bash
git clone https://github.com/future-beat/research-agent.git
cd research-agent

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-service.txt

cp .env.example .env               # then add your two keys
```

Dependencies come in three files, so you install what you're actually running:

| File | Gets you | Contains |
|---|---|---|
| `requirements.txt` | the graph, the REPL, the evals | LangGraph, Anthropic, Voyage, numpy |
| `requirements-service.txt` | the above plus the HTTP service | + FastAPI, uvicorn |
| `requirements-dev.txt` | the above plus the test suite | + pytest, ruff |

The core file deliberately excludes the web server: a worker image or a batch job that imports the graph shouldn't ship FastAPI.

You need two separate API keys:

- **`ANTHROPIC_API_KEY`** — [console.anthropic.com](https://console.anthropic.com/settings/keys)
- **`VOYAGE_API_KEY`** — [dashboard.voyageai.com](https://dashboard.voyageai.com/) (separate account; used only for embeddings)

`chat.py` loads `.env` automatically. If you'd rather export the variables yourself, that works too.

### Verify the setup

```bash
python vector_memory.py
```

Embeds two sentences, saves them, and retrieves one by similarity. If it prints a one-element list, your Voyage key and the memory layer are working.

---

## Usage

**Interactive (recommended):**

```bash
python chat.py
```

| Command | Does |
|---|---|
| *any text* | Run the full pipeline on that question |
| `/ask <q>` | Follow up on the last run using its notes — no new web search |
| `/memory` | How many notes are stored, and in which backend |
| `/trace` | Node-by-node trace of the last run |
| `/help` | Command list |
| `/exit` | Quit (Ctrl-D also works) |

`/ask` chains: each follow-up sees the earlier ones in the thread, and all of them stay anchored to the original report and its notes. Ask a new bare question and the thread resets.

Ctrl-C during a run cancels that run and returns you to the prompt. Transient API errors are retried with backoff inside each node; anything that survives that is caught per-turn, so a rate limit doesn't end the session.

**One-shot:**

```bash
python research_agent.py
```

Runs the single hardcoded task at the bottom of the file and prints the report plus the full trace.

---

## HTTP service

```bash
uvicorn service:app --host 0.0.0.0 --port 8000
```

Interactive API docs at `/docs`, schema at `/openapi.json`.

| Method | Path | Does |
|---|---|---|
| `GET` | `/` | Demo page in a browser; the JSON index for anything else |
| `GET` | `/demo` | Current guardrail settings and remaining budget |
| `GET` | `/health` | **Liveness** — always 200 while the process runs; reports unreachable dependencies |
| `GET` | `/ready` | **Readiness** — 503 when a store can't be reached |
| `POST` | `/research` | Full pipeline; returns the finished report and opens a session |
| `POST` | `/research/stream` | Same run, streamed as SSE |
| `POST` | `/sessions/{id}/ask` | Follow-up answered from that session's notes |
| `POST` | `/sessions/{id}/ask/stream` | Same, streamed |
| `GET` | `/sessions` | Recent sessions (summaries only) |
| `GET` | `/sessions/{id}` | Latest answer and the full follow-up thread |
| `GET` | `/sessions/{id}/trace` | Node-by-node trace of the last run |
| `DELETE` | `/sessions/{id}` | Delete a session |
| `GET` | `/memory` | Note count and live backend |
| `GET` | `/metrics` | Volume, approval rate, guardrail firings, cost, latency |
| `GET` | `/pricing` | The rates cost accounting is using today |

```bash
curl -sN localhost:8000/research/stream \
  -H 'content-type: application/json' \
  -d '{"question":"What are the current approaches to LLM agent memory?"}'
```

```
event: node
data: {"node": "classifier", "topic_type": "technical"}

event: node
data: {"node": "researcher", "recalled_from_memory": 2}

event: node
data: {"node": "critic", "approved": true}

event: result
data: {"session_id": "3f2a…", "answer": "# Current Approaches…", "approved": true, …}
```

Then follow up on that `session_id`:

```bash
curl -s localhost:8000/sessions/3f2a…/ask \
  -H 'content-type: application/json' \
  -d '{"question":"Which of those handles multi-session recall?"}'
```

A run takes tens of seconds, so the blocking endpoints suit a job queue and the streaming ones suit anything with a human waiting — the same reason the REPL streams.

**Liveness is not readiness.** `/health` returns 200 whenever the process is running, and reports unreachable dependencies in the body rather than failing. `/ready` returns 503 when a store can't be reached. The distinction is load-bearing: a failing health check makes Fly restart the machine, and **a restart does not fix a database that is down** — it just turns one broken dependency into a restart loop and takes down the endpoints that still worked. Point a load balancer at `/ready`; point a restart-triggering probe at `/health`, never the reverse.

**Guardrails.** The service is reachable by anyone with the URL and every run spends real money, so the endpoints that cost money are gated three ways: an optional `DEMO_TOKEN` header, a per-visitor rate limit, and a rolling 24-hour spend cap read from the metrics table. Read-only endpoints are never gated — they cost nothing, and they're how you diagnose a service that's refusing work. The per-run cap in the supervisor bounds one runaway run; these bound the bill.

**Observability.** Every model call and every finished run emits one JSON log line keyed by `run_id`, carrying node, duration, tokens, and cost — set `LOG_FORMAT=text` for a readable terminal. `/metrics` aggregates over a runs table that records failures alongside successes. OpenTelemetry spans are emitted per node when `opentelemetry-api` is installed; without it, `span()` is a no-op and nothing else changes.

**Cost.** Each response carries `cost_usd` and a `usage` breakdown. A run that exceeds `AGENT_MAX_RUN_COST_USD` stops with `forced_stop_reason: "budget_exceeded"` — the answer you get back is whatever was finished, honestly labelled, rather than a surprise invoice.

**Status codes.** Transient upstream failures are already retried with backoff inside each node, so what reaches the caller has either failed persistently or outlived its budget. `429` means back off, `502` means upstream is unwell, `422` means the request was bad and nothing billable ran. `/health` deliberately never calls Claude or Voyage: a health check that fails when a third party does will get a perfectly healthy container killed.

---

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

364 tests, ~2s, no API keys and no network. The 27 Postgres tests skip locally unless `DATABASE_URL` is set, and run for real in CI against a `pgvector/pgvector` service container — with a guard test that **fails** rather than skips if CI's database is missing, so the build can't go green over an untested backend. The Claude client is stubbed and a fake embedder replaces Voyage; SQLite and the FastAPI app are real, because persistence and routing are exactly what would be worth faking least:

| File | Covers |
|---|---|
| `tests/test_supervisor_routing.py` | Every row of the routing table, in both modes; the caps; `route()`; and a check that no reachable decision lacks a graph edge |
| `tests/test_graph_smoke.py` | Full runs through the compiled graph — revision loops, the follow-up path, recall, guardrails |
| `tests/test_retry.py` | Which errors are retryable, backoff and jitter arithmetic, `retry-after`, budget exhaustion |
| `tests/test_memory_stores.py` | Both brute-force backends against one shared contract, persistence, the similarity floor, backend selection |
| `tests/test_sessions.py` | Session round-trips through real SQLite, turn accumulation, survival across a reopen, concurrent writes |
| `tests/test_service.py` | Every endpoint, SSE framing and in-band error events, follow-ups across a restart, upstream failure → status code, cost reporting |
| `tests/test_usage.py` | Both Sonnet 5 price windows, cache-rate multipliers, usage extraction, per-run accumulation |
| `tests/test_metrics.py` | Aggregation, rate denominators, percentile edges, concurrent writes |
| `tests/test_observability.py` | JSON log shape, handler idempotence, the tracing no-op |
| `tests/test_evals.py` | Dataset coverage, every grader's failure path, judge parsing, threshold and exit-code behaviour |
| `tests/test_limits.py` | Rate-limit window and sweep, spoofable-header handling, token, spend cap, enforcement order |
| `tests/test_store_contract.py` | One suite run against **every** backend — SQLite/Postgres sessions and metrics, JSON/in-memory/pgvector notes |
| `tests/test_deploy_config.py` | fly.toml sanity: not aimed at the database app, ports match the Dockerfile, store paths inside the mounted volume |

---

## Evals

```bash
python -m evals                                   # offline: free, no keys, CI-safe
python -m evals --live                            # real API + judge graders (costs money)
python -m evals --case followup-admits-a-gap      # one case; repeatable
python -m evals --report evals-report.json --min-pass-rate 0.9
```

```
Research agent evals  (offline, 12 cases)

  PASS  technical-figures
  PASS  contested-viewpoints
  FAIL  revision-cap-is-labelled
        forced_stop: expected 'max_revisions_exceeded', got 'max_iterations_exceeded'
        why it matters: A critic that never approves must not loop forever, and
        the draft it gives up on must be labelled unapproved.
  ...

PASS  11/12 cases (92% vs 90% required)
```

Exits non-zero below `--min-pass-rate`, so CI fails on a regression without anyone reading the output. Every case carries a `why` sentence saying what regressing it would cost — printed next to the failure, which is the moment it's worth reading.

| Grader | Kind | Checks |
|---|---|---|
| `never_silently_unapproved` | deterministic | A draft is approved, or says why it isn't. The invariant that matters most. |
| `terminates` | deterministic | The run reached the supervisor's `done` |
| `topic_type` · `approval` · `forced_stop` · `revisions` | deterministic | The run took the expected path and the expected guardrail fired |
| `answer_present` · `within_budget` · `notes_stored` | deterministic | Non-empty output, spend in range, recall still being written |
| `followup_reuses_notes` · `followup_fact_checked` | deterministic | Follow-ups skip search but not the critic |
| `judge_grounding` | judge | Every claim in the report follows from the notes |
| `judge_answers_the_question` | judge | The report addresses what was asked |
| `judge_followup_honesty` | judge | An uncovered follow-up admits the gap instead of guessing |

---

## Deployment

```bash
cp .env.example .env               # add your two keys
docker compose up --build
curl localhost:8000/health
```

The image runs as a non-root user, installs `requirements-service.txt` only, and excludes `tests/` and `evals/` — the eval dataset contains scripted model output that has no business inside a production image.

**Mount a volume at `/data`.** Both SQLite databases and the vector store live there. Without it, every follow-up thread and every stored note dies with the container, and the memory feature quietly becomes a no-op.

### Going stateless

One volume on one machine is fine for a demo, but it means downtime during host maintenance and up to 24h of data loss between snapshots. Moving the state to Postgres removes both, and it's one variable:

```bash
APP=research-agent-rippling-waterfall-9963   # the AGENT app, not the database

fly postgres create --name research-agent-db
fly postgres attach research-agent-db -a "$APP"   # sets DATABASE_URL on the agent
fly deploy -a "$APP"

fly ssh console -a "$APP" -C "python /app/migrate_to_postgres.py --dry-run"
fly ssh console -a "$APP" -C "python /app/migrate_to_postgres.py"
```

**Always pass `-a` explicitly.** `fly postgres create` makes a *separate*,
Fly-managed app; you attach to it, you never deploy into it.

**Don't merge Fly's "New files from Fly.io Launch" pull requests.** They
regenerate `fly.toml` from the web UI's defaults, and have twice broken this
deploy: once by pointing `app` at the Postgres cluster, and once by setting
`internal_port` to `8080` while the container listens on `8000`. The second is
the nastier one — it changes a line `fly.toml` hasn't touched since the branch
point, so it merges with **no conflict shown** and only surfaces as every
request failing. Copy any value you want out of such a PR by hand and close
it. `tests/test_deploy_config.py` fails the build on both cases.

Then delete the `[[mounts]]` block from `fly.toml` and `fly scale count 2`. Sessions, metrics, and notes all follow `DATABASE_URL`, so there's no second flag to forget.

The migration is re-runnable — anything already copied is skipped — and it carries notes across with their existing embeddings rather than re-embedding them. `/health` reports which backend each store is actually using, so you can confirm the switch took:

```bash
curl https://YOUR-APP.fly.dev/health
```

**Deploying to Fly.io:**

```bash
fly launch --no-deploy --copy-config
fly volumes create agent_data --size 1
fly secrets set ANTHROPIC_API_KEY=... VOYAGE_API_KEY=...
fly deploy
```

`fly.toml` pins `min_machines_running = 1` on purpose. SQLite with a single writer and a per-machine volume does not scale horizontally: a second machine would hold its own database, so a follow-up could land on a machine that has never heard of the session. Scaling out means moving sessions to Postgres and notes to Chroma first — both already sit behind interfaces, so it's a swap rather than a rewrite.

**Credentials never reach an image layer.** `.env` is in `.dockerignore`; compose passes the keys through from the environment; Fly uses `fly secrets`. `/health` reports whether each key is *present*, never its value — the clients are lazy, so a container with no keys starts up perfectly healthy and then fails every real request, and you want to learn that from the deploy rather than from the first user.

### CI

```
lint · tests · evals            ruff, tests, 12 offline eval cases
image build · smoke test        docker build, boot the container, probe it
```

Every gate runs with `ANTHROPIC_API_KEY=""`. A CI suite that needs a live key
breaks on forks, on key rotation, and during someone else's outage — and bills
you for every push. The offline eval step doubles as a guard on the lazy-client
decision: if a client ever becomes eager again, that step is what fails.

The smoke test boots the built image and probes `/health`, `/metrics`,
`/pricing`, and `/openapi.json`, then waits for Docker's own `HEALTHCHECK` to
report `healthy`. A Dockerfile that builds but whose entrypoint crashes on
startup passes a build-only check and fails in production instead.

`main` is protected: both checks must pass before a pull request can merge, and
force pushes and branch deletion are blocked. That's the setting that would have
stopped the config PR which pointed the deploy at the Postgres cluster.

Deploys are handled by Fly's GitHub integration, which deploys pushes to `main`.
Note that this is **not** gated on CI — a direct push that fails tests still
deploys, since branch protection only gates pull requests.

---

## Configuration

| Knob | Where | Default |
|---|---|---|
| `MAX_REVISIONS` | `research_agent.py` | `2` |
| `MAX_ITERATIONS` | `research_agent.py` | `8` |
| Model | `MODEL` in `research_agent.py` | `claude-sonnet-5` |
| Effort | per-node `output_config` | `medium` |
| Thinking | per-node `thinking` | `disabled` (classifier) / `adaptive` (rest) |
| `min_similarity` | `MemoryStore.query()` | `0.3` |

Set by environment variable:

| Variable | Does | Default |
|---|---|---|
| `VECTOR_STORE` | Backend: `json`, `memory`, or `chroma` | `json` |
| `VECTOR_STORE_PATH` | JSON store location | next to `vector_memory.py` |
| `CHROMA_PATH` / `CHROMA_COLLECTION` | Chroma location and collection | `chroma_store` / `research_notes` |
| `VOYAGE_EMBEDDING_MODEL` | Embedding model | `voyage-3.5` |
| `SESSION_DB_PATH` | SQLite session database | `sessions.db` beside the code |
| `AGENT_MAX_ATTEMPTS` | Attempts per node, including the first | `4` |
| `AGENT_RETRY_BASE_DELAY` | Seconds before the first retry | `1.0` |
| `AGENT_RETRY_MAX_DELAY` | Ceiling on any single backoff sleep | `30.0` |
| `AGENT_MAX_RUN_COST_USD` | Per-run spend cap; `0` disables it | `1.00` |
| `DEMO_DAILY_USD_CAP` | Rolling 24h spend ceiling across all callers; `0` disables | `5.00` |
| `DEMO_RATE_LIMIT_PER_HOUR` | Requests per visitor IP; `0` disables | `10` |
| `DEMO_TOKEN` | When set, write endpoints need an `X-Demo-Token` header | *(unset)* |
| `TRUST_FORWARDED_FOR` | Believe `X-Forwarded-For` for client IP | `false` |
| `DATABASE_URL` | Postgres DSN. **Setting it moves all three stores.** | *(unset)* |
| `SESSION_BACKEND` / `METRICS_BACKEND` | `sqlite` or `postgres` | follows `DATABASE_URL` |
| `PGVECTOR_TABLE` / `VECTOR_DIMENSIONS` | pgvector table and column width | `research_notes` / `1024` |
| `PG_CONNECT_TIMEOUT` | Seconds before a connection attempt gives up | `3` |
| `METRICS_DB_PATH` | Runs table location | same file as sessions |
| `LOG_FORMAT` / `LOG_LEVEL` | `json` or `text`; log level | `json` / `INFO` |
| `OTEL_ENABLED` | Emit OpenTelemetry spans when the package is present | `true` |

Switching backends does **not** migrate existing notes — each store owns its own data. `VECTOR_STORE=chroma` additionally needs `pip install chromadb`.

Research strategies and critic rubrics live in the `RESEARCH_STRATEGY` and `CRITIC_RUBRIC` dicts — add a topic type by adding a key to both.

---

## Project structure

```
research_agent.py       the graph: nodes, supervisor, routing, compile
vector_memory.py        Embedder + MemoryStore seams and the three backends
retry.py                retryable-error classification, backoff, node decorator
limits.py               demo token, rate limit, and rolling spend cap
static/index.html       the demo page — one self-contained file, no build step
db.py                   reconnecting Postgres connection shared by the stores
migrate_to_postgres.py  copies an existing SQLite/JSON deployment across
usage.py                effective-dated price table, cost accounting, spend cap
observability.py        JSON logging and the optional OpenTelemetry seam
metrics.py              runs table and the /metrics aggregation
sessions.py             SQLite-backed conversation sessions
service.py              FastAPI surface: blocking + SSE, sessions, ops
chat.py                 terminal REPL with streamed progress
evals/                  golden dataset, graders, runner, CLI
tests/                  pytest suite (no keys, no network)
Dockerfile              two-stage image, non-root, healthchecked
docker-compose.yml      local run with a mounted volume
fly.toml                deploy config
.github/workflows/      CI: lint, tests, evals, container smoke test
requirements.txt        core agent
requirements-service.txt  + FastAPI and uvicorn
requirements-dev.txt    + pytest and ruff
ruff.toml               lint config
.env.example            key template
```

Both stores default to paths beside the code, not the working directory, so the same data is used no matter where you launch from. In a container, point `SESSION_DB_PATH` and `VECTOR_STORE_PATH` at a mounted volume.

`service.py` is deliberately thin: it validates input, picks a state constructor, runs the graph, and persists the result. No routing logic lives there — any that did would mean the supervisor is no longer the single place deciding what runs next.

---

## Limitations

Known, and deliberate for the scope:

- **Follow-ups can't reach for new information.** By design: the responder is confined to the notes it was given, so a follow-up needing a fresh search gets "the research didn't cover that" rather than an answer. Ask it as a new question instead. A `/dig` that routes a follow-up back through the researcher would close this.
- **The default backend still scans the whole store.** `JSONMemoryStore.query()` scores every note — O(n) per call, and it rewrites the entire file on every add. Correct at hundreds of notes, the wrong shape at thousands. That's what `VECTOR_STORE=chroma` is for; the JSON store stays the default because it needs no extra dependency.
- **The critic shares the writer's model.** Independent enough to catch ungrounded claims, but not a genuinely independent evaluator.
- **The store grows without bound.** No eviction, no deduplication, no summarization.
- **REPL conversations are still per-process.** `/ask` threads in `chat.py` live in a local variable and vanish on exit. The HTTP service persists them; the REPL doesn't.
- **Retries assume nodes are safe to re-run.** They are today — each node overwrites its own fields — but a node that appended to state instead of replacing it would double-write on retry.
- **No auth, no rate limiting, no per-caller quotas.** The budget caps what a *single* run can spend; nothing caps how many runs a caller can start. Put this behind a gateway before exposing it.
- **The spend cap is per run, not per hour or per tenant.** A thousand runs at $0.99 each is a thousand dollars and no guardrail fires.
- **Offline evals cannot measure answer quality.** The model output is authored in the dataset, so a green offline run says the pipeline is intact, not that the answers are good. Only `--live` measures that, and it costs money and varies between runs.
- **The judge is one model's opinion.** `judge_grounding` is a stronger, independent check than the in-graph critic, not ground truth. Twelve cases is a smoke test, not a benchmark.
- **Cost is computed from list prices.** Enterprise discounts, batch pricing, and the `inference_geo` multiplier are not modelled, so `/metrics` is an estimate that tracks the shape of the bill, not the bill itself.
- **Sessions grow without bound and belong to nobody.** No expiry, no ownership, no pagination beyond a 50-row cap on listing. Anyone who can reach the service can read any session.
- **SQLite is still the default, and it pins you to one machine.** `fly.toml` keeps `min_machines_running = 1` for that reason. Set `DATABASE_URL` and the constraint lifts; until you do, a second machine would hold its own database and 404 on sessions that exist.
- **Postgres adds a failure mode SQLite didn't have.** The database is now a dependency the service can't start without. `/health` will report the backend but won't tell you the connection is dead until something tries to use it.
- **No connection pool.** One lock-guarded connection per machine, which is right when a run occupies a worker for tens of seconds and a query takes milliseconds — but it's a ceiling worth knowing about before raising machine concurrency much past the current `soft_limit = 8`.
- **Changing embedding model means a new pgvector table.** The column width is fixed at creation. The dimension check fails loudly rather than mysteriously, but it can't migrate for you.
- **The container image is unbuilt.** Docker isn't installed on the machine this was written on, so the Dockerfile, compose file, and CI smoke test are written but have never been run. The first `docker compose up --build` may need a fix.
- **Nothing is deployed.** `fly.toml` needs your own `app` name and region, and the deploy step is deliberately left to you — it spends money on your account.

---

## License

MIT — see [LICENSE](LICENSE).
