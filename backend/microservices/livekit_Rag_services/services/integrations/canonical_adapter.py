"""
Reading a school's canonical records (store.py) through the same interface
every records adapter has (erp_services/records_base.RecordsConnector) -
for every source that is copied into Vocira: Excel/CSV, Google Sheets, a
REST API, a database, and Native Records.

The rows come back in the shapes ERPNext's do (spreadsheet.shaped), so the
same compaction and the same answer prompt apply whatever the source.
"""

import time

from backend.microservices.livekit_Rag_services.services import tenants
from backend.microservices.livekit_Rag_services.services.erp_services import spreadsheet
from backend.microservices.livekit_Rag_services.services.erp_services.compact import compact_records
from backend.microservices.livekit_Rag_services.services.erp_services.records_base import (
    GuardianScoped,
    RecordsConnector,
    about_of,
    note,
)
from backend.microservices.livekit_Rag_services.services.integrations import store

# Which canonical table answers each of the agent's resources
TABLE_FOR = {
    "student": "students", "class": "students", "program_enrollment": "students",
    "attendance": "attendance", "leave": "attendance",
    "fee": "fees", "payment": "fees",
    "assessment": "results", "exam": "results", "course": "results", "remarks": "results",
    "schedule": "timetable",
    "guardian": "guardians",
}

_NOT_KEPT = "The school's records do not include this information. Tell the parent to ask the school office."


class CanonicalConnector(GuardianScoped, RecordsConnector):
    """A school whose records are copied into Vocira, or kept in it."""

    available = True

    def __init__(self, school, kind: str):
        self._school = school
        self.kind = kind
        self._legacy = None
        self._legacy_checked = 0.0

    async def _sheets_fallback(self):
        """
        A Google Sheets school whose sheets were linked before the canonical
        store existed: until its first sync copies them in, its sheet copies
        on disk are read as before.
        """
        if self.kind != "spreadsheet":
            return None
        if time.monotonic() - self._legacy_checked < 60:
            return self._legacy
        self._legacy_checked = time.monotonic()
        from backend.microservices.livekit_Rag_services.services.erp_services.connectors import SpreadsheetConnector

        folder = tenants.records_dir(self._school.id)
        if not await store.has_students(self._school.id) and spreadsheet.has_table(folder, "students"):
            self._legacy = SpreadsheetConnector(self._school)
        else:
            self._legacy = None
        return self._legacy

    async def children_of(self, guardian_id: str) -> list[dict]:
        legacy = await self._sheets_fallback()
        if legacy:
            return await legacy.children_of(guardian_id)
        return await store.children_of(self._school.id, guardian_id)

    async def guardians(self) -> list[dict]:
        legacy = await self._sheets_fallback()
        if legacy:
            return await legacy.guardians()
        return await store.guardians(self._school.id)

    async def fetch(self, resource, guardian_id, student_name=None, session_id=None) -> dict:
        legacy = await self._sheets_fallback()
        if legacy:
            return await legacy.fetch(resource, guardian_id, student_name, session_id)

        about = about_of(resource)
        table = TABLE_FOR.get(resource)
        if table is None:
            return note(about, _NOT_KEPT)

        if resource == "guardian":
            found = await store.guardian(self._school.id, guardian_id)
            if not found:
                return note(about, "The school's records have no details for this parent.")
            return {"data": [{k: v for k, v in found.items() if k not in ("id", "source") and v}], "_about": about}

        # Whose records: always this guardian's own children, from the
        # school's own records - never anything said on the call.
        children = await self.children_of(guardian_id)
        ids, reply = await self.pick_children(children, student_name, session_id, about)
        if reply:
            return reply
        names = {c["id"].lower(): c["name"] for c in children}
        chosen = [c for c in children if c["id"] in ids]

        if table == "students":
            # the profile names the parent asking, as a sheet's row did
            parent = await store.guardian(self._school.id, guardian_id)
            rows = [spreadsheet.shaped("students", {**self._flat(r), **({"guardian_name": parent["guardian_name"]} if parent else {})},
                                       names.get(r["student_id"].lower(), r["student_name"]))
                    for r in await store.records_for(self._school.id, "students", ids)]
        elif table == "timetable":
            rows = await self._timetable(chosen)
        else:
            stored = await store.records_for(self._school.id, table, ids)
            if resource == "leave":
                stored = [r for r in stored if (r.get("status") or "").lower() == "leave"]
            if resource == "remarks":
                stored = [r for r in stored if (r.get("_extra") or {}).get("remarks")]
            rows = [spreadsheet.shaped(table, self._flat(r), names.get(r["student_id"].lower(), ""))
                    for r in stored]
            if resource == "exam":
                rows = list({(r.get("student"), r.get("assessment_group"), r.get("academic_year")): {
                    "student": r.get("student"), "student_name": r.get("student_name"),
                    "assessment_group": r.get("assessment_group"), "academic_year": r.get("academic_year"),
                } for r in rows if r.get("assessment_group")}.values())
            elif resource == "course":
                rows = list({(r.get("student"), r.get("course")): {
                    "student": r.get("student"), "student_name": r.get("student_name"), "course": r.get("course"),
                } for r in rows if r.get("course")}.values())

        if not rows and not await store.has_rows(self._school.id, table):
            return note(about, _NOT_KEPT)
        data = compact_records(resource, {"data": rows})
        data["_about"] = about
        if not rows:
            data["_note"] = "The school's records have nothing on this yet for this child."
        return data

    @staticmethod
    def _flat(row: dict) -> dict:
        """A stored row as the sheet row it would have been - extras alongside."""
        flat = {k: v for k, v in row.items() if k not in ("id", "source", "_extra")}
        flat.update(row.get("_extra") or {})
        return {k: ("" if v is None else v) for k, v in flat.items()}

    async def _timetable(self, children: list[dict]) -> list[dict]:
        classes = {}
        for child in children:
            if child.get("class"):
                classes.setdefault(child["class"].lower(), []).append(child["name"])
        rows = []
        for r in await store.timetable_for(self._school.id, list(classes)):
            rows.append({k: v for k, v in {
                "class": r["class"], "for": ", ".join(classes.get((r["class"] or "").lower(), [])),
                "day": r["day"], "start_time": r["start_time"], "end_time": r["end_time"],
                "subject": r["subject"], "teacher": r["teacher"], "room": r["room"],
            }.items() if v})
        return rows
