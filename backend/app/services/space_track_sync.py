from __future__ import annotations

from backend.app.observability.operations import observe_ingestion

from dataclasses import dataclass
from typing import Any

from sqlalchemy import (
    update,
)
from sqlalchemy.dialects.postgresql import (
    insert,
)
from sqlalchemy.orm import Session

from backend.app.db.models.orbital_element import (
    OrbitalElement,
)
from backend.app.db.models.orbital_object import (
    OrbitalObject,
)
from backend.app.db.repositories.orbital_objects import (
    OrbitalObjectRepository,
)
from backend.app.services.orbital_elements import (
    build_orbital_element_values,
)


@dataclass(
    frozen=True,
    slots=True,
)
class SpaceTrackSyncResult:
    records: int
    matched_objects: int
    unmatched_objects: int

    elements_created: int
    elements_existing: int


def _chunks(
    values: list,
    size: int,
):
    for offset in range(
        0,
        len(values),
        size,
    ):
        yield values[
            offset:
            offset + size
        ]


@observe_ingestion("space-track")
def sync_space_track_gp(
    session: Session,
    records: list[
        dict[str, Any]
    ],
) -> SpaceTrackSyncResult:
    prepared: dict[
        int,
        dict[str, Any],
    ] = {}


    for record in records:
        raw_cat_id = (
            record.get(
                "NORAD_CAT_ID"
            )
        )

        if raw_cat_id in (
            None,
            "",
        ):
            continue

        prepared[
            int(raw_cat_id)
        ] = record


    repository = (
        OrbitalObjectRepository(
            session
        )
    )


    object_map: dict[
        int,
        OrbitalObject,
    ] = {}


    identifiers = list(
        prepared
    )


    for chunk in _chunks(
        identifiers,
        5000,
    ):
        for orbital_object in (
            repository
            .list_by_norad_cat_ids(
                chunk
            )
        ):
            object_map[
                orbital_object
                .norad_cat_id
            ] = orbital_object


    rows: list[
        dict[str, Any]
    ] = []

    matched_object_ids: set[
        int
    ] = set()

    unmatched = 0


    for (
        norad_cat_id,
        record,
    ) in prepared.items():
        orbital_object = (
            object_map.get(
                norad_cat_id
            )
        )

        if orbital_object is None:
            unmatched += 1
            continue


        values = (
            build_orbital_element_values(
                record,
                source="space-track",
            )
        )


        rows.append({
            "orbital_object_id":
                orbital_object.id,
            **values,
        })


        matched_object_ids.add(
            orbital_object.id
        )


    inserted = 0


    try:
        for batch in _chunks(
            rows,
            1000,
        ):
            statement = (
                insert(
                    OrbitalElement
                )
                .values(
                    batch
                )
                .on_conflict_do_nothing(
                    constraint=(
                        "uq_orbital_elements_"
                        "object_source_epoch"
                    )
                )
                .returning(
                    OrbitalElement.id
                )
            )


            inserted += len(
                session.scalars(
                    statement
                ).all()
            )


        for object_id_batch in (
            _chunks(
                list(
                    matched_object_ids
                ),
                5000,
            )
        ):
            session.execute(
                update(
                    OrbitalObject
                )
                .where(
                    OrbitalObject.id.in_(
                        object_id_batch
                    )
                )
                .values(
                    has_current_elements=True
                )
            )


        session.commit()

    except Exception:
        session.rollback()
        raise


    matched = len(
        matched_object_ids
    )


    return SpaceTrackSyncResult(
        records=len(
            prepared
        ),

        matched_objects=
            matched,

        unmatched_objects=
            unmatched,

        elements_created=
            inserted,

        elements_existing=(
            matched
            - inserted
        ),
    )
