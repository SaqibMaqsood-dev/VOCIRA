"""remove user_roles table

Revision ID: cc0aeddec18d
Revises: 2796e6768b4f
Create Date: 2026-08-20 13:38:33.830988

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "cc0aeddec18d"
down_revision: Union[str, Sequence[str], None] = "2796e6768b4f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # Remove the old many-to-many user/role mapping table.
    op.drop_table("user_roles")

    # Remove the old role column.
    # Users now use users.role_id -> role.role_id.
    op.drop_column("users", "role")


def downgrade() -> None:
    """Downgrade schema."""

    # Recreate the old role column.
    op.add_column(
        "users",
        sa.Column(
            "role",
            postgresql.ENUM(
                "user",
                "guest",
                "admin",
                name="roles",
            ),
            nullable=False,
        ),
    )

    # Recreate the old user_roles table.
    op.create_table(
        "user_roles",
        sa.Column(
            "user_id",
            sa.VARCHAR(length=100),
            nullable=False,
        ),
        sa.Column(
            "role_id",
            sa.VARCHAR(length=100),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["role.role_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "user_id",
            "role_id",
        ),
    )