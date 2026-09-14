from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from backend.app.db.models.propagation import (
    PropagatedState,
    PropagationRun,
)


class PropagationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_run(
        self,
        *,
        target_time: datetime,
    ) -> PropagationRun:
        run = PropagationRun(
            target_time=target_time,
        )

        self._session.add(run)
        self._session.flush()

        return run

    def add_state(
        self,
        state: PropagatedState,
    ) -> None:
        self._session.add(state)

    def complete_run(
        self,
        run: PropagationRun,
        *,
        completed_at: datetime,
        total_objects: int,
        successful: int,
        failed: int,
        duration_ms: float,
    ) -> None:
        run.completed_at = completed_at
        run.total_objects = total_objects
        run.successful = successful
        run.failed = failed
        run.duration_ms = duration_ms

        self._session.flush()
