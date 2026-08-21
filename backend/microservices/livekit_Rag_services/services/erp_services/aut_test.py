import asyncio
import sys
from uuid import UUID

from .auth_client import AuthClient

async def main():
    if len(sys.argv) < 2:
        print("Usage: pass a real vocira_user_id, e.g.")
        print("  ... aut_test <vocira_user_id>")
        return

    vocira_user_id = UUID(sys.argv[1])

    client = AuthClient(base_url="http://127.0.0.1:8000")
    guardian_id = await client.get_erp_guardian_id(
        vocira_user_id=vocira_user_id,
    )
    print("ERP GUARDIAN ID:", guardian_id)


if __name__ == "__main__":
    asyncio.run(main())