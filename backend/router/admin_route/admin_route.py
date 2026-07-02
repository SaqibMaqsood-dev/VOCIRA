from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, asc, or_
from models import  role_model , permision_model , role_permission_model
from tokken.access_tokken.get_current_user import current_user
from services.rbac.required_permission import require_permission
from services.rbac import assign_user_role
from database import database



router = APIRouter(prefix="/admin", tags=["Admin"])





# ---------------- ASSIGN ROLE ----------------
@router.post("/assign-role/{user_id}/{role_id}")
async def assign_role(
    user_id: int,
    role_id: int,
    db: AsyncSession = Depends(database.get_db)
):

    return await assign_user_role.assign_role_to_user(db, user_id, role_id)



# ---------------- Permission Assigned Role----------------
@router.post("/assign-role-permission/{role_id}/{permission_id}")
async def assign_role(
    role_id: int,
    permission_id: int,
    db: AsyncSession = Depends(database.get_db)
):

    # Role 
    role = (await db.execute(
        select(role_model.Role).where(role_model.Role.role_id == role_id)

    )).scalar_one_or_none()

    if not role :
        raise HTTPException(status_code=404 , detail="user not found")

    permission = (await db.execute(
        select(permision_model.Permission).where(permision_model.Permission.id == permission_id)

    )).first()

    if not permission:
        raise HTTPException(404, "Permission not found")

    role_permissions = (await db.execute(
        select(role_permission_model.role_permissions).where(
            role_permission_model.role_permissions.role_id == role_id,
            role_permission_model.role_permissions.permission_id == permission_id,
        )
    )).scalar_one_or_none()
    
    
    if role_permissions:
        raise HTTPException(400, "Permission already assigned")

    new_exsistence = role_permission_model.role_permissions(
        role_id = role_id,
        permission_id = permission_id
    )
    
    db.add(new_exsistence)
    await db.commit()   


    return {
        "message" : "Permission assigned to role successfully"
    }




# ---------------- Remove Assigned Permission----------------
@router.post("/remove-role-permission/{role_id}/{permission_id}")
async def assign_role(
    role_id: int,
    permission_id: int,
    db: AsyncSession = Depends(database.get_db)
):

    exsisting = (await db.execute(
             select(role_permission_model.role_permissions)
             .where(role_permission_model.role_permissions.role_id== role_id ,
                    role_permission_model.role_permissions.permission_id == permission_id)
             ))
    
    result = exsisting.scalar_one_or_none()

    if not result :
        raise HTTPException(status_code=404,detail= "Not Found")
   
    await db.delete(result)
    await db.commit()   


    return {
        "message" : "permission removed"
    }


