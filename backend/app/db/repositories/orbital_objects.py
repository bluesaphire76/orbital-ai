from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models.orbital_object import OrbitalObject


class OrbitalObjectRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_norad_cat_id(
        self,
        norad_cat_id: int,
    ) -> OrbitalObject | None:
        statement = select(OrbitalObject).where(
            OrbitalObject.norad_cat_id == norad_cat_id
        )

        return self._session.scalar(statement)

    def list_by_norad_cat_ids(
        self,
        norad_cat_ids: list[int],
    ) -> list[OrbitalObject]:
        if not norad_cat_ids:
            return []

        statement = (
            select(OrbitalObject)
            .where(
                OrbitalObject.norad_cat_id.in_(
                    norad_cat_ids
                )
            )
        )

        return list(
            self._session.scalars(
                statement
            ).all()
        )


    def upsert(
        self,
        *,
        norad_cat_id: int,
        values: dict[str, Any],
    ) -> tuple[OrbitalObject, bool]:
        orbital_object = self.get_by_norad_cat_id(
            norad_cat_id
        )

        created = orbital_object is None

        if orbital_object is None:
            orbital_object = OrbitalObject(
                norad_cat_id=norad_cat_id,
                **values,
            )
            self._session.add(orbital_object)
        else:
            for field, value in values.items():
                setattr(
                    orbital_object,
                    field,
                    value,
                )

        self._session.flush()

        return orbital_object, created
