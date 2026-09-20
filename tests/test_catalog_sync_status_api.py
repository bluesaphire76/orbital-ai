from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json

from fastapi.testclient import TestClient
from prometheus_client import CollectorRegistry
import pytest

from backend.app.api.routes import catalog
from backend.app.main import create_app
from backend.app.services.catalog_sync_status import (
    evaluate_catalog_sync_freshness,
    normalize_catalog_sync_state,
)


SOURCE_KEYS = {
    "running",
    "status",
    "last_started_at",
    "last_completed_at",
    "last_success_at",
    "last_duration_seconds",
    "last_records",
    "last_from_cache",
    "consecutive_failures",
    "next_retry_at",
    "freshness",
    "last_success_age_seconds",
    "freshness_warning_seconds",
    "freshness_stale_seconds",
}
SOURCES = {
    "satcat",
    "celestrak",
    "space-track",
}

NOW = datetime(2026, 9, 20, 8, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def fixed_freshness_time(monkeypatch):
    monkeypatch.setattr(catalog, "_utc_now", lambda: NOW)


@pytest.fixture
def client():
    registry = CollectorRegistry()
    with TestClient(create_app(metrics_registry=registry)) as test_client:
        yield test_client


def _use_state(monkeypatch, state):
    monkeypatch.setattr(
        catalog,
        "read_catalog_sync_state",
        lambda: state,
    )


def test_complete_response_has_stable_contract_and_utc_timestamps(client, monkeypatch):
    state = {
        "updated_at": "2026-09-20T09:51:22.379959+02:00",
        "sources": {
            "satcat": {
                "running": False,
                "last_status": "success",
                "last_started_at": "2026-09-20T07:50:00Z",
                "last_completed_at": "2026-09-20T07:51:22.379959+00:00",
                "last_success_at": "2026-09-20T07:51:22.379959Z",
                "last_duration_seconds": 82.379959,
                "last_records": 70_711,
                "last_from_cache": False,
                "consecutive_failures": 0,
                "next_retry_at": None,
                "last_error": "must not be public",
                "last_details": {"url": "https://private.invalid"},
            },
            "celestrak": {
                "running": False,
                "last_status": "error",
                "last_completed_at": "2026-09-20T07:49:00Z",
                "consecutive_failures": 2,
                "next_retry_at": "2026-09-20T07:51:00Z",
            },
            "space-track": {},
            "unknown": {"running": True},
        },
    }
    original = deepcopy(state)
    _use_state(monkeypatch, state)

    response = client.get("/catalog/sync-status", follow_redirects=False)

    assert response.status_code == 200
    assert response.history == []
    payload = response.json()
    assert set(payload) == {"updated_at", "overall_freshness", "sources"}
    assert set(payload["sources"]) == SOURCES
    assert all(set(row) == SOURCE_KEYS for row in payload["sources"].values())
    assert payload["updated_at"] == "2026-09-20T07:51:22.379959Z"
    assert payload["overall_freshness"] == "unknown"
    assert payload["sources"]["satcat"] == {
        "running": False,
        "status": "success",
        "last_started_at": "2026-09-20T07:50:00Z",
        "last_completed_at": "2026-09-20T07:51:22.379959Z",
        "last_success_at": "2026-09-20T07:51:22.379959Z",
        "last_duration_seconds": 82.379959,
        "last_records": 70_711,
        "last_from_cache": False,
        "consecutive_failures": 0,
        "next_retry_at": None,
        "freshness": "fresh",
        "last_success_age_seconds": 517.620041,
        "freshness_warning_seconds": 64_800,
        "freshness_stale_seconds": 86_400,
    }
    assert payload["sources"]["celestrak"]["status"] == "error"
    assert payload["sources"]["space-track"]["status"] == "never_run"
    serialized = json.dumps(payload)
    assert "last_error" not in serialized
    assert "last_details" not in serialized
    assert "private.invalid" not in serialized
    assert state == original


@pytest.mark.parametrize(
    "source_state, expected",
    (
        ({"running": True, "last_status": "error"}, "running"),
        ({"running": False, "last_status": "success"}, "success"),
        ({"running": False, "last_status": "error"}, "error"),
        ({}, "never_run"),
    ),
)
def test_status_precedence(client, monkeypatch, source_state, expected):
    _use_state(monkeypatch, {"sources": {"satcat": source_state}})

    payload = client.get("/catalog/sync-status").json()

    assert payload["sources"]["satcat"]["status"] == expected


def test_legacy_outcome_is_inferred_without_exposing_error(client, monkeypatch):
    _use_state(
        monkeypatch,
        {
            "sources": {
                "satcat": {
                    "last_completed_at": "2026-09-20T07:00:00Z",
                    "last_error": None,
                },
                "celestrak": {
                    "last_completed_at": "2026-09-20T07:00:00Z",
                    "last_error": "credential-bearing provider failure",
                },
            }
        },
    )

    response = client.get("/catalog/sync-status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["sources"]["satcat"]["status"] == "success"
    assert payload["sources"]["celestrak"]["status"] == "error"
    assert "credential-bearing" not in response.text


def test_absent_state_file_returns_all_sources_as_never_run(
    client,
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("ORBITAL_SYNC_STATE_DIR", str(tmp_path))

    response = client.get("/catalog/sync-status")

    assert response.status_code == 200
    assert response.json()["updated_at"] is None
    assert response.json()["overall_freshness"] == "unknown"
    assert set(response.json()["sources"]) == SOURCES
    assert {
        row["status"] for row in response.json()["sources"].values()
    } == {"never_run"}


def test_partial_and_invalid_fields_degrade_independently(client, monkeypatch):
    _use_state(
        monkeypatch,
        {
            "updated_at": "invalid",
            "sources": {
                "satcat": {
                    "running": "yes",
                    "last_status": "unexpected",
                    "last_started_at": "2026-09-20T07:00:00",
                    "last_completed_at": 123,
                    "last_success_at": "bad",
                    "last_duration_seconds": -1,
                    "last_records": 1.5,
                    "last_from_cache": "false",
                    "consecutive_failures": -2,
                    "next_retry_at": "bad",
                },
                "celestrak": None,
            },
        },
    )

    response = client.get("/catalog/sync-status")

    assert response.status_code == 200
    payload = response.json()
    row = payload["sources"]["satcat"]
    assert payload["updated_at"] is None
    assert row["running"] is False
    assert row["status"] == "never_run"
    assert row["last_started_at"] is None
    assert row["last_completed_at"] is None
    assert row["last_success_at"] is None
    assert row["last_duration_seconds"] is None
    assert row["last_records"] is None
    assert row["last_from_cache"] is None
    assert row["consecutive_failures"] == 0
    assert row["next_retry_at"] is None
    assert row["freshness"] == "unknown"
    assert row["last_success_age_seconds"] is None
    assert row["freshness_warning_seconds"] == 64_800
    assert row["freshness_stale_seconds"] == 86_400
    assert payload["sources"]["celestrak"]["status"] == "never_run"


def test_corrupt_state_returns_generic_503(client, monkeypatch, tmp_path):
    monkeypatch.setenv("ORBITAL_SYNC_STATE_DIR", str(tmp_path))
    path = tmp_path / "catalog-sync-status.json"
    path.write_text('{"password":"secret",', encoding="utf-8")
    before = path.read_bytes()

    response = client.get("/catalog/sync-status")

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Catalog sync status is temporarily unavailable"
    }
    assert "secret" not in response.text
    assert str(path) not in response.text
    assert path.read_bytes() == before


def test_reading_valid_file_does_not_modify_it(client, monkeypatch, tmp_path):
    monkeypatch.setenv("ORBITAL_SYNC_STATE_DIR", str(tmp_path))
    path = tmp_path / "catalog-sync-status.json"
    path.write_text(
        json.dumps(
            {
                "updated_at": "2026-09-20T07:00:00Z",
                "sources": {
                    "space-track": {
                        "running": False,
                        "last_status": "success",
                        "last_error": None,
                        "last_details": {"private": "value"},
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    before = path.read_bytes()
    modified_at = path.stat().st_mtime_ns

    response = client.get("/catalog/sync-status")

    assert response.status_code == 200
    assert response.json()["sources"]["space-track"]["status"] == "success"
    assert path.read_bytes() == before
    assert path.stat().st_mtime_ns == modified_at


def test_openapi_documents_read_only_endpoint_and_503(client, monkeypatch):
    _use_state(monkeypatch, {"sources": {}})

    schema = client.get("/openapi.json").json()
    operation = schema["paths"]["/catalog/sync-status"]

    assert set(operation) == {"get"}
    assert operation["get"]["responses"].keys() >= {"200", "503"}
    assert operation["get"]["summary"] == "Get catalog synchronization status"


def _freshness_payload(
    source_rows,
    *,
    intervals=None,
):
    normalized = normalize_catalog_sync_state({
        "sources": source_rows,
    })
    return evaluate_catalog_sync_freshness(
        normalized,
        intervals=(
            intervals
            or {
                "satcat": 43_200,
                "celestrak": 7_200,
                "space-track": 3_600,
            }
        ),
        now=NOW,
    )


@pytest.mark.parametrize(
    "age_seconds, expected_freshness, expected_age",
    (
        (60, "fresh", 60.0),
        (5_400, "fresh", 5_400.0),
        (5_401, "warning", 5_401.0),
        (7_200, "warning", 7_200.0),
        (7_201, "stale", 7_201.0),
        (-60, "fresh", 0.0),
        (None, "unknown", None),
    ),
)
def test_freshness_boundaries_and_future_clamp(
    age_seconds,
    expected_freshness,
    expected_age,
):
    last_success = (
        None
        if age_seconds is None
        else (NOW - timedelta(seconds=age_seconds)).isoformat()
    )
    payload = _freshness_payload({
        "space-track": {
            "last_success_at": last_success,
        }
    })
    row = payload["sources"]["space-track"]

    assert row["freshness"] == expected_freshness
    assert row["last_success_age_seconds"] == expected_age
    assert row["freshness_warning_seconds"] == 5_400
    assert row["freshness_stale_seconds"] == 7_200


def test_running_source_keeps_stale_last_success():
    payload = _freshness_payload({
        "space-track": {
            "running": True,
            "last_success_at": (NOW - timedelta(hours=3)).isoformat(),
        }
    })
    row = payload["sources"]["space-track"]

    assert row["status"] == "running"
    assert row["freshness"] == "stale"


def test_failed_attempt_keeps_freshness_from_previous_success():
    payload = _freshness_payload({
        "space-track": {
            "last_status": "error",
            "last_completed_at": (NOW - timedelta(minutes=1)).isoformat(),
            "last_success_at": (NOW - timedelta(minutes=30)).isoformat(),
        }
    })
    row = payload["sources"]["space-track"]

    assert row["status"] == "error"
    assert row["freshness"] == "fresh"
    assert row["last_success_age_seconds"] == 1_800


@pytest.mark.parametrize(
    "ages, expected",
    (
        ({"satcat": 60, "celestrak": 60, "space-track": 7_201}, "stale"),
        ({"satcat": 60, "celestrak": 10_801, "space-track": 60}, "warning"),
        ({"satcat": 60, "celestrak": 60, "space-track": 60}, "fresh"),
        ({"satcat": 60, "celestrak": 60, "space-track": None}, "unknown"),
    ),
)
def test_overall_freshness_precedence(ages, expected):
    rows = {
        source: {
            "last_success_at": (
                None
                if age is None
                else (NOW - timedelta(seconds=age)).isoformat()
            )
        }
        for source, age in ages.items()
    }

    assert _freshness_payload(rows)["overall_freshness"] == expected


def test_configured_intervals_control_thresholds():
    payload = _freshness_payload(
        {
            source: {
                "last_success_at": (NOW - timedelta(seconds=151)).isoformat(),
            }
            for source in SOURCES
        },
        intervals={
            "satcat": 100,
            "celestrak": 200,
            "space-track": 300,
        },
    )

    assert payload["sources"]["satcat"]["freshness"] == "warning"
    assert payload["sources"]["satcat"]["freshness_warning_seconds"] == 150
    assert payload["sources"]["celestrak"]["freshness"] == "fresh"
    assert payload["sources"]["space-track"]["freshness_stale_seconds"] == 600
