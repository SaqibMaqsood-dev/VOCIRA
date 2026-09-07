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
# Kuch endpoints dono tarah chalte hain: login ho to account se
# kaam lein, na ho to guest ki tarah. Support tickets aise hi hain -
# parent login kar sakta hai, magar jis ka account na ho wo bhi
# madad maang sake.
#
# current_user token na hone par 401 phenk deta hai, is liye us se
# ye kaam nahi hota. Ye wala None lauta deta hai.
# =========================================================

optional_oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/login",
    auto_error=False,
)


async def optional_current_user(
    token: Annotated[str | None, Depends(optional_oauth2_scheme)]
):
    """Token ho aur sahi ho to user, warna None."""

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
        # Purana ya kharab token - guest ki tarah aage barhein.
        # Yahan 401 phenkna theek nahi hoga: guest ke liye ye
        # endpoint khula hai, aur ek bekaar token us ka raasta
        # nahi rok sakta.
        return None
