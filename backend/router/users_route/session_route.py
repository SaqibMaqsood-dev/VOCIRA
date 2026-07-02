from tokken.access_tokken.get_current_user import current_user
from services.rbac.required_permission import require_permission
from services.router_services import session_logic
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends
from schema import session_schema
from database import database
from typing import List


router = APIRouter(prefix="/sessions", tags=["Sessions"])

@router.post("/create_session", response_model=session_schema.SessionResponse)
async def create_session(
    request: session_schema.SessionCreate,
    db: AsyncSession = Depends(database.get_db),
    current_user=Depends(current_user),
    _=Depends(require_permission("session.create"))
):
    return await session_logic.create_session(db=db, request=request, current_user=current_user)


@router.get("/", response_model=List[session_schema.SessionResponse])
async def get_sessions(db: AsyncSession = Depends(database.get_db)):
    return await session_logic.get_all_sessions(db=db)


@router.get("/{id}", response_model=session_schema.SessionResponse)
async def get_session_by_id(id: int, db: AsyncSession = Depends(database.get_db)):
    return await session_logic.get_session_by_id(db=db, id_value=id)


@router.delete("/{id}")
async def delete_session(id: int, db: AsyncSession = Depends(database.get_db)):
    return await session_logic.delete_session(db=db, id_value=id)


@router.put("/{id}")
async def update_session(
    request: session_schema.SessionCreate,
    id: int,
    db: AsyncSession = Depends(database.get_db)
):
    return await session_logic.update_session(db=db, id_value=id, request=request)


@router.patch("/{id}")
async def partial_update_session(
    request: session_schema.SessionPatch,
    id: int,
    db: AsyncSession = Depends(database.get_db)
):
    return await session_logic.partial_update_session(db=db, id_value=id, request=request)



