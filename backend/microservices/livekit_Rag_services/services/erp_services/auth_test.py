import asyncio
import sys
from uuid import UUID

from .auth_client import AuthClient
from .erp_service import ERPService


async def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python -m ... <vocira_user_id> [user query]")
        return

    vocira_user_id = UUID(sys.argv[1])

    user_query = (
        sys.argv[2]
        if len(sys.argv) > 2
        else "Show me the students"
    )

    # 1. Get ERP guardian ID from Auth Service
    auth_client = AuthClient(
        base_url="http://127.0.0.1:8000"
    )

    erp_parent_id = await auth_client.get_erp_guardian_id(
        vocira_user_id=vocira_user_id,
    )

    print("=" * 70)
    print("VOCIRA USER ID :", vocira_user_id)
    print("ERP PARENT ID  :", erp_parent_id)
    print("=" * 70)

    # 2. Query ERP using ERP parent ID
    service = ERPService()

    result = await service.handle_query(
        user_query=user_query,
        erp_parent_id=erp_parent_id,
    )

    print("\nERP RESULT:")
    print(result)


if __name__ == "__main__":
    asyncio.run(main())