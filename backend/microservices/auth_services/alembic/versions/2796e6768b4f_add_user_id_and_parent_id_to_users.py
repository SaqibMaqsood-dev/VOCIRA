"""add user_id and parent_id to users

Revision ID: 2796e6768b4f
Revises: 7341d27773ec
Create Date: 2026-08-20 10:00:25.884709
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2796e6768b4f"
down_revision: Union[str, Sequence[str], None] = "7341d27773ec"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    # ---------------------------------------------------------
    # 1. Remove old foreign keys pointing to users.id
    # ---------------------------------------------------------

    op.drop_constraint(
        op.f("refresh_tokken_user_id_fkey"),
        "refresh_tokken",
        type_="foreignkey",
    )

    op.drop_constraint(
        op.f("user_roles_user_id_fkey"),
        "user_roles",
        type_="foreignkey",
    )

    # ---------------------------------------------------------
    # 2. Add new user_id column
    # ---------------------------------------------------------

    op.add_column(
        "users",
        sa.Column(
            "user_id",
            sa.VARCHAR(length=100),
            nullable=True,
        ),
    )

    # ---------------------------------------------------------
    # 3. Generate UUIDs for existing users
    # ---------------------------------------------------------

    op.execute(
        """
        UPDATE users
        SET user_id = gen_random_uuid()::text
        WHERE user_id IS NULL
        """
    )

    # ---------------------------------------------------------
    # 4. user_id cannot be NULL
    # ---------------------------------------------------------

    op.alter_column(
        "users",
        "user_id",
        existing_type=sa.VARCHAR(length=100),
        nullable=False,
    )

    # ---------------------------------------------------------
    # 5. Add parent_id
    # ---------------------------------------------------------

    op.add_column(
        "users",
        sa.Column(
            "parent_id",
            sa.VARCHAR(length=100),
            nullable=True,
        ),
    )

    # ---------------------------------------------------------
    # 6. Change primary key from id -> user_id
    # ---------------------------------------------------------

    op.drop_constraint(
        op.f("users_pkey"),
        "users",
        type_="primary",
    )

    op.create_primary_key(
        "users_pkey",
        "users",
        ["user_id"],
    )

    # ---------------------------------------------------------
    # 7. parent_id is unique
    # ---------------------------------------------------------

    op.create_unique_constraint(
        "uq_users_parent_id",
        "users",
        ["parent_id"],
    )

    # ---------------------------------------------------------
    # 8. Remove old id column
    # ---------------------------------------------------------

    op.drop_column(
        "users",
        "id",
    )

    # ---------------------------------------------------------
    # 9. Re-create foreign keys using users.user_id
    # ---------------------------------------------------------

    op.create_foreign_key(
        "refresh_tokken_user_id_fkey",
        "refresh_tokken",
        "users",
        ["user_id"],
        ["user_id"],
    )

    op.create_foreign_key(
        "user_roles_user_id_fkey",
        "user_roles",
        "users",
        ["user_id"],
        ["user_id"],
    )


def downgrade() -> None:

    # ---------------------------------------------------------
    # 1. Remove new foreign keys
    # ---------------------------------------------------------

    op.drop_constraint(
        "refresh_tokken_user_id_fkey",
        "refresh_tokken",
        type_="foreignkey",
    )

    op.drop_constraint(
        "user_roles_user_id_fkey",
        "user_roles",
        type_="foreignkey",
    )

    # ---------------------------------------------------------
    # 2. Add old id column
    # ---------------------------------------------------------

    op.add_column(
        "users",
        sa.Column(
            "id",
            sa.VARCHAR(length=100),
            nullable=True,
        ),
    )

    # Copy user_id back to id
    op.execute(
        """
        UPDATE users
        SET id = user_id
        """
    )

    # ---------------------------------------------------------
    # 3. Change primary key back to id
    # ---------------------------------------------------------

    op.drop_constraint(
        "users_pkey",
        "users",
        type_="primary",
    )

    op.create_primary_key(
        "users_pkey",
        "users",
        ["id"],
    )

    # ---------------------------------------------------------
    # 4. Remove parent_id
    # ---------------------------------------------------------

    op.drop_constraint(
        "uq_users_parent_id",
        "users",
        type_="unique",
    )

    op.drop_column(
        "users",
        "parent_id",
    )

    # ---------------------------------------------------------
    # 5. Remove user_id
    # ---------------------------------------------------------

    op.drop_column(
        "users",
        "user_id",
    )

    # ---------------------------------------------------------
    # 6. Re-create old foreign keys
    # ---------------------------------------------------------

    op.create_foreign_key(
        "refresh_tokken_user_id_fkey",
        "refresh_tokken",
        "users",
        ["user_id"],
        ["id"],
    )

    op.create_foreign_key(
        "user_roles_user_id_fkey",
        "user_roles",
        "users",
        ["user_id"],
        ["id"],
    )