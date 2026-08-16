# from database.database import AsyncSession
# from fastapi import Depends , HTTPException
# from backend.microservices.auth_services.services.tokken.access_tokken.get_current_user import current_user
# from database.database import get_db
# from backend.microservices.livekit_Rag_serivces.services.rbac.get_permisions import get_user_permissions
# # 

# def require_permission(permission: str):
#     async def checker(
#         current_user = Depends(current_user),
#         db: AsyncSession = Depends(get_db)
#     ):
#         permissions = await get_user_permissions(db, current_user.user_id)

#         if permission not in permissions:
#             raise HTTPException(403, "You are not authenticated")
#         user_id = current_user.user_id 
#         return current_user

#     return checker
