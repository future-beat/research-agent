# Design decisions

The parts worth reading the code for. Each of these is a choice that could
reasonably have gone the other way; this records why it didn't.

For what the system *is*, see the [README](../README.md).

The load-bearing decisions below are also kept as numbered architecture decision records —
see the [ADR index](adr/README.md) for their current status and any supersessions. The prose
here is the argument; the records are what a later reversal has to supersede explicitly.


## The graph

**Routing is a state machine, not a prompt.** `supervisor_node` is plain Python — a chain of `if` statements over `AgentState`. No model call decides what runs next, so the control flow is deterministic, unit-testable, and identical on every run. The LLM does the work; the graph decides the order. Recorded as [ADR-0001](adr/0001-deterministic-python-routing.md).

**The critic is a separate node with its own rubric.** Asking one model to draft and self-assess in a single call reliably produces "looks good to me." Splitting the draft and the grounding check into separate calls, with the critic given the research notes as the sole source of truth, catches ungrounded claims the writer introduced. Recorded as [ADR-0002](adr/0002-separate-critic-node.md).

**Every loop is bounded, and stopping early is reported honestly.** `MAX_REVISIONS` caps the critic↔writer cycle; `MAX_ITERATIONS` caps total supervisor turns as a backstop against any unforeseen cycle. When a cap fires, `forced_stop_reason` propagates to the output so the user knows the report they're reading was never approved — a silent unapproved draft would be worse than no draft.

**Follow-ups reuse the critic instead of bypassing it, and reach when their notes can't answer.** The responder writes into the same `draft` field the writer does, so the critic grades a follow-up answer with the same rubric and the same revision loop — a follow-up can be sent back for revision exactly like a report. Grounding means an answer comes only from notes the researcher gathered and the critic reviewed; it never meant those notes had to exist before the conversation started. So a follow-up whose notes can't cover the question neither guesses nor gives up: the responder signals the gap, that signal *routes* the turn to the researcher for exactly one pass, and the enlarged note set gets one authoring attempt the critic reviews as usual. The window in between produces no answer at all, which is what keeps the failure this whole pipeline exists to prevent — a model improvising once the notes run out — structurally impossible rather than merely discouraged. If the answer still isn't there after looking, "the research didn't cover that" ships as the answer, with the trace showing the attempt. One pass, deliberately: a follow-up can't loop research → insufficient → research. Recorded as [ADR-0011](adr/0011-followups-reach-for-new-information.md), which supersedes [ADR-0003](adr/0003-followups-reuse-critic-no-prior-research.md) — the record that bought the same guarantee the cheaper way, by refusing to search at all.

**Inference settings are tuned per node, not globally.** The classifier emits one word from a fixed set, so it runs with thinking disabled under a 20-token ceiling — no budget spent deliberating a four-way label. The researcher, writer, and critic do genuine reasoning and run with adaptive thinking, letting the model scale its own depth per task. Everything runs at `effort: "medium"`.

**Every run is traceable.** Each node appends to `state["trace"]`, giving a full record of routing decisions, recall counts, draft lengths, and critic verdicts. Inspect it with `/trace` in the REPL.


## Memory

**Memory is real retrieval, not a growing prompt.** Notes are embedded with `voyage-3.5` and retrieved by cosine similarity with a relevance floor, so an unrelated past task doesn't leak into the current one. The researcher is explicitly told to prefer information not already covered, which turns memory into a coverage-expander rather than an echo.

**The store and the embedder are separate seams.** `MemoryStore` is an ABC — `add()`, `query()`, `len()`, `describe()` — with four implementations behind a `VECTOR_STORE` env var: JSON (default), in-memory, Chroma, and pgvector. `Embedder` is a separate protocol, so switching stores never silently switches embedding models; that would invalidate every vector already written. Chroma keeps the same cosine ranking but adds an ANN index and stops loading the entire corpus into the agent process. A test asserts the graph never reaches past those four methods, so the seam can't rot.

**pgvector replaces the scan, not just the file.** The brute-force stores score every note on every query and pull the whole corpus into the agent process — exact, O(n), and the thing the Limitations section has flagged since Phase 1. HNSW keeps the same cosine ranking and stops doing either. It's also shared, so every machine recalls everything the agent has learned rather than only what it personally wrote.

**Migration copies embeddings rather than re-embedding.** It's free and exact — but the real reason is that re-embedding would change recall behaviour at the same moment you're changing infrastructure. If recall then got worse you'd have two suspects and no way to separate them.


## Cost

**The spend cap is a routing rule, not a wrapper.** The iteration and revision caps bound how many model calls a run makes; they say nothing about what those calls cost, and a capped run can still be an expensive one. Because every node folds its usage into `state["usage"]` before returning, the supervisor can read the running cost on its next hop — so the budget became one more row in the same table, with the same `forced_stop_reason` machinery, rather than a separate mechanism bolted around the graph. It is checked *between* nodes because cost is only knowable after a call returns, which means a run can overshoot by at most one node rather than by an unbounded amount.

**Prices are effective-dated, and the reason survives the fact that none of them is currently dated.** The design was written for a real deadline: Sonnet 5's $2/$10 introductory rate was to become $3/$15 on 2026-09-01, and a single hardcoded rate would have kept reporting confident numbers a third too low from that morning — the worst kind of wrong, because nothing fails. On 2026-08-12 that rate was made permanent, so every model in the table now has one open-ended window and `/pricing` reports `next: null` for all of them.

The machinery stays, for a reason worth stating rather than assuming: the argument for it was never "Sonnet 5 in particular has a deadline", it was that a price can change on a date somebody else chooses, and the cheapest possible response to that is a table edit. What *did* change is that no shipped model exercises the dated path any more, so the tests that proved it moved onto a synthetic two-window table declared in `tests/test_usage.py` and labelled as such. Without that, `window_for` would only ever return `(None, None)` and `next_window` only ever `None` — the dated half of the module with nothing to prove it works. `price_for()` still resolves by date, `/pricing` still exposes what accounting is using today, and cache-rate constants are still asserted to be the documented 1.25× and 0.1× of base input rather than trusted as typed-in numbers.

**An unpriced model is reported, not costed at zero.** If `MODEL` is changed to something with no row in the price table, tokens are still counted but `cost_usd` becomes a floor and `pricing_unknown` goes true. Silently costing those calls at zero would quietly disable the budget guardrail — a cost control that fails open without saying so is worse than none.

**Failed runs are in the metrics denominator.** A run that died opens no session, but it still burned tokens and still happened. Recording only successes would make an upstream outage look like a quiet day and would flatter every rate on the dashboard. Rates whose denominator is zero return `null` rather than `0.0`, because "no runs yet" and "nothing was approved" are different facts and a dashboard shouldn't conflate them. Latency percentiles cover completed runs only — time-to-failure is not time-to-report, and mixing them makes an outage look like a speed-up.


## Data and backends

**Sessions store completed runs, not mid-run checkpoints.** A follow-up arrives as a separate request, likely on a different worker, possibly after a redeploy, so the final state of every run goes to SQLite. Deliberately *not* LangGraph's checkpointer: that solves resuming a half-finished graph, a different feature with a different failure model, and adopting it here would buy resumability nobody asked for at the price of a schema coupled to LangGraph internals. A crash mid-run loses that run and the caller retries — which is the honest behaviour when the alternative is resuming into a half-researched report. Recorded as [ADR-0004](adr/0004-sessions-in-sqlite-not-langgraph-checkpointer.md).

**One variable moves all three stores.** Sessions, metrics, and notes each default to Postgres when `DATABASE_URL` is present and to local disk when it isn't. Three separate backend flags would have been more configurable and worse: the failure you'd actually hit is setting one and forgetting another, and a deployment with sessions shared across machines but notes still split between them is broken in a way that only shows up as slowly degrading answers. Any of the three can still be pinned explicitly when you genuinely want a mixture.

**"Swappable" is a test, not a claim.** Two hand-written SQL dialects agreeing is exactly the sort of thing that quietly stops being true — SQLite sums booleans where Postgres needs `COUNT(*) FILTER`, and Postgres returns `SUM(BIGINT)` as `Decimal`, which isn't JSON-serialisable and would have 500'd `/metrics` on the first recorded run. So the behavioural tests live in one file and run against every backend, and one test asserts both metrics backends produce *byte-identical* summaries from identical input.


## Reliability

**Retries happen at the node boundary, and are recorded.** A graph node is a whole unit of work, so retrying there means a transient 529 costs one repeated node rather than a failed run. `retry.py` retries only what can actually succeed on a second try — connection errors and 408/429/5xx — and raises straight through on 401 or 400, where waiting just burns wall-clock time. Backoff is exponential with equal jitter, and a server's `retry-after` wins when it asks for longer, because our curve is a guess and the header isn't. Every attempt lands in `state["trace"]`, so a slow run explains itself in `/trace` instead of looking like a stall. `sleep` and `rng` are injectable, which is why the retry tests run in milliseconds and assert exact delays.

**Nothing is constructed at import time.** Both API clients are built on first use. Eager construction would make the modules unimportable without a full set of keys — which would mean the routing table, the one genuinely deterministic part of the system, could not be tested at all. The whole suite runs with no keys and no network.

**Nothing a dependency does should stop the process starting.** The Postgres stores register their schema instead of executing it in `__init__`, and apply it on first use. Running DDL at construction meant an unreachable database stopped the service from *booting*, which made the degraded-dependency reporting in `/health` unreachable by definition. It's worse against a provider that pauses idle instances: the app couldn't boot, so it never connected, so nothing ever woke the database — a deadlock no restart could break. Now it comes up degraded and heals itself the moment the database answers.

**A stream that fails has to say so in-band.** By the time a node dies, the `200` and the headers are long gone. So `_stream` catches everything and emits a terminal `error` event: exactly one terminal event per stream, never both, never neither. Without it a mid-run failure is indistinguishable from a truncated connection, and the client's only options are to guess or to hang.


## Testing

**Offline evals grade the pipeline; only `--live` grades the model.** The suite drives the real compiled graph either way, but offline it replaces the API with a scripted client whose output is authored in the dataset. That makes it free, deterministic, and safe to run on every push — and it means it cannot say anything about answer quality, because the answers are ours. What it *can* check is everything around the model: routing, both guardrails, the one-pass bound on a follow-up that reaches for new notes, and the invariant that an unapproved draft is never returned as if approved. The CLI prints that caveat under every offline run, because a green suite that quietly implies "the model is good" is worse than no suite. Phase 15 extended what an offline run may claim without touching that principle: real pipeline runs are recorded once as committed fixtures and replayed on every push, so *those* answers are graded deterministically for grounding, coverage, structure and refusal honesty — with the recording's date, model and commit printed beside the verdict, and a hard gate when the recorded model is no longer the one this tree runs. What is still out of reach is unchanged: only `--live` can say what the *current* model would produce. Recorded as [ADR-0009](adr/0009-recorded-answer-quality-evals.md).

**The judge runs on a different, stronger model than the pipeline.** The in-graph critic shares the writer's model — good enough to catch ungrounded claims, not an independent evaluator, and the README has said so since Phase 1. A judge on that same model would inherit exactly the blind spots it exists to find, so it runs on Opus 5 against Sonnet 5, and returns a structured verdict rather than a text convention: a scoring harness that mis-parses a verdict reports a confident wrong number, which is worse than crashing. Recorded as [ADR-0005](adr/0005-opus-5-eval-judge.md), superseded in Phase 16 by [ADR-0010](adr/0010-judge-rederived-for-an-independent-critic.md) and in Phase 18 by [ADR-0012](adr/0012-judge-independent-of-the-critic.md) — the paragraph above is the argument as it stood, and each record re-derives the judge's rationale rather than inheriting a premise that no longer holds. Phase 16 gave the critic its own model, so the shared-model premise went; Phase 18 moved the judge off the critic's model too, so the judge no longer runs on Opus 5 at all. It ships on `claude-opus-4-8`, which buys independence of the critic's model *identity* and not of its family — ADR-0012 states that residual rather than solving it, and is where the rationale currently lives.

**The evals found a real bug on their first run.** `MAX_ITERATIONS` was 8 and `MAX_REVISIONS` 2, which made the revision cap **unreachable in research mode** — reaching `revision_count > 2` needs supervisor turn 10, so the iteration backstop always fired first. A run where the critic kept rejecting reported `max_iterations_exceeded`, which reads like an internal fault, instead of `max_revisions_exceeded`, which is the truth: the draft never got grounded. Both caps "worked"; they were just the wrong way round. `MAX_ITERATIONS` is now derived from `MAX_REVISIONS` so the backstop stays above the cap, and a test pins the relationship. No unit test caught this, because each cap was correct in isolation — it took running whole scenarios and asserting on *which* guardrail fired.


**A paid record run found three things free testing structurally could not.** The offline
suite stubs the classifier and the critic, so drift between the shipped pipeline and what the
golden cases assert is invisible to it by construction. Recording 40 real answers in Phase 21
($9.90 against a $17.48 quote) surfaced all three at once, and the split of what came back is
the useful part — 25 cases recorded, 15 refused, in `evals/REFUSALS.json` with a per-case
reason.

*Seven refusals are the machinery working*: a grader or the judge declined a recording, which
is what they are for. Two of those entries were rewritten when the Opus 5 classifier removed
their original cause, rather than left carrying a reason that no longer applies. The other
eight are defects, and neither is fixed:

**The judge's verdict truncates.** `max_tokens=1500` is shared with adaptive thinking, so a
long deliberation cuts the JSON off mid-object. `Judge.verdict`'s own docstring in
`evals/graders.py` predicted this before any run hit it, which is why it surfaces by name as
truncation rather than as a malformed verdict — labelled correctly, and still costing the
recording. Raising or splitting that budget changes the judge, and
[ADR-0012](adr/0012-judge-independent-of-the-critic.md) is where the judge's configuration is
decided; it should not move in a phase that is not about the judge.

**Record-time and replay-time grading disagree.** Six recordings passed at record time and
failed replay, because `grade_case_pins` runs only on the replay path. Five are contested-topic
cases whose pins require the words *proponents* and *critics* while the recordings argue both
sides at length in other words. Re-authoring the pins was tried and **reverted**: the same
`must_mention` must also hold against the case's hand-authored reference report in
`dataset.py`, which is written in that vocabulary, so every replacement collapsed to a word
testing less than the pin it replaced. The sixth is a follow-up that admitted no source covered
a forecast and then supplied a reasoned estimate anyway — the hedged half-answer the
recorded-refusal grader's docstring says it cannot catch. That record-time grading approved it
at all is the finding; widening the patterns to keep it would teach the suite to accept the
failure the pipeline exists to prevent.

Neither is a limitation the project chose, which is why neither sits in the README's
Limitations list. They are written down with their per-case evidence instead of averaged into
a pass rate.

## Packaging

**The image ships what it runs, and nothing else.** the base package is the agent alone; the web server lives in the `[service]` extra, so a worker or batch job that imports the graph doesn't drag in FastAPI and uvicorn. The image installs `[service]`, not `[dev]`, and `src/` layout keeps `tests/` and `evals/` outside the package entirely — the eval dataset contains scripted model output, which has no business inside a production image.
