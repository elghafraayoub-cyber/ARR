from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

from kg_building.agents import critic, planner, worker
from kg_building.agents.session import AgentSession
from kg_building.chunking.chunker import chunk as chunk_text
from kg_building.graph.storage import KGStorage
from kg_building.llm.client import LLMClient
from kg_building.utils.trace import TraceWriter

log = logging.getLogger(__name__)


def process_paper(
    client: LLMClient,
    storage: KGStorage,
    paper_source: str,
    text: str,
    max_critic_rounds: int = 3,
    trace_dir: str | Path = "data/output/traces",
    on_checkpoint: Callable[[KGStorage, str], None] | None = None,
) -> AgentSession:
    """
    Plan -> Work -> Critique -> Repair, looping until the critic approves or
    max_critic_rounds is reached. This is the agentic replacement for the old
    fixed Pass A / Pass B / Pass C pipeline: the number of extraction and
    repair steps is decided at runtime by the Planner and Critic, not fixed
    in code.

    Every prompt/response/tool-call for every agent on this paper is written
    to `<trace_dir>/<paper_source>.jsonl` for debugging — see the README's
    "Debugging" section for how to read it.

    `on_checkpoint`, if given, is called with (storage, stage_label) at the
    same points storage.save() is called — used by the backend to project
    the graph into SQLite as the run progresses, without touching this
    function's own behavior when left as None (the CLI's default).
    """
    chunks = chunk_text(text, paper_source)
    safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in paper_source)
    trace = TraceWriter(Path(trace_dir) / f"{safe_name}.jsonl")
    session = AgentSession(paper_source=paper_source, chunks=chunks, storage=storage, trace=trace)
    session.log(f"=== {paper_source}: {len(chunks)} chunks ===")

    planner.plan(client, session)

    round_no = 0
    try:
        while True:
            round_no += 1
            drained = _drain_queue(client, session)
            session.log(f"[orchestrator] round {round_no}: executed {drained} task(s)")
            storage.record_extraction(paper_source, f"round_{round_no}", note=f"{drained} tasks")
            storage.save()
            if on_checkpoint:
                on_checkpoint(storage, f"round_{round_no}_extract")

            if round_no > max_critic_rounds:
                session.log("[orchestrator] max critic rounds reached — finalizing without further review")
                break

            approved = critic.review(client, session, round_no=round_no)
            storage.save()
            if on_checkpoint:
                on_checkpoint(storage, f"round_{round_no}_critic")
            if approved:
                session.log("[orchestrator] critic approved — done")
                break
            # else: critic queued repair tasks -> loop back and drain them
    finally:
        trace.close()

    return session


def _drain_queue(client: LLMClient, session: AgentSession) -> int:
    count = 0
    while True:
        task = session.next_task()
        if task is None:
            break
        worker.run_task(client, session, task)
        count += 1
    return count
