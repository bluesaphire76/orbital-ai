from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from time import perf_counter

from sqlalchemy.orm import Session

from backend.app.db.models.conjunction import (
    ConjunctionEvent,
    ConjunctionRun,
)
from backend.app.db.repositories.conjunctions import (
    ConjunctionRepository,
)
from backend.app.db.repositories.orbital_elements import (
    OrbitalElementRepository,
)
from backend.app.services.conjunction_grid import (
    ConjunctionGridResult,
    run_conjunction_grid,
)


@dataclass(frozen=True, slots=True)
class ConjunctionExecutionResult:
    run_id: int
    duration_ms: float
    result: ConjunctionGridResult


def execute_conjunction_screening(
    session: Session,
    *,
    start_time: datetime,
    horizon_seconds: int,
    step_seconds: int,
    candidate_distance_km: float,
    max_relative_speed_km_s: float = 16.0,
    source: str = "celestrak",
) -> ConjunctionExecutionResult:
    started_at = datetime.now(
        timezone.utc
    )

    timer = perf_counter()

    result = run_conjunction_grid(
        session,
        start_time=start_time,
        horizon_seconds=horizon_seconds,
        step_seconds=step_seconds,
        candidate_distance_km=candidate_distance_km,
        max_relative_speed_km_s=max_relative_speed_km_s,
        source=source,
    )

    duration_ms = (
        perf_counter() - timer
    ) * 1000.0

    completed_at = datetime.now(
        timezone.utc
    )

    element_repository = (
        OrbitalElementRepository(
            session
        )
    )

    latest_elements = (
        element_repository.list_latest(
            source=source
        )
    )

    element_ids = {
        element.orbital_object_id: element.id
        for element in latest_elements
    }

    repository = ConjunctionRepository(
        session
    )

    try:
        run = repository.add_run(
            ConjunctionRun(
                source=source,
                window_start=result.start_time,
                window_end=result.end_time,
                step_seconds=step_seconds,
                candidate_distance_km=(
                    candidate_distance_km
                ),
                max_relative_speed_km_s=(
                    max_relative_speed_km_s
                ),
                objects=result.objects,
                samples=result.samples,
                propagation_attempts=(
                    result.propagation_attempts
                ),
                propagation_failures=(
                    result.propagation_failures
                ),
                expired_skips=(
                    result.expired_skips
                ),
                shared_solution_groups=(
                    result.shared_solution_groups
                ),
                shared_solution_objects=(
                    result.shared_solution_objects
                ),
                suppressed_shared_pairs=(
                    result.suppressed_shared_pairs
                ),
                raw_candidates=(
                    result.raw_candidates
                ),
                unique_candidates=(
                    result.unique_candidates
                ),
                refinement_attempts=(
                    result.refinement_attempts
                ),
                refinement_failures=(
                    result.refinement_failures
                ),
                event_count=len(
                    result.refined_conjunctions
                ),
                duration_ms=duration_ms,
                started_at=started_at,
                completed_at=completed_at,
            )
        )

        for conjunction in (
            result.refined_conjunctions
        ):
            primary_element_id = (
                element_ids.get(
                    conjunction.primary_object_id
                )
            )

            secondary_element_id = (
                element_ids.get(
                    conjunction.secondary_object_id
                )
            )

            if (
                primary_element_id is None
                or secondary_element_id is None
            ):
                raise RuntimeError(
                    "Missing orbital element "
                    "for conjunction event"
                )

            repository.add_event(
                ConjunctionEvent(
                    run_id=run.id,
                    primary_object_id=(
                        conjunction.primary_object_id
                    ),
                    secondary_object_id=(
                        conjunction.secondary_object_id
                    ),
                    primary_element_id=(
                        primary_element_id
                    ),
                    secondary_element_id=(
                        secondary_element_id
                    ),
                    tca=conjunction.tca,
                    miss_distance_km=(
                        conjunction.miss_distance_km
                    ),
                    relative_velocity_km_s=(
                        conjunction
                        .relative_velocity_km_s
                    ),
                    method=(
                        conjunction.method
                    ),
                )
            )

        run_id = run.id

        session.commit()

    except Exception:
        session.rollback()
        raise

    return ConjunctionExecutionResult(
        run_id=run_id,
        duration_ms=duration_ms,
        result=result,
    )
