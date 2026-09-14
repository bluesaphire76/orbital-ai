from __future__ import annotations

from datetime import datetime, timezone

from sgp4 import omm
from sgp4.api import SGP4_ERRORS, Satrec, jday


def satrec_from_omm(record: dict) -> Satrec:
    """Create an SGP4 satellite model from an OMM record."""

    satellite = Satrec()
    omm.initialize(satellite, record)

    return satellite


def propagate_utc(
    satellite: Satrec,
    when: datetime,
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """
    Propagate a satellite to a UTC datetime.

    Returns:
        position_km
        velocity_km_s
    """

    if when.tzinfo is None:
        raise ValueError("Datetime must be timezone-aware")

    when = when.astimezone(timezone.utc)

    seconds = when.second + when.microsecond / 1_000_000

    jd, fraction = jday(
        when.year,
        when.month,
        when.day,
        when.hour,
        when.minute,
        seconds,
    )

    error, position, velocity = satellite.sgp4(jd, fraction)

    if error:
        description = SGP4_ERRORS.get(error, "Unknown SGP4 error")
        raise RuntimeError(
            f"SGP4 propagation failed ({error}): {description}"
        )

    return position, velocity
