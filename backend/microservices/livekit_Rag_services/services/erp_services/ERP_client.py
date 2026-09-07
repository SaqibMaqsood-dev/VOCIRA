import httpx
from fastapi import HTTPException, status

from backend.microservices.livekit_Rag_services.core.config import settings


class ERPClient:

    def __init__(self):

        self.base_url = settings.ERP_BASE_URL.rstrip("/")

        self.headers = {
            "Authorization": (
                f"token "
                f"{settings.ERP_API_KEY}:"
                f"{settings.ERP_API_SECRET}"
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

        # NOTE: yahan pehle poora self.headers chhapta tha, jis mein
        # "token <API_KEY>:<API_SECRET>" hota hai - yaani ERP ki
        # dono chabiyan har request par logs mein chali jati thin.
        # Sirf itna batayein ke auth laga hua hai ya nahi.
        print("=" * 52)
        print("🔎 [ERP CLIENT REQUEST]")
        print(f"URL     : {url}")
        print(f"PARAMS  : {params}")
        print(
            f"AUTH    : "
            f"{'set' if settings.ERP_API_KEY else 'GHAYAB'}"
        )
        print("=" * 52)

        try:

            async with httpx.AsyncClient(
                timeout=10.0
            ) as client:

                response = await client.get(
                    url,
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
        ERP mein nayi cheez banayein.

        Pehle yahan sirf get() tha - poora ERP integration read-only
        tha. Support tickets ke liye likhna bhi zaroori hua.
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
        print("✍️ [ERP CLIENT WRITE]")
        print(f"URL     : {url}")
        print(f"FIELDS  : {sorted(payload.keys())}")
        print(
            f"AUTH    : "
            f"{'set' if settings.ERP_API_KEY else 'GHAYAB'}"
        )
        print("=" * 52)

        try:

            async with httpx.AsyncClient(
                timeout=20.0
            ) as client:

                response = await client.post(
                    url,
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

            # ERPNext apni asli wajah body mein bhejta hai
            # (mandatory field, ghalat link waghera) - wo log
            # mein rakhein, warna sirf "417" hath aata hai.
            print(
                f"❌ [ERP WRITE FAILED] "
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
