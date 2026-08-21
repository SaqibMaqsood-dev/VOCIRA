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

        # --------------------------------
        # 1. Check existing email
        # --------------------------------
        if request.email:
            result = await db.execute(
                select(Users).where(Users.email == request.email)
            )

            existing_user = result.scalar_one_or_none()

            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="User already exists",
                )

        # --------------------------------
        # 2. Get role from database
        # --------------------------------
        result = await db.execute(
            select(Role).where(
                Role.name.ilike(request.role.strip())
            )
        )

        role_obj = result.scalar_one_or_none()

        if role_obj is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Role '{request.role}' not found",
            )

        role_name = role_obj.name.lower()

        # --------------------------------
        # 3. Guest
        # --------------------------------
        if role_name == "guest":

            guest_identifier = uuid.uuid4().hex[:8]

            data = {
                "name": f"guest_{guest_identifier}",
                "parent_id": None,
                "email": f"guest_{guest_identifier}@guest.local",
                "password_hashed": None,
                "role_id": role_obj.role_id,
                "phone_number": None,
                "address": None,
                "location": None,
                "date_birth": None,
            }

        # --------------------------------
        # 4. Guardian / Parent
        # --------------------------------
        elif role_name in ("guardian", "parent"):

            if not request.parent_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="parent_id is required for guardian",
                )

            # One ERP parent ID = one VOCIRA guardian account
            result = await db.execute(
                select(Users).where(
                    Users.parent_id == request.parent_id
                )
            )

            existing_parent = result.scalar_one_or_none()

            if existing_parent:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Guardian with this parent_id already exists",
                )

            hashed_password = Hash.get_hash_password(
                request.password
            )

            data = {
                "name": request.name,
                "parent_id": request.parent_id,
                "email": request.email,
                "password_hashed": hashed_password,
                "role_id": role_obj.role_id,
                "phone_number": getattr(request, "phone_number", None),
                "address": getattr(request, "address", None),
                "location": getattr(request, "location", None),
                "date_birth": getattr(request, "date_birth", None),
            }

        # --------------------------------
        # 5. Admin
        # --------------------------------
        elif role_name == "admin":

            hashed_password = Hash.get_hash_password(
                request.password
            )

            data = {
                "name": request.name,
                "parent_id": None,
                "email": request.email,
                "password_hashed": hashed_password,
                "role_id": role_obj.role_id,
                "phone_number": getattr(request, "phone_number", None),
                "address": getattr(request, "address", None),
                "location": getattr(request, "location", None),
                "date_birth": getattr(request, "date_birth", None),
            }

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid or unsupported role: '{role_name}'",
            )

        # --------------------------------
        # 6. Create user
        # --------------------------------
        user = await self.user_repo.create(
            db=db,
            data=data,
        )

        await db.commit()
        await db.refresh(user)

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


