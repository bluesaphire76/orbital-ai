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
