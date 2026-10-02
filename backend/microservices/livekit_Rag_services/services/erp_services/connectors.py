"""
Records connectors - one door to any school's records system.

The agent asks a school's records only two things: which children a
guardian has, and one resource (attendance, fees, results, ...) for
them. Every records system - ERPNext, Open School MIS, or live
spreadsheet links (Google Sheets / CSV / Excel) - answers those two
through an adapter behind the same interface, so the agent never
changes when a school with a different system joins.

KINDS below is the catalogue the Schools page offers: each kind says
what it needs to connect (its fields - the secret ones are encrypted,
see connections.py), what it can read, how to test a connection, and
how to build its adapter. A new records system is one more adapter and
one more entry in KINDS; the panel shows it with its own form.

Authorization does not move into the adapters' hands: the guardian is
always the one the auth service vouched for (never anything said on
the call), and each adapter must return only that guardian's
children's records.
"""

import os
from dataclasses import dataclass, field
from typing import Awaitable, Callable

from backend.microservices.livekit_Rag_services.services import tenants
from backend.microservices.livekit_Rag_services.services.erp_services import connections, open_school_mis, spreadsheet
from backend.microservices.livekit_Rag_services.services.erp_services.compact import compact_records
from backend.microservices.livekit_Rag_services.services.erp_services.ERP_client import ERPClient
from backend.microservices.livekit_Rag_services.services.erp_services.erp_service import ERPService
from backend.microservices.livekit_Rag_services.services.erp_services.records_base import (  # noqa: F401 - re-exported
    CAPABILITIES,
    GuardianScoped,
    NoRecordsConnector,
    OnlyAllowed,
    RecordsConnector,
    RecordsUnavailable,
    about_of,
    note,
)
from backend.microservices.livekit_Rag_services.services.tenants import DEFAULT_SCHOOL_ID


class ERPNextConnector(RecordsConnector):
    """A school on ERPNext's Education module."""

    kind = "erpnext"
    available = True

    def __init__(self, service: ERPService):
        self._service = service

    async def children_of(self, guardian_id: str) -> list[dict]:
        if not guardian_id:
            return []
        students = await self._service.get_parent_students(erp_parent_id=guardian_id)
        return [
            {"id": s["name"], "name": s["student_name"].strip()}
            for s in students
            if isinstance(s, dict) and s.get("name") and s.get("student_name")
        ]

    async def guardians(self) -> list[dict]:
        """ERPNext's guardians - name, email, mobile and how many children each has."""
        import json

        client = self._service.client
        rows = await client.get("/api/resource/Guardian", params={
            "limit_page_length": 0,
            "fields": json.dumps(["name", "guardian_name", "email_address", "mobile_number"]),
            "order_by": "guardian_name asc",
        })
        try:
            links = (await client.get("/api/resource/Student Guardian", params={
                "limit_page_length": 0, "parent": "Student", "fields": json.dumps(["guardian"]),
            })).get("data") or []
        except Exception:
            links = []
        counts = {}
        for link in links:
            if link.get("guardian"):
                counts[link["guardian"]] = counts.get(link["guardian"], 0) + 1
        return [
            {
                "id": g["name"],
                "name": g.get("guardian_name") or g["name"],
                "email": (g.get("email_address") or "").strip() or None,
                "mobile": g.get("mobile_number"),
                "students": counts.get(g["name"], 0),
            }
            for g in (rows or {}).get("data") or []
        ]

    async def fetch(self, resource, guardian_id, student_name=None, session_id=None) -> dict:
        return await self._service.fetch(
            resource=resource,
            erp_parent_id=guardian_id,
            student_name=student_name,
            session_id=session_id,
        )


class SpreadsheetConnector(GuardianScoped, RecordsConnector):
    """
    A school whose records are live spreadsheet links set on the Schools
    page (see spreadsheet.py, records_sync.py). Answers the same two
    questions as ERPNext, in the same shapes, so the agent cannot tell
    them apart.
    """

    kind = "spreadsheet"

    # ERPNext resource -> the table that answers it
    _TABLE_FOR = {
        "student": "students",
        "attendance": "attendance",
        "assessment": "results",
        "fee": "fees",
        "payment": "fees",
    }

    def __init__(self, school):
        self._dir = tenants.records_dir(school.id)

    @property
    def available(self) -> bool:
        return spreadsheet.has_table(self._dir, "students")

    async def children_of(self, guardian_id: str) -> list[dict]:
        if not guardian_id:
            return []
        children = {}
        for row in spreadsheet.rows(self._dir, "students"):
            if spreadsheet.same_id(row.get("guardian_id"), guardian_id):
                children.setdefault(row["student_id"], {
                    "id": row["student_id"],
                    "name": row["student_name"],
                    "class": (row.get("class") or "").strip() or None,  # an optional column
                })
        return list(children.values())

    async def guardians(self) -> list[dict]:
        found = {}
        for row in spreadsheet.rows(self._dir, "students"):
            key = (row.get("guardian_id") or "").strip()
            if not key:
                continue
            entry = found.setdefault(key, {
                "id": key, "name": "", "email": None, "mobile": None, "_students": set(),
            })
            entry["name"] = entry["name"] or (row.get("guardian_name") or "").strip()
            entry["email"] = entry["email"] or (row.get("guardian_email") or "").strip() or None
            entry["mobile"] = entry["mobile"] or (row.get("guardian_mobile") or "").strip() or None
            entry["_students"].add(row["student_id"])
        return sorted(
            ({**{k: v for k, v in g.items() if k != "_students"},
              "name": g["name"] or g["id"], "students": len(g["_students"])}
             for g in found.values()),
            key=lambda g: g["name"].lower(),
        )

    async def fetch(self, resource, guardian_id, student_name=None, session_id=None) -> dict:
        about = about_of(resource)

        # Whose records: always this guardian's own children, from the
        # school's own list - never anything said on the call.
        children = await self.children_of(guardian_id)
        ids, reply = await self.pick_children(children, student_name, session_id, about)
        if reply:
            return reply

        table = self._TABLE_FOR.get(resource)
        if table is None or not spreadsheet.has_table(self._dir, table):
            return note(about, "The school's records do not include this information. "
                               "Tell the parent to ask the school office.")

        names = {c["id"]: c["name"] for c in children}
        wanted = {i.strip().lower() for i in ids}
        rows = [
            spreadsheet.shaped(table, row, names.get(row["student_id"], row.get("student_name", "")))
            for row in spreadsheet.rows(self._dir, table)
            if row.get("student_id", "").strip().lower() in wanted
        ]
        if table == "students":
            # one profile per child, however many guardians they have
            rows = list({r["student"]: r for r in rows}.values())
        data = compact_records(resource, {"data": rows})
        data["_about"] = about
        if not rows:
            data["_note"] = "The school's records have nothing on this yet for this child."
        return data


# =========================================================
# THE CATALOGUE
# =========================================================

@dataclass(frozen=True)
class SettingField:
    key: str
    label: str
    kind: str = "text"          # text | url | email | secret
    required: bool = True
    placeholder: str = ""
    help: str = ""


@dataclass(frozen=True)
class ConnectorKind:
    kind: str
    label: str
    description: str
    setup: str                                  # "connection" (fields + Test) | "links" (spreadsheet tables)
    build: Callable
    fields: tuple = ()
    capabilities: tuple = ()
    test: Callable[[dict, dict, bool], Awaitable[dict]] | None = None
    extra: dict = field(default_factory=dict)

    def public(self) -> dict:
        return {
            "kind": self.kind,
            "label": self.label,
            "description": self.description,
            "setup": self.setup,
            "fields": [f.__dict__ for f in self.fields],
            "capabilities": [{"key": c, "label": CAPABILITIES[c]["label"]} for c in self.capabilities],
            **self.extra,
        }


# ---- ERPNext

def _erpnext_for(school, connection, default_service: ERPService | None) -> RecordsConnector:
    if connection is not None:
        s, k = connection.settings, connection.secrets
        if not (s.get("base_url") and k.get("api_key") and k.get("api_secret")):
            print(f"[Records] {school.id}: ERPNext connection incomplete - no records for this school")
            return NoRecordsConnector()
        return ERPNextConnector(ERPService(client=ERPClient(s["base_url"], k["api_key"], k["api_secret"])))

    prefix = school.records_env_prefix
    if not prefix:
        # Only the first school keeps the service's own ERP settings.
        if school.id == DEFAULT_SCHOOL_ID:
            return ERPNextConnector(default_service or ERPService())
        print(f"[Records] {school.id}: ERPNext without settings - no records for this school")
        return NoRecordsConnector()

    # older setup: the keys are in the server environment under a prefix
    names = {part: f"{prefix}_{part}" for part in ("BASE_URL", "API_KEY", "API_SECRET")}
    values = {part: os.getenv(name) for part, name in names.items()}
    missing = [names[part] for part, value in values.items() if not value]
    if missing:
        # ERPClient would fill the gaps with the first school's ERP
        # settings - another school's records. General questions only
        # until the server has this school's own.
        print(f"[Records] {school.id}: {', '.join(missing)} not set - no records for this school")
        return NoRecordsConnector()
    return ERPNextConnector(ERPService(client=ERPClient(values["BASE_URL"], values["API_KEY"], values["API_SECRET"])))


async def _test_erpnext(settings: dict, secrets: dict, allow_private_network: bool) -> dict:
    steps, capabilities = [], []

    def step(name, ok, detail=""):
        steps.append({"name": name, "ok": ok, "detail": detail})

    if not (settings.get("base_url") and secrets.get("api_key") and secrets.get("api_secret")):
        # never let ERPClient fall back to the first school's own ERP keys
        step("Connection details", False, "The address, API key and API secret are all needed.")
        return {"ok": False, "steps": steps, "capabilities": [], "counts": {}}
    client = ERPClient(settings["base_url"], secrets["api_key"], secrets["api_secret"])

    async def count(doctype: str) -> int:
        body = await client.get("/api/method/frappe.client.get_count", params={"doctype": doctype})
        return int((body or {}).get("message") or 0)

    try:
        students, guardians = await count("Student"), await count("Guardian")
    except Exception as error:
        step("Sign in and read the students", False, getattr(error, "detail", None) or str(error))
        return {"ok": False, "steps": steps, "capabilities": [], "counts": {}}
    step("Signed in", True, "the API key works")
    step("Students and guardians", students > 0, f"{students} students, {guardians} guardians")
    capabilities.append("profile")
    for capability, label, doctype in [("attendance", "Attendance", "Student Attendance"),
                                       ("results", "Results and marks", "Assessment Result"),
                                       ("fees", "Fees", "Sales Invoice"),
                                       ("timetable", "Timetable", "Course Schedule")]:
        try:
            n = await count(doctype)
            step(label, True, f"{n} records")
            capabilities.append(capability)
            if capability == "results":
                capabilities.append("marks")
        except Exception as error:
            step(label, False, getattr(error, "detail", None) or str(error))
    return {"ok": students > 0, "steps": steps, "capabilities": capabilities,
            "counts": {"students": students, "guardians": guardians}}


# ---- Open School MIS

def _mis_for(school, connection, default_service) -> RecordsConnector:
    if connection is None or not connection.secrets.get("password"):
        print(f"[Records] {school.id}: Open School MIS not connected - no records for this school")
        return NoRecordsConnector()
    s = connection.settings
    return open_school_mis.OpenSchoolMISConnector(open_school_mis.OpenSchoolMISClient(
        s.get("base_url", ""), s.get("email", ""), connection.secrets["password"], connection.allow_private_network))


# ---- Live spreadsheet

def _spreadsheet_for(school, connection, default_service) -> RecordsConnector:
    return SpreadsheetConnector(school)


KINDS: dict[str, ConnectorKind] = {k.kind: k for k in [
    ConnectorKind(
        kind="erpnext",
        label="ERPNext",
        description="ERPNext with the Education module, read live through its API.",
        setup="connection",
        build=_erpnext_for,
        fields=(
            SettingField("base_url", "ERPNext address", "url", placeholder="https://school.erpnext.com"),
            SettingField("api_key", "API key", "secret", help="ERPNext: User > API Access > Generate Keys - for a read-only user."),
            SettingField("api_secret", "API secret", "secret"),
        ),
        capabilities=("profile", "attendance", "results", "fees", "marks", "timetable"),
        test=_test_erpnext,
    ),
    ConnectorKind(
        kind="open-school-mis",
        label="Open School MIS (MIS-ILSMS)",
        description="Globussoft Open School MIS, read live through its REST API with a service account.",
        setup="connection",
        build=_mis_for,
        fields=(
            SettingField("base_url", "MIS API address", "url", placeholder="https://mis.school.edu/api/v1",
                         help="The address of the MIS API, ending in /api/v1."),
            SettingField("email", "Service account email", "email", placeholder="vocira@school.edu",
                         help="An MIS account made for Vocira - not a person's own login."),
            SettingField("password", "Service account password", "secret"),
        ),
        capabilities=("profile", "attendance", "results", "fees", "marks"),
        test=open_school_mis.test,
    ),
    ConnectorKind(
        kind="spreadsheet",
        label="Live spreadsheet (Google Sheets / CSV link)",
        description="A link per table - students, attendance, results, fees - re-read every few minutes.",
        setup="links",
        build=_spreadsheet_for,
        capabilities=("profile", "attendance", "results", "fees", "marks"),
    ),
]}


def catalogue() -> list[dict]:
    return [k.public() for k in KINDS.values()]


async def check_address(url: str, allow_private_network: bool) -> None:
    """A connection's address: http(s), and on the public internet unless the school says otherwise."""
    from urllib.parse import urlparse

    from backend.microservices.livekit_Rag_services.services.erp_services import records_sync

    parsed = urlparse(url or "")
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise connections.ConnectionSettingsError("The address must be a full link starting with https://")
    if not allow_private_network:
        try:
            await records_sync._check_public(url)
        except records_sync.LinkError as error:
            raise connections.ConnectionSettingsError(f"{error} If the system runs on the school's own network, tick that option.")


# Keyed by the school, its records setting and its connection's version,
# so a school whose system was changed in the panel gets a fresh connector.
_connectors: dict[tuple, RecordsConnector] = {}


def connector_for(school, default_service: ERPService | None = None) -> RecordsConnector:
    """
    The records connector for a school - now the Records Integration Hub's
    (services/integrations/registry.py), which knows every provider: the
    live ones here (ERPNext, Open School MIS) and every source copied into
    Vocira's canonical records (Excel/CSV, Google Sheets, REST API,
    database, Native Records).
    """
    from backend.microservices.livekit_Rag_services.services.integrations import registry

    return registry.connector_for(school, default_service)


def _legacy_connector_for(school, default_service: ERPService | None = None) -> RecordsConnector:
    """The connector as it was built before the Integration Hub - kept for reference and comparison tests."""
    connection = connections.get(school.id)
    if connection is not None and connection.kind != school.records:
        connection = None
    key = (school.id, school.records, school.records_env_prefix, connection.version if connection else None)
    found = _connectors.get(key)
    if found is None:
        kind = KINDS.get(school.records or "")
        found = kind.build(school, connection, default_service) if kind else NoRecordsConnector()
        if connection is not None and kind is not None and kind.setup == "connection" and found.available:
            # only what the school allowed Vocira to read
            found = OnlyAllowed(found, set(connection.capabilities))
        _connectors[key] = found
    return found
