from datetime import datetime, timedelta, timezone

import pytest

from backend.app.services.ephemeris_quality import (
    EphemerisStatus,
    assess_ephemeris_quality,
)


TARGET = datetime(
    2026,
    9,
    15,
    0,
    0,
    tzinfo=timezone.utc,
)


@pytest.mark.parametrize(
    (
        "age_hours",
        "expected_status",
        "expected_allowed",
    ),
    [
        (2, EphemerisStatus.FRESH, True),
        (18, EphemerisStatus.AGING, True),
        (48, EphemerisStatus.STALE, True),
        (96, EphemerisStatus.EXPIRED, False),
    ],
)
def test_ephemeris_quality(
    age_hours: float,
    expected_status: EphemerisStatus,
    expected_allowed: bool,
) -> None:
    epoch = TARGET - timedelta(
        hours=age_hours
    )

    quality = assess_ephemeris_quality(
        epoch=epoch,
        target_time=TARGET,
        warning_hours=12,
        stale_hours=24,
        max_hours=72,
    )

    assert quality.status == expected_status
    assert (
        quality.propagation_allowed
        is expected_allowed
    )


def test_invalid_thresholds_are_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="Invalid ephemeris thresholds",
    ):
        assess_ephemeris_quality(
            epoch=TARGET,
            target_time=TARGET,
            warning_hours=24,
            stale_hours=12,
            max_hours=72,
        )
