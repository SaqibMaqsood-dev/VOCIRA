import enum
from datetime import datetime
from sqlalchemy import VARCHAR,  DateTime,  func , ForeignKey , Float , text , Integer , Text , Boolean
from sqlalchemy.orm import Mapped, mapped_column
from backend.helper_functions.database import Base , engine
from sqlalchemy.orm import relationship
from sqlalchemy import Text
from datetime import datetime, timedelta , timezone
from sqlalchemy.dialects.postgresql import UUID as SQLUUID
from uuid import uuid4 , UUID



class Refresh_Tokken(Base):
    __tablename__ = "refresh_tokken"
    
    id             : Mapped[UUID]                   =    mapped_column(SQLUUID(as_uuid=True) ,  primary_key=True , default=uuid4)
    user_id        : Mapped[UUID]                   =    mapped_column( SQLUUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False) 
    token_hash     : Mapped[str]                    =    mapped_column(Text)
    is_revoked     : Mapped[bool]                   =    mapped_column(Boolean , default=False)
    created_at     : Mapped[datetime]               =    mapped_column(DateTime, server_default=func.now())
    expires_at     : Mapped[datetime]               =    mapped_column(DateTime(timezone=True), nullable=False)   
    user           = relationship("Users"           ,    back_populates  = "refresh_tokens" )
    