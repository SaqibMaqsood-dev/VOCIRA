# from sqlalchemy import select
# from models.role_permission_model import role_permissions


# async def assign_permission_role(db, role_id: int, permission_id: int):

#     result = await db.execute(
#         select(role_permissions).where(
#             role_permissions.role_id == role_id,
#             role_permissions.permission_id == permission_id
#         )
#     )

#     existing = result.first()
    
#     if existing:
#         return {"message": "Permission already assigned"}

#     await db.add(existing)

#     await db.commit()

#     return {"message": "Permission assigned successfully"}