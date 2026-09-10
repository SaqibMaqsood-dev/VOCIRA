from datetime import datetime , timezone , timedelta
from backend.microservices.auth_services.core.config import settings
import jwt




def create_refresh_tokken(data: dict):
    """
    Mint a refresh token.

    The caller must include user_id in `data`: verify_refresh_tokken
    rejects a token without it, and the /refresh endpoint used to mint
    replacements carrying only "sub" - so a session could be refreshed
    exactly once and every attempt after that failed.

    The lifetime comes from REFRESH_TOKEN_EXPIRE_DAYS. It was hardcoded
    to 1 day here while the database row was written with 7, so the
    stored token outlived the JWT itself by six days and the setting
    was ignored entirely.
    """
    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )

    to_encode.update({"exp": expire,
                      "type" : "refresh"
                      })
    

    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    # NOTE: this used to print JWT_SECRET_KEY - meaning the signing
    # key went into the logs on every login. Removed.
    return encoded_jwt

