from typing import Optional, Sequence
from sqlalchemy.ext.asyncio import AsyncSession
from backend.microservices.livekit_Rag_services.models import escalation_model
from backend.microservices.livekit_Rag_services.models import session_model 
from backend.helper_functions.base_repository import base_repository
from backend.helper_functions.base_repository.base_repository import BaseRepository
from backend.microservices.livekit_Rag_services.models.escalation_model import Escalation , EscalationStatus
from backend.microservices.livekit_Rag_services.models import message_model
from sqlalchemy import select , func
from backend.helper_functions.database import SessionLocal
from fastapi import HTTPException , status

class EsclationRepository(BaseRepository[Escalation]):

    def __init__(self ):
        super().__init__(Escalation)


class EsclationRepository:
    # ... your existing repo methods ...

    async def get_occurred_escalation_stats(self, db: AsyncSession):
        stmt = select(
            func.count(Escalation.id).label("total"),
            func.count(Escalation.id).filter(Escalation.status != EscalationStatus.pending).label("occurred")
        )
        
        result = await db.execute(stmt)
        counts = result.one()

        total = counts.total or 0
        occurred = counts.occurred or 0

        if total == 0:
            return None

        return {
            "occurred_escalations": occurred,
            "occurred_percentage": round((occurred / total) * 100, 2)
        }