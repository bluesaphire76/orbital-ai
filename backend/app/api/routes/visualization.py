from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
)
from sqlalchemy.orm import Session

from backend.app.api.dependencies import (
    get_db_session,
)
from backend.app.schemas.visualization import (
    ObjectTrajectory,
    VisualizationPlayback,
    VisualizationSnapshot,
)
from backend.app.services.visualization import (
    VisualizationEphemerisExpired,
    VisualizationObjectNotFound,
    build_object_trajectory,
    build_visualization_snapshot,
)
from backend.app.services.visualization_playback import (
    build_visualization_playback,
)


router = APIRouter(
    prefix="/visualization",
    tags=["visualization"],
)


@router.get(
    "/snapshot",
    response_model=VisualizationSnapshot,
)
def get_snapshot(
    at: datetime | None = Query(
        default=None
    ),
    session: Session = Depends(
        get_db_session
    ),
) -> VisualizationSnapshot:
    target_time = (
        at
        if at is not None
        else datetime.now(
            timezone.utc
        )
    )

    try:
        return build_visualization_snapshot(
            session,
            when=target_time,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc


@router.get(
    "/objects/{object_id}/trajectory",
    response_model=ObjectTrajectory,
)
def get_trajectory(
    object_id: int,
    start: datetime,
    end: datetime,
    step_seconds: int = Query(
        default=60,
        ge=10,
        le=3600,
    ),
    session: Session = Depends(
        get_db_session
    ),
) -> ObjectTrajectory:
    try:
        return build_object_trajectory(
            session,
            object_id=object_id,
            start=start,
            end=end,
            step_seconds=step_seconds,
        )

    except VisualizationObjectNotFound as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except VisualizationEphemerisExpired as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc


@router.get(
    "/playback",
    response_model=VisualizationPlayback,
)
def get_playback(
    start: datetime,
    end: datetime,
    step_seconds: int = Query(
        default=60,
        ge=10,
        le=3600,
    ),
    session: Session = Depends(
        get_db_session
    ),
) -> VisualizationPlayback:
    try:
        return build_visualization_playback(
            session,
            start=start,
            end=end,
            step_seconds=step_seconds,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc
