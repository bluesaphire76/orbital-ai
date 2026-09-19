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
from backend.app.db.models.orbital_element import (
    OrbitalElement,
)
from backend.app.db.models.orbital_object import (
    OrbitalObject,
)
from backend.app.db.repositories.orbital_elements import (
    OrbitalElementRepository,
)
from backend.app.schemas.visualization import (
    PlaybackObject,
    TrajectoryPoint,
    VisualizationPlayback,
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


def _ensure_utc(
    value: datetime,
) -> datetime:
    if value.tzinfo is None:
        raise ValueError(
            "Datetime must be timezone-aware"
        )

    return value.astimezone(
        timezone.utc
    )


def _validate_window(
    *,
    start: datetime,
    end: datetime,
    step_seconds: int,
) -> None:
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
            "playback window cannot exceed "
            "24 hours"
        )

    estimated_samples = (
        int(
            (
                end - start
            ).total_seconds()
            / step_seconds
        )
        + 1
    )

    if estimated_samples > 1000:
        raise ValueError(
            "playback cannot exceed "
            "1000 samples per object"
        )


def _sample_times(
    *,
    start: datetime,
    end: datetime,
    step_seconds: int,
) -> list[datetime]:
    result: list[
        datetime
    ] = []

    current = start

    while current <= end:
        result.append(
            current
        )

        current += timedelta(
            seconds=step_seconds
        )

    if (
        result
        and result[-1] < end
    ):
        result.append(
            end
        )

    return result


def build_visualization_playback(
    session: Session,
    *,
    start: datetime,
    end: datetime,
    step_seconds: int = 60,
    source: str = "celestrak",
    object_ids: list[int] | None = None,
    element_ids: list[int] | None = None,
) -> VisualizationPlayback:
    start = _ensure_utc(
        start
    )

    end = _ensure_utc(
        end
    )

    _validate_window(
        start=start,
        end=end,
        step_seconds=step_seconds,
    )

    times = _sample_times(
        start=start,
        end=end,
        step_seconds=step_seconds,
    )

    settings = get_settings()

    repository = (
        OrbitalElementRepository(
            session
        )
    )


    requested_ids = (
        {
            int(
                object_id
            )
            for object_id
            in object_ids
        }
        if object_ids is not None
        else None
    )


    if (
        requested_ids is not None
        and len(
            requested_ids
        ) > 16
    ):
        raise ValueError(
            "playback supports at most "
            "16 targeted objects"
        )


    exact_event_replay = (
        element_ids is not None
    )


    if element_ids is not None:
        requested_element_ids = {
            int(
                element_id
            )
            for element_id
            in element_ids
        }


        if (
            len(
                requested_element_ids
            )
            > 16
        ):
            raise ValueError(
                "playback supports at most "
                "16 exact orbital elements"
            )


        elements = list(
            session.scalars(
                select(
                    OrbitalElement
                )
                .where(
                    OrbitalElement.id.in_(
                        requested_element_ids
                    )
                )
                .order_by(
                    OrbitalElement
                    .orbital_object_id
                )
            )
        )


        returned_element_ids = {
            element.id
            for element
            in elements
        }


        missing_element_ids = (
            requested_element_ids
            - returned_element_ids
        )


        if missing_element_ids:
            raise ValueError(
                "Unknown orbital element IDs: "
                + ", ".join(
                    str(
                        element_id
                    )
                    for element_id
                    in sorted(
                        missing_element_ids
                    )
                )
            )


        if requested_ids is not None:
            element_object_ids = {
                element.orbital_object_id
                for element
                in elements
            }


            if (
                element_object_ids
                != requested_ids
            ):
                raise ValueError(
                    "element_id values do not "
                    "match requested object_id values"
                )

    else:
        elements = (
            repository.list_latest(
                source=source
            )
        )


        if requested_ids is not None:
            elements = [
                element
                for element
                in elements
                if element.orbital_object_id
                in requested_ids
            ]


    catalog_object_ids = [
        element.orbital_object_id
        for element in elements
    ]

    orbital_objects = (
        session.scalars(
            select(
                OrbitalObject
            ).where(
                OrbitalObject.id.in_(
                    catalog_object_ids
                )
            )
        )
        if catalog_object_ids
        else []
    )

    objects_by_id = {
        orbital_object.id:
            orbital_object
        for orbital_object
        in orbital_objects
    }

    rendered: list[
        PlaybackObject
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

        try:
            satellite = (
                satrec_from_omm(
                    element.raw_omm
                )
            )

        except Exception:
            propagation_failures += 1
            continue

        points: list[
            TrajectoryPoint
        ] = []

        expired = False
        failed = False
        first_status: str | None = None

        for when in times:
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

            if first_status is None:
                first_status = (
                    quality.status.value
                )

            if (
                not quality
                .propagation_allowed
                and not exact_event_replay
            ):
                expired = True
                break

            try:
                position, _ = (
                    itrs_state_from_satrec(
                        satellite,
                        when,
                    )
                )

            except Exception:
                failed = True
                break

            points.append(
                TrajectoryPoint(
                    at=when,
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

        if expired:
            expired_skips += 1
            continue

        if failed:
            propagation_failures += 1
            continue

        if not points:
            propagation_failures += 1
            continue

        rendered.append(
            PlaybackObject(
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
                owner=(
                    orbital_object
                    .owner
                ),
                launch_date=(
                    orbital_object
                    .launch_date
                ),
                launch_site=(
                    orbital_object
                    .launch_site
                ),
                ops_status_code=(
                    orbital_object
                    .ops_status_code
                ),
                epoch=element.epoch,
                ephemeris_status=(
                    first_status
                    or "UNKNOWN"
                ),
                points=points,
            )
        )

    return VisualizationPlayback(
        start=start,
        end=end,
        step_seconds=(
            step_seconds
        ),
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
