from datetime import (
    datetime,
    timedelta,
    timezone,
)
from dataclasses import dataclass
from contextlib import nullcontext
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from backend.app.services import (
    catalog_sync_orchestrator,
)
from backend.app.services.catalog_sync_config import (
    CatalogSyncConfig,
)
from backend.app.services.catalog_sync_orchestrator import (
    CatalogSyncOutcome,
)
from workers.ingestion.run_catalog_sync_scheduler import (
    due_sources,
    seconds_until_next_run,
)


def _config() -> CatalogSyncConfig:
    return CatalogSyncConfig(
        satcat_interval_seconds=43_200,
        celestrak_interval_seconds=7_200,
        space_track_interval_seconds=3_600,
        poll_seconds=60,
        retry_initial_seconds=60,
        retry_max_seconds=1_800,
        retry_multiplier=2,
        celestrak_group="ACTIVE",
        celestrak_max_records=40_000,
    )


def _completed_at(
    value: datetime,
) -> dict:
    return {
        "last_completed_at": value.isoformat(),
    }


def test_config_defaults_match_target_cadence():
    config = CatalogSyncConfig.from_env({})

    assert config.satcat_interval_seconds == 43_200
    assert config.celestrak_interval_seconds == 7_200
    assert config.space_track_interval_seconds == 3_600
    assert config.poll_seconds == 60
    assert config.retry_initial_seconds == 60
    assert config.retry_max_seconds == 1_800
    assert config.retry_multiplier == 2
    assert config.celestrak_group == "ACTIVE"
    assert config.celestrak_max_records == 40_000


def test_config_normalizes_group_and_accepts_overrides():
    config = CatalogSyncConfig.from_env({
        "ORBITAL_CATALOG_SYNC_SATCAT_INTERVAL_SECONDS": "120",
        "ORBITAL_CATALOG_SYNC_CELESTRAK_INTERVAL_SECONDS": "90",
        "ORBITAL_CATALOG_SYNC_SPACE_TRACK_INTERVAL_SECONDS": "60",
        "ORBITAL_CATALOG_SYNC_POLL_SECONDS": "5",
        "ORBITAL_CATALOG_SYNC_RETRY_INITIAL_SECONDS": "10",
        "ORBITAL_CATALOG_SYNC_RETRY_MAX_SECONDS": "80",
        "ORBITAL_CATALOG_SYNC_RETRY_MULTIPLIER": "4",
        "ORBITAL_CATALOG_SYNC_CELESTRAK_GROUP": " active ",
        "ORBITAL_CATALOG_SYNC_CELESTRAK_MAX_RECORDS": "1000",
    })

    assert config.satcat_interval_seconds == 120
    assert config.celestrak_interval_seconds == 90
    assert config.space_track_interval_seconds == 60
    assert config.poll_seconds == 5
    assert config.retry_initial_seconds == 10
    assert config.retry_max_seconds == 80
    assert config.retry_multiplier == 4
    assert config.celestrak_group == "ACTIVE"
    assert config.celestrak_max_records == 1000


@pytest.mark.parametrize(
    "name",
    (
        "ORBITAL_CATALOG_SYNC_SATCAT_INTERVAL_SECONDS",
        "ORBITAL_CATALOG_SYNC_CELESTRAK_INTERVAL_SECONDS",
        "ORBITAL_CATALOG_SYNC_SPACE_TRACK_INTERVAL_SECONDS",
        "ORBITAL_CATALOG_SYNC_POLL_SECONDS",
        "ORBITAL_CATALOG_SYNC_RETRY_INITIAL_SECONDS",
        "ORBITAL_CATALOG_SYNC_RETRY_MAX_SECONDS",
        "ORBITAL_CATALOG_SYNC_RETRY_MULTIPLIER",
        "ORBITAL_CATALOG_SYNC_CELESTRAK_MAX_RECORDS",
    ),
)
def test_config_rejects_non_positive_values(name):
    with pytest.raises(
        ValueError,
        match="must be greater than zero",
    ):
        CatalogSyncConfig.from_env({
            name: "0",
        })


def test_retry_configuration_relationships_are_validated():
    with pytest.raises(
        ValueError,
        match="must be greater than or equal",
    ):
        CatalogSyncConfig.from_env({
            "ORBITAL_CATALOG_SYNC_RETRY_INITIAL_SECONDS": "60",
            "ORBITAL_CATALOG_SYNC_RETRY_MAX_SECONDS": "30",
        })

    with pytest.raises(
        ValueError,
        match="must be greater than or equal to 2",
    ):
        CatalogSyncConfig.from_env({
            "ORBITAL_CATALOG_SYNC_RETRY_MULTIPLIER": "1",
        })


def test_retry_backoff_is_exponential_and_capped():
    config = _config()

    assert config.retry_delay_seconds(1) == 60
    assert config.retry_delay_seconds(2) == 120
    assert config.retry_delay_seconds(3) == 240
    assert config.retry_delay_seconds(10) == 1_800

    with pytest.raises(
        ValueError,
        match="greater than zero",
    ):
        config.retry_delay_seconds(0)


def test_failed_source_uses_retry_deadline_not_normal_cadence():
    now = datetime(
        2026,
        9,
        20,
        12,
        tzinfo=timezone.utc,
    )

    state = {
        "sources": {
            source: _completed_at(now)
            for source in (
                "satcat",
                "celestrak",
                "space-track",
            )
        },
    }

    state["sources"]["space-track"].update({
        "last_status": "error",
        "last_error": "test failure",
        "consecutive_failures": 1,
        "next_retry_at": (
            now + timedelta(seconds=60)
        ).isoformat(),
    })

    assert due_sources(
        state,
        now=now + timedelta(seconds=59),
        config=_config(),
    ) == ()

    assert due_sources(
        state,
        now=now + timedelta(seconds=60),
        config=_config(),
    ) == (
        "space-track",
    )


def test_outcome_persists_and_resets_retry_state(
    monkeypatch,
):
    monkeypatch.setenv(
        "ORBITAL_CATALOG_SYNC_RETRY_INITIAL_SECONDS",
        "60",
    )
    monkeypatch.setenv(
        "ORBITAL_CATALOG_SYNC_RETRY_MAX_SECONDS",
        "1800",
    )
    monkeypatch.setenv(
        "ORBITAL_CATALOG_SYNC_RETRY_MULTIPLIER",
        "2",
    )

    holder = {
        "state": {
            "sources": {},
        },
    }

    monkeypatch.setattr(
        catalog_sync_orchestrator,
        "_read_state",
        lambda: holder["state"],
    )
    monkeypatch.setattr(
        catalog_sync_orchestrator,
        "_write_state",
        lambda state: holder.__setitem__(
            "state",
            state,
        ),
    )

    def outcome(
        *,
        status,
        completed_at,
        error,
    ):
        return CatalogSyncOutcome(
            source="space-track",
            status=status,
            started_at=completed_at,
            completed_at=completed_at,
            duration_seconds=1.0,
            records=None,
            from_cache=None,
            details={},
            error=error,
        )

    catalog_sync_orchestrator._record_outcome(
        outcome(
            status="error",
            completed_at=(
                "2026-09-20T12:00:00+00:00"
            ),
            error="first failure",
        )
    )

    source_state = holder[
        "state"
    ]["sources"]["space-track"]

    assert source_state["last_status"] == "error"
    assert source_state["consecutive_failures"] == 1
    assert source_state["next_retry_at"] == (
        "2026-09-20T12:01:00+00:00"
    )

    catalog_sync_orchestrator._record_outcome(
        outcome(
            status="error",
            completed_at=(
                "2026-09-20T12:01:00+00:00"
            ),
            error="second failure",
        )
    )

    assert source_state["consecutive_failures"] == 2
    assert source_state["next_retry_at"] == (
        "2026-09-20T12:03:00+00:00"
    )

    catalog_sync_orchestrator._record_outcome(
        outcome(
            status="success",
            completed_at=(
                "2026-09-20T12:03:00+00:00"
            ),
            error=None,
        )
    )

    assert source_state["last_status"] == "success"
    assert source_state["consecutive_failures"] == 0
    assert source_state["next_retry_at"] is None


def test_no_state_makes_all_sources_due_in_canonical_order():
    now = datetime(
        2026,
        9,
        19,
        tzinfo=timezone.utc,
    )

    assert due_sources(
        {},
        now=now,
        config=_config(),
    ) == (
        "satcat",
        "celestrak",
        "space-track",
    )


def test_only_elapsed_sources_are_due():
    now = datetime(
        2026,
        9,
        19,
        12,
        tzinfo=timezone.utc,
    )

    state = {
        "sources": {
            "satcat": _completed_at(
                now - timedelta(hours=11)
            ),
            "celestrak": _completed_at(
                now - timedelta(hours=2)
            ),
            "space-track": _completed_at(
                now - timedelta(minutes=30)
            ),
        },
    }

    assert due_sources(
        state,
        now=now,
        config=_config(),
    ) == (
        "celestrak",
    )


def test_invalid_timestamp_is_due_for_recovery():
    now = datetime.now(
        timezone.utc
    )

    state = {
        "sources": {
            "satcat": {
                "last_completed_at": "invalid",
            },
        },
    }

    assert "satcat" in due_sources(
        state,
        now=now,
        config=_config(),
    )


def test_sleep_is_bounded_by_poll_interval():
    now = datetime(
        2026,
        9,
        19,
        12,
        tzinfo=timezone.utc,
    )

    state = {
        "sources": {
            "satcat": _completed_at(now),
            "celestrak": _completed_at(now),
            "space-track": _completed_at(now),
        },
    }

    assert seconds_until_next_run(
        state,
        now=now,
        config=_config(),
    ) == 60


def test_orchestrator_isolates_sources_and_clears_running_state(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv(
        "ORBITAL_SYNC_STATE_DIR",
        str(tmp_path),
    )

    calls = []

    def succeed(source):
        def run(*args, **kwargs):
            calls.append(source)
            return 1, False, {"source": source}

        return run

    def fail_celestrak(*args, **kwargs):
        calls.append("celestrak")
        raise RuntimeError("isolated provider failure")

    monkeypatch.setattr(
        catalog_sync_orchestrator,
        "_run_satcat",
        succeed("satcat"),
    )
    monkeypatch.setattr(
        catalog_sync_orchestrator,
        "_run_celestrak",
        fail_celestrak,
    )
    monkeypatch.setattr(
        catalog_sync_orchestrator,
        "_run_space_track",
        succeed("space-track"),
    )

    outcomes = catalog_sync_orchestrator.run_catalog_sync()

    assert calls == [
        "satcat",
        "celestrak",
        "space-track",
    ]
    assert [outcome.status for outcome in outcomes] == [
        "success",
        "error",
        "success",
    ]

    state = catalog_sync_orchestrator.read_catalog_sync_state()
    assert all(
        row["running"] is False
        for row in state["sources"].values()
    )
    assert state["sources"]["celestrak"]["last_status"] == "error"
    assert state["sources"]["space-track"]["last_status"] == "success"

    calls.clear()
    monkeypatch.setattr(
        catalog_sync_orchestrator,
        "_run_celestrak",
        succeed("celestrak"),
    )

    single = catalog_sync_orchestrator.run_catalog_sync(
        sources=("celestrak",),
    )

    assert calls == ["celestrak"]
    assert [outcome.source for outcome in single] == ["celestrak"]


def test_lock_contention_is_cross_process_and_releases_after_exception(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv(
        "ORBITAL_SYNC_STATE_DIR",
        str(tmp_path),
    )
    environment = {
        **os.environ,
        "ORBITAL_SYNC_STATE_DIR": str(tmp_path),
    }
    probe = (
        "from backend.app.services.catalog_sync_orchestrator import "
        "CatalogSyncAlreadyRunning, catalog_sync_lock\n"
        "try:\n"
        "    with catalog_sync_lock():\n"
        "        pass\n"
        "except CatalogSyncAlreadyRunning:\n"
        "    raise SystemExit(23)\n"
    )

    with catalog_sync_orchestrator.catalog_sync_lock():
        contended = subprocess.run(
            [sys.executable, "-c", probe],
            cwd=Path(__file__).resolve().parents[1],
            env=environment,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )

    assert contended.returncode == 23

    with pytest.raises(RuntimeError, match="test release"):
        with catalog_sync_orchestrator.catalog_sync_lock():
            raise RuntimeError("test release")

    released = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert released.returncode == 0


def test_state_write_atomically_replaces_complete_json(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv(
        "ORBITAL_SYNC_STATE_DIR",
        str(tmp_path),
    )
    state_path = tmp_path / "catalog-sync-status.json"
    previous = {"sources": {"satcat": {"running": True}}}
    replacement = {"sources": {"satcat": {"running": False}}}
    state_path.write_text(
        json.dumps(previous),
        encoding="utf-8",
    )

    observed = []
    original_replace = Path.replace

    def observe_replace(source, destination):
        observed.append({
            "destination_before": json.loads(
                Path(destination).read_text(encoding="utf-8")
            ),
            "temporary": json.loads(
                source.read_text(encoding="utf-8")
            ),
        })
        return original_replace(source, destination)

    monkeypatch.setattr(Path, "replace", observe_replace)

    catalog_sync_orchestrator._write_state(replacement)

    assert observed == [{
        "destination_before": previous,
        "temporary": replacement,
    }]
    assert json.loads(state_path.read_text(encoding="utf-8")) == replacement
    assert not state_path.with_suffix(".tmp").exists()


def test_provider_cache_ttls_follow_configured_intervals(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("ORBITAL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv(
        "ORBITAL_CATALOG_SYNC_SATCAT_INTERVAL_SECONDS",
        "101",
    )
    monkeypatch.setenv(
        "ORBITAL_CATALOG_SYNC_CELESTRAK_INTERVAL_SECONDS",
        "202",
    )
    monkeypatch.setenv(
        "ORBITAL_CATALOG_SYNC_SPACE_TRACK_INTERVAL_SECONDS",
        "303",
    )

    observed = {}

    def fetch(source):
        def run(**kwargs):
            observed[source] = kwargs["max_age_seconds"]
            return [], False

        return run

    @dataclass
    class Result:
        records: int = 0

    monkeypatch.setattr(
        catalog_sync_orchestrator,
        "fetch_satcat_csv",
        fetch("satcat"),
    )
    monkeypatch.setattr(
        catalog_sync_orchestrator,
        "fetch_gp_by_group",
        lambda group, **kwargs: fetch("celestrak")(**kwargs),
    )
    monkeypatch.setattr(
        catalog_sync_orchestrator,
        "fetch_current_gp",
        fetch("space-track"),
    )
    monkeypatch.setattr(
        catalog_sync_orchestrator,
        "get_session_factory",
        lambda: lambda: nullcontext(object()),
    )
    monkeypatch.setattr(
        catalog_sync_orchestrator,
        "sync_satcat_records",
        lambda session, records: Result(),
    )
    monkeypatch.setattr(
        catalog_sync_orchestrator,
        "sync_celestrak_records",
        lambda session, records: Result(),
    )
    monkeypatch.setattr(
        catalog_sync_orchestrator,
        "sync_space_track_gp",
        lambda session, records: Result(),
    )

    catalog_sync_orchestrator._run_satcat()
    catalog_sync_orchestrator._run_celestrak(
        group="ACTIVE",
        max_records=1,
    )
    catalog_sync_orchestrator._run_space_track()

    assert observed == {
        "satcat": 101,
        "celestrak": 202,
        "space-track": 303,
    }


@pytest.mark.parametrize(
    "environment, message",
    (
        (
            {"ORBITAL_CATALOG_SYNC_POLL_SECONDS": "not-an-integer"},
            "must be an integer",
        ),
        (
            {"ORBITAL_CATALOG_SYNC_CELESTRAK_GROUP": "   "},
            "cannot be empty",
        ),
    ),
)
def test_additional_invalid_configurations_are_rejected(
    environment,
    message,
):
    with pytest.raises(ValueError, match=message):
        CatalogSyncConfig.from_env(environment)
