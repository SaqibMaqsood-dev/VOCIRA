from sqlalchemy import Table, Column, ForeignKey, Integer
from database.database import Base


class UserRole(Base):
    __tablename__ = "user_roles"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    role_id = Column(Integer, ForeignKey("role.role_id"), primary_key=True)