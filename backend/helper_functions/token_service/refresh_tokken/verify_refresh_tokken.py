from jwt import InvalidTokenError
import jwt

from backend.microservices.auth_services.core.config import settings
from backend.microservices.auth_services.schema.token_schema import TokenData


def verify_refresh_tokken(token, credentials_exception):
    """
    Verify a refresh token and return TokenData.

    There were two bugs here that made /refresh return a 500:

      1. settings.ALGORITHM  -> no such field exists on Settings (it
         is JWT_ALGORITHM). It raised AttributeError, which was not
         caught either, not being an InvalidTokenError.

      2. TokenData(username=email) -> TokenData also requires
         user_id: UUID (it has no default). Pydantic validation
         failed.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )

        email = payload.get("sub")
        user_id = payload.get("user_id")
        token_type = payload.get("type")

        # accept refresh tokens only - not access tokens
        if email is None or user_id is None or token_type != "refresh":
            raise credentials_exception

        return TokenData(
            username=email,
            user_id=user_id,
        )

    except InvalidTokenError:
        raise credentials_exception
