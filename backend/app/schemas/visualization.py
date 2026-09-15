from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class VisualizationObject(BaseModel):
    object_id: int
    norad_cat_id: int
    object_name: str
    object_type: str | None

    epoch: datetime
    ephemeris_status: str

    x_m: float
    y_m: float
    z_m: float

    vx_m_s: float
    vy_m_s: float
    vz_m_s: float


class VisualizationSnapshot(BaseModel):
    at: datetime
    frame: str

    objects: list[
        VisualizationObject
    ]

    total_elements: int
    rendered_objects: int
    expired_skips: int
    propagation_failures: int


class TrajectoryPoint(BaseModel):
    at: datetime

    x_m: float
    y_m: float
    z_m: float


class ObjectTrajectory(BaseModel):
    object_id: int
    norad_cat_id: int
    object_name: str

    frame: str

    start: datetime
    end: datetime
    step_seconds: int

    points: list[
        TrajectoryPoint
    ]
