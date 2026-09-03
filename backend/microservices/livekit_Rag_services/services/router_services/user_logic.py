# # from backend.microservices.livekit_Rag_serivces.services.livekit.livekit_services.livekit_room_service import LivekitServices
# # from backend.microservices.livekit_Rag_serivces.services.session_services.session_create import SessionCreate
# # from sqlalchemy.ext.asyncio import AsyncSession
# # from backend.microservices.livekit_Rag_serivces.models import role_model , user_model
# # from fastapi import HTTPException, status
# # from backend.microservices.livekit_Rag_serivces.repository import base_repository
# # from backend.microservices.livekit_Rag_serivces.repository import user_repository
# # from backend.microservices.livekit_Rag_serivces.core.config import settings
# # from backend.microservices.auth_services.services.hashing_service.hashing import Hash
# # from schema import user_schema
# # import uuid


# # # -------------------- AUTHORIZATION HELPER --------------------
# # async def _authorize(user, current_user, id_value: int):
# #     if not user:
# #         raise HTTPException(404, "User not found")
# #     if current_user.role.name != "admin" and current_user.id != id_value:
# #         raise HTTPException(403, "Not allowed")


# # # -------------------- GET --------------------
# # async def get_all_users(db: AsyncSession , limit , skip):
# #     users = await user_repository.get_all_users(db=db , limit = limit , skip = skip)
# #     if not users:
# #         raise HTTPException(404, "No users found")
# #     return users


# # async def get_user_by_id(db: AsyncSession, id_value: int, current_user):
# #     user = await user_repository.get_user_by_id(db=db, id_value=id_value)
# #     await _authorize(user, current_user, id_value)
# #     return user


# # # -------------------- DELETE --------------------
# # async def delete_user(db: AsyncSession, id_value: int, current_user):
# #     user = await user_repository.get_user_by_id(db=db, id_value=id_value)
# #     await _authorize(user, current_user, id_value)
# #     await user_repository.delete_user(db=db, user=user)
# #     return {"message": f"User deleted with id {id_value}"}


# # # -------------------- UPDATE --------------------
# # async def update_user_full(db: AsyncSession, id_value: int, request, current_user):
# #     user = await user_repository.get_user_by_id(db=db, id_value=id_value)
# #     await _authorize(user, current_user, id_value)

# #     data = {
# #         "name":         request.name,
# #         "email":        request.email,
# #         "password":     Hash.get_hash_password(request.password),
# #         "date_birth":   request.date_birth,
# #         "phone_number": request.phone_number,
# #         "address":      request.address,
# #         "location":     request.location,
# #     }

# #     await user_repository.update_user_full(db=db, user=user, data=data)
# #     return {"message": "User updated"}


# # async def update_user_partial(db: AsyncSession, id_value: int, request, current_user):
# #     user = await user_repository.get_user_by_id(db=db, id_value=id_value)
# #     await _authorize(user, current_user, id_value)

# #     data = request.model_dump(exclude_unset=True)
# #     if "password" in data:
# #         data["password"] = Hash.get_hash_password(data["password"])

# #     await user_repository.update_user_partial(db=db, user=user, data=data)
# #     return {"message": "User updated", "updated_fields": data}


# # # -------------------- SEARCH --------------------
# # async def search_users(db: AsyncSession, search_term: str):
# #     users = await user_repository.search_users(db=db, search_term=search_term)
# #     if not users:
# #         raise HTTPException(404, "No matching users found")
# #     return users



# # user_logic.py — add this

# async def create_user(db: AsyncSession, request):
#     # check existing user — repository handles the query
#     existing_user = await user_repository.get_user_by_email(db=db, email=request.email)
#     if existing_user:
#         raise HTTPException(400, "User already exists")

#     # get role — repository handles the query
#     role_obj = await user_repository.get_role_by_name(db=db, name=request.role)
#     if not role_obj:
#         raise HTTPException(400, "Role not found")

#     # guest vs normal — pure business logic, stays in service
#     if role_obj.name == "guest":
#         new_user = user_model.Users(
#             name=f"guest_{uuid.uuid4().hex[:8]}",
#             email=f"guest_{uuid.uuid4().hex[:8]}@guest.local",
#             password=None,
#             role_id=role_obj.role_id,
#             date_birth=None,
#             phone_number=None,
#             address=None,
#             location=None
#         )
#     else:
#         new_user = user_model.Users(
#             name=request.name,
#             email=request.email,
#             password=Hash.get_hash_password(request.password),
#             role_id=role_obj.role_id,
#             date_birth=request.date_birth,
#             phone_number=request.phone_number,
#             address=request.address,
#             location=request.location
#         )

#     return await base_repository.create(db=db, instance=new_user)