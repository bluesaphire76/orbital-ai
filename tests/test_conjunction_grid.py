from datetime import datetime, timedelta, timezone

import pytest

from orbital_engine.conjunction.grid import (
    inflated_screening_distance_km,
    screen_propagation_grid,
)
from orbital_engine.conjunction.models import (
    StateVector,
)


WHEN = datetime(
    2026,
    9,
    15,
    0,
    0,
    tzinfo=timezone.utc,
)


def _state(
    object_id: int,
    when: datetime,
    position: tuple[float, float, float],
    velocity: tuple[float, float, float],
) -> StateVector:
    return StateVector(
        object_id=object_id,
        when=when,
        position_km=position,
        velocity_km_s=velocity,
    )


def test_screening_distance_is_inflated() -> None:
    result = inflated_screening_distance_km(
        candidate_distance_km=10.0,
        step_seconds=60.0,
        max_relative_speed_km_s=16.0,
    )

    assert result == pytest.approx(
        490.0
    )


def test_grid_refines_crossing_pair() -> None:
    primary = _state(
        1,
        WHEN,
        (0.0, 0.0, 0.0),
        (0.0, 0.0, 0.0),
    )

    secondary = _state(
        2,
        WHEN,
        (10.0, 1.0, 0.0),
        (-1.0, 0.0, 0.0),
    )

    result = screen_propagation_grid(
        [
            (
                WHEN,
                [primary, secondary],
            ),
            (
                WHEN + timedelta(
                    seconds=60
                ),
                [],
            ),
        ],
        candidate_distance_km=2.0,
        step_seconds=60.0,
        max_relative_speed_km_s=16.0,
    )

    assert len(
        result.conjunctions
    ) == 1

    conjunction = (
        result.conjunctions[0]
    )

    assert (
        conjunction.miss_distance_km
        == pytest.approx(1.0)
    )

    assert (
        conjunction.tca
        == WHEN
        + timedelta(seconds=10)
    )


def test_grid_deduplicates_pair() -> None:
    first_time = WHEN
    second_time = (
        WHEN
        + timedelta(seconds=60)
    )

    snapshots = [
        (
            first_time,
            [
                _state(
                    1,
                    first_time,
                    (0.0, 0.0, 0.0),
                    (0.0, 0.0, 0.0),
                ),
                _state(
                    2,
                    first_time,
                    (5.0, 0.0, 0.0),
                    (0.0, 0.0, 0.0),
                ),
            ],
        ),
        (
            second_time,
            [
                _state(
                    1,
                    second_time,
                    (0.0, 0.0, 0.0),
                    (0.0, 0.0, 0.0),
                ),
                _state(
                    2,
                    second_time,
                    (4.0, 0.0, 0.0),
                    (0.0, 0.0, 0.0),
                ),
            ],
        ),
    ]

    result = screen_propagation_grid(
        snapshots,
        candidate_distance_km=10.0,
        step_seconds=60.0,
    )

    assert (
        result.raw_candidates
        == 2
    )

    assert (
        result.unique_candidates
        == 1
    )


def test_grid_suppresses_excluded_shared_solution_pair() -> None:
    primary = _state(
        1,
        WHEN,
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
    )

    secondary = _state(
        2,
        WHEN,
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
    )

    result = screen_propagation_grid(
        [
            (
                WHEN,
                [
                    primary,
                    secondary,
                ],
            )
        ],
        candidate_distance_km=10.0,
        step_seconds=60.0,
        excluded_pairs={
            (1, 2),
        },
    )

    assert (
        result.raw_candidates
        == 1
    )

    assert (
        result.suppressed_shared_pairs
        == 1
    )

    assert (
        result.unique_candidates
        == 0
    )

    assert (
        result.conjunctions
        == ()
    )
