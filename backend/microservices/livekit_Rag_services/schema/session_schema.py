from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import enum
from uuid import UUID

class SessionStatus(enum.Enum):
    active = "active"
    closed = "closed"


class SessionCreate(BaseModel):
    title     : Optional[str] = Field(None, min_length=3, max_length=100)    
    

class SessionResponse(BaseModel):
    id      : UUID
    user_id : Optional[int] = None
    title: Optional[str]
    start_at : datetime
    status     : SessionStatus

    

    class Config:
        from_attributes = True





class SessionUpdate(BaseModel):
    title: Optional[str] = Field( None, min_length=3,max_length=100)

    class Config:
        from_attributes = True



class SessionPatch(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=100)

    class Config:
        extra = "forbid"
        from_attributes = True


