import os

import httpx


class AuthClient:

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

        # Auth service ka /users/internal/ ab shared secret maangta hai.
        # Dono services ki .env mein ye ek jaisi honi chahiye.
        self.internal_key = os.getenv(
            "INTERNAL_SERVICE_KEY",
            "vocira-internal-dev-key-change-me",
        )

    async def get_internal_user(
        self,
        vocira_user_id,
    ) -> dict:

        url = (
            f"{self.base_url}"
            f"/users/internal/{vocira_user_id}"
        )

        print("=" * 70)
        print("🔐 [AUTH CLIENT]")
        print(f"Auth URL        : {url}")
        print(f"VOCIRA User ID  : {vocira_user_id}")
        print("=" * 70)

        try:
            async with httpx.AsyncClient(
                timeout=10.0
            ) as client:

                response = await client.get(
                    url,
                    headers={
                        "X-Internal-Key": self.internal_key,
                    },
                )

                print(
                    f"🔐 [AUTH STATUS] : "
                    f"{response.status_code}"
                )

                print(
                    f"🔐 [AUTH BODY]   : "
                    f"{response.text}"
                )

                response.raise_for_status()

                data = response.json()

        except httpx.TimeoutException as exc:
            raise RuntimeError(
                "Auth Service request timed out"
            ) from exc

        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"Auth Service returned HTTP "
                f"{exc.response.status_code}: "
                f"{exc.response.text}"
            ) from exc

        except httpx.RequestError as exc:
            raise RuntimeError(
                f"Unable to connect to Auth Service: {exc}"
            ) from exc

        # --------------------------------------------------
        # Validate Auth response
        # --------------------------------------------------

        if not data:
            raise RuntimeError(
                "Auth Service returned empty response"
            )

        if not data.get("user_id"):
            raise RuntimeError(
                "Auth Service response does not contain "
                "'user_id'"
            )

        if not data.get("parent_id"):
            raise RuntimeError(
                "Auth Service response does not contain "
                "'parent_id'"
            )

        if not data.get("role"):
            raise RuntimeError(
                "Auth Service response does not contain "
                "'role'"
            )

        print(
            f"👤 [USER ID]   : "
            f"{data.get('user_id')}"
        )

        print(
            f"👨‍👩‍👧 [PARENT ID] : "
            f"{data.get('parent_id')}"
        )

        print(
            f"🔐 [ROLE]      : "
            f"{data.get('role')}"
        )

        return data