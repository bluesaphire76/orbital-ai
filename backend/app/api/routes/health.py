from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy.exc import SQLAlchemyError

from backend.app.db.engine import database_is_ready


router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "orbitalai-api",
    }


@router.get("/ready")
def readiness() -> dict[str, str]:
    try:
        database_is_ready()
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="database unavailable",
        ) from exc

    return {
        "status": "ready",
        "database": "ok",
    }
