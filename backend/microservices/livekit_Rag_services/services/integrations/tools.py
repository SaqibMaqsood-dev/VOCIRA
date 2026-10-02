"""
The agent's records tools - the only way it reads a school's records.

    get_student        the child's profile and class (student, class, program_enrollment, guardian)
    get_attendance     attendance and leave
    get_fee_status     fees and payments
    get_results        results, marks, exams, subjects, remarks
    get_timetable      the class timetable
    get_announcements  the school's current notices - for any caller, guests too

The tools never know which system a school runs: each asks the school's
adapter (registry.connector_for), which is ERPNext's, Open School MIS's,
or the canonical records' - Excel/CSV, Google Sheets, a REST API, a
database, or Native Records.

Whose records: a tool is given the guardian the auth service vouched for,
and the adapter answers only about that guardian's own children.
"""

import re

from backend.microservices.livekit_Rag_services.services.integrations import registry, store

# The router's resource names (erp_services/endpoint.py) -> the tool that answers them
RESOURCE_TOOL = {
    "student": "get_student", "guardian": "get_student", "class": "get_student", "program_enrollment": "get_student",
    "attendance": "get_attendance", "leave": "get_attendance",
    "fee": "get_fee_status", "payment": "get_fee_status",
    "assessment": "get_results", "exam": "get_results", "course": "get_results", "remarks": "get_results",
    "schedule": "get_timetable",
}

TOOL_DEFAULT_RESOURCE = {
    "get_student": "student", "get_attendance": "attendance", "get_fee_status": "fee",
    "get_results": "assessment", "get_timetable": "schedule",
}


async def _ask(school, tool: str, guardian_id: str, student_name=None, session_id=None, resource=None) -> dict:
    resource = resource or TOOL_DEFAULT_RESOURCE[tool]
    if RESOURCE_TOOL.get(resource) != tool:
        raise ValueError(f"{tool} does not answer '{resource}'")
    adapter = registry.connector_for(school)
    data = await adapter.fetch(resource=resource, guardian_id=guardian_id, student_name=student_name,
                               session_id=session_id)
    if isinstance(data, dict):
        data.setdefault("_tool", tool)
    return data


async def get_student(school, guardian_id, student_name=None, session_id=None, resource="student") -> dict:
    return await _ask(school, "get_student", guardian_id, student_name, session_id, resource)


async def get_attendance(school, guardian_id, student_name=None, session_id=None, resource="attendance") -> dict:
    return await _ask(school, "get_attendance", guardian_id, student_name, session_id, resource)


async def get_fee_status(school, guardian_id, student_name=None, session_id=None, resource="fee") -> dict:
    return await _ask(school, "get_fee_status", guardian_id, student_name, session_id, resource)


async def get_results(school, guardian_id, student_name=None, session_id=None, resource="assessment") -> dict:
    return await _ask(school, "get_results", guardian_id, student_name, session_id, resource)


async def get_timetable(school, guardian_id, student_name=None, session_id=None, resource="schedule") -> dict:
    return await _ask(school, "get_timetable", guardian_id, student_name, session_id, resource)


TOOLS = {
    "get_student": get_student,
    "get_attendance": get_attendance,
    "get_fee_status": get_fee_status,
    "get_results": get_results,
    "get_timetable": get_timetable,
}


async def lookup(school, resource: str, guardian_id: str, student_name=None, session_id=None) -> dict:
    """The router's {resource, student} answered by the tool for it."""
    tool = RESOURCE_TOOL.get(resource)
    if tool is None:
        raise ValueError(f"No records tool answers '{resource}'")
    return await TOOLS[tool](school, guardian_id, student_name, session_id, resource=resource)


# ---------------------------------------------------------
# Announcements - school-wide, for every caller
# ---------------------------------------------------------

_ASKS_NOTICES = re.compile(
    r"\b(announcements?|notices?|notice board|circulars?|latest news|school news|ailaan|elaan|ilan)\b|اعلان|نوٹس",
    re.IGNORECASE,
)


def asks_announcements(question: str) -> bool:
    return bool(_ASKS_NOTICES.search(question or ""))


def keeps_announcements(school) -> bool:
    """Only schools whose records are in Vocira have announcements in them."""
    provider = registry.get(school.records)
    return provider is not None and provider.mode in ("sync", "native")


async def get_announcements(school, class_names: list[str] | None = None) -> dict:
    """The notices showing today, for everyone or for these classes."""
    about = "The school's current announcements and notices."
    if not keeps_announcements(school):
        return {"data": [], "_about": about, "_tool": "get_announcements"}
    rows = await store.announcements(school.id, class_names)
    data = [{k: v for k, v in {"title": r["title"], "message": r["message"], "for": r["audience"],
                               "date": r["date"], "until": r["expires"]}.items() if v} for r in rows]
    return {"data": data, "_about": about, "_tool": "get_announcements"}
