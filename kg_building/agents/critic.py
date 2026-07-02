from __future__ import annotations

import logging

from kg_building.agents.session import AgentSession
from kg_building.agents.tools import CRITIC_TOOLS, dispatch_critic
from kg_building.llm.client import LLMClient

log = logging.getLogger(__name__)

_SYSTEM = """You are the critic agent for a soil-health knowledge-graph pipeline. Extraction
workers have already processed this paper. Your job is to INSPECT the resulting graph and decide
whether it's good enough, or whether specific gaps are worth repairing.

Use every one of these tools each round — go through everything each tool returns, not a sample:
- list_orphan_entities — an isolated entity (no finding connects it to anything) is a defect.
  Queue an ORPHAN_REPAIR naming the chunk it most likely connects from. Only skip one if you
  genuinely cannot ground a likely connection in this paper.
- list_duplicate_entity_candidates — entity pairs whose names likely refer to the same concept
  (e.g. an abbreviation and its full form) that fell below the auto-merge threshold at creation
  time. If two clearly are the same thing, call merge_entities directly — do not queue a repair
  task for this, it's a direct graph edit you can do yourself right now.
- list_vacuous_conditions — conditions whose text carries no information beyond the entity name
  it's attached to. These inflate condition_coverage without adding real scope. Queue a
  CONDITION_REPAIR for each, naming the chunk/study-context source of the real condition.
- list_findings_missing_conditions — worth repairing if you can point to WHERE the condition
  information likely lives (usually the study context, or a nearby chunk). Don't queue a repair
  you can't ground.
- list_broken_chains — a management practice jumping straight to an outcome with no mechanism.
  Queue a CHAIN_COMPLETION repair naming which chunk to re-check.
- verify_quote — spot-check findings to catch hallucinated evidence quotes. If a quote isn't
  grounded, queue a QUOTE_REVERIFY repair.

Review every item each tool surfaces and queue a repair (or merge) for every clearly-fixable
gap — only skip ones you can't ground in a specific chunk or study-context field. Batch related
issues into one repair task where it makes sense (e.g. several orphan entities that likely all
connect via the same chunk/section go in ONE ORPHAN_REPAIR note listing all of them, not one
task per entity) so thoroughness doesn't turn into a flood of near-duplicate tasks. Call approve
once you've triaged everything the tools returned, with a short summary.
"""


def review(client: LLMClient, session: AgentSession, max_steps: int = 30, round_no: int = 1) -> bool:
    """Returns True if the critic approved (no more repairs queued this round)."""
    stats = session.storage.stats()
    user = (
        f"paper_source: {session.paper_source}\n"
        f"graph stats: {stats}\n\n"
        "Review the graph using your tools and either queue targeted repairs or approve."
    )

    def _dispatch(name: str, args: dict) -> str:
        return dispatch_critic(name, args, session)

    session.log(f"[critic] reviewing graph (round {round_no})")
    transcript = client.run_agent_loop(
        _SYSTEM, user, CRITIC_TOOLS, _dispatch, max_steps=max_steps,
        agent_name="critic",
        trace_writer=session.trace,
        trace_meta={"paper_source": session.paper_source, "task_id": f"critic_round_{round_no}"},
    )

    queued_this_round = any(
        entry.get("role") == "tool" and "Queued repair task" in str(entry.get("content", ""))
        for entry in transcript
    )
    return not queued_this_round
