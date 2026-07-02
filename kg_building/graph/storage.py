from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import networkx as nx

log = logging.getLogger(__name__)


class KGStorage:
    """
    Backbone graph store. Entities and findings are both nodes; findings
    also carry `cause`/`effect` edges to their source/target entities
    (the reified finding-node model).
    """

    def __init__(self, kg_path: str | Path, provider: str = "", model: str = "") -> None:
        self.kg_path = Path(kg_path)
        self.graph = nx.DiGraph()
        self.entities: dict[str, dict] = {}
        self.findings: dict[str, dict] = {}
        self.study_contexts: dict[str, dict] = {}
        self.concepts: dict[str, dict] = {}
        self.metadata: dict = {
            "paper_sources": [],
            "extraction_history": [],
            "provider": provider,
            "model": model,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if self.kg_path.exists():
            self._load()

    # ------------------------------------------------------------------ #
    def _load(self) -> None:
        try:
            data = json.loads(self.kg_path.read_text(encoding="utf-8"))
        except Exception as exc:
            log.warning("Could not load existing KG at %s: %s — starting fresh", self.kg_path, exc)
            return
        self.entities = data.get("entities", {})
        self.findings = data.get("findings", {})
        self.study_contexts = data.get("study_contexts", {})
        self.concepts = data.get("concepts", {})
        self.metadata.update(data.get("metadata", {}))
        for eid, e in self.entities.items():
            self.graph.add_node(eid, kind="entity", **{})
        for fid, f in self.findings.items():
            self.graph.add_node(fid, kind="finding")
            if f.get("source_id") in self.entities:
                self.graph.add_edge(f["source_id"], fid, role="cause")
            if f.get("target_id") in self.entities:
                self.graph.add_edge(fid, f["target_id"], role="effect")
        log.info("Loaded existing KG: %d entities, %d findings", len(self.entities), len(self.findings))

    # ------------------------------------------------------------------ #
    # Entities
    # ------------------------------------------------------------------ #
    def add_entity(self, entity: dict) -> bool:
        eid = entity["id"]
        is_new = eid not in self.entities
        self.entities[eid] = entity
        self.graph.add_node(eid, kind="entity")
        return is_new

    def get_entity(self, eid: str) -> dict | None:
        return self.entities.get(eid)

    def entity_index(self) -> list[dict]:
        return [{"id": e["id"], "name": e["name"], "entity_type": e["entity_type"]}
                for e in self.entities.values()]

    def search_entities(self, query: str, limit: int = 10) -> list[dict]:
        q = query.lower().strip()
        if not q:
            return []
        scored = []
        matched_ids = set()
        for e in self.entities.values():
            name = e.get("name", "").lower()
            aliases = [a.lower() for a in e.get("aliases", [])]
            score = 0
            if q == name:
                score = 100
            elif q in name or name in q:
                score = 50
            elif any(q in a or a in q for a in aliases):
                score = 40
            else:
                q_terms = set(q.split())
                name_terms = set(name.split())
                overlap = len(q_terms & name_terms)
                if overlap:
                    score = 10 * overlap
            if score:
                scored.append((score, e))
                matched_ids.add(e["id"])
        scored.sort(key=lambda x: -x[0])

        # Lexical matching misses semantically-equivalent names (e.g. "PC" vs
        # "PC rotation"). Layer in an embedding pass so those near-misses still
        # surface — this is a "worth reviewing" threshold, distinct from (and
        # lower than) the 0.88 hard-merge threshold used at entity-creation time.
        if len(scored) < limit:
            try:
                from kg_building.graph.dedup import find_similar_entities
                candidates = [e for e in self.entities.values() if e["id"] not in matched_ids]
                for sim, match in find_similar_entities(query, candidates, threshold=0.75):
                    scored.append((int(sim * 30), match))
                    matched_ids.add(match["id"])
            except Exception as exc:
                log.debug("Embedding-assisted search_entities pass skipped: %s", exc)
            scored.sort(key=lambda x: -x[0])

        return [e for _, e in scored[:limit]]

    def orphan_entities(self) -> list[dict]:
        """Entities with no finding attached (degree 0 in the reified graph)."""
        return [
            {"id": eid, "name": e.get("name"), "entity_type": e.get("entity_type")}
            for eid, e in self.entities.items()
            if self.graph.degree(eid) == 0
        ]

    def duplicate_entity_candidates(self, threshold: float = 0.75, limit: int = 20) -> list[dict]:
        """Entity pairs whose names are similar enough to be worth a human/critic look,
        but below the 0.88 threshold that auto-merges at creation time."""
        from kg_building.graph.dedup import find_all_duplicate_pairs
        entities = list(self.entities.values())
        return find_all_duplicate_pairs(entities, threshold=threshold, limit=limit)

    def vacuous_conditions(self) -> list[dict]:
        """Conditions whose condition_text carries no information beyond the
        entity names it's attached to (echoes the name, or is empty)."""
        from kg_building.extraction.types import is_vacuous_condition
        flagged = []
        for fid, f in self.findings.items():
            src = self.entities.get(f.get("source_id", ""), {})
            tgt = self.entities.get(f.get("target_id", ""), {})
            for cond in f.get("conditions", []):
                text = cond.get("condition_text", "")
                if is_vacuous_condition(text, src.get("name", ""), tgt.get("name", "")):
                    flagged.append({"finding_id": fid, "condition_text": text})
        return flagged

    # ------------------------------------------------------------------ #
    # Findings
    # ------------------------------------------------------------------ #
    def add_finding(self, finding: dict) -> bool:
        fid = finding["id"]
        is_new = fid not in self.findings
        self.findings[fid] = finding
        self.graph.add_node(fid, kind="finding")
        if finding.get("source_id") in self.entities:
            self.graph.add_edge(finding["source_id"], fid, role="cause")
        if finding.get("target_id") in self.entities:
            self.graph.add_edge(fid, finding["target_id"], role="effect")
        return is_new

    def get_finding(self, fid: str) -> dict | None:
        return self.findings.get(fid)

    def findings_missing_conditions(self) -> list[str]:
        return [fid for fid, f in self.findings.items() if not f.get("conditions")]

    def broken_chains(self) -> list[dict]:
        """
        MANAGEMENT_PRACTICE -> outcome findings with no intermediate
        SOIL_PROCESS / BIOLOGICAL_AGENT node reachable within 1 hop.
        """
        gaps = []
        for fid, f in self.findings.items():
            src = self.entities.get(f.get("source_id", ""))
            tgt = self.entities.get(f.get("target_id", ""))
            if not src or not tgt:
                continue
            if src.get("entity_type") == "MANAGEMENT_PRACTICE" and tgt.get("entity_type") in (
                "PLANT_RESPONSE", "QUANTITATIVE_OUTCOME", "ECOSYSTEM_SERVICE",
            ):
                gaps.append({"finding_id": fid, "source": src["name"], "target": tgt["name"]})
        return gaps

    # ------------------------------------------------------------------ #
    # Study context
    # ------------------------------------------------------------------ #
    def set_study_context(self, paper_source: str, ctx: dict) -> None:
        self.study_contexts[paper_source] = ctx

    def get_study_context(self, paper_source: str) -> dict:
        return self.study_contexts.get(paper_source, {})

    # ------------------------------------------------------------------ #
    def record_extraction(self, paper_source: str, stage: str, note: str = "") -> None:
        self.metadata["extraction_history"].append({
            "paper_source": paper_source, "stage": stage, "note": note,
            "at": datetime.now(timezone.utc).isoformat(),
        })
        if paper_source not in self.metadata["paper_sources"]:
            self.metadata["paper_sources"].append(paper_source)

    def stats(self) -> dict:
        return {
            "entities": len(self.entities),
            "findings": len(self.findings),
            "papers": len(self.metadata["paper_sources"]),
            "findings_missing_conditions": len(self.findings_missing_conditions()),
            "orphan_entities": len(self.orphan_entities()),
            "duplicate_candidates": len(self.duplicate_entity_candidates()),
            "vacuous_conditions": len(self.vacuous_conditions()),
        }

    def save(self) -> None:
        self.metadata["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.kg_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "entities": self.entities,
            "findings": self.findings,
            "study_contexts": self.study_contexts,
            "concepts": self.concepts,
            "metadata": self.metadata,
        }
        self.kg_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        log.info("Saved KG -> %s (%d entities, %d findings)",
                  self.kg_path, len(self.entities), len(self.findings))
