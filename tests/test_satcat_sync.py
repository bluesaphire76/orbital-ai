from backend.app.services.satcat_sync import (
    build_satcat_object_values,
    normalize_object_type,
)


def test_normalize_satcat_types():
    assert (
        normalize_object_type(
            "PAY"
        )
        == "PAYLOAD"
    )

    assert (
        normalize_object_type(
            "R/B"
        )
        == "ROCKET_BODY"
    )

    assert (
        normalize_object_type(
            "DEB"
        )
        == "DEBRIS"
    )


def test_satcat_supports_six_digit_catalog_ids():
    record = {
        "OBJECT_NAME":
            "TEST OBJECT",

        "OBJECT_ID":
            "2026-001A",

        "NORAD_CAT_ID":
            "100688",

        "OBJECT_TYPE":
            "PAY",

        "OPS_STATUS_CODE":
            "+",

        "OWNER":
            "US",

        "LAUNCH_DATE":
            "2026-07-11",

        "LAUNCH_SITE":
            "AFETR",

        "DECAY_DATE":
            "",

        "PERIOD":
            "95.5",

        "INCLINATION":
            "51.6",

        "APOGEE":
            "550",

        "PERIGEE":
            "540",

        "RCS":
            "2.5",

        "DATA_STATUS_CODE":
            "",

        "ORBIT_CENTER":
            "EA",

        "ORBIT_TYPE":
            "ORB",
    }

    norad_cat_id, values = (
        build_satcat_object_values(
            record
        )
    )

    assert norad_cat_id == 100688
    assert values[
        "object_type"
    ] == "PAYLOAD"

    assert values[
        "owner"
    ] == "US"

    assert values[
        "is_on_orbit"
    ] is True

    assert values[
        "apogee_km"
    ] == 550.0


def test_earth_orbit_classification():
    record = {
        "OBJECT_NAME": "EARTH OBJECT",
        "NORAD_CAT_ID": "100700",
        "OBJECT_TYPE": "PAY",
        "DECAY_DATE": "",
        "ORBIT_CENTER": "EA",
        "ORBIT_TYPE": "ORB",
    }

    _, values = (
        build_satcat_object_values(
            record
        )
    )

    assert values[
        "is_on_orbit"
    ] is True

    assert values[
        "is_earth_orbit"
    ] is True


def test_non_earth_orbit_is_not_screening_orbit():
    record = {
        "OBJECT_NAME": "LUNAR OBJECT",
        "NORAD_CAT_ID": "100701",
        "OBJECT_TYPE": "PAY",
        "DECAY_DATE": "",
        "ORBIT_CENTER": "MO",
        "ORBIT_TYPE": "ORB",
    }

    _, values = (
        build_satcat_object_values(
            record
        )
    )

    assert values[
        "is_on_orbit"
    ] is True

    assert values[
        "is_earth_orbit"
    ] is False
