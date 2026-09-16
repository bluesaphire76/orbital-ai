"""add earth orbit classification

Revision ID: a84f17c92b61
Revises: 9b7c4e21f3a1
Create Date: 2026-09-15

"""

from typing import (
    Sequence,
    Union,
)

from alembic import op
import sqlalchemy as sa


revision: str = "a84f17c92b61"

down_revision: Union[
    str,
    Sequence[str],
    None,
] = "9b7c4e21f3a1"

branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "orbital_objects",
        sa.Column(
            "is_earth_orbit",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    op.execute(
        """
        UPDATE orbital_objects
        SET is_earth_orbit = TRUE
        WHERE decay_date IS NULL
          AND orbit_center = 'EA'
          AND orbit_type = 'ORB'
        """
    )

    op.create_index(
        "ix_orbital_objects_is_earth_orbit",
        "orbital_objects",
        ["is_earth_orbit"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_orbital_objects_is_earth_orbit",
        table_name="orbital_objects",
    )

    op.drop_column(
        "orbital_objects",
        "is_earth_orbit",
    )
