from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from contextlib import contextmanager, nullcontext
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.app.db.repositories.conjunctions import ConjunctionRepository
from backend.app.services.conjunction_screening_config import (
    ConjunctionScreeningConfig,
)
from backend.app.services import conjunction_screening_scheduler as scheduler


NOW = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)


def _config() -> ConjunctionScreeningConfig:
    return ConjunctionScreeningConfig.from_env({})


def test_config_defaults():
    config = _config()

    assert config.interval_seconds == 14_400
    assert config.poll_seconds == 60
    assert config.retry_initial_seconds == 900
    assert config.retry_max_seconds == 3_600
    assert config.retry_multiplier == 2
    assert config.hours == 6
    assert config.horizon_seconds == 21_600
    assert config.step_seconds == 60


def test_config_overrides():
    config = ConjunctionScreeningConfig.from_env({
        "ORBITAL_CONJUNCTION_SCREENING_INTERVAL_SECONDS": "7200",
        "ORBITAL_CONJUNCTION_SCREENING_POLL_SECONDS": "30",
        "ORBITAL_CONJUNCTION_SCREENING_RETRY_INITIAL_SECONDS": "120",
        "ORBITAL_CONJUNCTION_SCREENING_RETRY_MAX_SECONDS": "960",
        "ORBITAL_CONJUNCTION_SCREENING_RETRY_MULTIPLIER": "3",
        "ORBITAL_CONJUNCTION_SCREENING_HOURS": "8",
        "ORBITAL_CONJUNCTION_SCREENING_STEP_SECONDS": "120",
        "ORBITAL_SCREENING_CHUNK_SECONDS": "960",
    })

    assert config == ConjunctionScreeningConfig(
        interval_seconds=7_200,
        poll_seconds=30,
        retry_initial_seconds=120,
        retry_max_seconds=960,
        retry_multiplier=3,
        hours=8,
        step_seconds=120,
    )


@pytest.mark.parametrize(
    "environment, message",
    (
        ({"ORBITAL_CONJUNCTION_SCREENING_INTERVAL_SECONDS": "0"}, "greater than zero"),
        ({"ORBITAL_CONJUNCTION_SCREENING_POLL_SECONDS": "invalid"}, "must be an integer"),
        ({
            "ORBITAL_CONJUNCTION_SCREENING_RETRY_INITIAL_SECONDS": "901",
            "ORBITAL_CONJUNCTION_SCREENING_RETRY_MAX_SECONDS": "900",
        }, "greater than or equal"),
        ({"ORBITAL_CONJUNCTION_SCREENING_RETRY_MULTIPLIER": "1"}, "greater than or equal"),
        ({
            "ORBITAL_CONJUNCTION_SCREENING_INTERVAL_SECONDS": "60",
            "ORBITAL_CONJUNCTION_SCREENING_POLL_SECONDS": "61",
        }, "less than or equal"),
        ({
            "ORBITAL_CONJUNCTION_SCREENING_HOURS": "1",
            "ORBITAL_CONJUNCTION_SCREENING_STEP_SECONDS": "3601",
        }, "cannot exceed"),
        ({
            "ORBITAL_CONJUNCTION_SCREENING_STEP_SECONDS": "120",
            "ORBITAL_SCREENING_CHUNK_SECONDS": "900",
        }, "must be at least and a multiple"),
    ),
)
def test_invalid_config_is_rejected(environment, message):
    with pytest.raises(ValueError, match=message):
        ConjunctionScreeningConfig.from_env(environment)


def test_retry_delay_is_exponential_and_capped():
    config = _config()

    assert [config.retry_delay_seconds(value) for value in range(1, 6)] == [
        900,
        1_800,
        3_600,
        3_600,
        3_600,
    ]
    with pytest.raises(ValueError, match="greater than zero"):
        config.retry_delay_seconds(0)


def _latest(*, completed_at=NOW, run_id=26):
    return scheduler.LatestCanonicalRun(
        run_id=run_id,
        completed_at=completed_at,
    )


def _decision(latest, state=None, *, now=NOW):
    return scheduler.evaluate_due(
        latest,
        state or {},
        now=now,
        config=_config(),
    )


def test_no_previous_run_is_due():
    decision = _decision(None)
    assert decision.due is True
    assert decision.reason == "no_successful_run"


def test_recent_run_is_not_due():
    decision = _decision(_latest(completed_at=NOW - timedelta(hours=1)))
    assert decision.due is False
    assert decision.next_due_at == NOW + timedelta(hours=3)


def test_exact_boundary_is_due():
    assert _decision(_latest(completed_at=NOW - timedelta(hours=4))).due is True


def test_stale_run_is_due():
    assert _decision(_latest(completed_at=NOW - timedelta(hours=5))).due is True


def test_future_timestamp_is_not_due_and_wait_is_bounded():
    decision = _decision(_latest(completed_at=NOW + timedelta(hours=1)))
    assert decision.due is False
    assert decision.future_completion is True
    assert scheduler.seconds_until_next_check(
        decision,
        now=NOW,
        config=_config(),
    ) == 60


def test_missing_scheduler_state_still_uses_recent_database_run():
    decision = _decision(
        _latest(completed_at=NOW - timedelta(minutes=5)),
        {},
    )
    assert decision.due is False
    assert decision.latest_run_id == 26


def test_next_due_is_based_on_completion_not_window_start():
    completed = NOW - timedelta(hours=2, minutes=3)
    assert _decision(_latest(completed_at=completed)).next_due_at == (
        completed + timedelta(hours=4)
    )


def test_retry_in_future_prevents_run():
    state = {
        "last_status": "error",
        "last_completed_at": (NOW - timedelta(minutes=1)).isoformat(),
        "consecutive_failures": 1,
        "next_retry_at": (NOW + timedelta(minutes=14)).isoformat(),
    }
    decision = _decision(None, state)
    assert decision.due is False
    assert decision.reason == "retry_pending"


def test_retry_boundary_is_due():
    state = {
        "last_status": "error",
        "last_completed_at": (NOW - timedelta(minutes=15)).isoformat(),
        "consecutive_failures": 1,
        "next_retry_at": NOW.isoformat(),
    }
    assert _decision(None, state).due is True


def test_retry_is_derived_for_legacy_partial_state():
    failed = NOW - timedelta(minutes=10)
    decision = _decision(None, {
        "last_status": "error",
        "last_completed_at": failed.isoformat(),
        "consecutive_failures": 2,
    })
    assert decision.next_due_at == failed + timedelta(minutes=30)


def test_invalid_legacy_failure_count_is_tolerated():
    decision = _decision(None, {
        "last_status": "error",
        "last_completed_at": NOW.isoformat(),
        "consecutive_failures": "legacy-invalid",
    })
    assert decision.next_due_at == NOW + timedelta(minutes=15)


def test_read_state_tolerates_missing_partial_and_invalid_json(tmp_path, monkeypatch):
    monkeypatch.setenv("ORBITAL_METRICS_DIR", str(tmp_path))
    assert scheduler.read_conjunction_screening_state() == {}
    scheduler.conjunction_screening_state_path().write_text(
        '{"running": true}', encoding="utf-8"
    )
    assert scheduler.read_conjunction_screening_state() == {"running": True}
    scheduler.conjunction_screening_state_path().write_text("{", encoding="utf-8")
    assert scheduler.read_conjunction_screening_state() == {}


def test_state_write_is_atomic_and_leaves_no_temporary_file(tmp_path, monkeypatch):
    monkeypatch.setenv("ORBITAL_METRICS_DIR", str(tmp_path))
    scheduler.write_conjunction_screening_state({"running": False, "last_run_id": 26})
    assert json.loads(scheduler.conjunction_screening_state_path().read_text()) == {
        "last_run_id": 26,
        "running": False,
    }
    assert list(tmp_path.glob("*.tmp")) == []


def test_lock_is_nonblocking_between_processes(tmp_path, monkeypatch):
    monkeypatch.setenv("ORBITAL_METRICS_DIR", str(tmp_path))
    code = (
        "from backend.app.services.conjunction_screening_scheduler import "
        "conjunction_screening_lock\n"
        "with conjunction_screening_lock():\n"
        " print('locked', flush=True)\n"
        " input()\n"
    )
    environment = dict(os.environ, ORBITAL_METRICS_DIR=str(tmp_path))
    process = subprocess.Popen(
        [sys.executable, "-c", code],
        cwd=Path(__file__).parents[1],
        env=environment,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert process.stdout.readline().strip() == "locked"
        with pytest.raises(scheduler.ConjunctionScreeningAlreadyRunning):
            with scheduler.conjunction_screening_lock():
                pass
    finally:
        process.stdin.write("\n")
        process.stdin.flush()
        process.wait(timeout=5)
    assert process.returncode == 0


def test_lock_is_released_after_exception(tmp_path, monkeypatch):
    monkeypatch.setenv("ORBITAL_METRICS_DIR", str(tmp_path))
    with pytest.raises(RuntimeError, match="boom"):
        with scheduler.conjunction_screening_lock():
            raise RuntimeError("boom")
    with scheduler.conjunction_screening_lock():
        pass


def test_scheduler_lock_contention_is_a_skip(tmp_path, monkeypatch):
    monkeypatch.setenv("ORBITAL_METRICS_DIR", str(tmp_path))

    @contextmanager
    def busy_lock():
        raise scheduler.ConjunctionScreeningAlreadyRunning("busy")
        yield

    monkeypatch.setattr(scheduler, "conjunction_screening_lock", busy_lock)
    result = scheduler.run_scheduler_cycle(
        config=_config(),
        runner=lambda **kwargs: pytest.fail("runner must not execute"),
        now=NOW,
        latest_run_loader=lambda: None,
    )
    assert result.status == "lock_busy"


def test_success_resets_retry_and_running_state(tmp_path, monkeypatch):
    monkeypatch.setenv("ORBITAL_METRICS_DIR", str(tmp_path))
    scheduler.write_conjunction_screening_state({
        "running": False,
        "last_status": "error",
        "last_completed_at": (NOW - timedelta(hours=1)).isoformat(),
        "consecutive_failures": 3,
        "next_retry_at": (NOW - timedelta(seconds=1)).isoformat(),
    })
    result = scheduler.run_scheduler_cycle(
        config=_config(),
        runner=lambda **kwargs: SimpleNamespace(run_id=27),
        now=NOW,
        latest_run_loader=lambda: None,
        persisted_run_loader=lambda run_id: _latest(
            completed_at=NOW + timedelta(minutes=1),
            run_id=run_id,
        ),
        clock=lambda: NOW + timedelta(minutes=2),
    )
    state = scheduler.read_conjunction_screening_state()
    assert result.status == "success"
    assert state["running"] is False
    assert state["consecutive_failures"] == 0
    assert state["next_retry_at"] is None
    assert state["last_run_id"] == 27


def test_failure_records_backoff_and_restores_running(tmp_path, monkeypatch):
    monkeypatch.setenv("ORBITAL_METRICS_DIR", str(tmp_path))

    def fail(**kwargs):
        raise LookupError("synthetic")

    result = scheduler.run_scheduler_cycle(
        config=_config(),
        runner=fail,
        now=NOW,
        latest_run_loader=lambda: None,
        clock=lambda: NOW + timedelta(minutes=1),
    )
    state = scheduler.read_conjunction_screening_state()
    assert result.status == "error"
    assert result.error_type == "LookupError"
    assert state["running"] is False
    assert state["consecutive_failures"] == 1
    assert state["next_retry_at"] == (NOW + timedelta(minutes=16)).isoformat()
    assert state["last_error"] == "LookupError: synthetic"


def test_consecutive_failure_uses_exponential_retry(tmp_path, monkeypatch):
    monkeypatch.setenv("ORBITAL_METRICS_DIR", str(tmp_path))
    scheduler.write_conjunction_screening_state({
        "last_status": "error",
        "last_completed_at": (NOW - timedelta(hours=1)).isoformat(),
        "consecutive_failures": 1,
        "next_retry_at": (NOW - timedelta(seconds=1)).isoformat(),
    })
    result = scheduler.run_scheduler_cycle(
        config=_config(),
        runner=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("again")),
        now=NOW,
        latest_run_loader=lambda: None,
        clock=lambda: NOW,
    )
    assert result.next_due_at == NOW + timedelta(minutes=30)
    assert scheduler.read_conjunction_screening_state()["consecutive_failures"] == 2


def test_manual_success_newer_than_error_resets_retry(tmp_path, monkeypatch):
    monkeypatch.setenv("ORBITAL_METRICS_DIR", str(tmp_path))
    scheduler.write_conjunction_screening_state({
        "last_status": "error",
        "last_completed_at": (NOW - timedelta(hours=2)).isoformat(),
        "consecutive_failures": 2,
        "next_retry_at": (NOW + timedelta(hours=1)).isoformat(),
    })
    manual = _latest(completed_at=NOW - timedelta(minutes=10), run_id=91)
    result = scheduler.run_scheduler_cycle(
        config=_config(),
        runner=lambda **kwargs: pytest.fail("recent manual run must postpone scheduler"),
        now=NOW,
        latest_run_loader=lambda: manual,
    )
    state = scheduler.read_conjunction_screening_state()
    assert result.status == "not_due"
    assert state["last_run_id"] == 91
    assert state["consecutive_failures"] == 0
    assert state["next_retry_at"] is None


def test_cycle_passes_hours_step_and_canonical_worker_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("ORBITAL_METRICS_DIR", str(tmp_path))
    calls = []

    def runner(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(run_id=32)

    scheduler.run_scheduler_cycle(
        config=_config(),
        runner=runner,
        now=NOW,
        latest_run_loader=lambda: None,
        persisted_run_loader=lambda run_id: _latest(
            completed_at=NOW,
            run_id=run_id,
        ),
        clock=lambda: NOW,
    )
    assert calls == [{"hours": 6, "step_seconds": 60, "start_time": NOW}]


def test_repository_latest_source_query_filters_canonical():
    class Session:
        statement = None

        def scalar(self, statement):
            self.statement = statement
            return None

    session = Session()
    ConjunctionRepository(session).get_latest_run_for_source("canonical")
    compiled = session.statement.compile()
    assert "conjunction_runs.source" in str(compiled)
    assert "canonical" in compiled.params.values()


def test_shared_worker_uses_canonical_source_and_explicit_parameters(monkeypatch):
    from workers.conjunction import run_screening as worker

    calls = []
    monkeypatch.setattr(worker, "get_session_factory", lambda: lambda: nullcontext(None))
    monkeypatch.setattr(
        worker,
        "execute_conjunction_screening",
        lambda session, **kwargs: calls.append(kwargs) or SimpleNamespace(run_id=1),
    )
    worker.run_screening(hours=6, step_seconds=60, start_time=NOW)
    assert calls[0]["source"] == "canonical"
    assert calls[0]["horizon_seconds"] == 21_600
    assert calls[0]["candidate_distance_km"] == 10.0


def test_manual_cli_lock_contention_is_nonzero(monkeypatch, capsys):
    from workers.conjunction import run_screening as worker

    @contextmanager
    def busy_lock():
        raise scheduler.ConjunctionScreeningAlreadyRunning("already running")
        yield

    monkeypatch.setattr(worker, "conjunction_screening_lock", busy_lock)
    monkeypatch.setattr(sys, "argv", ["screening", "--summary-only"])
    with pytest.raises(SystemExit) as raised:
        worker.main()
    assert raised.value.code == 2
    assert "already running" in capsys.readouterr().err


def test_once_does_not_force_recent_run(monkeypatch):
    from workers.conjunction import run_screening_scheduler as worker

    called = []
    monkeypatch.setattr(worker, "_print_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        worker,
        "run_scheduler_cycle",
        lambda **kwargs: scheduler.ScreeningCycleResult(
            status="not_due",
            next_due_at=NOW + timedelta(hours=3),
            run_id=26,
        ),
    )
    assert worker.run_scheduler(
        config=_config(),
        stop_event=threading.Event(),
        once=True,
        runner=lambda **kwargs: called.append(kwargs),
        clock=lambda: NOW,
    ) == 0
    assert called == []


def test_scheduler_success_uses_database_completed_at(tmp_path, monkeypatch):
    monkeypatch.setenv("ORBITAL_METRICS_DIR", str(tmp_path))
    database_completed_at = NOW + timedelta(minutes=17, seconds=37)
    process_completed_at = database_completed_at + timedelta(seconds=20)
    events = []

    result = scheduler.run_scheduler_cycle(
        config=_config(),
        runner=lambda **kwargs: SimpleNamespace(run_id=27),
        now=NOW,
        latest_run_loader=lambda: None,
        persisted_run_loader=lambda run_id: _latest(
            completed_at=database_completed_at,
            run_id=run_id,
        ),
        event_callback=lambda event, details: events.append((event, details)),
        clock=lambda: process_completed_at,
    )

    assert result.status == "success"
    assert result.next_due_at == database_completed_at + timedelta(hours=4)
    completed_event = next(details for event, details in events if event == "run_completed")
    assert completed_event["completed_at"] == database_completed_at.isoformat()
    assert completed_event["next_due_at"] == result.next_due_at.isoformat()
    state = scheduler.read_conjunction_screening_state()
    assert state["last_completed_at"] == database_completed_at.isoformat()


def test_completed_next_due_matches_following_poll(tmp_path, monkeypatch):
    monkeypatch.setenv("ORBITAL_METRICS_DIR", str(tmp_path))
    persisted = _latest(
        completed_at=NOW + timedelta(minutes=17, seconds=37),
        run_id=27,
    )
    events = []
    completed = scheduler.run_scheduler_cycle(
        config=_config(),
        runner=lambda **kwargs: SimpleNamespace(run_id=27),
        now=NOW,
        latest_run_loader=lambda: None,
        persisted_run_loader=lambda run_id: persisted,
        event_callback=lambda event, details: events.append((event, details)),
        clock=lambda: persisted.completed_at + timedelta(seconds=20),
    )
    following_poll = scheduler.run_scheduler_cycle(
        config=_config(),
        runner=lambda **kwargs: pytest.fail("recent run must not execute"),
        now=persisted.completed_at + timedelta(minutes=1),
        latest_run_loader=lambda: persisted,
    )

    completed_event = next(details for event, details in events if event == "run_completed")
    assert completed.next_due_at == following_poll.next_due_at
    assert completed_event["next_due_at"] == following_poll.next_due_at.isoformat()


def test_restart_with_recent_run_27_does_not_screen(tmp_path, monkeypatch):
    monkeypatch.setenv("ORBITAL_METRICS_DIR", str(tmp_path))
    run_27 = _latest(completed_at=NOW - timedelta(minutes=30), run_id=27)
    result = scheduler.run_scheduler_cycle(
        config=_config(),
        runner=lambda **kwargs: pytest.fail("restart must not screen"),
        now=NOW,
        latest_run_loader=lambda: run_27,
    )
    assert result.status == "not_due"
    assert result.run_id == 27
    assert result.next_due_at == run_27.completed_at + timedelta(hours=4)


def test_persistent_success_state_reconciles_to_database_completed_at(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("ORBITAL_METRICS_DIR", str(tmp_path))
    database_completed_at = NOW - timedelta(minutes=20)
    scheduler.write_conjunction_screening_state({
        "running": False,
        "last_status": "success",
        "last_run_id": 27,
        "last_completed_at": (database_completed_at + timedelta(seconds=20)).isoformat(),
        "consecutive_failures": 0,
        "next_retry_at": None,
    })
    run_27 = _latest(completed_at=database_completed_at, run_id=27)
    result = scheduler.run_scheduler_cycle(
        config=_config(),
        runner=lambda **kwargs: pytest.fail("recent run must not execute"),
        now=NOW,
        latest_run_loader=lambda: run_27,
    )
    state = scheduler.read_conjunction_screening_state()
    assert result.next_due_at == database_completed_at + timedelta(hours=4)
    assert state["last_completed_at"] == database_completed_at.isoformat()


class _StopAfterWaits:
    def __init__(self, waits: int):
        self._waits = waits
        self.calls = 0

    def is_set(self):
        return self.calls >= self._waits

    def wait(self, _seconds):
        self.calls += 1
        return self.is_set()


def test_consecutive_not_due_polls_log_next_due_once(monkeypatch):
    from workers.conjunction import run_screening_scheduler as worker

    events = []
    decision = scheduler.ScreeningCycleResult(
        status="not_due",
        next_due_at=NOW + timedelta(hours=3),
        run_id=27,
    )
    monkeypatch.setattr(worker, "run_scheduler_cycle", lambda **kwargs: decision)
    monkeypatch.setattr(
        worker,
        "_print_event",
        lambda event, **details: events.append((event, details)),
    )
    worker.run_scheduler(
        config=_config(),
        stop_event=_StopAfterWaits(3),
        clock=lambda: NOW,
    )
    next_due_events = [
        details
        for event, details in events
        if event == "conjunction_screening_scheduler_next_due"
    ]
    assert len(next_due_events) == 1


def test_new_run_id_logs_next_due_even_when_deadline_matches(monkeypatch):
    from workers.conjunction import run_screening_scheduler as worker

    events = []
    results = iter((
        scheduler.ScreeningCycleResult(
            status="not_due",
            next_due_at=NOW + timedelta(hours=3),
            run_id=27,
        ),
        scheduler.ScreeningCycleResult(
            status="not_due",
            next_due_at=NOW + timedelta(hours=3),
            run_id=28,
        ),
    ))
    monkeypatch.setattr(worker, "run_scheduler_cycle", lambda **kwargs: next(results))
    monkeypatch.setattr(
        worker,
        "_print_event",
        lambda event, **details: events.append((event, details)),
    )
    worker.run_scheduler(
        config=_config(),
        stop_event=_StopAfterWaits(2),
        clock=lambda: NOW,
    )
    next_due_events = [
        details
        for event, details in events
        if event == "conjunction_screening_scheduler_next_due"
    ]
    assert [event["latest_run_id"] for event in next_due_events] == [27, 28]


def test_recoverable_cycle_error_does_not_escape_loop(monkeypatch):
    from workers.conjunction import run_screening_scheduler as worker

    stop_event = threading.Event()
    events = []

    def fail_cycle(**kwargs):
        stop_event.set()
        raise ConnectionError("database unavailable")

    monkeypatch.setattr(worker, "run_scheduler_cycle", fail_cycle)
    monkeypatch.setattr(
        worker,
        "_print_event",
        lambda event, **details: events.append((event, details)),
    )
    assert worker.run_scheduler(
        config=_config(),
        stop_event=stop_event,
        clock=lambda: NOW,
    ) == 0
    assert events[1] == (
        "conjunction_screening_scheduler_cycle_failed",
        {"error_type": "ConnectionError"},
    )


def test_scheduler_import_has_no_output_or_execution():
    result = subprocess.run(
        [sys.executable, "-c", "import workers.conjunction.run_screening_scheduler"],
        cwd=Path(__file__).parents[1],
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout == ""
    assert result.stderr == ""


def test_shutdown_event_prevents_cycle(monkeypatch):
    from workers.conjunction import run_screening_scheduler as worker

    stop_event = threading.Event()
    stop_event.set()
    monkeypatch.setattr(worker, "_print_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        worker,
        "run_scheduler_cycle",
        lambda **kwargs: pytest.fail("cycle must not run after shutdown"),
    )
    assert worker.run_scheduler(
        config=_config(),
        stop_event=stop_event,
        clock=lambda: NOW,
    ) == 0


def test_wait_is_interruptible():
    event = threading.Event()
    timer = threading.Timer(0.02, event.set)
    timer.start()
    try:
        assert event.wait(5) is True
    finally:
        timer.cancel()


def test_compose_defines_scheduler_service_and_guardrails():
    compose = (
        Path(__file__).parents[1] / "deploy/compose/compose.core.yml"
    ).read_text(encoding="utf-8")
    service = compose.split("  conjunction-screening:\n", 1)[1].split(
        "\nnetworks:", 1
    )[0]
    assert "workers.conjunction.run_screening_scheduler" in service
    assert "restart: unless-stopped" in service
    assert "../../data:/app/data" in service
    assert "condition: service_completed_successfully" in service
    for variable in (
        "ORBITAL_CONJUNCTION_SCREENING_INTERVAL_SECONDS",
        "ORBITAL_CONJUNCTION_SCREENING_POLL_SECONDS",
        "ORBITAL_CONJUNCTION_SCREENING_RETRY_INITIAL_SECONDS",
        "ORBITAL_CONJUNCTION_SCREENING_RETRY_MAX_SECONDS",
        "ORBITAL_CONJUNCTION_SCREENING_RETRY_MULTIPLIER",
        "ORBITAL_CONJUNCTION_SCREENING_HOURS",
        "ORBITAL_CONJUNCTION_SCREENING_STEP_SECONDS",
        "ORBITAL_SCREENING_MAX_OBJECTS",
        "ORBITAL_SCREENING_MAX_PROPAGATIONS",
        "ORBITAL_SCREENING_CHUNK_SECONDS",
        "ORBITAL_SCREENING_MAX_CHUNK_UNIQUE_CANDIDATES",
    ):
        assert variable in service
    assert "ports:" not in service
    assert "healthcheck:" not in service
