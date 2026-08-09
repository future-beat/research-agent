# Research agent

[![CI](https://github.com/future-beat/research-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/future-beat/research-agent/actions/workflows/ci.yml)

### **[▶ Live demo — research-agent.fly.dev](https://research-agent.fly.dev)**

Ask a question. It classifies the topic, searches the web, drafts a report,
then **fact-checks that draft against its own research notes** and revises
until every claim is grounded. Watch the critic push back — that's the part
worth seeing.

A production service, not a notebook: bounded loops, per-run cost accounting,
a spend cap, swappable Postgres/pgvector backends, an eval harness, and 615
tests that run with no API keys.

**Stack:** Python 3.10+ · LangGraph · Claude Sonnet 5 · Voyage embeddings · FastAPI · SQLite/Supabase Postgres + pgvector

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
alone, `[service]` adds FastAPI and the Postgres driver, `[dev]` adds pytest
and ruff. A worker that imports the graph never pulls in a web server.

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
pytest                    # 615 tests, ~25s, no API keys, no network
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

Runs non-root with a healthcheck; locally, mount a volume at `/data` or every
session and stored note dies with the container. In production `DATABASE_URL`
points at Supabase Postgres — one variable moves sessions, metrics and notes to
Postgres and pgvector, over a pool shared by all three — which is what lets the
service run on more than one machine.

🚀 **[Operations →](docs/OPERATIONS.md)** — Fly.io setup, the Postgres
migration, CI, and the full configuration table.

---

## Limitations

Known, and deliberate for the scope.

- **Follow-ups can't reach for new information.** By design: a follow-up needing a fresh search gets "the research didn't cover that" rather than an answer.
- **The critic shares the writer's model.** Independent enough to catch ungrounded claims, not a genuinely independent evaluator. The eval judge runs on a stronger model precisely because of this.
- **Offline evals can't measure answer quality**, and twelve live cases are a smoke test, not a benchmark.
- **Cost approximates the invoice. It is not the invoice.** What it now includes: list price scaled by two multipliers at the single point tokens become dollars — `COST_DISCOUNT_FACTOR`, a negotiated discount the API cannot report and you therefore declare, and the `inference_geo` multiplier, where `INFERENCE_GEO_MULTIPLIER` sets the *rate* but the **response's** `usage.inference_geo` decides per call whether it applies (a workspace default can put a request in a billed geo with no code change, so an env-only flag would disagree with the bill in one direction or the other). It also now includes Voyage embedding spend — around `$0.0002` of a `~$0.15` run, the point being that a whole provider is no longer missing rather than that the number moved. Those embedding dollars are computed from **Voyage-reported token counts, which are telemetry and not billing truth**: measured live, a corpus the tokenizer counted at 40 tokens was reported as 25, and a one-word document was reported as 0 while returning a perfectly good embedding. What is still **not** included: any reconciliation against the actual bill — nothing here reads an invoice; the geo multiplier on the `$10/1k` web-search fee, since the published `1.1x` is scoped to token pricing categories; Voyage's free-allowance tiers; and the 1-hour cache-write rate, which this service never uses and does not model. List prices remain effective-dated rather than fixed: Claude Sonnet 5's introductory window runs through `2026-08-31` and the standard window applies from `2026-09-01`, so any rate quoted as permanent is wrong by some date. `/pricing` reports the window accounting is using today, the one that comes next, and the multipliers in effect — read it there, not from a number in a document.
- **Notes and sessions expire after seven days, and neither is shared.** Both belong to the identity that created them; a session stops resolving seven days after its last turn, a note seven days after it was written, and the next write sweeps what has aged out. Reads deliberately don't renew that clock — otherwise "seven days since you used it" would quietly mean "seven days since you looked at it". Scoping notes is a safety fix as much as a hygiene one: recalled notes are pasted into the researcher's prompt and the critic reviews what comes back, so a communal store put one visitor's text on the path to another visitor's verdict. What remains unbounded is *within* one identity — no dedup or summarisation, because neither has semantics that four different vector backends can agree on, and the whole claim here is that they behave identically.
- **Running on SQLite pins you to one machine.** That's the local and container default: a second machine would hold its own database and 404 on sessions that exist. Production points `DATABASE_URL` at Supabase Postgres, which is what removes the constraint — the deploy config asserts the two can't drift apart in either direction.
- **The database is a single region and a free tier.** Supabase Nano in `ap-southeast-2`, no read replica, and a 60-connection ceiling of which the fleet holds ten. Fine at this traffic; the first thing to look at if it isn't.
- **The demo spend cap reserves against an estimate, not the real cost.** A starting run claims `DEMO_RESERVED_RUN_USD` ($0.20, about what a run costs) against `DEMO_DAILY_USD_CAP` and settles to the actual figure when it finishes, so in-flight runs count and concurrency can no longer overshoot — the check and the insert share one transaction holding a Postgres advisory lock, and the state is shared across machines rather than held per process. What remains: a run whose process dies keeps its reservation for 900s before it is reclaimed, and a wrong estimate makes the cap slightly early or slightly late, never absent.
- **Changing embedding model still means a new pgvector table — but there is now a path to it.** The column width is fixed at creation, so a new model or a new dimension needs a new table; what changed is that `python -m research_agent.migrate embeddings` will build one for you. Two subcommands, deliberately never one: `embeddings copy` moves a corpus with its existing vectors, so recall is provably unchanged and infrastructure is the only variable, and `embeddings re-embed` puts the same texts through a new model at a new width, where recall *may* change and — because `copy` proves the other half against a frozen golden query set — whatever changed is attributable to the model. Both carry `owner` and `created_at`, so nothing arrives belonging to nobody or with its seven-day clock restarted. `embeddings re-embed` prints a cost preview before it embeds anything and requires `--yes` to spend; an unpriced model refuses rather than quoting $0.00, and a width above 2000 refuses because pgvector's HNSW index cannot take it. The loud dimension check has not become a silent coercion: every vector goes through the store's own check on the way in. Cutover is a config change (`PGVECTOR_TABLE`, `VECTOR_DIMENSIONS`) and a restart; rollback is pointing them back, which works because the old table is never touched — no command drops it, and deleting it is a manual step ([the operator procedure](docs/OPERATIONS.md#changing-the-embedding-model-or-dimension), [ADR-0008](docs/adr/0008-embedding-migration-two-commands.md)). Read at honest scale: notes expire after seven days, so the live corpus is tiny and the point of all this is the *path*, not rescuing a large corpus. The whole path has been run once end to end against the production Supabase — scratch tables seeded with real voyage-3.5 vectors, copied, re-embedded to voyage-3.5-lite, and dropped — and it behaved as designed: the copy leg showed **zero** recall delta and the re-embed leg moved 8 of 8 golden queries, one of them changing which notes came back. What is *not* claimed: recall equality is asserted on the vectors themselves and on queries run with the index turned off, never through the approximate HNSW index; and the money is an estimate, not accounting. The preview quotes list price from an effective-dated table verified against Voyage's published rates, and it is an **upper bound** — measured live, a corpus the local tokenizer counted at 40 tokens came back reported by the API as 25, and a one-word document came back as 0, so neither figure is an invoice. Voyage embedding spend is no longer *absent* from the cost report, though: each embed call's reported token count is now captured at that seam instead of discarded, priced against the same effective-dated table, and folded into the one `cost_usd` the spend caps, `/metrics` and the API response already read. It is around $0.0002 of a ~$0.15 run — the point is that a whole provider is no longer missing, not that the number moved — and it is counted exactly as the provider reports it, 0-token anomaly and all.
- **Callers are identified, but only as an anonymous browser.** The demo is still open to anyone — the first request mints a signed `HttpOnly` cookie silently, so a stranger following a link reaches a working demo with no signup, no wall, and nothing to dismiss. What that identity is worth is exactly possession of the cookie: it's the right strength for a public demo, and it is *not* a verified person. It buys two real things — your sessions and notes are yours, and the hourly rate limit is fair between visitors instead of shared by everyone behind one NAT. It doesn't bound the bill, because identities are free to mint: clear your browser storage and you get fresh limits. That's a documented ceiling, not an oversight, which is why the **global** rolling daily spend cap survives as the actual backstop. `SESSIONS_TOKEN` remains, now as the operator's cross-owner debugging view rather than the visitor's credential. Recorded as [ADR-0007](docs/adr/0007-anonymous-identity-fairness-global-cap.md), which supersedes [ADR-0006](docs/adr/0006-separate-sessions-token-fails-closed.md).

---

## License

MIT — see [LICENSE](LICENSE).
