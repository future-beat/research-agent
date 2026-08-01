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

**✅ Phase 5 — Observability & cost control** *(this phase)*
Per-run token and cost accounting against a date-aware price table, a spend cap that becomes another row in the routing table, structured JSON logs keyed by `run_id`, optional OpenTelemetry spans, and `/metrics` over a runs table that counts failures as well as successes. 220 tests.

**⬜ Phase 6 — Evaluation harness**
A golden set of research questions. Deterministic grading of routing, guardrails, and grounding-refusal behaviour, plus an LLM-as-judge check that reports actually follow from their notes. JSON report artifact and a threshold exit code so CI can fail on a regression.

**⬜ Phase 7 — Ship it**
Dockerfile with a healthcheck, compose file for local runs, GitHub Actions running lint, tests, and a container smoke test on every push, and a deploy config with a mounted volume for the memory and session stores.

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
pip install -r requirements.txt

cp .env.example .env               # then add your two keys
```

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
| `GET` | `/health` | Liveness, memory backend, session count |
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

**Observability.** Every model call and every finished run emits one JSON log line keyed by `run_id`, carrying node, duration, tokens, and cost — set `LOG_FORMAT=text` for a readable terminal. `/metrics` aggregates over a runs table that records failures alongside successes. OpenTelemetry spans are emitted per node when `opentelemetry-api` is installed; without it, `span()` is a no-op and nothing else changes.

**Cost.** Each response carries `cost_usd` and a `usage` breakdown. A run that exceeds `AGENT_MAX_RUN_COST_USD` stops with `forced_stop_reason: "budget_exceeded"` — the answer you get back is whatever was finished, honestly labelled, rather than a surprise invoice.

**Status codes.** Transient upstream failures are already retried with backoff inside each node, so what reaches the caller has either failed persistently or outlived its budget. `429` means back off, `502` means upstream is unwell, `422` means the request was bad and nothing billable ran. `/health` deliberately never calls Claude or Voyage: a health check that fails when a third party does will get a perfectly healthy container killed.

---

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

220 tests, ~1.5s, no API keys and no network. The Claude client is stubbed and a fake embedder replaces Voyage; SQLite and the FastAPI app are real, because persistence and routing are exactly what would be worth faking least:

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
usage.py                effective-dated price table, cost accounting, spend cap
observability.py        JSON logging and the optional OpenTelemetry seam
metrics.py              runs table and the /metrics aggregation
sessions.py             SQLite-backed conversation sessions
service.py              FastAPI surface: blocking + SSE, sessions, ops
chat.py                 terminal REPL with streamed progress
tests/                  pytest suite (no keys, no network)
requirements.txt        pinned dependencies
requirements-dev.txt    + pytest
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
- **Cost is computed from list prices.** Enterprise discounts, batch pricing, and the `inference_geo` multiplier are not modelled, so `/metrics` is an estimate that tracks the shape of the bill, not the bill itself.
- **Sessions grow without bound and belong to nobody.** No expiry, no ownership, no pagination beyond a 50-row cap on listing. Anyone who can reach the service can read any session.
- **Single-writer SQLite.** One container is fine. Horizontal scaling wants Postgres for sessions and Chroma for notes — both already behind interfaces, so it's a swap rather than a rewrite.

---

## License

MIT — see [LICENSE](LICENSE).
