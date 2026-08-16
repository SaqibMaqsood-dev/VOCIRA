from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from backend.helper_functions.database import get_db
from backend.microservices.livekit_Rag_services.schema import livekit_schema
from backend.microservices.livekit_Rag_services.services.router_services.message_service import MessageService 
from backend.microservices.livekit_Rag_services.schema import livekit_schema
from backend.helper_functions.token_service.access_tokken.get_current_user import current_user
from backend.microservices.livekit_Rag_services.services.livekit.livekit_services.livekit_room_service import LivekitRoomServices
from backend.microservices.livekit_Rag_services.services.router_services.livekit_services import LivekitServices
from backend.microservices.auth_services.schema import user_schema



livekit_service = LivekitServices()

router = APIRouter(prefix="/livekit", tags=["Livekit"])

# ---------------- LIVEKIT ----------------
@router.post("/live_kit/token", response_model=livekit_schema.LiveKitToken)
async def room_token(
    db: AsyncSession = Depends(get_db),
    current_user: user_schema.User = Depends(current_user),
):
    return await livekit_service.create_user_room_token(db=db, current_user=current_user)


@router.post("/guest/live_kit/token")
async def guest_room_token():
    return await livekit_service.create_guest_room_token()
