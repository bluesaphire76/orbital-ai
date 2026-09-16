from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from sqlalchemy.orm import Session

from backend.app.db.repositories.orbital_elements import (
    OrbitalElementRepository,
)
from backend.app.db.repositories.orbital_objects import (
    OrbitalObjectRepository,
)
from backend.app.services.orbital_catalog import (
    build_orbital_object_values,
)
from backend.app.services.orbital_elements import (
    build_orbital_element_values,
)


@dataclass(frozen=True, slots=True)
class CelesTrakSyncResult:
    records: int
    objects_created: int
    objects_updated: int
    elements_created: int
    elements_existing: int


def sync_celestrak_records(
    session: Session,
    records: Iterable[dict[str, Any]],
) -> CelesTrakSyncResult:
    object_repository = OrbitalObjectRepository(session)
    element_repository = OrbitalElementRepository(session)

    records_processed = 0
    objects_created = 0
    objects_updated = 0
    elements_created = 0
    elements_existing = 0

    try:
        for record in records:
            norad_cat_id, object_values = (
                build_orbital_object_values(record)
            )

            object_values[
                "has_current_elements"
            ] = True

            object_values[
                "is_on_orbit"
            ] = True

            orbital_object, object_created = (
                object_repository.upsert(
                    norad_cat_id=norad_cat_id,
                    values=object_values,
                )
            )

            if object_created:
                objects_created += 1
            else:
                objects_updated += 1

            element_values = (
                build_orbital_element_values(record)
            )

            _, element_created = (
                element_repository.create_if_missing(
                    orbital_object_id=orbital_object.id,
                    values=element_values,
                )
            )

            if element_created:
                elements_created += 1
            else:
                elements_existing += 1

            records_processed += 1

        session.commit()

    except Exception:
        session.rollback()
        raise

    return CelesTrakSyncResult(
        records=records_processed,
        objects_created=objects_created,
        objects_updated=objects_updated,
        elements_created=elements_created,
        elements_existing=elements_existing,
    )
