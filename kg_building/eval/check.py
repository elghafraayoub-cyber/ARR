from __future__ import annotations

import json
import logging
from pathlib import Path

from kg_building.graph.storage import KGStorage

log = logging.getLogger(__name__)


def run(kg_path: str | Path) -> dict:
    storage = KGStorage(kg_path)
    findings = storage.findings
    entities = storage.entities

    n = len(findings)
    n_entities = len(entities)
    with_conditions = sum(1 for f in findings.values() if f.get("conditions"))
    grounded_quotes = sum(
        1 for f in findings.values()
        if f.get("evidence_quote") and f["evidence_quote"].strip()
    )
    n_orphans = len(storage.orphan_entities())

    report = {
        "entities": n_entities,
        "findings": n,
        "condition_coverage": round(with_conditions / n, 3) if n else None,
        "findings_with_quote": grounded_quotes,
        "flagged_findings": sum(1 for f in findings.values() if f.get("flags")),
        "orphan_entity_rate": round(n_orphans / n_entities, 3) if n_entities else None,
        "duplicate_entity_candidates": len(storage.duplicate_entity_candidates()),
        "avg_degree": round(n * 2 / n_entities, 3) if n_entities else None,
        "vacuous_condition_rate": round(len(storage.vacuous_conditions()) / with_conditions, 3) if with_conditions else None,
    }
    log.info("Quality check: %s", report)
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    import sys
    run(sys.argv[1] if len(sys.argv) > 1 else "data/output/soil_kg.json")
