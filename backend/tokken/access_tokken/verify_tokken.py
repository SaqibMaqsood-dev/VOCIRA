from core.config import settings
from schema.jwt_token import TokenData
from jwt import InvalidTokenError
import jwt


def verify_jwt(token , credentials_exception):
    try:  
        payload = jwt.decode(token,settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email   = payload.get("sub")
        user_id = payload.get("user_id")
      
        if email  is None or user_id is None :
            raise credentials_exception  
        return  TokenData(username=email , user_id=user_id )
    except InvalidTokenError:
        raise credentials_exception
    