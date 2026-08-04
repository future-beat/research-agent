## Conflict Detection Report

Mode: new (net-new bootstrap, no existing .planning context to check against)
Precedence: ADR > SPEC > PRD > DOC — no precedence contest arose; all three
source documents classified DOC, so no source outranks another.
Docs ingested: README.md, docs/DESIGN.md, docs/OPERATIONS.md

### BLOCKERS (0)

No blockers. No LOCKED decisions exist in the ingest set (zero ADRs), so no
LOCKED-vs-LOCKED contradiction is possible. No UNKNOWN classifications and no
low-confidence classifications — all three docs classified DOC at medium
confidence. No derivation cycle (see INFO below).

### WARNINGS (3)

[WARNING] Deploy gating: repo evidence and owner's working understanding disagree
  Found: docs/OPERATIONS.md states "Deploys currently run through Fly's GitHub
    integration, which is **not** gated on CI: a direct push that fails tests
    still deploys, because branch protection only gates pull requests." Repo
    evidence supports this: commit 9ebee6b "Use Fly's GitHub integration for
    deploys; drop the CI-gated workflow" deleted .github/workflows/deploy.yml,
    and the only remaining workflow (.github/workflows/ci.yml) contains no
    deploy or fly step. Against this, the project owner's working understanding
    has been that deploys are manual via `fly deploy -a research-agent` — and
    docs/OPERATIONS.md itself lists exactly that command twice, in the "Fly.io"
    and "Going stateless" sections, without marking it as setup-only.
  Impact: Both cannot be the current reality, and they imply opposite risk
    postures. If the integration is live, a direct push to main auto-deploys
    failing code to a public service with real spend attached — and
    REQ-multi-machine-state, which changes fly.toml, would ship on push. If it
    is not live, production is running whatever was last hand-deployed and may
    already differ from main. Synthesis cannot resolve this: the deciding state
    lives in Fly's dashboard, outside the repo, and guessing either way
    mis-plans the next milestone.
  → Verify out-of-band, do not infer. Check the Fly dashboard for the
    research-agent app under Settings → GitHub / source integration, and check
    github.com/future-beat/research-agent Settings → Integrations for the Fly
    app's repo access. Cross-check by comparing the currently deployed release
    (`fly releases -a research-agent`) against the last commit on main. Then
    either (a) correct the owner's mental model and add a CI gate as an explicit
    requirement, or (b) correct docs/OPERATIONS.md line 49-51 to say deploys are
    manual. Record the outcome as a decision before any deployment-touching work
    is planned.

[WARNING] Six of the nine next-milestone requirements reverse a stated design position
  Found: README.md's "## Limitations" section frames all nine items as "Known,
    and deliberate for the scope" — accepted trade-offs, not defects. The owner
    has decided to take on all nine. But docs/DESIGN.md argues *for* several of
    them. The two strongest: (1) REQ-followup-live-search reverses the position
    that follow-ups cannot search, which README.md marks "By design" and
    docs/DESIGN.md builds the responder around — "the research didn't cover
    that" is taught to the responder as a correct answer, and no_prior_research
    is called "the single failure mode this whole pipeline exists to prevent."
    (2) REQ-independent-critic-model removes the premise of docs/DESIGN.md's
    judge decision, which states the judge "runs on Opus 5 against Sonnet 5"
    precisely because the in-graph critic shares the writer's model. Four
    lower-stakes reversals also apply: REQ-embedding-model-migration vs the
    copy-don't-re-embed migration decision, REQ-offline-eval-quality vs the
    offline-evals-cannot-grade-quality position, REQ-demo-authentication vs the
    rate-limited-not-authenticated scope call, and REQ-connection-pool vs the
    single-connection sizing judgement.
  Impact: Planning these as bug fixes would silently retire six argued design
    decisions and leave the docs asserting things that are no longer true — in
    particular README.md's sentence "The eval judge runs on a stronger model
    precisely because of this" becomes false the moment the critic model splits.
    Synthesis will not auto-retire a decision on the strength of a limitations
    checkbox.
  → Before routing, confirm each reversal explicitly. For the two strong ones,
    decide what replaces the retired guarantee: for follow-up search, what
    no_prior_research now means and how grounding is preserved; for the critic
    model, re-derive the eval judge decision rather than inheriting it. Full
    analysis in .planning/intel/constraints.md under "Requirements that reverse
    a stated design position."

[WARNING] Twenty-two architectural decisions carried at DOC precedence, none locked
  Found: docs/DESIGN.md classified DOC (medium confidence) — prose rationale
    with no frontmatter, no Status field, no Context/Decision/Consequences
    structure. Its classifier nonetheless emitted a non-schema
    decision_candidates array holding 22 discrete architectural decisions, each
    with a rejected alternative. These were read and carried into
    .planning/intel/decisions.md rather than discarded. README.md and
    docs/OPERATIONS.md contributed further decisions at the same precedence.
  Impact: This project's entire architectural record sits at the lowest
    precedence tier with zero locked entries. Any future ingest of an ADR, SPEC,
    or PRD will outrank all 22 automatically, and nothing will block a
    contradiction. The routing decision, the separate critic, the checkpointer
    rejection, and the metrics-denominator rule are all overridable by a
    passing mention in a higher-precedence doc.
  → Confirm you want these treated as soft/revisable (decisions.md states this
    explicitly at the top). Recommended: promote at least DEC-01, DEC-02,
    DEC-04, DEC-13 and DEC-20 into numbered ADRs under docs/adr/ with an
    explicit Status, so the next reversal is recorded rather than silent. This
    also gives the six reversals above a supersession target.

### INFO (6)

[INFO] Verified: README's critic-vs-judge model claim is accurate
  Note: README.md's Limitations claims "The critic shares the writer's model...
    The eval judge runs on a stronger model precisely because of this."
    Confirmed against source. src/research_agent/graph.py:38 defines a single
    MODEL = "claude-sonnet-5", used by every node call site in that file
    (lines 96, 99, 103, 111) with no per-node override — the critic runs on the
    same model as the writer. evals/graders.py:28 defines JUDGE_MODEL =
    os.environ.get("EVAL_JUDGE_MODEL", "claude-opus-5"), consumed by the judge
    grader at line 237. No conflict: the README, docs/DESIGN.md and the code all
    agree. Recorded because REQ-independent-critic-model changes both, and the
    docs will need updating together.

[INFO] Cross-ref cycle present but navigational, not derivational — gate not applied
  Note: The cross_refs graph contains a cycle: README.md → docs/DESIGN.md →
    ../README.md, and README.md → docs/OPERATIONS.md → ../README.md, with
    docs/OPERATIONS.md → DESIGN.md. Depth is 2, far under the 50 cap. Inspection
    of the link sites shows these are reciprocal "see also" pointers — DESIGN.md
    line 6 "For what the system *is*, see the README"; OPERATIONS.md lines 4-5
    "For what the system is, see the README; for why it's built this way,
    DESIGN.md" — not content-derivation edges. No document derives its content
    from another, so no synthesis loop is possible and the cycle blocker was not
    raised. Flagging for transparency: if you consider a strict reading of the
    cycle rule mandatory, this is the entry to escalate.

[INFO] Stale backend count in docs/DESIGN.md
  Note: docs/DESIGN.md "Memory" states MemoryStore has "three implementations
    behind a VECTOR_STORE env var: JSON (default), in-memory, and Chroma." That
    predates Phase 8. docs/OPERATIONS.md's config table lists four (json, memory,
    chroma, pgvector) and its project layout says "Embedder + MemoryStore seams
    and four backends"; docs/DESIGN.md's own next paragraph then describes the
    pgvector backend. Not a precedence conflict (both docs are DOC, equal rank)
    and it self-resolves in-document. Synthesized intel records four backends.
    → Optional doc fix, no planning impact.

[INFO] No competing acceptance variants
  Note: All nine requirements derive from a single source section (README.md
    "## Limitations"). No second document defines overlapping requirements with
    divergent acceptance criteria, so no variant preservation was needed. The
    acceptance criteria written into .planning/intel/requirements.md are
    synthesis proposals derived from the limitation text plus the corresponding
    DESIGN.md rationale — they are not user-ratified and should be reviewed.

[INFO] Time-sensitive cost figures
  Note: docs/DESIGN.md records Claude Sonnet 5 on introductory pricing of $2/$10
    per MTok through 2026-08-31, moving to $3/$15 on 2026-09-01. Ingest date is
    2026-08-04, so every cost figure in the ingested docs and in downstream
    planning has a 27-day shelf life. The effective-dated price table and
    /pricing already handle this in the running system; the risk is planning
    documents quoting a stale rate. REQ-real-cost-accounting touches this table.

[INFO] No open roadmap items inherited from source docs
  Note: README.md's "## Status" carries nine phase checkboxes, all marked
    complete (phases 1-9). Nothing in-flight was carried into intel. The next
    milestone is net-new work sourced entirely from "## Limitations", which is
    why that section produced all nine requirements.
