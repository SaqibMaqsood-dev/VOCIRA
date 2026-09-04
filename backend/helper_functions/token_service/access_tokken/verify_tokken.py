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

        # login ke waqt JWT mein role bhi jata hai; pehle yahan
        # se nikala nahi jata tha, is liye koi endpoint ye tay
        # nahi kar sakta tha ke caller admin hai ya nahi.
        role = payload.get("role")

        if isinstance(role, dict):
            role = role.get("name")

        if email is None or user_id is None:
            raise credentials_exception

        return TokenData(
            username=email,
            user_id=user_id,
            parent_id=parent_id,
            role=str(role).strip().lower() if role else None,
        )

    except InvalidTokenError:
        raise credentials_exception

    