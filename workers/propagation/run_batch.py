from __future__ import annotations

import argparse
from datetime import datetime, timezone

from backend.app.db.session import (
    get_session_factory,
)
from backend.app.services.propagation import (
    run_batch_propagation,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run deterministic SGP4 batch propagation "
            "for the latest orbital elements."
        )
    )

    parser.add_argument(
        "--at",
        type=str,
        default=None,
        help=(
            "UTC propagation timestamp in ISO 8601. "
            "Defaults to current UTC time."
        ),
    )

    return parser.parse_args()


def parse_target_time(
    value: str | None,
) -> datetime:
    if value is None:
        return datetime.now(
            timezone.utc
        )

    target = datetime.fromisoformat(
        value.replace(
            "Z",
            "+00:00",
        )
    )

    if target.tzinfo is None:
        raise ValueError(
            "--at must include timezone information"
        )

    return target.astimezone(
        timezone.utc
    )


def main() -> None:
    args = parse_args()

    target_time = parse_target_time(
        args.at
    )

    session_factory = (
        get_session_factory()
    )

    with session_factory() as session:
        result = run_batch_propagation(
            session,
            target_time=target_time,
        )

    print(f"Run ID: {result.run_id}")
    print(
        f"Target time: "
        f"{result.target_time.isoformat()}"
    )
    print(f"Objects: {result.total}")
    print(
        f"Successful: {result.successful}"
    )
    print(f"Failed: {result.failed}")
    print(
        f"Duration: "
        f"{result.duration_ms:.3f} ms"
    )


if __name__ == "__main__":
    main()
