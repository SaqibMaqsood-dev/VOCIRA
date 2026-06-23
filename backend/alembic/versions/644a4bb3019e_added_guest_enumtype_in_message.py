"""added guest enumtype in message 

Revision ID: 644a4bb3019e
Revises: e8bcb5582c06
Create Date: 2026-06-21 16:29:26.524731

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '644a4bb3019e'
down_revision: Union[str, Sequence[str], None] = 'e8bcb5582c06'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 💡 PostgreSQL requires 'ALTER TYPE ... ADD VALUE' to update enums without rebuilding tables.
    # 'execute' runs raw SQL directly on your database connection.
    op.execute("ALTER TYPE sendertypeenum ADD VALUE 'guest';")


def downgrade() -> None:
    """Downgrade schema."""
    # ⚠️ WARNING: PostgreSQL does not natively support dropping a value from an Enum type.
    # If you need to roll back, it requires dropping columns and recreations, so we pass.
    pass