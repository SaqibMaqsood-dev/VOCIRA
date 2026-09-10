from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from .verify_tokken import verify_jwt


oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/login"
)



async def current_user(
    token: Annotated[str, Depends(oauth2_scheme)]
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={
            "WWW-Authenticate": "Bearer"
        },
    )

    user = verify_jwt(
        token=token,
        credentials_exception=credentials_exception,
    )

    return user

# =========================================================
# OPTIONAL AUTH
#
# Some endpoints work both ways: use the account when logged in,
# behave as a guest otherwise. Support tickets are like that - a
# parent can log in, but someone without an account must still be
# able to ask for help.
#
# current_user raises a 401 when there is no token, so it cannot do
# this job. This one returns None instead.
# =========================================================

optional_oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/login",
    auto_error=False,
)


async def optional_current_user(
    token: Annotated[str | None, Depends(optional_oauth2_scheme)]
):
    """The user when the token is present and valid, otherwise None."""

    if not token:
        return None

    try:
        return verify_jwt(
            token=token,
            credentials_exception=HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
            ),
        )

    except HTTPException:
        # An expired or malformed token - carry on as a guest.
        # Raising a 401 here would be wrong: this endpoint is open to
        # guests, and a useless token must not block that path.
        return None
