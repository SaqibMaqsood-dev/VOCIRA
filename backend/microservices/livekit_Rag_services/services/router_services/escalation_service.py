from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.microservices.livekit_Rag_services.repository.escalation_repository import (
    EsclationRepository,
)

from backend.microservices.livekit_Rag_services.schema.escalation_schema import (
    CreateEscalation,
    EscalationPatch,
)


class EscalationService:

    def __init__(self):
        self.escalation_repo = EsclationRepository()

    # ============================================================
    # CREATE
    # ============================================================

    async def create_escalation(
        self,
        db: AsyncSession,
        data: CreateEscalation,
    ):
        escalation = await self.escalation_repo.create(
            data=data,
            db=db,
        )

        if not escalation:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error while creating escalation",
            )

        return escalation

    # ============================================================
    # GET ALL
    # ============================================================

    async def get_all_escalations(
        self,
        db: AsyncSession,
        limit: int = 10,
        skip: int = 0,
    ):
        return await self.escalation_repo.get_multi(
            db=db,
            limit=limit,
            skip=skip,
        )

    # ============================================================
    # GET BY ID
    # ============================================================

    async def get_escalation_by_id(
        self,
        db: AsyncSession,
        id_value: UUID,
    ):
        escalation = await self.escalation_repo.get_escalation_by_id(
            db=db,
            id_value=id_value,
        )

        if not escalation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No escalation found with id {id_value}",
            )

        return escalation

    # ============================================================
    # OCCURRED ESCALATION STATS
    # ============================================================

    async def get_occurred_escalations(
        self,
        db: AsyncSession,
    ):
        stats = await self.escalation_repo.get_occurred_escalation_stats(
            db=db,
        )

        if not stats:
            return {
                "occurred_escalations": 0,
                "occurred_percentage": 0,
            }

        return stats

    # ============================================================
    # PARTIAL UPDATE
    # ============================================================

    async def partial_update_escalation(
        self,
        db: AsyncSession,
        id_value: UUID,
        request: EscalationPatch,
    ):
        escalation = await self.escalation_repo.get_escalation_by_id(
            db=db,
            id_value=id_value,
        )

        if not escalation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No escalation found with id {id_value}",
            )

        data = request.model_dump(
            exclude_unset=True,
            exclude_none=True,
        )

        if not data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields provided for update",
            )

        return await self.escalation_repo.update_escalation(
            db=db,
            escalation=escalation,
            data=data,
        )

    # ============================================================
    # DELETE
    # ============================================================

    async def delete_escalation(
        self,
        db: AsyncSession,
        id_value: UUID,
    ):
        escalation = await self.escalation_repo.get_escalation_by_id(
            db=db,
            id_value=id_value,
        )

        if not escalation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Escalation not found with id {id_value}",
            )

        await self.escalation_repo.delete_escalation(
            db=db,
            escalation=escalation,
        )

        return {
            "message": f"Escalation deleted with id {id_value}",
        }
