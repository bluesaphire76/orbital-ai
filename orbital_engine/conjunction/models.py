from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


Vector3 = tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class StateVector:
    object_id: int
    when: datetime
    position_km: Vector3
    velocity_km_s: Vector3


@dataclass(frozen=True, slots=True)
class CandidatePair:
    primary: StateVector
    secondary: StateVector
    screening_distance_km: float


@dataclass(frozen=True, slots=True)
class ClosestApproach:
    primary_object_id: int
    secondary_object_id: int
    tca: datetime

    miss_distance_km: float
    relative_velocity_km_s: float
    delta_t_seconds: float

    method: str = "linear-relative-motion"
