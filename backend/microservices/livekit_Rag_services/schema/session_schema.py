from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import enum
from uuid import UUID


class SessionStatus(enum.Enum):
    active = "active"
    closed = "closed"


class SessionCreate(BaseModel):
    title: Optional[str] = Field(
        None,
        min_length=3,
        max_length=100,
    )


class SessionResponse(BaseModel):
    id: UUID
    user_id: Optional[UUID] = None
    title: Optional[str] = None

    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None

    status: SessionStatus

    # The dashboard's Duration and Handler columns always showed
    # "-" because the API never returned these two things.
    #
    # duration_seconds: only for calls that have ended. A call in
    # progress has no "duration" - it is still growing.
    #
    # handler: "Human" if the call was ever escalated, otherwise
    # "AI". An escalation links to a message and a message to a
    # session, so this comes out of a join - no new column was
    # needed.
    duration_seconds: Optional[int] = None
    handler: Optional[str] = None

    class Config:
        from_attributes = True


class SessionUpdate(BaseModel):
    title: Optional[str] = Field(
        None,
        min_length=3,
        max_length=100,
    )

    class Config:
        from_attributes = True


class SessionPatch(BaseModel):
    title: Optional[str] = Field(
        None,
        min_length=3,
        max_length=100,
    )

    status: Optional[SessionStatus] = None

    class Config:
        extra = "forbid"
        from_attributes = True