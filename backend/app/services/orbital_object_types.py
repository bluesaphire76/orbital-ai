from __future__ import annotations

from typing import Any


OBJECT_TYPE_MAP = {
    "PAY": "PAYLOAD",
    "PAYLOAD": "PAYLOAD",

    "R/B": "ROCKET_BODY",
    "ROCKET BODY": "ROCKET_BODY",
    "ROCKET_BODY": "ROCKET_BODY",

    "DEB": "DEBRIS",
    "DEBRIS": "DEBRIS",

    "UNK": "UNKNOWN",
    "UNKNOWN": "UNKNOWN",
}


def normalize_object_type(
    value: Any,
) -> str:
    if value is None:
        return "UNKNOWN"

    normalized = str(
        value
    ).strip().upper()

    if not normalized:
        return "UNKNOWN"

    return OBJECT_TYPE_MAP.get(
        normalized,
        normalized.replace(
            " ",
            "_",
        ),
    )
