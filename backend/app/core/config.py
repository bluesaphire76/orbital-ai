from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True, slots=True)
class Settings:
    environment: str
    log_level: str

    postgres_host: str
    postgres_port: int
    postgres_db: str
    postgres_user: str
    postgres_password: str

    @classmethod
    def from_env(cls) -> "Settings":
        password = os.getenv("POSTGRES_PASSWORD")

        if not password:
            raise RuntimeError("POSTGRES_PASSWORD is required")

        return cls(
            environment=os.getenv("ORBITAL_ENV", "development"),
            log_level=os.getenv("ORBITAL_LOG_LEVEL", "INFO"),
            postgres_host=os.getenv("POSTGRES_HOST", "postgres"),
            postgres_port=int(os.getenv("POSTGRES_PORT", "5432")),
            postgres_db=os.getenv("POSTGRES_DB", "orbitalai"),
            postgres_user=os.getenv("POSTGRES_USER", "orbitalai"),
            postgres_password=password,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings.from_env()
