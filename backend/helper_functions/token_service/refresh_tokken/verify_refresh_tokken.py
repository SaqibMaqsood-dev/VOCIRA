from jwt import InvalidTokenError
import jwt

from backend.microservices.auth_services.core.config import settings
from backend.microservices.auth_services.schema.token_schema import TokenData


def verify_refresh_tokken(token, credentials_exception):
    """
    Refresh token verify karein aur TokenData lautayein.

    Pehle yahan do bug the, jin ki wajah se /refresh 500 deta tha:

      1. settings.ALGORITHM  -> Settings mein aisa koi field hai hi
         nahi (JWT_ALGORITHM hai). AttributeError uthta tha, aur wo
         InvalidTokenError na hone ki wajah se catch bhi nahi hota tha.

      2. TokenData(username=email) -> TokenData ko user_id: UUID bhi
         chahiye (koi default nahi). Pydantic validation fail hoti thi.
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

        # sirf refresh token qubool karein - access token nahi
        if email is None or user_id is None or token_type != "refresh":
            raise credentials_exception

        return TokenData(
            username=email,
            user_id=user_id,
        )

    except InvalidTokenError:
        raise credentials_exception
