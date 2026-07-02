from __future__ import annotations

import logging

from kg_building.agents.session import AgentSession
from kg_building.extraction.types import AgentTask, TaskType
from kg_building.llm.client import LLMClient

log = logging.getLogger(__name__)

_SYSTEM = """You are the planning agent for a soil-health knowledge-graph pipeline.
You are given the chunk manifest for one research paper (chunk ids, section labels,
sizes). Decide the ORDER of work for the extraction agents that follow you.

Rules of thumb (you may deviate if the paper's structure warrants it):
- A STUDY_CONTEXT task should usually run first, pointed at methods/site chunks —
  its output (region, climate, soil, treatments, duration) becomes a global
  condition source for every finding extracted afterward.
- Then an EXTRACT_CHUNK task per chunk. Prioritize Methods and Results chunks
  (that's where causal claims and quantitative outcomes live) over Introduction/
  Discussion, but don't skip chunks entirely — background chunks often name
  entities used later.
- You do NOT need to plan repairs (chain completion, condition fixes) — a critic
  agent handles that after extraction, dynamically, based on what's actually
  missing.

Return ONLY a JSON object of this exact shape:
{
  "reasoning": "one or two sentences",
  "tasks": [
    {"id": "t_0000", "task_type": "STUDY_CONTEXT", "chunk_id": null, "note": "...", "priority": 0},
    {"id": "t_0001", "task_type": "EXTRACT_CHUNK", "chunk_id": "<chunk_id>", "note": "...", "priority": 1},
    ...
  ]
}
task_type must be one of: STUDY_CONTEXT, EXTRACT_CHUNK.
"""


def plan(client: LLMClient, session: AgentSession) -> None:
    manifest = [{"chunk_id": c.chunk_id, "section": c.section_hint, "chars": len(c.text)}
                for c in session.chunks]
    user = f"paper_source: {session.paper_source}\n\nchunk manifest:\n{manifest}"

    data = client.complete_json(
        [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": user}],
        temperature=0.1, max_tokens=2500,
        agent_name="planner",
        trace_writer=session.trace,
        trace_meta={"paper_source": session.paper_source},
    )

    reasoning = data.get("reasoning", "")
    raw_tasks = data.get("tasks", [])
    session.log(f"[planner] {reasoning or '(no reasoning given)'}")

    if not raw_tasks:
        log.warning("Planner returned no tasks — falling back to a default plan")
        raw_tasks = _fallback_plan(session)

    for i, t in enumerate(raw_tasks):
        try:
            task = AgentTask(
                id=t.get("id") or f"t_{i:04d}",
                task_type=TaskType(t["task_type"]),
                chunk_id=t.get("chunk_id"),
                note=t.get("note", ""),
                origin="planner",
                priority=t.get("priority", i),
            )
            session.enqueue(task)
        except Exception as exc:
            log.warning("Skipping malformed planned task %s: %s", t, exc)


def _fallback_plan(session: AgentSession) -> list[dict]:
    tasks = [{"id": "t_0000", "task_type": "STUDY_CONTEXT", "chunk_id": None,
              "note": "extract study-wide context", "priority": 0}]
    for i, c in enumerate(session.chunks, 1):
        tasks.append({"id": f"t_{i:04d}", "task_type": "EXTRACT_CHUNK", "chunk_id": c.chunk_id,
                       "note": f"extract entities/findings from {c.section_hint}", "priority": i})
    return tasks
