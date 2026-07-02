from fastapi import HTTPException

from sqlalchemy.ext.asyncio import AsyncSession

from models import session_model
from repository import session_repository
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ...core.
from models import session_model 
from database.database import SessionLocal
from datetime import datetime , timezone



async def create_sessoin(users_id) -> dict:
    """Called internally by LiveKit token route — creates session + publishes to RabbitMQ."""
    async with SessionLocal() as db:
        new_session = await session_repository.create_session_record(
            db=db,
            user_id=users_id
        )
        await RabbitMQ().producer(message={"session_id": new_session.id})
        return {"session_id": new_session.id, "status": "active"}


async def close_session_by_id(session_id) -> None:
    """Called internally by LiveKit worker on teardown."""
    try:
        clean_session_id = int(session_id)
    except (ValueError, TypeError):
        print(f"❌ [Session Cleanup] Invalid session_id format: {session_id}")
        return

    async with SessionLocal() as db:
        try:
            session = await session_repository.get_session_by_id_raw(
                db=db,
                session_id=clean_session_id
            )

            if not session:
                print(f"⚠️ [Session Cleanup] No session found for ID: {clean_session_id}")
                return

            if session.status == session_model.SessionStatus.closed:
                print(f"ℹ️ [Session Cleanup] Session {clean_session_id} already closed.")
                return

            await session_repository.close_session_record(db=db, session=session)
            print(f"🔒 [Session Cleanup] Session {clean_session_id} closed.")

        except Exception as e:
            await db.rollback()
            print(f"❌ [Session Cleanup Error] Transaction failed: {e}")

async def get_all_sessions(db: AsyncSession):
    sessions = await session_repository.get_all_sessions(db=db)
    if not sessions:
        raise HTTPException(404, "No sessions found")
    return sessions


async def get_session_by_id(db: AsyncSession, id_value: int):
    session = await session_repository.get_session_by_id(db=db, id_value=id_value)
    if not session:
        raise HTTPException(404, f"No session found with id {id_value}")
    return session


async def update_session(db: AsyncSession, id_value: int, request):
    session = await session_repository.get_session_by_id(db=db, id_value=id_value)
    if not session:
        raise HTTPException(404, f"No session found with id {id_value}")

    await session_repository.update_session(db=db, session=session, data={"title": request.title})
    return {"message": "Session updated successfully"}


async def partial_update_session(db: AsyncSession, id_value: int, request):
    session = await session_repository.get_session_by_id(db=db, id_value=id_value)
    if not session:
        raise HTTPException(404, f"No session found with id {id_value}")

    data = request.model_dump(exclude_unset=True)
    await session_repository.update_session(db=db, session=session, data=data)
    return {"message": "Session partially updated", "updated_fields": data}


async def delete_session(db: AsyncSession, id_value: int):
    session = await session_repository.get_session_by_id(db=db, id_value=id_value)
    if not session:
        raise HTTPException(404, f"No session found with id {id_value}")

    await session_repository.delete_session(db=db, session=session)
    return {"message": f"Session deleted with id {id_value}"}



