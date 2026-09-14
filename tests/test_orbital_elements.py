from datetime import timezone

import pytest

from backend.app.services.orbital_elements import (
    build_orbital_element_values,
)


def test_build_orbital_element_values() -> None:
    record = {
        "EPOCH": "2026-09-14T03:26:13.932384",
        "ELEMENT_SET_NO": 999,
        "EPHEMERIS_TYPE": 0,
        "INCLINATION": 51.6341,
        "RA_OF_ASC_NODE": 123.456,
        "ECCENTRICITY": 0.0001234,
        "ARG_OF_PERICENTER": 42.0,
        "MEAN_ANOMALY": 180.0,
        "MEAN_MOTION": 15.5,
        "MEAN_MOTION_DOT": 0.0001,
        "MEAN_MOTION_DDOT": 0.0,
        "BSTAR": 0.0002,
        "REV_AT_EPOCH": 12345,
    }

    values = build_orbital_element_values(
        record
    )

    assert values["epoch"].tzinfo == timezone.utc
    assert values["mean_motion"] == 15.5
    assert values["eccentricity"] == 0.0001234
    assert values["source"] == "celestrak"
    assert values["raw_omm"] == record


def test_missing_required_omm_field_is_rejected() -> None:
    record = {
        "EPOCH": "2026-09-14T03:26:13Z",
    }

    with pytest.raises(
        ValueError,
        match="missing required fields",
    ):
        build_orbital_element_values(
            record
        )
