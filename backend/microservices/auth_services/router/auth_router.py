from datetime import datetime, timedelta, timezone

from backend.helper_functions.token_service.access_tokken.jtw_tokken import (
    create_access_token,
)

from backend.helper_functions.token_service.refresh_tokken.jwt_refresh_tokken import (
    create_refresh_tokken,
)

from backend.microservices.auth_services.services.hashing_service.hashing import (
    Hash,
)

from fastapi import APIRouter, Depends, HTTPException, status

from fastapi.security import OAuth2PasswordRequestForm

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from backend.microservices.auth_services.db import get_db

from backend.microservices.auth_services.models.user_model import Users

from backend.microservices.auth_services.models.refresh_tokken import (
    Refresh_Tokken,
)

from backend.microservices.auth_services.schema.token_schema import Token


router = APIRouter(tags=["Authentication"])


# Define default expiration duration (e.g., 7 days)
REFRESH_TOKEN_EXPIRE_DAYS = 7


@router.post("/login", response_model=Token)
async def login(
    user_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):

    # =========================================================
    # 1. Find user + eagerly load role
    # =========================================================

    result = await db.execute(
        select(Users)
        .options(
            selectinload(Users.role)
        )
        .where(
            Users.email == user_data.username
        )
    )

    user = result.scalar_one_or_none()

    # DEBUG
    print("========================================")
    print("LOGIN EMAIL:", user_data.username)
    print("USER FOUND:", user is not None)

    if not user:
        print("❌ USER NOT FOUND")
        print("========================================")

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={
                "WWW-Authenticate": "Bearer"
            },
        )

    print("✅ USER FOUND")
    print("VOCIRA USER ID:", user.user_id)

    # =========================================================
    # 2. Verify password
    # =========================================================

    password_valid = Hash.verify_password(
        plain_password=user_data.password,
        hashed_password=user.password_hashed,
    )

    # DEBUG
    print("PASSWORD VALID:", password_valid)

    if not password_valid:
        print("❌ PASSWORD VERIFICATION FAILED")
        print("========================================")

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={
                "WWW-Authenticate": "Bearer"
            },
        )

    print("✅ PASSWORD VERIFIED")

    # =========================================================
    # 3. Get VOCIRA User ID
    # =========================================================

    user_id = user.user_id

    print(f"🔐 VOCIRA User ID : {user_id}")

    # =========================================================
    # 4. Get role
    # =========================================================

    # user.role ek Role model object hai, enum nahi. Pehle yahan
    # sirf "value" check tha, jo Role par maujood hi nahi - is liye
    # str(user.role) chal jata tha aur JWT mein role ki jagah
    # "<...Role object at 0x...>" chala jata tha.
    if user.role is None:
        role = None
    elif getattr(user.role, "name", None):
        role = user.role.name
    elif hasattr(user.role, "value"):
        role = user.role.value
    else:
        role = str(user.role)

    print(f"👤 Role : {role}")

    # =========================================================
    # 5. Create Access Token
    # =========================================================

    access_token = create_access_token(
        {
            "sub": user.email,
            "user_id": str(user_id),
            "role": role,
            # Naam bhi - warna UI ke paas sirf email hoti hai aur
            # "Muhammad Ahmed" ki jagah "ahmed@test.com" dikhana
            # parta hai. Ye DB mein pehle se mojood hai, is ke
            # liye alag endpoint banana faltu tha.
            "name": user.name,
        }
    )

    print("✅ ACCESS TOKEN CREATED")

    # =========================================================
    # 6. Create Refresh Token & Calculate Expiration
    # =========================================================

    refresh_token = create_refresh_tokken(
        {
            "sub": user.email,
            "user_id": str(user_id),
        }
    )

    # Calculate expiration datetime (UTC)
    expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    print("✅ REFRESH TOKEN CREATED")

    # =========================================================
    # 7. Hash Refresh Token
    # =========================================================

    hashed_refresh_token = Hash.hash_token(
        refresh_token
    )

    # =========================================================
    # 8. Store Refresh Token with expires_at
    # =========================================================

    db.add(
        Refresh_Tokken(
            user_id=user_id,
            token_hash=hashed_refresh_token,
            is_revoked=False,
            expires_at=expires_at,  # <-- Added expires_at here
        )
    )

    await db.commit()

    print("✅ REFRESH TOKEN STORED")
    print("========================================")

    # =========================================================
    # 9. Return Access Token
    # =========================================================

    return Token(
        access_token=access_token,
        token_type="bearer",
    )
