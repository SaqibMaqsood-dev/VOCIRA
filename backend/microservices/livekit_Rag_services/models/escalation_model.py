import enum
from datetime import datetime
from uuid import uuid4
from sqlalchemy import DateTime, ForeignKey, Integer , Enum , func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.helper_functions.database import (
    Base,
)
from sqlalchemy.dialects.postgresql import UUID as SQLUUID
from uuid import uuid4 , UUID

class EscalationStatus(str , enum.Enum):
    pending = "pending"
    open    = "open"
    customer_waiting = "customer_waiting"
    resolved   = "resolved"
    closed     = "closed"


class Escalation(Base):
    __tablename__ = "escalations"
    
    id             : Mapped[UUID]               = mapped_column(SQLUUID(as_uuid=True)      , default=uuid4 , primary_key=True)
    user_id        : Mapped[UUID]               = mapped_column(SQLUUID(as_uuid=True)      ,  nullable=True)
    message_id     : Mapped[UUID]               = mapped_column(ForeignKey("messages.id"))
    status         : Mapped[EscalationStatus]   = mapped_column(Enum(EscalationStatus)     , default="pending" )
    created_at     : Mapped[datetime]           = mapped_column(DateTime                   , server_default=func.now())

    