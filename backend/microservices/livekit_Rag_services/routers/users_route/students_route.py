import json

from fastapi import APIRouter, Depends

from backend.helper_functions.token_service.access_tokken.get_current_user import (
    current_user,
)

from backend.microservices.livekit_Rag_services.services.erp_services.erp_service import (
    ERPService,
)
from backend.microservices.livekit_Rag_services.services.erp_services.ERP_client import (
    ERPClient,
)
from backend.microservices.livekit_Rag_services.services.erp_services.auth_client import (
    AuthClient,
)
from backend.microservices.livekit_Rag_services.core.config import settings


router = APIRouter(prefix="/children", tags=["Children"])

erp_service = ERPService()
erp_client = ERPClient()
auth_client = AuthClient(base_url=settings.AUTH_SERVICE_URL)


# =========================================================
# MY CHILDREN
# =========================================================

@router.get("/")
async def get_my_children(
    current_user=Depends(current_user),
):
    """
    The logged-in guardian's own children (name + program), for the
    dashboard's "My Children" card. Nothing here comes from the
    caller - the guardian's ERP id is looked up from their own
    account, the same way the voice pipeline decides whose data a
    call may see.

    The ERP id is NOT read off the JWT: access_claims() never put
    parent_id in the token, so it is always None there.
    """

    try:
        auth_user = await auth_client.get_internal_user(
            vocira_user_id=current_user.user_id,
        )
    except RuntimeError as error:
        # No ERP link on this account yet (or auth is down) - the card
        # simply stays hidden rather than breaking the dashboard.
        print(f"[Children] auth lookup failed: {error}")
        return {"children": []}

    erp_parent_id = auth_user.get("parent_id")

    if not erp_parent_id:
        return {"children": []}

    students = await erp_service.get_parent_students(
        erp_parent_id=erp_parent_id,
    )

    student_ids = [
        s["name"] for s in students if isinstance(s, dict) and s.get("name")
    ]

    if not student_ids:
        return {"children": []}

    enrollments = (
        await erp_client.get(
            endpoint="/api/resource/Program Enrollment",
            params={
                "filters": json.dumps(
                    [["student", "in", student_ids], ["docstatus", "=", 1]]
                ),
                "fields": json.dumps(["student", "program", "academic_year"]),
                "limit_page_length": 0,
            },
        )
    ).get("data", [])

    # A student can have more than one year's enrollment (e.g. rolled
    # forward already) - keep the latest academic_year per student.
    by_student: dict[str, dict] = {}
    for e in enrollments:
        sid = e.get("student")
        if not sid:
            continue
        current = by_student.get(sid)
        if not current or e.get("academic_year", "") > current.get("academic_year", ""):
            by_student[sid] = e

    children = []
    for s in students:
        sid = s.get("name")
        enr = by_student.get(sid, {})
        children.append(
            {
                "student_id": sid,
                "name": s.get("student_name"),
                "program": enr.get("program"),
                "academic_year": enr.get("academic_year"),
            }
        )

    return {"children": children}
