from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from typing import Annotated
from fastapi import Depends , HTTPException , status
from .verify_refresh_tokken import verify_refresh_tokken

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="refresh_tokken")

async def get_current_user_refresh(token: Annotated[str, Depends(oauth2_scheme)]):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    user = verify_refresh_tokken(token=token , credentials_exception=credentials_exception)
    

    return user

