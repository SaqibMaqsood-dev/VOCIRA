from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import database
from models import session_model
from schema import session_schema
from typing import List
from tokken.access_tokken.get_current_user import current_user
from services.rbac.required_permission import require_permission

router = APIRouter(prefix="/sessions", tags=["Sessions"])

# ⁡⁢⁢⁢
#  CREATE SESSION⁡

@router.post("/create_session", response_model=session_schema.SessionResponse)
async def create_session(   
    request: session_schema.SessionCreate,
    db: AsyncSession = Depends(database.get_db),
    current_user     = Depends(current_user),           
    _=Depends(require_permission("session.create"))
):  
    
    try:
        
        new_session   =   session_model.Session(
            user_id   =   current_user.user_id,
            title     =   request.title ) 
            
        db.add(new_session)
        await db.commit()
        await db.refresh(new_session)

        return new_session

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# GET ALL SESSIONS

@router.get("/", response_model=List[session_schema.SessionResponse])
async def get_sessions(db: AsyncSession = Depends(database.get_db)):
    try:
        query = select(session_model.Session).order_by(session_model.Session.id.desc())
        result = await db.execute(query)
        
        sessions = result.scalars().all()
        if not sessions:
            raise HTTPException(status_code=404, detail="No sessions found")
        return sessions
   
    except HTTPException:
        raise
  
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# GET SESSION BY ID
@router.get("/{id}", response_model=session_schema.SessionResponse)
async def get_session_by_id(id: int, db: AsyncSession = Depends(database.get_db)):
    try:
        result = await db.execute(select(session_model.Session).where(session_model.Session.id == id))
        session = result.scalar_one_or_none()

        if not session:
            raise HTTPException(status_code=404,  detail=f"No session found with id {id}")
        return session
    
    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

# DELETE SESSION
@router.delete("/{id}")
async def delete_session(id: int, db: AsyncSession = Depends(database.get_db)):
    try:
        result = await db.execute(select(session_model.Session).where(session_model.Session.id == id) )

        session = result.scalar_one_or_none()

        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"No session found with id {id}"
            )

        await db.delete(session)
        await db.commit()

        return {"message": f"Session deleted with id {id}"}

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
    
@router.put("/{id}")
async def update_session(
    request: session_schema.SessionCreate,
    id: int,
    db: AsyncSession = Depends(database.get_db)
):
    try:
        result = await db.execute(
            select(session_model.Session).where(session_model.Session.id == id)
        )
        session = result.scalar_one_or_none()

        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"No session found with id {id}"
            )
        
        session.title = request.title

        await db.commit()
        await db.refresh(session)

        return {
            "message": "Session updated successfully"
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@router.patch("/{id}")
async def partial_update_session(
    request: session_schema.SessionPatch,
    id: int,
    db: AsyncSession = Depends(database.get_db)
):
    try:
        result = await db.execute(
            select(session_model.Session).where(session_model.Session.id == id)
        )
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"No session found with id {id}"
            )
        data = request.model_dump(exclude_unset=True)

        for key, value in data.items():
            setattr(session, key, value)

        await db.commit()
        await db.refresh(session)
        return {
            "message": "Session partially updated",
            "updated_fields": data
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e))
    
    