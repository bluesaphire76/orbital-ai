from __future__ import annotations

import argparse
from datetime import datetime, timezone

from backend.app.db.session import (
    get_session_factory,
)
from backend.app.services.conjunction_grid import (
    ConjunctionObjectLabel,
)
from backend.app.services.conjunction_runs import (
    execute_conjunction_screening,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run deterministic OrbitalAI "
            "conjunction screening and persist results."
        )
    )

    parser.add_argument(
        "--hours",
        type=float,
        default=6.0,
        help="Future screening horizon in hours",
    )

    parser.add_argument(
        "--step-seconds",
        type=int,
        default=60,
        help="Propagation grid interval in seconds",
    )

    parser.add_argument(
        "--candidate-distance-km",
        type=float,
        default=10.0,
        help=(
            "Maximum refined miss distance "
            "to persist and report"
        ),
    )

    parser.add_argument(
        "--max-relative-speed-km-s",
        type=float,
        default=16.0,
        help=(
            "Maximum relative speed used to inflate "
            "the coarse screening distance"
        ),
    )

    return parser.parse_args()


def _validate_args(
    args: argparse.Namespace,
) -> None:
    if args.hours <= 0:
        raise ValueError(
            "--hours must be greater than zero"
        )

    if args.step_seconds <= 0:
        raise ValueError(
            "--step-seconds must be greater than zero"
        )

    if args.candidate_distance_km <= 0:
        raise ValueError(
            "--candidate-distance-km "
            "must be greater than zero"
        )

    if args.max_relative_speed_km_s <= 0:
        raise ValueError(
            "--max-relative-speed-km-s "
            "must be greater than zero"
        )


def _format_object(
    label: ConjunctionObjectLabel | None,
    object_id: int,
) -> str:
    if label is None:
        return (
            "Unknown object "
            f"(internal id {object_id})"
        )

    return (
        f"{label.object_name} "
        f"(NORAD {label.norad_cat_id})"
    )


def main() -> None:
    args = parse_args()

    _validate_args(
        args
    )

    start_time = datetime.now(
        timezone.utc
    )

    horizon_seconds = int(
        args.hours * 3600
    )

    session_factory = (
        get_session_factory()
    )

    with session_factory() as session:
        execution = (
            execute_conjunction_screening(
                session,
                start_time=start_time,
                horizon_seconds=(
                    horizon_seconds
                ),
                step_seconds=(
                    args.step_seconds
                ),
                candidate_distance_km=(
                    args.candidate_distance_km
                ),
                max_relative_speed_km_s=(
                    args.max_relative_speed_km_s
                ),
            )
        )

    result = execution.result

    labels = {
        label.orbital_object_id: label
        for label in result.object_labels
    }

    print(
        f"Run ID: {execution.run_id}"
    )

    print(
        "Duration: "
        f"{execution.duration_ms:.3f} ms"
    )

    print(
        "Window: "
        f"{result.start_time.isoformat()} "
        "-> "
        f"{result.end_time.isoformat()}"
    )

    print(
        f"Objects: {result.objects}"
    )

    print(
        f"Samples: {result.samples}"
    )

    print(
        "Propagation attempts: "
        f"{result.propagation_attempts}"
    )

    print(
        "Propagation failures: "
        f"{result.propagation_failures}"
    )

    print(
        "Expired skips: "
        f"{result.expired_skips}"
    )

    print(
        "Shared-solution groups: "
        f"{result.shared_solution_groups}"
    )

    print(
        "Shared-solution objects: "
        f"{result.shared_solution_objects}"
    )

    print(
        "Suppressed shared pairs: "
        f"{result.suppressed_shared_pairs}"
    )

    print(
        "Raw candidates: "
        f"{result.raw_candidates}"
    )

    print(
        "Unique candidates: "
        f"{result.unique_candidates}"
    )

    print(
        "Refinement attempts: "
        f"{result.refinement_attempts}"
    )

    print(
        "Refinement failures: "
        f"{result.refinement_failures}"
    )

    print(
        "Conjunctions: "
        f"{len(result.refined_conjunctions)}"
    )

    for conjunction in (
        result.refined_conjunctions
    ):
        primary = labels.get(
            conjunction.primary_object_id
        )

        secondary = labels.get(
            conjunction.secondary_object_id
        )

        print()

        print(
            "Primary: "
            + _format_object(
                primary,
                conjunction.primary_object_id,
            )
        )

        print(
            "Secondary: "
            + _format_object(
                secondary,
                conjunction.secondary_object_id,
            )
        )

        print(
            "TCA: "
            f"{conjunction.tca.isoformat()}"
        )

        print(
            "Miss distance: "
            f"{conjunction.miss_distance_km:.6f} km"
        )

        print(
            "Relative velocity: "
            f"{conjunction.relative_velocity_km_s:.6f} km/s"
        )

        print(
            "Method: "
            f"{conjunction.method}"
        )


if __name__ == "__main__":
    main()
