from uuid import UUID
from typing import Generic, TypeVar, Any, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


ModelType = TypeVar("ModelType")


class BaseRepository(Generic[ModelType]):

    def __init__(self, model_cls: type[ModelType]):
        self.model_cls = model_cls

    # =========================================================
    # GET BY ID
    # =========================================================

    async def get_by_id(
        self,
        db: AsyncSession,
        id: UUID,
    ) -> ModelType | None:

        return await db.get(
            self.model_cls,
            id,
        )

    # =========================================================
    # GET MULTIPLE
    # =========================================================

    async def get_multi(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 10,
    ) -> Sequence[ModelType]:

        query = (
            select(self.model_cls)
            .offset(skip)
            .limit(limit)
        )

        result = await db.execute(query)

        return result.scalars().all()

    # =========================================================
    # CREATE
    # =========================================================

    async def create(
        self,
        db: AsyncSession,
        data: dict[str, Any],
    ) -> ModelType:

        instance = self.model_cls(**data)

        db.add(instance)

        # Flush sends INSERT to DB without committing.
        # This allows generated IDs to become available.
        await db.flush()
        
        await db.refresh(instance)

        return instance

    # =========================================================
    # UPDATE
    # =========================================================

    async def update(
        self,
        db: AsyncSession,
        id: UUID,
        data: dict[str, Any],
    ) -> ModelType | None:

        instance = await db.get(
            self.model_cls,
            id,
        )

        if instance is None:
            return None

        for key, value in data.items():

            if hasattr(instance, key):
                setattr(
                    instance,
                    key,
                    value,
                )

        await db.flush()

        await db.refresh(instance)

        return instance

    # =========================================================
    # PARTIAL UPDATE
    # =========================================================

    async def partial_update(
        self,
        db: AsyncSession,
        id: UUID,
        data: dict[str, Any],
    ) -> ModelType | None:

        instance = await db.get(
            self.model_cls,
            id,
        )

        if instance is None:
            return None

        for key, value in data.items():

            if hasattr(instance, key):
                setattr(
                    instance,
                    key,
                    value,
                )

        await db.flush()

        await db.refresh(instance)

        return instance

    # =========================================================
    # DELETE
    # =========================================================

    async def delete(
        self,
        db: AsyncSession,
        id: UUID,
    ) -> bool:

        instance = await db.get(
            self.model_cls,
            id,
        )

        if instance is None:
            return False

        await db.delete(instance)

        await db.flush()

        return True