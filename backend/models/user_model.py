import enum
from datetime import datetime, date
from sqlalchemy import String, Text, DateTime, Date, Enum, func , Integer , ForeignKey
from sqlalchemy.orm import Mapped, mapped_column , relationship
from sqlalchemy.dialects.postgresql import UUID as SQLUUID
from database.database import  Base



class Roles(str, enum.Enum):
    user = "user"
    guest = "guest"
    admin = "admin"
    

# -------------------------
# Users Table
# -------------------------


class Users(Base):
    __tablename__ = "users"
    
    id               : Mapped[int]       =  mapped_column( Integer               ,      primary_key=True )
    name             : Mapped[str]       =  mapped_column(String(100)            ,      nullable=False)          
    role             : Mapped[Roles]     =  mapped_column(Enum(Roles)            ,      default=Roles.guest)
    email            : Mapped[str]       =  mapped_column(String(200)            ,      nullable=True   ,unique=True)
    phone_number     : Mapped[str]       =  mapped_column(String(20)             ,      nullable=True   ,unique=True)
    password         : Mapped[Text]      =  mapped_column(Text                   ,      nullable=True)
    location         : Mapped[str]       =  mapped_column(Text                   ,      nullable=True)
    address          : Mapped[str]       =  mapped_column(Text                   ,      nullable=True)
    date_birth       : Mapped[date]      =  mapped_column(Date                   ,      nullable=True)                  
    role_id          : Mapped[int]       =  mapped_column(ForeignKey("role.role_id"))   
    created_at       : Mapped[datetime]  =  mapped_column(DateTime               ,      server_default=func.now())
    updated_at       : Mapped[datetime]  =  mapped_column(DateTime               ,      server_default=func.now() ,  onupdate=func.now())
    
    # relationship

    message                =  relationship("Message"            , back_populates  = "users")
    session                =  relationship("Session"            , back_populates  = "users")   
    
    # Solving Graph problem         
    escalations_created    =  relationship("Escalation"         , foreign_keys    = "[Escalation.user_id]"        ,  back_populates="user")
    escalations_assigned   =  relationship("Escalation"         , foreign_keys    = "[Escalation.assigned_admin]" ,  back_populates="admin")
    # refresh_tokens         =  relationship("Refresh_Tokken"     , back_populates  = "user")
    role                   =  relationship("Role"               , back_populates  = "users")
    