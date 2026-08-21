from uuid import UUID
import httpx


class AuthClient:

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    async def get_user(self, user_id: UUID) -> dict:

        url = f"{self.base_url}/internal/users/{user_id}"

        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()

            return response.json()