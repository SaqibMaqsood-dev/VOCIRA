import enum
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer , func , Text , Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID as SQLUUID  
from backend.helper_functions.database.base import (

    Base,
)
from uuid import uuid4 , UUID


class SessionStatus(str , enum.Enum):
    active = "active"
    closed = "closed"
    
class Session(Base):
    __tablename__ = "sessions"
    
    id              : Mapped[UUID]              =    mapped_column(SQLUUID(as_uuid=True)  , default=uuid4, primary_key=True)
    user_id         : Mapped[UUID]              =    mapped_column(SQLUUID(as_uuid=True)  , nullable=True)
    start_at        : Mapped[datetime]          =    mapped_column(DateTime               ,server_default=func.now())
    end_at          : Mapped[datetime]          =    mapped_column(DateTime               ,nullable=True)
    title           : Mapped[str]               =    mapped_column(Text)
    status          : Mapped[SessionStatus]     =    mapped_column(Enum(SessionStatus) , default=SessionStatus.active )
    # Which school the call was for (services/tenants.py) - what a
    # school's admin is limited to.
    school_id       : Mapped[str | None]        =    mapped_column(String(40), nullable=True)
    
    # relationship
    messages        = relationship("Message"    ,    back_populates="session")

