import enum
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer , func , Text , Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.database import Base

class SessionStatus(str , enum.Enum):
    active = "active"
    closed = "closed"

class Session(Base):
    __tablename__ = "sessions"
    
    id              : Mapped[int]               =    mapped_column(Integer             , primary_key=True)
    user_id         : Mapped[int]               =    mapped_column(ForeignKey("users.id") , nullable=True)
    start_at        : Mapped[datetime]          =    mapped_column(DateTime            ,server_default=func.now())
    end_at          : Mapped[datetime]          =    mapped_column(DateTime            ,nullable=True)
    title           : Mapped[str]               =    mapped_column(Text)
    status          : Mapped[SessionStatus]     =    mapped_column(Enum(SessionStatus) , default=SessionStatus.active )
    # relationship
    messages        = relationship("Message"    ,    back_populates="session")
    users           = relationship("Users"      ,    back_populates="session")
    