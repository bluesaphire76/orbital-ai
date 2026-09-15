from datetime import datetime, timedelta, timezone

import pytest

from orbital_engine.conjunction.models import (
    CandidatePair,
    StateVector,
)
from orbital_engine.conjunction.refinement import (
    refine_closest_approach,
)


WHEN = datetime(
    2026,
    9,
    15,
    0,
    0,
    tzinfo=timezone.utc,
)


def test_linear_closest_approach() -> None:
    primary = StateVector(
        object_id=1,
        when=WHEN,
        position_km=(0.0, 0.0, 0.0),
        velocity_km_s=(0.0, 0.0, 0.0),
    )

    secondary = StateVector(
        object_id=2,
        when=WHEN,
        position_km=(10.0, 1.0, 0.0),
        velocity_km_s=(-1.0, 0.0, 0.0),
    )

    candidate = CandidatePair(
        primary=primary,
        secondary=secondary,
        screening_distance_km=10.05,
    )

    result = refine_closest_approach(
        candidate,
        half_window_seconds=60.0,
    )

    assert result.delta_t_seconds == pytest.approx(
        10.0
    )

    assert result.tca == (
        WHEN + timedelta(seconds=10)
    )

    assert result.miss_distance_km == pytest.approx(
        1.0
    )

    assert (
        result.relative_velocity_km_s
        == pytest.approx(1.0)
    )


def test_zero_relative_velocity() -> None:
    primary = StateVector(
        object_id=1,
        when=WHEN,
        position_km=(0.0, 0.0, 0.0),
        velocity_km_s=(1.0, 0.0, 0.0),
    )

    secondary = StateVector(
        object_id=2,
        when=WHEN,
        position_km=(5.0, 0.0, 0.0),
        velocity_km_s=(1.0, 0.0, 0.0),
    )

    candidate = CandidatePair(
        primary=primary,
        secondary=secondary,
        screening_distance_km=5.0,
    )

    result = refine_closest_approach(
        candidate
    )

    assert result.delta_t_seconds == 0.0
    assert result.miss_distance_km == 5.0
    assert result.relative_velocity_km_s == 0.0
