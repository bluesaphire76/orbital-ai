from __future__ import annotations

from functools import lru_cache

from sqlalchemy import URL, create_engine, text
from sqlalchemy.engine import Engine

from backend.app.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()

    url = URL.create(
        drivername="postgresql+psycopg",
        username=settings.postgres_user,
        password=settings.postgres_password,
        host=settings.postgres_host,
        port=settings.postgres_port,
        database=settings.postgres_db,
    )

    return create_engine(
        url,
        pool_pre_ping=True,
    )


def database_is_ready() -> bool:
    with get_engine().connect() as connection:
        connection.execute(text("SELECT 1"))

    return True
