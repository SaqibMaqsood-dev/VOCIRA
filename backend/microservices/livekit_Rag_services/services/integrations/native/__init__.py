"""
Vocira Native Records - for a school with no software of its own.

Its students, parents, classes, teachers, attendance, fees, results,
timetable and announcements are kept in Vocira's canonical records and
managed on the school admin's panel: typed in one at a time, imported from
an Excel/CSV file, and attendance marked class by class. Nothing to connect
and nothing to sync - the agent reads them as they are saved.
"""

from datetime import date

from backend.microservices.livekit_Rag_services.services.integrations import canonical, normalizer, store
from backend.microservices.livekit_Rag_services.services.integrations.base import Provider

SOURCE = "native"
ATTENDANCE_STATUSES = ("Present", "Absent", "Leave", "Late")


class NativeError(ValueError):
    """The record could not be saved - the reason is shown on the form."""


def _check_table(table: str) -> None:
    if table not in canonical.TABLES:
        raise NativeError(f"Unknown table '{table}'.")


async def create(school_id: str, table: str, data: dict) -> dict:
    _check_table(table)
    try:
        row = normalizer.normalize_record(table, data, native=True)
        return await store.create_row(school_id, table, row, SOURCE)
    except (normalizer.NormalizeError, store.DuplicateRecord) as error:
        raise NativeError(str(error))


async def update(school_id: str, table: str, row_id: int, data: dict) -> dict | None:
    _check_table(table)
    try:
        row = normalizer.normalize_record(table, data, native=True)
        return await store.update_row(school_id, table, row_id, row)
    except (normalizer.NormalizeError, store.DuplicateRecord) as error:
        raise NativeError(str(error))


async def remove(school_id: str, table: str, row_id: int) -> bool:
    _check_table(table)
    return await store.delete_row(school_id, table, row_id)


async def mark_attendance(school_id: str, day: str | None, marks: dict[str, str]) -> int:
    """A class's register for one day: student id -> Present / Absent / Leave / Late."""
    day = normalizer.iso_date(day) if day else date.today().isoformat()
    if not day or len(day) != 10:
        raise NativeError("The date is not a date.")
    cleaned = {}
    for student_id, status in (marks or {}).items():
        status = normalizer.attendance_status(status)
        if status not in ATTENDANCE_STATUSES:
            raise NativeError(f"Unknown attendance mark '{status}'.")
        cleaned[student_id] = status
    return await store.mark_attendance(school_id, day, cleaned, SOURCE)


PROVIDER = Provider(
    kind="native",
    label="Vocira Native Records",
    description="No school software? Keep students, parents, attendance, fees, results, timetable and notices in Vocira.",
    category="native",
    mode="native",
    setup="native",
    tables=tuple(canonical.TABLE_ORDER),
    notes="Managed on the school admin's Records page. Teachers' attendance register works on a phone.",
)
