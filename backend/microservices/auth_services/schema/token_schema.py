from pydantic import BaseModel
from uuid import UUID


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str | None = None
    user_id: UUID
    role: str | None = None
    parent_id: str | None = None


class RefreshToken(BaseModel):
    refreshtoken: str
