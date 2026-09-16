from __future__ import annotations

from backend.app.observability.operations import observe_screening

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
from backend.app.services.conjunction_grid import (
    ConjunctionGridResult,
    run_conjunction_grid,
)


@dataclass(frozen=True, slots=True)
class ConjunctionExecutionResult:
    run_id: int
    duration_ms: float
    result: ConjunctionGridResult


@observe_screening
def execute_conjunction_screening(
    session: Session,
    *,
    start_time: datetime,
    horizon_seconds: int,
    step_seconds: int,
    candidate_distance_km: float,
    max_relative_speed_km_s: float = 16.0,
    source: str = "celestrak",
    use_linear_prefilter: bool = True,
    chunk_seconds: int | None = None,
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
        candidate_distance_km=(
            candidate_distance_km
        ),
        max_relative_speed_km_s=(
            max_relative_speed_km_s
        ),
        source=source,
        use_linear_prefilter=(
            use_linear_prefilter
        ),
        chunk_seconds=chunk_seconds,
    )

    duration_ms = (
        perf_counter()
        - timer
    ) * 1000.0

    completed_at = datetime.now(
        timezone.utc
    )

    # Use the exact orbital elements that were
    # selected for this screening run.
    #
    # Do not query canonical ephemerides again after
    # screening because:
    #
    # 1. it is unnecessary work;
    # 2. provider data could theoretically change;
    # 3. event provenance must reference the precise
    #    orbital solution used by the engine.
    element_ids = dict(
        result.element_ids
    )

    repository = ConjunctionRepository(
        session
    )

    try:
        run = repository.add_run(
            ConjunctionRun(
                source=source,
                window_start=(
                    result.start_time
                ),
                window_end=(
                    result.end_time
                ),
                step_seconds=(
                    step_seconds
                ),
                candidate_distance_km=(
                    candidate_distance_km
                ),
                max_relative_speed_km_s=(
                    max_relative_speed_km_s
                ),
                objects=(
                    result.objects
                ),
                samples=(
                    result.samples
                ),
                chunk_count=result.chunk_count,
                chunk_seconds=result.chunk_seconds,
                duplicate_events_suppressed=result.duplicate_events_suppressed,
                max_chunk_raw_candidates=result.max_chunk_raw_candidates,
                max_chunk_unique_candidates=result.max_chunk_unique_candidates,
                max_chunk_refinement_attempts=result.max_chunk_refinement_attempts,
                propagation_attempts=(
                    result
                    .propagation_attempts
                ),
                propagation_failures=(
                    result
                    .propagation_failures
                ),
                expired_skips=(
                    result.expired_skips
                ),
                shared_solution_groups=(
                    result
                    .shared_solution_groups
                ),
                shared_solution_objects=(
                    result
                    .shared_solution_objects
                ),
                suppressed_shared_pairs=(
                    result
                    .suppressed_shared_pairs
                ),
                raw_candidates=(
                    result.raw_candidates
                ),
                unique_candidates=(
                    result.unique_candidates
                ),
                refinement_attempts=(
                    result
                    .refinement_attempts
                ),
                refinement_failures=(
                    result
                    .refinement_failures
                ),
                event_count=len(
                    result
                    .refined_conjunctions
                ),
                duration_ms=(
                    duration_ms
                ),
                started_at=(
                    started_at
                ),
                completed_at=(
                    completed_at
                ),
            )
        )

        for conjunction in (
            result.refined_conjunctions
        ):
            primary_element_id = (
                element_ids.get(
                    conjunction
                    .primary_object_id
                )
            )

            secondary_element_id = (
                element_ids.get(
                    conjunction
                    .secondary_object_id
                )
            )

            if (
                primary_element_id is None
                or secondary_element_id
                is None
            ):
                raise RuntimeError(
                    "Missing orbital element "
                    "provenance for conjunction "
                    f"pair "
                    f"{conjunction.primary_object_id}/"
                    f"{conjunction.secondary_object_id}"
                )

            repository.add_event(
                ConjunctionEvent(
                    run_id=(
                        run.id
                    ),
                    primary_object_id=(
                        conjunction
                        .primary_object_id
                    ),
                    secondary_object_id=(
                        conjunction
                        .secondary_object_id
                    ),
                    primary_element_id=(
                        primary_element_id
                    ),
                    secondary_element_id=(
                        secondary_element_id
                    ),
                    tca=(
                        conjunction.tca
                    ),
                    miss_distance_km=(
                        conjunction
                        .miss_distance_km
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
        run_id=(
            run_id
        ),
        duration_ms=(
            duration_ms
        ),
        result=(
            result
        ),
    )
