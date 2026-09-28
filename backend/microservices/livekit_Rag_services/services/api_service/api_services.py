import httpx
from fastapi import Request

from backend.microservices.livekit_Rag_services.services.http_retry import (
    request_with_retry,
)


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

        # No timeout at all before this: on a phone's connection a
        # stalled request could hang the call's own setup with
        # nothing to time it out.
        response = await request_with_retry(
            "GET",
            url,
            timeout=15.0,
            label="AUTH user record",
            headers=headers,
        )

        response.raise_for_status()

        return response.json()