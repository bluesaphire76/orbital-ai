from __future__ import annotations

from datetime import timedelta

from orbital_engine.conjunction.distance import (
    add_scaled,
    dot,
    magnitude,
    subtract,
)
from orbital_engine.conjunction.models import (
    CandidatePair,
    ClosestApproach,
)


def refine_closest_approach(
    candidate: CandidatePair,
    *,
    half_window_seconds: float = 300.0,
) -> ClosestApproach:
    if half_window_seconds <= 0:
        raise ValueError(
            "half_window_seconds must be greater than zero"
        )

    primary = candidate.primary
    secondary = candidate.secondary

    relative_position = subtract(
        secondary.position_km,
        primary.position_km,
    )

    relative_velocity = subtract(
        secondary.velocity_km_s,
        primary.velocity_km_s,
    )

    relative_speed_squared = dot(
        relative_velocity,
        relative_velocity,
    )

    if relative_speed_squared == 0.0:
        delta_t_seconds = 0.0

    else:
        unconstrained_dt = (
            -dot(
                relative_position,
                relative_velocity,
            )
            / relative_speed_squared
        )

        delta_t_seconds = max(
            -half_window_seconds,
            min(
                half_window_seconds,
                unconstrained_dt,
            ),
        )

    relative_position_at_tca = add_scaled(
        relative_position,
        relative_velocity,
        delta_t_seconds,
    )

    miss_distance_km = magnitude(
        relative_position_at_tca
    )

    relative_velocity_km_s = magnitude(
        relative_velocity
    )

    tca = primary.when + timedelta(
        seconds=delta_t_seconds
    )

    return ClosestApproach(
        primary_object_id=(
            primary.object_id
        ),
        secondary_object_id=(
            secondary.object_id
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
    )
