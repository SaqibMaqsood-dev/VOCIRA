import httpx
from fastapi import HTTPException, status

from backend.microservices.livekit_Rag_services.core.config import settings
from backend.microservices.livekit_Rag_services.services.http_retry import (
    request_with_retry,
)


class ERPClient:

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        api_secret: str | None = None,
    ):

        # One school's ERP site (see connectors.py). Left out, it is
        # the one in the service settings - the first school's.
        self.base_url = (base_url or settings.ERP_BASE_URL).rstrip("/")

        self._api_key = api_key or settings.ERP_API_KEY

        self.headers = {
            "Authorization": (
                f"token "
                f"{self._api_key}:"
                f"{api_secret or settings.ERP_API_SECRET}"
            ),
            "Accept": "application/json",
        }

    async def get(
        self,
        endpoint: str,
        params: dict | None = None,
    ) -> dict:

        # --------------------------------------------------
        # SECURITY
        # --------------------------------------------------

        if not endpoint.startswith("/api/"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="ERP endpoint is not allowed",
            )

        url = f"{self.base_url}{endpoint}"

        # NOTE: this used to print the whole of self.headers, which
        # contains "token <API_KEY>:<API_SECRET>" - meaning both ERP
        # keys went into the logs on every request. Report only
        # whether auth is set.
        print("=" * 52)
        print("[ERP CLIENT REQUEST]")
        print(f"URL     : {url}")
        print(f"PARAMS  : {params}")
        print(
            f"AUTH    : "
            f"{'set' if self._api_key else 'GHAYAB'}"
        )
        print("=" * 52)

        try:

            response = await request_with_retry(
                "GET",
                url,
                timeout=15.0,
                label=f"ERP GET {endpoint}",
                headers=self.headers,
                params=params,
            )

            response.raise_for_status()

            return response.json()

        except httpx.TimeoutException:

            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="ERP service request timed out",
            )

        except httpx.HTTPStatusError as exc:

            raise HTTPException(
                status_code=exc.response.status_code,
                detail=(
                    f"ERP service returned "
                    f"HTTP {exc.response.status_code}"
                ),
            )

        except httpx.RequestError:

            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Unable to connect to ERP service",
            )
    # ------------------------------------------------------
    # POST  (support tickets ke liye)
    # ------------------------------------------------------

    async def post(
        self,
        endpoint: str,
        payload: dict,
    ) -> dict:
        """
        Create something new in ERP.

        There was only get() here before - the whole ERP integration
        was read-only. Support tickets made writing necessary too.
        """

        # --------------------------------------------------
        # SECURITY  (get() jaisa hi usool)
        # --------------------------------------------------

        if not endpoint.startswith("/api/"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="ERP endpoint is not allowed",
            )

        url = f"{self.base_url}{endpoint}"

        print("=" * 52)
        print("[ERP CLIENT WRITE]")
        print(f"URL     : {url}")
        print(f"FIELDS  : {sorted(payload.keys())}")
        print(
            f"AUTH    : "
            f"{'set' if self._api_key else 'GHAYAB'}"
        )
        print("=" * 52)

        try:

            response = await request_with_retry(
                "POST",
                url,
                timeout=25.0,
                label=f"ERP POST {endpoint}",
                headers={
                    **self.headers,
                    "Content-Type": "application/json",
                },
                json=payload,
            )

            response.raise_for_status()

            return response.json()

        except httpx.TimeoutException:

            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="ERP service request timed out",
            )

        except httpx.HTTPStatusError as exc:

            # ERPNext sends the real reason in the body (a
            # mandatory field, a bad link, and so on) - keep that in
            # the log, or all you have is "417".
            print(
                f"[ERP WRITE FAILED] "
                f"HTTP {exc.response.status_code}: "
                f"{exc.response.text[:400]}"
            )

            raise HTTPException(
                status_code=exc.response.status_code,
                detail=(
                    f"ERP service returned "
                    f"HTTP {exc.response.status_code}"
                ),
            )

        except httpx.RequestError:

            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Unable to connect to ERP service",
            )
