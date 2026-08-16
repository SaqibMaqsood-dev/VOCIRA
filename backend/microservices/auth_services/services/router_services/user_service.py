import uuid
from uuid import UUID
from typing import Optional
from sqlalchemy import select
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from backend.microservices.auth_services.models.role_model import Role
from backend.microservices.auth_services.models.user_model import Users
from backend.microservices.auth_services.repository.user_repository import UserRepository
from backend.microservices.auth_services.schema.user_schema import ShowUser
from backend.microservices.auth_services.services.hashing_service.hashing import Hash


class UserServices:

    def __init__(self):
        self.user_repo = UserRepository()

    # ---------------- CREATE USER ----------------

    async def UserCreate(
        self,
        db: AsyncSession,
        request,
    ) -> Users:

        result = await db.execute(
            select(Users).where(Users.email == request.email)
        )
        existing_user = result.scalar_one_or_none()

        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User already exists",
            )

        result = await db.execute(
            select(Role).where(Role.name == request.role)
        )
        role_obj = result.scalar_one_or_none()

        if role_obj is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Role not found",
            )

        if role_obj.name == "guest":

            data = {
                "name": f"guest_{uuid.uuid4().hex[:8]}",
                "email": f"guest_{uuid.uuid4().hex[:8]}@guest.local",
                "password_hashed": None,
                "role_id": role_obj.role_id,
                "phone_number": None,
                "address": None,
                "location": None,
                "date_birth": None,
            }

        else:

            hashed_password = Hash.get_hash_password(request.password)

            data = {
                "name": request.name,
                "email": request.email,
                "password_hashed": hashed_password,
                "role_id": role_obj.role_id,
                "phone_number": request.phone_number,
                "address": request.address,
                "location": request.location,
                "date_birth": request.date_birth,
            }

        user = await self.user_repo.create(
            db=db,
            data=data,
        )

        await db.commit()

        return user

    # ---------------- GET USER ----------------

    async def get_user(
        self,
        user_id: UUID,
        db: AsyncSession,
    ) -> Users:

        user = await self.user_repo.get_by_id(
            db=db,
            id=user_id,
        )

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with id {user_id} not found.",
            )

        return user

    # ---------------- GET ALL USERS ----------------

    async def get_all_users(
        self,
        db: AsyncSession,
        limit: int = 10,
        skip: int = 0,
    ):

        users = await self.user_repo.get_multi(
            db=db,
            limit=limit,
            skip=skip,
        )

        if not users:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No users found.",
            )

        return users

    # ---------------- UPDATE USER ----------------
    async def update_user(
    self,
    user_id: UUID,
    data: dict[str, any],
    db: AsyncSession,
):      

        print("updated_user in user_service")
        
        result = await  self.user_repo.update(
            db=db,
            id=user_id,
            data=data,
        )

        print("====result=====" , result)

        if result is None :
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND , detail= f"User is not avaialble with id {user_id}")


        return result       

    # ---------------- Partial Update USER ----------------

    async def user_partialy_update(
        self,
        user_id: UUID,
        request,
        db: AsyncSession,
    ):

        user = await self.user_repo.get_by_id(
            db=db,
            id=user_id,
        )

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found.",
            )

        data = request.model_dump(exclude_unset=True)

        return await self.user_repo.partial_update(
            db=db,
            id=user_id,
            data=data,
        )

    # ---------------- DELETE USER ----------------

    async def delete_user(
        self,
        user_id       : UUID,
        db            : AsyncSession,
    ):

        user = await self.user_repo.get_by_id(
            db=db,
            id=user_id,
        )

        

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found.",
            )
        
        await self.user_repo.delete(
            db=db,
            id=user_id,
        )

        return {
            "message": f"User {user.name} with id {user_id} deleted successfully."
        }


