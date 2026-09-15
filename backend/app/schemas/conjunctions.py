from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


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

    propagation_attempts: int
    propagation_failures: int
    expired_skips: int

    shared_solution_groups: int
    shared_solution_objects: int
    suppressed_shared_pairs: int

    raw_candidates: int
    unique_candidates: int

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
