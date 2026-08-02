# Research agent

[![CI](https://github.com/future-beat/research-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/future-beat/research-agent/actions/workflows/ci.yml)

### **[▶ Live demo — research-agent.fly.dev](https://research-agent.fly.dev)**

Ask a question. It classifies the topic, searches the web, drafts a report,
then **fact-checks that draft against its own research notes** and revises
until every claim is grounded. Watch the critic push back — that's the part
worth seeing.

A production service, not a notebook: bounded loops, per-run cost accounting,
a spend cap, swappable Postgres/pgvector backends, an eval harness, and 364
tests that run with no API keys.

**Stack:** Python 3.10+ · LangGraph · Claude Sonnet 5 · Voyage embeddings · FastAPI · SQLite/Postgres

---

## Status

- [x] **1 — Core loop.** Supervisor pattern: classifier, researcher, writer, critic. Routing is deterministic Python over state, not a model call.
- [x] **2 — Memory.** Voyage embeddings, cosine recall with a relevance floor, persisted across runs.
- [x] **3 — Conversation & resilience.** Follow-ups over prior notes; pluggable stores; per-node retry with jittered backoff.
- [x] **4 — Service.** FastAPI, blocking and SSE, sessions that survive a restart.
- [x] **5 — Cost & observability.** Date-aware price table, spend cap as a routing rule, JSON logs, `/metrics`.
- [x] **6 — Evals.** Twelve-case golden set, deterministic graders plus an LLM judge on a stronger model. Found a real bug on its first run.
- [x] **7 — Ship it.** Two-stage Dockerfile, non-root, healthchecked. CI runs lint, tests, evals, and a container smoke test.
- [x] **8 — Stateless.** Postgres and pgvector behind the existing interfaces. One contract suite proves every backend agrees.
- [x] **9 — Demo & guardrails.** Streaming demo page, rolling spend cap, per-visitor rate limit, optional token.

---

## Quick start

```bash
git clone https://github.com/future-beat/research-agent.git
cd research-agent
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-service.txt
cp .env.example .env          # add ANTHROPIC_API_KEY and VOYAGE_API_KEY
```

Then either the terminal REPL:

```bash
python chat.py
```

```
task> What are the current approaches to LLM agent memory?
  ... classifying topic -> technical
  ... searching the web (recalled 2 note(s) from memory)
  ... drafting report
  ... fact-checking draft -> revision requested     ← the critic rejecting
  ... drafting report (revision 1)
  ... fact-checking draft -> approved

  technical topic | 7 supervisor turns | 1/2 revisions | approved | $0.14
```

…or the service:

```bash
uvicorn service:app --port 8000     # demo page at http://localhost:8000
```

Dependencies split three ways so you install what you run: `requirements.txt`
is the agent alone, `-service` adds FastAPI, `-dev` adds pytest and ruff.

---

## API

| Method | Path | Does |
|---|---|---|
| `GET` | `/` | Demo page in a browser, JSON index to `curl` |
| `POST` | `/research` · `/research/stream` | Full pipeline; blocking or SSE |
| `POST` | `/sessions/{id}/ask` · `/ask/stream` | Follow-up from that session's notes — no new search |
| `GET` | `/sessions` · `/sessions/{id}` · `/{id}/trace` | Session list, thread, node-by-node trace |
| `GET` | `/health` · `/ready` | Liveness (always 200) · readiness (503 when a store is down) |
| `GET` | `/metrics` · `/pricing` · `/demo` | Volume, approval rate, cost, latency · live rates · guardrail state |

```bash
curl -sN localhost:8000/research/stream -H 'content-type: application/json' \
  -d '{"question":"What are the current approaches to LLM agent memory?"}'
```

```
event: node
data: {"node": "classifier", "topic_type": "technical"}
event: node
data: {"node": "critic", "approved": false}
event: result
data: {"session_id": "3f2a…", "approved": true, "cost_usd": 0.14, …}
```

Interactive docs at `/docs`.

---

## Architecture

Every worker returns to a central supervisor, which re-reads state and picks
the next hop. Control flow is a deterministic function of state — never an
LLM's choice.

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

The routing table *is* `supervisor_node`, in order:

| Supervisor sees | Routes to |
|---|---|
| iteration or revision cap exceeded | END *(sets `forced_stop_reason`)* |
| run cost over budget | END *(`budget_exceeded`)* |
| follow-up with no prior notes | END *(`no_prior_research`)* |
| `topic_type` unset | classifier |
| no research notes | researcher |
| no draft | **author** |
| draft not yet reviewed | critic |
| critic returned `REVISE` | **author** *(revision)* |
| otherwise — approved | END |

**author** is the writer in research mode and the responder in follow-up mode.
That substitution is the *only* thing `mode` changes; the caps, the critic hop
and the revision loop are byte-identical in both.

The classifier's label isn't cosmetic — it selects the researcher's strategy
*and* the critic's rubric. A `technical` run gets hunted for numbers absent
from the notes; a `sparse` one gets checked for overstated confidence.

📐 **[Design decisions →](docs/DESIGN.md)** — why routing is a state machine,
why the critic is a separate node, why the spend cap is a routing rule, and 20
other calls that could have gone the other way.

---

## Tests and evals

```bash
pip install -r requirements-dev.txt
pytest                    # 364 tests, ~10s, no API keys, no network
python -m evals           # 12 golden cases, offline and free
python -m evals --live    # real API + LLM-judge graders (costs money)
```

The Claude client is stubbed and a fake embedder replaces Voyage; SQLite,
Postgres and the FastAPI app are real, because persistence and routing are
what would be worth faking least. Postgres runs in CI against a
`pgvector/pgvector` container, with a guard that fails rather than skips when
the database is missing.

Offline evals grade the **pipeline** — routing, both guardrails, follow-up
isolation, and the invariant that an unapproved draft is never returned as if
approved. They cannot grade answer quality, because the answers are authored in
the dataset; only `--live` does that. The CLI prints that caveat under every
offline run.

---

## Deployment

```bash
docker compose up --build
```

Runs non-root with a healthcheck; mount a volume at `/data` or every session
and stored note dies with the container. Setting `DATABASE_URL` moves sessions,
metrics and notes to Postgres and pgvector in one variable, and lifts the
one-machine constraint.

🚀 **[Operations →](docs/OPERATIONS.md)** — Fly.io setup, the Postgres
migration, CI, and the full configuration table.

---

## Limitations

Known, and deliberate for the scope.

- **Follow-ups can't reach for new information.** By design: a follow-up needing a fresh search gets "the research didn't cover that" rather than an answer.
- **The critic shares the writer's model.** Independent enough to catch ungrounded claims, not a genuinely independent evaluator. The eval judge runs on a stronger model precisely because of this.
- **Offline evals can't measure answer quality**, and twelve live cases are a smoke test, not a benchmark.
- **Cost is computed from list prices** — no enterprise discounts or `inference_geo` multiplier, so `/metrics` tracks the shape of the bill, not the bill.
- **Stores grow without bound.** No eviction, dedup, or summarisation for notes; no expiry or ownership for sessions. Anyone who can reach the service can read any session.
- **SQLite pins you to one machine.** `DATABASE_URL` lifts it; until then a second machine would hold its own database and 404 on sessions that exist.
- **No connection pool.** One lock-guarded Postgres connection per machine — right when a run occupies a worker for tens of seconds, but a ceiling worth knowing before raising concurrency.
- **Changing embedding model means a new pgvector table.** The column width is fixed at creation; the dimension check fails loudly but can't migrate for you.
- **The public demo is rate-limited, not authenticated.** Guardrails bound the spend; they don't identify callers.

---

## License

MIT — see [LICENSE](LICENSE).
