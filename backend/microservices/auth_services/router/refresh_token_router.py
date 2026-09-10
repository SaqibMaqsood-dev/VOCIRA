from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import and_, select
from sqlalchemy.orm import selectinload
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

from backend.microservices.auth_services.core.config import settings
from backend.microservices.auth_services.models.user_model import Users
from backend.microservices.auth_services.services.token_claims import (
    access_claims,
    refresh_claims,
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
    # 4. Load the user
    # -------------------------------------------------

    # The refresh token carries only sub and user_id - not role or
    # name. Those have to come from the database, or the renewed
    # access token would be missing exactly the claims the admin
    # guard and the navbar read.
    #
    # Loading the user again also revokes access properly: a deleted
    # or disabled account cannot refresh its way into a new token.
    user = (
        await db.execute(
            select(Users)
            .options(selectinload(Users.role))
            .where(Users.user_id == token_obj.user_id)
        )
    ).scalar_one_or_none()

    if user is None:
        raise credentials_exception

    # -------------------------------------------------
    # 5. Create New Tokens
    # -------------------------------------------------

    # NOTE: there were two bugs here -
    #   1. create_access_token(data=...) - the signature is "payload",
    #      not "data"
    #   2. jwt_refresh_tokken(...) - that is a MODULE, not a function
    # Between them the /refresh endpoint raised TypeError every time.
    #
    # And after those were fixed, both tokens were still minted with
    # only {"sub": ...}:
    #   - the access token had no user_id, and verify_jwt rejects a
    #     token without one, so every renewed session got a 401 on its
    #     very first request
    #   - the refresh token had no user_id either, and
    #     verify_refresh_tokken rejects that, so a session could be
    #     refreshed exactly once and never again
    # Both now go through token_claims, the same as /login.
    new_access_token = create_access_token(access_claims(user))

    new_refresh_token = create_refresh_tokken(refresh_claims(user))

    # -------------------------------------------------
    # 6. Revoke Old Refresh Token
    # -------------------------------------------------
    token_obj.is_revoked = True

    # -------------------------------------------------
    # 7. Store New Refresh Token
    # -------------------------------------------------

    # One setting drives the JWT's exp, this row, and the cookie
    # below. The 7 here was a bare literal while the JWT itself was
    # minted for 1 day, so the row claimed a lifetime the token did
    # not have.
    refresh_lifetime = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    new_db_token = Refresh_Tokken(
        user_id=token_obj.user_id,
        token_hash=Hash.hash_token(new_refresh_token),
        is_revoked=False,
        expires_at=datetime.now(timezone.utc) + refresh_lifetime,
    )

    db.add(new_db_token)

    await db.commit()

    # -------------------------------------------------
    # 8. Store Refresh Token in HttpOnly Cookie
    # -------------------------------------------------
    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=int(refresh_lifetime.total_seconds()),
    )

    # -------------------------------------------------
    # 9. Return New Access Token
    # -------------------------------------------------

    return Token(
        access_token=new_access_token,
        token_type="bearer",
        # The client has to be given the replacement: the old one was
        # just revoked above, so without this the next /refresh would
        # present a dead token and the session would end.
        refresh_token=new_refresh_token,
    )

