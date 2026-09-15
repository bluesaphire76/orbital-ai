from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

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

    country_code: Mapped[str | None] = mapped_column(
        String(16),
        nullable=True,
    )

    launch_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    decay_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    source: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="celestrak",
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
