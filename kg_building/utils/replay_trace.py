"""
Pretty-print an agent trace JSONL file for debugging.

Usage:
    python -m kg_building.utils.replay_trace data/output/traces/soil1.txt.jsonl
    python -m kg_building.utils.replay_trace data/output/traces/soil1.txt.jsonl --task t_0003
    python -m kg_building.utils.replay_trace data/output/traces/soil1.txt.jsonl --agent critic
    python -m kg_building.utils.replay_trace data/output/traces/soil1.txt.jsonl --full   # show full prompt text
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

_W = 100


def _trunc(s: str, full: bool) -> str:
    s = str(s)
    return s if full else (s if len(s) <= _W else s[:_W] + "…")


def replay(path: str, task_filter: str | None, agent_filter: str | None, full: bool) -> None:
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        ev = json.loads(line)
        if task_filter and ev.get("task_id") != task_filter:
            continue
        if agent_filter and ev.get("agent") != agent_filter:
            continue

        kind = ev.get("kind", "?")
        agent = ev.get("agent", "?")
        task_id = ev.get("task_id", "")
        prefix = f"[{agent}{'/' + task_id if task_id else ''}]"

        if kind == "agent_start":
            print(f"\n{'=' * 90}\n{prefix} START")
            print(f"  system: {_trunc(ev.get('system_prompt', ''), full)}")
            print(f"  user  : {_trunc(ev.get('user_prompt', ''), full)}")
        elif kind == "call_input":
            print(f"\n{'=' * 90}\n{prefix} CALL (json mode)")
            for m in ev.get("messages", []):
                print(f"  {m.get('role')}: {_trunc(m.get('content', ''), full)}")
        elif kind == "call_output":
            print(f"  -> {_trunc(ev.get('raw', ''), full)}")
        elif kind == "assistant_turn":
            step = ev.get("step")
            content = ev.get("content", "")
            tcs = ev.get("tool_calls", [])
            if content:
                print(f"  [step {step}] assistant: {_trunc(content, full)}")
            for tc in tcs:
                fn = tc.get("function", {})
                print(f"  [step {step}] -> tool_call: {fn.get('name')}({_trunc(fn.get('arguments', ''), full)})")
        elif kind == "tool_call":
            print(f"  [step {ev.get('step')}] tool={ev.get('tool')} args={_trunc(ev.get('args'), full)}")
            print(f"  [step {ev.get('step')}]   result: {_trunc(ev.get('result', ''), full)}")
        elif kind == "agent_end":
            print(f"{prefix} END (reason={ev.get('reason')}, steps={ev.get('steps')})")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("trace_file")
    p.add_argument("--task", default=None, help="Filter to one task_id (e.g. t_0003, critic_round_1)")
    p.add_argument("--agent", default=None, choices=["planner", "worker", "critic"])
    p.add_argument("--full", action="store_true", help="Don't truncate long text")
    args = p.parse_args()
    replay(args.trace_file, args.task, args.agent, args.full)


if __name__ == "__main__":
    main()
