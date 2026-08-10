"""
Research-and-Report Agent System

A supervisor pattern with a critic, persisted vector memory, topic-type
classification, and two run modes sharing one graph.

    research mode (a new question):
        supervisor -> classifier (once) -> supervisor
                   -> researcher (recalls + stores via the memory store)
                   -> writer -> critic -> approved? END : writer (capped)

    followup mode (a question about the run you just got):
        supervisor -> responder -> critic -> approved? END : responder (capped)
                   -> researcher, once, when the notes cannot answer
                      -> responder -> critic -> ...

Follow-ups never classify -- they inherit the topic type of the run they are
about. They answer from that run's notes; and when those notes cannot cover
the question, the responder says so and that signal ROUTES the turn to the
researcher for exactly one pass, which enlarges the note set rather than
replacing it. The window in between produces no answer at all, and the critic
loop is reused untouched on either path -- so an answer to a follow-up is
fact-checked exactly as hard as the report it's about, and the one thing a
follow-up still cannot do is answer from the model's own knowledge.

Requires: pip install langgraph anthropic voyageai numpy
Requires: ANTHROPIC_API_KEY and VOYAGE_API_KEY in your environment
"""

from __future__ import annotations

import os
import time
import uuid
from typing import Literal, TypedDict

import anthropic
from langgraph.graph import END, StateGraph

from research_agent import usage as usage_accounting
from research_agent.memory import MemoryStore, get_memory_store
from research_agent.observability import get_logger, span
from research_agent.retry import retry_node

MODEL = "claude-sonnet-5"
MAX_REVISIONS = 2
# The backstop has to sit above the revision cap, or it stops being a backstop.
# A research run that exhausts its revisions takes: classifier, researcher, then
# a writer/critic pair per attempt (1 initial + MAX_REVISIONS + 1 to trip it),
# so the revision cap can only fire on supervisor turn 2 + 2*(MAX_REVISIONS+2).
# At the original 8 it never did -- a critic stuck rejecting reported
# "max_iterations_exceeded", which reads like an internal fault rather than
# the truth, which is that the draft never got grounded. Found by the evals.
# A follow-up that reaches lands on the same worst case rather than a longer
# one: its insufficiency signal and the pass that signal buys take the two
# turns the classifier and the researcher take in research mode, so ten is
# still the ceiling and the revision cap is still what fires first.
MAX_ITERATIONS = 2 * (MAX_REVISIONS + 2) + 4  # 12: reachable, with headroom


def critic_model() -> str:
    """The model the critic runs on. `CRITIC_MODEL` unset or blank means the
    writer's model -- a neutral default, so shipping the capability changes
    nothing until an operator sets the variable.

    Read on every call rather than cached in a module constant, the
    `sessions_token()` idiom from limits.py: a module-scope read would freeze
    the value at import, so an operator changing configuration would not
    change what the process does, and tests could not flip it with
    monkeypatch.setenv.

    No validation past strip-or-default. An unknown-but-real model must be
    allowed -- being able to point the critic at any model is the feature.
    A model with no price row is `pricing_unknown`'s job (DEC-12), not this
    accessor's: the run is costed as a floor and says so, rather than being
    refused by a whitelist that would need maintaining against every release.
    """
    return os.environ.get("CRITIC_MODEL", "").strip() or MODEL


log = get_logger()

# Both clients are built on first use, not at import. Constructing them at
# module scope would mean you cannot import this module -- or unit-test the
# routing table -- without a full set of API keys.
_client: anthropic.Anthropic | None = None
_memory: MemoryStore | None = None


def client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def memory() -> MemoryStore:
    """The configured memory backend (see VECTOR_STORE in vector_memory.py)."""
    global _memory
    if _memory is None:
        _memory = get_memory_store()
    return _memory


def set_memory(store: MemoryStore | None) -> None:
    """Swap the backend at runtime. Tests use this; so would a service that
    wants one store per tenant."""
    global _memory
    _memory = store


def _text(response) -> str:
    return "".join(block.text for block in response.content if block.type == "text")


def call_model(state: AgentState, node: str, *, model: str | None = None, **kwargs):
    """Every model call in this system goes through here.

    One choke point for the three things you need per call in production:
    what it cost, how long it took, and a span to hang it off. Nodes that
    called the client directly would each have to remember all three.

    Usage is folded into `state["usage"]` before the response is returned, so
    the supervisor sees the true running cost on its very next hop.

    `model` is keyword-only and defaults to the writer's model, so a node that
    does not care stays exactly as it was. The name it resolves to is used at
    all four sites below -- the span, the API call, the cost record, and the
    log line. Threading three of them and leaving the fourth reading `MODEL`
    is the silent-misbilling bug: an Opus critic recorded as Sonnet
    under-reports every critic call 2.5x, with no error anywhere. Cost
    attribution here is a *passed constant*, not something read back off the
    response -- `CallUsage.from_response` never looks at `response.model`.
    """
    model = model or MODEL
    started = time.perf_counter()
    with span(
        f"node.{node}", run_id=state.get("run_id", ""), node=node, model=model,
        mode=state.get("mode", ""),
    ):
        response = client().messages.create(model=model, **kwargs)

    elapsed_ms = (time.perf_counter() - started) * 1000
    call = usage_accounting.CallUsage.from_response(response)
    cost = usage_accounting.record(state["usage"], call, model)

    log.info(
        "model call",
        extra={
            "event": "model_call",
            "run_id": state.get("run_id", ""),
            "node": node,
            "model": model,
            "duration_ms": round(elapsed_ms, 1),
            "input_tokens": call.input_tokens,
            "output_tokens": call.output_tokens,
            "cache_read_tokens": call.cache_read_input_tokens,
            "web_searches": call.web_search_requests,
            "cost_usd": round(cost, 6),
            "run_cost_usd": round(state["usage"]["cost_usd"], 6),
        },
    )
    return response


class AgentState(TypedDict):
    run_id: str  # identifies this run in logs, spans, and the metrics table
    owner: str  # caller identity this run's notes belong to; "" means nobody
    task: str  # the research question, or the follow-up question in followup mode
    mode: str  # "research" | "followup"
    topic_type: str  # "technical" | "contested" | "sparse" | "general"
    research_notes: str
    source_report: str  # followup mode: the report being asked about
    conversation: list  # followup mode: earlier {question, answer} turns
    draft: str  # the report, or the follow-up answer -- whatever the critic checks
    critic_feedback: str
    approved: bool
    reviewed: bool
    revision_count: int
    # followup mode: the responder found the notes could not answer the
    # question, and the supervisor has not acted on that yet. Set by the
    # responder, consumed (and cleared) by the supervisor when it routes.
    notes_insufficient: bool
    # followup mode: this turn has already had its one research pass. Both
    # reach rows set it; the insufficiency row reads it, which is what bounds
    # a follow-up to one pass and stops research -> insufficient -> research.
    followup_research_done: bool
    forced_stop_reason: str
    next_step: str
    iteration: int
    usage: dict  # running token and cost totals for this run
    trace: list


def initial_state(task: str, owner: str = "") -> AgentState:
    """A clean research run. Only the memory store persists across runs.

    `owner` is the caller this run's notes belong to -- what the researcher
    may recall and what it writes. The default of "" is the REPL, the eval
    harness and the CLI, none of which have a caller; the service always
    passes a real identity. It is an exact value, not a wildcard: a run owned
    by "" recalls only notes owned by "".
    """
    return {
        "run_id": uuid.uuid4().hex,
        "owner": owner,
        "task": task,
        "mode": "research",
        "topic_type": "",
        "research_notes": "",
        "source_report": "",
        "conversation": [],
        "draft": "",
        "critic_feedback": "",
        "approved": False,
        "reviewed": False,
        "revision_count": 0,
        # Both reach flags are per RUN, and a follow-up turn is a run -- so
        # `followup_state` resets them for free by building on this, and a new
        # turn gets a fresh pass allowance the way it gets a fresh budget.
        "notes_insufficient": False,
        "followup_research_done": False,
        "forced_stop_reason": "",
        "next_step": "",
        "iteration": 0,
        "usage": usage_accounting.new_usage(),
        "trace": [],
    }


def followup_state(previous: AgentState, question: str, owner: str = "") -> AgentState:
    """A follow-up turn grounded in `previous`.

    Accepts either a research run or an earlier follow-up, so chaining is just
    followup_state(last_state, q) every turn. Notes and the source report carry
    forward unchanged; each answered turn is appended to the conversation.

    A follow-up's owner is the caller asking it, and falls back to the previous
    turn's owner when there is no caller -- which is what keeps REPL chaining
    working. `previous` may also be a state blob persisted before Phase 12,
    which has no owner key at all, so it is read defensively; those runs are
    followups and never touch the note store anyway.
    """
    was_followup = previous.get("mode") == "followup"

    conversation = list(previous.get("conversation") or [])
    if was_followup and previous.get("draft"):
        conversation.append({"question": previous["task"], "answer": previous["draft"]})

    state = initial_state(question, owner=owner or previous.get("owner", ""))
    state.update(
        {
            "mode": "followup",
            "topic_type": previous.get("topic_type") or "general",
            "research_notes": previous.get("research_notes", ""),
            "source_report": (
                previous["source_report"] if was_followup else previous.get("draft", "")
            ),
            "conversation": conversation,
        }
    )
    return state


RESEARCH_STRATEGY = {
    "technical": "Prioritize precise figures, version numbers, and named sources. "
                 "Flag anything you couldn't verify with a specific source.",
    "contested": "Actively search for multiple viewpoints, not just the first "
                 "framing you find. Note where sources disagree.",
    "sparse": "This topic may have limited coverage. Broaden the search if initial "
              "results are thin, and explicitly note any gaps in available information.",
    "general": "Summarize the most relevant, well-supported facts.",
}

CRITIC_RUBRIC = {
    "technical": "Check especially for numbers, dates, or figures not explicitly "
                 "present in the research notes — these are the easiest ungrounded "
                 "claims to miss.",
    "contested": "Check that the draft presents competing viewpoints as viewpoints, "
                 "not as settled fact, if the research notes show disagreement.",
    "sparse": "Check that the draft doesn't overstate confidence where the research "
              "notes themselves flagged a gap or limited coverage.",
    "general": "Check that every claim in the draft is supported by the research notes.",
}


@retry_node("classifier")
def classifier_node(state: AgentState) -> AgentState:
    response = call_model(
        state,
        "classifier",
        max_tokens=20,
        thinking={"type": "disabled"},  # one-word label; no room (or need) for thinking
        output_config={"effort": "medium"},
        messages=[{
            "role": "user",
            "content": (
                f"Classify this research task into exactly one category: "
                f"technical, contested, sparse, or general.\n\n"
                f"technical = involves specific figures/versions/technical facts\n"
                f"contested = involves differing opinions or disputed claims\n"
                f"sparse = likely has limited web coverage (niche/local/very recent)\n"
                f"general = none of the above apply strongly\n\n"
                f"Task: {state['task']}\n\n"
                f"Respond with exactly one word: technical, contested, sparse, or general."
            ),
        }],
    )
    label = _text(response).strip().lower()
    state["topic_type"] = label if label in RESEARCH_STRATEGY else "general"
    state["trace"].append({"node": "classifier", "topic_type": state["topic_type"]})
    return state


@retry_node("researcher")
def researcher_node(state: AgentState) -> AgentState:
    store = memory()
    # This is the only node that embeds -- recall on the way in, the note on
    # the way out -- so it is the only node with an embedding bill. The meter
    # spans both, and it is opened and read inside this one function frame:
    # that is what makes the contextvar attribution safe when two runs are in
    # flight on different threads of the service's pool. The model call in the
    # middle reports nothing into it and is simply carried along.
    with usage_accounting.embedding_meter() as embeddings:
        # Scoped to the caller in both directions, and this is the whole of the
        # fix. Recall used to read one communal store, so a note written during
        # someone else's run arrived in this prompt -- and the draft built from
        # it is what the critic then reviews, which is how untrusted text from
        # one visitor could steer another visitor's report toward APPROVED. A
        # run now only ever reads what its own caller caused to be written.
        recalled = store.query(state["task"], top_k=3, owner=state["owner"])
        recalled_block = (
            "Relevant notes from previous research sessions:\n" + "\n".join(recalled) + "\n\n"
            if recalled else ""
        )

        response = call_model(
            state,
            "researcher",
            max_tokens=4000,
            thinking={"type": "adaptive"},
            output_config={"effort": "medium"},
            tools=[{"type": "web_search_20260209", "name": "web_search"}],
            messages=[{
                "role": "user",
                "content": (
                    f"{recalled_block}"
                    f"Search the web and summarize 4-5 concrete, recent facts "
                    f"relevant to: {state['task']}. Be specific and cite what you find. "
                    f"Prefer new information not already covered above. "
                    f"{RESEARCH_STRATEGY[state['topic_type']]}"
                ),
            }],
        )
        notes = _text(response)
        # Append, never replace. In research mode `existing` is always empty
        # here -- the supervisor only routes to this node when it is -- so the
        # branch exists for the follow-up pass, where replacing would swap the
        # session's note set for this pass's findings instead of enlarging it.
        # Nothing would go red: the critic grades the draft against whatever
        # `research_notes` holds, so the earlier turns would just quietly lose
        # the ground they were standing on.
        existing = state["research_notes"]
        state["research_notes"] = f"{existing}\n\n{notes}" if existing else notes
        # The stored note keeps only what this pass found, prefixed with the
        # task -- which in follow-up mode is the follow-up question, so the
        # note says which turn went and got it.
        store.add(f"[{state['task']}] {notes}", owner=state["owner"])

    # Nothing embedded means nothing to bill: a store backed by a fake embedder
    # reports nothing, and folding a zero-request meter would invent a $0.00
    # Voyage line item for a run that never called Voyage.
    if embeddings.requests:
        usage_accounting.record_embedding(
            state["usage"], embeddings.model, embeddings.total_tokens, embeddings.requests
        )
    state["trace"].append({
        "node": "researcher", "notes_length": len(notes),
        "recalled_from_memory": len(recalled),
    })
    return state


@retry_node("writer")
def writer_node(state: AgentState) -> AgentState:
    is_revision = bool(state["critic_feedback"])
    feedback_block = (
        f"\n\nPrevious critic feedback to address:\n{state['critic_feedback']}"
        if is_revision else ""
    )
    response = call_model(
        state,
        "writer",
        max_tokens=4000,
        thinking={"type": "adaptive"},
        output_config={"effort": "medium"},
        messages=[{
            "role": "user",
            "content": (
                f"Research notes:\n{state['research_notes']}\n\n"
                f"Write a concise, well-organized report answering: {state['task']}"
                f"{feedback_block}\n\n"
                f"Only state things supported by the research notes."
            ),
        }],
    )
    draft = _text(response)
    state["draft"] = draft
    state["reviewed"] = False
    if is_revision:
        state["revision_count"] += 1
    state["trace"].append({
        "node": "writer", "draft_length": len(draft),
        "revision_count": state["revision_count"],
    })
    return state


def _conversation_block(state: AgentState) -> str:
    if not state["conversation"]:
        return ""
    turns = "\n\n".join(
        f"Q: {turn['question']}\nA: {turn['answer']}" for turn in state["conversation"]
    )
    return f"\n\nEarlier follow-up questions in this conversation:\n{turns}"


INSUFFICIENCY_SENTINEL = "INSUFFICIENT:"


@retry_node("responder")
def responder_node(state: AgentState) -> AgentState:
    """Answer a follow-up question from the notes -- or say they cannot.

    Structurally this is the writer's twin: it writes into state["draft"] so
    the critic grades an answer with the same rubric it grades a report with.
    It has exactly two alternatives, and neither of them is guessing:

    1. answer from the notes and the report, or
    2. signal that the notes do not cover the question.

    Before this turn has spent its research pass, (2) is the sentinel below --
    a flag, not a draft. It ROUTES: the supervisor sends the turn to the
    researcher, and the window between the signal and the new notes produces
    no answer at all. After the pass it is prose -- "the research didn't cover
    that" is the honest answer once looking has been tried, and it ships as a
    draft the critic reviews like any other.

    So this node no longer "never searches"; what it never does is answer from
    the model's own knowledge, which was always the property that mattered.
    """
    is_revision = bool(state["critic_feedback"])
    feedback_block = (
        f"\n\nPrevious critic feedback to address:\n{state['critic_feedback']}"
        if is_revision else ""
    )
    # ONE boolean for both the prompt branch and the parse below. Gating them
    # separately is the bug that writes itself: a parse that outlives its
    # prompt turns a stray post-research "INSUFFICIENT:" -- text the model was
    # never asked for -- into a routing input.
    pre_research = not state["followup_research_done"]
    gap_instruction = (
        f"If the notes do not cover what was asked, respond with exactly "
        f"'{INSUFFICIENCY_SENTINEL} ' followed by one line naming what is "
        f"missing. Never answer from your own knowledge."
        if pre_research else
        "If the notes do not cover what was asked, say plainly "
        "that the research didn't cover it rather than guessing."
    )
    response = call_model(
        state,
        "responder",
        max_tokens=2000,
        thinking={"type": "adaptive"},
        output_config={"effort": "medium"},
        messages=[{
            "role": "user",
            "content": (
                f"Research notes:\n{state['research_notes']}\n\n"
                f"Report previously given to the user:\n{state['source_report']}"
                f"{_conversation_block(state)}\n\n"
                f"The user is now asking a follow-up question: {state['task']}\n\n"
                f"Answer it directly and concisely, using only the research notes "
                f"and the report above. Do not introduce facts from your own "
                f"knowledge. {gap_instruction}"
                f"{feedback_block}"
            ),
        }],
    )
    answer = _text(response)

    if pre_research and answer.strip().startswith(INSUFFICIENCY_SENTINEL):
        # The signal sets a flag and does nothing else. `draft` is left
        # untouched -- the sentinel text is never a draft, so it reaches
        # neither the critic nor the caller -- and `reviewed`, `revision_count`
        # and the usual trace entry are all skipped, because no answer was
        # produced to review, revise or measure. Parsed by fixed prefix, which
        # is exactly how `approved` is read off the critic; the supervisor
        # still routes on plain state (ADR-0001).
        state["notes_insufficient"] = True
        state["trace"].append({"node": "responder", "insufficient": True})
        return state

    state["draft"] = answer
    state["reviewed"] = False
    if is_revision:
        state["revision_count"] += 1
    state["trace"].append({
        "node": "responder", "answer_length": len(answer),
        "revision_count": state["revision_count"],
    })
    return state


@retry_node("critic")
def critic_node(state: AgentState) -> AgentState:
    subject = "answer" if state["mode"] == "followup" else "draft report"
    response = call_model(
        state,
        "critic",
        model=critic_model(),
        max_tokens=2000,
        thinking={"type": "adaptive"},
        output_config={"effort": "medium"},
        messages=[{
            "role": "user",
            "content": (
                f"Research notes:\n{state['research_notes']}\n\n"
                f"{subject.capitalize()}:\n{state['draft']}\n\n"
                f"Does the {subject} contain any claim NOT supported by the research notes? "
                f"{CRITIC_RUBRIC[state['topic_type']]} "
                f"Respond with exactly 'APPROVED' if it's fully grounded, "
                f"otherwise respond with 'REVISE: ' followed by specific feedback."
            ),
        }],
    )
    verdict = _text(response).strip()

    state["approved"] = verdict.startswith("APPROVED")
    state["critic_feedback"] = "" if state["approved"] else verdict
    state["reviewed"] = True
    state["trace"].append({"node": "critic", "approved": state["approved"]})
    return state


def supervisor_node(state: AgentState) -> AgentState:
    """The routing table. Plain Python over state -- no model call decides what
    runs next, which is what makes the control flow deterministic and testable.

    `mode` changes which node produces the text -- the writer (from web
    research) or the responder (from notes already gathered) -- and, since
    Phase 17, gates the two rows that can send a follow-up to the researcher.
    The caps, the critic hop, and the revision loop are identical either way,
    and the caps sit above everything: a follow-up that reaches for new
    information is still a run under the same guardrails, so a capped or
    over-budget one ENDs with its own honest reason and never researches.
    """
    state["iteration"] += 1
    author = "responder" if state["mode"] == "followup" else "writer"
    budget = usage_accounting.max_run_cost_usd()
    # Why this turn is being sent to the researcher, when it is a follow-up.
    # Folded into the one trace entry below rather than appended separately:
    # `/sessions/{id}/trace` is the surface of record, and one supervisor
    # entry per decision is what makes it readable.
    followup_research = ""

    if state["iteration"] > MAX_ITERATIONS:
        state["next_step"] = "done"
        state["forced_stop_reason"] = "max_iterations_exceeded"
    elif state["revision_count"] > MAX_REVISIONS:
        state["next_step"] = "done"
        state["forced_stop_reason"] = "max_revisions_exceeded"
    elif budget > 0 and state["usage"]["cost_usd"] > budget:
        # The iteration and revision caps bound how many calls a run makes;
        # this bounds what they cost. Checked between nodes, because cost is
        # only knowable after a call returns -- so a run can overshoot by at
        # most one node, not by an unbounded amount.
        state["next_step"] = "done"
        state["forced_stop_reason"] = "budget_exceeded"
    elif state["mode"] == "followup" and not state["research_notes"]:
        # A follow-up with nothing to follow up on. This row used to END the
        # run: refusing beat silently answering from the model's own
        # knowledge, which is the one thing this whole pipeline exists to
        # prevent. That is still true of answering -- it was never an argument
        # against going and getting notes first, which is the honest move and
        # is what this row does now. The guarantee that replaces "a follow-up
        # never searches" is the window: nothing ships until the researcher
        # has gathered and the critic has reviewed, so there is still no path
        # from an unanswerable question to an unreviewed answer.
        #
        # The row stays HERE, above the classifier row, and that position is
        # load-bearing: it is what keeps "a follow-up never classifies" a
        # property of the table rather than of how `followup_state` happens to
        # be built.
        state["next_step"] = "researcher"
        state["followup_research_done"] = True
        followup_research = "no_prior_research"
    elif (
        state["mode"] == "followup"
        and state["notes_insufficient"]
        and not state["followup_research_done"]
    ):
        # Notes exist but the responder said they do not cover the question.
        # One pass, and the flag is what bounds it: a post-research
        # insufficiency signal cannot buy a second one, so a follow-up can
        # never loop research -> insufficient -> research.
        state["next_step"] = "researcher"
        state["followup_research_done"] = True
        state["notes_insufficient"] = False
        followup_research = "notes_insufficient"
    elif not state["topic_type"]:
        state["next_step"] = "classifier"
    elif not state["research_notes"]:
        state["next_step"] = "researcher"
    elif not state["draft"]:
        state["next_step"] = author
    elif not state["reviewed"]:
        state["next_step"] = "critic"
    elif not state["approved"]:
        state["next_step"] = author
    else:
        state["next_step"] = "done"

    decision = {"node": "supervisor", "routed_to": state["next_step"]}
    if followup_research:
        # `no_prior_research` used to be a forced stop reason. It is this
        # instead now: not "the run gave up", but "this is why the follow-up
        # went looking". Without it on the record, a reach the design intended
        # and a reach caused by a routing row moving by accident look
        # identical, and both look green.
        decision["followup_research"] = followup_research
    state["trace"].append(decision)

    if state["next_step"] == "done":
        log.info(
            "run finished",
            extra={
                "event": "run_finished",
                "run_id": state.get("run_id", ""),
                "mode": state["mode"],
                "topic_type": state["topic_type"],
                "approved": bool(state["approved"]),
                "forced_stop_reason": state["forced_stop_reason"],
                "iterations": state["iteration"],
                "revisions": state["revision_count"],
                "model_calls": state["usage"]["calls"],
                "cost_usd": round(state["usage"]["cost_usd"], 6),
            },
        )
    return state


def route(
    state: AgentState,
) -> Literal["classifier", "researcher", "writer", "responder", "critic", "__end__"]:
    return state["next_step"] if state["next_step"] != "done" else "__end__"


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("classifier", classifier_node)
    graph.add_node("researcher", researcher_node)
    graph.add_node("writer", writer_node)
    graph.add_node("responder", responder_node)
    graph.add_node("critic", critic_node)

    graph.set_entry_point("supervisor")
    for worker in ("classifier", "researcher", "writer", "responder", "critic"):
        graph.add_edge(worker, "supervisor")

    graph.add_conditional_edges(
        "supervisor",
        route,
        {
            "classifier": "classifier",
            "researcher": "researcher",
            "writer": "writer",
            "responder": "responder",
            "critic": "critic",
            "__end__": END,
        },
    )
    return graph.compile()


app = build_graph()


if __name__ == "__main__":
    result = app.invoke(initial_state(
        "What are the most notable recent developments in agentic AI "
        "frameworks and agent design patterns?"
    ))

    print("=== FINAL REPORT ===\n")
    print(result["draft"])
    if result["forced_stop_reason"]:
        print(f"\n(note: loop ended via guardrail — {result['forced_stop_reason']}, "
              f"draft may not be critic-approved)")
    print("\n=== EXECUTION TRACE ===")
    for step in result["trace"]:
        print(" ", step)
