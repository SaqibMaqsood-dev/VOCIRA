import httpx
from fastapi import Request


class APIServices:

    def __init__(self, endpoint: str):
        self.endpoint = endpoint

    async def Fetching_data(self, request: Request):
        
        authorization = request.headers.get("Authorization")

        if not authorization:
            raise ValueError("Authorization header missing")

        headers = {
            "Authorization": authorization
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.endpoint,
                headers=headers
            )

        response.raise_for_status()

        return response.json()