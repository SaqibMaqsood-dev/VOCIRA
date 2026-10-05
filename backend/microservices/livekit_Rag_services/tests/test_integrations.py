"""
The Records Integration Hub (services/integrations/) - its pieces, without
the running services:

    normalizer      columns and values of any source into canonical fields
    sheets          spreadsheet.parse still reads the sheets schools already link
    database        only read-only SQL gets through; the session itself refuses writes
    security        no credential survives into an error message
    rest_api        a real HTTP server: auth, pagination, list paths, private addresses
    registry        providers without an official API can never be a school's records

The database tests use the development Postgres; nothing they write
outlives them (tests/test_integrations_tenancy.py has the store's own).

Run:
    uv run --no-sync --project backend/microservices/livekit_Rag_services \
        pytest backend/microservices/livekit_Rag_services/tests/test_integrations.py -v
"""

import io
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from backend.microservices.livekit_Rag_services.services.integrations import normalizer, registry, security
from backend.microservices.livekit_Rag_services.services.integrations.base import SourceError
from backend.microservices.livekit_Rag_services.services.integrations.generic import database, excel, rest_api

# the async tests share one event loop - the database pool lives on it
module_loop = pytest.mark.asyncio(loop_scope="module")


# =========================================================
# Normalizer
# =========================================================

def test_roll_no_is_the_student_id_when_there_is_no_other():
    result = normalizer.normalize("students", ["Roll No", "Name", "Parent ID"], [["12", "Ali", "G-1"]])
    assert result.mapping == {"student_id": "Roll No", "student_name": "Name", "guardian_id": "Parent ID"}
    assert result.rows[0]["student_id"] == "12"


def test_roll_no_stays_a_roll_number_next_to_a_student_id():
    result = normalizer.normalize("students", ["Student ID", "Roll No", "Name", "Parent ID"],
                                  [["S-1", "12", "Ali", "G-1"]])
    assert result.mapping["student_id"] == "Student ID"
    assert result.rows[0]["roll_no"] == "12"


def test_a_schools_own_mapping_wins():
    result = normalizer.normalize("students", ["GR #", "Bachay ka naam", "Family"], [["7", "Zoya", "F-9"]],
                                  {"student_id": "GR #", "student_name": "Bachay ka naam", "guardian_id": "Family"})
    assert result.rows[0] == {"student_id": "7", "student_name": "Zoya", "guardian_id": "F-9"}


def test_values_are_cleaned():
    att = normalizer.normalize("attendance", ["Adm No", "Date", "Status"],
                               [["1", "02/10/2026", "p"], ["1", "2026-10-03", "A"], ["1", "4-Oct-2026", "leave"]])
    assert [r["status"] for r in att.rows] == ["Present", "Absent", "Leave"]
    assert [r["date"] for r in att.rows] == ["2026-10-02", "2026-10-03", "2026-10-04"]

    fees = normalizer.normalize("fees", ["Student ID", "Total Fee", "Paid Amount"], [["1", "Rs 1,500", "500"]])
    assert fees.rows[0]["amount"] == 1500 and fees.rows[0]["outstanding"] == 1000
    assert fees.rows[0]["status"] == "Unpaid"

    days = normalizer.normalize("timetable", ["Class", "Day", "Subject"], [["5-A", "mon", "Maths"], ["5-A", "Juma", "Urdu"]])
    assert [r["day"] for r in days.rows] == ["Monday", "Friday"]


def test_missing_columns_and_empty_rows_are_explained():
    with pytest.raises(normalizer.NormalizeError, match="Parent / guardian ID"):
        normalizer.normalize("students", ["Student ID", "Name"], [["1", "Ali"]])
    with pytest.raises(normalizer.NormalizeError, match="appear twice"):
        normalizer.normalize("students", ["Name", "name"], [["a", "b"]])
    result = normalizer.normalize("results", ["Student ID", "Subject", "Marks"],
                                  [["1", "Maths", "80"], ["2", "", "70"], ["3", "Urdu", "abc"]])
    assert len(result.rows) == 1
    assert any("left out" in w for w in result.warnings)


def test_extra_columns_are_kept():
    result = normalizer.normalize("students", ["Student ID", "Name", "Parent ID", "Bus Route"], [["1", "Ali", "G", "R-4"]])
    assert result.rows[0]["_extra"] == {"bus_route": "R-4"}


def test_a_native_form_is_checked_like_an_import():
    assert normalizer.normalize_record("students", {"student_name": "Ali"}, native=True)["student_name"] == "Ali"
    with pytest.raises(normalizer.NormalizeError, match="Student name"):
        normalizer.normalize_record("students", {"student_id": "1"}, native=True)
    with pytest.raises(normalizer.NormalizeError, match="Not a number"):
        normalizer.normalize_record("fees", {"student_id": "1", "amount": "a lot"}, native=True)


def test_suggested_mapping_for_the_mapping_step():
    suggested = normalizer.suggest_mapping("fees", ["Adm No", "Month", "Total", "Balance"])
    assert suggested["student_id"] == "Adm No" and suggested["description"] == "Month"
    assert suggested["amount"] == "Total" and suggested["outstanding"] == "Balance"
    assert suggested["paid"] is None


# =========================================================
# The sheets schools already link keep working
# =========================================================

def test_a_linked_sheet_parses_as_before():
    from backend.microservices.livekit_Rag_services.services.erp_services import spreadsheet

    csv = "Roll Number,Name,Parent ID,Email,Class\n12,Ali Khan,G-1,a@x.pk,5\n13,Sara,G-1,,5\n".encode()
    header, rows, warnings = spreadsheet.parse("students", "link.csv", csv)
    assert header[:3] == ["student_id", "student_name", "guardian_id"]
    assert rows[0]["guardian_email"] == "a@x.pk" and rows[1]["class"] == "5"
    assert warnings == []


def test_an_excel_upload_previews_before_it_imports():
    from openpyxl import Workbook

    book = Workbook()
    sheet = book.active
    sheet.append(["Adm No", "Student", "Father ID", "Father Name"])
    sheet.append(["101", "Hamza", "F-1", "Bilal"])
    sheet.append(["102", "Ayesha", "F-1", "Bilal"])
    buffer = io.BytesIO()
    book.save(buffer)
    preview = excel.preview("students", "students.xlsx", buffer.getvalue())
    assert preview["ok"] and preview["rows"] == 2
    assert preview["mapping"]["student_id"] == "Adm No" and preview["mapping"]["guardian_id"] == "Father ID"


# =========================================================
# Database: reading only
# =========================================================

@pytest.mark.parametrize("sql", [
    "SELECT id, name FROM students",
    "with s as (select * from students) select * from s",
    "SELECT name FROM students WHERE note = 'deleted; drop table x'",
    "SELECT comment, status, date FROM attendance;",
])
def test_reading_queries_pass(sql):
    assert database.check_query(sql)


@pytest.mark.parametrize("sql, why", [
    ("INSERT INTO students VALUES (1)", "SELECT"),
    ("SELECT 1; DROP TABLE students", "One query"),
    ("SELECT * INTO copy FROM students", "INTO"),
    ("SELECT * FROM students FOR UPDATE", "UPDATE"),
    ("WITH x AS (DELETE FROM students RETURNING *) SELECT * FROM x", "DELETE"),
    ("SELECT pg_sleep(60)", "PG_SLEEP"),
    ("", "empty"),
])
def test_anything_that_writes_is_refused(sql, why):
    with pytest.raises(SourceError, match=why):
        database.check_query(sql)


def _local_database_settings():
    from sqlalchemy.engine import make_url

    from backend.microservices.livekit_Rag_services.core.config import settings

    url = make_url(settings.DATABASE_URL)
    return ({"engine": "postgresql", "host": url.host, "port": str(url.port or 5432), "database": url.database,
             "username": url.username, "sslmode": "disable"},
            {"password": url.password or ""})


@module_loop
async def test_the_database_session_itself_refuses_writes():
    settings, secrets = _local_database_settings()
    conn = await database._connect(settings, secrets, allow_private=True)
    try:
        import asyncpg

        with pytest.raises(asyncpg.ReadOnlySQLTransactionError):
            await conn.execute("UPDATE rec_students SET name = name WHERE false")
        columns, rows = await database._run(conn, "SELECT 1 AS one, 'x' AS two", 10)
        assert columns == ["one", "two"] and rows == [{"one": 1, "two": "x"}]
    finally:
        await conn.close()


@module_loop
async def test_a_private_database_needs_the_super_admins_permission():
    settings, secrets = _local_database_settings()
    with pytest.raises(SourceError, match="private network"):
        await database._connect({**settings, "host": "127.0.0.1"}, secrets, allow_private=False)


@module_loop
async def test_a_wrong_password_says_so_and_shows_no_secret():
    settings, _ = _local_database_settings()
    result = await database.test({**settings, "queries": {"students": "SELECT 1 AS student_id"}},
                                 {"password": "definitely-wrong-pw"}, allow_private_network=True)
    assert not result["ok"]
    assert "definitely-wrong-pw" not in json.dumps(result)


# =========================================================
# Security
# =========================================================

def test_no_credential_survives_into_an_error():
    secrets = {"token": "s3cr3t-token-value", "password": "hunter22"}
    text = ("GET https://admin:hunter22@api.school.pk/x?api_key=AKIA123456 failed: "
            "Authorization: Bearer s3cr3t-token-value; token=abcdef123456")
    scrubbed = security.scrub(text, secrets)
    for leaked in ("s3cr3t-token-value", "hunter22", "AKIA123456", "abcdef123456", "admin:"):
        assert leaked not in scrubbed


# =========================================================
# Generic REST API - against a real HTTP server
# =========================================================

STUDENTS = [{"admission_no": f"A{i}", "full_name": f"Student {i}", "parent": {"id": "P1", "name": "Parent"}}
            for i in range(1, 6)]


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.headers.get("X-API-Key") != "key-123":
            self.send_response(401)
            self.end_headers()
            return
        page = 2 if "page=2" in self.path else 1
        items = STUDENTS[:3] if page == 1 else STUDENTS[3:]
        body = {"result": {"items": items}, "links": {"next": "/v1/students?page=2" if page == 1 else None}}
        data = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


@pytest.fixture(scope="module")
def api_server():
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}/v1"
    server.shutdown()


def _rest_settings(base):
    return {"base_url": base, "auth_type": "header", "auth_header": "X-API-Key",
            "endpoints": {"students": {"path": "/students", "list_path": "result.items", "next_path": "links.next"}}}


@module_loop
async def test_every_page_is_read_and_flattened(api_server):
    records = await rest_api.fetch_table(_rest_settings(api_server), {"token": "key-123"}, True, "students")
    assert len(records) == 5
    assert records[0]["parent.id"] == "P1"
    mapped = normalizer.normalize("students", rest_api._columns(records), records,
                                  {"student_id": "admission_no", "student_name": "full_name", "guardian_id": "parent.id"})
    # "parent.name" is a known name for the parent's name
    assert mapped.rows[4] == {"student_id": "A5", "student_name": "Student 5", "guardian_id": "P1",
                              "guardian_name": "Parent"}


@module_loop
async def test_a_wrong_key_is_refused_without_echoing_it(api_server):
    result = await rest_api.test(_rest_settings(api_server), {"token": "wrong-key-999"}, True)
    assert not result["ok"]
    assert "refused the credentials" in json.dumps(result)
    assert "wrong-key-999" not in json.dumps(result)


@module_loop
async def test_a_private_api_needs_the_super_admins_permission(api_server):
    with pytest.raises(SourceError, match="private network"):
        await rest_api.fetch_table(_rest_settings(api_server), {"token": "key-123"}, False, "students")


@module_loop
async def test_a_wrong_list_path_is_explained(api_server):
    settings = _rest_settings(api_server)
    settings["endpoints"]["students"]["list_path"] = "data"
    with pytest.raises(SourceError, match="No list was found at 'data'"):
        await rest_api.fetch_table(settings, {"token": "key-123"}, True, "students")


# =========================================================
# Registry
# =========================================================

def test_providers_without_an_official_api_can_never_be_a_schools_records():
    from backend.microservices.livekit_Rag_services.services import tenants

    unavailable = [p for p in registry.PROVIDERS.values() if p.mode == "unavailable"]
    assert {p.kind for p in unavailable} == {"skoo", "eschools", "schooldost", "skoolee"}
    for p in unavailable:
        assert p.status == "official_integration_required"
        assert p.build is None and p.sync is None and p.test is None and not p.fields
        assert p.kind not in tenants.RECORDS_KINDS
    assert set(tenants.RECORDS_KINDS) == set(registry.USABLE)


def test_rest_api_and_database_are_kept_back_for_now():
    from backend.microservices.livekit_Rag_services.services import tenants

    offered = {p["kind"] for p in registry.catalogue()}
    for kind in ("rest-api", "database"):
        assert kind in registry.HIDDEN
        assert kind not in offered and kind not in registry.USABLE and kind not in tenants.RECORDS_KINDS
        assert registry.get(kind) is not None          # the code stays - one line brings it back
    assert {"native", "excel", "spreadsheet", "erpnext", "open-school-mis"} <= offered


def test_erpnext_and_open_school_mis_are_optional_demo_providers():
    assert registry.get("erpnext").status == "demo" and registry.get("erpnext").mode == "live"
    assert registry.get("open-school-mis").status == "demo"
