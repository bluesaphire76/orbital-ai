from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping


DEFAULT_SATCAT_INTERVAL_SECONDS = 12 * 60 * 60
DEFAULT_CELESTRAK_INTERVAL_SECONDS = 2 * 60 * 60
DEFAULT_SPACE_TRACK_INTERVAL_SECONDS = 60 * 60
DEFAULT_POLL_SECONDS = 60
DEFAULT_RETRY_INITIAL_SECONDS = 60
DEFAULT_RETRY_MAX_SECONDS = 30 * 60
DEFAULT_RETRY_MULTIPLIER = 2
DEFAULT_CELESTRAK_GROUP = "ACTIVE"
DEFAULT_CELESTRAK_MAX_RECORDS = 40_000


def _positive_int(
    environment: Mapping[str, str],
    name: str,
    default: int,
) -> int:
    raw_value = environment.get(
        name,
        str(default),
    )

    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(
            f"{name} must be an integer"
        ) from exc

    if value <= 0:
        raise ValueError(
            f"{name} must be greater than zero"
        )

    return value


@dataclass(frozen=True, slots=True)
class CatalogSyncConfig:
    satcat_interval_seconds: int
    celestrak_interval_seconds: int
    space_track_interval_seconds: int
    poll_seconds: int
    retry_initial_seconds: int
    retry_max_seconds: int
    retry_multiplier: int
    celestrak_group: str
    celestrak_max_records: int

    def retry_delay_seconds(
        self,
        consecutive_failures: int,
    ) -> int:
        if consecutive_failures <= 0:
            raise ValueError(
                "consecutive_failures must be "
                "greater than zero"
            )

        delay = self.retry_initial_seconds

        for _ in range(
            consecutive_failures - 1
        ):
            if delay >= self.retry_max_seconds:
                return self.retry_max_seconds

            delay = min(
                self.retry_max_seconds,
                delay * self.retry_multiplier,
            )

        return delay

    @classmethod
    def from_env(
        cls,
        environment: Mapping[str, str] | None = None,
    ) -> "CatalogSyncConfig":
        values = (
            os.environ
            if environment is None
            else environment
        )

        group = values.get(
            "ORBITAL_CATALOG_SYNC_CELESTRAK_GROUP",
            DEFAULT_CELESTRAK_GROUP,
        ).strip().upper()

        if not group:
            raise ValueError(
                "ORBITAL_CATALOG_SYNC_CELESTRAK_GROUP "
                "cannot be empty"
            )

        retry_initial_seconds = _positive_int(
            values,
            "ORBITAL_CATALOG_SYNC_RETRY_INITIAL_SECONDS",
            DEFAULT_RETRY_INITIAL_SECONDS,
        )

        retry_max_seconds = _positive_int(
            values,
            "ORBITAL_CATALOG_SYNC_RETRY_MAX_SECONDS",
            DEFAULT_RETRY_MAX_SECONDS,
        )

        if retry_max_seconds < retry_initial_seconds:
            raise ValueError(
                "ORBITAL_CATALOG_SYNC_RETRY_MAX_SECONDS "
                "must be greater than or equal to "
                "ORBITAL_CATALOG_SYNC_RETRY_INITIAL_SECONDS"
            )

        retry_multiplier = _positive_int(
            values,
            "ORBITAL_CATALOG_SYNC_RETRY_MULTIPLIER",
            DEFAULT_RETRY_MULTIPLIER,
        )

        if retry_multiplier < 2:
            raise ValueError(
                "ORBITAL_CATALOG_SYNC_RETRY_MULTIPLIER "
                "must be greater than or equal to 2"
            )

        return cls(
            satcat_interval_seconds=_positive_int(
                values,
                "ORBITAL_CATALOG_SYNC_SATCAT_INTERVAL_SECONDS",
                DEFAULT_SATCAT_INTERVAL_SECONDS,
            ),
            celestrak_interval_seconds=_positive_int(
                values,
                "ORBITAL_CATALOG_SYNC_CELESTRAK_INTERVAL_SECONDS",
                DEFAULT_CELESTRAK_INTERVAL_SECONDS,
            ),
            space_track_interval_seconds=_positive_int(
                values,
                "ORBITAL_CATALOG_SYNC_SPACE_TRACK_INTERVAL_SECONDS",
                DEFAULT_SPACE_TRACK_INTERVAL_SECONDS,
            ),
            poll_seconds=_positive_int(
                values,
                "ORBITAL_CATALOG_SYNC_POLL_SECONDS",
                DEFAULT_POLL_SECONDS,
            ),
            retry_initial_seconds=retry_initial_seconds,
            retry_max_seconds=retry_max_seconds,
            retry_multiplier=retry_multiplier,
            celestrak_group=group,
            celestrak_max_records=_positive_int(
                values,
                "ORBITAL_CATALOG_SYNC_CELESTRAK_MAX_RECORDS",
                DEFAULT_CELESTRAK_MAX_RECORDS,
            ),
        )
