from sqlalchemy import String, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.helper_functions.database.base import Base


class Permission(Base):
    __tablename__ = "permissions"

    permission_id: Mapped[str] = mapped_column(
        VARCHAR(100),
        primary_key=True,
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )

    roles = relationship(
        "Role",
        secondary="role_permissions",
        back_populates="permissions",
    )
