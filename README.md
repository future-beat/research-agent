# Research agent

[![CI](https://github.com/future-beat/research-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/future-beat/research-agent/actions/workflows/ci.yml)

### **[▶ Live demo — research-agent.fly.dev](https://research-agent.fly.dev)**

Ask a question. It classifies the topic, searches the web, drafts a report,
then **fact-checks that draft against its own research notes** and revises
until every claim is grounded. Watch the critic push back — that's the part
worth seeing.

A production service, not a notebook: bounded loops, per-run cost accounting,
a spend cap that survives concurrency and multiple machines, per-caller
identity with owned and expiring sessions, swappable Postgres/pgvector
backends, an eval harness that grades real recorded answers, and 663 tests
that run with no API keys.

It runs on two machines against Supabase Postgres, and a stranger following
the demo link never signs up for anything.

**Stack:** Python (3.14 in CI and the image) · LangGraph · Claude Sonnet 5 · Voyage embeddings · FastAPI · SQLite/Supabase Postgres + pgvector

---

## Status

- [x] **1 — Core loop.** Supervisor pattern: classifier, researcher, writer, critic. Routing is deterministic Python over state, not a model call.
- [x] **2 — Memory.** Voyage embeddings, cosine recall with a relevance floor, persisted across runs.
- [x] **3 — Conversation & resilience.** Follow-ups over prior notes; pluggable stores; per-node retry with jittered backoff.
- [x] **4 — Service.** FastAPI, blocking and SSE, sessions that survive a restart.
- [x] **5 — Cost & observability.** Date-aware price table, spend cap as a routing rule, JSON logs, `/metrics`.
- [x] **6 — Evals.** Golden set with deterministic graders plus an LLM judge on a stronger model. Found a real bug on its first run. *(Twelve cases then; forty now — see 15.)*
- [x] **7 — Ship it.** Two-stage Dockerfile, non-root, healthchecked. CI runs lint, tests, evals, and a container smoke test.
- [x] **8 — Stateless.** Postgres and pgvector behind the existing interfaces. One contract suite proves every backend agrees.
- [x] **9 — Demo & guardrails.** Streaming demo page, rolling spend cap, per-visitor rate limit, optional token. *(Limits key on identity rather than visitor IP now — see 12.)*

**v1.1 — closing the limitations list.** Each entry below closes something the
README used to list as a known gap, or reverses a design decision on purpose.

- [x] **10 — Architectural record.** Nine numbered ADRs under `docs/adr/`, each with a status. Every later reversal supersedes a record instead of quietly contradicting prose.
- [x] **10.5 — Session endpoints closed.** The session read and delete routes were reachable by anyone; found by mapping the codebase, confirmed against production, fixed and redeployed.
- [x] **11 — Multi-machine state.** `DATABASE_URL` points at Supabase Postgres; one pooled connection set per machine; two machines serving one shared session store.
- [x] **12 — Identity, ownership, bounded stores.** An auto-issued signed cookie — no signup, no wall. Sessions and notes belong to a caller and expire after seven days; rate limits key on identity; the spend cap reserves against in-flight runs so concurrency can't overshoot it.
- [x] **13 — Embedding migration.** Two commands: copy a corpus (recall provably unchanged) or re-embed it at a new model and dimension (recall changes, and the change is measured). Cost quoted before spending.
- [x] **14 — Real cost accounting.** A negotiated discount and the `inference_geo` multiplier feed cost, applied at one choke point; Voyage embedding spend is counted for the first time; `/pricing` shows which multipliers are in effect and what the next rate window is.
- [x] **15 — Answer-quality evals.** Forty golden cases, and real recorded answers graded deterministically, keylessly, free on every push. What that can and cannot claim is written down rather than implied.

---

## Quick start

```bash
git clone https://github.com/future-beat/research-agent.git
cd research-agent
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'       # or '.[service]' to run it without the tests
cp .env.example .env          # add ANTHROPIC_API_KEY and VOYAGE_API_KEY
```

Then either the terminal REPL:

```bash
research-agent            # or: python -m research_agent.chat
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
uvicorn research_agent.service:app --port 8000   # demo at localhost:8000
```

Extras split so you install what you run: the base package is the agent
alone, `[service]` adds FastAPI and the Postgres driver and pool, `[dev]` adds
pytest, ruff and Chroma — the shared store-contract suite runs a Chroma arm, so
it has to reach CI, while a SQLite/JSON deploy installing `[service]` alone
never pulls it. A worker that imports the graph never pulls in a web server.

---

## API

| Method | Path | Does |
|---|---|---|
| `GET` | `/` | Demo page in a browser, JSON index to `curl` |
| `POST` | `/research` · `/research/stream` | Full pipeline; blocking or SSE |
| `POST` | `/sessions/{id}/ask` · `/ask/stream` | Follow-up from that session's notes — no new search |
| `GET` | `/sessions` · `/sessions/{id}` · `/{id}/trace` | Session list, thread, node-by-node trace — your own sessions; `X-Demo-Token` lists everyone's |
| `DELETE` | `/sessions/{id}` | Delete a session — the owner, or `X-Demo-Token` |
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
pytest                    # 663 tests, ~25s, no API keys, no network
python -m evals           # 40 golden cases + every recording, offline and free
python -m evals --live    # real API + LLM-judge graders (costs money)
python -m evals --record  # price a recording run; refuses to spend without --yes
```

The Claude client is stubbed and a fake embedder replaces Voyage; SQLite,
Postgres and the FastAPI app are real, because persistence and routing are
what would be worth faking least. Postgres runs in CI against a
`pgvector/pgvector` container, with a guard that fails rather than skips when
the database is missing.

Offline evals grade the **pipeline** — routing, both guardrails, follow-up
isolation, and the invariant that an unapproved draft is never returned as if
approved. The answers that leg runs against are authored in the dataset, so
nothing about answer quality can be read from it.

An offline run also replays any real answers recorded under `evals/fixtures/`
and grades those deterministically, keylessly, for free — and any red among
them fails the run outright, whatever the overall pass rate says. That is a
claim about what the pipeline said when it was recorded, not about what the
current model would say. **One case of forty is recorded** (recording is a
deliberate, paid, operator act), so a run now grades 41 cases and the caveat
prints that recording's date, model, commit and age instead of the original
line.

Recording is `python -m evals --record`, and it is the only command here that
spends money on purpose. It always prints a per-case cost preview and then
stops: `--yes` is required before an API client is even constructed. The quote
is computed at run time from the same effective-dated rate tables the service
bills against — a case already recorded is priced from its fixture's measured
cost, everything else from stated token assumptions — so it re-quotes itself
when Sonnet 5's introductory window closes on `2026-08-31` instead of going
quietly stale. It is an estimate and says so. A recording whose own graders or
judge failed is refused rather than committed, which is what lets replay treat
a fixture's verdicts as a gate rather than a restatement.

---

## Deployment

```bash
docker compose up --build
```

Runs non-root with a healthcheck; locally, mount a volume at `/data` or every
session and stored note dies with the container. In production `DATABASE_URL`
points at Supabase Postgres — one variable moves sessions, metrics and notes to
Postgres and pgvector, over a pool shared by all three — which is what lets the
service run on more than one machine.

Changing the embedding model or its dimension runs through
`python -m research_agent.migrate embeddings` — `copy` moves a corpus with its
existing vectors so recall is provably unchanged, `re-embed` puts the same texts
through a new model at a new width. Both quote a cost and require `--yes` before
spending; cutover is
`PGVECTOR_TABLE` and a restart, and rollback is pointing it back, because the
old table is never touched.

`COST_DISCOUNT_FACTOR` and `INFERENCE_GEO_MULTIPLIER` scale reported cost to
what you actually pay; `SESSIONS_TOKEN` is the operator's cross-owner view of
sessions. `/pricing` shows which are in effect.

🚀 **[Operations →](docs/OPERATIONS.md)** — Fly.io setup, the Postgres
migration, CI, the embedding-migration procedure, and the full configuration table.

---

## Limitations

Known, and deliberate for the scope.

- **Follow-ups can't reach for new information.** By design: a follow-up needing a fresh search gets "the research didn't cover that" rather than an answer.
- **The critic shares the writer's model.** Independent enough to catch ungrounded claims, not a genuinely independent evaluator. The eval judge runs on a stronger model precisely because of this.
- **Only one of forty answers is recorded.** Offline runs grade real recorded answers, but recording costs real money and only the calibration case has been run. Until the rest are recorded, the suite claims one measured answer, not a benchmark — and even then it reports what the pipeline said on a stated date and model, never what the model would say today. `--live` is the only thing that answers that. [ADR-0009](docs/adr/0009-recorded-answer-quality-evals.md) states what each grader can and cannot see.
- **Reported cost is an approximation, never the invoice.** Nothing here reads a bill. Provider token counts are telemetry — measured live, Voyage reported 25 tokens where the tokenizer counted 40, and 0 for a one-word document that embedded fine. `/pricing` shows the rate window and multipliers in effect; read it there, not from a number in a document.
- **Identities are free to mint.** Clearing browser storage gets you a fresh one with fresh limits, so per-caller limits buy fairness, not a bound on the bill. The global rolling daily spend cap is the actual backstop. Recorded as [ADR-0007](docs/adr/0007-anonymous-identity-fairness-global-cap.md).
- **The database is a single region on a free tier.** Supabase Nano in `ap-southeast-2`, no read replica, a 60-connection ceiling of which the fleet holds ten. Fine at this traffic; the first thing to look at if it isn't.
- **Notes are bounded by expiry alone.** Within one identity there's no dedup or summarisation — neither has semantics that four vector backends can agree on, and identical behaviour across them is the claim being defended.

---

## License

MIT — see [LICENSE](LICENSE).
