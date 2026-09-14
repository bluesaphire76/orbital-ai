from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable

from sqlalchemy.orm import Session

from backend.app.db.repositories.orbital_objects import (
    OrbitalObjectRepository,
)


@dataclass(frozen=True, slots=True)
class CatalogSyncResult:
    total: int
    created: int
    updated: int


def _parse_optional_date(
    value: Any,
) -> date | None:
    if value in (None, ""):
        return None

    if isinstance(value, date):
        return value

    return date.fromisoformat(str(value)[:10])


def build_orbital_object_values(
    record: dict[str, Any],
) -> tuple[int, dict[str, Any]]:
    raw_norad_cat_id = record.get("NORAD_CAT_ID")

    if raw_norad_cat_id in (None, ""):
        raise ValueError(
            "CelesTrak record is missing NORAD_CAT_ID"
        )

    norad_cat_id = int(raw_norad_cat_id)

    object_name = str(
        record.get("OBJECT_NAME")
        or f"NORAD {norad_cat_id}"
    )

    values = {
        "object_name": object_name,
        "object_id": record.get("OBJECT_ID"),
        "object_type": record.get("OBJECT_TYPE"),
        "country_code": record.get("COUNTRY_CODE"),
        "launch_date": _parse_optional_date(
            record.get("LAUNCH_DATE")
        ),
        "decay_date": _parse_optional_date(
            record.get("DECAY_DATE")
        ),
        "source": "celestrak",
    }

    return norad_cat_id, values


def sync_celestrak_records(
    session: Session,
    records: Iterable[dict[str, Any]],
) -> CatalogSyncResult:
    repository = OrbitalObjectRepository(session)

    total = 0
    created = 0
    updated = 0

    try:
        for record in records:
            norad_cat_id, values = (
                build_orbital_object_values(record)
            )

            _, was_created = repository.upsert(
                norad_cat_id=norad_cat_id,
                values=values,
            )

            total += 1

            if was_created:
                created += 1
            else:
                updated += 1

        session.commit()

    except Exception:
        session.rollback()
        raise

    return CatalogSyncResult(
        total=total,
        created=created,
        updated=updated,
    )
