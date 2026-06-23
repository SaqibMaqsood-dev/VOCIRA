import enum
from datetime import datetime
from sqlalchemy import   DateTime,  func , ForeignKey  , text , Integer , Text , Enum
from sqlalchemy.orm import Mapped, mapped_column
from database.database import Base
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
    
    id             : Mapped[int]              = mapped_column(Integer, primary_key=True)
    user_id        : Mapped[int | None]       = mapped_column(ForeignKey("users.id") , nullable=True)
    session_id     : Mapped[int]              = mapped_column(ForeignKey("sessions.id"))
    sender_type    : Mapped[SenderTypeEnum]   = mapped_column(Enum(SenderTypeEnum) , default=SenderTypeEnum.guest)
    created_at     : Mapped[datetime]         = mapped_column(DateTime, server_default=func.now())
    content        : Mapped[str]              = mapped_column(Text)
    intent         : Mapped[str]              = mapped_column(Text)
    source_type    : Mapped[SourceTypeEnum]   = mapped_column(Enum(SourceTypeEnum) , default=SourceTypeEnum.database)
    
    
    #relationship 
    session             = relationship("Session"            , back_populates="messages")
    users               = relationship("Users"              , back_populates="message")
    