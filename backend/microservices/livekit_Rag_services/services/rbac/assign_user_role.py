# from fastapi.routing import APIRouter
# from fastapi import Depends, HTTPException
# from sqlalchemy import select
# from backend.microservices.auth_services.services.tokken.access_tokken.get_current_user import current_user
# from sqlalchemy import select
# from backend.microservices.livekit_Rag_serivces.models.user_role_model import UserRole

# router = APIRouter(prefix="/users", tags=["Users"])


# async def assign_role_to_user(db, user_id: int, role_id: int):

#     # check duplicate
#     existing = (await db.execute(
#         select(UserRole).where(
#             UserRole.user_id == user_id,
#             UserRole.role_id == role_id
#         )
#     )).scalar_one_or_none()

#     if existing:
#         return {"message": "Role already assigned"}

#     db.add(UserRole(user_id=user_id, role_id=role_id))
#     await db.commit()

#     return {"message": "Role assigned successfully"}