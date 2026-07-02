from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Run(SQLModel, table=True):
    id: str = Field(primary_key=True)
    paper_source: str
    status: str = "queued"  # queued | running | done | failed
    provider: str
    model: str
    max_critic_rounds: int = 3
    round_no: int = 0
    entity_count: int = 0
    finding_count: int = 0
    orphan_count: int | None = None
    duplicate_count: int | None = None
    vacuous_condition_count: int | None = None
    condition_coverage: float | None = None
    kg_path: str
    trace_path: str | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class Entity(SQLModel, table=True):
    pk: int | None = Field(default=None, primary_key=True)
    run_id: str = Field(index=True, foreign_key="run.id")
    entity_id: str  # original id from the KG JSON
    name: str
    entity_type: str = Field(index=True)
    description: str = ""
    evidence_quote: str = ""
    confidence: float = 0.0
    paper_source: str = ""
    is_orphan: bool = False


class Finding(SQLModel, table=True):
    pk: int | None = Field(default=None, primary_key=True)
    run_id: str = Field(index=True, foreign_key="run.id")
    finding_id: str
    source_id: str
    target_id: str
    relation_type: str = Field(index=True)
    effect_magnitude: str | None = None
    p_value: str | None = None
    evidence_quote: str = ""
    confidence: float = 0.0
    has_flags: bool = False
    conditions_json: str = "[]"  # serialized list[Condition] — see backend/db/sync.py


class StudyContext(SQLModel, table=True):
    pk: int | None = Field(default=None, primary_key=True)
    run_id: str = Field(index=True, foreign_key="run.id")
    paper_source: str
    geographic_region: str | None = None
    climate_zone: str | None = None
    soil_series_json: str = "[]"  # serialized list[str]
    soil_texture: str | None = None
    study_scale: str | None = None
    study_duration: str | None = None
    treatments_json: str = "[]"  # serialized list[str]
    rainfall_range: str | None = None
    statistical_design: str | None = None
