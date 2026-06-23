import enum
from datetime import datetime
from sqlalchemy import VARCHAR,  DateTime,  func , ForeignKey , Float , text , Integer , Text , Enum
from sqlalchemy.orm import Mapped, mapped_column
from database.database import Base
from sqlalchemy.orm import relationship
from sqlalchemy import Text, Enum
from models.role_permission_model import role_permissions



class Role(Base):
    __tablename__ = "role"
    
    role_id        : Mapped[int]   = mapped_column(Integer , primary_key=True)
    name           : Mapped[str]   = mapped_column(Text    , unique=True)
    #relationship 
    users          = relationship("Users"   , back_populates="role")
    permissions    = relationship(
        "Permission",
        secondary="role_permissions",
        back_populates="roles"
    )

    