from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum


class EphemerisStatus(StrEnum):
    FRESH = "fresh"
    AGING = "aging"
    STALE = "stale"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class EphemerisQuality:
    age_seconds: float
    age_hours: float
    status: EphemerisStatus
    propagation_allowed: bool


def assess_ephemeris_quality(
    *,
    epoch: datetime,
    target_time: datetime,
    warning_hours: float,
    stale_hours: float,
    max_hours: float,
) -> EphemerisQuality:
    if epoch.tzinfo is None:
        raise ValueError(
            "Ephemeris epoch must be timezone-aware"
        )

    if target_time.tzinfo is None:
        raise ValueError(
            "Target time must be timezone-aware"
        )

    if not (
        0 < warning_hours
        <= stale_hours
        <= max_hours
    ):
        raise ValueError(
            "Invalid ephemeris thresholds"
        )

    epoch_utc = epoch.astimezone(
        timezone.utc
    )
    target_utc = target_time.astimezone(
        timezone.utc
    )

    age_seconds = (
        target_utc - epoch_utc
    ).total_seconds()

    age_hours = age_seconds / 3600.0

    # Target time earlier than the element epoch.
    if age_seconds < 0:
        return EphemerisQuality(
            age_seconds=age_seconds,
            age_hours=age_hours,
            status=EphemerisStatus.FRESH,
            propagation_allowed=True,
        )

    if age_hours <= warning_hours:
        status = EphemerisStatus.FRESH
        allowed = True

    elif age_hours <= stale_hours:
        status = EphemerisStatus.AGING
        allowed = True

    elif age_hours <= max_hours:
        status = EphemerisStatus.STALE
        allowed = True

    else:
        status = EphemerisStatus.EXPIRED
        allowed = False

    return EphemerisQuality(
        age_seconds=age_seconds,
        age_hours=age_hours,
        status=status,
        propagation_allowed=allowed,
    )
