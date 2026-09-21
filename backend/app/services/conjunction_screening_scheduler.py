from __future__ import annotations

import fcntl
import json
import os
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Callable, Iterator, Literal, Mapping, Protocol

from sqlalchemy.orm import sessionmaker

from backend.app.db.repositories.conjunctions import ConjunctionRepository
from backend.app.db.session import get_session_factory
from backend.app.services.conjunction_screening_config import (
    ConjunctionScreeningConfig,
)


class ConjunctionScreeningAlreadyRunning(RuntimeError):
    pass


class ScreeningExecution(Protocol):
    run_id: int


@dataclass(frozen=True, slots=True)
class LatestCanonicalRun:
    run_id: int
    completed_at: datetime


@dataclass(frozen=True, slots=True)
class DueDecision:
    due: bool
    next_due_at: datetime | None
    latest_run_id: int | None
    reason: str
    future_completion: bool = False


@dataclass(frozen=True, slots=True)
class ScreeningCycleResult:
    status: Literal["not_due", "success", "error", "lock_busy"]
    next_due_at: datetime | None
    run_id: int | None = None
    error_type: str | None = None
    future_completion: bool = False


SchedulerRunner = Callable[..., ScreeningExecution]
SchedulerEventCallback = Callable[[str, Mapping[str, object]], None]
LatestRunLoader = Callable[[], LatestCanonicalRun | None]
PersistedRunLoader = Callable[[int], LatestCanonicalRun | None]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return normalize_utc(datetime.fromisoformat(value))
    except ValueError:
        return None


def _state_dir() -> Path:
    return Path(os.getenv("ORBITAL_METRICS_DIR", "data/observability"))


def conjunction_screening_state_path() -> Path:
    return _state_dir() / "conjunction-screening-status.json"


def conjunction_screening_lock_path() -> Path:
    return _state_dir() / "conjunction-screening.lock"


def read_conjunction_screening_state() -> dict[str, object]:
    try:
        state = json.loads(
            conjunction_screening_state_path().read_text(encoding="utf-8")
        )
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return state if isinstance(state, dict) else {}


def write_conjunction_screening_state(state: Mapping[str, object]) -> None:
    path = conjunction_screening_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as output:
            temporary_path = Path(output.name)
            json.dump(state, output, indent=2, sort_keys=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


@contextmanager
def conjunction_screening_lock() -> Iterator[None]:
    path = conjunction_screening_lock_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ConjunctionScreeningAlreadyRunning(
                "A conjunction screening run is already in progress"
            ) from exc
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def load_latest_canonical_run(
    session_factory: sessionmaker | None = None,
) -> LatestCanonicalRun | None:
    factory = session_factory or get_session_factory()
    with factory() as session:
        run = ConjunctionRepository(session).get_latest_run_for_source("canonical")
        if run is None:
            return None
        return LatestCanonicalRun(
            run_id=run.id,
            completed_at=normalize_utc(run.completed_at),
        )


def load_canonical_run(
    run_id: int,
    session_factory: sessionmaker | None = None,
) -> LatestCanonicalRun | None:
    factory = session_factory or get_session_factory()
    with factory() as session:
        run = ConjunctionRepository(session).get_run(run_id)
        if run is None or run.source != "canonical":
            return None
        return LatestCanonicalRun(
            run_id=run.id,
            completed_at=normalize_utc(run.completed_at),
        )


def _state_failure_is_current(
    state: Mapping[str, object],
    latest_run: LatestCanonicalRun | None,
) -> bool:
    if state.get("last_status") != "error":
        return False
    failed_at = parse_timestamp(state.get("last_completed_at"))
    if failed_at is None:
        return latest_run is None
    return (
        latest_run is None
        or normalize_utc(latest_run.completed_at) <= failed_at
    )


def _failure_count(value: object, *, default: int) -> int:
    try:
        return max(0, int(value or default))
    except (TypeError, ValueError):
        return default


def evaluate_due(
    latest_run: LatestCanonicalRun | None,
    state: Mapping[str, object],
    *,
    now: datetime,
    config: ConjunctionScreeningConfig,
) -> DueDecision:
    now = normalize_utc(now)

    if _state_failure_is_current(state, latest_run):
        next_retry_at = parse_timestamp(state.get("next_retry_at"))
        if next_retry_at is None:
            failures = max(
                1,
                _failure_count(state.get("consecutive_failures"), default=1),
            )
            failed_at = parse_timestamp(state.get("last_completed_at")) or now
            next_retry_at = failed_at + timedelta(
                seconds=config.retry_delay_seconds(failures)
            )
        return DueDecision(
            due=now >= next_retry_at,
            next_due_at=next_retry_at,
            latest_run_id=latest_run.run_id if latest_run else None,
            reason="retry_due" if now >= next_retry_at else "retry_pending",
        )

    if latest_run is None:
        return DueDecision(
            due=True,
            next_due_at=None,
            latest_run_id=None,
            reason="no_successful_run",
        )

    completed_at = normalize_utc(latest_run.completed_at)
    next_due_at = completed_at + timedelta(seconds=config.interval_seconds)
    future_completion = completed_at > now
    return DueDecision(
        due=now >= next_due_at,
        next_due_at=next_due_at,
        latest_run_id=latest_run.run_id,
        reason="cadence_due" if now >= next_due_at else "cadence_pending",
        future_completion=future_completion,
    )


def seconds_until_next_check(
    decision: DueDecision,
    *,
    now: datetime,
    config: ConjunctionScreeningConfig,
) -> float:
    if decision.due or decision.next_due_at is None:
        return 0.0
    remaining = max(
        0.0,
        (decision.next_due_at - normalize_utc(now)).total_seconds(),
    )
    return min(float(config.poll_seconds), remaining)


def _base_state(state: Mapping[str, object]) -> dict[str, object]:
    return dict(state)


def _record_started(
    state: Mapping[str, object],
    *,
    started_at: datetime,
) -> dict[str, object]:
    updated = _base_state(state)
    updated.update({
        "running": True,
        "last_started_at": started_at.isoformat(),
        "last_error": None,
        "updated_at": started_at.isoformat(),
    })
    write_conjunction_screening_state(updated)
    return updated


def _record_success(
    state: Mapping[str, object],
    *,
    completed_at: datetime,
    run_id: int,
) -> dict[str, object]:
    updated = _base_state(state)
    updated.update({
        "running": False,
        "last_completed_at": completed_at.isoformat(),
        "last_status": "success",
        "last_error": None,
        "last_run_id": run_id,
        "consecutive_failures": 0,
        "next_retry_at": None,
        "updated_at": completed_at.isoformat(),
    })
    write_conjunction_screening_state(updated)
    return updated


def _record_error(
    state: Mapping[str, object],
    *,
    completed_at: datetime,
    error: Exception,
    config: ConjunctionScreeningConfig,
) -> tuple[dict[str, object], datetime]:
    failures = _failure_count(
        state.get("consecutive_failures"),
        default=0,
    ) + 1
    next_retry_at = completed_at + timedelta(
        seconds=config.retry_delay_seconds(failures)
    )
    updated = _base_state(state)
    updated.update({
        "running": False,
        "last_completed_at": completed_at.isoformat(),
        "last_status": "error",
        "last_error": f"{type(error).__name__}: {error}",
        "consecutive_failures": failures,
        "next_retry_at": next_retry_at.isoformat(),
        "updated_at": completed_at.isoformat(),
    })
    write_conjunction_screening_state(updated)
    return updated, next_retry_at


def _reconcile_state_with_database(
    state: Mapping[str, object],
    latest_run: LatestCanonicalRun | None,
) -> tuple[dict[str, object], bool]:
    if latest_run is None:
        return dict(state), False

    database_completed_at = normalize_utc(latest_run.completed_at)
    state_completed_at = parse_timestamp(state.get("last_completed_at"))

    if state.get("last_status") == "error":
        should_reconcile = (
            state_completed_at is not None
            and database_completed_at > state_completed_at
        )
    else:
        should_reconcile = (
            state.get("last_status") != "success"
            or state.get("last_run_id") != latest_run.run_id
            or state_completed_at != database_completed_at
        )

    if not should_reconcile:
        return dict(state), False

    return (
        _record_success(
            state,
            completed_at=database_completed_at,
            run_id=latest_run.run_id,
        ),
        True,
    )


def run_scheduler_cycle(
    *,
    config: ConjunctionScreeningConfig,
    runner: SchedulerRunner,
    now: datetime | None = None,
    latest_run_loader: LatestRunLoader = load_latest_canonical_run,
    persisted_run_loader: PersistedRunLoader = load_canonical_run,
    event_callback: SchedulerEventCallback | None = None,
    clock: Callable[[], datetime] = utc_now,
) -> ScreeningCycleResult:
    cycle_now = normalize_utc(now or clock())
    state = read_conjunction_screening_state()
    latest_run = latest_run_loader()

    state, _ = _reconcile_state_with_database(state, latest_run)

    decision = evaluate_due(latest_run, state, now=cycle_now, config=config)
    if not decision.due:
        return ScreeningCycleResult(
            status="not_due",
            next_due_at=decision.next_due_at,
            run_id=decision.latest_run_id,
            future_completion=decision.future_completion,
        )

    try:
        with conjunction_screening_lock():
            # Another process may have completed a run between the first DB read
            # and lock acquisition. Re-read under the shared lock before work.
            state = read_conjunction_screening_state()
            latest_run = latest_run_loader()
            state, _ = _reconcile_state_with_database(state, latest_run)
            decision = evaluate_due(
                latest_run,
                state,
                now=cycle_now,
                config=config,
            )
            if not decision.due:
                return ScreeningCycleResult(
                    status="not_due",
                    next_due_at=decision.next_due_at,
                    run_id=decision.latest_run_id,
                    future_completion=decision.future_completion,
                )

            state = _record_started(state, started_at=cycle_now)
            if event_callback is not None:
                event_callback("run_started", {
                    "start_time": cycle_now.isoformat(),
                    "hours": config.hours,
                    "step_seconds": config.step_seconds,
                })

            try:
                execution = runner(
                    hours=config.hours,
                    step_seconds=config.step_seconds,
                    start_time=cycle_now,
                )
                persisted_run = persisted_run_loader(execution.run_id)
                if persisted_run is None:
                    raise RuntimeError(
                        "Successful conjunction screening run was not found "
                        "in PostgreSQL"
                    )
            except Exception as exc:
                completed_at = normalize_utc(clock())
                _, next_retry_at = _record_error(
                    state,
                    completed_at=completed_at,
                    error=exc,
                    config=config,
                )
                if event_callback is not None:
                    event_callback("run_failed", {
                        "error_type": type(exc).__name__,
                        "next_retry_at": next_retry_at.isoformat(),
                    })
                return ScreeningCycleResult(
                    status="error",
                    next_due_at=next_retry_at,
                    error_type=type(exc).__name__,
                )

            completed_at = normalize_utc(persisted_run.completed_at)
            _record_success(
                state,
                completed_at=completed_at,
                run_id=execution.run_id,
            )
            next_due_at = completed_at + timedelta(
                seconds=config.interval_seconds
            )
            if event_callback is not None:
                event_callback("run_completed", {
                    "run_id": execution.run_id,
                    "completed_at": completed_at.isoformat(),
                    "next_due_at": next_due_at.isoformat(),
                })
            return ScreeningCycleResult(
                status="success",
                next_due_at=next_due_at,
                run_id=execution.run_id,
            )
    except ConjunctionScreeningAlreadyRunning:
        if event_callback is not None:
            event_callback("lock_busy", {})
        return ScreeningCycleResult(
            status="lock_busy",
            next_due_at=cycle_now + timedelta(seconds=config.poll_seconds),
            run_id=latest_run.run_id if latest_run else None,
        )
