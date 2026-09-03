import asyncio
import sys
from uuid import UUID
from .erp_service import ERPService



async def main():
    if len(sys.argv) < 2:
        print("Usage: pass a real vocira_user_id, e.g.")
        print("  ... erp_test <vocira_user_id> [user query]")
        return

    vocira_user_id = UUID(sys.argv[1])
    user_query = sys.argv[2] if len(sys.argv) > 2 else "Show me the students"

    service = ERPService(
        auth_service_url="http://127.0.0.1:8000",
    )

    result = await service.handle_query(
        user_query=user_query,
        user_id=vocira_user_id,
    )

    print("\nERP RESULT:")
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
