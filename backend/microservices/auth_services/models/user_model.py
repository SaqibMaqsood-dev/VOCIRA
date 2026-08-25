from datetime import datetime, date
from uuid import UUID, uuid4

from sqlalchemy import (
    VARCHAR,
    Text,
    DateTime,
    Date,
    ForeignKey,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as SQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.helper_functions.database.base import Base


class Users(Base):
    __tablename__ = "users"
    __table_args__ = {'extend_existing': True}

    user_id         : Mapped[UUID]        = mapped_column(SQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    parent_id       : Mapped[str | None]  = mapped_column(VARCHAR(100), nullable=True)
    name            : Mapped[str]         = mapped_column(VARCHAR(100), nullable=False)
    role_id         : Mapped[str]         = mapped_column(ForeignKey("role.role_id"), nullable=False)
    email           : Mapped[str | None]  = mapped_column(VARCHAR(200), nullable=True, unique=True)
    password_hashed : Mapped[str | None]  = mapped_column(Text, nullable=True)
    phone_number    : Mapped[str | None]  = mapped_column(VARCHAR(20), nullable=True, unique=True)
    location        : Mapped[str | None]  = mapped_column(Text, nullable=True)
    address         : Mapped[str | None]  = mapped_column(Text, nullable=True)
    date_birth      : Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at      : Mapped[datetime]    = mapped_column(DateTime, server_default=func.now())
    updated_at      : Mapped[datetime]    = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    role           = relationship("Role", back_populates="users")
    refresh_tokens = relationship("Refresh_Tokken", back_populates="user", cascade="all, delete-orphan")