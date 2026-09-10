"""change user id to varchar in all table and user enum to parent enum

Revision ID: 7341d27773ec
Revises: 1db24eaa07b3
Create Date: 2026-08-20 02:40:38.690668
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7341d27773ec"
down_revision: Union[str, Sequence[str], None] = "1db24eaa07b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Convert UUID-based IDs to VARCHAR while preserving relationships.
    """

    # ============================================================
    # 1. Drop FOREIGN KEYS first
    # ============================================================

    # refresh_tokken.user_id -> users.id
    op.drop_constraint(
        "refresh_tokken_user_id_fkey",
        "refresh_tokken",
        type_="foreignkey",
    )

    # users.role_id -> role.role_id
    op.drop_constraint(
        "users_role_id_fkey",
        "users",
        type_="foreignkey",
    )

    # user_roles.role_id -> role.role_id
    op.drop_constraint(
        "user_roles_role_id_fkey",
        "user_roles",
        type_="foreignkey",
    )

    # user_roles.user_id -> users.id
    op.drop_constraint(
        "user_roles_user_id_fkey",
        "user_roles",
        type_="foreignkey",
    )

    # role_permissions.role_id -> role.role_id
    op.drop_constraint(
        "role_permissions_role_id_fkey",
        "role_permissions",
        type_="foreignkey",
    )

    # role_permissions.permission_id -> permissions.permission_id
    op.drop_constraint(
        "role_permissions_permission_id_fkey",
        "role_permissions",
        type_="foreignkey",
    )


    # ============================================================
    # 2. Remove old ERP guardian mapping table
    # ============================================================

    op.drop_index(
        op.f("ix_erp_guardian_mappings_erp_guardian_id"),
        table_name="erp_guardian_mappings",
    )

    op.drop_index(
        op.f("ix_erp_guardian_mappings_vocira_user_id"),
        table_name="erp_guardian_mappings",
    )

    op.drop_table("erp_guardian_mappings")


    # ============================================================
    # 3. Change CHILD columns first
    # ============================================================

    # refresh_tokken.user_id
    op.alter_column(
        "refresh_tokken",
        "user_id",
        existing_type=sa.UUID(),
        type_=sa.VARCHAR(length=100),
        existing_nullable=False,
        postgresql_using="user_id::text",
    )

    # users.role_id
    op.alter_column(
        "users",
        "role_id",
        existing_type=sa.UUID(),
        type_=sa.VARCHAR(),
        existing_nullable=False,
        postgresql_using="role_id::text",
    )

    # user_roles.user_id
    op.alter_column(
        "user_roles",
        "user_id",
        existing_type=sa.UUID(),
        type_=sa.VARCHAR(length=100),
        existing_nullable=False,
        postgresql_using="user_id::text",
    )

    # user_roles.role_id
    op.alter_column(
        "user_roles",
        "role_id",
        existing_type=sa.UUID(),
        type_=sa.VARCHAR(),
        existing_nullable=False,
        postgresql_using="role_id::text",
    )

    # role_permissions.role_id
    op.alter_column(
        "role_permissions",
        "role_id",
        existing_type=sa.UUID(),
        type_=sa.VARCHAR(),
        existing_nullable=False,
        postgresql_using="role_id::text",
    )

    # role_permissions.permission_id
    op.alter_column(
        "role_permissions",
        "permission_id",
        existing_type=sa.UUID(),
        type_=sa.VARCHAR(),
        existing_nullable=False,
        postgresql_using="permission_id::text",
    )


    # ============================================================
    # 4. Change PARENT columns
    # ============================================================

    # permissions.permission_id
    op.alter_column(
        "permissions",
        "permission_id",
        existing_type=sa.UUID(),
        type_=sa.VARCHAR(),
        existing_nullable=False,
        postgresql_using="permission_id::text",
    )

    # role.role_id
    op.alter_column(
        "role",
        "role_id",
        existing_type=sa.UUID(),
        type_=sa.VARCHAR(),
        existing_nullable=False,
        postgresql_using="role_id::text",
    )

    # users.id
    op.alter_column(
        "users",
        "id",
        existing_type=sa.UUID(),
        type_=sa.VARCHAR(length=100),
        existing_nullable=False,
        postgresql_using="id::text",
    )


    # ============================================================
    # 5. Re-create FOREIGN KEYS
    # ============================================================

    # refresh_tokken.user_id -> users.id
    op.create_foreign_key(
        "refresh_tokken_user_id_fkey",
        "refresh_tokken",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # users.role_id -> role.role_id
    op.create_foreign_key(
        "users_role_id_fkey",
        "users",
        "role",
        ["role_id"],
        ["role_id"],
    )

    # user_roles.role_id -> role.role_id
    op.create_foreign_key(
        "user_roles_role_id_fkey",
        "user_roles",
        "role",
        ["role_id"],
        ["role_id"],
        ondelete="CASCADE",
    )

    # user_roles.user_id -> users.id
    op.create_foreign_key(
        "user_roles_user_id_fkey",
        "user_roles",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # role_permissions.role_id -> role.role_id
    op.create_foreign_key(
        "role_permissions_role_id_fkey",
        "role_permissions",
        "role",
        ["role_id"],
        ["role_id"],
        ondelete="CASCADE",
    )

    # role_permissions.permission_id -> permissions.permission_id
    op.create_foreign_key(
        "role_permissions_permission_id_fkey",
        "role_permissions",
        "permissions",
        ["permission_id"],
        ["permission_id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    """
    Reverse UUID -> VARCHAR conversion.
    """

    # ============================================================
    # 1. Drop foreign keys
    # ============================================================

    op.drop_constraint(
        "refresh_tokken_user_id_fkey",
        "refresh_tokken",
        type_="foreignkey",
    )

    op.drop_constraint(
        "users_role_id_fkey",
        "users",
        type_="foreignkey",
    )

    op.drop_constraint(
        "user_roles_role_id_fkey",
        "user_roles",
        type_="foreignkey",
    )

    op.drop_constraint(
        "user_roles_user_id_fkey",
        "user_roles",
        type_="foreignkey",
    )

    op.drop_constraint(
        "role_permissions_role_id_fkey",
        "role_permissions",
        type_="foreignkey",
    )

    op.drop_constraint(
        "role_permissions_permission_id_fkey",
        "role_permissions",
        type_="foreignkey",
    )


    # ============================================================
    # 2. Convert CHILD columns back to UUID
    # ============================================================

    op.alter_column(
        "refresh_tokken",
        "user_id",
        existing_type=sa.VARCHAR(length=100),
        type_=sa.UUID(),
        existing_nullable=False,
        postgresql_using="user_id::uuid",
    )

    op.alter_column(
        "users",
        "role_id",
        existing_type=sa.VARCHAR(),
        type_=sa.UUID(),
        existing_nullable=False,
        postgresql_using="role_id::uuid",
    )

    op.alter_column(
        "user_roles",
        "user_id",
        existing_type=sa.VARCHAR(length=100),
        type_=sa.UUID(),
        existing_nullable=False,
        postgresql_using="user_id::uuid",
    )

    op.alter_column(
        "user_roles",
        "role_id",
        existing_type=sa.VARCHAR(),
        type_=sa.UUID(),
        existing_nullable=False,
        postgresql_using="role_id::uuid",
    )

    op.alter_column(
        "role_permissions",
        "role_id",
        existing_type=sa.VARCHAR(),
        type_=sa.UUID(),
        existing_nullable=False,
        postgresql_using="role_id::uuid",
    )

    op.alter_column(
        "role_permissions",
        "permission_id",
        existing_type=sa.VARCHAR(),
        type_=sa.UUID(),
        existing_nullable=False,
        postgresql_using="permission_id::uuid",
    )


    # ============================================================
    # 3. Convert PARENT columns back to UUID
    # ============================================================

    op.alter_column(
        "permissions",
        "permission_id",
        existing_type=sa.VARCHAR(),
        type_=sa.UUID(),
        existing_nullable=False,
        postgresql_using="permission_id::uuid",
    )

    op.alter_column(
        "role",
        "role_id",
        existing_type=sa.VARCHAR(),
        type_=sa.UUID(),
        existing_nullable=False,
        postgresql_using="role_id::uuid",
    )

    op.alter_column(
        "users",
        "id",
        existing_type=sa.VARCHAR(length=100),
        type_=sa.UUID(),
        existing_nullable=False,
        postgresql_using="id::uuid",
    )


    # ============================================================
    # 4. Re-create foreign keys
    # ============================================================

    op.create_foreign_key(
        "refresh_tokken_user_id_fkey",
        "refresh_tokken",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.create_foreign_key(
        "users_role_id_fkey",
        "users",
        "role",
        ["role_id"],
        ["role_id"],
    )

    op.create_foreign_key(
        "user_roles_role_id_fkey",
        "user_roles",
        "role",
        ["role_id"],
        ["role_id"],
        ondelete="CASCADE",
    )

    op.create_foreign_key(
        "user_roles_user_id_fkey",
        "user_roles",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.create_foreign_key(
        "role_permissions_role_id_fkey",
        "role_permissions",
        "role",
        ["role_id"],
        ["role_id"],
        ondelete="CASCADE",
    )

    op.create_foreign_key(
        "role_permissions_permission_id_fkey",
        "role_permissions",
        "permissions",
        ["permission_id"],
        ["permission_id"],
        ondelete="CASCADE",
    )
