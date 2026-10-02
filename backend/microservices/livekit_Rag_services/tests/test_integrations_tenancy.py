"""
Tenant isolation of the canonical records - one school never sees, changes
or deletes another's.

Two made-up schools (zz-test-a, zz-test-b) get records with the SAME
student ids and the SAME guardian id, which is exactly what would leak if a
query forgot its school. Then every way in is tried from the other school:
the store, the Native Records functions, and the agent's tools.

Uses the development Postgres; both schools' rows are removed at the end.

Run:
    uv run --no-sync --project backend/microservices/livekit_Rag_services \
        pytest backend/microservices/livekit_Rag_services/tests/test_integrations_tenancy.py -v
"""

import pytest
import pytest_asyncio

from backend.helper_functions.database.base import Base
from backend.helper_functions.database.session import engine
from backend.microservices.livekit_Rag_services.models import canonical_records_model  # noqa: F401
from backend.microservices.livekit_Rag_services.services.integrations import native, store, tools

pytestmark = pytest.mark.asyncio(loop_scope="module")

A, B = "zz-test-a", "zz-test-b"


def _school(school_id: str, records: str = "native"):
    from backend.microservices.livekit_Rag_services.services.tenants import School

    return School(id=school_id, name=school_id.upper(), name_ur=school_id, helpline="000", namespace=f"school-{school_id}",
                  pdf_dir="", text_dir="", urls_file="", records=records)


def _students(prefix: str):
    return [
        {"student_id": "S1", "student_name": f"{prefix} Ali", "guardian_id": "G1", "guardian_name": f"{prefix} Parent",
         "class": "5-A"},
        {"student_id": "S2", "student_name": f"{prefix} Sara", "guardian_id": "G1", "class": "5-A"},
        {"student_id": "S3", "student_name": f"{prefix} Other", "guardian_id": "G2", "class": "6-B"},
    ]


@pytest_asyncio.fixture(scope="module", loop_scope="module", autouse=True)
async def two_schools():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    for school in (A, B):
        await store.clear(school)
        prefix = school[-1].upper()
        await store.replace_table(school, "students", _students(prefix), "native")
        await store.replace_table(school, "attendance", [
            {"student_id": "S1", "date": "2026-10-01", "status": "Present" if school == A else "Absent"},
            {"student_id": "S3", "date": "2026-10-01", "status": "Leave"},
        ], "native")
        await store.replace_table(school, "fees", [
            {"student_id": "S1", "amount": 1000 if school == A else 9999, "paid": 0, "outstanding": 1000 if school == A else 9999,
             "description": f"{prefix} October"},
        ], "native")
        await store.replace_table(school, "timetable", [
            {"class": "5-A", "day": "Monday", "subject": f"{prefix} Maths", "start_time": "08:00"},
        ], "native")
        await store.replace_table(school, "announcements", [
            {"title": f"{prefix} notice", "message": f"Only for school {prefix}", "audience": "all"},
        ], "native")
    yield
    for school in (A, B):
        await store.clear(school)


async def test_a_guardian_sees_only_their_own_schools_children():
    a = await store.children_of(A, "G1")
    b = await store.children_of(B, "G1")
    assert [c["name"] for c in a] == ["A Ali", "A Sara"]
    assert [c["name"] for c in b] == ["B Ali", "B Sara"]


async def test_records_counts_and_parents_stay_apart():
    assert [r["status"] for r in await store.records_for(A, "attendance", ["S1"])] == ["Present"]
    assert [r["status"] for r in await store.records_for(B, "attendance", ["S1"])] == ["Absent"]
    assert (await store.counts(A))["students"] == 3 and (await store.counts(B))["students"] == 3
    assert {g["name"] for g in await store.guardians(A)} == {"A Parent", "G2"}
    assert all(n["title"] == "A notice" for n in await store.announcements(A))


async def test_one_school_cannot_change_or_delete_anothers_record():
    b_rows, _ = await store.list_rows(B, "fees")
    b_fee = b_rows[0]["id"]
    assert await store.update_row(A, "fees", b_fee, {"student_id": "S1", "amount": 1}) is None
    assert await native.update(A, "fees", b_fee, {"student_id": "S1", "amount": "1"}) is None
    assert await store.delete_row(A, "fees", b_fee) is False
    still, _ = await store.list_rows(B, "fees")
    assert still[0]["amount"] == 9999


async def test_listing_never_shows_another_schools_rows():
    rows, total = await store.list_rows(A, "students", q="B Ali")
    assert total == 0 and rows == []
    rows, total = await store.list_rows(A, "students", q="A Ali")
    assert total == 1 and rows[0]["guardian_id"] == "G1"
    rows, total = await store.list_rows(A, "students")
    assert total == 3 and all(r["student_name"].startswith("A ") for r in rows)


async def test_attendance_marked_in_one_school_lands_only_there():
    marked = await native.mark_attendance(A, "2026-10-02", {"S1": "A", "S2": "P"})
    assert marked == 2
    assert [r["status"] for r in await store.records_for(B, "attendance", ["S1"])] == ["Absent"]
    register = await store.register(A, "5-A", "2026-10-02")
    assert {r["student_id"]: r["status"] for r in register} == {"S1": "Absent", "S2": "Present"}


async def test_the_agents_tools_answer_only_from_the_callers_school():
    fee_a = await tools.get_fee_status(_school(A), "G1")
    assert fee_a["_tool"] == "get_fee_status"
    text = repr(fee_a)
    assert "1000" in text and "9999" not in text and "B October" not in text

    att_b = await tools.lookup(_school(B), "attendance", "G1", student_name="B Ali")
    assert att_b["data"][0]["student_name"] == "B Ali"
    assert att_b["data"][0]["absent_days"] == 1 and not att_b["data"][0].get("present_days")

    timetable = await tools.get_timetable(_school(A), "G1")
    assert "A Maths" in repr(timetable) and "B Maths" not in repr(timetable)

    notices = await tools.get_announcements(_school(B))
    assert [n["title"] for n in notices["data"]] == ["B notice"]


async def test_a_guardian_cannot_ask_about_a_child_who_is_not_theirs():
    # S3 belongs to G2: asking G1's records for "Other" finds nothing of S3's
    reply = await tools.get_attendance(_school(A), "G1", student_name="A Other")
    assert "Leave" not in repr(reply)
    assert reply.get("_note")


async def test_clearing_one_school_leaves_the_other():
    await store.replace_table(A, "results", [{"student_id": "S1", "subject": "Maths", "marks": 80}], "native")
    await store.replace_table(B, "results", [{"student_id": "S1", "subject": "Maths", "marks": 40}], "native")
    await store.replace_table(A, "results", [], "native")
    assert (await store.counts(A))["results"] == 0
    assert [r["marks"] for r in await store.records_for(B, "results", ["S1"])] == [40]
