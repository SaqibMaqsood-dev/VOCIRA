import enum
from ....helper_functions.database import Base
from uuid import uuid4 , UUID
from datetime import datetime, date
from backend.helper_functions.database import Base
from sqlalchemy.dialects.postgresql import UUID as SQLUUID
from sqlalchemy.orm import Mapped, mapped_column 
from sqlalchemy import String, Text, DateTime, Date, Enum, func  , ForeignKey 
from sqlalchemy.orm import relationship



class Roles(str, enum.Enum):
    user = "user"
    guest = "guest"
    admin = "admin"
    
# -------------------------
# Users Table
# -------------------------

class Users(Base):
    __tablename__ = "users"
    
    id               : Mapped[UUID]        =     mapped_column(SQLUUID(as_uuid=True)           ,      primary_key=True , default=uuid4 )
    name             : Mapped[str]         =     mapped_column(String(100)                     ,      nullable=False)          
    role             : Mapped[Roles]       =     mapped_column(Enum(Roles)                     ,      default=Roles.guest)
    role_id          : Mapped[int]         =     mapped_column(ForeignKey("role.role_id"))
    email            : Mapped[str]         =     mapped_column(String(200)                     ,      nullable=True   ,unique=True)
    password_hashed  : Mapped[Text]        =     mapped_column(Text                            ,      nullable=True)
    phone_number     : Mapped[str]         =     mapped_column(String(20)                      ,      nullable=True   ,unique=True)
    location         : Mapped[str]         =     mapped_column(Text                            ,      nullable=True)
    address          : Mapped[str]         =     mapped_column(Text                            ,      nullable=True)
    date_birth       : Mapped[date]        =     mapped_column(Date                            ,      nullable=True)                  
    created_at       : Mapped[datetime]    =     mapped_column(DateTime                        ,      server_default=func.now())
    updated_at       : Mapped[datetime]    =     mapped_column(DateTime                        ,      server_default=func.now() ,  onupdate=func.now())

    # relationship
    roles            = relationship("Role" , secondary="user_roles", back_populates="users")

    refresh_tokens = relationship( "Refresh_Tokken", back_populates="user", cascade="all, delete-orphan")