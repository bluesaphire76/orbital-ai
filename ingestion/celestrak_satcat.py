from __future__ import annotations

import csv
import time
from io import StringIO
from pathlib import Path
from typing import Any

import httpx


CELESTRAK_SATCAT_URL = (
    "https://celestrak.org/pub/satcat.csv"
)

DEFAULT_CACHE_TTL_SECONDS = (
    12 * 60 * 60
)

USER_AGENT = (
    "OrbitalAI-SATCAT/0.3 "
    "(https://github.com/bluesaphire76/orbital-ai)"
)


_REQUIRED_FIELDS = {
    "OBJECT_NAME",
    "NORAD_CAT_ID",
    "OBJECT_TYPE",
}


def _cache_is_fresh(
    path: Path,
    *,
    max_age_seconds: int,
) -> bool:
    if not path.exists():
        return False

    return (
        time.time()
        - path.stat().st_mtime
        <= max_age_seconds
    )


def _parse_csv(
    content: str,
) -> list[dict[str, Any]]:
    reader = csv.DictReader(
        StringIO(content)
    )

    fields = set(
        reader.fieldnames
        or []
    )

    missing = (
        _REQUIRED_FIELDS
        - fields
    )

    if missing:
        raise RuntimeError(
            "SATCAT CSV missing required fields: "
            + ", ".join(
                sorted(missing)
            )
        )

    records = [
        dict(record)
        for record in reader
        if record.get(
            "NORAD_CAT_ID"
        )
    ]

    if not records:
        raise RuntimeError(
            "CelesTrak SATCAT returned no records"
        )

    return records


def fetch_satcat_csv(
    cache_dir: Path = Path(
        "data/raw/celestrak"
    ),
    max_age_seconds: int = (
        DEFAULT_CACHE_TTL_SECONDS
    ),
) -> tuple[
    list[dict[str, Any]],
    bool,
]:
    cache_path = (
        cache_dir
        / "satcat.csv"
    )

    if _cache_is_fresh(
        cache_path,
        max_age_seconds=max_age_seconds,
    ):
        return (
            _parse_csv(
                cache_path.read_text(
                    encoding="utf-8-sig"
                )
            ),
            True,
        )


    headers = {
        "User-Agent":
            USER_AGENT,
    }


    with httpx.Client(
        timeout=60.0,
        follow_redirects=True,
        headers=headers,
    ) as client:
        response = client.get(
            CELESTRAK_SATCAT_URL
        )

        response.raise_for_status()

        content = (
            response.content
            .decode(
                "utf-8-sig"
            )
        )


    records = _parse_csv(
        content
    )


    cache_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    cache_path.write_text(
        content,
        encoding="utf-8",
    )


    return records, False
