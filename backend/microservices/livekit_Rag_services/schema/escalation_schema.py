from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum
from datetime import datetime
from uuid import UUID


class EscalationStatus(str, Enum):
    pending   = "pending"
    open      = "open"
    customer_waiting = "customer_waiting"
    resolved  = "resolved"
    closed    = "closed"


class CreateEscalation(BaseModel):
    status          : Optional[EscalationStatus]       =    EscalationStatus.pending
    assigned_admin  : Optional[int]    = Field(default =    None , description  =   "Admin assigned to handle escalation" )
    

    

class EscalationResponse(BaseModel):
    id              : UUID
    user_id         : UUID
    message_id      : UUID
    status          : EscalationStatus
    # assigned_admin  : Optional[UUID] = None
    created_at      : datetime
    class Config    :
        from_attributes = True  




class EscalationPatch(BaseModel):
    status          : Optional[EscalationStatus] = None
    assigned_admin  : Optional[int] = None
    message_id      : Optional[UUID] = None

    class Config:
        from_attributes = True

