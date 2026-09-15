from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
from math import isfinite

from sgp4.api import Satrec
from skyfield.api import EarthSatellite, load
from skyfield.framelib import itrs


Vector3 = tuple[
    float,
    float,
    float,
]


@lru_cache(maxsize=1)
def _timescale():
    # Explicitly use Skyfield's bundled time tables.
    # This keeps OrbitalAI local-first and avoids downloads.
    return load.timescale(
        builtin=True
    )


def _ensure_utc(
    when: datetime,
) -> datetime:
    if when.tzinfo is None:
        raise ValueError(
            "Datetime must be timezone-aware"
        )

    return when.astimezone(
        timezone.utc
    )


def itrs_state_from_satrec(
    satellite: Satrec,
    when: datetime,
) -> tuple[
    Vector3,
    Vector3,
]:
    """
    Propagate an SGP4 Satrec and return position and velocity
    in the Earth-fixed ITRS/ECEF reference frame.

    Position: km
    Velocity: km/s
    """
    when = _ensure_utc(
        when
    )

    ts = _timescale()

    skyfield_satellite = (
        EarthSatellite.from_satrec(
            satellite,
            ts,
        )
    )

    t = ts.from_datetime(
        when
    )

    geocentric = (
        skyfield_satellite.at(
            t
        )
    )

    position, velocity = (
        geocentric
        .frame_xyz_and_velocity(
            itrs
        )
    )

    xyz = tuple(
        float(value)
        for value in position.km
    )

    vxyz = tuple(
        float(value)
        for value in velocity.km_per_s
    )

    if not all(
        isfinite(value)
        for value in (
            *xyz,
            *vxyz,
        )
    ):
        raise RuntimeError(
            "Non-finite ITRS state returned"
        )

    return (
        xyz,
        vxyz,
    )
