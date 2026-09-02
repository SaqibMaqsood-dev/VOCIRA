from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
from enum import Enum


class EscalationStatus(str, Enum):
    pending = "pending"
    resolved = "resolved"


class CreateEscalation(BaseModel):
    status: EscalationStatus = EscalationStatus.pending


class EscalationResponse(BaseModel):
    id: UUID
    user_id: UUID
    message_id: UUID
    status: EscalationStatus
    created_at: datetime

    class Config:
        from_attributes = True


class EscalationPatch(BaseModel):
    status: EscalationStatus | None = None
    message_id: UUID | None = None

    class Config:
        from_attributes = True