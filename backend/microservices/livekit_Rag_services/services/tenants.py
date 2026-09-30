"""
Which school a call belongs to, and what that school has.

One voice agent serves every school. What differs is per school and
lives here: its name and helpline, where its documents are, the
Pinecone namespace its knowledge is searched in, and whether it has a
records system (ERP) at all.

The first schools are defined in code below. More are added from the
admin panel's Schools page and kept in the database - either way the
agent, the router and the prompts do not change.

The school of a call comes from the login or the link the caller
opened, never from anything said on the call: "I am from the other
school" must not open another school's knowledge or records.
"""

import os
import re
import time
from dataclasses import dataclass

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
    records: str | None  # "erpnext", or None: general questions only
    # Where this school's records system credentials are read from:
    # <PREFIX>_BASE_URL / _API_KEY / _API_SECRET in the environment -
    # never in code. None = the service's own ERP_* settings.
    records_env_prefix: str | None = None

    def display_name(self, language: str | None) -> str:
        return self.name_ur if (language or "").lower() == "ur" else self.name


def _school_dir(school_id: str) -> str:
    return os.path.join(DATA_DIR, "schools", school_id)


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

# The schools defined in code. They cannot be changed or removed from
# the admin panel - the first school's records and knowledge depend on
# them staying exactly as they are.
SCHOOLS: dict[str, School] = {s.id: s for s in (EDUCATORS, DEMO_B)}

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
_added: dict[str, School] = {}
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

    fresh = {r.id: _school_from_record(r) for r in rows if r.id not in SCHOOLS}
    _added.clear()
    _added.update(fresh)
    _loaded_at = time.monotonic()


def all_schools() -> dict[str, School]:
    return {**_added, **SCHOOLS}


def get_school(school_id: str | None) -> School:
    """The school for an id - the default one for anything unknown."""
    return all_schools().get((school_id or "").strip().lower(), SCHOOLS[DEFAULT_SCHOOL_ID])


def is_known(school_id: str | None) -> bool:
    return (school_id or "").strip().lower() in all_schools()


def is_built_in(school_id: str | None) -> bool:
    return (school_id or "").strip().lower() in SCHOOLS


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
        }
        for s in all_schools().values()
    ]


# ---------------------------------------------------------
# Adding, changing and removing a school
# ---------------------------------------------------------

_HELPLINE = re.compile(r"^0[0-9][0-9 -]{5,18}[0-9]$")
_ENV_PREFIX = re.compile(r"^[A-Z][A-Z0-9_]{1,30}$")
RECORDS_KINDS = ("erpnext",)


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
    if not _HELPLINE.match(helpline):
        raise TenantError("Helpline must be a phone number, like 042-111-777-800.")
    if records is not None and records not in RECORDS_KINDS:
        raise TenantError(f"Records system must be one of: {', '.join(RECORDS_KINDS)}, or none.")
    if records is None:
        records_env_prefix = None
    elif not records_env_prefix or not _ENV_PREFIX.match(records_env_prefix):
        # Never the service's own ERP settings: those are the first
        # school's records, and another school must not reach them.
        raise TenantError(
            "A school with a records system needs its own credentials prefix "
            "(for example SCHOOLX_ERP, read as SCHOOLX_ERP_BASE_URL, _API_KEY and "
            "_API_SECRET from the server environment)."
        )
    return {"name": name, "name_ur": name_ur, "helpline": helpline,
            "records": records, "records_env_prefix": records_env_prefix}


async def create_school(name: str, helpline: str, name_ur: str | None = None,
                        records: str | None = None, records_env_prefix: str | None = None) -> School:
    """Add a school. Its id - and so its namespace and folders - come from its name."""
    from backend.helper_functions.database.session import SessionLocal
    from backend.microservices.livekit_Rag_services.models.school_model import SchoolRecord

    fields = _clean(name, name_ur, helpline, records, records_env_prefix)
    base = _slug(fields["name"])
    if len(base) < 2:
        raise TenantError("The name needs some English letters or digits for the school's id.")

    await refresh(force=True)
    taken = set(all_schools())
    school_id, n = base, 2
    while school_id in taken:
        school_id, n = f"{base[:27]}-{n}", n + 1

    async with SessionLocal() as db:
        db.add(SchoolRecord(id=school_id, **fields))
        await db.commit()

    await refresh(force=True)
    return get_school(school_id)


async def update_school(school_id: str, name: str, helpline: str, name_ur: str | None = None,
                        records: str | None = None, records_env_prefix: str | None = None) -> School:
    """Change a school added from the panel. Its id and namespace stay."""
    from backend.helper_functions.database.session import SessionLocal
    from backend.microservices.livekit_Rag_services.models.school_model import SchoolRecord

    if is_built_in(school_id):
        raise TenantError("This school is defined in code and cannot be changed here.")
    fields = _clean(name, name_ur, helpline, records, records_env_prefix)

    async with SessionLocal() as db:
        record = await db.get(SchoolRecord, school_id)
        if record is None:
            raise LookupError(school_id)
        for key, value in fields.items():
            setattr(record, key, value)
        await db.commit()

    await refresh(force=True)
    return get_school(school_id)


async def delete_school(school_id: str) -> School:
    """Remove a school added from the panel. Its documents stay on disk."""
    from backend.helper_functions.database.session import SessionLocal
    from backend.microservices.livekit_Rag_services.models.school_model import SchoolRecord

    if is_built_in(school_id):
        raise TenantError("This school is defined in code and cannot be removed here.")

    async with SessionLocal() as db:
        record = await db.get(SchoolRecord, school_id)
        if record is None:
            raise LookupError(school_id)
        school = _school_from_record(record)
        await db.delete(record)
        await db.commit()

    await refresh(force=True)
    return school
