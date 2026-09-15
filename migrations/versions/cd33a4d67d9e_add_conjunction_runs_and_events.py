"""add conjunction runs and events

Revision ID: cd33a4d67d9e
Revises: 6ca119e8ff20
Create Date: 2026-09-15 07:53:54.750618

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cd33a4d67d9e'
down_revision: Union[str, Sequence[str], None] = '6ca119e8ff20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "conjunction_runs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("step_seconds", sa.Integer(), nullable=False),
        sa.Column("candidate_distance_km", sa.Float(), nullable=False),
        sa.Column("max_relative_speed_km_s", sa.Float(), nullable=False),
        sa.Column("objects", sa.Integer(), nullable=False),
        sa.Column("samples", sa.Integer(), nullable=False),
        sa.Column("propagation_attempts", sa.Integer(), nullable=False),
        sa.Column("propagation_failures", sa.Integer(), nullable=False),
        sa.Column("expired_skips", sa.Integer(), nullable=False),
        sa.Column("shared_solution_groups", sa.Integer(), nullable=False),
        sa.Column("shared_solution_objects", sa.Integer(), nullable=False),
        sa.Column("suppressed_shared_pairs", sa.Integer(), nullable=False),
        sa.Column("raw_candidates", sa.Integer(), nullable=False),
        sa.Column("unique_candidates", sa.Integer(), nullable=False),
        sa.Column("refinement_attempts", sa.Integer(), nullable=False),
        sa.Column("refinement_failures", sa.Integer(), nullable=False),
        sa.Column("event_count", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Float(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_conjunction_runs_window_start",
        "conjunction_runs",
        ["window_start"],
    )

    op.create_table(
        "conjunction_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.BigInteger(), nullable=False),
        sa.Column("primary_object_id", sa.BigInteger(), nullable=False),
        sa.Column("secondary_object_id", sa.BigInteger(), nullable=False),
        sa.Column("primary_element_id", sa.BigInteger(), nullable=False),
        sa.Column("secondary_element_id", sa.BigInteger(), nullable=False),
        sa.Column("tca", sa.DateTime(timezone=True), nullable=False),
        sa.Column("miss_distance_km", sa.Float(), nullable=False),
        sa.Column("relative_velocity_km_s", sa.Float(), nullable=False),
        sa.Column("method", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["conjunction_runs.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["primary_object_id"],
            ["orbital_objects.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["secondary_object_id"],
            ["orbital_objects.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["primary_element_id"],
            ["orbital_elements.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["secondary_element_id"],
            ["orbital_elements.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id",
            "primary_object_id",
            "secondary_object_id",
            name="uq_conjunction_event_run_pair",
        ),
    )

    op.create_index(
        "ix_conjunction_events_run_id",
        "conjunction_events",
        ["run_id"],
    )

    op.create_index(
        "ix_conjunction_events_tca",
        "conjunction_events",
        ["tca"],
    )

    op.create_index(
        "ix_conjunction_events_miss_distance_km",
        "conjunction_events",
        ["miss_distance_km"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_conjunction_events_miss_distance_km",
        table_name="conjunction_events",
    )
    op.drop_index(
        "ix_conjunction_events_tca",
        table_name="conjunction_events",
    )
    op.drop_index(
        "ix_conjunction_events_run_id",
        table_name="conjunction_events",
    )

    op.drop_table("conjunction_events")

    op.drop_index(
        "ix_conjunction_runs_window_start",
        table_name="conjunction_runs",
    )

    op.drop_table("conjunction_runs")
