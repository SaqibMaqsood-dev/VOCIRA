from uuid import UUID

from pydantic import BaseModel


class LiveKitToken(BaseModel):
    room: str = "vocira-room"


class CallSchool(BaseModel):
    id: str
    name: str


class LiveKitTokenResponse(BaseModel):
    session_id: UUID
    token: str
    room: str
    url: str
    # the school the call goes to - the Assistant page shows it
    school: CallSchool | None = None


class AdminAcceptCallRequest(BaseModel):
    escalation_id: UUID