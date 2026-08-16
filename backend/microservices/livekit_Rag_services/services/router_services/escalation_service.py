from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.microservices.livekit_Rag_services.repository.escalation_repository import (
    EsclationRepository,
)


class EslcalationService:

    def __init__(self):
        self.escalation_repo = EsclationRepository()

    # ---------------- CREATE ----------------

    async def create_escalation(
        self,
        db: AsyncSession,
        data,
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

    # ---------------- GET ALL ----------------

    async def get_all_escalations(
        self,
        db: AsyncSession,
        limit: int = 10,
        skip: int = 0,
    ):
        escalations = await self.escalation_repo.get_multi(
            db=db,
            limit=limit,
            skip=skip,
        )

        if not escalations:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No escalations found",
            )

        return escalations

    # ---------------- GET BY ID ----------------

    async def get_escalation_by_id(
        self,
        db: AsyncSession,
        id_value: int,
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

    # ---------------- UPDATE ----------------

    async def update_escalation(
        self,
        db: AsyncSession,
        id_value: int,
        request,
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

        data = {
            "user_id": request.user_id,
            "message_id": request.message_id,
        }

        updated_escalation = await self.escalation_repo.update_escalation(
            db=db,
            escalation=escalation,
            data=data,
        )

        return updated_escalation

    # ---------------- PARTIAL UPDATE ----------------

    async def partial_update_escalation(
        self,
        db: AsyncSession,
        id_value: int,
        request,
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

        updated_escalation = await self.escalation_repo.update_escalation(
            db=db,
            escalation=escalation,
            data=data,
        )

        return updated_escalation

    # ---------------- DELETE ----------------

    async def delete_escalation(
        self,
        db: AsyncSession,
        id_value: int,
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

        await self.escalation_repo.delete_escalation(
            db=db,
            escalation=escalation,
        )

        return {
            "message": f"Escalation deleted with id {id_value}"
        }

    # ---------------- ASSIGN ----------------

    async def assign_escalation(
        self,
        db: AsyncSession,
        id_value: int,
        admin_id: int,
    ):
        escalation = await self.escalation_repo.get_escalation_by_id(
            db=db,
            id_value=id_value,
        )

        if not escalation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Escalation not found",
            )

        updated_escalation = await self.escalation_repo.assign_escalation(
            db=db,
            escalation=escalation,
            admin_id=admin_id,
        )

        return updated_escalation

