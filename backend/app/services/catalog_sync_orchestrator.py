from __future__ import annotations

import fcntl
import json
import os
from contextlib import contextmanager
from dataclasses import (
    asdict,
    dataclass,
)
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from pathlib import Path
from typing import (
    Iterator,
    Literal,
)

from backend.app.db.session import (
    get_session_factory,
)
from backend.app.services.catalog_sync_config import (
    CatalogSyncConfig,
)
from backend.app.services.celestrak_sync import (
    sync_celestrak_records,
)
from backend.app.services.satcat_sync import (
    sync_satcat_records,
)
from backend.app.services.space_track_sync import (
    sync_space_track_gp,
)
from ingestion.celestrak import (
    fetch_gp_by_group,
    normalize_group_name,
)
from ingestion.celestrak_satcat import (
    fetch_satcat_csv,
)
from ingestion.providers.space_track import (
    fetch_current_gp,
)


CatalogSyncSource = Literal[
    "satcat",
    "celestrak",
    "space-track",
]

DEFAULT_SYNC_ORDER: tuple[
    CatalogSyncSource,
    ...,
] = (
    "satcat",
    "celestrak",
    "space-track",
)


class CatalogSyncAlreadyRunning(
    RuntimeError
):
    pass


@dataclass(
    frozen=True,
    slots=True,
)
class CatalogSyncOutcome:
    source: CatalogSyncSource
    status: Literal[
        "success",
        "error",
    ]

    started_at: str
    completed_at: str
    duration_seconds: float

    records: int | None
    from_cache: bool | None

    details: dict[
        str,
        object,
    ]

    error: str | None


def _utc_now() -> datetime:
    return datetime.now(
        timezone.utc
    )


def _isoformat(
    value: datetime,
) -> str:
    return value.isoformat()


def _data_root() -> Path:
    return Path(
        os.getenv(
            "ORBITAL_DATA_DIR",
            "data",
        )
    )


def _state_dir() -> Path:
    return Path(
        os.getenv(
            "ORBITAL_SYNC_STATE_DIR",
            os.getenv(
                "ORBITAL_METRICS_DIR",
                "data/observability",
            ),
        )
    )


def _state_path() -> Path:
    return (
        _state_dir()
        / "catalog-sync-status.json"
    )


def _lock_path() -> Path:
    return (
        _state_dir()
        / "catalog-sync.lock"
    )


def _read_state() -> dict:
    path = _state_path()

    if not path.exists():
        return {
            "sources": {},
        }

    data = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(
        data,
        dict,
    ):
        raise RuntimeError(
            "Catalog sync state is not an object"
        )

    sources = data.get(
        "sources"
    )

    if not isinstance(
        sources,
        dict,
    ):
        data[
            "sources"
        ] = {}

    return data


def _write_state(
    state: dict,
) -> None:
    path = _state_path()

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
            state,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    temporary.replace(
        path
    )


def _record_started(
    source: CatalogSyncSource,
    started_at: datetime,
) -> None:
    state = _read_state()

    source_state = (
        state[
            "sources"
        ]
        .setdefault(
            source,
            {},
        )
    )

    source_state[
        "running"
    ] = True

    source_state[
        "last_started_at"
    ] = _isoformat(
        started_at
    )

    source_state[
        "last_error"
    ] = None

    state[
        "updated_at"
    ] = _isoformat(
        _utc_now()
    )

    _write_state(
        state
    )


def _record_outcome(
    outcome: CatalogSyncOutcome,
) -> None:
    state = _read_state()

    source_state = (
        state[
            "sources"
        ]
        .setdefault(
            outcome.source,
            {},
        )
    )

    source_state[
        "running"
    ] = False

    source_state[
        "last_completed_at"
    ] = outcome.completed_at

    source_state[
        "last_duration_seconds"
    ] = outcome.duration_seconds

    source_state[
        "last_records"
    ] = outcome.records

    source_state[
        "last_from_cache"
    ] = outcome.from_cache

    source_state[
        "last_details"
    ] = outcome.details

    source_state[
        "last_error"
    ] = outcome.error

    source_state[
        "last_status"
    ] = outcome.status

    if (
        outcome.status
        == "success"
    ):
        source_state[
            "last_success_at"
        ] = outcome.completed_at

        source_state[
            "consecutive_failures"
        ] = 0

        source_state[
            "next_retry_at"
        ] = None
    else:
        source_state[
            "last_failure_at"
        ] = outcome.completed_at

        consecutive_failures = int(
            source_state.get(
                "consecutive_failures",
                0,
            )
            or 0
        ) + 1

        source_state[
            "consecutive_failures"
        ] = consecutive_failures

        config = (
            CatalogSyncConfig.from_env()
        )

        next_retry_at = (
            datetime.fromisoformat(
                outcome.completed_at
            )
            + timedelta(
                seconds=(
                    config.retry_delay_seconds(
                        consecutive_failures
                    )
                )
            )
        )

        source_state[
            "next_retry_at"
        ] = _isoformat(
            next_retry_at
        )

    state[
        "updated_at"
    ] = outcome.completed_at

    _write_state(
        state
    )


@contextmanager
def catalog_sync_lock() -> Iterator[
    None
]:
    path = _lock_path()

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "a+",
        encoding="utf-8",
    ) as handle:
        try:
            fcntl.flock(
                handle.fileno(),
                (
                    fcntl.LOCK_EX
                    | fcntl.LOCK_NB
                ),
            )
        except BlockingIOError as exc:
            raise (
                CatalogSyncAlreadyRunning(
                    "A catalog sync is already running"
                )
            ) from exc

        try:
            yield
        finally:
            fcntl.flock(
                handle.fileno(),
                fcntl.LOCK_UN,
            )


def _run_satcat() -> tuple[
    int,
    bool,
    dict[str, object],
]:
    config = (
        CatalogSyncConfig.from_env()
    )

    data_root = _data_root()

    records, from_cache = (
        fetch_satcat_csv(
            cache_dir=(
                data_root
                / "raw"
                / "celestrak"
            ),
            max_age_seconds=(
                config
                .satcat_interval_seconds
            ),
        )
    )

    session_factory = (
        get_session_factory()
    )

    with session_factory() as session:
        result = (
            sync_satcat_records(
                session,
                records,
            )
        )

    return (
        result.records,
        from_cache,
        asdict(
            result
        ),
    )


def _run_celestrak(
    *,
    group: str,
    max_records: int,
) -> tuple[
    int,
    bool,
    dict[str, object],
]:
    config = (
        CatalogSyncConfig.from_env()
    )

    normalized_group = (
        normalize_group_name(
            group
        )
    )

    data_root = _data_root()

    records, from_cache = (
        fetch_gp_by_group(
            normalized_group,
            cache_dir=(
                data_root
                / "raw"
                / "celestrak"
            ),
            max_age_seconds=(
                config
                .celestrak_interval_seconds
            ),
        )
    )

    if (
        len(records)
        > max_records
    ):
        raise RuntimeError(
            "CelesTrak group "
            f"{normalized_group} returned "
            f"{len(records)} records; "
            "configured safety limit is "
            f"{max_records}"
        )

    session_factory = (
        get_session_factory()
    )

    with session_factory() as session:
        result = (
            sync_celestrak_records(
                session,
                records,
            )
        )

    details = asdict(
        result
    )

    details[
        "group"
    ] = normalized_group

    return (
        result.records,
        from_cache,
        details,
    )


def _run_space_track() -> tuple[
    int,
    bool,
    dict[str, object],
]:
    config = (
        CatalogSyncConfig.from_env()
    )

    data_root = _data_root()

    records, from_cache = (
        fetch_current_gp(
            cache_dir=(
                data_root
                / "raw"
                / "space-track"
            ),
            max_age_seconds=(
                config
                .space_track_interval_seconds
            ),
        )
    )

    session_factory = (
        get_session_factory()
    )

    with session_factory() as session:
        result = (
            sync_space_track_gp(
                session,
                records,
            )
        )

    return (
        result.records,
        from_cache,
        asdict(
            result
        ),
    )


def run_catalog_source(
    source: CatalogSyncSource,
    *,
    celestrak_group: str = "ACTIVE",
    celestrak_max_records: int = 40_000,
) -> CatalogSyncOutcome:
    started_at = _utc_now()

    _record_started(
        source,
        started_at,
    )

    records: int | None = None
    from_cache: bool | None = None
    details: dict[
        str,
        object,
    ] = {}

    error: str | None = None

    try:
        if source == "satcat":
            (
                records,
                from_cache,
                details,
            ) = _run_satcat()

        elif source == "celestrak":
            (
                records,
                from_cache,
                details,
            ) = _run_celestrak(
                group=(
                    celestrak_group
                ),
                max_records=(
                    celestrak_max_records
                ),
            )

        elif source == "space-track":
            (
                records,
                from_cache,
                details,
            ) = _run_space_track()

        else:
            raise ValueError(
                "Unsupported catalog source: "
                f"{source}"
            )

        status: Literal[
            "success",
            "error",
        ] = "success"

    except Exception as exc:
        status = "error"

        error = (
            f"{type(exc).__name__}: "
            f"{exc}"
        )

    completed_at = _utc_now()

    outcome = (
        CatalogSyncOutcome(
            source=source,
            status=status,
            started_at=(
                _isoformat(
                    started_at
                )
            ),
            completed_at=(
                _isoformat(
                    completed_at
                )
            ),
            duration_seconds=(
                completed_at
                - started_at
            ).total_seconds(),
            records=records,
            from_cache=from_cache,
            details=details,
            error=error,
        )
    )

    _record_outcome(
        outcome
    )

    return outcome


def run_catalog_sync(
    sources: tuple[
        CatalogSyncSource,
        ...,
    ] = DEFAULT_SYNC_ORDER,
    *,
    celestrak_group: str = "ACTIVE",
    celestrak_max_records: int = 40_000,
) -> tuple[
    CatalogSyncOutcome,
    ...,
]:
    outcomes: list[
        CatalogSyncOutcome
    ] = []

    with catalog_sync_lock():
        for source in sources:
            outcomes.append(
                run_catalog_source(
                    source,
                    celestrak_group=(
                        celestrak_group
                    ),
                    celestrak_max_records=(
                        celestrak_max_records
                    ),
                )
            )

    return tuple(
        outcomes
    )


def read_catalog_sync_state() -> dict:
    return _read_state()
