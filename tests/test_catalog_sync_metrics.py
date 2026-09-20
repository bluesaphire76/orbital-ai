from copy import deepcopy
from datetime import datetime, timezone
from math import isnan

from fastapi.testclient import TestClient
from prometheus_client import CollectorRegistry, Gauge, generate_latest

from backend.app.observability.catalog_sync_metrics import (
    CATALOG_SYNC_SOURCES,
    CatalogSyncMetricsCollector,
)


def _registry(state):
    registry = CollectorRegistry()
    registry.register(CatalogSyncMetricsCollector(lambda: state))
    return registry


def _value(registry, suffix, source):
    return registry.get_sample_value(
        f"orbitalai_catalog_sync_{suffix}",
        {"source": source},
    )


def test_complete_state_exports_fixed_sources_and_normalized_values():
    state = {
        "sources": {
            "satcat": {
                "running": True,
                "last_status": "success",
                "consecutive_failures": 0,
                "next_retry_at": None,
                "last_started_at": "2026-09-20T10:00:00Z",
                "last_completed_at": "2026-09-20T10:00:05+00:00",
                "last_success_at": "2026-09-20T12:00:05+02:00",
                "last_duration_seconds": 5.25,
                "last_records": 70_000,
                "last_from_cache": True,
            },
            "celestrak": {
                "running": False,
                "last_status": "error",
                "consecutive_failures": 2,
                "next_retry_at": "2026-09-20T10:30:00+00:00",
                "last_started_at": "2026-09-20T10:20:00+00:00",
                "last_completed_at": "2026-09-20T10:20:03+00:00",
                "last_duration_seconds": 3,
                "last_records": 0,
                "last_from_cache": False,
            },
            "space-track": {},
            "arbitrary-provider": {
                "running": True,
                "last_error": "must not become a label",
            },
        },
    }
    original = deepcopy(state)
    registry = _registry(state)

    assert _value(registry, "running", "satcat") == 1
    assert _value(registry, "running", "celestrak") == 0
    assert _value(registry, "last_execution_success", "satcat") == 1
    assert _value(registry, "last_execution_success", "celestrak") == 0
    assert _value(registry, "consecutive_failures", "celestrak") == 2
    assert _value(registry, "last_duration_seconds", "satcat") == 5.25
    assert _value(registry, "last_records", "satcat") == 70_000
    assert _value(registry, "last_from_cache", "satcat") == 1
    assert _value(registry, "last_from_cache", "celestrak") == 0
    assert isnan(_value(registry, "last_execution_success", "space-track"))
    assert isnan(_value(registry, "last_duration_seconds", "space-track"))
    assert isnan(_value(registry, "last_records", "space-track"))
    assert isnan(_value(registry, "last_from_cache", "space-track"))

    expected_start = datetime(2026, 9, 20, 10, tzinfo=timezone.utc).timestamp()
    expected_complete = datetime(2026, 9, 20, 10, 0, 5, tzinfo=timezone.utc).timestamp()
    assert _value(registry, "last_started_timestamp_seconds", "satcat") == expected_start
    assert _value(registry, "last_completed_timestamp_seconds", "satcat") == expected_complete
    assert _value(registry, "last_success_timestamp_seconds", "satcat") == expected_complete
    assert _value(registry, "next_retry_timestamp_seconds", "celestrak") == datetime(
        2026, 9, 20, 10, 30, tzinfo=timezone.utc
    ).timestamp()

    running = next(
        family for family in registry.collect()
        if family.name == "orbitalai_catalog_sync_running"
    )
    assert {sample.labels["source"] for sample in running.samples} == set(CATALOG_SYNC_SOURCES)
    assert all(set(sample.labels) == {"source"} for sample in running.samples)
    assert "arbitrary-provider" not in generate_latest(registry).decode()
    assert state == original


def test_empty_missing_and_partial_state_emit_defaults_for_every_source():
    for state in ({}, {"sources": {}}, {"sources": None}, {"sources": {"satcat": None}}):
        registry = _registry(state)
        for source in CATALOG_SYNC_SOURCES:
            assert _value(registry, "running", source) == 0
            assert _value(registry, "consecutive_failures", source) == 0
            assert _value(registry, "next_retry_timestamp_seconds", source) == 0
            assert _value(registry, "last_started_timestamp_seconds", source) == 0
            assert _value(registry, "last_completed_timestamp_seconds", source) == 0
            assert _value(registry, "last_success_timestamp_seconds", source) == 0
            assert isnan(_value(registry, "last_execution_success", source))
            assert isnan(_value(registry, "last_duration_seconds", source))
            assert isnan(_value(registry, "last_records", source))
            assert isnan(_value(registry, "last_from_cache", source))


def test_legacy_state_infers_outcome_without_rewriting_state():
    state = {
        "sources": {
            "satcat": {
                "last_completed_at": "2026-09-20T10:00:00+00:00",
                "last_error": None,
            },
            "celestrak": {
                "last_completed_at": "2026-09-20T10:00:00+00:00",
                "last_error": "provider failed",
            },
        },
    }
    original = deepcopy(state)
    registry = _registry(state)

    assert _value(registry, "last_execution_success", "satcat") == 1
    assert _value(registry, "last_execution_success", "celestrak") == 0
    assert isnan(_value(registry, "last_execution_success", "space-track"))
    assert state == original


def test_invalid_fields_fall_back_independently_without_breaking_scrape():
    state = {
        "sources": {
            "satcat": {
                "running": "yes",
                "last_status": "unexpected",
                "consecutive_failures": -1,
                "next_retry_at": "not-a-time",
                "last_started_at": "2026-09-20T10:00:00",
                "last_completed_at": 123,
                "last_success_at": "invalid",
                "last_duration_seconds": -0.5,
                "last_records": float("inf"),
                "last_from_cache": "false",
            },
            "celestrak": {
                "consecutive_failures": 1.5,
                "last_duration_seconds": "4",
                "last_records": True,
            },
            "space-track": {
                "consecutive_failures": 10**1000,
                "next_retry_at": "0001-01-01T00:00:00+14:00",
                "last_duration_seconds": 10**1000,
                "last_records": 10**1000,
            },
        },
    }
    registry = _registry(state)

    assert _value(registry, "running", "satcat") == 0
    assert isnan(_value(registry, "last_execution_success", "satcat"))
    assert _value(registry, "consecutive_failures", "satcat") == 0
    assert _value(registry, "consecutive_failures", "celestrak") == 0
    assert _value(registry, "consecutive_failures", "space-track") == 0
    for suffix in (
        "next_retry_timestamp_seconds",
        "last_started_timestamp_seconds",
        "last_completed_timestamp_seconds",
        "last_success_timestamp_seconds",
    ):
        assert _value(registry, suffix, "satcat") == 0
    assert isnan(_value(registry, "last_duration_seconds", "satcat"))
    assert isnan(_value(registry, "last_duration_seconds", "celestrak"))
    assert isnan(_value(registry, "last_duration_seconds", "space-track"))
    assert isnan(_value(registry, "last_records", "satcat"))
    assert isnan(_value(registry, "last_records", "celestrak"))
    assert isnan(_value(registry, "last_records", "space-track"))
    assert isnan(_value(registry, "last_from_cache", "satcat"))
    assert b"orbitalai_catalog_sync_running" in generate_latest(registry)


def test_cached_collector_standard_metrics_and_failed_refresh_are_safe():
    calls = [0]

    def reader():
        calls[0] += 1
        if calls[0] == 1:
            return {"sources": {}}
        raise RuntimeError("secret state read failure")

    collector = CatalogSyncMetricsCollector(reader)
    collector.refresh_seconds = 0
    registry = CollectorRegistry()
    registry.register(collector)

    assert registry.get_sample_value("orbitalai_catalog_sync_metrics_available") == 1
    last_refresh = registry.get_sample_value(
        "orbitalai_catalog_sync_metrics_last_refresh_timestamp_seconds"
    )
    assert last_refresh > 0
    assert registry.get_sample_value("orbitalai_catalog_sync_metrics_available") == 0
    assert _value(registry, "running", "satcat") == 0
    assert registry.get_sample_value(
        "orbitalai_catalog_sync_metrics_last_refresh_timestamp_seconds"
    ) == last_refresh
    assert "secret" not in generate_latest(registry).decode()


def test_failed_initial_read_still_exports_fixed_default_series():
    def fail():
        raise RuntimeError("unreadable state")

    registry = CollectorRegistry()
    registry.register(CatalogSyncMetricsCollector(fail))

    assert registry.get_sample_value("orbitalai_catalog_sync_metrics_available") == 0
    for source in CATALOG_SYNC_SOURCES:
        assert _value(registry, "running", source) == 0
        assert isnan(_value(registry, "last_execution_success", source))


def test_initialize_metrics_registers_collector_once(monkeypatch):
    from backend.app.core import metrics

    class RecordingRegistry:
        def __init__(self):
            self.collectors = []

        def register(self, collector):
            self.collectors.append(collector)

    registry = RecordingRegistry()
    monkeypatch.setattr(metrics, "REGISTRY", registry)
    monkeypatch.setattr(metrics, "_initialized", False)

    metrics.initialize_metrics()
    metrics.initialize_metrics()

    assert sum(isinstance(item, CatalogSyncMetricsCollector) for item in registry.collectors) == 1


def test_metrics_endpoint_keeps_existing_families_and_catalog_sync_series():
    from backend.app.main import create_app

    registry = _registry({"sources": {}})
    Gauge("orbitalai_existing_test_metric", "Existing family", registry=registry).set(1)

    with TestClient(create_app(metrics_registry=registry)) as client:
        assert client.get("/metrics", follow_redirects=False).status_code == 307
        response = client.get("/metrics/")

    assert response.status_code == 200
    assert "orbitalai_existing_test_metric 1.0" in response.text
    assert "orbitalai_catalog_sync_running{source=\"satcat\"} 0.0" in response.text
    assert "orbitalai_catalog_sync_running{source=\"celestrak\"} 0.0" in response.text
    assert "orbitalai_catalog_sync_running{source=\"space-track\"} 0.0" in response.text
