from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import httpx


LOGIN_URL = (
    "https://www.space-track.org/"
    "ajaxauth/login"
)

GP_CURRENT_URL = (
    "https://www.space-track.org/"
    "basicspacedata/query/"
    "class/gp/"
    "decay_date/null-val/"
    "epoch/%3Enow-10/"
    "orderby/NORAD_CAT_ID/"
    "format/json"
)

DEFAULT_CACHE_TTL_SECONDS = (
    60 * 60
)

USER_AGENT = (
    "OrbitalAI/0.3 "
    "(https://github.com/"
    "bluesaphire76/orbital-ai)"
)


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


def _load_cache(
    path: Path,
) -> list[dict[str, Any]]:
    data = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(
        data,
        list,
    ):
        raise RuntimeError(
            "Invalid Space-Track GP cache"
        )

    return data


def _write_cache(
    path: Path,
    records: list[
        dict[str, Any]
    ],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = (
        path.with_suffix(
            ".tmp"
        )
    )

    temporary.write_text(
        json.dumps(
            records,
            separators=(
                ",",
                ":",
            ),
        ),
        encoding="utf-8",
    )

    temporary.replace(
        path
    )


def fetch_current_gp(
    cache_dir: Path = Path(
        "data/raw/space-track"
    ),
    max_age_seconds: int = (
        DEFAULT_CACHE_TTL_SECONDS
    ),
) -> tuple[
    list[dict[str, Any]],
    bool,
]:
    identity = os.getenv(
        "SPACE_TRACK_IDENTITY"
    )

    password = os.getenv(
        "SPACE_TRACK_PASSWORD"
    )

    if not identity:
        raise RuntimeError(
            "SPACE_TRACK_IDENTITY "
            "is required"
        )

    if not password:
        raise RuntimeError(
            "SPACE_TRACK_PASSWORD "
            "is required"
        )


    cache_path = (
        cache_dir
        / "gp_current.json"
    )


    if _cache_is_fresh(
        cache_path,
        max_age_seconds=
            max_age_seconds,
    ):
        return (
            _load_cache(
                cache_path
            ),
            True,
        )


    headers = {
        "User-Agent":
            USER_AGENT,
    }


    with httpx.Client(
        timeout=180.0,
        follow_redirects=True,
        headers=headers,
    ) as client:
        login_response = (
            client.post(
                LOGIN_URL,
                data={
                    "identity":
                        identity,

                    "password":
                        password,
                },
            )
        )

        login_response.raise_for_status()


        response = client.get(
            GP_CURRENT_URL
        )

        response.raise_for_status()


        try:
            records = (
                response.json()
            )

        except Exception as exc:
            raise RuntimeError(
                "Space-Track GP response "
                "is not JSON; authentication "
                "may have failed"
            ) from exc


    if not isinstance(
        records,
        list,
    ):
        raise RuntimeError(
            "Unexpected Space-Track "
            "GP response"
        )


    if not records:
        raise RuntimeError(
            "Space-Track returned "
            "no GP records"
        )


    _write_cache(
        cache_path,
        records,
    )


    return (
        records,
        False,
    )
