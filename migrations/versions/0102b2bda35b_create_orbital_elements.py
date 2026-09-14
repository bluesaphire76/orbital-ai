"""create orbital elements

Revision ID: 0102b2bda35b
Revises: 4a9df0521eb8
Create Date: 2026-09-14 23:07:58.316352

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0102b2bda35b'
down_revision: Union[str, Sequence[str], None] = '4a9df0521eb8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "orbital_elements",
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "orbital_object_id",
            sa.BigInteger(),
            nullable=False,
        ),
        sa.Column(
            "source",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "epoch",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "element_set_no",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "ephemeris_type",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "inclination",
            sa.Float(),
            nullable=False,
        ),
        sa.Column(
            "ra_of_asc_node",
            sa.Float(),
            nullable=False,
        ),
        sa.Column(
            "eccentricity",
            sa.Float(),
            nullable=False,
        ),
        sa.Column(
            "arg_of_pericenter",
            sa.Float(),
            nullable=False,
        ),
        sa.Column(
            "mean_anomaly",
            sa.Float(),
            nullable=False,
        ),
        sa.Column(
            "mean_motion",
            sa.Float(),
            nullable=False,
        ),
        sa.Column(
            "mean_motion_dot",
            sa.Float(),
            nullable=True,
        ),
        sa.Column(
            "mean_motion_ddot",
            sa.Float(),
            nullable=True,
        ),
        sa.Column(
            "bstar",
            sa.Float(),
            nullable=True,
        ),
        sa.Column(
            "rev_at_epoch",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "raw_omm",
            postgresql.JSONB(),
            nullable=False,
        ),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["orbital_object_id"],
            ["orbital_objects.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "orbital_object_id",
            "source",
            "epoch",
            name="uq_orbital_elements_object_source_epoch",
        ),
    )

    op.create_index(
        "ix_orbital_elements_orbital_object_id",
        "orbital_elements",
        ["orbital_object_id"],
    )

    op.create_index(
        "ix_orbital_elements_epoch",
        "orbital_elements",
        ["epoch"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_orbital_elements_epoch",
        table_name="orbital_elements",
    )

    op.drop_index(
        "ix_orbital_elements_orbital_object_id",
        table_name="orbital_elements",
    )

    op.drop_table(
        "orbital_elements"
    )

