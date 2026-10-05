"""
Which school a call belongs to, and what that school has.

One voice agent serves every school. What differs is per school and
lives here: its name and helpline, where its documents are, the
Pinecone namespace its knowledge is searched in, and whether it has a
records system (ERP) at all.

The first schools are defined in code below. More are added from the
admin panel's Schools page and kept in the database - either way the
agent, the router and the prompts do not change.

The school of a call comes from the login or the address the caller
opened (the school's own subdomain, like medicaps.vocira.com), never
from anything said on the call: "I am from the other school" must not
open another school's knowledge or records. No school is ever shown a
list of the others.
"""

import os
import re
import time
from dataclasses import dataclass, replace

from backend.microservices.livekit_Rag_services.services.rag_engine.config import (
    DATA_DIR,
    PDF_PATH,
    PINECONE_NAMESPACE,
    TEXT_FILES_PATH,
    URLS_FILE_PATH,
)


@dataclass(frozen=True)
class School:
    id: str
    name: str            # as said in English
    name_ur: str         # as said in Urdu
    helpline: str        # digits as written, read out digit by digit
    namespace: str       # Pinecone namespace its knowledge is in
    pdf_dir: str
    text_dir: str
    urls_file: str
    # "erpnext", "spreadsheet" (live Google Sheets / CSV / Excel links,
    # set on the Schools page), or None: general questions only
    records: str | None
    # Where this school's ERPNext credentials are read from:
    # <PREFIX>_BASE_URL / _API_KEY / _API_SECRET in the environment -
    # never in code. None = the service's own ERP_* settings.
    records_env_prefix: str | None = None
    # The school's own address: <subdomain>.vocira.com (here
    # <subdomain>.localhost:3000). None = its id. See address_of().
    subdomain: str | None = None

    def display_name(self, language: str | None) -> str:
        return self.name_ur if (language or "").lower() == "ur" else self.name


def _school_dir(school_id: str) -> str:
    return os.path.join(DATA_DIR, "schools", school_id)


def records_dir(school_id: str) -> str:
    """Where the last good copy of a school's records sheets is kept."""
    return os.path.join(_school_dir(school_id), "records")


# The first school keeps the folders and namespace it always had, so
# its knowledge base stays exactly as it was - nothing to re-index.
EDUCATORS = School(
    id="educators",
    name="The Educators",
    name_ur="دی ایجوکیٹرز",
    helpline="042-111-777-800",
    namespace=PINECONE_NAMESPACE,
    pdf_dir=PDF_PATH,
    text_dir=TEXT_FILES_PATH,
    urls_file=URLS_FILE_PATH,
    records="erpnext",
)

# A made-up second school for the demo: general questions only, no
# records system connected.
DEMO_B = School(
    id="demo-b",
    name="Demo School B",
    name_ur="ڈیمو اسکول بی",
    helpline="021-111-000-222",
    namespace="school-demo-b",
    pdf_dir=os.path.join(_school_dir("demo-b"), "pdf"),
    text_dir=os.path.join(_school_dir("demo-b"), "text_files"),
    urls_file=os.path.join(_school_dir("demo-b"), "urls.txt"),
    records=None,
)

# The schools defined in code. On the Schools page they are like any
# other school: name, helpline and records connection can be changed,
# and they can be removed. Their knowledge stays where it always was
# (the first school's namespace and folders), and a removed one keeps
# its documents and knowledge on the server.
SCHOOLS: dict[str, School] = {s.id: s for s in (EDUCATORS, DEMO_B)}

# The first school. It is the default - for a guest without a school
# link and an account without a school - for as long as it is there;
# when it was removed, the next school is (see default_school_id).
DEFAULT_SCHOOL_ID = EDUCATORS.id


# =========================================================
# SCHOOLS ADDED FROM THE ADMIN PANEL
#
# Stored in the database (models/school_model.py), because the API
# that adds a school and the voice worker that answers its calls are
# separate processes - both read the same table. Each keeps a copy in
# memory, refreshed every few seconds, and at once whenever an id it
# does not know turns up (a school added a moment ago).
# =========================================================

_REFRESH_SECONDS = 20
_added: dict[str, School] = {}      # oldest first
# A school defined in code that was changed in the panel (a row in the
# same table under its id) - or removed there.
_edited: dict[str, School] = {}
_removed: set[str] = set()
_loaded_at = 0.0


class TenantError(ValueError):
    """The admin's input was not usable - becomes an HTTP 4xx."""


def _school_from_record(record) -> School:
    folder = _school_dir(record.id)
    return School(
        id=record.id,
        name=record.name,
        name_ur=record.name_ur or record.name,
        helpline=record.helpline,
        namespace=f"school-{record.id}",
        pdf_dir=os.path.join(folder, "pdf"),
        text_dir=os.path.join(folder, "text_files"),
        urls_file=os.path.join(folder, "urls.txt"),
        records=record.records,
        records_env_prefix=record.records_env_prefix,
        subdomain=getattr(record, "subdomain", None),
    )


async def refresh(force: bool = False) -> None:
    """Re-read the schools added from the admin panel."""
    global _loaded_at
    if not force and time.monotonic() - _loaded_at < _REFRESH_SECONDS:
        return
    try:
        from sqlalchemy import select

        from backend.helper_functions.database.session import SessionLocal
        from backend.microservices.livekit_Rag_services.models.school_model import SchoolRecord

        async with SessionLocal() as db:
            rows = (await db.execute(select(SchoolRecord))).scalars().all()
    except Exception as error:
        # The table may not exist yet (the API creates it when it
        # starts), or the database may be briefly away: the schools
        # in code keep working either way.
        print(f"[Tenants] could not read the added schools: {type(error).__name__}: {error}")
        _loaded_at = time.monotonic()
        return

    added = sorted((r for r in rows if r.id not in SCHOOLS), key=lambda r: (str(r.created_at or ""), r.id))
    fresh = {r.id: _school_from_record(r) for r in added}
    edited = {
        r.id: replace(
            SCHOOLS[r.id], name=r.name, name_ur=r.name_ur or r.name, helpline=r.helpline,
            records=r.records, records_env_prefix=r.records_env_prefix,
            subdomain=getattr(r, "subdomain", None),
        )
        for r in rows if r.id in SCHOOLS and not getattr(r, "deleted", False)
    }
    removed = {r.id for r in rows if r.id in SCHOOLS and getattr(r, "deleted", False)}
    _added.clear()
    _added.update(fresh)
    _edited.clear()
    _edited.update(edited)
    _removed.clear()
    _removed.update(removed)
    _loaded_at = time.monotonic()

    # The schools' records-system connections, kept in step with them -
    # the voice worker learns of a new or changed connection this way.
    try:
        from backend.microservices.livekit_Rag_services.services.erp_services import connections

        await connections.refresh()
    except Exception as error:
        print(f"[Tenants] could not read the records connections: {type(error).__name__}: {error}")


def all_schools() -> dict[str, School]:
    return {**_added, **{i: _edited.get(i, s) for i, s in SCHOOLS.items() if i not in _removed}}


def default_school_id() -> str | None:
    """The first school while it is there; then the next school in code; then the oldest added one."""
    schools = all_schools()
    return next((i for i in SCHOOLS if i in schools), None) or next(iter(_added), None)


def get_school(school_id: str | None) -> School:
    """The school for an id - the default one for anything unknown."""
    schools = all_schools()
    found = schools.get((school_id or "").strip().lower())
    if found is not None:
        return found
    default = default_school_id()
    # the last school can never be removed, so there always is one
    return schools[default] if default else EDUCATORS


def is_known(school_id: str | None) -> bool:
    return (school_id or "").strip().lower() in all_schools()


def is_built_in(school_id: str | None) -> bool:
    return (school_id or "").strip().lower() in SCHOOLS


def address_of(school: School) -> str:
    """The school's subdomain - the one set for it, or its id."""
    return school.subdomain or school.id


def find_by_address(address: str | None) -> School | None:
    """
    The school at an address - its subdomain, or its id (the older
    /s/<id> links). None for anything else: an unknown address gets
    no school at all, never the default one.
    """
    key = (address or "").strip().lower()
    if not key:
        return None
    schools = all_schools()
    return next((s for s in schools.values() if address_of(s) == key), None) or schools.get(key)


def public_list() -> list[dict]:
    """What the admin panel and the frontend may know about each school."""
    return [
        {
            "id": s.id,
            "name": s.name,
            "name_ur": s.name_ur,
            "helpline": s.helpline,
            "namespace": s.namespace,
            "records": s.records,
            "records_env_prefix": s.records_env_prefix,
            "built_in": s.id in SCHOOLS,
            "subdomain": address_of(s),
            # set on the Schools page, or None - the id is used
            "subdomain_set": s.subdomain,
        }
        for s in all_schools().values()
    ]


# ---------------------------------------------------------
# Adding, changing and removing a school
# ---------------------------------------------------------

# Any country's number: an optional + and country code, then digits
# grouped by spaces, dashes, dots or brackets - 6 to 15 digits in all.
_HELPLINE = re.compile(r"^\+?[0-9(][0-9 ()\-.]{3,24}[0-9]$")
_ENV_PREFIX = re.compile(r"^[A-Z][A-Z0-9_]{1,30}$")
# The providers a school's records can be set to - integrations/registry.py USABLE
# (the named systems still waiting for an official integration are not among them,
# nor the ones registry.HIDDEN keeps back for now: rest-api, database)
RECORDS_KINDS = ("erpnext", "spreadsheet", "open-school-mis", "excel", "native")

# One DNS label: lower-case letters, digits and inner dashes.
_SUBDOMAIN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,38}[a-z0-9])$")
# Addresses that are Vocira's own, never a school's.
RESERVED_SUBDOMAINS = frozenset({
    "www", "api", "app", "admin", "superadmin", "auth", "login", "s", "static", "assets", "cdn",
    "mail", "smtp", "ftp", "vocira", "localhost", "dev", "test", "staging", "status", "support", "help",
})

# update_school(): leave the subdomain as it is
KEEP = object()


def _clean_subdomain(value: str | None, school_id: str | None) -> str | None:
    """A school's subdomain as set on the Schools page; None = use its id."""
    value = (value or "").strip().lower()
    if not value or value == school_id:
        return None
    if not _SUBDOMAIN.match(value) or value.startswith("xn--"):
        raise TenantError(
            "The address must be 2 to 40 lower-case English letters, digits or dashes "
            "(not at the start or end), like medicaps."
        )
    if value in RESERVED_SUBDOMAINS:
        raise TenantError(f"'{value}' is kept for Vocira itself - choose another address.")
    for other in all_schools().values():
        if other.id != school_id and value in (other.id, address_of(other)):
            raise TenantError("Another school already uses this address.")
    return value


def _slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:30].strip("-")


def _clean(name: str, name_ur: str | None, helpline: str,
           records: str | None, records_env_prefix: str | None) -> dict:
    name = " ".join((name or "").split())
    name_ur = " ".join((name_ur or "").split()) or name
    helpline = " ".join((helpline or "").split())
    records = (records or "").strip().lower() or None
    records_env_prefix = (records_env_prefix or "").strip().upper() or None

    if not 3 <= len(name) <= 80:
        raise TenantError("School name must be 3 to 80 characters.")
    if len(name_ur) > 80:
        raise TenantError("Urdu name must be at most 80 characters.")
    if not _HELPLINE.match(helpline) or not 6 <= len(re.sub(r"\D", "", helpline)) <= 15:
        raise TenantError(
            "Helpline must be a phone number - digits, with an optional + and country code, "
            "like +92 300 1234567 or 042-111-777-800."
        )
    if records is not None and records not in RECORDS_KINDS:
        raise TenantError(f"Records system must be one of: {', '.join(RECORDS_KINDS)}, or none.")
    if records != "erpnext":
        # Every other system's settings are its connection (or its links),
        # set on the Schools page - not server environment variables.
        records_env_prefix = None
    elif records_env_prefix and not _ENV_PREFIX.match(records_env_prefix):
        # An ERPNext school is connected on the Schools page; the older way -
        # keys under a prefix in the server environment - still works.
        # Never the service's own ERP settings: those are the first
        # school's records, and another school must not reach them.
        raise TenantError(
            "A credentials prefix looks like SCHOOLX_ERP (read as SCHOOLX_ERP_BASE_URL, "
            "_API_KEY and _API_SECRET from the server environment)."
        )
    return {"name": name, "name_ur": name_ur, "helpline": helpline,
            "records": records, "records_env_prefix": records_env_prefix}


async def create_school(name: str, helpline: str, name_ur: str | None = None,
                        records: str | None = None, records_env_prefix: str | None = None,
                        subdomain: str | None = None) -> School:
    """Add a school. Its id - and so its namespace and folders - come from its name."""
    from backend.helper_functions.database.session import SessionLocal
    from backend.microservices.livekit_Rag_services.models.school_model import SchoolRecord

    fields = _clean(name, name_ur, helpline, records, records_env_prefix)
    base = _slug(fields["name"])
    if len(base) < 2:
        raise TenantError("The name needs some English letters or digits for the school's id.")

    await refresh(force=True)
    # an id is also an address (until a subdomain is set), so it must not
    # be another school's subdomain or one of Vocira's own either
    taken = set(all_schools()) | {address_of(s) for s in all_schools().values()} | RESERVED_SUBDOMAINS
    school_id, n = base, 2
    while school_id in taken:
        school_id, n = f"{base[:27]}-{n}", n + 1
    fields["subdomain"] = _clean_subdomain(subdomain, school_id)

    async with SessionLocal() as db:
        db.add(SchoolRecord(id=school_id, **fields))
        await db.commit()

    await refresh(force=True)
    return get_school(school_id)


async def update_school(school_id: str, name: str, helpline: str, name_ur: str | None = None,
                        records: str | None = None, records_env_prefix: str | None = None,
                        subdomain=KEEP) -> School:
    """Change a school. Its id and namespace stay; its subdomain only when one is given."""
    from backend.helper_functions.database.session import SessionLocal
    from backend.microservices.livekit_Rag_services.models.school_model import SchoolRecord

    built_in = is_built_in(school_id)
    await refresh(force=True)
    current = all_schools().get(school_id)
    if current is None:
        # unknown, or a removed school - a change must not bring it back
        raise LookupError(school_id)
    if not (name_ur or "").strip() and current.name_ur != current.name:
        # No Urdu name sent (the panel does not ask for one): keep the
        # one the school has, so Urdu calls still say its name in Urdu.
        name_ur = current.name_ur
    fields = _clean(name, name_ur, helpline, records, records_env_prefix)
    fields["subdomain"] = current.subdomain if subdomain is KEEP else _clean_subdomain(subdomain, school_id)

    async with SessionLocal() as db:
        record = await db.get(SchoolRecord, school_id)
        if record is None:
            if not built_in:
                raise LookupError(school_id)
            record = SchoolRecord(id=school_id)
            db.add(record)
        for key, value in fields.items():
            setattr(record, key, value)
        await db.commit()

    await refresh(force=True)
    return get_school(school_id)


async def delete_school(school_id: str) -> School:
    """
    Remove a school. Its documents stay on disk. A school defined in code
    is marked removed (its row says so); an added one's row is deleted.
    The last school cannot go - a guest without a link needs one.
    """
    from backend.helper_functions.database.session import SessionLocal
    from backend.microservices.livekit_Rag_services.models.school_model import SchoolRecord

    await refresh(force=True)
    schools = all_schools()
    if school_id not in schools:
        raise LookupError(school_id)
    if len(schools) <= 1:
        raise TenantError("The last school cannot be removed - add another school first.")

    if is_built_in(school_id):
        school = schools[school_id]
        async with SessionLocal() as db:
            record = await db.get(SchoolRecord, school_id)
            if record is None:
                record = SchoolRecord(id=school_id, name=school.name, name_ur=school.name_ur, helpline=school.helpline,
                                      records=school.records, records_env_prefix=school.records_env_prefix)
                db.add(record)
            record.deleted = True
            await db.commit()
        await refresh(force=True)
        return school

    async with SessionLocal() as db:
        record = await db.get(SchoolRecord, school_id)
        if record is None:
            raise LookupError(school_id)
        school = _school_from_record(record)
        await db.delete(record)
        await db.commit()

    await refresh(force=True)
    return school
