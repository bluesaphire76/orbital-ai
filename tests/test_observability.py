from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
from types import SimpleNamespace

from fastapi.testclient import TestClient
from prometheus_client import CollectorRegistry, generate_latest
from sqlalchemy import Boolean, Column, DateTime, Integer, MetaData, Table, create_engine
from sqlalchemy.orm import Session
import pytest

from backend.app.observability.cache import CachedCollector, gauge
from backend.app.observability.catalog_metrics import catalog_metrics
from backend.app.observability.conjunction_metrics import ConjunctionMetricsCollector
from backend.app.observability import operations
from backend.app.services import conjunction_runs
from test_conjunction_chunking import _execute, persistence_session, synthetic_scene


def registry_for(*collectors):
    registry = CollectorRegistry()
    for collector in collectors:
        registry.register(collector)
    return registry


def value(registry, name, labels=None):
    return registry.get_sample_value(name, labels or {})


def test_completed_screening_publishes_persisted_fields_and_execution_histogram(synthetic_scene, persistence_session):
    execution = _execute(persistence_session)
    from contextlib import nullcontext
    registry = registry_for(
        ConjunctionMetricsCollector(lambda: nullcontext(persistence_session)),
        operations.OperationsMetricsCollector(),
    )
    for suffix, expected in {
        "objects": 2, "samples": 4, "chunk_count": 3, "chunk_seconds": 60,
        "propagation_attempts": 8, "propagation_failures": 0, "refinement_failures": 0,
        "duplicate_events_suppressed": execution.result.duplicate_events_suppressed,
        "events": len(execution.result.refined_conjunctions),
        "max_chunk_unique_candidates": execution.result.max_chunk_unique_candidates,
        "duration_seconds": execution.duration_ms / 1000,
    }.items():
        assert value(registry, "orbitalai_conjunction_last_run_" + suffix) == expected
    assert value(registry, "orbitalai_conjunction_runs_total", {"source": "canonical"}) == 1
    assert value(registry, "orbitalai_conjunction_failures_total", {"source": "canonical"}) == 0
    assert value(registry, "orbitalai_conjunction_screening_duration_seconds_count", {"source": "canonical"}) == 1
    assert value(registry, "orbitalai_conjunction_screening_duration_seconds_sum", {"source": "canonical"}) == execution.duration_ms / 1000


def test_failed_screening_records_original_failure_with_bounded_source(monkeypatch):
    error = RuntimeError("sensitive provider payload")
    def fail(*args, **kwargs):
        raise error
    monkeypatch.setattr(conjunction_runs, "run_conjunction_grid", fail)
    with pytest.raises(RuntimeError) as raised:
        conjunction_runs.execute_conjunction_screening(None, start_time=datetime.now(timezone.utc),
            horizon_seconds=60, step_seconds=60, candidate_distance_km=10, source="unbounded-user-input")
    assert raised.value is error
    registry = registry_for(operations.OperationsMetricsCollector())
    assert value(registry, "orbitalai_conjunction_failures_total", {"source": "other"}) == 1
    output = generate_latest(registry).decode()
    assert "sensitive" not in output and "unbounded-user-input" not in output


@pytest.mark.parametrize("provider, result", [
    ("satcat", SimpleNamespace(records=3, created=1, updated=2)),
    ("celestrak", SimpleNamespace(records=3, objects_created=1, objects_updated=2, elements_created=1)),
    ("space-track", SimpleNamespace(records=3, matched_objects=2, unmatched_objects=1, elements_created=1)),
])
def test_ingestion_success_and_nested_entrypoint_are_counted_once(provider, result):
    @operations.observe_ingestion(provider)
    def sync(session, records):
        return result
    @operations.observe_ingestion(provider)
    def entrypoint():
        return sync(None, [{}, {}, {}])
    assert entrypoint() is result
    registry = registry_for(operations.OperationsMetricsCollector())
    labels = {"provider": provider}
    assert value(registry, "orbitalai_ingestion_runs_total", labels) == 1
    assert value(registry, "orbitalai_ingestion_last_success_timestamp_seconds", labels) > 0
    assert value(registry, "orbitalai_ingestion_last_attempt_timestamp_seconds", labels) > 0
    assert value(registry, "orbitalai_ingestion_last_execution_duration_seconds", labels) >= 0
    assert value(registry, "orbitalai_ingestion_records", labels | {"result": "received"}) == 3
    assert value(registry, "orbitalai_ingestion_records", labels | {"result": "imported"}) == 1


def test_provider_download_failure_is_observed_without_storing_secrets(monkeypatch, caplog):
    from scripts import sync_space_track_gp
    secret = "https://user:password@example.invalid/private?cookie=secret"
    def fail():
        raise RuntimeError(secret)
    monkeypatch.setattr(sync_space_track_gp, "fetch_current_gp", fail)
    with pytest.raises(RuntimeError):
        sync_space_track_gp.main()
    registry = registry_for(operations.OperationsMetricsCollector())
    assert value(registry, "orbitalai_ingestion_failures_total", {"provider": "space-track"}) == 1
    assert value(registry, "orbitalai_ingestion_last_success_timestamp_seconds", {"provider": "space-track"}) == 0
    assert secret not in generate_latest(registry).decode()
    assert secret not in operations.get_operation_store().path.read_text()
    assert secret not in caplog.text


def test_metric_write_failure_cannot_change_success_or_leak_errors(monkeypatch, caplog):
    def fail(*args, **kwargs):
        raise RuntimeError("password=private")
    monkeypatch.setattr(operations.OperationStore, "update", fail)
    result = SimpleNamespace(duration_ms=50)
    assert operations.observe_screening(lambda: result)() is result
    assert "Operational metrics update failed" in caplog.text
    assert "private" not in caplog.text


def test_cache_is_atomic_throttles_failures_and_preserves_last_good_snapshot():
    now, calls = [1000.0], []
    def load():
        calls.append(now[0])
        yield gauge("orbitalai_test_snapshot", "test", now[0])
        if now[0] == 1061:
            raise RuntimeError("secret")
    collector = CachedCollector("catalog", load, clock=lambda: now[0], wall_clock=lambda: now[0])
    registry = registry_for(collector)
    assert calls == []  # Registration performs no reads.
    assert value(registry, "orbitalai_test_snapshot") == 1000
    assert value(registry, "orbitalai_test_snapshot") == 1000
    assert len(calls) == 1
    now[0] = 1061
    assert value(registry, "orbitalai_catalog_metrics_available") == 0
    assert value(registry, "orbitalai_test_snapshot") == 1000
    assert value(registry, "orbitalai_catalog_metrics_last_refresh_timestamp_seconds") == 1000
    assert len(calls) == 2
    now[0] = 1122
    assert value(registry, "orbitalai_catalog_metrics_available") == 1
    assert value(registry, "orbitalai_test_snapshot") == 1122


def test_operation_store_serializes_independent_writers_and_fresh_readers(tmp_path):
    def writer(index):
        store = operations.OperationStore(tmp_path)
        for _ in range(10):
            store.update("conjunction", "canonical", success=True, duration=45)
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(writer, range(4)))
    # A separately constructed reader models the API reading one-shot worker state.
    registry = registry_for(operations.OperationsMetricsCollector(operations.OperationStore(tmp_path)))
    assert value(registry, "orbitalai_conjunction_runs_total", {"source": "canonical"}) == 40
    assert value(registry, "orbitalai_conjunction_screening_duration_seconds_count", {"source": "canonical"}) == 40
    assert len(operations.OperationStore(tmp_path).read()["conjunction"]) == 1


def test_all_operation_labels_are_from_fixed_allowlists():
    registry = registry_for(operations.OperationsMetricsCollector())
    allowed = {"provider": set(operations.PROVIDERS), "source": set(operations.SOURCES),
               "result": set(operations.RECORD_RESULTS), "le": {str(v) for v in operations.DURATION_BUCKETS[:-1]} | {"+Inf"}}
    for family in registry.collect():
        for sample in family.samples:
            for key, label in sample.labels.items():
                assert key in allowed and label in allowed[key]
    with pytest.raises(ValueError):
        operations.observe_ingestion("provider-from-user-input")


def test_catalog_sql_counts_match_epoch_boundaries_without_loading_omm():
    engine = create_engine("sqlite://")
    metadata = MetaData()
    objects = Table("orbital_objects", metadata, Column("id", Integer, primary_key=True),
                    Column("is_earth_orbit", Boolean), Column("has_current_elements", Boolean))
    elements = Table("orbital_elements", metadata, Column("id", Integer, primary_key=True),
                     Column("orbital_object_id", Integer), Column("epoch", DateTime))
    metadata.create_all(engine)
    now = datetime(2026, 9, 16, tzinfo=timezone.utc)
    with engine.begin() as connection:
        connection.execute(objects.insert(), [dict(id=i, is_earth_orbit=i != 8, has_current_elements=i != 7) for i in range(1, 9)])
        connection.execute(elements.insert(), [dict(id=i, orbital_object_id=obj, epoch=now - age)
            for i, (obj, age) in enumerate([
                (1, timedelta(hours=12)), (2, timedelta(hours=24)), (3, timedelta(hours=72)),
                (4, timedelta(hours=72, seconds=1)), (5, timedelta(hours=-1)), (6, timedelta(hours=1)),
                (6, timedelta(hours=200)), (2, timedelta(hours=24)), (8, timedelta(hours=1)),
            ], start=1)])
    with Session(engine) as session:
        settings = SimpleNamespace(ephemeris_warning_hours=12, ephemeris_stale_hours=24, ephemeris_max_hours=72)
        collector = CachedCollector("catalog", lambda: catalog_metrics(session, settings, now))
        registry = registry_for(collector)
        for metric, expected in {"catalog_total_objects": 8, "earth_orbit_objects": 7,
                                 "objects_with_current_elements": 7, "canonical_elements_total": 7,
                                 "screening_eligible_objects": 5}.items():
            assert value(registry, "orbitalai_" + metric) == expected
        for status, expected in {"fresh": 3, "aging": 1, "stale": 1, "expired": 1}.items():
            assert value(registry, "orbitalai_ephemeris_objects", {"status": status}) == expected
    engine.dispose()


def test_api_metrics_canonical_path_and_key_families(synthetic_scene, persistence_session):
    from contextlib import nullcontext
    from backend.app.main import create_app
    _execute(persistence_session)
    registry = registry_for(ConjunctionMetricsCollector(lambda: nullcontext(persistence_session)),
                            operations.OperationsMetricsCollector())
    # Refresh on the SQLite-owning thread; the ASGI scrape must use this cache.
    generate_latest(registry)
    with TestClient(create_app(metrics_registry=registry)) as client:
        assert client.get("/metrics", follow_redirects=False).status_code == 307
        response = client.get("/metrics/")
    assert response.status_code == 200
    for name in ("orbitalai_conjunction_last_run_events", "orbitalai_conjunction_last_run_chunk_count",
                 "orbitalai_conjunction_screening_duration_seconds_bucket", "orbitalai_ingestion_records"):
        assert name in response.text


def test_dashboard_is_provisioned_with_bounded_operational_queries():
    root = Path(__file__).resolve().parents[1]
    dashboard = json.loads((root / "observability/grafana/provisioning/dashboards/json/orbital-operations-overview.json").read_text())
    assert dashboard["title"] == "OrbitalAI - Orbital Operations Overview"
    assert dashboard["uid"] == "orbitalai-operations"
    assert dashboard["refresh"] == "30s"
    data_panels = [
        panel
        for panel in dashboard["panels"]
        if panel["type"] != "row"
    ]
    assert all(
        panel["datasource"]["uid"] == "orbitalai-prometheus"
        for panel in data_panels
    )
    panel_ids = [panel["id"] for panel in dashboard["panels"]]
    assert len(panel_ids) == len(set(panel_ids))
    assert panel_ids == [
        24, 1, 2, 3, 4, 5,
        25, 7, 8,
        26, 9, 10, 11, 6, 12, 13, 14,
        27, 15, 16,
        28, 18, 19, 20, 21, 22, 23,
        29, 17,
        30, 31, 32, 33, 34, 35, 36,
    ]

    section_rows = [
        panel
        for panel in dashboard["panels"]
        if panel["type"] == "row"
    ]
    assert [panel["title"] for panel in section_rows] == [
        "System Overview",
        "Catalog & Ephemeris",
        "Conjunction Screening",
        "Ingestion",
        "Automated Catalog Synchronization",
        "Alerting",
        "Local AI",
    ]
    assert all(
        panel["gridPos"]["x"] == 0
        and panel["gridPos"]["w"] == 24
        and panel["gridPos"]["h"] == 1
        and panel["collapsed"] is False
        for panel in section_rows
    )

    expected_grid = {
        1: (0, 1, 8, 4), 2: (8, 1, 4, 4), 3: (12, 1, 4, 4),
        4: (16, 1, 4, 4), 5: (20, 1, 4, 4),
        7: (0, 6, 12, 7), 8: (12, 6, 12, 7),
        9: (0, 14, 8, 6), 10: (8, 14, 4, 6),
        11: (12, 14, 8, 6), 6: (20, 14, 4, 6),
        12: (0, 20, 8, 7), 13: (8, 20, 8, 7), 14: (16, 20, 8, 7),
        15: (0, 28, 8, 7), 16: (8, 28, 16, 7),
        18: (0, 36, 6, 5), 19: (6, 36, 6, 5),
        20: (12, 36, 6, 5), 21: (18, 36, 6, 5),
        22: (0, 41, 12, 5), 23: (12, 41, 12, 5),
        17: (0, 47, 24, 4),
        31: (0, 52, 6, 6), 32: (6, 52, 18, 6),
        33: (0, 58, 12, 7), 34: (12, 58, 12, 7),
        35: (0, 65, 12, 7), 36: (12, 65, 12, 7),
    }
    assert {
        panel["id"]: (
            panel["gridPos"]["x"], panel["gridPos"]["y"],
            panel["gridPos"]["w"], panel["gridPos"]["h"],
        )
        for panel in data_panels
    } == expected_grid

    stat_panels = [panel for panel in data_panels if panel["type"] == "stat"]
    assert all(
        panel["options"]["justifyMode"] == "center"
        and panel["options"]["orientation"] == "horizontal"
        and panel["options"]["wideLayout"] is True
        and panel["options"]["text"] == {
            "titleSize": 12,
            "valueSize": 20,
        }
        for panel in stat_panels
    )

    bar_gauges = [
        panel
        for panel in data_panels
        if panel["type"] == "bargauge"
    ]
    assert all(
        panel["options"]["namePlacement"] == "left"
        and panel["options"]["sizing"] == "manual"
        and panel["options"]["minVizHeight"] == 24
        and panel["options"]["maxVizHeight"] == 32
        and panel["options"]["text"] == {
            "titleSize": 12,
            "valueSize": 18,
        }
        for panel in bar_gauges
    )

    original_panels = {
        1: "Platform and worker status",
        2: "Eligible objects",
        3: "Last screening duration",
        4: "Conjunction events",
        5: "Propagation failures",
        6: "Chunk count",
        7: "Catalog coverage",
        8: "Earth-orbit ephemeris age",
        9: "Conjunction pipeline reduction",
        10: "Duplicate events suppressed",
        11: "Largest chunk workload",
        12: "Pipeline ratios",
        13: "Screening performance",
        14: "Execution counts in selected range",
        15: "Ingestion — time since successful sync",
        16: "Ingestion — latest records and execution",
        17: "Firing Alerts",
    }
    panels_by_id = {
        panel["id"]: panel
        for panel in dashboard["panels"]
    }
    assert {
        panel_id: panels_by_id[panel_id]["title"]
        for panel_id in original_panels
    } == original_panels

    catalog_panels = {
        panel["title"]: panel
        for panel in dashboard["panels"]
        if 18 <= panel["id"] <= 23
    }
    assert set(catalog_panels) == {
        "Catalog Synchronization",
        "Last Successful Sync Age",
        "Last Execution Status",
        "Consecutive Failures",
        "Last Sync Records",
        "Last Sync Duration",
    }
    expressions = {
        target["expr"]
        for panel in catalog_panels.values()
        for target in panel["targets"]
    }
    expected_metrics = {
        "orbitalai_catalog_sync_metrics_available",
        "orbitalai_catalog_sync_last_success_timestamp_seconds",
        "orbitalai_catalog_sync_last_execution_success",
        "orbitalai_catalog_sync_consecutive_failures",
        "orbitalai_catalog_sync_last_records",
        "orbitalai_catalog_sync_last_duration_seconds",
    }
    referenced_metrics = set(re.findall(
        r"orbitalai_catalog_sync_[a-z_]+",
        "\n".join(expressions),
    ))
    assert referenced_metrics == expected_metrics
    assert all(
        forbidden not in expression
        for expression in expressions
        for forbidden in ("pod=", "container=", "instance=", "job=")
    )
    assert all(
        target["datasource"]["uid"] == "orbitalai-prometheus"
        for panel in catalog_panels.values()
        for target in panel["targets"]
    )
    source_panels = set(catalog_panels) - {"Catalog Synchronization"}
    assert all(
        target["legendFormat"] == "{{source}}"
        for title in source_panels
        for target in catalog_panels[title]["targets"]
    )
    assert (root / "observability/grafana/provisioning/dashboards/operations.yml").exists()

    ai_panels = {
        panel["title"]: panel
        for panel in dashboard["panels"]
        if 31 <= panel["id"] <= 36
    }
    assert set(ai_panels) == {
        "AI Provider Availability",
        "AI Requests by Task and Status",
        "AI Request Duration",
        "AI Prompt and Completion Tokens",
        "AI Active Requests and Queue",
        "AI Errors/Rejections",
    }
    ai_expressions = {
        target["expr"]
        for panel in ai_panels.values()
        for target in panel["targets"]
    }
    expected_ai_metrics = {
        "orbitalai_ai_runtime_ready",
        "orbitalai_ai_requests_total",
        "orbitalai_ai_request_duration_seconds_bucket",
        "orbitalai_ai_prompt_tokens_total",
        "orbitalai_ai_completion_tokens_total",
        "orbitalai_ai_active_requests",
        "orbitalai_ai_queue_depth",
        "orbitalai_ai_concurrency_capacity",
        "orbitalai_ai_queue_capacity",
    }
    assert set(re.findall(
        r"orbitalai_ai_[a-z_]+",
        "\n".join(ai_expressions),
    )) == expected_ai_metrics
    assert any("conjunction_analyst_brief" in expression for expression in ai_expressions)
    assert all(
        forbidden not in expression
        for expression in ai_expressions
        for forbidden in (
            "event_id", "run_id", "object_id", "norad", "model_path",
            "grounding_sha256", "request_id", "instance=", "pod=", "container=",
        )
    )
    assert all(
        panel["datasource"]["uid"] == "orbitalai-prometheus"
        and all(
            target["datasource"]["uid"] == "orbitalai-prometheus"
            for target in panel["targets"]
        )
        for panel in ai_panels.values()
    )
