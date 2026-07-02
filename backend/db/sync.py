from __future__ import annotations

import json

from sqlmodel import Session, delete

from backend.db.models import Entity, Finding, Run, StudyContext
from kg_building.graph.storage import KGStorage


def _safe_float(value, default: float = 0.0) -> float:
    """Entities/findings are stored as raw LLM-provided dicts without strict
    schema validation, so a 'confidence' field can occasionally be a
    non-numeric string (e.g. 'HIGH') instead of a float. The DB projection
    tolerates this rather than crashing the sync."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def sync_run(session: Session, run_id: str, storage: KGStorage) -> None:
    """Upsert-projects storage.entities/findings/study_contexts into SQLite,
    tagged with run_id. Called after every storage.save() checkpoint.

    Full delete-then-reinsert per run_id: entity/finding counts here are at
    most a few thousand, so a full replace is simpler than diffing and still
    fast enough to run on every checkpoint.
    """
    orphans = storage.orphan_entities()
    orphan_ids = {e["id"] for e in orphans}
    duplicates = storage.duplicate_entity_candidates()
    vacuous = storage.vacuous_conditions()

    session.exec(delete(Entity).where(Entity.run_id == run_id))
    session.exec(delete(Finding).where(Finding.run_id == run_id))
    session.exec(delete(StudyContext).where(StudyContext.run_id == run_id))

    for eid, e in storage.entities.items():
        session.add(Entity(
            run_id=run_id,
            entity_id=eid,
            name=e.get("name", ""),
            entity_type=e.get("entity_type", "OTHER"),
            description=e.get("description", ""),
            evidence_quote=e.get("evidence_quote", ""),
            confidence=_safe_float(e.get("confidence")),
            paper_source=e.get("paper_source", ""),
            is_orphan=eid in orphan_ids,
        ))

    with_conditions = 0
    for fid, f in storage.findings.items():
        if f.get("conditions"):
            with_conditions += 1
        session.add(Finding(
            run_id=run_id,
            finding_id=fid,
            source_id=f.get("source_id", ""),
            target_id=f.get("target_id", ""),
            relation_type=f.get("relation_type", "OTHER"),
            effect_magnitude=f.get("effect_magnitude"),
            p_value=f.get("p_value"),
            evidence_quote=f.get("evidence_quote", ""),
            confidence=_safe_float(f.get("confidence")),
            has_flags=bool(f.get("flags")),
            conditions_json=json.dumps(f.get("conditions", [])),
        ))

    for paper_source, ctx in storage.study_contexts.items():
        session.add(StudyContext(
            run_id=run_id,
            paper_source=paper_source,
            geographic_region=ctx.get("geographic_region"),
            climate_zone=ctx.get("climate_zone"),
            soil_series_json=json.dumps(ctx.get("soil_series", [])),
            soil_texture=ctx.get("soil_texture"),
            study_scale=ctx.get("study_scale"),
            study_duration=ctx.get("study_duration"),
            treatments_json=json.dumps(ctx.get("treatments", [])),
            rainfall_range=ctx.get("rainfall_range"),
            statistical_design=ctx.get("statistical_design"),
        ))

    run = session.get(Run, run_id)
    if run:
        n_entities = len(storage.entities)
        n_findings = len(storage.findings)
        run.entity_count = n_entities
        run.finding_count = n_findings
        run.orphan_count = len(orphans)
        run.duplicate_count = len(duplicates)
        run.vacuous_condition_count = len(vacuous)
        run.condition_coverage = round(with_conditions / n_findings, 3) if n_findings else None
        session.add(run)

    session.commit()
