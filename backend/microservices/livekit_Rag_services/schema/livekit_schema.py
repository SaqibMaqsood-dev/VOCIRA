from uuid import UUID

from pydantic import BaseModel


class LiveKitToken(BaseModel):
    room: str = "vocira-room"


class LiveKitTokenResponse(BaseModel):
    session_id: UUID
    token: str
    room: str
    url: str


class AdminAcceptCallRequest(BaseModel):
    escalation_id: UUID