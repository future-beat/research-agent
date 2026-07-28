#!/usr/bin/env python3
"""
Interactive terminal REPL for the LangGraph research agent.

Each turn takes a research task, runs the full supervisor pipeline
(classifier -> researcher -> writer -> critic), and prints the report.
Turns build on each other through VectorMemory: the researcher recalls
notes from earlier tasks in this session and from previous sessions.

Usage:  .venv/bin/python chat.py
Commands:  /help  /memory  /trace  /exit
"""

# Load .env BEFORE importing the agent: research_agent constructs
# anthropic.Anthropic() and VectorMemory() at module scope, and both read
# their keys from the environment at that moment. Importing first would
# read an empty environment.
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # python-dotenv absent -- fall back to a pre-exported env
    pass

import sys

import anthropic

from research_agent import MAX_REVISIONS, app, memory

# Announced as each node finishes. supervisor is omitted deliberately --
# it fires between every other node and would drown out the real progress.
NODE_LABELS = {
    "classifier": "classifying topic",
    "researcher": "searching the web",
    "writer": "drafting report",
    "critic": "fact-checking draft",
}

_COLOR = sys.stdout.isatty()


def _dim(s: str) -> str:
    return f"\033[2m{s}\033[0m" if _COLOR else s


def _bold(s: str) -> str:
    return f"\033[1m{s}\033[0m" if _COLOR else s


def fresh_state(task: str) -> dict:
    """A clean AgentState. Only VectorMemory persists across turns."""
    return {
        "task": task,
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
    }


def run_task(task: str) -> dict | None:
    """
    Stream the graph so the user sees progress instead of a silent
    multi-minute pause. Returns the final state, or None if the run
    failed or was interrupted.
    """
    final_state = None
    try:
        for chunk in app.stream(fresh_state(task)):
            for node_name, node_state in chunk.items():
                final_state = node_state

                label = NODE_LABELS.get(node_name)
                if not label:
                    continue

                detail = ""
                if node_name == "classifier":
                    detail = f" -> {node_state['topic_type']}"
                elif node_name == "researcher":
                    recalled = node_state["trace"][-1].get("recalled_from_memory", 0)
                    if recalled:
                        detail = f" (recalled {recalled} note(s) from memory)"
                elif node_name == "writer" and node_state["revision_count"]:
                    detail = f" (revision {node_state['revision_count']})"
                elif node_name == "critic":
                    detail = " -> approved" if node_state["approved"] else " -> revision requested"

                print(_dim(f"  ... {label}{detail}"), flush=True)

    except KeyboardInterrupt:
        print(_dim("\n  ^C -- run cancelled, returning to prompt"))
        return None
    except anthropic.RateLimitError as e:
        retry = e.response.headers.get("retry-after", "?")
        print(f"  rate limited -- retry after {retry}s")
        return None
    except anthropic.APIStatusError as e:
        print(f"  API error {e.status_code}: {e.message}")
        return None
    except anthropic.APIConnectionError:
        print("  network error -- check your connection and try again")
        return None

    return final_state


def print_report(state: dict) -> None:
    print()
    print(_bold("=== REPORT ==="))
    print()
    print(state["draft"])

    if state["forced_stop_reason"]:
        print()
        print(
            _dim(
                f"  note: stopped by guardrail ({state['forced_stop_reason']}) -- "
                f"this draft was not critic-approved"
            )
        )

    revisions = state["revision_count"]
    summary = (
        f"  {state['topic_type']} topic | {state['iteration']} supervisor turns | "
        f"{revisions}/{MAX_REVISIONS} revisions | "
        f"{'approved' if state['approved'] else 'not approved'}"
    )
    print()
    print(_dim(summary))
    print()


HELP = """
Type a research question and press Enter. Each run does a full pass:
classify -> web search -> draft -> fact-check (with up to
{max_rev} revisions if the critic pushes back).

  /help    this message
  /memory  how many notes are in the persisted vector store
  /trace   node-by-node trace of the last run
  /exit    quit (Ctrl-D also works)

Ctrl-C during a run cancels it and returns you to the prompt.
""".strip()


def main() -> int:
    print(_bold("Research agent") + _dim("  --  /help for commands, /exit to quit"))
    print()

    last_state: dict | None = None

    while True:
        try:
            task = input(_bold("task> ")).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        if not task:
            continue

        if task in ("/exit", "/quit", "exit", "quit"):
            return 0

        if task == "/help":
            print(HELP.format(max_rev=MAX_REVISIONS))
            print()
            continue

        if task == "/memory":
            n = len(memory.entries)
            print(_dim(f"  {n} note(s) stored in {memory.path}"))
            print()
            continue

        if task == "/trace":
            if not last_state:
                print(_dim("  no runs yet this session"))
            else:
                for step in last_state["trace"]:
                    print(_dim(f"  {step}"))
            print()
            continue

        if task.startswith("/"):
            print(_dim(f"  unknown command {task!r} -- try /help"))
            print()
            continue

        state = run_task(task)
        if state:
            last_state = state
            print_report(state)


if __name__ == "__main__":
    raise SystemExit(main())
