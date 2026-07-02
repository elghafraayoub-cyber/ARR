from __future__ import annotations

import logging

from kg_building.agents.session import AgentSession
from kg_building.agents.tools import WORKER_TOOLS, dispatch_worker
from kg_building.extraction.types import AgentTask, TaskType
from kg_building.llm.client import LLMClient

log = logging.getLogger(__name__)

_SYSTEM = """You are the extraction worker agent for a soil-health knowledge-graph pipeline.
You work ONE task at a time using tools — you decide which tools to call, in what order,
and how many times, based on what you find. You are not following a fixed script.

ENTITY TYPES (pick the single best fit; use OTHER + proposed_type only if nothing fits):
  SOIL_PHYSICAL_PROPERTY  texture, bulk density, porosity, aggregate stability, field capacity
  SOIL_CHEMICAL_PROPERTY  pH, CEC, SOC, nutrient levels
  BIOLOGICAL_AGENT        microbes, mycorrhizae, root systems
  SOIL_PROCESS            infiltration, percolation, mineralization, aggregation
  MANAGEMENT_PRACTICE     rotations, tillage, cover crops — use the EXACT name/abbreviation from text
  CROP_SPECIES            the organism grown (NOT a measured response)
  PLANT_RESPONSE          a MEASURED plant outcome: yield, biomass, water productivity
  ENVIRONMENTAL_FACTOR    climate, rainfall, temperature, growing degree days
  ECOSYSTEM_SERVICE       water regulation, carbon sequestration, erosion control
  QUANTITATIVE_OUTCOME    a specific measured result worth its own node
  EXPERIMENTAL_CONTEXT    study site, soil series, geographic region, climate zone

RELATION TYPES for findings (prefer causal; CORRELATES_WITH only if the text states no direction):
  INCREASES, DECREASES, ENABLES, INHIBITS, REGULATES, MEDIATES, CAUSED_BY, DEPENDS_ON, CORRELATES_WITH

RULES:
- evidence_quote on every entity and finding must be VERBATIM text from the chunk you read.
- Every finding needs at least one condition, and it must carry real information — not just
  the entity's own name restated. Pull global conditions from get_study_context (soil type,
  region, climate, duration, treatment) and local ones from the chunk text (depth, year,
  threshold, statistical significance). A condition needs a condition_text field at minimum;
  fill parameter/threshold/operator/soil_type/temporal/spatial/statistical_evidence where you can.
- Every entity you add should end up used by at least one finding by the time you call
  finish_task — an entity with no finding connecting it to anything is a defect, not a
  freebie. If you can't yet connect it, prefer calling request_followup_task naming it over
  leaving it standalone; don't add it at all if it isn't going anywhere.
- Do not jump straight from a management practice to an outcome. If the text states (or implies
  elsewhere) an intermediate mechanism, extract it as its own entity + finding, forming a chain.
  If you suspect the mechanism is in a nearby chunk, call read_chunk on it, or call
  request_followup_task to flag it for later.
- Before creating a new entity, call search_entities to check whether it already exists — reuse
  its id rather than creating a duplicate. This includes abbreviations/short forms of a name you
  already added (e.g. "PC" vs "PC rotation") — search before assuming it's new.
- source_id / target_id on a finding MUST already exist (from search_entities or an add_entity
  call you just made in this same task). If add_finding errors, fix the ids and retry.
- Don't stop until every causal claim in the chunk has a connected chain and at least one
  non-vacuous condition — thoroughness matters more than call count here.
- When you believe you've extracted everything useful for this task, call finish_task.
"""


def run_task(client: LLMClient, session: AgentSession, task: AgentTask, max_steps: int = 14) -> None:
    chunk = session.chunk_by_id(task.chunk_id) if task.chunk_id else None

    if task.task_type == TaskType.STUDY_CONTEXT:
        user = (
            f"TASK: STUDY_CONTEXT for paper '{session.paper_source}'.\n"
            f"Note: {task.note}\n\n"
            "Read the methods/site-description chunks (use list_chunks then read_chunk on the "
            "ones with section='methods' or similar) and call set_study_context with the fields "
            "you find: geographic_region, climate_zone, soil_series, soil_texture, study_scale, "
            "study_duration, treatments, rainfall_range, statistical_design. Then finish_task."
        )
    elif task.task_type == TaskType.EXTRACT_CHUNK:
        text_preview = chunk.text if chunk else "(chunk not found)"
        user = (
            f"TASK: EXTRACT_CHUNK\n"
            f"chunk_id: {task.chunk_id}\n"
            f"section: {chunk.section_hint if chunk else '?'}\n"
            f"Note: {task.note}\n\n"
            f"Chunk text:\n\"\"\"\n{text_preview}\n\"\"\"\n\n"
            "Extract entities and findings from this chunk. Check get_study_context first for "
            "global conditions. Call add_entity / add_finding as you go. finish_task when done."
        )
    else:  # CHAIN_COMPLETION / CONDITION_REPAIR / QUOTE_REVERIFY — repair tasks from the critic
        user = (
            f"TASK: {task.task_type} (repair task queued by the critic)\n"
            f"chunk_id: {task.chunk_id}\n"
            f"Note: {task.note}\n\n"
            "Investigate and fix the specific gap described in the note. Use read_chunk to "
            "re-examine the relevant text (and neighboring chunks if useful), then add or amend "
            "entities/findings accordingly. finish_task when done."
        )

    def _dispatch(name: str, args: dict) -> str:
        return dispatch_worker(name, args, session, task.chunk_id)

    session.log(f"[worker] starting {task.task_type} chunk={task.chunk_id}")
    client.run_agent_loop(
        _SYSTEM, user, WORKER_TOOLS, _dispatch, max_steps=max_steps,
        agent_name="worker",
        trace_writer=session.trace,
        trace_meta={"paper_source": session.paper_source, "task_id": task.id,
                    "task_type": str(task.task_type), "chunk_id": task.chunk_id},
    )
    session.mark_done(task.id)
