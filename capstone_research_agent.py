"""
CAPSTONE: Research-and-Report Agent System

Architecture (supervisor pattern, extended with a critic + persisted memory
+ topic-type classification for generalizing across any subject):

    supervisor -> classifier (runs once) -> supervisor
               -> researcher (recalls + stores via VectorMemory) -> supervisor
               -> writer -> supervisor
                                  |
                              critic checks draft
                                  |
                 approved? -> END : back to writer (capped by MAX_REVISIONS)

Requires: pip install langgraph anthropic voyageai
Requires: ANTHROPIC_API_KEY and VOYAGE_API_KEY in your environment
"""

from typing import TypedDict, Literal
import anthropic

client = anthropic.Anthropic()

from langgraph.graph import StateGraph, END
from vector_memory import VectorMemory

memory = VectorMemory()

MAX_ITERATIONS = 8
MAX_REVISIONS = 2


class AgentState(TypedDict):
    task: str
    topic_type: str  # "technical" | "contested" | "sparse" | "general"
    research_notes: str
    draft: str
    critic_feedback: str
    approved: bool
    reviewed: bool
    revision_count: int
    forced_stop_reason: str
    next_step: str
    iteration: int
    trace: list


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


def classifier_node(state: AgentState) -> AgentState:
    response = client.messages.create(
        model="claude-sonnet-5",
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
    label = "".join(b.text for b in response.content if b.type == "text").strip().lower()
    state["topic_type"] = label if label in RESEARCH_STRATEGY else "general"
    state["trace"].append({"node": "classifier", "topic_type": state["topic_type"]})
    return state


def researcher_node(state: AgentState) -> AgentState:
    recalled = memory.query(state["task"], top_k=3)
    recalled_block = (
        f"Relevant notes from previous research sessions:\n" + "\n".join(recalled) + "\n\n"
        if recalled else ""
    )

    response = client.messages.create(
        model="claude-sonnet-5",
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
    notes = "".join(b.text for b in response.content if b.type == "text")
    state["research_notes"] = notes
    memory.add(f"[{state['task']}] {notes}")
    state["trace"].append({
        "node": "researcher", "notes_length": len(notes),
        "recalled_from_memory": len(recalled),
    })
    return state


def writer_node(state: AgentState) -> AgentState:
    is_revision = bool(state["critic_feedback"])
    feedback_block = (
        f"\n\nPrevious critic feedback to address:\n{state['critic_feedback']}"
        if is_revision else ""
    )
    response = client.messages.create(
        model="claude-sonnet-5",
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
    draft = "".join(b.text for b in response.content if b.type == "text")
    state["draft"] = draft
    state["reviewed"] = False
    if is_revision:
        state["revision_count"] += 1
    state["trace"].append({
        "node": "writer", "draft_length": len(draft),
        "revision_count": state["revision_count"],
    })
    return state


def critic_node(state: AgentState) -> AgentState:
    response = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=2000,
        thinking={"type": "adaptive"},
        output_config={"effort": "medium"},
        messages=[{
            "role": "user",
            "content": (
                f"Research notes:\n{state['research_notes']}\n\n"
                f"Draft report:\n{state['draft']}\n\n"
                f"Does the draft contain any claim NOT supported by the research notes? "
                f"{CRITIC_RUBRIC[state['topic_type']]} "
                f"Respond with exactly 'APPROVED' if it's fully grounded, "
                f"otherwise respond with 'REVISE: ' followed by specific feedback."
            ),
        }],
    )
    verdict = "".join(b.text for b in response.content if b.type == "text").strip()

    state["approved"] = verdict.startswith("APPROVED")
    state["critic_feedback"] = "" if state["approved"] else verdict
    state["reviewed"] = True
    state["trace"].append({"node": "critic", "approved": state["approved"]})
    return state


def supervisor_node(state: AgentState) -> AgentState:
    state["iteration"] += 1

    if state["iteration"] > MAX_ITERATIONS:
        state["next_step"] = "done"
        state["forced_stop_reason"] = "max_iterations_exceeded"
    elif state["revision_count"] > MAX_REVISIONS:
        state["next_step"] = "done"
        state["forced_stop_reason"] = "max_revisions_exceeded"
    elif not state["topic_type"]:
        state["next_step"] = "classifier"
    elif not state["research_notes"]:
        state["next_step"] = "researcher"
    elif not state["draft"]:
        state["next_step"] = "writer"
    elif not state["reviewed"]:
        state["next_step"] = "critic"
    elif not state["approved"]:
        state["next_step"] = "writer"
    else:
        state["next_step"] = "done"

    state["trace"].append({"node": "supervisor", "routed_to": state["next_step"]})
    return state


def route(state: AgentState) -> Literal["classifier", "researcher", "writer", "critic", "__end__"]:
    return state["next_step"] if state["next_step"] != "done" else "__end__"


graph = StateGraph(AgentState)
graph.add_node("supervisor", supervisor_node)
graph.add_node("classifier", classifier_node)
graph.add_node("researcher", researcher_node)
graph.add_node("writer", writer_node)
graph.add_node("critic", critic_node)

graph.set_entry_point("supervisor")
graph.add_edge("classifier", "supervisor")
graph.add_edge("researcher", "supervisor")
graph.add_edge("writer", "supervisor")
graph.add_edge("critic", "supervisor")

graph.add_conditional_edges(
    "supervisor",
    route,
    {"classifier": "classifier", "researcher": "researcher", "writer": "writer",
     "critic": "critic", "__end__": END},
)

app = graph.compile()


if __name__ == "__main__":
    result = app.invoke({
        "task": "What are the most notable recent developments in agentic AI frameworks and agent design patterns?",
        "topic_type": "",
        "research_notes": "",
        "draft": "",
        "critic_feedback": "",
        "approved": False,
        "reviewed": False,
        "revision_count": 0,
        "forced_stop_reason": "",
        "next_step": "",
        "iteration": 0,
        "trace": [],
    })

    print("=== FINAL REPORT ===\n")
    print(result["draft"])
    if result["forced_stop_reason"]:
        print(f"\n(note: loop ended via guardrail — {result['forced_stop_reason']}, "
              f"draft may not be critic-approved)")
    print("\n=== EXECUTION TRACE ===")
    for step in result["trace"]:
        print(" ", step)
