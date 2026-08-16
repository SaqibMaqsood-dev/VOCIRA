from backend.microservices.auth_services.core.config import settings
from backend.microservices.auth_services.schema.token_schema import TokenData
from jwt import InvalidTokenError
import jwt
from typing import Optional


def verify_refresh_tokken(token, credentials_exception):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        
        email = payload.get("sub")
        token_type = payload.get("type")  
        print(token_type)

        if email is None or token_type != "refresh":
            raise credentials_exception

        return TokenData(username=email)

    except InvalidTokenError:
        raise credentials_exception 