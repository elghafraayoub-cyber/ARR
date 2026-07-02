"""
Soil Health KG — domain schema (reified finding-node model).

Design: type enums are curated (domain knowledge, prevents misclassification)
but the schema is open — every typed object carries an `extra` dict, and
EntityType/RelationType include an OTHER member paired with free-text
proposed_type / proposed_relation so novel concepts are surfaced for human
review instead of force-fit or silently dropped.
"""

from __future__ import annotations

import re
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class EntityType(str, Enum):
    SOIL_PHYSICAL_PROPERTY = "SOIL_PHYSICAL_PROPERTY"
    SOIL_CHEMICAL_PROPERTY = "SOIL_CHEMICAL_PROPERTY"
    BIOLOGICAL_AGENT = "BIOLOGICAL_AGENT"
    SOIL_PROCESS = "SOIL_PROCESS"
    MANAGEMENT_PRACTICE = "MANAGEMENT_PRACTICE"
    CROP_SPECIES = "CROP_SPECIES"
    PLANT_RESPONSE = "PLANT_RESPONSE"
    ENVIRONMENTAL_FACTOR = "ENVIRONMENTAL_FACTOR"
    ECOSYSTEM_SERVICE = "ECOSYSTEM_SERVICE"
    QUANTITATIVE_OUTCOME = "QUANTITATIVE_OUTCOME"
    EXPERIMENTAL_CONTEXT = "EXPERIMENTAL_CONTEXT"
    OTHER = "OTHER"


class RelationType(str, Enum):
    INCREASES = "INCREASES"
    DECREASES = "DECREASES"
    ENABLES = "ENABLES"
    INHIBITS = "INHIBITS"
    REGULATES = "REGULATES"
    MEDIATES = "MEDIATES"
    CAUSED_BY = "CAUSED_BY"
    DEPENDS_ON = "DEPENDS_ON"
    CORRELATES_WITH = "CORRELATES_WITH"
    OTHER = "OTHER"


class TaskType(str, Enum):
    """Units of work the Planner/Critic can queue for the Worker agent."""
    STUDY_CONTEXT = "STUDY_CONTEXT"
    EXTRACT_CHUNK = "EXTRACT_CHUNK"
    CHAIN_COMPLETION = "CHAIN_COMPLETION"
    CONDITION_REPAIR = "CONDITION_REPAIR"
    QUOTE_REVERIFY = "QUOTE_REVERIFY"
    DEDUP_PASS = "DEDUP_PASS"
    ORPHAN_REPAIR = "ORPHAN_REPAIR"


class Condition(BaseModel):
    model_config = ConfigDict(extra="ignore")

    condition_text: str = Field(..., description="Verbatim phrase from the text stating the condition.")
    parameter: str | None = Field(None, description="What is constrained, e.g. 'soil texture', 'year', 'depth'.")
    threshold: str | None = Field(None, description="The value, e.g. '94%', '2006', '60 cm'.")
    operator: str | None = Field(None, description='One of "<", ">", "=", "during", "in", "at".')
    context: str | None = Field(None, description="Qualitative context, e.g. 'dry year', 'karst landscape'.")
    temporal: str | None = Field(None, description="Time qualifier.")
    spatial: str | None = Field(None, description="Location qualifier, e.g. 'top 15 cm'.")
    soil_type: str | None = Field(None, description="Soil qualifier, e.g. 'sandy (94% sand)'.")
    statistical_evidence: str | None = Field(None, description="e.g. 'p=0.0027', 'n=4 years'.")
    extra: dict[str, str] = Field(default_factory=dict)


class SoilEntity(BaseModel):
    model_config = ConfigDict(use_enum_values=True, extra="ignore")

    id: str
    name: str
    entity_type: EntityType
    proposed_type: str | None = None
    description: str
    aliases: list[str] = Field(default_factory=list)
    measurement_unit: str | None = None
    typical_range: str | None = None
    evidence_quote: str
    paper_source: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    concept_id: str | None = None
    extra: dict[str, str] = Field(default_factory=dict)


class Finding(BaseModel):
    model_config = ConfigDict(use_enum_values=True, extra="ignore")

    id: str
    source_id: str
    target_id: str
    relation_type: RelationType
    proposed_relation: str | None = None
    conditions: list[Condition] = Field(default_factory=list)
    effect_magnitude: str | None = None
    effect_unit: str | None = None
    effect_strength: float | None = Field(None, ge=0.0, le=1.0)
    p_value: str | None = None
    study_site: str | None = None
    applicable_soil_types: list[str] = Field(default_factory=list)
    applicable_climate_zones: list[str] = Field(default_factory=list)
    evidence_quote: str
    evidence_char_start: int | None = None
    evidence_char_end: int | None = None
    paper_source: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    flags: list[str] = Field(default_factory=list)
    extra: dict[str, str] = Field(default_factory=dict)


class StudyContext(BaseModel):
    model_config = ConfigDict(extra="ignore")

    paper_source: str
    geographic_region: str | None = None
    climate_zone: str | None = None
    soil_series: list[str] = Field(default_factory=list)
    soil_texture: str | None = None
    study_scale: str | None = None
    study_duration: str | None = None
    treatments: list[str] = Field(default_factory=list)
    rainfall_range: str | None = None
    statistical_design: str | None = None
    extra: dict[str, str] = Field(default_factory=dict)


class AgentTask(BaseModel):
    """A unit of work in the shared task queue (planner-created or critic-created)."""
    model_config = ConfigDict(use_enum_values=True, extra="ignore")

    id: str
    task_type: TaskType
    chunk_id: str | None = None
    note: str = Field("", description="Why this task exists / what to focus on.")
    origin: str = Field("planner", description="planner | critic | worker (self-queued)")
    priority: int = Field(0, description="Lower runs first.")


class PlanResult(BaseModel):
    model_config = ConfigDict(extra="ignore")
    tasks: list[AgentTask] = Field(default_factory=list)
    reasoning: str = Field("", description="Brief plan rationale, for the run log.")


class CriticFinding(BaseModel):
    """A gap the critic identified in the graph."""
    model_config = ConfigDict(extra="ignore")
    issue: str
    target_finding_id: str | None = None
    target_chunk_id: str | None = None
    proposed_task: TaskType
    note: str = ""


class CriticReport(BaseModel):
    model_config = ConfigDict(extra="ignore")
    approved: bool
    summary: str = ""
    issues: list[CriticFinding] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
_TYPE_PREFIX = {
    EntityType.SOIL_PHYSICAL_PROPERTY: "soil_phys",
    EntityType.SOIL_CHEMICAL_PROPERTY: "soil_chem",
    EntityType.BIOLOGICAL_AGENT: "bio",
    EntityType.SOIL_PROCESS: "proc",
    EntityType.MANAGEMENT_PRACTICE: "mgmt",
    EntityType.CROP_SPECIES: "crop",
    EntityType.PLANT_RESPONSE: "resp",
    EntityType.ENVIRONMENTAL_FACTOR: "env",
    EntityType.ECOSYSTEM_SERVICE: "svc",
    EntityType.QUANTITATIVE_OUTCOME: "qty",
    EntityType.EXPERIMENTAL_CONTEXT: "ctx",
    EntityType.OTHER: "other",
}


def slugify(text: str, max_len: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return s[:max_len] or "x"


def make_entity_id(entity_type: EntityType | str, n: int) -> str:
    et = entity_type if isinstance(entity_type, EntityType) else EntityType(entity_type)
    return f"{_TYPE_PREFIX.get(et, 'ent')}_{n:03d}"


def quote_is_grounded(quote: str, source_text: str) -> bool:
    norm = lambda s: re.sub(r"\s+", " ", s).strip().lower()
    return norm(quote) in norm(source_text)


def is_vacuous_condition(condition_text: str, *names: str) -> bool:
    """True if condition_text carries no information beyond the entity name(s)
    it's attached to — e.g. a condition that just echoes "PC Rotation" on a
    finding about the PC Rotation entity, or is empty."""
    norm = lambda s: re.sub(r"\s+", " ", (s or "")).strip().lower()
    text = norm(condition_text)
    if not text:
        return True
    return any(text == norm(name) for name in names if name)
