from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def parse_omm_epoch(value: Any) -> datetime:
    if not value:
        raise ValueError("OMM record is missing EPOCH")

    if isinstance(value, datetime):
        epoch = value
    else:
        epoch = datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )

    if epoch.tzinfo is None:
        epoch = epoch.replace(
            tzinfo=timezone.utc
        )

    return epoch.astimezone(
        timezone.utc
    )


def build_orbital_element_values(
    record: dict[str, Any],
) -> dict[str, Any]:
    required_fields = (
        "INCLINATION",
        "RA_OF_ASC_NODE",
        "ECCENTRICITY",
        "ARG_OF_PERICENTER",
        "MEAN_ANOMALY",
        "MEAN_MOTION",
    )

    missing = [
        field
        for field in required_fields
        if record.get(field) in (None, "")
    ]

    if missing:
        raise ValueError(
            "OMM record is missing required fields: "
            + ", ".join(missing)
        )

    return {
        "source": "celestrak",
        "epoch": parse_omm_epoch(
            record.get("EPOCH")
        ),
        "element_set_no": _optional_int(
            record.get("ELEMENT_SET_NO")
        ),
        "ephemeris_type": _optional_int(
            record.get("EPHEMERIS_TYPE")
        ),
        "inclination": float(
            record["INCLINATION"]
        ),
        "ra_of_asc_node": float(
            record["RA_OF_ASC_NODE"]
        ),
        "eccentricity": float(
            record["ECCENTRICITY"]
        ),
        "arg_of_pericenter": float(
            record["ARG_OF_PERICENTER"]
        ),
        "mean_anomaly": float(
            record["MEAN_ANOMALY"]
        ),
        "mean_motion": float(
            record["MEAN_MOTION"]
        ),
        "mean_motion_dot": _optional_float(
            record.get("MEAN_MOTION_DOT")
        ),
        "mean_motion_ddot": _optional_float(
            record.get("MEAN_MOTION_DDOT")
        ),
        "bstar": _optional_float(
            record.get("BSTAR")
        ),
        "rev_at_epoch": _optional_int(
            record.get("REV_AT_EPOCH")
        ),
        "raw_omm": dict(record),
    }


def _optional_float(
    value: Any,
) -> float | None:
    if value in (None, ""):
        return None

    return float(value)


def _optional_int(
    value: Any,
) -> int | None:
    if value in (None, ""):
        return None

    return int(value)
