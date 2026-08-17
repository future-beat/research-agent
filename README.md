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
backends, an eval harness that grades real recorded answers, and 835 tests
that run with no API keys.

It runs on two machines against Supabase Postgres, and a stranger following
the demo link never signs up for anything.

**Stack:** Python (3.14 in CI and the image) · LangGraph · Claude Sonnet 5 (Opus 5 critic and classifier) · Voyage embeddings · FastAPI · SQLite/Supabase Postgres + pgvector

---

## Status

- [x] **1 — Core loop.** Supervisor pattern: classifier, researcher, writer, critic. Routing is deterministic Python over state, not a model call.
- [x] **2 — Memory.** Voyage embeddings, cosine recall with a relevance floor, persisted across runs.
- [x] **3 — Conversation & resilience.** Follow-ups over prior notes; pluggable stores; per-node retry with jittered backoff. *(A follow-up reaches for new notes when the old ones can't answer now — see 17.)*
- [x] **4 — Service.** FastAPI, blocking and SSE, sessions that survive a restart.
- [x] **5 — Cost & observability.** Date-aware price table, spend cap as a routing rule, JSON logs, `/metrics`.
- [x] **6 — Evals.** Golden set with deterministic graders plus an LLM judge on a stronger model. Found a real bug on its first run. *(Twelve cases then; forty now — see 15.)*
- [x] **7 — Ship it.** Two-stage Dockerfile, non-root, healthchecked. CI runs lint, tests, evals, and a container smoke test.
- [x] **8 — Stateless.** Postgres and pgvector behind the existing interfaces. One contract suite proves every backend agrees.
- [x] **9 — Demo & guardrails.** Streaming demo page, rolling spend cap, per-visitor rate limit, optional token. *(Limits key on identity rather than visitor IP now — see 12.)*

**v1.1 — closing the limitations list.** Each entry below closes something the
README used to list as a known gap, or reverses a design decision on purpose.

- [x] **10 — Architectural record.** Nine numbered ADRs under `docs/adr/`, each with a status. Every later reversal supersedes a record instead of quietly contradicting prose. *(Nine then; fourteen now, four of them superseded on the record — see 16 and 17.)*
- [x] **10.5 — Session endpoints closed.** The session read and delete routes were reachable by anyone; found by mapping the codebase, confirmed against production, fixed and redeployed.
- [x] **11 — Multi-machine state.** `DATABASE_URL` points at Supabase Postgres; one pooled connection set per machine; two machines serving one shared session store.
- [x] **12 — Identity, ownership, bounded stores.** An auto-issued signed cookie — no signup, no wall. Sessions and notes belong to a caller and expire after seven days; rate limits key on identity; the spend cap reserves against in-flight runs so concurrency can't overshoot it.
- [x] **13 — Embedding migration.** Two commands: copy a corpus (recall provably unchanged) or re-embed it at a new model and dimension (recall changes, and the change is measured). Cost quoted before spending.
- [x] **14 — Real cost accounting.** A negotiated discount and the `inference_geo` multiplier feed cost, applied at one choke point; Voyage embedding spend is counted for the first time; `/pricing` shows which multipliers are in effect and what the next rate window is — a field that is null for every model since Sonnet 5's introductory rate became permanent on 2026-08-12, and stays published because the next dated price is a table edit away.
- [x] **15 — Answer-quality evals.** Forty golden cases, and real recorded answers graded deterministically, keylessly, free on every push. What that can and cannot claim is written down rather than implied.
- [x] **16 — Independent critic.** `CRITIC_MODEL` gives the critic its own model, priced per node at every place a model is named, and production pins it to Opus 5 — the gate now runs on a *more capable* model than the writer it checks. The eval judge's rationale is re-derived rather than inherited, including what the choice costs in independence ([ADR-0010](docs/adr/0010-judge-rederived-for-an-independent-critic.md)).
- [x] **17 — Follow-ups reach for new information.** A follow-up whose notes can't answer no longer refuses: the responder signals the gap, and that signal routes the turn to the researcher for exactly one pass. Grounding is unchanged and was never what was being given up — an answer still comes only from notes the critic reviewed, and the window in between ships nothing at all. This closes the last of the nine limitations v1.0 listed ([ADR-0011](docs/adr/0011-followups-reach-for-new-information.md), superseding ADR-0003 — the sharpest reversal in the milestone).
- [x] **17.5 — Row level security.** Every Postgres table the service creates denies every role but its owner, enabled by the schema DDL itself rather than by hand — so a table created later, like the one an embedding migration builds, is covered the moment it exists. Found by a provider's security linter rather than by the plan, which is the second time a live exposure arrived from outside the roadmap (see 10.5). Live on Fly release v13.

**v1.2 — nothing uncovered.** v1.1 closed all nine of v1.0's limitations but left
seven behind it. This milestone closes four of those without successors, records
the three that cannot close honestly, and — because one phase spent real money on
real answers — finds three things no free test could see.

- [x] **18 — Independent eval judge.** The judge moves off the critic's model to `claude-opus-4-8`: not the critic's, stronger than the writer it grades, and no cost change. Its response handling now checks `stop_reason` before reading content, because a safety-classifier refusal used to surface as a misleading parse error ([ADR-0012](docs/adr/0012-judge-independent-of-the-critic.md), superseding ADR-0010 and deliberately reopening the reversal register v1.1 had closed as spent).
- [x] **19 — Credential validity, log addressability, demo CSP.** `/health` reports whether the keys actually *work* beside whether they are present, from a cached probe the endpoint never waits on — so a provider outage still cannot restart a healthy container. `run_finished` carries `session_id`, and the demo page ships a hash-based CSP derived from the page itself, so the header cannot disagree with what it protects. The phase found that a failed *streaming* run had been logging nothing at all — every failed demo run, invisible.
- [x] **20 — Note count bound.** Notes gain a second bound beside expiry: a per-owner cap with oldest-first eviction, identical across all four backends. Tie-breaking is the hard part — `time.time()` was measured giving 14 unique values per 200 calls — so each backend uses a storage-native secondary key. Found, by mutation, that the shared contract suite is *structurally blind* to one chroma regression; a dedicated gate covers what the suite cannot.
- [x] **21 — Forty recorded answers.** The paid record run, five operator-approved stages, $9.90 against a $17.48 quote. It measured the requirement's own two halves pulling against each other — record all forty, but commit only what the graders and judge approve — so every case is now either recorded or carries a documented refusal in [`evals/REFUSALS.json`](evals/REFUSALS.json), a union a test holds total. Nothing was forced to reach forty.
- [x] **21.5 — Classifier on its own model.** The record run exposed the classifier mislabelling a whole stratum; a probe scored Opus 5 at 37/38 against Sonnet 5's 32/38, five fixes and no regressions, for about +0.2% a run. Fixed rather than recorded, and the switch was gated on repeating the measurement before trusting it ([ADR-0013](docs/adr/0013-classifier-on-its-own-model.md)). Live on Fly release v21.
- [x] **22 — Limitations recorded.** This section, rebuilt: the four closed bullets deleted rather than reworded into it, the three survivors each ending at the record that argues them, and the defects the paid run found written down with their evidence instead of quietly carried.
- [x] **22.5 — The demo shows progress.** The demo looked frozen: the page could only draw a stage when one *finished*, so it asserted "classifying the topic" for the two minutes the researcher spends searching. One reproduction measured it — classifier at +2s, researcher at +122s, a clean terminal result at +183s, the run recorded and billed — so nothing was broken except what a visitor could see. The supervisor already announces what it is routing to, and the stream was discarding it as noise; forwarding it moves "searching the web" from +122s to ~+2s. Found by a user, not by a gate.

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
| `POST` | `/sessions/{id}/ask` · `/ask/stream` | Follow-up from that session's notes; one fresh search when they can't answer |
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
data: {"node": "classifier", "status": "started"}
event: node
data: {"node": "classifier", "topic_type": "technical"}
event: node
data: {"node": "critic", "approved": false}
event: result
data: {"session_id": "3f2a…", "approved": true, "cost_usd": 0.14, …}
```

A `node` event carrying `status` announces a stage *beginning*; the same event
without it reports that stage *finishing*, with its detail. The supervisor's
own hops never reach the wire — what a started event names is the node about to
run — and the terminal routing that ends the run is not announced at all.

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
| follow-up with no prior notes | researcher *(traced `no_prior_research`)* |
| follow-up whose notes don't cover it, one pass unspent | researcher *(traced `notes_insufficient`)* |
| `topic_type` unset | classifier |
| no research notes | researcher |
| no draft | **author** |
| draft not yet reviewed | critic |
| critic returned `REVISE` | **author** *(revision)* |
| otherwise — approved | END |

**author** is the writer in research mode and the responder in follow-up mode.
That substitution and the two follow-up rows are all `mode` changes; the caps,
the critic hop and the revision loop are byte-identical in both. Those two rows
sit *below* the caps and *above* the classifier deliberately: a capped or
over-budget follow-up still ENDs with its own reason and never researches, and
a follow-up never classifies a topic it already inherited. `no_prior_research`
names a row that reaches, recorded on the supervisor's trace entry — it is not
a stop reason.

Those two rows are worth spelling out, because they replace something this
README used to list as a limitation. A follow-up whose notes can't answer the
question neither guesses nor gives up: the responder signals the gap, that
signal *routes* instead of shipping, and no text reaches the caller until the
researcher has gathered and the critic has reviewed. Grounding never meant "no
new search" — it meant the answer comes only from notes the critic checked, and
that is untouched. One pass per turn, deliberately: if the answer still isn't
in the notes after looking, "the research didn't cover that" is the answer, and
the trace shows the attempt. Recorded as
[ADR-0011](docs/adr/0011-followups-reach-for-new-information.md).

The classifier's label isn't cosmetic — it selects the researcher's strategy
*and* the critic's rubric. A `technical` run gets hunted for numbers absent
from the notes; a `sparse` one gets checked for overstated confidence.

📐 **[Design decisions →](docs/DESIGN.md)** — why routing is a state machine,
why the critic is a separate node, why the spend cap is a routing rule, and 20
other calls that could have gone the other way.

---

## Tests and evals

```bash
pytest                    # 835 tests, ~30s, no API keys, no network
python -m evals           # 40 golden cases + every recording, offline and free
python -m evals --live    # real API + LLM-judge graders (costs money)
python -m evals --record  # price a recording run; refuses to spend without --yes
```

The Claude client is stubbed and a fake embedder replaces Voyage; SQLite,
Postgres and the FastAPI app are real, because persistence and routing are
what would be worth faking least. Postgres runs in CI against a
`pgvector/pgvector` container, with a guard that fails rather than skips when
the database is missing.

Offline evals grade the **pipeline** — routing, both guardrails, the one-pass
bound on a follow-up that reaches for new notes, and the invariant that an
unapproved draft is never returned as if approved. The answers that leg runs against are authored in the dataset, so
nothing about answer quality can be read from it.

An offline run also replays any real answers recorded under `evals/fixtures/`
and grades those deterministically, keylessly, for free — and any red among
them fails the run outright, whatever the overall pass rate says. That is a
claim about what the pipeline said when it was recorded, not about what the
current model would say. **Twenty-five cases of forty are recorded** (recording is a
deliberate, paid, operator act), so a run now grades 65 cases and the caveat
prints those recordings' date, model, commit and age instead of the original
line.

The other fifteen are in [`evals/REFUSALS.json`](evals/REFUSALS.json), each
with the reason it was not recorded, because a committed fixture is one the
graders and the judge approved and buying the number forty by forcing them
would discard exactly the property that makes a fixture worth grading. A test
holds the union total, so a case cannot quietly leave both sets — and a second
test derives every number in this section from that file and from
`evals/fixtures/`, so none of them can go stale while still sounding confident.

The fifteen split three ways, and the split is the point. **Seven are the
machinery working** — a grader or the judge declined a recording, which is what
they are for; two of those entries were rewritten when the Opus 5 classifier
removed their original reason, rather than left carrying a cause that no longer
applies. The other eight are two defects a paid run found, and **neither is
fixed here**.

**Two are a real defect.** The judge's verdict truncates against a
`max_tokens=1500` budget it shares with adaptive thinking, so a long
deliberation cuts the JSON off mid-object. `Judge.verdict`'s own docstring in
`evals/graders.py` predicted this before any run had hit it, which is why it
surfaces by name as truncation rather than as a malformed verdict — the failure
is labelled correctly and still costs the recording. Raising or splitting that
budget is a change to the judge, and
[ADR-0012](docs/adr/0012-judge-independent-of-the-critic.md) is where the judge's
configuration is decided; it does not move in a phase that is not about the
judge. Successor-milestone work, deliberately.

**Six are recordings that passed at record time and then failed replay**, which
is its own finding about the two grading paths disagreeing. Five are contested-topic
cases whose pins require the words *proponents* and *critics*; the recordings
argue both sides at length in different words. The pins cannot simply be
re-authored, and that was tried: the same `must_mention` must also hold against
the case's hand-authored reference report in `dataset.py`, which is written in
that vocabulary, so any replacement collapses to a word testing less than the pin
it replaced. The sixth is a follow-up that admitted no source covered a forecast
and then supplied a reasoned estimate anyway — the hedged half-answer the
recorded-refusal grader's own docstring says it cannot catch. That record-time
grading approved it at all is the finding; widening the patterns to keep it would
teach the suite to accept the failure the pipeline exists to prevent.

Neither defect is a limitation this project chose. They are things a paid run
found that free testing structurally could not see, written down with their
per-case evidence rather than averaged into a pass rate.

Recording is `python -m evals --record`, and it is the only command here that
spends money on purpose. It always prints a per-case cost preview and then
stops: `--yes` is required before an API client is even constructed. The quote
is computed at run time from the same effective-dated rate tables the service
bills against — a case already recorded is priced from its fixture's measured
cost, everything else from stated token assumptions — so it re-quotes itself
from the table instead of going quietly stale. It is an estimate and says so. A recording whose own graders or
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

Every table the service creates in Postgres enables row level security as part
of its own schema, so a `public` schema exposed over a provider's HTTP API
returns nothing rather than everything. **No policies, deliberately** — RLS
exempts a table's owner, which is the `DATABASE_URL` role because it ran the
DDL, so the service is unaffected and everything else is denied. A linter will
suggest adding one; adding a permissive one is what would reopen the hole.
Doing this in the schema rather than by hand is what covers the table an
embedding migration creates later.

`COST_DISCOUNT_FACTOR` and `INFERENCE_GEO_MULTIPLIER` scale reported cost to
what you actually pay; `SESSIONS_TOKEN` is the operator's cross-owner view of
sessions. `/pricing` shows which are in effect. `CRITIC_MODEL` names the model
the critic runs on — unset, it falls back to the writer's; production pins
`claude-opus-5` in `fly.toml [env]`, as configuration rather than a secret.
`CLASSIFIER_MODEL` is its mirror image: unset means `claude-opus-5`, because
there the default *is* the production choice
([ADR-0013](docs/adr/0013-classifier-on-its-own-model.md) records the
measurement), and setting it is the emergency downgrade. `fly.toml` carries a
matching line so the per-node stance reads in one place, but that line is
deliberately not load-bearing — deleting it leaves the same model in effect.

🚀 **[Operations →](docs/OPERATIONS.md)** — Fly.io setup, the Postgres
migration, CI, the embedding-migration procedure, and the full configuration table.

---

## Limitations

Known, and deliberate for the scope. **The v1.0 README listed nine limitations
and v1.1 closed all nine; v1.2 has now closed four more.** The eval judge
stopped sharing the critic's model, `/health` stopped calling a revoked key
healthy, notes gained a second bound beside expiry, and the recorded-answers
claim was rebuilt on a real paid run — the eval section above reports what that
bought, refusals included, every number in it derived from the tree rather than
typed. Those four are *gone* from this list rather than reworded into it, which
is the only version of "closed" worth writing.

**Three remain, and this milestone's work was to stop them standing bare.**
Several of the nine closed by narrowing rather than erasing, so their narrower
successors are still here; each of the three below is one of those or a limit
the v1.1 work created, and each now ends at the record that argues it — an ADR,
or an operations note — so the position can be checked rather than taken.

**The paid run also found three things free testing structurally could not
see**, and a close-out claiming otherwise would be the one dishonest sentence in
the section. The classifier was mislabelling: 32 of 38 labelled cases where Opus
5 got 37, on a probe run once and kept, and *fixed* rather than recorded
([ADR-0013](docs/adr/0013-classifier-on-its-own-model.md)). The other two are
defects rather than positions — the judge's verdict truncating against a token
budget it shares with adaptive thinking, and record-time grading disagreeing
with replay-time grading — and they sit in the eval section above with their
per-case evidence and the reason neither is fixed here. A defect belongs there,
not in a list of choices.

What remains below is **chosen, recorded, and argued for**.

- **Reported cost is an approximation, never the invoice.** Nothing here reads a bill: provider token counts are telemetry — measured live, Voyage reported 25 tokens where the tokenizer counted 40, and 0 for a one-word document that embedded fine. Recorded as [ADR-0014](docs/adr/0014-cost-approximation-by-design.md), which also states why reconciling against Anthropic's Admin cost API was rejected.
- **Identities are free to mint.** Clearing browser storage gets you a fresh one with fresh limits, so per-caller limits buy fairness, not a bound on the bill. The global rolling daily spend cap is the actual backstop. Recorded as [ADR-0007](docs/adr/0007-anonymous-identity-fairness-global-cap.md).
- **The database is a single region on a free tier.** Fine at this traffic, and the first thing to look at if it isn't — the tier, the measured headroom behind that judgement, and the one part of the upgrade path that is not a toggle are in [the database posture note](docs/OPERATIONS.md#the-free-tier-posture-and-the-upgrade-path).

---

## License

MIT — see [LICENSE](LICENSE).
