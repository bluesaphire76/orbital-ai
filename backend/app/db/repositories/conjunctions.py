from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from backend.app.db.models.conjunction import (
    ConjunctionEvent,
    ConjunctionRun,
)
from backend.app.db.models.orbital_object import OrbitalObject
from backend.app.db.models.orbital_element import OrbitalElement


class ConjunctionRepository:
    def __init__(
        self,
        session: Session,
    ) -> None:
        self._session = session

    def add_run(
        self,
        run: ConjunctionRun,
    ) -> ConjunctionRun:
        self._session.add(run)
        self._session.flush()

        return run

    def add_event(
        self,
        event: ConjunctionEvent,
    ) -> None:
        self._session.add(event)

    def get_latest_run(
        self,
    ) -> ConjunctionRun | None:
        statement = (
            select(ConjunctionRun)
            .order_by(
                ConjunctionRun.id.desc()
            )
            .limit(1)
        )

        return self._session.scalar(
            statement
        )

    def get_latest_run_for_source(
        self,
        source: str,
    ) -> ConjunctionRun | None:
        statement = (
            select(ConjunctionRun)
            .where(
                ConjunctionRun.source == source
            )
            .order_by(
                ConjunctionRun.completed_at.desc(),
                ConjunctionRun.id.desc(),
            )
            .limit(1)
        )

        return self._session.scalar(
            statement
        )

    def get_run(
        self,
        run_id: int,
    ) -> ConjunctionRun | None:
        return self._session.get(
            ConjunctionRun,
            run_id,
        )

    def list_events_with_objects(
        self,
        *,
        run_id: int,
        limit: int,
    ):
        primary = aliased(
            OrbitalObject
        )
        secondary = aliased(
            OrbitalObject
        )

        statement = (
            select(
                ConjunctionEvent,
                primary,
                secondary,
            )
            .join(
                primary,
                primary.id
                == ConjunctionEvent.primary_object_id,
            )
            .join(
                secondary,
                secondary.id
                == ConjunctionEvent.secondary_object_id,
            )
            .where(
                ConjunctionEvent.run_id
                == run_id
            )
            .order_by(
                ConjunctionEvent.miss_distance_km,
                ConjunctionEvent.tca,
            )
            .limit(limit)
        )

        return self._session.execute(
            statement
        ).all()

    def get_event_grounding(self, event_id: int):
        """Load an event and only the exact persisted records it references."""
        primary_object = aliased(OrbitalObject)
        secondary_object = aliased(OrbitalObject)
        primary_element = aliased(OrbitalElement)
        secondary_element = aliased(OrbitalElement)

        statement = (
            select(
                ConjunctionEvent,
                ConjunctionRun,
                primary_object,
                secondary_object,
                primary_element,
                secondary_element,
            )
            .outerjoin(ConjunctionRun, ConjunctionRun.id == ConjunctionEvent.run_id)
            .outerjoin(
                primary_object,
                primary_object.id == ConjunctionEvent.primary_object_id,
            )
            .outerjoin(
                secondary_object,
                secondary_object.id == ConjunctionEvent.secondary_object_id,
            )
            .outerjoin(
                primary_element,
                primary_element.id == ConjunctionEvent.primary_element_id,
            )
            .outerjoin(
                secondary_element,
                secondary_element.id == ConjunctionEvent.secondary_element_id,
            )
            .where(ConjunctionEvent.id == event_id)
        )
        return self._session.execute(statement).one_or_none()
