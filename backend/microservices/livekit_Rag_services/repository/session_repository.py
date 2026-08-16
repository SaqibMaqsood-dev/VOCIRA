
from typing import Optional, Sequence
from sqlalchemy.ext.asyncio import AsyncSession
from backend.helper_functions.base_repository.base_repository import BaseRepository
from backend.microservices.livekit_Rag_services.models import (
    session_model
)
from backend.helper_functions.database import SessionLocal
from backend.microservices.livekit_Rag_services.core.rabitmq import RabbitMQ
from sqlalchemy import select
from datetime import datetime , timezone



class SessionRepository(BaseRepository[session_model.Session]):
    def __init__(self):
        super().__init__(session_model.Session)

        
    async def session_create(self, user_id):

        async with SessionLocal() as db:

            producer = RabbitMQ()

            new_session = session_model.Session(
                user_id=user_id,
                title="Voice Agent Session",
                status=session_model.SessionStatus.active,
            )
            
            db.add(new_session)

            await db.commit()
            await db.refresh(new_session)

            message = {
                "session_id": str(new_session.id)
            }

            await producer.producer(message=message)

            return new_session
    
    @staticmethod  
        
    async def close_session_by_id(session_id: any ):
          async with SessionLocal() as db:
           
            try:
                clean_session_id = int(session_id)
            except (ValueError, TypeError):
                print(f"❌ [Session Cleanup] Invalid session_id format received: {session_id}")
                return
    
            try:
                stmt = select(session_model.Session).where(session_model.Session.id == clean_session_id)
                result = await db.execute(stmt) 
                session = result.scalars().first()
    
                if not session:
                    print(f"⚠️ [Session Cleanup] No session row found for Session ID: {clean_session_id}")
                    return
                
                if session.status == session_model.SessionStatus.closed:
                    print(f"ℹ️ [Session Cleanup] Session {clean_session_id} is already closed.")
                    return
                
                # Close it cleanly
                session.status = session_model.SessionStatus.closed
                session.end_at = datetime.now(timezone.utc).replace(tzinfo=None)
                await db.commit()
                print(f"🔒 [Session Cleanup] Cleanly deactivated session ID: {clean_session_id}")
    
            except Exception as e:
                await db.rollback()
                print(f"❌ [Session Cleanup Error] Database transaction failed: {e}")
    
    

 