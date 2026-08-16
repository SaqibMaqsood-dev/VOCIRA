from backend.microservices.livekit_Rag_services.services.router_services.session_service import SessionService
from backend.microservices.livekit_Rag_services.core.config import settings
from backend.microservices.livekit_Rag_services.services.api_service.api_services import APIServices 
from fastapi import HTTPException
from backend.microservices.livekit_Rag_services.services.router_services.session_service import SessionService
from backend.microservices.livekit_Rag_services.schema.livekit_schema import  LivekitTokkenResponse
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import status
from fastapi import HTTPException, status
from livekit.api import AccessToken, VideoGrants

# from . import voice_pipeline 

 
class LivekitServices :

        def __init__(self):

            self.api_integrate = APIServices(endpoint="http://auth-service:8000/users/me")
            self.ss_service    = SessionService()
            
        # -------------------- LIVEKIT --------------------
        async def create_user_room_token(self, db: AsyncSession, current_user) -> LivekitTokkenResponse:
            user_record = await self.api_integrate.Fetching_data()
            
            if not user_record:
                raise HTTPException(404, "User not found")
            
            session_data = await self.ss_service.create_session(users_id=current_user.user_id)
            if not session_data or "session_id" not in session_data:
                raise HTTPException(500, "Failed to initiate voice backend infrastructure session token.")
            
            real_session_id = session_data["session_id"]
            room = f"room-{real_session_id}"

            livekit = LivekitServices(
                user_id=current_user.user_id,
                user_role=user_record.role.value if hasattr(user_record.role, "value") else str(user_record.role),
            )

            token = livekit.livekit_token(
                api_key=settings.LIVEKIT_API_KEY,
                api_secret=settings.LIVEKIT_API_SECRET,
                room_name=room,
                user_name=user_record.name
            )
            
            return LivekitTokkenResponse(tokken=token, room=room, url=settings.LIVEKIT_URL)

        
        async def create_guest_room_token(self):

            # 1. Create session in database
            session = await self.ss_service.create_session(
                user_id=None
            )
    
            if not session:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create session"
                )

            # 2. Get UUID from SQLAlchemy model
            session_id = str(session.id)

            # 3. Use session UUID as LiveKit room name
            room_name = f"room-{session_id}"

            # 4. Generate LiveKit access token
            token = (
                AccessToken(
                    api_key=settings.LIVEKIT_API_KEY,
                    api_secret=settings.LIVEKIT_API_SECRET
                )
                .with_identity(f"guest-{session_id}")
                .with_name("Guest")
                .with_grants(
                    VideoGrants(
                        room_join=True,
                        room=room_name,
                    )
                )
            )

            # 5. Return API response
            return {
                "session_id": session_id,
                "room_name": room_name,
                "token": token.to_jwt(),
            }