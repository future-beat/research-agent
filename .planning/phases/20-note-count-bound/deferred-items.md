# Phase 20 — deferred items

Out-of-scope discoveries from Phase 20's doc pass (20-02). Both were **found by
measurement, left unfixed deliberately, and recorded rather than silently stepped
around**. Neither is drift this phase created.

## `.planning/codebase/CONCERNS.md:242-270` still says notes have no eviction path

The map asserts, as current fact:

> ### Stores grow without bound — confirmed, and worse in the memory store
> **Verified as stated, with detail.** There is genuinely no eviction, deduplication,
> or summarisation anywhere. The `MemoryStore` contract does not even have a method
> that could remove a note — the seam would need widening before an eviction policy
> could be written.

**Already false entering this phase.** Phase 12's unconditional TTL sweep physically
removes rows inside `add()`, so "no eviction anywhere" died two milestones ago. Phase 20
makes it more false, not newly false.

Its prediction is also wrong in a way worth keeping: it says the seam would need widening
first. Phase 20 wrote an eviction policy with the seam **character-identical** — no `+`/`-`
line in the `memory.py` diff matches `def (add|query|__len__|describe)\(`, and `graph.py`'s
diff is zero lines. Eviction lives inside `add()` and returns nothing.

**Why not fixed here:** the file is a dated audit snapshot (`**Analysis Date:** 2026-08-04`)
whose findings carry "Fix approach" sections — editing them rewrites an audit rather than
updating a doc. It is also `/gsd-map-codebase` output, regenerated wholesale, and Phase 18
already recorded three maps' staleness as a deferral for that reason. Phase 19's precedent is
the boundary followed: it corrected a map line **its own phase** falsified and left the rest.

**Candidate owner:** a `/gsd-map-codebase` re-run. Anyone reading that map as current fact
before then will be misled about this subsystem more than by any other sentence in the repo.

## `.planning/PROJECT.md:31-32`'s test counts are two phases stale

Reads "749 tests pass with no API keys, and 67 more are Postgres-gated ... 816 collected.
(Measured 2026-08-14, keyless.)" — Phase 18's correction, accurate the day it was written.

**Measured today, at Phase 20's close:** **796 passed / 71 skipped keyless, 867 collected.**
Phase 19 added 23 and left the line alone; Phase 20 added 23 more and four skips (the new
pgvector arms).

**Why not fixed here:** `PROJECT.md` is not in 20-02's `files_modified` and no plan task
names it; this wave's remit is the published doc surfaces (README, OPERATIONS, DESIGN) plus
the phase's own validation contract. Recorded with the measured numbers so the fix is a
two-line edit rather than another measurement run.

**Candidate owner:** Phase 22's doc pass, which rewrites the front-door claims anyway.
