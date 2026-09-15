from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

import httpx


CELESTRAK_GP_URL = (
    "https://celestrak.org/NORAD/elements/gp.php"
)

DEFAULT_CACHE_TTL_SECONDS = 2 * 60 * 60

USER_AGENT = (
    "OrbitalAI/0.1 "
    "(https://github.com/bluesaphire76/orbital-ai)"
)

_GROUP_PATTERN = re.compile(
    r"^[A-Z0-9_-]+$"
)


def _cache_is_fresh(
    path: Path,
    *,
    max_age_seconds: int,
) -> bool:
    if not path.exists():
        return False

    age_seconds = (
        time.time()
        - path.stat().st_mtime
    )

    return age_seconds <= max_age_seconds


def _load_cache(
    path: Path,
) -> list[dict[str, Any]]:
    data = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(data, list):
        raise RuntimeError(
            f"Invalid CelesTrak cache: {path}"
        )

    return data


def _write_cache(
    path: Path,
    records: list[dict[str, Any]],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            records,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def _fetch_gp_json(
    *,
    query: dict[str, str],
    cache_path: Path,
    max_age_seconds: int,
) -> tuple[list[dict[str, Any]], bool]:
    if _cache_is_fresh(
        cache_path,
        max_age_seconds=max_age_seconds,
    ):
        return (
            _load_cache(cache_path),
            True,
        )

    params = {
        **query,
        "FORMAT": "JSON",
    }

    headers = {
        "User-Agent": USER_AGENT,
    }

    with httpx.Client(
        timeout=30.0,
        follow_redirects=True,
        headers=headers,
    ) as client:
        response = client.get(
            CELESTRAK_GP_URL,
            params=params,
        )

        response.raise_for_status()

        records = response.json()

    if not isinstance(records, list):
        raise RuntimeError(
            "Unexpected CelesTrak response format"
        )

    if not records:
        raise RuntimeError(
            "CelesTrak returned no GP records"
        )

    _write_cache(
        cache_path,
        records,
    )

    return records, False


def normalize_group_name(
    group: str,
) -> str:
    normalized = (
        group.strip().upper()
    )

    if not normalized:
        raise ValueError(
            "CelesTrak group cannot be empty"
        )

    if not _GROUP_PATTERN.fullmatch(
        normalized
    ):
        raise ValueError(
            "Invalid CelesTrak group name"
        )

    return normalized


def fetch_gp_by_catnr(
    catnr: int,
    cache_dir: Path = Path(
        "data/raw/celestrak"
    ),
    max_age_seconds: int = (
        DEFAULT_CACHE_TTL_SECONDS
    ),
) -> tuple[list[dict[str, Any]], bool]:
    if catnr <= 0:
        raise ValueError(
            "CATNR must be greater than zero"
        )

    cache_path = (
        cache_dir
        / f"gp_catnr_{catnr}.json"
    )

    return _fetch_gp_json(
        query={
            "CATNR": str(catnr),
        },
        cache_path=cache_path,
        max_age_seconds=max_age_seconds,
    )


def fetch_gp_by_group(
    group: str,
    cache_dir: Path = Path(
        "data/raw/celestrak"
    ),
    max_age_seconds: int = (
        DEFAULT_CACHE_TTL_SECONDS
    ),
) -> tuple[list[dict[str, Any]], bool]:
    normalized = normalize_group_name(
        group
    )

    cache_path = (
        cache_dir
        / (
            "gp_group_"
            f"{normalized.lower()}.json"
        )
    )

    return _fetch_gp_json(
        query={
            "GROUP": normalized,
        },
        cache_path=cache_path,
        max_age_seconds=max_age_seconds,
    )
