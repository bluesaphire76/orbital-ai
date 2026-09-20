from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status

from backend.app.schemas.catalog_sync import CatalogSyncStatusRead
from backend.app.services.catalog_sync_config import CatalogSyncConfig
from backend.app.services.catalog_sync_orchestrator import (
    read_catalog_sync_state,
)
from backend.app.services.catalog_sync_status import (
    catalog_sync_intervals,
    evaluate_catalog_sync_freshness,
    normalize_catalog_sync_state,
)


STATUS_UNAVAILABLE = "Catalog sync status is temporarily unavailable"

router = APIRouter(
    prefix="/catalog",
    tags=["catalog"],
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@router.get(
    "/sync-status",
    response_model=CatalogSyncStatusRead,
    status_code=status.HTTP_200_OK,
    summary="Get catalog synchronization status",
    description=(
        "Return a read-only normalized snapshot of automated catalog and "
        "ephemeris synchronization state."
    ),
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Catalog synchronization status is unavailable",
            "content": {
                "application/json": {
                    "example": {
                        "detail": STATUS_UNAVAILABLE,
                    }
                }
            },
        }
    },
)
def get_catalog_sync_status() -> CatalogSyncStatusRead:
    try:
        state = read_catalog_sync_state()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=STATUS_UNAVAILABLE,
        ) from exc

    normalized = normalize_catalog_sync_state(state)
    config = CatalogSyncConfig.from_env()
    return CatalogSyncStatusRead.model_validate(
        evaluate_catalog_sync_freshness(
            normalized,
            intervals=catalog_sync_intervals(config),
            now=_utc_now(),
        )
    )
