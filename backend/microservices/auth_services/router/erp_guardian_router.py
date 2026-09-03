# from uuid import UUID

# from fastapi import APIRouter, Depends, status
# from sqlalchemy.ext.asyncio import AsyncSession

# from backend.microservices.auth_services.db import get_db

# from backend.microservices.auth_services.services.router_services.guardian_service import (
#     ERPGuardianService
# )

# from backend.microservices.auth_services.schema.guardian_schema import (
#     AddERPGuardianRequest
# )


# router = APIRouter(
#     prefix="/internal/erp-guardian",
#     tags=["Internal ERP Guardian"],
# )

# guardian_service = ERPGuardianService()


# # ============================================================
# # GET ERP GUARDIAN ID
# # ============================================================

# @router.get("/{user_id}")
# async def get_erp_guardian_id(
#     user_id: UUID,
#     db: AsyncSession = Depends(get_db),
# ):
#     erp_guardian_id = await guardian_service.get_erp_guardian_id(
#         db=db,
#         vocira_user_id=user_id,
#     )

#     return {
#         "erp_guardian_id": erp_guardian_id,
#     }


# # ============================================================
# # ADD ERP GUARDIAN MAPPING
# # ============================================================

# @router.post(
#     "",
#     status_code=status.HTTP_201_CREATED,
# )
# async def add_erp_guardian(
#     data: AddERPGuardianRequest,
#     db: AsyncSession = Depends(get_db),
# ):
#     mapping = await guardian_service.add_erp_guardian(
#         db=db,
#         vocira_user_id=data.vocira_user_id,
#         erp_guardian_id=data.erp_guardian_id,
#     )

#     return {
#         "vocira_user_id": mapping.vocira_user_id,
#         "erp_guardian_id": mapping.erp_guardian_id,
#     }