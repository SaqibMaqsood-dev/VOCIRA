import enum
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer , func , Text , Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID as SQLUUID  
from backend.helper_functions.database.base import (

    Base,
)
from uuid import uuid4 , UUID


class SessionStatus(str , enum.Enum):
    active = "active"
    closed = "closed"


class SessionHandler(str, enum.Enum):
    ai = "ai"
    admin = "admin"

    
class Session(Base):
    __tablename__ = "sessions"
    
    id              : Mapped[UUID]              =    mapped_column(SQLUUID(as_uuid=True)    ,  default=uuid4, primary_key=True)
    user_id         : Mapped[UUID]              =    mapped_column(SQLUUID(as_uuid=True)    ,  nullable=True)
    start_at        : Mapped[datetime]          =    mapped_column(DateTime                 ,  server_default=func.now())
    end_at          : Mapped[datetime]          =    mapped_column(DateTime                 ,  nullable=True)
    title           : Mapped[str]               =    mapped_column(Text) 
    status          : Mapped[SessionStatus]     =    mapped_column(Enum(SessionStatus)      ,  default=SessionStatus.active )
    handler         : Mapped[SessionHandler]    =    mapped_column(Enum(SessionHandler)     ,  default=SessionHandler.ai ,  nullable=False, server_default=SessionHandler.ai.value)  


    
    # relationship
    messages        = relationship("Message"    ,    back_populates="session")

