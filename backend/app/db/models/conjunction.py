from __future__ import annotations

from datetime import datetime

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
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class ConjunctionRun(Base):
    __tablename__ = "conjunction_runs"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    source: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    window_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    window_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    step_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    candidate_distance_km: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    max_relative_speed_km_s: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    objects: Mapped[int] = mapped_column(Integer, nullable=False)
    samples: Mapped[int] = mapped_column(Integer, nullable=False)

    propagation_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    propagation_failures: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    expired_skips: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    shared_solution_groups: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    shared_solution_objects: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    suppressed_shared_pairs: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    raw_candidates: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    unique_candidates: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    refinement_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    refinement_failures: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    event_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    duration_ms: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ConjunctionEvent(Base):
    __tablename__ = "conjunction_events"

    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "primary_object_id",
            "secondary_object_id",
            name="uq_conjunction_event_run_pair",
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
            "conjunction_runs.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    primary_object_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "orbital_objects.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    secondary_object_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "orbital_objects.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    primary_element_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "orbital_elements.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    secondary_element_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "orbital_elements.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    tca: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    miss_distance_km: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        index=True,
    )

    relative_velocity_km_s: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    method: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
