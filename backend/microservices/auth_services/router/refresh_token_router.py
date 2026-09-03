from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.microservices.auth_services.db import get_db
from backend.microservices.auth_services.models.refresh_tokken import Refresh_Tokken
from backend.microservices.auth_services.schema.token_schema import RefreshToken, Token
from backend.microservices.auth_services.services.hashing_service.hashing import Hash
from backend.helper_functions.token_service.access_tokken.jtw_tokken import (
    create_access_token,
)

from backend.helper_functions.token_service.refresh_tokken.jwt_refresh_tokken import (
    create_refresh_tokken,
)
from backend.helper_functions.token_service.refresh_tokken.verify_refresh_tokken import (
    verify_refresh_tokken,
)

route = APIRouter(tags=["Authentication with refresh token"])


@route.post("/refresh", response_model=Token)
async def refresh_token(
    response: Response,
    data: RefreshToken,
    db: AsyncSession = Depends(get_db),
):

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token",
    )

    # -------------------------------------------------
    # 1. Verify JWT Refresh Token
    # -------------------------------------------------
    payload = verify_refresh_tokken(
        data.refreshtoken,
        credentials_exception,
    )

    # -------------------------------------------------
    # 2. Hash Refresh Token
    # -------------------------------------------------
    hashed_token = Hash.hash_token(data.refreshtoken)

    # -------------------------------------------------
    # 3. Find Token in Database
    # -------------------------------------------------

    result = await db.execute(
        select(Refresh_Tokken).where(
            and_(
                Refresh_Tokken.token_hash == hashed_token,
                Refresh_Tokken.is_revoked == False,
                Refresh_Tokken.expires_at > datetime.now(timezone.utc),
            )
        )
    )

    token_obj = result.scalar_one_or_none()

    if token_obj is None:
        raise credentials_exception

    # -------------------------------------------------
    # 4. Create New Tokens
    # -------------------------------------------------

    # NOTE: pehle yahan do bug the -
    #   1. create_access_token(data=...) - signature "payload" hai, "data" nahi
    #   2. jwt_refresh_tokken(...) - wo MODULE hai, function nahi
    # Dono ki wajah se /refresh endpoint har baar TypeError deta tha.
    new_access_token = create_access_token(
        {"sub": payload.username}
    )

    new_refresh_token = create_refresh_tokken(
        {"sub": payload.username}
    )

    # -------------------------------------------------
    # 5. Revoke Old Refresh Token
    # -------------------------------------------------
    token_obj.is_revoked = True

    # -------------------------------------------------
    # 6. Store New Refresh Token
    # -------------------------------------------------

    new_db_token = Refresh_Tokken(
        user_id=token_obj.user_id,
        token_hash=Hash.hash_token(new_refresh_token),
        is_revoked=False,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )

    db.add(new_db_token)

    await db.commit()

    # -------------------------------------------------
    # 7. Store Refresh Token in HttpOnly Cookie
    # -------------------------------------------------
    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        secure=True,       
        samesite="lax",
        max_age=7 * 24 * 60 * 60,
    )

    # -------------------------------------------------
    # 8. Return New Access Token
    # -------------------------------------------------

    return Token(
        access_token=new_access_token,
        token_type="bearer",
    )

