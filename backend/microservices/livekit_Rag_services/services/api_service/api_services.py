import httpx
from fastapi import Request


class APIServices:

    def __init__(self, endpoint: str):
        self.endpoint = endpoint

    async def Fetching_data(
        self,
        request: Request,
        endpoint: str | None = None,
    ):

        authorization = request.headers.get("Authorization")

        if not authorization:
            raise ValueError("Authorization header missing")

        headers = {
            "Authorization": authorization
        }

        url = endpoint or self.endpoint

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers=headers,
            )

        response.raise_for_status()

        return response.json()