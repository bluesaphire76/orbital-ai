"""Persist chunk metrics and allow distinct encounters for one pair per run.

Revision ID: d28f6b91c4a7
Revises: a84f17c92b61
"""

from alembic import op
import sqlalchemy as sa


revision = "d28f6b91c4a7"
down_revision = "a84f17c92b61"
branch_labels = None
depends_on = None


CHUNK_DEFAULTS = {
    "chunk_count": "1",
    "chunk_seconds": "900",
    "duplicate_events_suppressed": "0",
    "max_chunk_raw_candidates": "0",
    "max_chunk_unique_candidates": "0",
    "max_chunk_refinement_attempts": "0",
}


def upgrade() -> None:
    for name, default in CHUNK_DEFAULTS.items():
        op.add_column(
            "conjunction_runs",
            sa.Column(name, sa.Integer(), nullable=False, server_default=default),
        )

    # Historical runs were monolithic. Represent their full window as one
    # chunk (rounded up to a full step), and backfill known maxima exactly.
    op.execute("""
        UPDATE conjunction_runs
        SET chunk_seconds = GREATEST(
                step_seconds,
                CEIL(EXTRACT(EPOCH FROM (window_end - window_start))
                     / step_seconds)::integer * step_seconds
            ),
            max_chunk_raw_candidates = raw_candidates,
            max_chunk_unique_candidates = unique_candidates,
            max_chunk_refinement_attempts = refinement_attempts
    """)

    op.create_unique_constraint(
        "uq_conjunction_event_run_pair_tca",
        "conjunction_events",
        ["run_id", "primary_object_id", "secondary_object_id", "tca"],
    )
    op.drop_constraint(
        "uq_conjunction_event_run_pair", "conjunction_events", type_="unique",
    )


def downgrade() -> None:
    # Restore the old constraint FIRST. PostgreSQL refuses the downgrade if
    # a run has multiple encounters for a pair; never delete scientific data
    # just to make an older schema fit. The migration remains transactional.
    op.create_unique_constraint(
        "uq_conjunction_event_run_pair",
        "conjunction_events",
        ["run_id", "primary_object_id", "secondary_object_id"],
    )
    op.drop_constraint(
        "uq_conjunction_event_run_pair_tca", "conjunction_events", type_="unique",
    )
    for name in reversed(CHUNK_DEFAULTS):
        op.drop_column("conjunction_runs", name)
