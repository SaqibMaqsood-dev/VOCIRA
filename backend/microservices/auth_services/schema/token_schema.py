from pydantic import BaseModel
from uuid import UUID

class Token(BaseModel):
    access_token: str
    token_type: str

    # The refresh token has to reach the client, or /refresh can never
    # be called: login created one and stored its hash, but returned
    # only the access token. That token expires in
    # ACCESS_TOKEN_EXPIRE_MINUTES and there was no way to renew it, so
    # every session simply ended there.
    refresh_token: str | None = None


class TokenData(BaseModel):
    username: str | None = None
    user_id : UUID

    # Both were already in the JWT but were not declared here -
    # pydantic dropped them silently. Without role, no endpoint could
    # tell whether the caller was an admin or a parent.
    role      : str | None = None
    parent_id : str | None = None

class RefreshToken(BaseModel):
    refreshtoken : str

