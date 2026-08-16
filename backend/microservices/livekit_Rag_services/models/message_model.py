import enum
from datetime import datetime
from sqlalchemy import   DateTime,  func , ForeignKey  , text , Integer , Text , Enum
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID as SQLUUID
from uuid import uuid4 , UUID
from backend.helper_functions.database import (
    Base,
)
from sqlalchemy.orm import relationship

from sqlalchemy import Text, Enum

class SourceTypeEnum(str, enum.Enum):
    rag = "rag"
    database = "database"


    
class SenderTypeEnum(str, enum.Enum):
    user = "user"
    ai = "ai"
    admin = "admin",
    guest = "guest"


class Message(Base):
    __tablename__ = "messages"

    id             : Mapped[UUID]             = mapped_column(SQLUUID(as_uuid=True)         , default=uuid4      , primary_key=True)
    user_id        : Mapped[UUID]             = mapped_column(SQLUUID(as_uuid=True)         ,  nullable=True)
    session_id     : Mapped[UUID]             = mapped_column(ForeignKey("sessions.id"))
    sender_type    : Mapped[SenderTypeEnum]   = mapped_column(Enum(SenderTypeEnum)          ,  default=SenderTypeEnum.guest)
    created_at     : Mapped[datetime]         = mapped_column(DateTime                      ,  server_default=func.now())
    content        : Mapped[str]              = mapped_column(Text)
    intent         : Mapped[str]              = mapped_column(Text , nullable=True)
    source_type    : Mapped[SourceTypeEnum]   = mapped_column(Enum(SourceTypeEnum)          ,  default=SourceTypeEnum.database)
    
    
    #relationship 
    session             = relationship("Session"            , back_populates="messages")
    