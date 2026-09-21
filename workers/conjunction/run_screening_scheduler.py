from __future__ import annotations

import argparse
import json
import signal
import threading
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Callable, Mapping

from backend.app.services.conjunction_screening_config import (
    ConjunctionScreeningConfig,
)
from backend.app.services.conjunction_screening_scheduler import (
    ScreeningCycleResult,
    run_scheduler_cycle,
)
from workers.conjunction.run_screening import run_screening


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the automatic canonical conjunction-screening scheduler. "
            "--once evaluates cadence and runs only when due."
        )
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Evaluate once; do not force a screening run",
    )
    return parser.parse_args(argv)


def _print_event(event: str, **details: object) -> None:
    print(
        json.dumps(
            {
                "event": event,
                "timestamp": _utc_now().isoformat(),
                **details,
            },
            sort_keys=True,
        ),
        flush=True,
    )


def _cycle_event(event: str, details: Mapping[str, object]) -> None:
    _print_event(f"conjunction_screening_scheduler_{event}", **details)


def _wait_seconds(
    result: ScreeningCycleResult,
    *,
    now: datetime,
    config: ConjunctionScreeningConfig,
) -> float:
    if result.next_due_at is None:
        return float(config.poll_seconds)
    return min(
        float(config.poll_seconds),
        max(0.0, (result.next_due_at - now).total_seconds()),
    )


def run_scheduler(
    *,
    config: ConjunctionScreeningConfig,
    stop_event: threading.Event,
    once: bool = False,
    runner: Callable[..., object] = run_screening,
    clock: Callable[[], datetime] = _utc_now,
) -> int:
    _print_event(
        "conjunction_screening_scheduler_started",
        config=asdict(config),
        once=once,
    )
    last_announced_decision: tuple[int | None, str | None] | None = None

    while not stop_event.is_set():
        now = clock()
        try:
            result = run_scheduler_cycle(
                config=config,
                runner=runner,
                now=now,
                event_callback=_cycle_event,
                clock=clock,
            )
        except Exception as exc:
            _print_event(
                "conjunction_screening_scheduler_cycle_failed",
                error_type=type(exc).__name__,
            )
            if once:
                return 1
            stop_event.wait(config.poll_seconds)
            continue

        next_due = (
            result.next_due_at.isoformat()
            if result.next_due_at is not None
            else None
        )
        announcement = (result.run_id, next_due)
        if announcement != last_announced_decision:
            _print_event(
                "conjunction_screening_scheduler_next_due",
                next_due_at=next_due,
                latest_run_id=result.run_id,
            )
            last_announced_decision = announcement
            if result.future_completion:
                _print_event(
                    "conjunction_screening_scheduler_future_completion",
                    latest_run_id=result.run_id,
                    next_due_at=next_due,
                )

        if once:
            return 1 if result.status == "error" else 0

        wait_seconds = _wait_seconds(
            result,
            now=clock(),
            config=config,
        )
        stop_event.wait(wait_seconds)

    _print_event("conjunction_screening_scheduler_stopped")
    return 0


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    config = ConjunctionScreeningConfig.from_env()
    stop_event = threading.Event()

    def stop_scheduler(_signum: int, _frame: object) -> None:
        stop_event.set()

    signal.signal(signal.SIGTERM, stop_scheduler)
    signal.signal(signal.SIGINT, stop_scheduler)
    raise SystemExit(
        run_scheduler(
            config=config,
            stop_event=stop_event,
            once=args.once,
        )
    )


if __name__ == "__main__":
    main()
