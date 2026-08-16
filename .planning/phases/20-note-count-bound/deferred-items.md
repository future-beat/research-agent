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

### FATE — dispositioned by Phase 22 (2026-08-16), **not edited**

Phase 22's plan settled this in advance as decision **P-08**, and execution honoured it. The
map **stays as-is**; the owner **remains a `/gsd-map-codebase` re-run**. `CONCERNS.md` was not
touched by this phase.

The reasoning, restated so the disposition is a decision rather than an omission: the file is
a dated audit snapshot (`**Analysis Date:** 2026-08-04`) regenerated wholesale by the mapper,
and Phase 19's precedent — *correct only what your own phase falsified* — is the boundary.
**Phase 22 falsified nothing in it.** Hand-patching the two sentences would leave every other
stale sentence in the snapshot equally stale while hiding that the snapshot needs re-running,
which is Phase 18's recorded lesson about generated documentation going stale silently
because no phase owns it.

Phase 22's no-orphan sweep found it again, from the other direction, and this is worth
recording: the four *enumerated* deletion patterns returned **zero hits** across `docs/` and
`.planning/codebase/`, so the sweep's exemption list came out **empty**. A deliberately
broader paraphrase sweep (`no (eviction|dedup)`) then surfaced **two** hits, both here —
`CONCERNS.md:129` and `CONCERNS.md:254`. So the item is confirmed still live, by measurement,
at Phase 22's close: the claim is false, it is not orphaned prose this phase created, and it
is dispositioned rather than silently stepped around for the second phase running.

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

### FATE — **SETTLED by Phase 22 (2026-08-16)**, exactly as the deferral predicted

The named owner took it. Re-measured at Phase 22's close rather than carried from Phase 20's
deferral note, because two more phases (21, 21.5, 22) had landed since:

```
$ ANTHROPIC_API_KEY="" VOYAGE_API_KEY="" .venv/bin/pytest -p no:warnings | tail -1
828 passed, 72 skipped in 26.50s

$ ANTHROPIC_API_KEY="" VOYAGE_API_KEY="" .venv/bin/pytest --collect-only -p no:warnings | tail -1
900 tests collected in 0.68s
```

`PROJECT.md` now reads **828 / 72 / 900**, dated 2026-08-16 and labelled keyless. The
deliberate absence Phase 18 established is preserved verbatim: the with-Postgres pass count
is still **not** restated, because nobody has run that arm and deriving it from the keyless
delta would be arithmetic rather than a measurement.

**Two further corrections landed in the same two-line neighbourhood**, both falsified by this
milestone's own work and neither named in the deferral:

- `PROJECT.md:29` — *"`docs/adr/` holds 12 records"* → **14**. Phase 21.5 added ADR-0013 and
  Phase 22's own wave 1 added ADR-0014, so this phase had falsified it itself. "Four of them
  superseded" was re-derived from the files (14 records: 10 `Accepted`, 4 `Superseded`) and
  is **still correct**, so it stands unchanged.
- `PROJECT.md:35` — *"Offline evals grade 41 cases"* → **65** (40 behavioural + 25 replayed),
  with the other 15 golden cases named as documented refusals in `evals/REFUSALS.json`. The
  old sentence also said *"including one real recorded answer"*, which has been false since
  Phase 21's record run.

Recorded here rather than folded silently into the "two-line edit", because the deferral
predicted the size of the fix and the fix turned out to be four lines — the same
whole-file-pass-means-counting family this project has now caught repeatedly.
