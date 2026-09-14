from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class PropagationRun(Base):
    __tablename__ = "propagation_runs"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    target_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    total_objects: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    successful: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    failed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    duration_ms: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )


class PropagatedState(Base):
    __tablename__ = "propagated_states"

    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "orbital_object_id",
            name="uq_propagated_states_run_object",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    run_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "propagation_runs.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
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

    orbital_element_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "orbital_elements.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    target_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    frame: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="TEME",
    )

    success: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )

    position_x_km: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    position_y_km: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    position_z_km: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    velocity_x_km_s: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    velocity_y_km_s: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    velocity_z_km_s: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    error_type: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    duration_ms: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    
    ephemeris_age_seconds: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    ephemeris_status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        index=True,
    )
