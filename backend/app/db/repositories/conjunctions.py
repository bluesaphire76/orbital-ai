from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from backend.app.db.models.conjunction import (
    ConjunctionEvent,
    ConjunctionRun,
)
from backend.app.db.models.orbital_object import OrbitalObject


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
