from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable

from scipy.optimize import minimize_scalar

from orbital_engine.conjunction.distance import (
    magnitude,
    subtract,
)
from orbital_engine.conjunction.models import (
    CandidatePair,
    ClosestApproach,
    Vector3,
)


StateAt = Callable[
    [datetime],
    tuple[Vector3, Vector3],
]


def refine_closest_approach_numerical(
    candidate: CandidatePair,
    *,
    primary_state_at: StateAt,
    secondary_state_at: StateAt,
    search_start: datetime,
    search_end: datetime,
    tolerance_seconds: float = 0.01,
) -> ClosestApproach:
    if search_start.tzinfo is None:
        raise ValueError(
            "search_start must be timezone-aware"
        )

    if search_end.tzinfo is None:
        raise ValueError(
            "search_end must be timezone-aware"
        )

    if search_end <= search_start:
        raise ValueError(
            "search_end must be after search_start"
        )

    if tolerance_seconds <= 0:
        raise ValueError(
            "tolerance_seconds must be greater than zero"
        )

    duration_seconds = (
        search_end - search_start
    ).total_seconds()

    def distance_squared(
        offset_seconds: float,
    ) -> float:
        when = (
            search_start
            + timedelta(
                seconds=offset_seconds
            )
        )

        primary_position, _ = (
            primary_state_at(
                when
            )
        )

        secondary_position, _ = (
            secondary_state_at(
                when
            )
        )

        relative_position = subtract(
            secondary_position,
            primary_position,
        )

        return (
            relative_position[0] ** 2
            + relative_position[1] ** 2
            + relative_position[2] ** 2
        )

    optimization = minimize_scalar(
        distance_squared,
        bounds=(
            0.0,
            duration_seconds,
        ),
        method="bounded",
        options={
            "xatol": tolerance_seconds,
            "maxiter": 100,
        },
    )

    if not optimization.success:
        raise RuntimeError(
            "Closest-approach numerical "
            f"minimization failed: "
            f"{optimization.message}"
        )

    delta_from_start = float(
        optimization.x
    )

    tca = (
        search_start
        + timedelta(
            seconds=delta_from_start
        )
    )

    primary_position, primary_velocity = (
        primary_state_at(
            tca
        )
    )

    secondary_position, secondary_velocity = (
        secondary_state_at(
            tca
        )
    )

    relative_position = subtract(
        secondary_position,
        primary_position,
    )

    relative_velocity = subtract(
        secondary_velocity,
        primary_velocity,
    )

    miss_distance_km = magnitude(
        relative_position
    )

    relative_velocity_km_s = magnitude(
        relative_velocity
    )

    delta_t_seconds = (
        tca
        - candidate.primary.when
    ).total_seconds()

    return ClosestApproach(
        primary_object_id=(
            candidate.primary.object_id
        ),
        secondary_object_id=(
            candidate.secondary.object_id
        ),
        tca=tca,
        miss_distance_km=(
            miss_distance_km
        ),
        relative_velocity_km_s=(
            relative_velocity_km_s
        ),
        delta_t_seconds=(
            delta_t_seconds
        ),
        method="numerical-propagation",
    )
