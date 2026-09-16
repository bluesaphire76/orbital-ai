from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import (
    datetime,
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
from backend.app.services.ephemeris_quality import (
    assess_ephemeris_quality,
)


@dataclass(
    frozen=True,
    slots=True,
)
class CanonicalEphemerisSelection:
    target_time: datetime

    canonical_total: int
    eligible_total: int
    expired_total: int

    eligible_elements: tuple[
        OrbitalElement,
        ...,
    ]

    status_counts: dict[
        str,
        int,
    ]

    source_counts: dict[
        str,
        int,
    ]

    eligible_source_counts: dict[
        str,
        int,
    ]

    eligible_object_type_counts: dict[
        str,
        int,
    ]


def select_screening_ephemerides(
    session: Session,
    *,
    target_time: datetime,
) -> CanonicalEphemerisSelection:
    if target_time.tzinfo is None:
        raise ValueError(
            "target_time must be timezone-aware"
        )

    target_time = (
        target_time.astimezone(
            timezone.utc
        )
    )

    settings = get_settings()

    repository = (
        OrbitalElementRepository(
            session
        )
    )

    elements = (
        repository
        .list_canonical_latest(
            earth_orbit_only=True
        )
    )


    object_ids = [
        element.orbital_object_id
        for element in elements
    ]


    if object_ids:
        orbital_objects = (
            session.scalars(
                select(
                    OrbitalObject
                )
                .where(
                    OrbitalObject.id.in_(
                        object_ids
                    )
                )
            )
            .all()
        )
    else:
        orbital_objects = []


    objects_by_id = {
        orbital_object.id:
            orbital_object
        for orbital_object
        in orbital_objects
    }


    eligible: list[
        OrbitalElement
    ] = []

    status_counts: Counter[
        str
    ] = Counter()

    source_counts: Counter[
        str
    ] = Counter()

    eligible_source_counts: Counter[
        str
    ] = Counter()

    object_type_counts: Counter[
        str
    ] = Counter()


    for element in elements:
        source_counts[
            element.source
        ] += 1


        quality = (
            assess_ephemeris_quality(
                epoch=element.epoch,
                target_time=target_time,
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


        status_counts[
            quality.status.value
        ] += 1


        if not quality.propagation_allowed:
            continue


        orbital_object = (
            objects_by_id.get(
                element.orbital_object_id
            )
        )

        if orbital_object is None:
            continue


        if not orbital_object.is_earth_orbit:
            continue


        eligible.append(
            element
        )

        eligible_source_counts[
            element.source
        ] += 1


        object_type = (
            orbital_object.object_type
            or "UNKNOWN"
        )

        object_type_counts[
            object_type
        ] += 1


    return CanonicalEphemerisSelection(
        target_time=target_time,

        canonical_total=len(
            elements
        ),

        eligible_total=len(
            eligible
        ),

        expired_total=(
            len(elements)
            - len(eligible)
        ),

        eligible_elements=tuple(
            eligible
        ),

        status_counts=dict(
            status_counts
        ),

        source_counts=dict(
            source_counts
        ),

        eligible_source_counts=dict(
            eligible_source_counts
        ),

        eligible_object_type_counts=dict(
            object_type_counts
        ),
    )
