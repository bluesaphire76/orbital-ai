from __future__ import annotations

from fastapi import APIRouter, HTTPException
from prometheus_client import Gauge
from sqlalchemy.exc import SQLAlchemyError
from time import time

from backend.app.db.engine import database_is_ready


router = APIRouter(tags=["system"])

DATABASE_READY = Gauge("orbitalai_database_ready", "Result of the existing PostgreSQL readiness probe; NaN until checked")
DATABASE_READY.set(float("nan"))
DATABASE_CHECKED = Gauge("orbitalai_database_last_check_timestamp_seconds", "Last PostgreSQL readiness probe timestamp")


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
        DATABASE_READY.set(0)
        raise HTTPException(
            status_code=503,
            detail="database unavailable",
        ) from exc
    else:
        DATABASE_READY.set(1)
    finally:
        DATABASE_CHECKED.set(time())

    return {
        "status": "ready",
        "database": "ok",
    }
