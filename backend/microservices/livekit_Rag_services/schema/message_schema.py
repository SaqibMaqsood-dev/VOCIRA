from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from datetime import datetime


class MessageCreate(BaseModel):
    sender_type : str 
    content     : str = Field(..., min_length=1, max_length=2000)
    intent      : str
    source_type : str 
    created_at  : datetime
    

class MessageResponse(BaseModel):
    user_id: Optional[int] = None
    id: UUID
    session_id: UUID
    sender_type: str
    content: str
    intent: Optional[str]
    source_type: Optional[str]
    created_at: datetime

    class Config:
        from_attributes  = True

class MessagePartialUpdate(BaseModel):
    content: Optional[str] = None
    sender_type: Optional[str] = None
    sender_id: Optional[int] = None
    session_id: Optional[int] = None


