from backend.microservices.auth_services.core.config import settings
from backend.microservices.auth_services.schema.token_schema import TokenData
from jwt import InvalidTokenError
import jwt


def verify_jwt(token, credentials_exception):
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )

        email = payload.get("sub")
        user_id = payload.get("user_id")
        parent_id = payload.get("parent_id")

        if email is None or user_id is None:
            raise credentials_exception

        return TokenData(
            username=email,
            user_id=user_id,
            parent_id=parent_id,
        )

    except InvalidTokenError:
        raise credentials_exception

    