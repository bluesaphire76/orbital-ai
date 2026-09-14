from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.db.models.orbital_element import OrbitalElement


class OrbitalElementRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_identity(
        self,
        *,
        orbital_object_id: int,
        source: str,
        epoch: datetime,
    ) -> OrbitalElement | None:
        statement = select(OrbitalElement).where(
            OrbitalElement.orbital_object_id == orbital_object_id,
            OrbitalElement.source == source,
            OrbitalElement.epoch == epoch,
        )

        return self._session.scalar(statement)

    def create_if_missing(
        self,
        *,
        orbital_object_id: int,
        values: dict[str, Any],
    ) -> tuple[OrbitalElement, bool]:
        source = str(values["source"])
        epoch = values["epoch"]

        existing = self.get_by_identity(
            orbital_object_id=orbital_object_id,
            source=source,
            epoch=epoch,
        )

        if existing is not None:
            return existing, False

        orbital_element = OrbitalElement(
            orbital_object_id=orbital_object_id,
            **values,
        )

        self._session.add(orbital_element)
        self._session.flush()

        return orbital_element, True

    def list_latest(
        self,
        *,
        source: str = "celestrak",
    ) -> list[OrbitalElement]:
        ranked = (
            select(
                OrbitalElement.id.label("element_id"),
                func.row_number()
                .over(
                    partition_by=OrbitalElement.orbital_object_id,
                    order_by=(
                        OrbitalElement.epoch.desc(),
                        OrbitalElement.id.desc(),
                    ),
                )
                .label("row_number"),
            )
            .where(
                OrbitalElement.source == source
            )
            .subquery()
        )

        statement = (
            select(OrbitalElement)
            .join(
                ranked,
                OrbitalElement.id
                == ranked.c.element_id,
            )
            .where(
                ranked.c.row_number == 1
            )
            .order_by(
                OrbitalElement.orbital_object_id
            )
        )

        return list(
            self._session.scalars(statement)
        )
