from datetime import date

import pytest

from backend.app.services.orbital_catalog import (
    build_orbital_object_values,
)


def test_build_orbital_object_values() -> None:
    record = {
        "NORAD_CAT_ID": 25544,
        "OBJECT_NAME": "ISS (ZARYA)",
        "OBJECT_ID": "1998-067A",
        "OBJECT_TYPE": "PAYLOAD",
        "COUNTRY_CODE": "ISS",
        "LAUNCH_DATE": "1998-11-20",
    }

    norad_cat_id, values = (
        build_orbital_object_values(record)
    )

    assert norad_cat_id == 25544
    assert values["object_name"] == "ISS (ZARYA)"
    assert values["object_id"] == "1998-067A"
    assert values["object_type"] == "PAYLOAD"
    assert values["launch_date"] == date(
        1998,
        11,
        20,
    )
    assert values["source"] == "celestrak"


def test_missing_norad_cat_id_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="NORAD_CAT_ID",
    ):
        build_orbital_object_values(
            {
                "OBJECT_NAME": "Unknown",
            }
        )


def test_gp_record_preserves_satcat_metadata() -> None:
    record = {
        "NORAD_CAT_ID": 25544,
        "OBJECT_NAME": "ISS (ZARYA)",
        "OBJECT_ID": "1998-067A",
        "EPOCH": "2026-09-17T12:00:00",
        "MEAN_MOTION": 15.49,
    }

    _, values = (
        build_orbital_object_values(
            record
        )
    )

    assert (
        values["object_name"]
        == "ISS (ZARYA)"
    )

    assert (
        values["object_id"]
        == "1998-067A"
    )

    assert (
        "object_type"
        not in values
    )

    assert (
        "country_code"
        not in values
    )

    assert (
        "launch_date"
        not in values
    )

    assert (
        "decay_date"
        not in values
    )
