"""create orbital objects

Revision ID: 4a9df0521eb8
Revises: 
Create Date: 2026-09-14 22:37:08.690270

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4a9df0521eb8'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "orbital_objects",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("norad_cat_id", sa.BigInteger(), nullable=False),
        sa.Column("object_name", sa.String(length=255), nullable=False),
        sa.Column("object_id", sa.String(length=32), nullable=True),
        sa.Column("object_type", sa.String(length=64), nullable=True),
        sa.Column("country_code", sa.String(length=16), nullable=True),
        sa.Column("launch_date", sa.Date(), nullable=True),
        sa.Column("decay_date", sa.Date(), nullable=True),
        sa.Column(
            "source",
            sa.String(length=64),
            nullable=False,
            server_default="celestrak",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("norad_cat_id"),
    )

    op.create_index(
        "ix_orbital_objects_norad_cat_id",
        "orbital_objects",
        ["norad_cat_id"],
    )
    op.create_index(
        "ix_orbital_objects_object_name",
        "orbital_objects",
        ["object_name"],
    )
    op.create_index(
        "ix_orbital_objects_object_id",
        "orbital_objects",
        ["object_id"],
    )
    op.create_index(
        "ix_orbital_objects_object_type",
        "orbital_objects",
        ["object_type"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_orbital_objects_object_type",
        table_name="orbital_objects",
    )
    op.drop_index(
        "ix_orbital_objects_object_id",
        table_name="orbital_objects",
    )
    op.drop_index(
        "ix_orbital_objects_object_name",
        table_name="orbital_objects",
    )
    op.drop_index(
        "ix_orbital_objects_norad_cat_id",
        table_name="orbital_objects",
    )
    op.drop_table("orbital_objects")
