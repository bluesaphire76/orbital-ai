from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable

from sqlalchemy.orm import Session

from backend.app.db.repositories.orbital_objects import (
    OrbitalObjectRepository,
)
from backend.app.services.orbital_object_types import (
    normalize_object_type,
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

    values: dict[str, Any] = {
        "object_name": object_name,
        "source": "celestrak",
    }


    object_id = record.get(
        "OBJECT_ID"
    )

    if object_id not in (
        None,
        "",
    ):
        values[
            "object_id"
        ] = object_id


    object_type = record.get(
        "OBJECT_TYPE"
    )

    if object_type not in (
        None,
        "",
    ):
        values[
            "object_type"
        ] = normalize_object_type(
            object_type
        )


    country_code = record.get(
        "COUNTRY_CODE"
    )

    if country_code not in (
        None,
        "",
    ):
        values[
            "country_code"
        ] = country_code


    launch_date = record.get(
        "LAUNCH_DATE"
    )

    if launch_date not in (
        None,
        "",
    ):
        values[
            "launch_date"
        ] = _parse_optional_date(
            launch_date
        )


    decay_date = record.get(
        "DECAY_DATE"
    )

    if decay_date not in (
        None,
        "",
    ):
        values[
            "decay_date"
        ] = _parse_optional_date(
            decay_date
        )

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
