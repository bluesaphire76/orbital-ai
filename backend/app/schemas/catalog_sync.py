from __future__ import annotations

from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeFloat,
    PositiveInt,
)

from backend.app.services.catalog_sync_status import (
    CatalogSyncFreshness,
    CatalogSyncPublicStatus,
)


class CatalogSyncSourceStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    running: bool
    status: CatalogSyncPublicStatus
    last_started_at: datetime | None
    last_completed_at: datetime | None
    last_success_at: datetime | None
    last_duration_seconds: float | None
    last_records: int | None
    last_from_cache: bool | None
    consecutive_failures: int
    next_retry_at: datetime | None
    freshness: CatalogSyncFreshness
    last_success_age_seconds: NonNegativeFloat | None
    freshness_warning_seconds: PositiveInt
    freshness_stale_seconds: PositiveInt


class CatalogSyncSources(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )

    satcat: CatalogSyncSourceStatus
    celestrak: CatalogSyncSourceStatus
    space_track: CatalogSyncSourceStatus = Field(alias="space-track")


class CatalogSyncStatusRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    updated_at: datetime | None
    overall_freshness: CatalogSyncFreshness
    sources: CatalogSyncSources
