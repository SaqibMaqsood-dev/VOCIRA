from backend.helper_functions.token_service.access_tokken.jtw_tokken import create_access_token
from backend.helper_functions.token_service.refresh_tokken.jwt_refresh_tokken import create_refresh_tokken
from backend.microservices.auth_services.services.hashing_service.hashing import Hash
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.helper_functions.database import get_db
from backend.microservices.auth_services.models.user_model import Users
from backend.microservices.auth_services.models.refresh_tokken import Refresh_Tokken
from backend.microservices.auth_services.schema.token_schema import Token

router = APIRouter(tags=["Authentication"])


@router.post("/login", response_model=Token)
async def login(
    user_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    # Fetch user
    result = await db.execute(
        select(Users).where(Users.email == user_data.username)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    # Verify password
    if not Hash.verify_password(
        plain_password=user_data.password,
        hashed_password=user.password_hashed,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    # Create access token
    access_token = create_access_token(
        data={
            "sub": user.email,
            "user_id": str(user.id),
            }
    )

    # Create refresh token
    refresh_token = create_refresh_tokken(
        data={
            "sub": user.email,
            "user_id": str(user.id),
        }
    )

    # Store hashed refresh token
    hashed_refresh_token = Hash.hash_token(refresh_token)

    db.add(
        Refresh_Tokken(
            user_id=user.id,
            token_hash=hashed_refresh_token,
            is_revoked=False,
        )
    )

    await db.commit()

    return Token(
        access_token=access_token,
        token_type="bearer",
    )