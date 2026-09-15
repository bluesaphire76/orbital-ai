"""add ephemeris quality to propagated states

Revision ID: 6ca119e8ff20
Revises: 612a2242ec89
Create Date: 2026-09-15 01:22:36.363712

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6ca119e8ff20'
down_revision: Union[str, Sequence[str], None] = '612a2242ec89'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "propagated_states",
        sa.Column(
            "ephemeris_age_seconds",
            sa.Float(),
            nullable=True,
        ),
    )

    op.add_column(
        "propagated_states",
        sa.Column(
            "ephemeris_status",
            sa.String(length=16),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_propagated_states_ephemeris_status",
        "propagated_states",
        ["ephemeris_status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_propagated_states_ephemeris_status",
        table_name="propagated_states",
    )

    op.drop_column(
        "propagated_states",
        "ephemeris_status",
    )

    op.drop_column(
        "propagated_states",
        "ephemeris_age_seconds",
    )
