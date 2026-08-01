"""
The golden dataset.

Twelve cases, chosen to cover the behaviours that would actually hurt if they
regressed: each topic type reaching its matching strategy and rubric, the
revision loop, both guardrails, follow-up isolation, and the one failure mode
this whole pipeline exists to prevent -- answering from the model's own
knowledge when the notes don't cover the question.

Every case carries two things:

    expectations  what a correct run looks like, graded by evals/graders.py
    script        canned model output, so the suite can run offline for free

The script is what makes this runnable in CI. It does *not* measure model
quality -- it can't, the outputs are authored here. What it measures is the
pipeline around the model: routing, guardrails, honesty about unapproved
drafts, and the graders themselves. Measuring the model needs `--live`.
"""

from __future__ import annotations

from dataclasses import dataclass

# Node names the scripted client can be asked to produce output for.
CLASSIFIER, RESEARCHER, WRITER, RESPONDER, CRITIC = (
    "classifier",
    "researcher",
    "writer",
    "responder",
    "critic",
)

APPROVED = "APPROVED"


def revise(reason: str) -> str:
    return f"REVISE: {reason}"


@dataclass(frozen=True)
class Followup:
    """A follow-up turn asked against the case's research run."""

    question: str
    # Whether the notes can actually answer this. When False, a correct answer
    # says so -- graders check that it neither guesses nor stays silent.
    answerable: bool = True
    expect_approved: bool = True
    answer: str = ""  # offline script


@dataclass(frozen=True)
class Case:
    id: str
    task: str
    why: str  # what regressing this would cost -- shown in the report

    # -- expectations -----------------------------------------------------
    expect_topic_type: str | None = None
    expect_approved: bool = True
    expect_forced_stop: str | None = None
    expect_revisions: int | None = None
    expect_notes_stored: bool = True
    max_cost_usd: float | None = None

    # -- offline script ---------------------------------------------------
    topic_label: str = "general"  # what the classifier returns offline
    notes: str = ""
    report: str = ""
    critic_verdicts: tuple[str, ...] = (APPROVED,)
    followups: tuple[Followup, ...] = ()

    # Offline-only knobs for cases that exercise guardrails.
    budget_usd: float | None = None

    @property
    def kind(self) -> str:
        return "followup" if self.followups else "research"


NOTES_MEMORY = (
    "FACTS: (1) LangGraph models agent control flow as an explicit state graph. "
    "(2) Vector stores retrieve prior notes by cosine similarity. "
    "(3) Retrieval with a relevance floor avoids leaking unrelated context. "
    "Sources: langchain docs, 2026-03."
)
REPORT_MEMORY = (
    "# Agent memory\n\nLangGraph models control flow as a state graph. "
    "Vector stores retrieve prior notes by cosine similarity, and a relevance "
    "floor keeps unrelated context out."
)

GOLDEN: tuple[Case, ...] = (
    # -- topic classification drives strategy and rubric -------------------
    Case(
        id="technical-figures",
        task="What are the current context window sizes and prices of the Claude model family?",
        why="Technical topics must reach the rubric that hunts for numbers absent "
            "from the notes; the wrong rubric lets an invented figure through.",
        expect_topic_type="technical",
        topic_label="technical",
        notes="FACTS: Claude Sonnet 5 has a 1M token context window. "
              "Introductory pricing is $2/$10 per MTok through 2026-08-31.",
        report="# Claude model family\n\nSonnet 5 offers a 1M token context window "
               "at introductory pricing of $2/$10 per MTok through 2026-08-31.",
    ),
    Case(
        id="contested-viewpoints",
        task="Are AI agent frameworks worth adopting, or is direct API orchestration better?",
        why="Contested topics must present disagreement as disagreement. A run "
            "that flattens two camps into one settled answer is confidently wrong.",
        expect_topic_type="contested",
        topic_label="contested",
        notes="FACTS: Proponents argue frameworks reduce boilerplate. Critics argue "
              "they add indirection over a loop you could write yourself. Sources disagree.",
        report="# Frameworks vs direct orchestration\n\nProponents argue frameworks "
               "cut boilerplate; critics argue they add indirection. The sources disagree.",
    ),
    Case(
        id="sparse-coverage",
        task="What is the adoption of LangGraph among Icelandic public-sector teams?",
        why="Sparse topics must flag their own gaps. Overstated confidence on a "
            "thin evidence base is the failure users are least able to detect.",
        expect_topic_type="sparse",
        topic_label="sparse",
        notes="FACTS: No published survey covers this specifically. Coverage is thin; "
              "only two blog posts mention public-sector use in the Nordics at all.",
        report="# LangGraph in Icelandic public-sector teams\n\nThe research found no "
               "published survey on this. Coverage is thin, and this should be treated "
               "as a gap rather than an absence of adoption.",
    ),
    Case(
        id="general-summary",
        task="What is retrieval-augmented generation?",
        why="The general path is the default; if it breaks, most traffic breaks.",
        expect_topic_type="general",
        topic_label="general",
        notes="FACTS: RAG retrieves documents relevant to a query and supplies them "
              "to a model as context before it answers.",
        report="# Retrieval-augmented generation\n\nRAG retrieves query-relevant "
               "documents and supplies them to the model as context before answering.",
    ),
    Case(
        id="unknown-label-falls-back",
        task="Summarise the history of the printing press.",
        why="A classifier that returns something off-menu must not crash the run "
            "or index a rubric that doesn't exist.",
        expect_topic_type="general",  # falls back
        topic_label="tEcHnIcAl-ish nonsense",
        notes="FACTS: Gutenberg introduced movable type in Europe around 1440.",
        report="# The printing press\n\nGutenberg introduced movable type in Europe "
               "around 1440.",
    ),
    # -- the critic loop ---------------------------------------------------
    Case(
        id="revision-then-approval",
        task="What are the most notable recent developments in agent design patterns?",
        why="The critic pushing back and the writer fixing it is the core quality "
            "loop. If revisions stop happening, ungrounded claims ship.",
        expect_topic_type="general",
        expect_revisions=1,
        topic_label="general",
        notes="FACTS: Supervisor patterns route on state. Critic nodes check claims "
              "against notes.",
        report="# Agent design patterns\n\nSupervisor patterns route on state, and "
               "critic nodes check claims against the research notes.",
        critic_verdicts=(revise("the adoption figure is not in the notes"), APPROVED),
    ),
    Case(
        id="revision-cap-is-labelled",
        task="Explain the internal architecture of a proprietary system with no public docs.",
        why="A critic that never approves must not loop forever, and the draft it "
            "gives up on must be labelled unapproved. A silent unapproved draft "
            "is the worst bug this service could have.",
        expect_approved=False,
        expect_forced_stop="max_revisions_exceeded",
        topic_label="sparse",
        notes="FACTS: No public documentation exists for this system.",
        report="# Internal architecture\n\nThe research found no public documentation.",
        critic_verdicts=tuple([revise("still unsupported")] * 12),
    ),
    Case(
        id="budget-cap-is-labelled",
        task="Produce an exhaustive survey of every agent framework released since 2023.",
        why="The spend cap has to fire and say so. A run that quietly costs "
            "unbounded money is a billing incident, not a feature.",
        expect_approved=False,
        expect_forced_stop="budget_exceeded",
        expect_notes_stored=False,  # stops before the researcher can finish
        budget_usd=0.0000001,
        topic_label="general",
        notes="FACTS: dozens of frameworks exist.",
        report="# Survey\n\nDozens of frameworks exist.",
    ),
    # -- memory ------------------------------------------------------------
    Case(
        id="notes-are-persisted",
        task="How do LLM agents implement long-term memory?",
        why="Recall across runs is the feature; if the researcher stops writing "
            "notes, later runs silently start cold and nobody notices.",
        expect_topic_type="technical",
        topic_label="technical",
        notes=NOTES_MEMORY,
        report=REPORT_MEMORY,
    ),
    # -- follow-ups --------------------------------------------------------
    Case(
        id="followup-uses-prior-notes",
        task="How do LLM agents implement long-term memory?",
        why="A follow-up must answer from the notes it already has. If it "
            "re-searches, every follow-up costs a full research run.",
        expect_topic_type="technical",
        topic_label="technical",
        notes=NOTES_MEMORY,
        report=REPORT_MEMORY,
        critic_verdicts=(APPROVED, APPROVED),
        followups=(
            Followup(
                question="Which of those handles recall across separate sessions?",
                answer="Vector stores handle cross-session recall: notes are retrieved "
                       "by cosine similarity, with a relevance floor.",
            ),
        ),
    ),
    Case(
        id="followup-admits-a-gap",
        task="How do LLM agents implement long-term memory?",
        why="THE failure this pipeline exists to prevent. Asked something the "
            "notes don't cover, a correct answer says so. Answering anyway from "
            "the model's own knowledge is a confident, ungrounded, invisible lie.",
        expect_topic_type="technical",
        topic_label="technical",
        notes=NOTES_MEMORY,
        report=REPORT_MEMORY,
        critic_verdicts=(APPROVED, APPROVED),
        followups=(
            Followup(
                question="What did Gartner forecast for agent memory spending in 2027?",
                answerable=False,
                answer="The research didn't cover Gartner forecasts or spending "
                       "projections, so I can't answer that from these notes.",
            ),
        ),
    ),
    Case(
        id="followups-chain",
        task="How do LLM agents implement long-term memory?",
        why="A second follow-up must see the first. Losing the thread turns a "
            "conversation back into a series of disconnected one-shots.",
        expect_topic_type="technical",
        topic_label="technical",
        notes=NOTES_MEMORY,
        report=REPORT_MEMORY,
        critic_verdicts=(APPROVED, APPROVED, APPROVED),
        followups=(
            Followup(
                question="Which of those handles recall across separate sessions?",
                answer="Vector stores handle cross-session recall by cosine similarity.",
            ),
            Followup(
                question="And what stops it recalling something irrelevant?",
                answer="A relevance floor: matches below the similarity threshold are "
                       "dropped rather than returned.",
            ),
        ),
    ),
)


def by_id(case_id: str) -> Case:
    for case in GOLDEN:
        if case.id == case_id:
            return case
    raise KeyError(f"No golden case {case_id!r}.")


def select(ids: list[str] | None = None) -> tuple[Case, ...]:
    return tuple(by_id(i) for i in ids) if ids else GOLDEN
