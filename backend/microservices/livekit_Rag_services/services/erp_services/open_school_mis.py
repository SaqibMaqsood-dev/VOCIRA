"""
Open School MIS (Globussoft MIS-ILSMS), read live through its REST API.

Vocira signs in as a service account the school makes for it in the MIS
(email + password, set on the Schools page) and reads:

  GET /students                          children, with their guardians
  GET /attendance/student/:id/summary    attendance
  GET /grading/student/:id               results
  GET /fees/payments/:id                 fees

A guardian is the parent's MIS login (guardians.userId) - the same
person on every child of theirs. A guardian without an MIS login is
known by their phone number ("phone:<digits>"). A Vocira parent account
carries one of these as its guardian id, so the agent only ever reads
that parent's own children.
"""

import base64
import json
import time
from datetime import date

import httpx

from backend.microservices.livekit_Rag_services.services.erp_services.compact import compact_records
from backend.microservices.livekit_Rag_services.services.erp_services.records_base import (
    GuardianScoped,
    RecordsConnector,
    about_of,
    note,
)

_TIMEOUT = httpx.Timeout(15.0, connect=8.0)


class MISError(Exception):
    """The MIS could not be read - the reason is shown to the super admin."""


def _token_expiry(token: str) -> float:
    """When the MIS access token runs out (its 'exp'), a minute early; 10 minutes if unreadable."""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return float(json.loads(base64.urlsafe_b64decode(payload))["exp"]) - 60
    except Exception:
        return time.time() + 600


class OpenSchoolMISClient:
    def __init__(self, base_url: str, email: str, password: str, allow_private_network: bool = False):
        self.base = (base_url or "").rstrip("/")
        self.email = email
        self._password = password
        self.allow_private_network = allow_private_network
        self.role = None
        self._token = None
        self._expires = 0.0
        self._checked_at = 0.0

    async def _guard(self) -> None:
        # the same rule as live sheet links: the public internet only, unless
        # the school said its MIS is on its own network
        if self.allow_private_network or time.monotonic() - self._checked_at < 300:
            return
        from backend.microservices.livekit_Rag_services.services.erp_services import records_sync

        try:
            await records_sync._check_public(self.base)
        except records_sync.LinkError as error:
            raise MISError(f"{error} If the MIS runs on the school's own network, tick that option.")
        self._checked_at = time.monotonic()

    async def _login(self, http: httpx.AsyncClient) -> None:
        r = await http.post(f"{self.base}/auth/login", json={"email": self.email, "password": self._password})
        if r.status_code in (400, 401):
            raise MISError("The MIS refused the service account's email or password.")
        if r.status_code >= 400:
            raise MISError(f"The MIS login answered HTTP {r.status_code}.")
        body = r.json()
        self._token = body.get("accessToken")
        if not self._token:
            raise MISError("The MIS did not return a login token - is this the MIS API address (…/api/v1)?")
        self.role = (body.get("user") or {}).get("role")
        self._expires = _token_expiry(self._token)

    async def get(self, path: str, params: dict | None = None):
        await self._guard()
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as http:
                if not self._token or time.time() > self._expires:
                    await self._login(http)
                r = await http.get(f"{self.base}{path}", params=params, headers={"Authorization": f"Bearer {self._token}"})
                if r.status_code == 401:  # token ended early - once more
                    await self._login(http)
                    r = await http.get(f"{self.base}{path}", params=params, headers={"Authorization": f"Bearer {self._token}"})
        except httpx.TimeoutException:
            raise MISError("The MIS took too long to answer.")
        except httpx.HTTPError as error:
            raise MISError(f"The MIS could not be reached ({type(error).__name__}) - check the address.")
        if r.status_code == 403:
            raise MISError(f"The service account is not allowed to read {path.split('?')[0]} (403) - give it a role that can.")
        if r.status_code == 404:
            raise MISError(f"The MIS has no {path.split('?')[0]} (404).")
        if r.status_code >= 400:
            raise MISError(f"The MIS answered HTTP {r.status_code} for {path.split('?')[0]}.")
        return r.json()


def guardian_key(guardian: dict) -> str:
    if guardian.get("userId"):
        return guardian["userId"]
    return "phone:" + "".join(ch for ch in guardian.get("phone") or "" if ch.isdigit())


def _child_name(student: dict) -> str:
    user = student.get("user") or {}
    return f"{user.get('firstName', '')} {user.get('lastName', '')}".strip()


def _class_of(student: dict) -> str:
    """ "Class 5 A" - the class and its section."""
    return " ".join(x for x in [(student.get("class") or {}).get("name"), (student.get("section") or {}).get("name")] if x)


class OpenSchoolMISConnector(GuardianScoped, RecordsConnector):
    kind = "open-school-mis"
    available = True
    _CACHE_SECONDS = 60

    def __init__(self, client: OpenSchoolMISClient):
        self._client = client
        self._cache = (0.0, [])

    async def _students(self) -> list[dict]:
        at, rows = self._cache
        if rows and time.monotonic() - at < self._CACHE_SECONDS:
            return rows
        rows = await self._client.get("/students")
        if not isinstance(rows, list):
            raise MISError("The MIS returned something other than a list of students.")
        self._cache = (time.monotonic(), rows)
        return rows

    async def children_of(self, guardian_id: str) -> list[dict]:
        key = str(guardian_id or "").strip()
        if not key:
            return []
        return [
            {"id": s["id"], "name": _child_name(s), "class": _class_of(s) or None}
            for s in await self._students()
            if any(guardian_key(g) == key for g in s.get("guardians") or [])
        ]

    async def guardians(self) -> list[dict]:
        found = {}
        for s in await self._students():
            for g in s.get("guardians") or []:
                key = guardian_key(g)
                entry = found.setdefault(key, {
                    "id": key, "name": g.get("name") or key, "email": g.get("email") or None,
                    "mobile": g.get("phone") or None, "relation": g.get("relation"),
                    "has_login": bool(g.get("userId")), "_children": set(),
                })
                entry["_children"].add(s["id"])
        return sorted(
            ({**{k: v for k, v in e.items() if k != "_children"}, "students": len(e["_children"])} for e in found.values()),
            key=lambda e: e["name"].lower(),
        )

    async def fetch(self, resource, guardian_id, student_name=None, session_id=None) -> dict:
        about = about_of(resource)
        children = await self.children_of(guardian_id)
        ids, reply = await self.pick_children(children, student_name, session_id, about)
        if reply:
            return reply
        names = {c["id"]: c["name"] for c in children}

        if resource == "student":
            by_id = {s["id"]: s for s in await self._students()}
            rows = [self._profile(by_id[i], names[i]) for i in ids if i in by_id]
            data = {"data": rows}
        elif resource == "attendance":
            rows = [r for r in [await self._attendance(i, names[i]) for i in ids] if r]
            data = {"data": rows}
        elif resource == "assessment":
            rows = [r for i in ids for r in await self._results(i, names[i])]
            data = compact_records("assessment", {"data": rows})
        elif resource in ("fee", "payment"):
            rows = [r for i in ids for r in await self._fees(i, names[i])]
            data = compact_records("fee", {"data": rows})
        else:
            return note(about, "The school's records do not include this information. Tell the parent to ask the school office.")

        data["_about"] = about
        if not data["data"]:
            data["_note"] = "The school's records have nothing on this yet for this child."
        return data

    # ---- one child's records, in the shapes the answer prompt knows

    @staticmethod
    def _profile(s: dict, name: str) -> dict:
        row = {
            "student_name": name,
            "class": _class_of(s),
            "roll_no": s.get("rollNo"),
            "admission_no": s.get("admissionNo"),
            "date_of_birth": (s.get("dateOfBirth") or "")[:10] or None,
            "gender": s.get("gender"),
        }
        return {k: v for k, v in row.items() if v not in (None, "")}

    async def _attendance(self, student_id: str, name: str) -> dict | None:
        s = await self._client.get(f"/attendance/student/{student_id}/summary",
                                   {"startDate": "2000-01-01", "endDate": date.today().isoformat()})
        if not s or not s.get("totalDays"):
            return None
        row = {
            "student_name": name,
            "total_days_recorded": s.get("totalDays"),
            "present_days": s.get("present"),
            "absent_days": s.get("absent"),
            "late_days": s.get("late"),
            "half_days": s.get("halfDay"),
            "excused_days": s.get("excused"),
            "attendance_percentage": s.get("percentage"),
        }
        return {k: v for k, v in row.items() if v not in (None, 0) or k in ("absent_days", "attendance_percentage")}

    async def _results(self, student_id: str, name: str) -> list[dict]:
        rows = []
        for g in await self._client.get(f"/grading/student/{student_id}") or []:
            rows.append({k: v for k, v in {
                "student": student_id, "student_name": name,
                "course": (g.get("subject") or {}).get("name"),
                "assessment_group": (g.get("assessment") or {}).get("title"),
                "total_score": g.get("marksObtained"),
                "maximum_score": g.get("maxMarks"),
                "grade": g.get("gradeLabel"),
            }.items() if v not in (None, "")})
        return rows

    async def _fees(self, student_id: str, name: str) -> list[dict]:
        rows = []
        for p in await self._client.get(f"/fees/payments/{student_id}") or []:
            total = (p.get("amount") or 0) - (p.get("discount") or 0)
            paid = p.get("paidAmount") or 0
            status = (p.get("status") or "").upper()
            rows.append({k: v for k, v in {
                "student": student_id, "student_name": name,
                "description": (p.get("feeHead") or {}).get("name"),
                "grand_total": total,
                "paid_amount": paid,
                "outstanding_amount": 0 if status == "PAID" else max(total - paid, 0),
                "status": status.title() or None,
                "paid_on": (p.get("paidAt") or "")[:10] or None,
            }.items() if v not in (None, "")})
        return rows


async def test(settings: dict, secrets: dict, allow_private_network: bool) -> dict:
    """Sign in, count, and try every kind of data on a real child - for the Test connection button."""
    steps, capabilities, counts = [], [], {}

    def step(name, ok, detail=""):
        steps.append({"name": name, "ok": ok, "detail": detail})

    client = OpenSchoolMISClient(settings.get("base_url", ""), settings.get("email", ""),
                                 secrets.get("password", ""), allow_private_network)
    try:
        students = await client.get("/students")
    except MISError as error:
        step("Sign in and read the students", False, str(error))
        return {"ok": False, "steps": steps, "capabilities": [], "counts": {}}
    step("Signed in", True, f"as {client.email} (role {client.role or '?'})")

    guardians = [g for s in students for g in s.get("guardians") or []]
    logins = {g["userId"] for g in guardians if g.get("userId")}
    counts = {"students": len(students), "guardians": len({guardian_key(g) for g in guardians}), "parent_logins": len(logins)}
    step("Students and guardians", bool(students),
         f"{counts['students']} students, {counts['guardians']} guardians ({counts['parent_logins']} with an MIS parent login)")
    if not students:
        return {"ok": False, "steps": steps, "capabilities": [], "counts": counts}

    capabilities.append("profile")
    sample = students[0]["id"]
    for capability, label, path, params in [
        ("attendance", "Attendance", f"/attendance/student/{sample}/summary", {"startDate": "2000-01-01", "endDate": date.today().isoformat()}),
        ("results", "Results and marks", f"/grading/student/{sample}", None),
        ("fees", "Fees", f"/fees/payments/{sample}", None),
    ]:
        try:
            await client.get(path, params)
            step(label, True, "readable")
            capabilities.append(capability)
            if capability == "results":
                capabilities.append("marks")    # the same records: overall result and each subject's marks
        except MISError as error:
            step(label, False, str(error))
    return {"ok": True, "steps": steps, "capabilities": capabilities, "counts": counts}
