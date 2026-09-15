from orbital_engine.conjunction.distance import (
    distance_km,
    relative_velocity_km_s,
)


def test_distance_km() -> None:
    assert distance_km(
        (0.0, 0.0, 0.0),
        (3.0, 4.0, 0.0),
    ) == 5.0


def test_relative_velocity() -> None:
    assert relative_velocity_km_s(
        (1.0, 0.0, 0.0),
        (0.0, 0.0, 0.0),
    ) == 1.0
