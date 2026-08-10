#!/usr/bin/env python3
"""
Interactive terminal REPL for the LangGraph research agent.

A bare question runs the full supervisor pipeline (classifier -> researcher ->
writer -> critic) and prints a report. `/ask <question>` runs a follow-up
against the notes from that report instead of searching again -- cheap, fast,
and grounded in the same source of truth.

Turns also build on each other through the vector store: the researcher
recalls notes from earlier tasks in this session and from previous sessions.

Usage:  .venv/bin/python chat.py
Commands:  /ask  /help  /memory  /trace  /exit
"""

# Load .env BEFORE importing the agent so the API keys are present by the time
# anything reads them. (The clients are lazy now, so this is belt-and-braces
# rather than load-bearing -- but it keeps the ordering obvious.)
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # python-dotenv absent -- fall back to a pre-exported env
    pass

import sys

import anthropic

from research_agent.graph import (
    MAX_REVISIONS,
    app,
    followup_state,
    initial_state,
    memory,
)

# Announced as each node finishes. supervisor is omitted deliberately --
# it fires between every other node and would drown out the real progress.
NODE_LABELS = {
    "classifier": "classifying topic",
    "researcher": "searching the web",
    "writer": "drafting report",
    "responder": "answering from prior notes",
    "critic": "fact-checking draft",
}

_COLOR = sys.stdout.isatty()


def _dim(s: str) -> str:
    return f"\033[2m{s}\033[0m" if _COLOR else s


def _bold(s: str) -> str:
    return f"\033[1m{s}\033[0m" if _COLOR else s


def run(state: dict) -> dict | None:
    """
    Stream the graph so the user sees progress instead of a silent
    multi-minute pause. Returns the final state, or None if the run
    failed or was interrupted.
    """
    final_state = None
    try:
        for chunk in app.stream(state):
            for node_name, node_state in chunk.items():
                final_state = node_state

                label = NODE_LABELS.get(node_name)
                if not label:
                    continue

                # Retries are logged inside the node, so they only surface once
                # it finishes -- but a slow run should say why it was slow.
                retries = sum(
                    1
                    for entry in node_state["trace"]
                    if entry.get("node") == node_name and entry.get("event") == "retry"
                )

                detail = ""
                if node_name == "classifier":
                    detail = f" -> {node_state['topic_type']}"
                elif node_name == "researcher":
                    recalled = node_state["trace"][-1].get("recalled_from_memory", 0)
                    if recalled:
                        detail = f" (recalled {recalled} note(s) from memory)"
                elif node_name in ("writer", "responder") and node_state["revision_count"]:
                    detail = f" (revision {node_state['revision_count']})"
                elif node_name == "critic":
                    detail = " -> approved" if node_state["approved"] else " -> revision requested"

                if retries:
                    detail += f" [{retries} retr{'y' if retries == 1 else 'ies'}]"

                print(_dim(f"  ... {label}{detail}"), flush=True)

    except KeyboardInterrupt:
        print(_dim("\n  ^C -- run cancelled, returning to prompt"))
        return None
    except anthropic.RateLimitError as e:
        retry = e.response.headers.get("retry-after", "?")
        print(f"  rate limited even after backoff -- retry after {retry}s")
        return None
    except anthropic.APIStatusError as e:
        print(f"  API error {e.status_code}: {e.message}")
        return None
    except anthropic.APIConnectionError:
        print("  network error -- check your connection and try again")
        return None

    return final_state


def print_result(state: dict) -> None:
    is_followup = state["mode"] == "followup"

    print()
    print(_bold("=== ANSWER ===" if is_followup else "=== REPORT ==="))
    print()
    print(state["draft"] or _dim("(nothing produced)"))

    if state["forced_stop_reason"]:
        # One line for every reason. The special case that used to live here
        # explained a follow-up that stopped because it had no notes behind
        # it; since Phase 17 that turn goes and researches instead, so every
        # stop left is a guardrail, and a guardrail says what it is.
        reason = state["forced_stop_reason"]
        print()
        print(_dim(f"  note: stopped by guardrail ({reason}) -- this was not critic-approved"))

    print()
    print(
        _dim(
            f"  {'follow-up' if is_followup else state['topic_type'] + ' topic'} | "
            f"{state['iteration']} supervisor turns | "
            f"{state['revision_count']}/{MAX_REVISIONS} revisions | "
            f"{'approved' if state['approved'] else 'not approved'}"
        )
    )
    print()


HELP = """
Type a research question and press Enter. Each run does a full pass:
classify -> web search -> draft -> fact-check (with up to
{max_rev} revisions if the critic pushes back).

  /ask <q>  follow up on the last run. Answered from that run's notes, or --
            when they can't cover it -- from one fresh search first.
            Chains: each /ask sees the earlier ones.
  /help     this message
  /memory   how many notes are in the vector store, and which backend
  /trace    node-by-node trace of the last run
  /exit     quit (Ctrl-D also works)

Ctrl-C during a run cancels it and returns you to the prompt.
""".strip()


def main() -> int:
    print(_bold("Research agent") + _dim("  --  /help for commands, /exit to quit"))
    print()

    last_state: dict | None = None

    while True:
        try:
            line = input(_bold("task> ")).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        if not line:
            continue

        if line in ("/exit", "/quit", "exit", "quit"):
            return 0

        if line == "/help":
            print(HELP.format(max_rev=MAX_REVISIONS))
            print()
            continue

        if line == "/memory":
            print(_dim(f"  {memory().describe()}"))
            print()
            continue

        if line == "/trace":
            if not last_state:
                print(_dim("  no runs yet this session"))
            else:
                for step in last_state["trace"]:
                    print(_dim(f"  {step}"))
            print()
            continue

        if line == "/ask" or line.startswith("/ask "):
            question = line[len("/ask"):].strip()
            if not question:
                print(_dim("  usage: /ask <question about the last run>"))
                print()
                continue
            if not last_state:
                print(_dim("  nothing to follow up on yet -- ask a research question first"))
                print()
                continue
            state = run(followup_state(last_state, question))
        elif line.startswith("/"):
            print(_dim(f"  unknown command {line!r} -- try /help"))
            print()
            continue
        else:
            state = run(initial_state(line))

        if state:
            last_state = state
            print_result(state)


if __name__ == "__main__":
    raise SystemExit(main())
