from typing import Optional, Sequence
from sqlalchemy.ext.asyncio import AsyncSession
from backend.microservices.livekit_Rag_services.models import escalation_model
from backend.microservices.livekit_Rag_services.models import session_model 
from backend.helper_functions.base_repository import base_repository
from backend.helper_functions.base_repository.base_repository import BaseRepository
from backend.microservices.livekit_Rag_services.models.escalation_model import Escalation
from backend.microservices.livekit_Rag_services.models import message_model

class EsclationRepository(BaseRepository[Escalation]):

    def __init__(self ):
        super().__init__(Escalation)

