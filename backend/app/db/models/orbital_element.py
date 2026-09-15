from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base


class OrbitalElement(Base):
    __tablename__ = "orbital_elements"

    __table_args__ = (
        UniqueConstraint(
            "orbital_object_id",
            "source",
            "epoch",
            name="uq_orbital_elements_object_source_epoch",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    orbital_object_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "orbital_objects.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    source: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="celestrak",
    )

    epoch: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    element_set_no: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    ephemeris_type: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    inclination: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    ra_of_asc_node: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    eccentricity: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    arg_of_pericenter: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    mean_anomaly: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    mean_motion: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    mean_motion_dot: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    mean_motion_ddot: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    bstar: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    rev_at_epoch: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    raw_omm: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )

    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
