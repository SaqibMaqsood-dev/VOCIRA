from backend.helper_functions.base_repository.base_repository import BaseRepository
from backend.microservices.auth_services.models.user_model import Users
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

class UserRepository(BaseRepository[Users]):
    def __init__(self):
        super().__init__(Users)

    
    async def get_by_email(
        self,
        db: AsyncSession,
        email: str
    ) -> Users| None:

        
        query = select(Users).where(Users.email == email)

        result = await db.execute(query)

        return result.scalar_one_or_none()

        