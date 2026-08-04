# ADR-0004 — Sessions persist completed runs in SQLite, not LangGraph's checkpointer

**Status:** Accepted
**Promoted from:** `docs/DESIGN.md` § Data and backends — "Sessions store completed runs, not mid-run checkpoints" (DEC-14)

## Context

A follow-up arrives as a separate HTTP request. It will likely land on a different worker
than the one that produced the report, and it may arrive after a redeploy has replaced that
worker entirely. So the final state of every run has to outlive the process that produced
it — in-process memory is not an option for anything the second turn needs to read.

That is a persistence requirement, and it is worth being precise about *what* needs
persisting, because the obvious library answer solves a different problem.

## Decision

The final state of each run is persisted to SQLite — Postgres when `DATABASE_URL` is set,
the same schema under a different backend — in a schema this project owns.

What is stored is the **completed** run: the state a follow-up needs to answer without
re-searching. Mid-run checkpoints are not stored.

## Consequences

### Accepted

- A crash mid-run loses that run, and the caller retries. This is the honest behaviour when
  the alternative is resuming into a half-researched report: a run that died partway has no
  trustworthy state to resume *into*, and presenting one as if it were complete is worse
  than asking for the request again.
- The schema is this project's, so it can be read, migrated and tested directly, and the
  two backends can be held to the same behavioural contract.

### Rejected alternative

**LangGraph's checkpointer.** It solves resuming a half-finished graph — a different
feature with a different failure model from the one this system has. Adopting it here would
buy resumability nobody asked for, at the price of a session schema coupled to LangGraph
internals: an upgrade to the framework would become a data-migration question about records
the product depends on.
