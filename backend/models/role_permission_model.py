from sqlalchemy import Table, Column, ForeignKey
from database.database import Base

class role_permissions(Base):
    __tablename__ = "role_permissions"

    role_id = Column(ForeignKey("role.role_id"), primary_key=True)
    permission_id = Column(ForeignKey("permissions.id"), primary_key=True)
    