from __future__ import annotations

import json
from pathlib import Path


def _format_event(event: dict) -> str | None:
    """Mirrors the human-readable one-line format the CLI already prints via
    logging in kg_building/llm/client.py's run_agent_loop, so the frontend's
    live log panel reads the same way the console does — this is the
    "Explainability Panel" analog, built from the existing trace JSONL
    instead of a websocket/event-bus feed."""
    kind = event.get("kind")
    agent = event.get("agent", "?")
    tag = f"[{agent}" + (f"/{event['task_id']}" if event.get("task_id") else "") + "]"

    if kind == "agent_start":
        return f"{tag} starting"
    if kind == "assistant_turn":
        step = event.get("step", "?")
        tool_calls = event.get("tool_calls") or []
        if tool_calls:
            names = ", ".join(tc["function"]["name"] for tc in tool_calls)
            return f"{tag} step {step} -> calling: {names}"
        return f"{tag} step {step} -> no tool call (stopping)"
    if kind == "tool_call":
        step = event.get("step", "?")
        tool = event.get("tool", "?")
        result = str(event.get("result", ""))[:120]
        return f"{tag} step {step} tool={tool} -> {result}"
    if kind == "agent_end":
        return f"{tag} completed via '{event.get('reason')}' ({event.get('steps')} steps)"
    return None


def tail_trace_lines(trace_path: str | Path | None, n: int = 50) -> list[str]:
    if not trace_path:
        return []
    path = Path(trace_path)
    if not path.exists():
        return []
    try:
        raw_lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []

    formatted: list[str] = []
    for line in raw_lines[-500:]:  # cap how much raw JSONL we parse per request
        try:
            event = json.loads(line)
        except Exception:
            continue
        formatted_line = _format_event(event)
        if formatted_line:
            formatted.append(formatted_line)
    return formatted[-n:]
