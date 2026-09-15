"""add propagation runs and states

Revision ID: 612a2242ec89
Revises: 0102b2bda35b
Create Date: 2026-09-15 01:03:30.576219

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '612a2242ec89'
down_revision: Union[str, Sequence[str], None] = '0102b2bda35b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "propagation_runs",
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "target_time",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "total_objects",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "successful",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "failed",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "duration_ms",
            sa.Float(),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_propagation_runs_target_time",
        "propagation_runs",
        ["target_time"],
    )

    op.create_table(
        "propagated_states",
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "run_id",
            sa.BigInteger(),
            nullable=False,
        ),
        sa.Column(
            "orbital_object_id",
            sa.BigInteger(),
            nullable=False,
        ),
        sa.Column(
            "orbital_element_id",
            sa.BigInteger(),
            nullable=False,
        ),
        sa.Column(
            "target_time",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "frame",
            sa.String(length=16),
            nullable=False,
        ),
        sa.Column(
            "success",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column("position_x_km", sa.Float()),
        sa.Column("position_y_km", sa.Float()),
        sa.Column("position_z_km", sa.Float()),
        sa.Column("velocity_x_km_s", sa.Float()),
        sa.Column("velocity_y_km_s", sa.Float()),
        sa.Column("velocity_z_km_s", sa.Float()),
        sa.Column(
            "error_type",
            sa.String(length=128),
        ),
        sa.Column(
            "error_message",
            sa.Text(),
        ),
        sa.Column(
            "duration_ms",
            sa.Float(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["orbital_element_id"],
            ["orbital_elements.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["orbital_object_id"],
            ["orbital_objects.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["propagation_runs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id",
            "orbital_object_id",
            name="uq_propagated_states_run_object",
        ),
    )

    op.create_index(
        "ix_propagated_states_run_id",
        "propagated_states",
        ["run_id"],
    )

    op.create_index(
        "ix_propagated_states_orbital_object_id",
        "propagated_states",
        ["orbital_object_id"],
    )

    op.create_index(
        "ix_propagated_states_target_time",
        "propagated_states",
        ["target_time"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_propagated_states_target_time",
        table_name="propagated_states",
    )
    op.drop_index(
        "ix_propagated_states_orbital_object_id",
        table_name="propagated_states",
    )
    op.drop_index(
        "ix_propagated_states_run_id",
        table_name="propagated_states",
    )
    op.drop_table("propagated_states")

    op.drop_index(
        "ix_propagation_runs_target_time",
        table_name="propagation_runs",
    )
    op.drop_table("propagation_runs")