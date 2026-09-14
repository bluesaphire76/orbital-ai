from __future__ import annotations

import json
import time
from pathlib import Path

import httpx


CELESTRAK_GP_URL = "https://celestrak.org/NORAD/elements/gp.php"
DEFAULT_CACHE_TTL_SECONDS = 2 * 60 * 60


def fetch_gp_by_catnr(
    catnr: int,
    cache_dir: Path = Path("data/raw/celestrak"),
    max_age_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
) -> tuple[list[dict], bool]:
    """
    Fetch CelesTrak General Perturbations data in OMM-compatible JSON.

    Returns:
        (records, from_cache)
    """

    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"gp_catnr_{catnr}.json"

    if cache_file.exists():
        age = time.time() - cache_file.stat().st_mtime

        if age < max_age_seconds:
            records = json.loads(cache_file.read_text(encoding="utf-8"))
            return records, True

    params = {
        "CATNR": str(catnr),
        "FORMAT": "JSON",
    }

    headers = {
        "User-Agent": (
            "OrbitalAI/0.1 "
            "(https://github.com/bluesaphire76/orbital-ai)"
        )
    }

    with httpx.Client(
        timeout=30.0,
        follow_redirects=True,
        headers=headers,
    ) as client:
        response = client.get(CELESTRAK_GP_URL, params=params)
        response.raise_for_status()
        records = response.json()

    if not isinstance(records, list) or not records:
        raise RuntimeError(
            f"CelesTrak returned no GP data for NORAD CATNR {catnr}"
        )

    cache_file.write_text(
        json.dumps(records, indent=2),
        encoding="utf-8",
    )

    return records, False
