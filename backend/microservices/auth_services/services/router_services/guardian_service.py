# from uuid import UUID

# from fastapi import HTTPException, status
# from sqlalchemy.ext.asyncio import AsyncSession

# from backend.microservices.auth_services.repository.guardian_repo import (
#     ERPGuardianRepository,
# )


# class ERPGuardianService:

#     def __init__(self):
#         self.repository = ERPGuardianRepository()

#     async def get_erp_guardian_id(
#         self,
#         db: AsyncSession,
#         vocira_user_id: UUID,
#     ) -> str:

#         mapping = await self.repository.get_by_vocira_user_id(
#             db=db,
#             vocira_user_id=vocira_user_id,
#         )

#         if mapping is None:
#             raise HTTPException(
#                 status_code=status.HTTP_404_NOT_FOUND,
#                 detail="ERP Guardian mapping not found for this Parent.",
#             )

#         return mapping.erp_guardian_id

#     async def add_erp_guardian(
#         self,
#         db: AsyncSession,
#         vocira_user_id: UUID,
#         erp_guardian_id: str,
#     ):
#         existing_mapping = await self.repository.get_by_vocira_user_id(
#             db=db,
#             vocira_user_id=vocira_user_id,
#         )

#         if existing_mapping is not None:
#             raise HTTPException(
#                 status_code=status.HTTP_409_CONFLICT,
#                 detail="ERP Guardian mapping already exists for this Parent.",
#             )

#         existing_guardian = await self.repository.get_by_erp_guardian_id(
#             db=db,
#             erp_guardian_id=erp_guardian_id,
#         )

#         if existing_guardian is not None:
#             raise HTTPException(
#                 status_code=status.HTTP_409_CONFLICT,
#                 detail="ERP Guardian is already mapped.",
#             )

#         mapping = await self.repository.create_mapping(
#             db=db,
#             vocira_user_id=vocira_user_id,
#             erp_guardian_id=erp_guardian_id,
#         )

#         return mapping

