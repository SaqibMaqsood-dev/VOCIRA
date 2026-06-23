import enum
from datetime import datetime
from uuid import uuid4
from sqlalchemy import DateTime, ForeignKey, Integer , Enum , func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.database import Base 

class EscalationStatus(str , enum.Enum):
    pending = "pending"
    open    = "open"
    customer_waiting = "customer_waiting"
    resolved   = "resolved"
    closed     = "closed"


class Escalation(Base):
    __tablename__ = "escalations"

    id             : Mapped[int]                = mapped_column(Integer        , primary_key=True)
    user_id        : Mapped[int]                = mapped_column(ForeignKey("users.id"))
    message_id     : Mapped[int]                = mapped_column(ForeignKey("messages.id"))
    status         : Mapped[EscalationStatus]   = mapped_column(Enum(EscalationStatus)    , default="pending" )
    assigned_admin : Mapped[int]                = mapped_column(ForeignKey("users.id")    , nullable=True)
    created_at     : Mapped[datetime]           = mapped_column(DateTime        , server_default=func.now())
    user           = relationship("Users"       , foreign_keys=[user_id]        , back_populates="escalations_created")
    admin          = relationship("Users"       , foreign_keys=[assigned_admin] , back_populates="escalations_assigned")      
    