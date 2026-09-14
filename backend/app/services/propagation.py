from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from time import perf_counter

from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.db.models.orbital_element import OrbitalElement
from backend.app.db.models.propagation import PropagatedState
from backend.app.db.repositories.orbital_elements import (
    OrbitalElementRepository,
)
from backend.app.db.repositories.propagation import (
    PropagationRepository,
)
from backend.app.services.ephemeris_quality import (
    assess_ephemeris_quality,
)
from orbital_engine.propagation import (
    propagate_utc,
    satrec_from_omm,
)


@dataclass(frozen=True, slots=True)
class PropagationOutcome:
    success: bool
    position: tuple[float, float, float] | None
    velocity: tuple[float, float, float] | None
    error_type: str | None
    error_message: str | None
    duration_ms: float


@dataclass(frozen=True, slots=True)
class BatchPropagationResult:
    run_id: int
    target_time: datetime
    total: int
    successful: int
    failed: int
    duration_ms: float


def ensure_utc(
    when: datetime,
) -> datetime:
    if when.tzinfo is None:
        raise ValueError(
            "Propagation target time must be timezone-aware"
        )

    return when.astimezone(
        timezone.utc
    )


def propagate_element(
    element: OrbitalElement,
    when: datetime,
) -> PropagationOutcome:
    target_time = ensure_utc(
        when
    )

    started = perf_counter()

    try:
        satellite = satrec_from_omm(
            element.raw_omm
        )

        position, velocity = propagate_utc(
            satellite,
            target_time,
        )

        return PropagationOutcome(
            success=True,
            position=position,
            velocity=velocity,
            error_type=None,
            error_message=None,
            duration_ms=(
                perf_counter() - started
            )
            * 1000.0,
        )

    except Exception as exc:
        return PropagationOutcome(
            success=False,
            position=None,
            velocity=None,
            error_type=type(exc).__name__,
            error_message=str(exc),
            duration_ms=(
                perf_counter() - started
            )
            * 1000.0,
        )


def run_batch_propagation(
    session: Session,
    *,
    target_time: datetime,
    source: str = "celestrak",
) -> BatchPropagationResult:
    target_time = ensure_utc(
        target_time
    )

    settings = get_settings()

    started = perf_counter()

    element_repository = (
        OrbitalElementRepository(
            session
        )
    )

    propagation_repository = (
        PropagationRepository(
            session
        )
    )

    elements = (
        element_repository.list_latest(
            source=source
        )
    )

    run = (
        propagation_repository.create_run(
            target_time=target_time
        )
    )

    successful = 0
    failed = 0

    try:
        for element in elements:
            quality = assess_ephemeris_quality(
                epoch=element.epoch,
                target_time=target_time,
                warning_hours=(
                    settings.ephemeris_warning_hours
                ),
                stale_hours=(
                    settings.ephemeris_stale_hours
                ),
                max_hours=(
                    settings.ephemeris_max_hours
                ),
            )

            if quality.propagation_allowed:
                outcome = propagate_element(
                    element,
                    target_time,
                )

            else:
                outcome = PropagationOutcome(
                    success=False,
                    position=None,
                    velocity=None,
                    error_type="ExpiredEphemeris",
                    error_message=(
                        "Orbital element age "
                        f"{quality.age_hours:.2f}h "
                        "exceeds maximum "
                        f"{settings.ephemeris_max_hours:.2f}h"
                    ),
                    duration_ms=0.0,
                )

            if outcome.success:
                successful += 1
            else:
                failed += 1

            position = outcome.position
            velocity = outcome.velocity

            state = PropagatedState(
                run_id=run.id,
                orbital_object_id=(
                    element.orbital_object_id
                ),
                orbital_element_id=(
                    element.id
                ),
                target_time=target_time,
                frame="TEME",
                success=outcome.success,
                ephemeris_age_seconds=(
                    quality.age_seconds
                ),
                ephemeris_status=(
                    quality.status.value
                ),
                position_x_km=(
                    position[0]
                    if position is not None
                    else None
                ),
                position_y_km=(
                    position[1]
                    if position is not None
                    else None
                ),
                position_z_km=(
                    position[2]
                    if position is not None
                    else None
                ),
                velocity_x_km_s=(
                    velocity[0]
                    if velocity is not None
                    else None
                ),
                velocity_y_km_s=(
                    velocity[1]
                    if velocity is not None
                    else None
                ),
                velocity_z_km_s=(
                    velocity[2]
                    if velocity is not None
                    else None
                ),
                error_type=(
                    outcome.error_type
                ),
                error_message=(
                    outcome.error_message
                ),
                duration_ms=(
                    outcome.duration_ms
                ),
            )

            propagation_repository.add_state(
                state
            )

        duration_ms = (
            perf_counter() - started
        ) * 1000.0

        completed_at = datetime.now(
            timezone.utc
        )

        propagation_repository.complete_run(
            run,
            completed_at=completed_at,
            total_objects=len(elements),
            successful=successful,
            failed=failed,
            duration_ms=duration_ms,
        )

        run_id = run.id

        session.commit()

    except Exception:
        session.rollback()
        raise

    return BatchPropagationResult(
        run_id=run_id,
        target_time=target_time,
        total=len(elements),
        successful=successful,
        failed=failed,
        duration_ms=duration_ms,
    )
