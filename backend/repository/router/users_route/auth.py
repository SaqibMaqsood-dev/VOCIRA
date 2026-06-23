from fastapi import APIRouter, status, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import database
from models.user_model import Users
from models.refresh_tokken_model import Refresh_Tokken
from schema.jwt_token import Token
from hashing.hashing import Hash
from tokken.access_tokken.jtw_tokken import create_access_token
from tokken.refresh_tokken.jwt_refresh_tokken import create_refresh_tokken
from sqlalchemy.orm import selectinload

router = APIRouter(tags=["Authentication"])



@router.post("/login", response_model=Token)
async def login_user(
    user_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(database.get_db),
):
    # fetching user 
    result = await db.execute(
        select(Users)
        .where(Users.email == user_data.username)
    )

    # fetching session 
            
   
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not Hash.verify_password(user_data.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    


    # ACCESS TOKEN
    access_token = create_access_token(data={
        "sub": user.email,
        "user_id": user.id
    })
    

     
    print("=================emial=============in=========verify-tokken" , user.email)
    print("=================user_id=============in=========verify-tokken" , user.id)



    #  REFRESH TOKEN
    refresh_token = create_refresh_tokken(data={"sub": user.email})
    hashed_refresh_token = Hash.hash_token(token=refresh_token)

    new_token = Refresh_Tokken(
        user_id = user.id,
        token_hash=hashed_refresh_token,
        is_revoked=False,
        expires_at=30
    )

    db.add(new_token)
    await db.commit()
        
    return Token(
        access_token=access_token,
        token_type="bearer"
    )


