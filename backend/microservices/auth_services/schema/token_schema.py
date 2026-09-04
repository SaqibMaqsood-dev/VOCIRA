from pydantic import BaseModel
from uuid import UUID

class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str | None = None
    user_id : UUID

    # Ye dono JWT mein pehle se the, magar yahan declare nahi thay -
    # pydantic inhein chup-chaap gira deta tha. role ke baghair koi
    # endpoint ye nahi jaan sakta tha ke caller admin hai ya parent.
    role      : str | None = None
    parent_id : str | None = None

class RefreshToken(BaseModel):
    refreshtoken : str

