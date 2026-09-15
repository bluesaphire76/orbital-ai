from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.db.models.orbital_object import (
    OrbitalObject,
)
from backend.app.db.repositories.orbital_elements import (
    OrbitalElementRepository,
)
from backend.app.services.ephemeris_quality import (
    assess_ephemeris_quality,
)
from backend.app.services.orbital_fingerprint import (
    analyze_shared_orbital_solutions,
)
from orbital_engine.conjunction.grid import (
    GridScreeningResult,
    screen_propagation_grid,
)
from orbital_engine.conjunction.models import (
    StateVector,
)
from orbital_engine.propagation import (
    propagate_utc,
    satrec_from_omm,
)


@dataclass(frozen=True, slots=True)
class ConjunctionObjectLabel:
    orbital_object_id: int
    norad_cat_id: int
    object_name: str


@dataclass(frozen=True, slots=True)
class ConjunctionGridResult:
    start_time: datetime
    end_time: datetime

    objects: int
    samples: int

    propagation_attempts: int
    propagation_failures: int
    expired_skips: int

    shared_solution_groups: int
    shared_solution_objects: int
    suppressed_shared_pairs: int

    raw_candidates: int
    unique_candidates: int

    object_labels: tuple[
        ConjunctionObjectLabel,
        ...
    ]

    screening: GridScreeningResult


def _ensure_utc(
    when: datetime,
) -> datetime:
    if when.tzinfo is None:
        raise ValueError(
            "Grid start time must be timezone-aware"
        )

    return when.astimezone(
        timezone.utc
    )


def _build_sample_times(
    *,
    start_time: datetime,
    horizon_seconds: int,
    step_seconds: int,
) -> list[datetime]:
    if horizon_seconds <= 0:
        raise ValueError(
            "horizon_seconds must be greater than zero"
        )

    if step_seconds <= 0:
        raise ValueError(
            "step_seconds must be greater than zero"
        )

    if step_seconds > horizon_seconds:
        raise ValueError(
            "step_seconds cannot exceed horizon_seconds"
        )

    end_time = (
        start_time
        + timedelta(
            seconds=horizon_seconds
        )
    )

    times: list[
        datetime
    ] = []

    current = start_time

    while current <= end_time:
        times.append(
            current
        )

        current += timedelta(
            seconds=step_seconds
        )

    if times[-1] < end_time:
        times.append(
            end_time
        )

    return times


def _load_object_labels(
    session: Session,
    *,
    object_ids: list[int],
) -> tuple[
    ConjunctionObjectLabel,
    ...
]:
    if not object_ids:
        return ()

    objects = session.scalars(
        select(OrbitalObject)
        .where(
            OrbitalObject.id.in_(
                object_ids
            )
        )
        .order_by(
            OrbitalObject.id
        )
    )

    return tuple(
        ConjunctionObjectLabel(
            orbital_object_id=(
                orbital_object.id
            ),
            norad_cat_id=(
                orbital_object.norad_cat_id
            ),
            object_name=(
                orbital_object.object_name
            ),
        )
        for orbital_object in objects
    )


def run_conjunction_grid(
    session: Session,
    *,
    start_time: datetime,
    horizon_seconds: int = 6 * 60 * 60,
    step_seconds: int = 60,
    candidate_distance_km: float = 10.0,
    max_relative_speed_km_s: float = 16.0,
    source: str = "celestrak",
) -> ConjunctionGridResult:
    start_time = _ensure_utc(
        start_time
    )

    settings = get_settings()

    repository = (
        OrbitalElementRepository(
            session
        )
    )

    elements = repository.list_latest(
        source=source
    )

    shared_solutions = (
        analyze_shared_orbital_solutions(
            elements
        )
    )

    object_ids = [
        element.orbital_object_id
        for element in elements
    ]

    object_labels = (
        _load_object_labels(
            session,
            object_ids=object_ids,
        )
    )

    sample_times = (
        _build_sample_times(
            start_time=start_time,
            horizon_seconds=(
                horizon_seconds
            ),
            step_seconds=(
                step_seconds
            ),
        )
    )

    satellites = []

    for element in elements:
        try:
            satellite = (
                satrec_from_omm(
                    element.raw_omm
                )
            )

        except Exception:
            continue

        satellites.append(
            (
                element,
                satellite,
            )
        )

    propagation_attempts = 0
    propagation_failures = 0
    expired_skips = 0

    snapshots: list[
        tuple[
            datetime,
            list[StateVector],
        ]
    ] = []

    for sample_time in sample_times:
        states: list[
            StateVector
        ] = []

        for (
            element,
            satellite,
        ) in satellites:
            quality = (
                assess_ephemeris_quality(
                    epoch=element.epoch,
                    target_time=sample_time,
                    warning_hours=(
                        settings
                        .ephemeris_warning_hours
                    ),
                    stale_hours=(
                        settings
                        .ephemeris_stale_hours
                    ),
                    max_hours=(
                        settings
                        .ephemeris_max_hours
                    ),
                )
            )

            if (
                not quality
                .propagation_allowed
            ):
                expired_skips += 1
                continue

            propagation_attempts += 1

            try:
                position, velocity = (
                    propagate_utc(
                        satellite,
                        sample_time,
                    )
                )

            except Exception:
                propagation_failures += 1
                continue

            states.append(
                StateVector(
                    object_id=(
                        element
                        .orbital_object_id
                    ),
                    when=sample_time,
                    position_km=position,
                    velocity_km_s=(
                        velocity
                    ),
                )
            )

        snapshots.append(
            (
                sample_time,
                states,
            )
        )

    screening = (
        screen_propagation_grid(
            snapshots,
            candidate_distance_km=(
                candidate_distance_km
            ),
            step_seconds=(
                step_seconds
            ),
            max_relative_speed_km_s=(
                max_relative_speed_km_s
            ),
            excluded_pairs=(
                shared_solutions.pairs
            ),
        )
    )

    return ConjunctionGridResult(
        start_time=start_time,
        end_time=sample_times[-1],
        objects=len(elements),
        samples=len(
            sample_times
        ),
        propagation_attempts=(
            propagation_attempts
        ),
        propagation_failures=(
            propagation_failures
        ),
        expired_skips=(
            expired_skips
        ),
        shared_solution_groups=(
            shared_solutions.groups
        ),
        shared_solution_objects=(
            shared_solutions.objects
        ),
        suppressed_shared_pairs=(
            screening
            .suppressed_shared_pairs
        ),
        raw_candidates=(
            screening.raw_candidates
        ),
        unique_candidates=(
            screening
            .unique_candidates
        ),
        object_labels=(
            object_labels
        ),
        screening=screening,
    )
