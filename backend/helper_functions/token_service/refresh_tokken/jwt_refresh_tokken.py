from datetime import datetime , timezone , timedelta
from backend.microservices.auth_services.core.config import settings
import jwt




def create_refresh_tokken(data: dict):
    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + timedelta(days=1)

    to_encode.update({"exp": expire,
                      "type" : "refresh"
                      })
    

    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    print("SECRET KEY:", settings.JWT_SECRET_KEY)
    print("ALGORITHM:", settings.JWT_ALGORITHM)
    print("EXPIRE MINUTES:", settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return encoded_jwt

