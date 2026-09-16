from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from backend.app.db.base import Base


class OrbitalObjectTag(Base):
    __tablename__ = "orbital_object_tags"

    __table_args__ = (
        UniqueConstraint(
            "orbital_object_id",
            "namespace",
            "tag",
            name="uq_orbital_object_tag",
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

    namespace: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    tag: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )

    source: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
