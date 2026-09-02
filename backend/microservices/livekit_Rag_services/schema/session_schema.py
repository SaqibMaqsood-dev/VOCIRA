from datetime import datetime
from typing import Optional
from uuid import UUID
import enum

from pydantic import BaseModel, Field, computed_field


# =========================================================
# SESSION STATUS
# =========================================================

class SessionStatus(str, enum.Enum):
    active = "active"
    closed = "closed"


# =========================================================
# SESSION HANDLER
# =========================================================

class SessionHandler(str, enum.Enum):
    ai = "ai"
    admin = "admin"


# =========================================================
# CREATE SESSION
# =========================================================

class SessionCreate(BaseModel):
    title: Optional[str] = Field(
        None,
        min_length=3,
        max_length=100,
    )

    handler: SessionHandler = SessionHandler.ai


# =========================================================
# SESSION RESPONSE
# =========================================================

class SessionResponse(BaseModel):
    id: UUID

    user_id: Optional[UUID] = None

    title: Optional[str] = None

    start_at: Optional[datetime] = None

    end_at: Optional[datetime] = None

    status: SessionStatus

    handler: SessionHandler

    # =====================================================
    # DURATION
    # =====================================================
        
    @computed_field
    @property
    def duration_seconds(self) -> Optional[int]:

        if not self.start_at or not self.end_at:
            return None

        return max(
            0,
            int(
                (
                    self.end_at - self.start_at
                ).total_seconds()
            ),
        )

    class Config:
        from_attributes = True


# =========================================================
# UPDATE SESSION
# =========================================================

class SessionUpdate(BaseModel):

    title: Optional[str] = Field(
        None,
        min_length=3,
        max_length=100,
    )

    class Config:
        from_attributes = True


# =========================================================
# PATCH SESSION
# =========================================================

class SessionPatch(BaseModel):

    title: Optional[str] = Field(
        None,
        min_length=3,
        max_length=100,
    )

    status: Optional[SessionStatus] = None

    handler: Optional[SessionHandler] = None

    class Config:
        extra = "forbid"
        from_attributes = True