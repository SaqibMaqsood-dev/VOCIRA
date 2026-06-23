from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum
from datetime import datetime


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
    id              : int
    user_id         : int
    message_id      : int
    status          : EscalationStatus
    assigned_admin  : Optional[int] = None
    created_at      : datetime
    class Config    :
        from_attributes = True  




class EscalationPatch(BaseModel):
    status          : Optional[EscalationStatus] = None
    assigned_admin  : Optional[int] = None
    message_id      : Optional[int] = None

    class Config:
        from_attributes = True

