from datetime import datetime, timedelta, timezone

import pytest

from orbital_engine.conjunction.models import (
    CandidatePair,
    StateVector,
)
from orbital_engine.conjunction.numerical_refinement import (
    refine_closest_approach_numerical,
)


WHEN = datetime(
    2026,
    9,
    15,
    0,
    0,
    tzinfo=timezone.utc,
)


def test_numerical_refinement_finds_known_tca() -> None:
    candidate = CandidatePair(
        primary=StateVector(
            object_id=1,
            when=WHEN,
            position_km=(0.0, 0.0, 0.0),
            velocity_km_s=(0.0, 0.0, 0.0),
        ),
        secondary=StateVector(
            object_id=2,
            when=WHEN,
            position_km=(10.0, 1.0, 0.0),
            velocity_km_s=(-1.0, 0.0, 0.0),
        ),
        screening_distance_km=10.05,
    )

    def primary_state_at(
        when: datetime,
    ):
        return (
            (0.0, 0.0, 0.0),
            (0.0, 0.0, 0.0),
        )

    def secondary_state_at(
        when: datetime,
    ):
        seconds = (
            when - WHEN
        ).total_seconds()

        return (
            (
                10.0 - seconds,
                1.0,
                0.0,
            ),
            (-1.0, 0.0, 0.0),
        )

    result = (
        refine_closest_approach_numerical(
            candidate,
            primary_state_at=(
                primary_state_at
            ),
            secondary_state_at=(
                secondary_state_at
            ),
            search_start=WHEN,
            search_end=(
                WHEN
                + timedelta(
                    seconds=20
                )
            ),
            tolerance_seconds=0.001,
        )
    )

    assert abs(
        (
            result.tca
            - (
                WHEN
                + timedelta(
                    seconds=10
                )
            )
        ).total_seconds()
    ) < 0.01

    assert (
        result.miss_distance_km
        == pytest.approx(
            1.0,
            abs=1e-6,
        )
    )

    assert (
        result.relative_velocity_km_s
        == pytest.approx(
            1.0,
            abs=1e-6,
        )
    )

    assert (
        result.method
        == "numerical-propagation"
    )


def test_numerical_refinement_rejects_bad_window() -> None:
    state = StateVector(
        object_id=1,
        when=WHEN,
        position_km=(0.0, 0.0, 0.0),
        velocity_km_s=(0.0, 0.0, 0.0),
    )

    candidate = CandidatePair(
        primary=state,
        secondary=StateVector(
            object_id=2,
            when=WHEN,
            position_km=(1.0, 0.0, 0.0),
            velocity_km_s=(0.0, 0.0, 0.0),
        ),
        screening_distance_km=1.0,
    )

    def state_at(
        when: datetime,
    ):
        return (
            (0.0, 0.0, 0.0),
            (0.0, 0.0, 0.0),
        )

    with pytest.raises(
        ValueError,
        match="search_end",
    ):
        refine_closest_approach_numerical(
            candidate,
            primary_state_at=state_at,
            secondary_state_at=state_at,
            search_start=WHEN,
            search_end=WHEN,
        )
