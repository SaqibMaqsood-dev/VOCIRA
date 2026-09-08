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

    # Dashboard ki Duration aur Handler columns pehle hamesha
    # "-" dikhati thin kyunke ye do cheezein API deti hi nahi thi.
    #
    # duration_seconds: sirf band ho chuki calls ke liye. Chalti
    # hui call ki koi "duration" nahi hoti - wo abhi barh rahi hai.
    #
    # handler: "Human" agar us call mein kabhi escalation hui,
    # warna "AI". Escalation message se juRi hai aur message
    # session se, is liye ye jorh kar nikalta hai - koi naya
    # column banane ki zaroorat nahi padi.
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