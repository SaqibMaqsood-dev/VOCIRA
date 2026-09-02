"""simplify escalation status

Revision ID: 750ea832be39
Revises: 48dbaa580136
Create Date: 2026-09-01 17:24:21.033155

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '750ea832be39'
down_revision: Union[str, Sequence[str], None] = '48dbaa580136'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
