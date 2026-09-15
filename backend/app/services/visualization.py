from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import (
    get_settings,
)
from backend.app.db.models.orbital_object import (
    OrbitalObject,
)
from backend.app.db.repositories.orbital_elements import (
    OrbitalElementRepository,
)
from backend.app.schemas.visualization import (
    ObjectTrajectory,
    TrajectoryPoint,
    VisualizationObject,
    VisualizationSnapshot,
)
from backend.app.services.ephemeris_quality import (
    assess_ephemeris_quality,
)
from orbital_engine.frames import (
    itrs_state_from_satrec,
)
from orbital_engine.propagation import (
    satrec_from_omm,
)


class VisualizationObjectNotFound(
    LookupError
):
    pass


class VisualizationEphemerisExpired(
    RuntimeError
):
    pass


def _ensure_utc(
    when: datetime,
) -> datetime:
    if when.tzinfo is None:
        raise ValueError(
            "Datetime must be timezone-aware"
        )

    return when.astimezone(
        timezone.utc
    )


def _object_map(
    session: Session,
    object_ids: list[int],
) -> dict[int, OrbitalObject]:
    if not object_ids:
        return {}

    objects = session.scalars(
        select(
            OrbitalObject
        ).where(
            OrbitalObject.id.in_(
                object_ids
            )
        )
    )

    return {
        orbital_object.id:
            orbital_object
        for orbital_object in objects
    }


def build_visualization_snapshot(
    session: Session,
    *,
    when: datetime,
    source: str = "celestrak",
) -> VisualizationSnapshot:
    when = _ensure_utc(
        when
    )

    settings = get_settings()

    repository = (
        OrbitalElementRepository(
            session
        )
    )

    elements = (
        repository.list_latest(
            source=source
        )
    )

    objects_by_id = _object_map(
        session,
        [
            element.orbital_object_id
            for element in elements
        ],
    )

    rendered: list[
        VisualizationObject
    ] = []

    expired_skips = 0
    propagation_failures = 0

    for element in elements:
        orbital_object = (
            objects_by_id.get(
                element.orbital_object_id
            )
        )

        if orbital_object is None:
            propagation_failures += 1
            continue

        quality = (
            assess_ephemeris_quality(
                epoch=element.epoch,
                target_time=when,
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

        if not quality.propagation_allowed:
            expired_skips += 1
            continue

        try:
            satellite = satrec_from_omm(
                element.raw_omm
            )

            (
                position,
                velocity,
            ) = itrs_state_from_satrec(
                satellite,
                when,
            )

        except Exception:
            propagation_failures += 1
            continue

        rendered.append(
            VisualizationObject(
                object_id=(
                    orbital_object.id
                ),
                norad_cat_id=(
                    orbital_object
                    .norad_cat_id
                ),
                object_name=(
                    orbital_object
                    .object_name
                ),
                object_type=(
                    orbital_object
                    .object_type
                ),
                epoch=element.epoch,
                ephemeris_status=(
                    quality.status.value
                ),
                x_m=(
                    position[0]
                    * 1000.0
                ),
                y_m=(
                    position[1]
                    * 1000.0
                ),
                z_m=(
                    position[2]
                    * 1000.0
                ),
                vx_m_s=(
                    velocity[0]
                    * 1000.0
                ),
                vy_m_s=(
                    velocity[1]
                    * 1000.0
                ),
                vz_m_s=(
                    velocity[2]
                    * 1000.0
                ),
            )
        )

    return VisualizationSnapshot(
        at=when,
        frame="ITRS/ECEF",
        objects=rendered,
        total_elements=len(
            elements
        ),
        rendered_objects=len(
            rendered
        ),
        expired_skips=(
            expired_skips
        ),
        propagation_failures=(
            propagation_failures
        ),
    )


def build_object_trajectory(
    session: Session,
    *,
    object_id: int,
    start: datetime,
    end: datetime,
    step_seconds: int = 60,
    source: str = "celestrak",
) -> ObjectTrajectory:
    start = _ensure_utc(
        start
    )

    end = _ensure_utc(
        end
    )

    if end <= start:
        raise ValueError(
            "end must be after start"
        )

    if step_seconds < 10:
        raise ValueError(
            "step_seconds must be at least 10"
        )

    if (
        end - start
        > timedelta(hours=24)
    ):
        raise ValueError(
            "trajectory window cannot exceed "
            "24 hours"
        )

    estimated_points = (
        int(
            (
                end - start
            ).total_seconds()
            / step_seconds
        )
        + 1
    )

    if estimated_points > 1000:
        raise ValueError(
            "trajectory cannot exceed "
            "1000 points"
        )

    repository = (
        OrbitalElementRepository(
            session
        )
    )

    elements = (
        repository.list_latest(
            source=source
        )
    )

    element = next(
        (
            item
            for item in elements
            if (
                item.orbital_object_id
                == object_id
            )
        ),
        None,
    )

    if element is None:
        raise VisualizationObjectNotFound(
            f"Orbital object {object_id} "
            "has no current orbital element"
        )

    orbital_object = session.get(
        OrbitalObject,
        object_id,
    )

    if orbital_object is None:
        raise VisualizationObjectNotFound(
            f"Orbital object {object_id} "
            "not found"
        )

    settings = get_settings()

    satellite = satrec_from_omm(
        element.raw_omm
    )

    points: list[
        TrajectoryPoint
    ] = []

    current = start

    while current <= end:
        quality = (
            assess_ephemeris_quality(
                epoch=element.epoch,
                target_time=current,
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

        if not quality.propagation_allowed:
            raise VisualizationEphemerisExpired(
                "Ephemeris becomes expired "
                f"at {current.isoformat()}"
            )

        position, _ = (
            itrs_state_from_satrec(
                satellite,
                current,
            )
        )

        points.append(
            TrajectoryPoint(
                at=current,
                x_m=(
                    position[0]
                    * 1000.0
                ),
                y_m=(
                    position[1]
                    * 1000.0
                ),
                z_m=(
                    position[2]
                    * 1000.0
                ),
            )
        )

        current += timedelta(
            seconds=step_seconds
        )

    if (
        points
        and points[-1].at < end
    ):
        position, _ = (
            itrs_state_from_satrec(
                satellite,
                end,
            )
        )

        points.append(
            TrajectoryPoint(
                at=end,
                x_m=(
                    position[0]
                    * 1000.0
                ),
                y_m=(
                    position[1]
                    * 1000.0
                ),
                z_m=(
                    position[2]
                    * 1000.0
                ),
            )
        )

    return ObjectTrajectory(
        object_id=(
            orbital_object.id
        ),
        norad_cat_id=(
            orbital_object
            .norad_cat_id
        ),
        object_name=(
            orbital_object
            .object_name
        ),
        frame="ITRS/ECEF",
        start=start,
        end=end,
        step_seconds=(
            step_seconds
        ),
        points=points,
    )
