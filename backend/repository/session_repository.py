from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime , timezone
from repository import base_repository
from typing import Optional, Sequence 
from models import session_model




async def get_all_sessions(db: AsyncSession) -> Sequence[session_model.Session]:
    return await base_repository.get_all(
        db=db,
        model=session_model.Session,
        order_by=session_model.Session.id.desc(),
    )


async def get_session_by_id(db: AsyncSession, id_value: int) -> Optional[session_model.Session]:
    return await base_repository.get_by_id(db=db, model=session_model.Session, id_value=id_value)


async def create_session(db: AsyncSession, session: session_model.Session) -> session_model.Session:
    return await base_repository.create(db=db, instance=session)


async def update_session(db: AsyncSession, session: session_model.Session, data: dict) -> session_model.Session:
    return await base_repository.update(db=db, instance=session, data=data)


async def delete_session(db: AsyncSession, session: session_model.Session) -> None:
    await base_repository.delete_by_id(db=db, model=session_model.Session, id_value=session.id)




async def get_session_by_id_raw(db: AsyncSession, session_id: int):
    """Raw fetch with no 404 raise — used internally by close_session logic."""
    return await base_repository.get_by_id(
        db=db,
        model=session_model.Session,
        id_value=session_id
    )

async def create_session_record(db: AsyncSession, user_id) -> session_model.Session:
    new_session = session_model.Session(
        user_id=user_id,
        title="Voice Agent Session",
        status=session_model.SessionStatus.active,
    )
    return await base_repository.create(db=db, instance=new_session)

async def close_session_record(db: AsyncSession, session: session_model.Session) -> None:
    data = {
        "status": session_model.SessionStatus.closed,
        "end_at": datetime.now(timezone.utc).replace(tzinfo=None),
    }
    await base_repository.update(db=db, instance=session, data=data)