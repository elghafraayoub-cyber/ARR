from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field

from kg_building.chunking.chunker import ChunkItem
from kg_building.extraction.types import AgentTask, quote_is_grounded
from kg_building.graph.dedup import find_duplicate
from kg_building.graph.storage import KGStorage

log = logging.getLogger(__name__)


@dataclass
class AgentSession:
    """
    Per-paper working memory shared by Planner, Worker and Critic.
    Holds the chunk manifest, the task queue, and a handle to KGStorage.
    Tool dispatch functions (tools.py) mutate this object; the agents never
    touch KGStorage directly.
    """
    paper_source: str
    chunks: list[ChunkItem]
    storage: KGStorage
    dedup_threshold: float = 0.88

    task_queue: list[AgentTask] = field(default_factory=list)
    completed_task_ids: set[str] = field(default_factory=set)
    run_log: list[str] = field(default_factory=list)
    trace: object | None = None  # TraceWriter, set by the orchestrator

    _entity_counter: int = 0
    _finding_counter: int = 0

    def chunk_by_id(self, chunk_id: str) -> ChunkItem | None:
        for c in self.chunks:
            if c.chunk_id == chunk_id:
                return c
        return None

    def log(self, msg: str) -> None:
        log.info(msg)
        self.run_log.append(msg)

    # ------------------------------------------------------------------ #
    # Task queue — this is what makes the pipeline iterative rather than
    # a fixed sequence: Planner seeds it, Worker can append to it
    # (request_followup_task), Critic can append repair tasks after review.
    # ------------------------------------------------------------------ #
    def enqueue(self, task: AgentTask) -> None:
        self.task_queue.append(task)
        self.log(f"[queue] +{task.task_type} chunk={task.chunk_id} origin={task.origin} :: {task.note}")

    def next_task(self) -> AgentTask | None:
        pending = [t for t in self.task_queue if t.id not in self.completed_task_ids]
        if not pending:
            return None
        pending.sort(key=lambda t: t.priority)
        return pending[0]

    def mark_done(self, task_id: str) -> None:
        self.completed_task_ids.add(task_id)

    # ------------------------------------------------------------------ #
    # Entity / finding mutation with dedup baked in
    # ------------------------------------------------------------------ #
    def add_entity(self, entity: dict) -> tuple[str, bool]:
        """Returns (final_id, is_new). Deduplicates against existing entities."""
        existing = list(self.storage.entities.values())
        dup = find_duplicate(entity["name"], existing, self.dedup_threshold)
        if dup:
            merged_aliases = set(dup.get("aliases", [])) | {entity["name"]} | set(entity.get("aliases", []))
            dup["aliases"] = sorted(merged_aliases)
            self.storage.add_entity(dup)
            return dup["id"], False
        if not entity.get("id"):
            entity["id"] = f"ent_{uuid.uuid4().hex[:8]}"
        self.storage.add_entity(entity)
        return entity["id"], True

    def add_finding(self, finding: dict) -> tuple[bool, str | None]:
        """Returns (ok, error). Validates endpoints exist before storing."""
        if finding.get("source_id") not in self.storage.entities:
            return False, f"source_id '{finding.get('source_id')}' does not exist — call search_entities or add_entity first"
        if finding.get("target_id") not in self.storage.entities:
            return False, f"target_id '{finding.get('target_id')}' does not exist — call search_entities or add_entity first"
        if not finding.get("id"):
            finding["id"] = f"find_{uuid.uuid4().hex[:8]}"
        self.storage.add_finding(finding)
        return True, None

    def verify_quote(self, quote: str, chunk_id: str) -> bool:
        c = self.chunk_by_id(chunk_id)
        if not c:
            return False
        return quote_is_grounded(quote, c.text)

    def merge_entities(self, keep_id: str, merge_id: str) -> tuple[bool, str | None]:
        """Merges merge_id into keep_id: reassigns findings, unions aliases, removes merge_id."""
        if keep_id == merge_id:
            return False, "keep_id and merge_id are the same"
        keep = self.storage.entities.get(keep_id)
        merge = self.storage.entities.get(merge_id)
        if not keep:
            return False, f"keep_id '{keep_id}' does not exist"
        if not merge:
            return False, f"merge_id '{merge_id}' does not exist"

        merged_aliases = set(keep.get("aliases", [])) | {merge["name"]} | set(merge.get("aliases", []))
        keep["aliases"] = sorted(merged_aliases)

        graph = self.storage.graph
        for finding in self.storage.findings.values():
            fid = finding["id"]
            if finding.get("source_id") == merge_id:
                finding["source_id"] = keep_id
                if graph.has_edge(merge_id, fid):
                    graph.remove_edge(merge_id, fid)
                graph.add_edge(keep_id, fid, role="cause")
            if finding.get("target_id") == merge_id:
                finding["target_id"] = keep_id
                if graph.has_edge(fid, merge_id):
                    graph.remove_edge(fid, merge_id)
                graph.add_edge(fid, keep_id, role="effect")

        if graph.has_node(merge_id):
            graph.remove_node(merge_id)
        del self.storage.entities[merge_id]
        return True, None
