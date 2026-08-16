from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship 
from backend.helper_functions.database import Base
from sqlalchemy.dialects.postgresql import UUID as SQLUUID
from uuid import uuid4 , UUID

class Permission(Base):
    __tablename__ = "permissions"

    permission_id    :  Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True) ,primary_key=True , default=uuid4)
    name             :  Mapped[str]  = mapped_column(String(100), unique=True, nullable=False)
    roles            = relationship(
                        "Role",
                        secondary="role_permissions",
                        back_populates="permissions"
                    )

