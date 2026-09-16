from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ConjunctionRunRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: int
    source: str

    window_start: datetime
    window_end: datetime

    step_seconds: int
    candidate_distance_km: float

    objects: int
    samples: int

    chunk_count: int = 1
    chunk_seconds: int = 900
    duplicate_events_suppressed: int = 0
    max_chunk_raw_candidates: int = 0
    max_chunk_unique_candidates: int = 0
    max_chunk_refinement_attempts: int = 0

    propagation_attempts: int
    propagation_failures: int
    expired_skips: int

    shared_solution_groups: int
    shared_solution_objects: int
    suppressed_shared_pairs: int

    raw_candidates: int
    unique_candidates: int = Field(description=(
        "Sum of unique candidate pairs evaluated within each chunk; "
        "not globally unique for runs with more than one chunk."
    ))

    refinement_attempts: int
    refinement_failures: int

    event_count: int
    duration_ms: float

    started_at: datetime
    completed_at: datetime


class ConjunctionEventRead(BaseModel):
    id: int
    run_id: int

    primary_object_id: int
    primary_norad_cat_id: int
    primary_name: str

    secondary_object_id: int
    secondary_norad_cat_id: int
    secondary_name: str

    tca: datetime

    miss_distance_km: float
    relative_velocity_km_s: float

    method: str
