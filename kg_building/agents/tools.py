from __future__ import annotations

import json
import logging
from typing import Any

from kg_building.agents.session import AgentSession
from kg_building.extraction.types import AgentTask, TaskType

log = logging.getLogger(__name__)


def _tool(name: str, description: str, params: dict, required: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": params, "required": required},
        },
    }


# ======================================================================== #
# WORKER tools — extraction agent operating on one task (a chunk, usually)
# ======================================================================== #
WORKER_TOOLS = [
    _tool(
        "read_chunk",
        "Read the full text of a chunk by id — including a chunk OTHER than the one you were "
        "assigned, if you suspect a mechanism/condition/entity you need lives nearby (e.g. the "
        "previous or next chunk). Use this whenever you're missing context instead of guessing.",
        {"chunk_id": {"type": "string"}},
        ["chunk_id"],
    ),
    _tool(
        "list_chunks",
        "List all chunk ids in this paper with their section hint, so you can decide which one to read next.",
        {},
        [],
    ),
    _tool(
        "search_entities",
        "Search already-extracted entities by name/keyword before creating a new one, so you reuse "
        "the correct id instead of creating a duplicate.",
        {"query": {"type": "string"}},
        ["query"],
    ),
    _tool(
        "get_study_context",
        "Get the paper-wide StudyContext (region, climate, soil, treatments, duration) extracted so "
        "far. Use its fields as global conditions on findings.",
        {},
        [],
    ),
    _tool(
        "set_study_context",
        "Set/update the paper-wide StudyContext. Only call this for a STUDY_CONTEXT task.",
        {"fields": {"type": "object", "description": "StudyContext fields as a JSON object."}},
        ["fields"],
    ),
    _tool(
        "add_entity",
        "Add a newly discovered entity to the knowledge graph. Will be deduplicated automatically "
        "against existing entities by name similarity.",
        {"entity": {"type": "object", "description": "SoilEntity fields: id, name, entity_type, description, evidence_quote, paper_source, confidence, aliases, etc."}},
        ["entity"],
    ),
    _tool(
        "add_finding",
        "Add a causal/relational finding connecting two entities. source_id and target_id MUST be "
        "ids that already exist (from search_entities or an add_entity call you just made). If it "
        "fails, fix the ids and retry — do not invent ids.",
        {"finding": {"type": "object", "description": "Finding fields: id, source_id, target_id, relation_type, conditions, evidence_quote, paper_source, confidence, etc."}},
        ["finding"],
    ),
    _tool(
        "request_followup_task",
        "Queue a new task for later — e.g. you noticed a management practice jumps straight to an "
        "outcome with no stated mechanism, and think another chunk might state it, or you found a "
        "finding with no usable condition information. This is how you extend the plan mid-work.",
        {
            "task_type": {"type": "string", "enum": [t.value for t in TaskType]},
            "chunk_id": {"type": "string", "description": "Relevant chunk id, if any."},
            "note": {"type": "string", "description": "What to look for / fix."},
        },
        ["task_type", "note"],
    ),
    _tool(
        "finish_task",
        "Call this when you have finished extracting everything useful from this task. "
        "Give a one-line summary of what you added.",
        {"summary": {"type": "string"}},
        ["summary"],
    ),
]


def dispatch_worker(name: str, args: dict, session: AgentSession, chunk_hint: str | None) -> str:
    if name == "read_chunk":
        c = session.chunk_by_id(args.get("chunk_id", chunk_hint or ""))
        if not c:
            return f"ERROR: no such chunk_id. Known ids: {[c.chunk_id for c in session.chunks][:10]}"
        return f"[section={c.section_hint}]\n{c.text}"

    if name == "list_chunks":
        return json.dumps([{"chunk_id": c.chunk_id, "section": c.section_hint, "chars": len(c.text)}
                            for c in session.chunks])

    if name == "search_entities":
        results = session.storage.search_entities(args.get("query", ""))
        return json.dumps(results) if results else "No matching entities found."

    if name == "get_study_context":
        return json.dumps(session.storage.get_study_context(session.paper_source)) or "{}"

    if name == "set_study_context":
        fields = args.get("fields", {})
        fields["paper_source"] = session.paper_source
        session.storage.set_study_context(session.paper_source, fields)
        return "StudyContext saved."

    if name == "add_entity":
        entity = args.get("entity", {})
        entity.setdefault("paper_source", session.paper_source)
        try:
            final_id, is_new = session.add_entity(entity)
        except Exception as exc:
            return f"ERROR validating entity: {exc}"
        return f"OK id={final_id} new={is_new}"

    if name == "add_finding":
        finding = args.get("finding", {})
        finding.setdefault("paper_source", session.paper_source)
        ok, err = session.add_finding(finding)
        if not ok:
            return f"ERROR: {err}"
        return f"OK id={finding['id']}"

    if name == "request_followup_task":
        task = AgentTask(
            id=f"t_{len(session.task_queue):04d}_wk",
            task_type=TaskType(args["task_type"]),
            chunk_id=args.get("chunk_id"),
            note=args.get("note", ""),
            origin="worker",
            priority=5,
        )
        session.enqueue(task)
        return f"Queued follow-up task {task.id}."

    if name == "finish_task":
        return f"Task finished: {args.get('summary', '')}"

    return f"ERROR: unknown tool '{name}'"


# ======================================================================== #
# CRITIC tools — whole-graph review agent, runs after worker tasks drain
# ======================================================================== #
CRITIC_TOOLS = [
    _tool(
        "list_findings_missing_conditions",
        "List findings that currently have zero conditions attached.",
        {}, [],
    ),
    _tool(
        "list_broken_chains",
        "List findings that jump directly from a MANAGEMENT_PRACTICE to an outcome "
        "(PLANT_RESPONSE / QUANTITATIVE_OUTCOME / ECOSYSTEM_SERVICE) with no intermediate "
        "mechanism entity — a likely missing causal chain.",
        {}, [],
    ),
    _tool(
        "list_orphan_entities",
        "List entities that have zero findings connecting them to anything else in the "
        "graph — isolated nodes. Check every one returned; queue an ORPHAN_REPAIR naming "
        "the chunk it likely connects from, unless it's genuinely unconnectable.",
        {}, [],
    ),
    _tool(
        "list_duplicate_entity_candidates",
        "List entity pairs whose names are similar enough to likely be the same "
        "real-world concept (e.g. 'PC' and 'PC rotation'), below the threshold that "
        "auto-merges at creation time. If two clearly refer to the same thing, call "
        "merge_entities.",
        {}, [],
    ),
    _tool(
        "list_vacuous_conditions",
        "List finding conditions whose condition_text carries no information beyond the "
        "entity name it's attached to (or is empty) — these inflate condition_coverage "
        "without adding real scope/applicability information.",
        {}, [],
    ),
    _tool(
        "merge_entities",
        "Merge two entities that refer to the same real-world concept: reassigns all "
        "findings from merge_id to keep_id, unions aliases, and removes merge_id. Use "
        "this directly (not request_repair) once you've confirmed a duplicate pair.",
        {
            "keep_id": {"type": "string", "description": "The entity id to keep."},
            "merge_id": {"type": "string", "description": "The duplicate entity id to remove."},
            "note": {"type": "string", "description": "Why these are the same concept."},
        },
        ["keep_id", "merge_id"],
    ),
    _tool(
        "get_finding",
        "Get full details of a finding by id, including its evidence_quote and paper_source.",
        {"finding_id": {"type": "string"}}, ["finding_id"],
    ),
    _tool(
        "verify_quote",
        "Check whether a finding's evidence_quote is an actual verbatim substring of its source "
        "chunk (catches hallucinated quotes). Requires the chunk_id the finding came from.",
        {"finding_id": {"type": "string"}, "chunk_id": {"type": "string"}},
        ["finding_id", "chunk_id"],
    ),
    _tool(
        "request_repair",
        "Queue a repair task for the Worker agent to fix a specific gap — e.g. re-read a chunk to "
        "find the missing mechanism, or re-derive conditions for a finding from the study context.",
        {
            "task_type": {"type": "string", "enum": [t.value for t in TaskType]},
            "chunk_id": {"type": "string"},
            "note": {"type": "string"},
        },
        ["task_type", "note"],
    ),
    _tool(
        "approve",
        "Call this when the graph looks complete enough (no repairs are worth queuing). "
        "Ends the review.",
        {"summary": {"type": "string"}}, ["summary"],
    ),
]


def dispatch_critic(name: str, args: dict, session: AgentSession) -> str:
    if name == "list_findings_missing_conditions":
        ids = session.storage.findings_missing_conditions()
        return json.dumps(ids[:30]) + (f" ... and {len(ids) - 30} more" if len(ids) > 30 else "")

    if name == "list_broken_chains":
        gaps = session.storage.broken_chains()
        return json.dumps(gaps[:30])

    if name == "list_orphan_entities":
        orphans = session.storage.orphan_entities()
        return json.dumps(orphans[:30]) + (f" ... and {len(orphans) - 30} more" if len(orphans) > 30 else "")

    if name == "list_duplicate_entity_candidates":
        pairs = session.storage.duplicate_entity_candidates()
        return json.dumps(pairs) if pairs else "No duplicate candidates found."

    if name == "list_vacuous_conditions":
        vacuous = session.storage.vacuous_conditions()
        return json.dumps(vacuous[:30]) + (f" ... and {len(vacuous) - 30} more" if len(vacuous) > 30 else "")

    if name == "merge_entities":
        keep_id, merge_id = args.get("keep_id", ""), args.get("merge_id", "")
        ok, err = session.merge_entities(keep_id, merge_id)
        if not ok:
            return f"ERROR: {err}"
        return f"Merged {merge_id} into {keep_id}."

    if name == "get_finding":
        f = session.storage.get_finding(args.get("finding_id", ""))
        return json.dumps(f) if f else "ERROR: no such finding"

    if name == "verify_quote":
        f = session.storage.get_finding(args.get("finding_id", ""))
        if not f:
            return "ERROR: no such finding"
        ok = session.verify_quote(f.get("evidence_quote", ""), args.get("chunk_id", ""))
        return f"grounded={ok}"

    if name == "request_repair":
        task = AgentTask(
            id=f"t_{len(session.task_queue):04d}_cr",
            task_type=TaskType(args["task_type"]),
            chunk_id=args.get("chunk_id"),
            note=args.get("note", ""),
            origin="critic",
            priority=1,
        )
        session.enqueue(task)
        return f"Queued repair task {task.id}."

    if name == "approve":
        return f"Approved: {args.get('summary', '')}"

    return f"ERROR: unknown tool '{name}'"
