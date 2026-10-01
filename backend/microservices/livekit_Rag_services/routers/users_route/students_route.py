import json

from fastapi import APIRouter, Depends

from backend.helper_functions.token_service.access_tokken.get_current_user import (
    current_user,
)

from backend.microservices.livekit_Rag_services.services import tenants
from backend.microservices.livekit_Rag_services.services.erp_services import connectors
from backend.microservices.livekit_Rag_services.services.erp_services.erp_service import (
    ERPService,
)
from backend.microservices.livekit_Rag_services.services.erp_services.auth_client import (
    AuthClient,
)
from backend.microservices.livekit_Rag_services.core.config import settings


router = APIRouter(prefix="/children", tags=["Children"])

# the first school's ERPNext, for a school that keeps the service's own settings
erp_service = ERPService()
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
        # Auth is down - the card simply stays hidden rather than
        # breaking the dashboard.
        print(f"[Children] auth lookup failed: {error}")
        return {"children": []}

    guardian_id = auth_user.get("parent_id")
    role = str(auth_user.get("role") or "").strip().lower()

    # Only a guardian's own login has children to show - the same rule as
    # on a call (voice_pipeline.ERP_ALLOWED_ROLES).
    if not guardian_id or role not in _GUARDIAN_ROLES:
        return {"children": []}

    # The guardian's own school's records, whatever system it keeps them
    # in. This always asked the first school's ERPNext: a guardian of a
    # school on a spreadsheet or the MIS was never found there, and the
    # card stayed hidden.
    await tenants.refresh()
    school = tenants.get_school(auth_user.get("school_id"))
    records = connectors.connector_for(school, default_service=erp_service)
    if not records.available:
        return {"children": []}

    try:
        found = await records.children_of(guardian_id)
    except Exception as error:
        print(f"[Children] {school.id}'s records could not be read: {error}")
        return {"children": []}

    children = [
        {
            "student_id": child["id"],
            "name": child["name"],
            "class_name": child.get("class"),
            "program": None,
            "academic_year": None,
        }
        for child in found
    ]

    # ERPNext keeps the class and program elsewhere - asked of that
    # school's own ERPNext, not the first school's.
    service = getattr(getattr(records, "_inner", records), "_service", None)
    if children and service is not None:
        await _erpnext_details(service.client, children)

    return {"children": children}


_GUARDIAN_ROLES = {"guardian", "parent"}


async def _erpnext_details(client, children: list[dict]) -> None:
    """Each child's program, academic year and class, from ERPNext - best-effort."""
    student_ids = [c["student_id"] for c in children]
    try:
        enrollments = await _enrollments(client, student_ids)
        class_by_student = await _classes_of(client, student_ids)
    except Exception as error:
        print(f"[Children] ERPNext details could not be read: {error}")
        return
    for child in children:
        enr = enrollments.get(child["student_id"], {})
        child["program"] = enr.get("program")
        child["academic_year"] = enr.get("academic_year")
        child["class_name"] = class_by_student.get(child["student_id"]) or child["class_name"]


async def _enrollments(client, student_ids: list[str]) -> dict[str, dict]:
    enrollments = (
        await client.get(
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

    return by_student


async def _classes_of(client, student_ids: list[str]) -> dict[str, str]:
    """
    Each child's class ("Class 2") - its Student Group.

    Asking for the child-table column returns one row per matching
    student, so the class can be told apart per child. A student can be
    in more than one group (a club, last year's class): a "Class ..."
    group wins, then the latest academic year. Best-effort - without it
    the card still shows the program.
    """
    try:
        groups = (
            await client.get(
                endpoint="/api/resource/Student Group",
                params={
                    "filters": json.dumps(
                        [["Student Group Student", "student", "in", student_ids]]
                    ),
                    "fields": json.dumps(
                        [
                            "student_group_name",
                            "academic_year",
                            "`tabStudent Group Student`.student",
                        ]
                    ),
                    "limit_page_length": 0,
                },
            )
        ).get("data", [])
    except Exception as error:
        print(f"[Children] class lookup failed: {error}")
        return {}

    def rank(group: dict) -> tuple:
        name = (group.get("student_group_name") or "").strip().lower()
        return (name.startswith("class"), group.get("academic_year") or "")

    best: dict[str, dict] = {}
    for group in groups:
        sid = group.get("student")
        if sid and (sid not in best or rank(group) > rank(best[sid])):
            best[sid] = group

    return {
        sid: group.get("student_group_name")
        for sid, group in best.items()
        if group.get("student_group_name")
    }
