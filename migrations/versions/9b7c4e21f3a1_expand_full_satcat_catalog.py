"""expand full satcat catalog

Revision ID: 9b7c4e21f3a1
Revises: cd33a4d67d9e
Create Date: 2026-09-15

"""

from typing import (
    Sequence,
    Union,
)

from alembic import op
import sqlalchemy as sa


revision: str = "9b7c4e21f3a1"

down_revision: Union[
    str,
    Sequence[str],
    None,
] = "cd33a4d67d9e"

branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "orbital_objects",
        sa.Column(
            "ops_status_code",
            sa.String(16),
            nullable=True,
        ),
    )

    op.add_column(
        "orbital_objects",
        sa.Column(
            "owner",
            sa.String(32),
            nullable=True,
        ),
    )

    op.add_column(
        "orbital_objects",
        sa.Column(
            "launch_site",
            sa.String(32),
            nullable=True,
        ),
    )

    op.add_column(
        "orbital_objects",
        sa.Column(
            "period_minutes",
            sa.Float(),
            nullable=True,
        ),
    )

    op.add_column(
        "orbital_objects",
        sa.Column(
            "inclination_deg",
            sa.Float(),
            nullable=True,
        ),
    )

    op.add_column(
        "orbital_objects",
        sa.Column(
            "apogee_km",
            sa.Float(),
            nullable=True,
        ),
    )

    op.add_column(
        "orbital_objects",
        sa.Column(
            "perigee_km",
            sa.Float(),
            nullable=True,
        ),
    )

    op.add_column(
        "orbital_objects",
        sa.Column(
            "rcs_m2",
            sa.Float(),
            nullable=True,
        ),
    )

    op.add_column(
        "orbital_objects",
        sa.Column(
            "data_status_code",
            sa.String(16),
            nullable=True,
        ),
    )

    op.add_column(
        "orbital_objects",
        sa.Column(
            "orbit_center",
            sa.String(32),
            nullable=True,
        ),
    )

    op.add_column(
        "orbital_objects",
        sa.Column(
            "orbit_type",
            sa.String(32),
            nullable=True,
        ),
    )

    op.add_column(
        "orbital_objects",
        sa.Column(
            "is_on_orbit",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )

    op.add_column(
        "orbital_objects",
        sa.Column(
            "has_current_elements",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    op.add_column(
        "orbital_objects",
        sa.Column(
            "catalog_updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_orbital_objects_ops_status_code",
        "orbital_objects",
        ["ops_status_code"],
    )

    op.create_index(
        "ix_orbital_objects_owner",
        "orbital_objects",
        ["owner"],
    )

    op.create_index(
        "ix_orbital_objects_decay_date",
        "orbital_objects",
        ["decay_date"],
    )

    op.create_index(
        "ix_orbital_objects_data_status_code",
        "orbital_objects",
        ["data_status_code"],
    )

    op.create_index(
        "ix_orbital_objects_orbit_type",
        "orbital_objects",
        ["orbit_type"],
    )

    op.create_index(
        "ix_orbital_objects_is_on_orbit",
        "orbital_objects",
        ["is_on_orbit"],
    )

    op.create_index(
        "ix_orbital_objects_has_current_elements",
        "orbital_objects",
        ["has_current_elements"],
    )


    op.execute(
        """
        UPDATE orbital_objects AS o
        SET has_current_elements = TRUE
        WHERE EXISTS (
            SELECT 1
            FROM orbital_elements AS e
            WHERE e.orbital_object_id = o.id
        )
        """
    )


    op.create_table(
        "orbital_object_tags",

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
            "namespace",
            sa.String(64),
            nullable=False,
        ),

        sa.Column(
            "tag",
            sa.String(128),
            nullable=False,
        ),

        sa.Column(
            "source",
            sa.String(64),
            nullable=False,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),

        sa.ForeignKeyConstraint(
            ["orbital_object_id"],
            ["orbital_objects.id"],
            ondelete="CASCADE",
        ),

        sa.PrimaryKeyConstraint(
            "id",
        ),

        sa.UniqueConstraint(
            "orbital_object_id",
            "namespace",
            "tag",
            name="uq_orbital_object_tag",
        ),
    )

    op.create_index(
        "ix_orbital_object_tags_object",
        "orbital_object_tags",
        ["orbital_object_id"],
    )

    op.create_index(
        "ix_orbital_object_tags_namespace",
        "orbital_object_tags",
        ["namespace"],
    )

    op.create_index(
        "ix_orbital_object_tags_tag",
        "orbital_object_tags",
        ["tag"],
    )


def downgrade() -> None:
    op.drop_table(
        "orbital_object_tags"
    )

    for index in (
        "ix_orbital_objects_has_current_elements",
        "ix_orbital_objects_is_on_orbit",
        "ix_orbital_objects_orbit_type",
        "ix_orbital_objects_data_status_code",
        "ix_orbital_objects_decay_date",
        "ix_orbital_objects_owner",
        "ix_orbital_objects_ops_status_code",
    ):
        op.drop_index(
            index,
            table_name="orbital_objects",
        )

    for column in (
        "catalog_updated_at",
        "has_current_elements",
        "is_on_orbit",
        "orbit_type",
        "orbit_center",
        "data_status_code",
        "rcs_m2",
        "perigee_km",
        "apogee_km",
        "inclination_deg",
        "period_minutes",
        "launch_site",
        "owner",
        "ops_status_code",
    ):
        op.drop_column(
            "orbital_objects",
            column,
        )
