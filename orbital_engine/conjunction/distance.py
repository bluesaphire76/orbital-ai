from __future__ import annotations

from math import sqrt

from orbital_engine.conjunction.models import Vector3


def subtract(
    a: Vector3,
    b: Vector3,
) -> Vector3:
    return (
        a[0] - b[0],
        a[1] - b[1],
        a[2] - b[2],
    )


def add_scaled(
    position: Vector3,
    velocity: Vector3,
    seconds: float,
) -> Vector3:
    return (
        position[0] + velocity[0] * seconds,
        position[1] + velocity[1] * seconds,
        position[2] + velocity[2] * seconds,
    )


def dot(
    a: Vector3,
    b: Vector3,
) -> float:
    return (
        a[0] * b[0]
        + a[1] * b[1]
        + a[2] * b[2]
    )


def magnitude(
    vector: Vector3,
) -> float:
    return sqrt(
        dot(vector, vector)
    )


def distance_km(
    a: Vector3,
    b: Vector3,
) -> float:
    return magnitude(
        subtract(a, b)
    )


def relative_velocity_km_s(
    a: Vector3,
    b: Vector3,
) -> float:
    return magnitude(
        subtract(a, b)
    )
