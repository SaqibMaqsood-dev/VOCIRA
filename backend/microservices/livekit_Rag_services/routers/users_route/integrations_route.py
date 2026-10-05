"""
The Records Integration Hub's endpoints (services/integrations/).

    /admin/integrations/...   connecting a school's records system, testing,
                              syncing, mapping, uploading, history
    /admin/records/...        Vocira Native Records - the school's own records,
                              typed in on the panel

Who may do what:
    super admin    every school: chooses its records system (connect, change,
                   disconnect), tests, syncs, sees status, counts and errors. May
                   allow a system on the school's own network (allow_private_network).
    school admin   their own school only, on the system the super admin chose:
                   its records (Native Records), uploads, mapping, sync. Never
                   another school's, never a different system, never a
                   private-network address.
    parents        nothing here (require_admin on both routers).

Secrets go in, never out: a connection's view says which secrets are set,
never what they are.
"""

import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field

from backend.helper_functions.token_service.access_tokken.require_admin import (
    caller_school,
    is_super_admin,
    require_admin,
)

router = APIRouter(prefix="/admin/integrations", tags=["Records integrations"], dependencies=[Depends(require_admin)])
records_router = APIRouter(prefix="/admin/records", tags=["Native records"], dependencies=[Depends(require_admin)])

Admin = Annotated[object, Depends(require_admin)]


def _actor(admin) -> str | None:
    return getattr(admin, "username", None)


def _fail(code: int, detail: str):
    raise HTTPException(status_code=code, detail=detail)


async def _known(school_id: str):
    from backend.microservices.livekit_Rag_services.services import tenants

    school_id = (school_id or "").strip().lower()
    await tenants.refresh(force=not tenants.is_known(school_id))
    if not tenants.is_known(school_id):
        _fail(status.HTTP_404_NOT_FOUND, "School not found")
    return tenants.get_school(school_id)


async def _scoped(admin, school_id: str):
    """The school a request may touch: any for the super admin, only their own for a school's admin."""
    own = caller_school(admin)
    if own is not None and (school_id or "").strip().lower() != own:
        _fail(status.HTTP_403_FORBIDDEN, "You can only manage your own school's records.")
    return await _known(school_id)


# =========================================================
# Reading: the catalogue, a school's integration, every school's
# =========================================================

@router.get("/catalogue")
async def catalogue():
    """Every records provider - usable or waiting for an official integration - and Vocira's canonical tables."""
    from backend.microservices.livekit_Rag_services.services.integrations import canonical, native, registry

    return {"providers": registry.catalogue(), "tables": canonical.public_tables(),
            "attendance_statuses": list(native.ATTENDANCE_STATUSES)}


@router.get("/overview")
async def overview(admin: Admin):
    """Every school's records integration at a glance - the super admin's Integrations page."""
    from backend.microservices.livekit_Rag_services.services.integrations import sync

    if not is_super_admin(admin):
        _fail(status.HTTP_403_FORBIDDEN, "Only the platform's super admin sees every school.")
    return {"schools": await sync.overview()}


async def _detail(school) -> dict:
    from backend.microservices.livekit_Rag_services.services import tenants
    from backend.microservices.livekit_Rag_services.services.erp_services import connections, records_sync, spreadsheet
    from backend.microservices.livekit_Rag_services.services.integrations import sync

    view = await connections.view(school.id)
    if view is not None and view["kind"] != school.records:
        view = None  # an earlier system's row - not this school's connection now
    out = {
        "school": {"id": school.id, "name": school.name},
        "status": await sync.school_status(school),
        "connection": view,
        "runs": await sync.history(school.id, 15),
    }
    if school.records == "spreadsheet":
        folder = tenants.records_dir(school.id)
        out["sheets"] = {"tables": spreadsheet.status(folder), "sync_minutes": records_sync.SYNC_MINUTES,
                         "last_round_at": records_sync.last_round_at, "next_round_at": records_sync.next_round_at}
    return out


@router.get("/mine")
async def my_integration(admin: Admin):
    """A school admin's own school's records integration."""
    own = caller_school(admin)
    if own is None:
        _fail(status.HTTP_400_BAD_REQUEST, "The super admin picks a school on the Integrations page.")
    return await _detail(await _known(own))


@router.get("/schools/{school_id}")
async def school_integration(school_id: str, admin: Admin):
    return await _detail(await _scoped(admin, school_id))


@router.get("/schools/{school_id}/runs")
async def school_runs(school_id: str, admin: Admin, limit: int = Query(30, ge=1, le=100)):
    from backend.microservices.livekit_Rag_services.services.integrations import sync

    school = await _scoped(admin, school_id)
    return {"runs": await sync.history(school.id, limit), "running": sync.is_running(school.id)}


# =========================================================
# Connecting, testing, disconnecting
# =========================================================

class IntegrationRequest(BaseModel):
    kind: str = Field(max_length=30)
    settings: dict[str, Any] = Field(default_factory=dict)
    # left empty: keep the secret already saved (the panel never has it)
    secrets: dict[str, str] = Field(default_factory=dict)
    capabilities: list[str] = Field(default_factory=list)
    allow_private_network: bool = False
    sync_minutes: int | None = Field(default=None, ge=15, le=1440)
    mapping: dict[str, dict[str, str]] | None = None


_ENDPOINT_KEYS = ("path", "list_path", "next_path")


def _address_of(settings: dict) -> str:
    return f"{settings.get('base_url') or ''}|{settings.get('host') or ''}|{settings.get('port') or ''}"


async def _checked(admin, school, request: IntegrationRequest, for_test: bool):
    """The request, checked against what its provider needs: (provider, settings, secrets, saved_secrets, private)."""
    from backend.microservices.livekit_Rag_services.services.erp_services import connections
    from backend.microservices.livekit_Rag_services.services.integrations import registry, security
    from backend.microservices.livekit_Rag_services.services.integrations.base import SourceError
    from backend.microservices.livekit_Rag_services.services.integrations.generic import database

    provider = registry.get(request.kind)
    if provider is None:
        _fail(422, f"Unknown records system '{request.kind}'.")
    if provider.kind in registry.HIDDEN:
        _fail(422, f"{provider.label} is not offered right now.")
    if provider.mode == "unavailable":
        _fail(422, f"{provider.label} needs its official integration first. {provider.notes}")

    saved = connections.get(school.id)
    saved = saved if saved is not None and saved.kind == provider.kind else None
    saved_secrets = saved.secrets if saved else {}

    # Only the super admin may let the server reach a private network - and a
    # school admin who changes the address loses that permission with it.
    private = bool(request.allow_private_network)
    if not is_super_admin(admin):
        if private and not (saved and saved.allow_private_network):
            _fail(403, "Only the platform's super admin can allow a system on the school's own network.")
        private = private and bool(saved and saved.allow_private_network
                                   and _address_of(saved.settings) == _address_of(request.settings))

    settings, secrets, missing = {}, {}, []
    for f in provider.fields:
        if f.kind == "secret":
            value = (request.secrets.get(f.key) or "").strip()
            if value:
                secrets[f.key] = value
            elif f.required and not saved_secrets.get(f.key):
                missing.append(f.label)
        else:
            value = str(request.settings.get(f.key) or "").strip()
            if f.kind == "select" and value and f.options and value not in [o[0] for o in f.options]:
                _fail(422, f"{f.label}: choose one of the options.")
            if value:
                settings[f.key] = value
            elif f.required:
                missing.append(f.label)

    if provider.setup == "rest":
        endpoints = {}
        for table, value in (request.settings.get("endpoints") or {}).items():
            if table not in provider.tables or not isinstance(value, dict) or not str(value.get("path") or "").strip():
                continue
            endpoints[table] = {k: str(value.get(k) or "").strip() for k in _ENDPOINT_KEYS if str(value.get(k) or "").strip()}
        if "students" not in endpoints:
            missing.append("the Students endpoint")
        settings["endpoints"] = endpoints
        if settings.get("auth_type", "none") != "none" and not (secrets.get("token") or saved_secrets.get("token")):
            missing.append("Token, API key or password")
    elif provider.setup == "database":
        queries = {}
        for table, sql in (request.settings.get("queries") or {}).items():
            if table in provider.tables and str(sql or "").strip():
                try:
                    queries[table] = database.check_query(str(sql))
                except SourceError as error:
                    _fail(422, f"{table.title()} query: {error}")
        if "students" not in queries:
            missing.append("the Students query")
        settings["queries"] = queries

    if missing:
        _fail(422, f"Needed: {', '.join(missing)}.")
    unknown = [c for c in request.capabilities if c not in provider.capabilities]
    if unknown:
        _fail(422, f"{provider.label} cannot read: {', '.join(unknown)}.")
    if not for_test and provider.fields and not request.capabilities:
        _fail(422, "Choose at least one kind of data Vocira may read.")
    if settings.get("base_url"):
        try:
            await security.check_url(settings["base_url"], private)
        except security.AddressError as error:
            _fail(422, str(error))
    return provider, settings, secrets, saved_secrets, private


@router.post("/schools/{school_id}/test")
async def test_integration(school_id: str, request: IntegrationRequest, admin: Admin):
    """Try the connection as typed (secrets left empty: the saved ones). Nothing is saved but the result."""
    from backend.microservices.livekit_Rag_services.services.erp_services import connections
    from backend.microservices.livekit_Rag_services.services.integrations import security, store

    school = await _scoped(admin, school_id)
    provider, settings, secrets, saved_secrets, private = await _checked(admin, school, request, for_test=True)
    merged = {**saved_secrets, **secrets}
    if provider.test is not None:
        try:
            result = await provider.test(settings, merged, private)
        except Exception as error:  # an adapter's surprise is still an answer to show
            result = {"ok": False, "steps": [{"name": "Test", "ok": False,
                                               "detail": security.scrub(f"{type(error).__name__}: {error}", merged)}],
                      "capabilities": [], "counts": {}}
    else:
        counts = {k: v for k, v in (await store.counts(school.id)).items() if v}
        result = {"ok": True, "capabilities": list(provider.capabilities), "counts": counts,
                  "steps": [{"name": provider.label, "ok": True,
                             "detail": "Nothing to sign in to - " + (", ".join(f"{t}: {n}" for t, n in counts.items())
                                                                     or "no records yet")}]}
    for step in result.get("steps", []):
        step["detail"] = security.scrub(step.get("detail"), merged)
    summary = "; ".join(f"{'✓' if s['ok'] else '✗'} {s['name']}: {s['detail']}" for s in result.get("steps", []))
    await connections.record_test(school.id, provider.kind, bool(result.get("ok")), summary, _actor(admin))
    return result


@router.put("/schools/{school_id}/connection")
async def save_integration(school_id: str, request: IntegrationRequest, admin: Admin):
    """Connect the school's records system, or change it. Secrets are stored encrypted."""
    from backend.microservices.livekit_Rag_services.services import tenants
    from backend.microservices.livekit_Rag_services.services.erp_services import connections

    school = await _scoped(admin, school_id)
    if not is_super_admin(admin) and request.kind != school.records:
        _fail(403, "The platform's super admin chooses where a school's records come from.")
    provider, settings, secrets, _, private = await _checked(admin, school, request, for_test=False)
    capabilities = request.capabilities or list(provider.capabilities)
    mapping = {t: {k: v for k, v in m.items() if v} for t, m in (request.mapping or {}).items()} \
        if request.mapping is not None else connections._KEEP
    try:
        await connections.save(school.id, provider.kind, settings, secrets, capabilities, private, _actor(admin),
                               mapping=mapping, sync_minutes=request.sync_minutes)
        if school.records != provider.kind:
            await tenants.update_school(school.id, name=school.name, helpline=school.helpline, name_ur=school.name_ur,
                                        records=provider.kind, records_env_prefix=None)
    except connections.ConnectionSettingsError as error:
        _fail(422, str(error))
    except tenants.TenantError as error:
        _fail(422, str(error))
    print(f"[Integrations] {school.id}: {provider.kind} saved by {_actor(admin)}")
    return await _detail(await _known(school.id))


@router.delete("/schools/{school_id}/connection")
async def disconnect_integration(school_id: str, admin: Admin, delete_records: bool = False):
    """
    Disconnect: the settings and secrets are deleted and the school answers
    general questions only. The records already copied into Vocira stay
    (reconnecting is quick) unless delete_records is set.
    """
    from backend.microservices.livekit_Rag_services.services import tenants
    from backend.microservices.livekit_Rag_services.services.erp_services import connections, spreadsheet
    from backend.microservices.livekit_Rag_services.services.integrations import store

    school = await _scoped(admin, school_id)
    if not is_super_admin(admin):
        _fail(403, "The platform's super admin chooses where a school's records come from.")
    await connections.delete(school.id, _actor(admin))
    if school.records is not None:
        await tenants.update_school(school.id, name=school.name, helpline=school.helpline, name_ur=school.name_ur,
                                    records=None, records_env_prefix=None)
    if delete_records:
        await store.clear(school.id)
        spreadsheet.remove_all(tenants.records_dir(school.id))
    print(f"[Integrations] {school.id}: disconnected by {_actor(admin)}{' (records deleted)' if delete_records else ''}")
    return await _detail(await _known(school.id))


class MappingRequest(BaseModel):
    mapping: dict[str, str] = Field(default_factory=dict)


@router.put("/schools/{school_id}/mapping/{table}")
async def save_mapping(school_id: str, table: str, request: MappingRequest, admin: Admin):
    """Which source column fills each of Vocira's fields, for one table - used from the next sync on."""
    from backend.microservices.livekit_Rag_services.services.erp_services import connections
    from backend.microservices.livekit_Rag_services.services.integrations import canonical, registry

    school = await _scoped(admin, school_id)
    if table not in canonical.TABLES:
        _fail(404, "No such table")
    unknown = [f for f in request.mapping if f not in canonical.field_names(table)]
    if unknown:
        _fail(422, f"Not a field of {table}: {', '.join(unknown)}.")
    provider = registry.get(school.records)
    if provider is None or provider.mode not in ("sync", "native"):
        _fail(409, "Mapping is for records copied into Vocira - connect such a source first.")
    await connections.ensure(school.id, school.records, _actor(admin))
    await connections.set_mapping(school.id, table, request.mapping, _actor(admin))
    return {"table": table, "mapping": {k: v for k, v in request.mapping.items() if v}}


# =========================================================
# Syncing
# =========================================================

class SyncRequest(BaseModel):
    trigger: str = Field(default="manual", pattern="^(manual|initial)$")


@router.post("/schools/{school_id}/sync", status_code=202)
async def start_sync(school_id: str, admin: Admin, request: SyncRequest | None = None):
    """Sync now, in the background - the run shows up in the history straight away."""
    from backend.microservices.livekit_Rag_services.services.integrations import sync

    school = await _scoped(admin, school_id)
    if school.records is None:
        _fail(409, "Connect a records system first.")
    try:
        run_id = await sync.start(school.id, (request or SyncRequest()).trigger, _actor(admin))
    except sync.Busy:
        _fail(409, "A sync of this school is already running.")
    return {"run_id": run_id, "state": "started"}


# =========================================================
# Excel / CSV uploads (Excel and Native Records schools)
# =========================================================

@router.post("/schools/{school_id}/upload/{table}")
async def upload_table(school_id: str, table: str, admin: Admin, file: UploadFile = File(...),
                       mapping: str = Form(default=""), dry_run: bool = Form(default=False)):
    """
    One table as an .xlsx / .csv file. dry_run: the columns, the suggested
    mapping and the first rows - nothing saved. Otherwise the file's rows
    replace the school's copy of that table.
    """
    from backend.microservices.livekit_Rag_services.services.erp_services import connections
    from backend.microservices.livekit_Rag_services.services.integrations import canonical, store, sync
    from backend.microservices.livekit_Rag_services.services.integrations.base import SourceError
    from backend.microservices.livekit_Rag_services.services.integrations.generic import excel

    school = await _scoped(admin, school_id)
    if table not in canonical.TABLES:
        _fail(404, "No such table")
    if school.records not in ("excel", "native"):
        _fail(409, "Uploads are for schools on Excel / CSV or Native Records - choose one of them first.")
    try:
        chosen = json.loads(mapping) if mapping.strip() else None
    except ValueError:
        _fail(422, "The mapping is not valid JSON.")
    if chosen is not None and not isinstance(chosen, dict):
        _fail(422, "The mapping must map each field to a column.")
    content = await file.read(excel.MAX_BYTES + 1)
    name = file.filename or "upload.csv"
    try:
        if dry_run:
            return excel.preview(table, name, content, chosen)
        outcome = await excel.import_file(school.id, table, name, content, chosen,
                                          source="native" if school.records == "native" else "excel")
    except SourceError as error:
        _fail(422, str(error))

    await connections.ensure(school.id, school.records, _actor(admin))
    await connections.set_mapping(school.id, table, outcome["mapping"], _actor(admin))
    counts = {k: v for k, v in (await store.counts(school.id)).items() if v}
    summary = f"{table}: {outcome['rows']} rows from {name}" + (f" ({outcome['skipped']} left out)" if outcome["skipped"] else "")
    run_id = await sync.record_run(school.id, school.records, "upload", _actor(admin), {
        "status": "success", "attempts": 1, "counts": counts, "summary": summary, "error": None})
    await connections.record_sync(school.id, school.records, "success", summary, counts)
    return {**outcome, "run_id": run_id, "counts": counts}


# =========================================================
# Google Sheets links - for the school's admin too
# =========================================================

class SheetLinkRequest(BaseModel):
    url: str = Field(min_length=10, max_length=2000)


@router.put("/schools/{school_id}/sheets/{table}")
async def link_sheet(school_id: str, table: str, request: SheetLinkRequest, admin: Admin):
    """One table's live link - read and checked now, copied into the canonical records, then re-read on the timer."""
    from backend.microservices.livekit_Rag_services.services import tenants
    from backend.microservices.livekit_Rag_services.services.erp_services import connections, records_sync, spreadsheet
    from backend.microservices.livekit_Rag_services.services.integrations.generic import google_sheets

    school = await _scoped(admin, school_id)
    if school.records != "spreadsheet":
        _fail(409, "Choose Google Sheets as the records system first.")
    if table not in spreadsheet.TABLES:
        _fail(404, "No such table")
    connection = await connections.ensure(school.id, "spreadsheet", _actor(admin))
    try:
        meta = await records_sync.connect(tenants.records_dir(school.id), table, request.url,
                                          (connection.mapping or {}).get(table))
    except (records_sync.LinkError, spreadsheet.SpreadsheetError) as error:
        _fail(422, str(error))
    rows = await google_sheets.import_table(school.id, table)
    print(f"[Integrations] {school.id}: {table} sheet linked ({rows} rows)")
    return {"table": table, "link": meta, "rows": rows}


@router.delete("/schools/{school_id}/sheets/{table}")
async def unlink_sheet(school_id: str, table: str, admin: Admin):
    from backend.microservices.livekit_Rag_services.services import tenants
    from backend.microservices.livekit_Rag_services.services.erp_services import spreadsheet
    from backend.microservices.livekit_Rag_services.services.integrations import store

    school = await _scoped(admin, school_id)
    if table not in spreadsheet.TABLES or not spreadsheet.remove(tenants.records_dir(school.id), table):
        _fail(404, "No such link")
    await store.replace_table(school.id, table, [], "sheets")
    return {"removed": table}


# =========================================================
# Native Records - the school admin's own school only
# =========================================================

async def _own_records(admin, write: bool):
    """The school a Native Records request is about: always the admin's own."""
    if is_super_admin(admin):
        _fail(403, "A school's records are kept by that school's admin.")
    school = await _known(caller_school(admin))
    from backend.microservices.livekit_Rag_services.services.integrations import registry

    provider = registry.get(school.records)
    if write and school.records != "native":
        _fail(409, "This school's records come from its connected system - choose Vocira Native Records to edit them here.")
    if not write and (provider is None or provider.mode not in ("sync", "native")):
        _fail(409, "This school's records are read live from its system - there is no copy in Vocira to show.")
    return school


def _table(table: str) -> str:
    from backend.microservices.livekit_Rag_services.services.integrations import canonical

    if table not in canonical.TABLES:
        _fail(404, "No such table")
    return table


class RegisterRequest(BaseModel):
    date: str | None = None
    marks: dict[str, str] = Field(default_factory=dict)


@records_router.get("/attendance/register")
async def attendance_register(admin: Admin, class_name: str = Query("", alias="class"), date: str = ""):
    """A class's students and what each is marked on a day - with the classes to choose from."""
    from datetime import date as today
    from backend.microservices.livekit_Rag_services.services.integrations import normalizer, store

    school = await _own_records(admin, write=False)
    day = normalizer.iso_date(date) if date else today.today().isoformat()
    classes = await store.class_names(school.id)
    chosen = class_name or (classes[0] if classes else "")
    return {"date": day, "class": chosen, "classes": classes,
            "students": await store.register(school.id, chosen, day) if chosen else []}


@records_router.post("/attendance/register")
async def save_register(request: RegisterRequest, admin: Admin):
    from backend.microservices.livekit_Rag_services.services.integrations import native

    school = await _own_records(admin, write=True)
    try:
        marked = await native.mark_attendance(school.id, request.date, request.marks)
    except native.NativeError as error:
        _fail(422, str(error))
    return {"marked": marked}


@records_router.get("/{table}")
async def list_records(table: str, admin: Admin, q: str = "", limit: int = Query(50, ge=1, le=200),
                       offset: int = Query(0, ge=0)):
    from backend.microservices.livekit_Rag_services.services.integrations import store

    school = await _own_records(admin, write=False)
    rows, total = await store.list_rows(school.id, _table(table), q, limit, offset)
    return {"rows": rows, "total": total, "editable": school.records == "native"}


@records_router.post("/{table}", status_code=201)
async def create_record(table: str, data: dict[str, Any], admin: Admin):
    from backend.microservices.livekit_Rag_services.services.integrations import native

    school = await _own_records(admin, write=True)
    try:
        return await native.create(school.id, _table(table), data)
    except native.NativeError as error:
        _fail(422, str(error))


@records_router.patch("/{table}/{row_id}")
async def update_record(table: str, row_id: int, data: dict[str, Any], admin: Admin):
    from backend.microservices.livekit_Rag_services.services.integrations import native

    school = await _own_records(admin, write=True)
    try:
        updated = await native.update(school.id, _table(table), row_id, data)
    except native.NativeError as error:
        _fail(422, str(error))
    if updated is None:
        _fail(404, "Record not found")
    return updated


@records_router.delete("/{table}/{row_id}")
async def delete_record(table: str, row_id: int, admin: Admin):
    from backend.microservices.livekit_Rag_services.services.integrations import native

    school = await _own_records(admin, write=True)
    if not await native.remove(school.id, _table(table), row_id):
        _fail(404, "Record not found")
    return {"deleted": row_id}
