from __future__ import annotations

from datetime import (
    date,
    datetime,
)

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    String,
    func,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from backend.app.db.base import Base


class OrbitalObject(Base):
    __tablename__ = "orbital_objects"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    norad_cat_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        nullable=False,
        index=True,
    )

    object_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    object_id: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        index=True,
    )

    object_type: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )

    ops_status_code: Mapped[str | None] = mapped_column(
        String(16),
        nullable=True,
        index=True,
    )

    owner: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        index=True,
    )

    country_code: Mapped[str | None] = mapped_column(
        String(16),
        nullable=True,
    )

    launch_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    launch_site: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )

    decay_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        index=True,
    )

    period_minutes: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    inclination_deg: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    apogee_km: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    perigee_km: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    rcs_m2: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    data_status_code: Mapped[str | None] = mapped_column(
        String(16),
        nullable=True,
        index=True,
    )

    orbit_center: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )

    orbit_type: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        index=True,
    )

    is_on_orbit: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
    )

    is_earth_orbit: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
    )

    has_current_elements: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
    )

    source: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="celestrak",
    )

    catalog_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
