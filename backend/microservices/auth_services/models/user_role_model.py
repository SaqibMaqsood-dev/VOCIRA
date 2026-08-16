from sqlalchemy import Table, Column, ForeignKey, Integer
from backend.helper_functions.database import Base
from uuid import uuid4 , UUID
from sqlalchemy.orm import  Mapped
from sqlalchemy.dialects.postgresql import UUID as SQLUUID

    
class UserRole(Base):
    __tablename__ = "user_roles"
    
    user_id : Mapped[UUID] = Column(SQLUUID(as_uuid=True)    ,  ForeignKey("users.id")       , primary_key=True)
    role_id : Mapped[UUID] = Column(SQLUUID(as_uuid=True)    ,  ForeignKey("role.role_id")   , primary_key=True)

