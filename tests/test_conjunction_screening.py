from datetime import datetime, timezone

from orbital_engine.conjunction.models import (
    StateVector,
)
from orbital_engine.conjunction.screening import (
    find_candidate_pairs,
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
    x: float,
    y: float,
    z: float,
) -> StateVector:
    return StateVector(
        object_id=object_id,
        when=WHEN,
        position_km=(x, y, z),
        velocity_km_s=(0.0, 0.0, 0.0),
    )


def test_screening_finds_near_pair() -> None:
    states = [
        _state(1, 0.0, 0.0, 0.0),
        _state(2, 3.0, 4.0, 0.0),
        _state(3, 100.0, 0.0, 0.0),
    ]

    candidates = find_candidate_pairs(
        states,
        screening_distance_km=10.0,
    )

    assert len(candidates) == 1

    candidate = candidates[0]

    assert candidate.primary.object_id == 1
    assert candidate.secondary.object_id == 2
    assert candidate.screening_distance_km == 5.0


def test_screening_does_not_duplicate_pairs() -> None:
    states = [
        _state(1, 0.0, 0.0, 0.0),
        _state(2, 1.0, 0.0, 0.0),
        _state(3, 2.0, 0.0, 0.0),
    ]

    candidates = find_candidate_pairs(
        states,
        screening_distance_km=5.0,
    )

    pairs = {
        (
            candidate.primary.object_id,
            candidate.secondary.object_id,
        )
        for candidate in candidates
    }

    assert pairs == {
        (1, 2),
        (1, 3),
        (2, 3),
    }
