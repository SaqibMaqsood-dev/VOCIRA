"""add language to users

Which language a guardian's voice calls run in ("en" / "ur"). It was
a single STT_LANGUAGE environment variable before, so the choice
applied to the whole deployment at once - every caller got the same
language, and changing it meant restarting the services.

NULL means "not chosen", which keeps falling back to that same
STT_LANGUAGE default, so existing accounts behave exactly as before.

Revision ID: b4c19ae7d301
Revises: 8bf38229660d
Create Date: 2026-09-27

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "b4c19ae7d301"
down_revision: Union[str, Sequence[str], None] = "8bf38229660d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("language", sa.VARCHAR(length=5), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "language")
