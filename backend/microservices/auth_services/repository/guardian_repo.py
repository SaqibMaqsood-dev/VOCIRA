# from uuid import UUID

# from sqlalchemy import select
# from sqlalchemy.ext.asyncio import AsyncSession

# from backend.helper_functions.base_repository.base_repository import (
#     BaseRepository,
# )

# from backend.microservices.auth_services.models.ErpGuardian import (
#     ERPGuardianMapping,
# )


# class ERPGuardianRepository(BaseRepository[ERPGuardianMapping]):

#     def __init__(self):
#         super().__init__(ERPGuardianMapping)

#     async def get_by_vocira_user_id(
#         self,
#         db: AsyncSession,
#         vocira_user_id: UUID,
#     ) -> ERPGuardianMapping | None:

#         query = select(ERPGuardianMapping).where(
#             ERPGuardianMapping.vocira_user_id == vocira_user_id
#         )

#         result = await db.execute(query)

#         return result.scalar_one_or_none()

#     async def get_by_erp_guardian_id(
#         self,
#         db: AsyncSession,
#         erp_guardian_id: str,
#     ) -> ERPGuardianMapping | None:

#         query = select(ERPGuardianMapping).where(
#             ERPGuardianMapping.erp_guardian_id == erp_guardian_id
#         )

#         result = await db.execute(query)

#         return result.scalar_one_or_none()

#     async def create_mapping(
#         self,
#         db: AsyncSession,
#         vocira_user_id: UUID,
#         erp_guardian_id: str,
#     ) -> ERPGuardianMapping:

#         mapping = ERPGuardianMapping(
#             vocira_user_id=vocira_user_id,
#             erp_guardian_id=erp_guardian_id,
#         )

#         db.add(mapping)

#         await db.flush()

#         return mapping