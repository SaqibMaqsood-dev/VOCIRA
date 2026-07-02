from fastapi import APIRouter, status, Depends, HTTPException
from schema.jwt_token import Token , RefreshToken
from tokken.access_tokken.jtw_tokken import create_access_token
from tokken.refresh_tokken.verify_refresh_tokken import verify_refresh_tokken 
from fastapi import  Response
from hashing.hashing import Hash
from sqlalchemy.ext.asyncio import AsyncSession
from database import database
from sqlalchemy import select , and_
from models.refresh_tokken_model import Refresh_Tokken
from datetime import datetime , timezone , timedelta
from tokken.refresh_tokken import jwt_refresh_tokken

route = APIRouter(tags=["Authentication with refresh_tokken"])


@route.post("/refresh", response_model=Token  )
async def refresh_token(response:Response, data: RefreshToken , db: AsyncSession = Depends(database.get_db)):
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )

    # ⁡⁢⁢⁢hashed refresh tokken ⁡
    hashed_tokken = Hash.hash_token(token=data.refreshtoken)
    
    # ⁡⁢⁢⁢verify refresh tokken ⁡ 
    hash_tokken_result = await db.execute(
        select(Refresh_Tokken).where(and_(
            Refresh_Tokken.token_hash == hashed_tokken,
            Refresh_Tokken.is_revoked == False,
            Refresh_Tokken.expires_at > datetime.now(timezone.utc)
        ))
    )

    tokken_obj =  hash_tokken_result.scalar_one_or_none()
    
    if not tokken_obj :
       raise credentials_exception
    
    #  ⁡⁢⁢⁢verify JWT⁡
    payload  = verify_refresh_tokken(hash_tokken_result , credentials_exception)
    
    # ⁡⁢⁢⁢create_access_tokken⁡
    new_access_token = create_access_token(data={"sub": payload.username})
   
    # ⁡⁢⁢⁢ create_access_tokken⁡ 
    new_refresh_token = jwt_refresh_tokken(data={"sub": payload.username})
    
    hashed_tokken = Hash.hash_token(token=new_refresh_token)

    # ⁡store new refresh token⁡
    new_db_token = Refresh_Tokken(
        user_id=tokken_obj.user_id,
        token_hash=hashed_tokken,
        is_revoked=False,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7)
    )
    
    revoke_previous_tokken =  tokken_obj.is_revoked = True

    db.add(new_db_token)
    await db.commit()
    await db.refresh(new_db_token)
    
    response.set_cookie(
        key="access_token",
        value=new_refresh_token,
        httponly=True,   
        secure=True,    
        samesite="lax",
    )


    return Token(
        access_token=new_access_token,
        token_type="bearer"
    )

