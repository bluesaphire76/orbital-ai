from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeFloat,
    NonNegativeInt,
    PositiveInt,
)


class AIHealthStatus(str, Enum):
    DISABLED = "disabled"
    READY = "ready"
    LOADING = "loading"
    UNAVAILABLE = "unavailable"


class AIFeaturesRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chat_completions: bool
    structured_output: bool
    conjunction_brief: bool


class AILimitsRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_output_tokens: PositiveInt
    max_queue: PositiveInt
    concurrency: PositiveInt


class AICapabilitiesRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool
    provider: str
    model: str | None
    features: AIFeaturesRead
    limits: AILimitsRead


class AIHealthRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool
    status: AIHealthStatus
    provider: str
    model: str | None
    latency_ms: NonNegativeFloat | None


class ConjunctionBriefEvidenceField(str, Enum):
    PRIMARY_ROLE = "primary_role"
    PRIMARY_OBJECT_TYPE = "primary_object_type"
    PRIMARY_ELEMENT_SOURCE = "primary_element_source"
    PRIMARY_ELEMENT_EPOCH = "primary_element_epoch"
    SECONDARY_ROLE = "secondary_role"
    SECONDARY_OBJECT_TYPE = "secondary_object_type"
    SECONDARY_ELEMENT_SOURCE = "secondary_element_source"
    SECONDARY_ELEMENT_EPOCH = "secondary_element_epoch"
    TCA = "tca"
    MISS_DISTANCE_KM = "miss_distance_km"
    RELATIVE_VELOCITY_KM_S = "relative_velocity_km_s"
    METHOD = "method"
    WINDOW_START = "window_start"
    WINDOW_END = "window_end"
    RUN_COMPLETED_AT = "run_completed_at"


class ConjunctionBriefObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    text: str = Field(min_length=15, max_length=180)
    evidence_fields: list[ConjunctionBriefEvidenceField] = Field(
        min_length=1,
        max_length=3,
    )


class ConjunctionBriefOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    executive_summary: str = Field(min_length=20, max_length=320)
    key_observations: list[ConjunctionBriefObservation] = Field(
        min_length=1,
        max_length=3,
    )
    recommended_checks: list[Literal[
        "verify_ephemeris_freshness",
        "review_event_evolution",
        "confirm_object_identification",
        "monitor_next_screening",
        "escalate_for_human_review",
    ]] = Field(min_length=1, max_length=3)
    limitations: list[Literal[
        "ai_explanation_not_orbital_calculation",
        "persisted_data_may_change_after_rescreening",
        "human_review_required",
    ]] = Field(min_length=1, max_length=3)


class ConjunctionBriefEventRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: PositiveInt
    run_id: PositiveInt
    run_source: str
    run_started_at: datetime
    run_completed_at: datetime
    window_start: datetime
    window_end: datetime
    primary_object_id: PositiveInt
    primary_norad_cat_id: PositiveInt
    primary_name: str
    primary_designator: str | None
    primary_object_type: str | None
    primary_element_id: PositiveInt
    primary_element_source: str
    primary_element_epoch: datetime
    secondary_object_id: PositiveInt
    secondary_norad_cat_id: PositiveInt
    secondary_name: str
    secondary_designator: str | None
    secondary_object_type: str | None
    secondary_element_id: PositiveInt
    secondary_element_source: str
    secondary_element_epoch: datetime
    tca: datetime
    miss_distance_km: NonNegativeFloat
    relative_velocity_km_s: NonNegativeFloat
    method: str


class ConjunctionBriefMetadataRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task: Literal["conjunction_analyst_brief"]
    prompt_version: Literal["conjunction-analyst-brief-v2"]
    grounding_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    generated_at: datetime
    provider: Literal["llama.cpp"]
    model: str
    finish_reason: Literal["stop"]
    prompt_tokens: NonNegativeInt | None
    completion_tokens: NonNegativeInt | None
    total_tokens: NonNegativeInt | None
    duration_seconds: NonNegativeFloat


class ConjunctionBriefResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: ConjunctionBriefEventRead
    brief: ConjunctionBriefOutput
    metadata: ConjunctionBriefMetadataRead
    disclaimer: Literal[
        "AI-generated explanation based on persisted deterministic screening data. Human review is required."
    ]
