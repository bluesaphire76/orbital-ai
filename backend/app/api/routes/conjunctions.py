from __future__ import annotations

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
from backend.app.db.repositories.conjunctions import (
    ConjunctionRepository,
)
from backend.app.schemas.conjunctions import (
    ConjunctionEventRead,
    ConjunctionRunRead,
)


router = APIRouter(
    prefix="/conjunctions",
    tags=["conjunctions"],
)


@router.get(
    "/runs/latest",
    response_model=ConjunctionRunRead,
)
def get_latest_run(
    session: Session = Depends(
        get_db_session
    ),
) -> ConjunctionRunRead:
    repository = ConjunctionRepository(
        session
    )

    run = repository.get_latest_run()

    if run is None:
        raise HTTPException(
            status_code=404,
            detail="No conjunction runs found",
        )

    return ConjunctionRunRead.model_validate(
        run
    )


@router.get(
    "/runs/{run_id}/events",
    response_model=list[
        ConjunctionEventRead
    ],
)
def list_run_events(
    run_id: int,
    limit: int = Query(
        default=100,
        ge=1,
        le=1000,
    ),
    session: Session = Depends(
        get_db_session
    ),
) -> list[ConjunctionEventRead]:
    repository = ConjunctionRepository(
        session
    )

    run = repository.get_run(
        run_id
    )

    if run is None:
        raise HTTPException(
            status_code=404,
            detail="Conjunction run not found",
        )

    rows = (
        repository.list_events_with_objects(
            run_id=run_id,
            limit=limit,
        )
    )

    return [
        ConjunctionEventRead(
            id=event.id,
            run_id=event.run_id,
            primary_object_id=(
                primary.id
            ),
            primary_element_id=(
                event.primary_element_id
            ),
            primary_norad_cat_id=(
                primary.norad_cat_id
            ),
            primary_name=(
                primary.object_name
            ),
            secondary_object_id=(
                secondary.id
            ),
            secondary_element_id=(
                event.secondary_element_id
            ),
            secondary_norad_cat_id=(
                secondary.norad_cat_id
            ),
            secondary_name=(
                secondary.object_name
            ),
            tca=event.tca,
            miss_distance_km=(
                event.miss_distance_km
            ),
            relative_velocity_km_s=(
                event.relative_velocity_km_s
            ),
            method=event.method,
        )
        for (
            event,
            primary,
            secondary,
        ) in rows
    ]
