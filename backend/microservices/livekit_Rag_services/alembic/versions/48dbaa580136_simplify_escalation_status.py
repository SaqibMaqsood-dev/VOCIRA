"""simplify escalation status

Revision ID: 48dbaa580136
Revises: d6fa458a4f0e
Create Date: 2026-09-01 16:59:23.903154

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "48dbaa580136"
down_revision: Union[str, Sequence[str], None] = "d6fa458a4f0e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # Create the new enum with only the required values.
    new_enum = sa.Enum(
        "pending",
        "resolved",
        name="escalationstatus_new",
    )
    new_enum.create(bind)

    # Convert the existing column to the new enum.
    #
    # Existing rows currently contain only "pending",
    # which is also present in the new enum.
    op.execute(
        """
        ALTER TABLE escalations
        ALTER COLUMN status TYPE escalationstatus_new
        USING status::text::escalationstatus_new
        """
    )

    # Remove the old enum type.
    op.execute(
        "DROP TYPE escalationstatus"
    )

    # Rename the new enum to the original type name.
    op.execute(
        """
        ALTER TYPE escalationstatus_new
        RENAME TO escalationstatus
        """
    )


def downgrade() -> None:
    bind = op.get_bind()

    # Recreate the original enum.
    old_enum = sa.Enum(
        "pending",
        "open",
        "customer_waiting",
        "resolved",
        "closed",
        name="escalationstatus_old",
    )
    old_enum.create(bind)

    # Convert the column back to the original enum.
    op.execute(
        """
        ALTER TABLE escalations
        ALTER COLUMN status TYPE escalationstatus_old
        USING status::text::escalationstatus_old
        """
    )

    # Remove the current enum.
    op.execute(
        "DROP TYPE escalationstatus"
    )

    # Restore the original enum name.
    op.execute(
        """
        ALTER TYPE escalationstatus_old
        RENAME TO escalationstatus
        """
    )