from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from models import escalation_model
from schema import escalation_schema 
from database import database
from sqlalchemy import select
from typing import List

router = APIRouter(prefix="/escalations", tags=["Escalations"])


@router.post("/create_escalations", response_model=escalation_schema.EscalationResponse)
async def create_escalation(
    request: escalation_schema.CreateEscalation,
    db: AsyncSession = Depends(database.get_db)):

    try:
        new_escalation = escalation_model.Escalation(
            user_id        = 1,
            status         = request.status,
            message_id     =  5,
            assigned_admin = 1,
        )

        db.add(new_escalation)
        await db.commit()
        await db.refresh(new_escalation)
        return new_escalation

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@router.get("/get_escalation", response_model=List[escalation_schema.EscalationResponse])
async def get_escalations(db: AsyncSession = Depends(database.get_db)):
    try:
        result = await db.execute(select(escalation_model.Escalation))
        escalations = result.scalars().all()

        if not escalations:
            raise HTTPException(
                status_code=404,
                detail="No escalations found"
            )

        return escalations

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@router.get("/get_escalation/{id}", response_model=escalation_schema.EscalationResponse)
async def get_escalation_by_id(id: int, db: AsyncSession = Depends(database.get_db)):
    try:
        result = await db.execute(
            select(escalation_model.Escalation).where(
                escalation_model.Escalation.id == id
            )
        )

        escalation = result.scalar_one_or_none()

        if not escalation:
            raise HTTPException(
                status_code=404,
                detail=f"No escalation found with id {id}"
            )

        return escalation

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))




@router.delete("/delete_escalation/{id}")
async def delete_escalation(id: int, db: AsyncSession = Depends(database.get_db)):
    try:
        result = await db.execute(
            select(escalation_model.Escalation).where(
                escalation_model.Escalation.id == id
            )
        )

        escalation = result.scalar_one_or_none()

        if not escalation:
            raise HTTPException(
                status_code=404,
                detail=f"No escalation found with id {id}"
            )

        await db.delete(escalation)
        await db.commit()

        return {"message": f"Escalation deleted with id {id}"}

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    


@router.put("/update_escalation/{id}")
async def update_escalation(
    request: escalation_schema.CreateEscalation,
    id: int,
    db: AsyncSession = Depends(database.get_db)
):
    try:
        result = await db.execute(
            select(escalation_model.Escalation).where(
                escalation_model.Escalation.id == id
            )
        )

        escalation = result.scalar_one_or_none()

        if not escalation:
            raise HTTPException(
                status_code=404,
                detail=f"No escalation found with id {id}"
            )

        escalation.user_id = request.user_id
        escalation.message_id = request.message_id

        await db.commit()
        await db.refresh(escalation)

        return {"message": "Escalation updated successfully"}

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.patch("/update_partial_escalation/{id}")
async def partial_update_escalation(
    request: escalation_schema.EscalationPatch,
    id: int,
    db: AsyncSession = Depends(database.get_db)
):
    try:
        result = await db.execute(
            select(escalation_model.Escalation).where(
                escalation_model.Escalation.id == id
            )
        )

        escalation = result.scalar_one_or_none()

        if not escalation:
            raise HTTPException(
                status_code=404,
                detail=f"No escalation found with id {id}"
            )

        data = request.model_dump(exclude_unset=True)

        for key, value in data.items():
            setattr(escalation, key, value)

        await db.commit()
        await db.refresh(escalation)

        return {
            "message": "Escalation partially updated",
            "updated_fields": data
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.patch("/assign/{id}")
async def assign_escalation(
    id: int,
    admin_id: int,
    db: AsyncSession = Depends(database.get_db)
):
    try:
        result = await db.execute(
            select(escalation_model.Escalation).where(
                escalation_model.Escalation.id == id
            )
        )

        escalation = result.scalar_one_or_none()

        if not escalation:
            raise HTTPException(
                status_code=404,
                detail="Escalation not found"
            )

        escalation.assigned_admin = admin_id

        await db.commit()

        return {"message": f"Escalation assigned to admin {admin_id}"}

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

