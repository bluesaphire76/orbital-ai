"""Pure normalization for persisted catalog-sync status consumers."""

from datetime import datetime, timezone
from math import isfinite
from typing import Literal, Mapping

from backend.app.services.catalog_sync_config import CatalogSyncConfig


CATALOG_SYNC_SOURCES = (
    "satcat",
    "celestrak",
    "space-track",
)

CatalogSyncPublicStatus = Literal[
    "never_run",
    "running",
    "success",
    "error",
]

CatalogSyncFreshness = Literal[
    "fresh",
    "warning",
    "stale",
    "unknown",
]


def normalize_datetime(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None

    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(timezone.utc)
    except (OSError, OverflowError, ValueError):
        return None


def normalize_non_negative_float(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None

    try:
        numeric = float(value)
    except (OverflowError, ValueError):
        return None
    if not isfinite(numeric) or numeric < 0:
        return None
    return numeric


def normalize_non_negative_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    try:
        if not isfinite(float(value)):
            return None
    except (OverflowError, ValueError):
        return None
    return value


def normalize_optional_bool(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


def completed_status(source_state: dict) -> Literal["success", "error"] | None:
    status = source_state.get("last_status")
    if status == "success":
        return "success"
    if status == "error":
        return "error"

    if (
        "last_status" not in source_state
        and source_state.get("last_completed_at") is not None
    ):
        return "error" if source_state.get("last_error") else "success"
    return None


def public_status(source_state: dict) -> CatalogSyncPublicStatus:
    if source_state.get("running") is True:
        return "running"
    return completed_status(source_state) or "never_run"


def normalize_catalog_sync_state(state: object) -> dict[str, object]:
    raw_sources = state.get("sources", {}) if isinstance(state, dict) else {}
    if not isinstance(raw_sources, dict):
        raw_sources = {}

    sources: dict[str, dict[str, object]] = {}
    for source in CATALOG_SYNC_SOURCES:
        candidate = raw_sources.get(source)
        row = candidate if isinstance(candidate, dict) else {}
        sources[source] = {
            "running": row.get("running") is True,
            "status": public_status(row),
            "last_started_at": normalize_datetime(row.get("last_started_at")),
            "last_completed_at": normalize_datetime(row.get("last_completed_at")),
            "last_success_at": normalize_datetime(row.get("last_success_at")),
            "last_duration_seconds": normalize_non_negative_float(
                row.get("last_duration_seconds")
            ),
            "last_records": normalize_non_negative_int(row.get("last_records")),
            "last_from_cache": normalize_optional_bool(row.get("last_from_cache")),
            "consecutive_failures": (
                normalize_non_negative_int(row.get("consecutive_failures")) or 0
            ),
            "next_retry_at": normalize_datetime(row.get("next_retry_at")),
        }

    return {
        "updated_at": normalize_datetime(
            state.get("updated_at") if isinstance(state, dict) else None
        ),
        "sources": sources,
    }


def catalog_sync_intervals(config: CatalogSyncConfig) -> dict[str, int]:
    return {
        "satcat": config.satcat_interval_seconds,
        "celestrak": config.celestrak_interval_seconds,
        "space-track": config.space_track_interval_seconds,
    }


def _thresholds(interval_seconds: object) -> tuple[int, int]:
    if (
        isinstance(interval_seconds, bool)
        or not isinstance(interval_seconds, int)
        or interval_seconds <= 0
    ):
        raise ValueError("Catalog sync intervals must be positive integers")

    warning_seconds = (interval_seconds * 3 + 1) // 2
    stale_seconds = interval_seconds * 2
    return warning_seconds, stale_seconds


def _source_freshness(
    last_success_at: object,
    *,
    warning_seconds: int,
    stale_seconds: int,
    now: datetime,
) -> tuple[CatalogSyncFreshness, float | None]:
    if not isinstance(last_success_at, datetime):
        return "unknown", None

    if last_success_at.tzinfo is None:
        return "unknown", None

    age_seconds = max(
        0.0,
        (now - last_success_at.astimezone(timezone.utc)).total_seconds(),
    )
    if age_seconds <= warning_seconds:
        return "fresh", age_seconds
    if age_seconds <= stale_seconds:
        return "warning", age_seconds
    return "stale", age_seconds


def evaluate_catalog_sync_freshness(
    normalized_state: Mapping[str, object],
    *,
    intervals: Mapping[str, int],
    now: datetime,
) -> dict[str, object]:
    if now.tzinfo is None:
        raise ValueError("Catalog sync freshness time must be timezone-aware")
    now_utc = now.astimezone(timezone.utc)

    raw_sources = normalized_state.get("sources", {})
    source_rows = raw_sources if isinstance(raw_sources, dict) else {}
    evaluated_sources: dict[str, dict[str, object]] = {}

    for source in CATALOG_SYNC_SOURCES:
        warning_seconds, stale_seconds = _thresholds(intervals[source])
        candidate = source_rows.get(source)
        row = dict(candidate) if isinstance(candidate, dict) else {}
        freshness, age_seconds = _source_freshness(
            row.get("last_success_at"),
            warning_seconds=warning_seconds,
            stale_seconds=stale_seconds,
            now=now_utc,
        )
        row.update({
            "freshness": freshness,
            "last_success_age_seconds": age_seconds,
            "freshness_warning_seconds": warning_seconds,
            "freshness_stale_seconds": stale_seconds,
        })
        evaluated_sources[source] = row

    freshness_values = {
        row["freshness"]
        for row in evaluated_sources.values()
    }
    if "stale" in freshness_values:
        overall: CatalogSyncFreshness = "stale"
    elif "warning" in freshness_values:
        overall = "warning"
    elif freshness_values == {"fresh"}:
        overall = "fresh"
    else:
        overall = "unknown"

    return {
        "updated_at": normalized_state.get("updated_at"),
        "overall_freshness": overall,
        "sources": evaluated_sources,
    }
