from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.helper_functions.database import get_db
from backend.microservices.livekit_Rag_services.schema import session_schema
from backend.microservices.livekit_Rag_services.services.router_services.session_service import SessionService
from uuid import UUID

router = APIRouter(prefix="/sessions", tags=["Sessions"])

ss_service = SessionService()



@router.get(
    "/",
    response_model=List[session_schema.SessionResponse]
)
async def get_sessions(
    db: AsyncSession = Depends(get_db)
):
    return await ss_service.get_all_sessions(db=db)


@router.get(
    "/{id}",
    response_model=session_schema.SessionResponse
)
async def get_session_with_id(
    id: UUID,
    db: AsyncSession = Depends(get_db)
):
    return await ss_service.get_session_by_id(
        db=db,
        id_value=id
    )


@router.delete("/{id}")
async def delete_session(
    id: UUID,
    db: AsyncSession = Depends(get_db)
):
    return await ss_service.delete_session(
        db=db,
        id_value=id
    )


@router.put("/{id}")
async def update_session(
    request: session_schema.SessionCreate,
    id: UUID,
    db: AsyncSession = Depends(get_db)
):
    return await ss_service.update_session(
        db=db,
        id_value=id,
        request=request
    )


@router.patch("/{id}")
async def partial_update_session(
    request: session_schema.SessionPatch,
    id: UUID,
    db: AsyncSession = Depends(get_db)
):
    return await ss_service.partial_update_session(
        db=db,
        id_value=id,
        request=request
    )

