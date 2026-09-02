"""add handler to sessions

Revision ID: d6fa458a4f0e
Revises: 911a3a171c5a
Create Date: 2026-08-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d6fa458a4f0e"
down_revision: Union[str, Sequence[str], None] = "911a3a171c5a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add handler column to sessions."""

    op.add_column(
        "sessions",
        sa.Column(
            "handler",
            sa.Enum(
                "ai",
                "admin",
                name="sessionhandler",
            ),
            server_default="ai",
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Remove handler column from sessions."""

    op.drop_column(
        "sessions",
        "handler",
    )

    op.execute(
        "DROP TYPE IF EXISTS sessionhandler"
    )