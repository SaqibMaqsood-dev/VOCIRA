from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.helper_functions.base_repository.base_repository import (
    BaseRepository,
)

from backend.microservices.livekit_Rag_services.models.escalation_model import (
    Escalation,
    EscalationStatus,
)


class EsclationRepository(BaseRepository[Escalation]):

    def __init__(self):
        super().__init__(Escalation)

    # ============================================================
    # GET ESCALATION BY ID
    # ============================================================

    async def get_escalation_by_id(
        self,
        db: AsyncSession,
        id_value: UUID,
    ) -> Optional[Escalation]:

        result = await db.execute(
            select(Escalation).where(
                Escalation.id == id_value
            )
        )

        return result.scalar_one_or_none()

    # ============================================================
    # UPDATE ESCALATION
    # ============================================================

    async def update_escalation(
        self,
        db: AsyncSession,
        escalation: Escalation,
        data: dict,
    ) -> Escalation:

        for field, value in data.items():

            if hasattr(escalation, field):
                setattr(
                    escalation,
                    field,
                    value,
                )

        db.add(escalation)

        await db.commit()

        await db.refresh(escalation)

        return escalation

    # ============================================================
    # DELETE ESCALATION
    # ============================================================

    async def delete_escalation(
        self,
        db: AsyncSession,
        escalation: Escalation,
    ) -> None:

        await db.delete(escalation)

        await db.commit()

    # ============================================================
    # OCCURRED ESCALATION STATS
    # ============================================================

    async def get_occurred_escalation_stats(
        self,
        db: AsyncSession,
    ):

        stmt = select(
            func.count(
                Escalation.id
            ).label("total"),

            func.count(
                Escalation.id
            )
            .filter(
                Escalation.status
                != EscalationStatus.pending
            )
            .label("occurred"),
        )

        result = await db.execute(stmt)

        counts = result.one()

        total = counts.total or 0
        occurred = counts.occurred or 0

        if total == 0:
            return None

        return {
            "occurred_escalations": occurred,
            "occurred_percentage": round(
                (occurred / total) * 100,
                2,
            ),
        }

