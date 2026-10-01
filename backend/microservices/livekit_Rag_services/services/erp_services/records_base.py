"""
What every records connector shares (connectors.py has the registry).

  RecordsConnector   the interface the agent uses: children_of, guardians, fetch
  GuardianScoped     picking the asked-about child among the caller's own
                     children by name, and remembering them for "her" / "uski"
  CAPABILITIES       the kinds of data a school can let Vocira read
  OnlyAllowed        a connector limited to what the school allowed
"""

from backend.microservices.livekit_Rag_services.core.redis import RedisServices
from backend.microservices.livekit_Rag_services.services.erp_services.endpoint import ERP_RESOURCES
from backend.microservices.livekit_Rag_services.services.erp_services.erp_service import (
    _LAST_STUDENT_TTL_SECONDS,
    _last_student_key,
    match_child_names,
)


class RecordsUnavailable(Exception):
    """This school has no records system connected."""


class RecordsConnector:
    """What the agent needs from a school's records system."""

    kind = "none"
    available = False

    async def children_of(self, guardian_id: str) -> list[dict]:
        """The guardian's children: [{"id": ..., "name": ...}]."""
        return []

    async def guardians(self) -> list[dict]:
        """Every guardian in the records, for the Accounts page:
        [{"id", "name", "email", "mobile", "students"}]."""
        return []

    async def fetch(
        self,
        resource: str,
        guardian_id: str,
        student_name: str | None = None,
        session_id: str | None = None,
    ) -> dict:
        """One resource for the guardian's children - or one child, by name."""
        raise RecordsUnavailable(self.kind)


class NoRecordsConnector(RecordsConnector):
    """A school with no records system: general questions only."""


# ---------------------------------------------------------
# Which data a school lets Vocira read
# ---------------------------------------------------------

# "assessment" (an exam's outcome) is shared by two of them: Results is the
# overall outcome (total, percentage, overall grade), Marks the number in
# each subject of each test. A school may share one without the other.
CAPABILITIES = {
    "profile": {"label": "Student profile", "resources": ("student", "guardian")},
    "attendance": {"label": "Attendance", "resources": ("attendance", "leave")},
    "results": {"label": "Results", "resources": ("assessment", "exam", "course", "program_enrollment", "class", "remarks")},
    "fees": {"label": "Fees", "resources": ("fee", "payment")},
    "marks": {"label": "Marks", "resources": ("assessment",)},
    "timetable": {"label": "Timetable", "resources": ("schedule",)},
}


def capabilities_of(resource: str) -> set[str]:
    return {name for name, c in CAPABILITIES.items() if resource in c["resources"]}


def capability_of(resource: str) -> str | None:
    return next(iter(sorted(capabilities_of(resource))), None)


def _limit_assessment(data: dict, allowed: set[str]) -> dict:
    """An exam's outcome cut to what the school shares: Results (the overall
    result) and / or Marks (the number in each subject)."""
    entries = data.get("data")
    if not isinstance(entries, list):
        return data
    keep_marks, keep_results = "marks" in allowed, "results" in allowed
    shaped = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        entry = dict(entry)
        if not keep_marks:
            entry.pop("records", None)          # each subject's marks
            for key in ("course", "total_score", "maximum_score", "grade", "percentage"):
                entry.pop(key, None)
        if not keep_results:
            entry.pop("overall_result", None)    # total, percentage, overall grade
            entry.pop("overall_results", None)
        shaped.append(entry)
    out = {**data, "data": shaped}
    if shaped and not out.get("_note"):  # never over a note of the connector's own ("No child named ...")
        if not keep_marks:
            out["_note"] = "The school shares only the overall result, not each subject's marks."
        elif not keep_results:
            out["_note"] = "The school shares each subject's marks, not an overall result or percentage."
    return out


def note(about: str, text: str) -> dict:
    return {"data": [], "_about": about, "_note": text}


def about_of(resource: str) -> str:
    if resource not in ERP_RESOURCES:
        raise ValueError(f"Unauthorized ERP resource: {resource}")
    return ERP_RESOURCES[resource].get("description") or ""


class OnlyAllowed(RecordsConnector):
    """A connector that answers only about what the school allowed Vocira to read."""

    def __init__(self, inner: RecordsConnector, allowed: set[str]):
        self._inner = inner
        self._allowed = set(allowed)
        self.kind = inner.kind

    @property
    def available(self) -> bool:
        return self._inner.available

    async def children_of(self, guardian_id: str) -> list[dict]:
        return await self._inner.children_of(guardian_id)

    async def guardians(self) -> list[dict]:
        return await self._inner.guardians()

    async def fetch(self, resource, guardian_id, student_name=None, session_id=None) -> dict:
        if not capabilities_of(resource) & self._allowed:
            return note(about_of(resource),
                        "The school has not shared this information with Vocira. Tell the parent to ask the school office.")
        data = await self._inner.fetch(resource, guardian_id, student_name, session_id)
        if resource == "assessment":
            data = _limit_assessment(data, self._allowed)
        return data


# ---------------------------------------------------------
# The caller's own children, and the one they mean
# ---------------------------------------------------------

class GuardianScoped:
    """
    For connectors that hold the guardian -> children list themselves
    (spreadsheets, Open School MIS): which of the caller's children a
    spoken name means, and the child this call last got an answer about -
    the same memory the router reads through ERPService.last_student_id,
    so "her" and "uski" work the same as with ERPNext.
    """

    _redis = None

    async def pick_children(self, children: list[dict], student_name: str | None,
                            session_id: str | None, about: str):
        """(ids, None) - the children to answer about; or (None, reply) when there is nothing to answer."""
        if not children:
            return None, note(about, "No children are linked to this parent in the school's records.")
        ids = [c["id"] for c in children]
        if not student_name:
            return ids, None

        matched = match_child_names(student_name, [{"name": c["id"], "student_name": c["name"]} for c in children])
        if len(matched) > 1:
            names = [c["name"] for c in children if c["id"] in matched]
            return None, note(about, f"More than one of this parent's children matched '{student_name}': "
                                     f"{', '.join(names)}. Ask the parent to say the full name of the one they mean.")
        if not matched:
            last = await self._last_student(session_id)
            matched = [last] if last in ids else []
        if not matched:
            return None, note(about, f"No child named '{student_name}' was found for this parent. "
                                     "The name may have been misheard - ask them to say it again.")
        await self._remember(session_id, matched[0])
        return matched, None

    def _memory(self):
        if self._redis is None:
            self._redis = RedisServices()
        return self._redis

    async def _last_student(self, session_id: str | None) -> str | None:
        if not session_id:
            return None
        try:
            return await self._memory().get_str_data(_last_student_key(session_id))
        except Exception as error:
            print(f"[Records] could not read the last child: {error}")
            return None

    async def _remember(self, session_id: str | None, student_id: str) -> None:
        if not session_id:
            return
        try:
            await self._memory().set_str_data(_last_student_key(session_id), student_id, expire=_LAST_STUDENT_TTL_SECONDS)
        except Exception as error:
            print(f"[Records] could not remember the child: {error}")
