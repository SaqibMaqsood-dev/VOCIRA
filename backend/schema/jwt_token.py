from pydantic import BaseModel
from uuid import UUID

class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str | None = None
    user_id : int

class RefreshToken(BaseModel):
    refreshtoken : str
    