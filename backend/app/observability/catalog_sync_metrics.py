"""Prometheus snapshot of the persisted automated catalog-sync state."""

from typing import Callable

from prometheus_client.core import GaugeMetricFamily

from backend.app.observability.cache import CachedCollector
from backend.app.services.catalog_sync_orchestrator import (
    read_catalog_sync_state,
)
from backend.app.services.catalog_sync_status import (
    CATALOG_SYNC_SOURCES,
    completed_status,
    normalize_datetime,
    normalize_non_negative_float,
    normalize_non_negative_int,
    normalize_optional_bool,
)


def _timestamp(value: object) -> float:
    parsed = normalize_datetime(value)
    if parsed is None:
        return 0.0
    try:
        return parsed.timestamp()
    except (OSError, OverflowError, ValueError):
        return 0.0


def _non_negative_number(value: object, default: float) -> float:
    normalized = normalize_non_negative_float(value)
    return normalized if normalized is not None else default


def _consecutive_failures(value: object) -> int:
    return normalize_non_negative_int(value) or 0


def _non_negative_integer(value: object, default: float) -> int | float:
    normalized = normalize_non_negative_int(value)
    return normalized if normalized is not None else default


def _last_execution_success(source_state: dict) -> float:
    status = completed_status(source_state)
    if status == "success":
        return 1.0
    if status == "error":
        return 0.0
    return float("nan")


def _optional_boolean(value: object) -> float:
    normalized = normalize_optional_bool(value)
    return float(normalized) if normalized is not None else float("nan")


class CatalogSyncMetricsCollector(CachedCollector):
    def __init__(self, reader: Callable[[], dict] | None = None):
        self.reader = reader or read_catalog_sync_state
        super().__init__("catalog_sync", self.load)
        # Preserve the fixed source series even if the first filesystem read
        # fails. CachedCollector still reports the refresh as unavailable.
        self._snapshot = tuple(self._families({}))

    def load(self):
        return self._families(self.reader())

    def _families(self, state):
        sources = state.get("sources", {}) if isinstance(state, dict) else {}
        if not isinstance(sources, dict):
            sources = {}

        rows = {
            source: value if isinstance(value := sources.get(source), dict) else {}
            for source in CATALOG_SYNC_SOURCES
        }

        definitions = (
            (
                "running",
                "Whether this catalog source is currently marked as running",
                lambda row: float(row.get("running") is True),
            ),
            (
                "last_execution_success",
                "Latest completed execution outcome; NaN means unobserved",
                _last_execution_success,
            ),
            (
                "consecutive_failures",
                "Consecutive failed executions; zero means none or unavailable",
                lambda row: _consecutive_failures(row.get("consecutive_failures")),
            ),
            (
                "next_retry_timestamp_seconds",
                "Next scheduled retry timestamp; zero means none or unavailable",
                lambda row: _timestamp(row.get("next_retry_at")),
            ),
            (
                "last_started_timestamp_seconds",
                "Latest execution start timestamp; zero means unobserved",
                lambda row: _timestamp(row.get("last_started_at")),
            ),
            (
                "last_completed_timestamp_seconds",
                "Latest execution completion timestamp; zero means unobserved",
                lambda row: _timestamp(row.get("last_completed_at")),
            ),
            (
                "last_success_timestamp_seconds",
                "Latest successful execution timestamp; zero means unobserved",
                lambda row: _timestamp(row.get("last_success_at")),
            ),
            (
                "last_duration_seconds",
                "Latest completed execution duration; NaN means unobserved",
                lambda row: _non_negative_number(
                    row.get("last_duration_seconds"),
                    float("nan"),
                ),
            ),
            (
                "last_records",
                "Records reported by the latest execution; NaN means unobserved",
                lambda row: _non_negative_integer(
                    row.get("last_records"),
                    float("nan"),
                ),
            ),
            (
                "last_from_cache",
                "Whether the latest execution used cached provider data; NaN means unavailable",
                lambda row: _optional_boolean(row.get("last_from_cache")),
            ),
        )

        for suffix, description, extract in definitions:
            metric = GaugeMetricFamily(
                f"orbitalai_catalog_sync_{suffix}",
                description,
                labels=["source"],
            )
            for source in CATALOG_SYNC_SOURCES:
                metric.add_metric([source], extract(rows[source]))
            yield metric
