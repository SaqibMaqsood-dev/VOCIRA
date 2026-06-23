from sqlalchemy import String , ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship 
from database.database import Base

class Permission(Base):
    __tablename__ = "permissions"

    id      :  Mapped[int] = mapped_column(primary_key=True)
    name    :  Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    roles = relationship(
        "Role",
        secondary="role_permissions",
        back_populates="permissions"
    )