from __future__ import annotations

import json
import time
from dataclasses import asdict
from datetime import (
    datetime,
    timedelta,
    timezone,
)

from backend.app.services.catalog_sync_config import (
    CatalogSyncConfig,
)
from backend.app.services.catalog_sync_orchestrator import (
    DEFAULT_SYNC_ORDER,
    CatalogSyncAlreadyRunning,
    CatalogSyncSource,
    read_catalog_sync_state,
    run_catalog_sync,
)


def _utc_now() -> datetime:
    return datetime.now(
        timezone.utc
    )


def _parse_timestamp(
    value: object,
) -> datetime | None:
    if not isinstance(
        value,
        str,
    ):
        return None

    try:
        parsed = datetime.fromisoformat(
            value
        )
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(
            tzinfo=timezone.utc
        )

    return parsed.astimezone(
        timezone.utc
    )


def _intervals(
    config: CatalogSyncConfig,
) -> dict[
    CatalogSyncSource,
    int,
]:
    return {
        "satcat": (
            config
            .satcat_interval_seconds
        ),
        "celestrak": (
            config
            .celestrak_interval_seconds
        ),
        "space-track": (
            config
            .space_track_interval_seconds
        ),
    }


def _next_due_at(
    source_state: object,
    *,
    interval_seconds: int,
    config: CatalogSyncConfig,
) -> datetime | None:
    if not isinstance(
        source_state,
        dict,
    ):
        return None

    completed_at = _parse_timestamp(
        source_state.get(
            "last_completed_at"
        )
    )

    if completed_at is None:
        return None

    last_failed = (
        source_state.get(
            "last_status"
        ) == "error"
        or bool(
            source_state.get(
                "last_error"
            )
        )
    )

    if last_failed:
        next_retry_at = _parse_timestamp(
            source_state.get(
                "next_retry_at"
            )
        )

        if next_retry_at is not None:
            return next_retry_at

        consecutive_failures = max(
            1,
            int(
                source_state.get(
                    "consecutive_failures",
                    1,
                )
                or 1
            ),
        )

        return completed_at + timedelta(
            seconds=config.retry_delay_seconds(
                consecutive_failures
            )
        )

    return completed_at + timedelta(
        seconds=interval_seconds
    )


def due_sources(
    state: dict,
    *,
    now: datetime,
    config: CatalogSyncConfig,
) -> tuple[
    CatalogSyncSource,
    ...,
]:
    sources_state = state.get(
        "sources",
        {},
    )

    if not isinstance(
        sources_state,
        dict,
    ):
        sources_state = {}

    intervals = _intervals(
        config
    )

    due: list[
        CatalogSyncSource
    ] = []

    for source in DEFAULT_SYNC_ORDER:
        next_due_at = _next_due_at(
            sources_state.get(source),
            interval_seconds=(
                intervals[source]
            ),
            config=config,
        )

        if (
            next_due_at is None
            or now >= next_due_at
        ):
            due.append(source)

    return tuple(due)


def seconds_until_next_run(
    state: dict,
    *,
    now: datetime,
    config: CatalogSyncConfig,
) -> float:
    sources_state = state.get(
        "sources",
        {},
    )

    if not isinstance(
        sources_state,
        dict,
    ):
        return 0.0

    intervals = _intervals(
        config
    )

    remaining: list[float] = []

    for source in DEFAULT_SYNC_ORDER:
        next_due_at = _next_due_at(
            sources_state.get(source),
            interval_seconds=(
                intervals[source]
            ),
            config=config,
        )

        if next_due_at is None:
            return 0.0

        remaining.append(
            max(
                0.0,
                (
                    next_due_at
                    - now
                ).total_seconds(),
            )
        )

    return min(
        float(config.poll_seconds),
        min(remaining),
    )


def _print_event(
    event: str,
    **details: object,
) -> None:
    print(
        json.dumps(
            {
                "event": event,
                "timestamp": (
                    _utc_now()
                    .isoformat()
                ),
                **details,
            },
            sort_keys=True,
        ),
        flush=True,
    )


def main() -> None:
    config = (
        CatalogSyncConfig.from_env()
    )

    _print_event(
        "catalog_sync_scheduler_started",
        config=asdict(config),
    )

    while True:
        state = read_catalog_sync_state()
        now = _utc_now()
        sources = due_sources(
            state,
            now=now,
            config=config,
        )

        if not sources:
            time.sleep(
                seconds_until_next_run(
                    state,
                    now=now,
                    config=config,
                )
            )
            continue

        try:
            outcomes = run_catalog_sync(
                sources=sources,
                celestrak_group=(
                    config.celestrak_group
                ),
                celestrak_max_records=(
                    config
                    .celestrak_max_records
                ),
            )
        except CatalogSyncAlreadyRunning as exc:
            _print_event(
                "catalog_sync_scheduler_lock_busy",
                error=str(exc),
            )
            time.sleep(
                config.poll_seconds
            )
            continue

        _print_event(
            "catalog_sync_scheduler_completed",
            outcomes=[
                asdict(outcome)
                for outcome in outcomes
            ],
        )


if __name__ == "__main__":
    main()
