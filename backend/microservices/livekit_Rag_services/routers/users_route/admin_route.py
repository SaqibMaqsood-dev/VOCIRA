"""
Endpoints for the admin panel.

The admin side of the frontend used to run entirely on the fake data
in `data.js` - 122 hardcoded lines and no backend call at all. The
backend already had escalations, messages and sessions; what it
lacked was an admin-wide view of them (that is, across ALL users):
`/sessions/stats` only counts the caller's own.

Every endpoint sits behind `require_admin`.
"""

import json

from datetime import datetime, timedelta
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.helper_functions.database.session import get_db
from backend.helper_functions.token_service.access_tokken.require_admin import (
    caller_school,
    is_super_admin,
    require_admin,
    require_super_admin,
)
from backend.microservices.livekit_Rag_services.models.escalation_model import (
    Escalation,
    EscalationStatus,
)
from backend.microservices.livekit_Rag_services.models.message_model import (
    Message,
    SenderTypeEnum,
)
from backend.microservices.livekit_Rag_services.models.session_model import Session
from backend.microservices.auth_services.models.user_model import Users


router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
    dependencies=[Depends(require_admin)],
)


# The question is the message the user spoke; the answer is the
# one the agent gave back.
_USER_SIDE = (SenderTypeEnum.user, SenderTypeEnum.guest)


def _status_for(message_id, escalated_ids: set) -> str:
    """The frontend thinks in three states."""
    return "Escalated" if message_id in escalated_ids else "Resolved"


# =========================================================
# DASHBOARD
# =========================================================

async def _scope(admin, requested: str | None = None) -> str | None:
    """
    The school a request covers. A school admin: always their own,
    whatever they ask for. A super admin: the school they ask for, or
    None - every school.
    """
    from backend.microservices.livekit_Rag_services.services import tenants

    own = caller_school(admin)
    if own is not None:
        return own
    if requested:
        await tenants.refresh(force=not tenants.is_known(requested))
        if tenants.is_known(requested):
            return tenants.get_school(requested).id
    return None


def _in_scope(stmt, scope: str | None):
    """Only the messages of the scope's calls."""
    if scope is None:
        return stmt
    return stmt.where(
        Message.session_id.in_(select(Session.id).where(Session.school_id == scope))
    )


@router.get("/stats")
async def admin_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[object, Depends(require_admin)],
    school: str | None = None,
):
    """The cards across the top of the dashboard, plus both charts."""

    scope = await _scope(admin, school)

    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=6)

    async def count_messages(since=None):
        stmt = _in_scope(select(func.count()).select_from(Message).where(
            Message.sender_type.in_(_USER_SIDE)
        ), scope)
        if since is not None:
            stmt = stmt.where(Message.created_at >= since)
        return (await db.execute(stmt)).scalar_one()

    today = await count_messages(today_start)
    week = await count_messages(week_start)
    total = await count_messages()

    escalated = (
        await db.execute(_in_scope(
            select(func.count()).select_from(Escalation)
            .join(Message, Message.id == Escalation.message_id),
            scope,
        ))
    ).scalar_one()

    sessions_stmt = select(func.count()).select_from(Session)
    if scope is not None:
        sessions_stmt = sessions_stmt.where(Session.school_id == scope)
    sessions = (await db.execute(sessions_stmt)).scalar_one()

    # ---- pichhle 7 din, roz ke sawal ----
    per_day_rows = (
        await db.execute(
            select(
                func.date(Message.created_at).label("day"),
                func.count().label("value"),
            )
            .where(
                Message.sender_type.in_(_USER_SIDE),
                Message.created_at >= week_start,
                *(
                    [Message.session_id.in_(select(Session.id).where(Session.school_id == scope))]
                    if scope is not None else []
                ),
            )
            .group_by("day")
            .order_by("day")
        )
    ).all()

    counts = {str(row.day): row.value for row in per_day_rows}

    queries_per_day = []
    for offset in range(6, -1, -1):
        day = (today_start - timedelta(days=offset)).date()
        queries_per_day.append(
            {
                "day": day.strftime("%a"),
                "date": str(day),
                "value": counts.get(str(day), 0),
            }
        )

    # ---- kitne AI ne hal kiye, kitne aage bheje gaye ----
    resolved = max(total - escalated, 0)
    denominator = total or 1

    escalation_rate = [
        {
            "label": "AI Resolved",
            "value": round(100 * resolved / denominator),
        },
        {
            "label": "Escalated",
            "value": round(100 * escalated / denominator),
        },
    ]

    return {
        "today": today,
        "week": week,
        "total": total,
        "escalated": escalated,
        "sessions": sessions,
        "queriesPerDay": queries_per_day,
        "escalationRate": escalation_rate,
    }


# =========================================================
# SAARE SAWAL (sab users ke)
# =========================================================

@router.get("/queries")
async def admin_queries(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[object, Depends(require_admin)],
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    school: str | None = None,
):
    """
    A question paired with its answer.

    Messages all live in one table, so the ai-message that follows a
    user-message in the same session is taken to be its answer - the
    same order the voice pipeline writes them in.
    """

    scope = await _scope(admin, school)

    rows = (
        await db.execute(
            _in_scope(select(Message), scope)
            .order_by(Message.created_at.desc())
            .limit(limit * 2 + 20)
            .offset(skip)
        )
    ).scalars().all()

    escalated_ids = set(
        (
            await db.execute(select(Escalation.message_id))
        ).scalars().all()
    )

    # oldest first, so an answer is easy to find
    rows = list(reversed(rows))

    # -----------------------------------------------------------
    # WHO ASKED
    #
    # Every row just said "Parent" - the admin panel could not tell
    # one guardian's questions from another's, which is exactly what
    # grouping by guardian needs. Message.user_id already points at
    # the same `users` table auth_services owns (Users.extend_existing
    # keeps both services pointed at one physical table), so this is
    # a single batched lookup, not a query per row.
    # -----------------------------------------------------------

    user_ids = {
        row.user_id
        for row in rows
        if row.sender_type is SenderTypeEnum.user and row.user_id
    }

    users_by_id = {}
    if user_ids:
        user_rows = (
            await db.execute(
                select(Users.user_id, Users.name, Users.email)
                .where(Users.user_id.in_(user_ids))
            )
        ).all()
        users_by_id = {
            uid: {"name": name, "email": email}
            for uid, name, email in user_rows
        }

    out = []

    for index, row in enumerate(rows):

        if row.sender_type not in _USER_SIDE:
            continue

        answer = None

        for later in rows[index + 1:]:
            if later.session_id != row.session_id:
                continue
            if later.sender_type is SenderTypeEnum.ai:
                answer = later.content
            break

        if row.sender_type is SenderTypeEnum.guest or not row.user_id:
            user_key = "guest"
            user_name = "Guest"
            user_email = None
        else:
            info = users_by_id.get(row.user_id)
            user_key = str(row.user_id)
            user_name = (info or {}).get("name") or "Parent"
            user_email = (info or {}).get("email")

        out.append(
            {
                "id": str(row.id),
                "sessionId": str(row.session_id),
                "userId": user_key,
                "user": user_name,
                "userEmail": user_email,
                "question": row.content,
                "response": answer or "—",
                "status": _status_for(row.id, escalated_ids),
                "intent": row.intent,
                "timestamp": row.created_at.isoformat(),
            }
        )

    out.reverse()          # naye pehle
    return out[:limit]


# =========================================================
# ESCALATIONS
# =========================================================

@router.get("/escalations")
async def admin_escalations(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[object, Depends(require_admin)],
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    school: str | None = None,
):
    """An escalation together with the question that caused it."""

    scope = await _scope(admin, school)

    rows = (
        await db.execute(
            _in_scope(
                select(Escalation, Message)
                .join(Message, Message.id == Escalation.message_id),
                scope,
            )
            .order_by(Escalation.created_at.desc())
            .limit(limit)
            .offset(skip)
        )
    ).all()

    return [
        {
            "id": str(escalation.id),
            "question": message.content,
            "sessionId": str(message.session_id),
            "status": escalation.status.value
            if hasattr(escalation.status, "value")
            else str(escalation.status),
            "userId": str(escalation.user_id) if escalation.user_id else None,
            "time": escalation.created_at.isoformat(),
        }
        for escalation, message in rows
    ]


# =========================================================
# KNOWLEDGE BASE
# =========================================================

async def _school_kinds(school: str | None, admin=None):
    """
    The school whose knowledge this request touches, and its document
    folders: always the school admin's own, whatever they ask for. A
    school's knowledge is its own admin's to manage - not the super
    admin's, who runs the platform (the Schools page shows each one's
    chunk count and last sync).
    """
    from backend.microservices.livekit_Rag_services.services import tenants
    from backend.microservices.livekit_Rag_services.services.rag_engine import documents

    if admin is not None and is_super_admin(admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A school's knowledge is managed by that school's admin.",
        )

    own = caller_school(admin) if admin is not None else None
    if own is not None:
        school = own
    await tenants.refresh(force=not tenants.is_known(school))
    chosen = tenants.get_school(school)
    return chosen, documents.kinds_for(chosen.pdf_dir, chosen.text_dir)


class SchoolRequest(BaseModel):
    name: str = Field(min_length=3, max_length=80)
    name_ur: str | None = Field(default=None, max_length=80)
    helpline: str = Field(min_length=6, max_length=30)
    records: str | None = None
    records_env_prefix: str | None = Field(default=None, max_length=40)
    # the school's own address (<subdomain>.vocira.com); empty = its id
    subdomain: str | None = Field(default=None, max_length=40)


@router.post("/schools", status_code=201, dependencies=[Depends(require_super_admin)])
async def admin_add_school(request: SchoolRequest):
    """
    Add a school - no code change. It gets its own knowledge base
    (namespace and folders, from its id) straight away; documents are
    added on the Knowledge page, and guests reach it by its link.
    """
    from backend.microservices.livekit_Rag_services.services import tenants

    try:
        school = await tenants.create_school(**request.model_dump())
    except tenants.TenantError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error))

    print(f"[Schools] added: {school.id} ({school.name})")
    return {"id": school.id, "name": school.name, "namespace": school.namespace,
            "subdomain": tenants.address_of(school), "guest_link": f"/s/{school.id}"}


@router.patch("/schools/{school_id}", dependencies=[Depends(require_super_admin)])
async def admin_update_school(school_id: str, request: SchoolRequest):
    """Change a school (name, helpline, records). A built-in school's
    records are set in code - only its name and helpline change."""
    from backend.microservices.livekit_Rag_services.services import tenants

    changes = request.model_dump()
    if "subdomain" not in request.model_fields_set:
        # an older caller that does not know about addresses keeps the school's
        changes.pop("subdomain")
    try:
        school = await tenants.update_school(school_id, **changes)
    except tenants.TenantError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error))
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="School not found")

    return {"id": school.id, "name": school.name, "subdomain": tenants.address_of(school)}


@router.delete("/schools/{school_id}")
async def admin_delete_school(school_id: str, admin: Annotated[object, Depends(require_super_admin)]):
    """
    Remove a school. An added school's knowledge is cleared from the
    index so it can never answer again; a school defined in code keeps
    its knowledge and documents on the server (it is only marked
    removed). Either way its records connection - with its keys - and its
    records spreadsheets go. The last school cannot be removed.
    """
    import os

    from backend.microservices.livekit_Rag_services.routers.users_route import rag_route
    from backend.microservices.livekit_Rag_services.services import tenants
    from backend.microservices.livekit_Rag_services.services.erp_services import connections, spreadsheet
    from backend.microservices.livekit_Rag_services.services.rag_engine.vectorstore import clear_namespace

    if rag_route._sync_lock.locked():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A sync is running - try again shortly.")

    built_in = tenants.is_built_in(school_id)
    try:
        school = await tenants.delete_school(school_id)
    except tenants.TenantError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error))
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="School not found")

    if not built_in:
        try:
            await clear_namespace(school.namespace)
        except Exception as exc:
            print(f"[Schools] could not clear {school.namespace}: {exc}")
        # Its sync record goes too; its uploaded files stay on disk.
        rag_route._sync_states.pop(school.id, None)
        try:
            os.remove(rag_route._state_file(school.id))
        except FileNotFoundError:
            pass

    # Its connection's keys and its records spreadsheets are the
    # school's - and students' personal data. They go with it.
    await connections.delete(school.id, getattr(admin, "username", None))
    spreadsheet.remove_all(tenants.records_dir(school.id))

    print(f"[Schools] removed: {school.id}{' (defined in code - knowledge kept)' if built_in else ''}")
    return {"removed": school.id}


# ---------------------------------------------------------
# A school's records as live spreadsheet links (records = "spreadsheet")
# ---------------------------------------------------------

async def _known_school(school_id: str):
    from backend.microservices.livekit_Rag_services.services import tenants

    await tenants.refresh(force=not tenants.is_known(school_id))
    if not tenants.is_known(school_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="School not found")
    return tenants.get_school(school_id)


@router.get("/schools/{school_id}/records", dependencies=[Depends(require_super_admin)])
async def admin_school_records(school_id: str):
    """The tables a spreadsheet school's records are read from - what
    each needs, its live link and how its syncing is going."""
    from backend.microservices.livekit_Rag_services.services import tenants
    from backend.microservices.livekit_Rag_services.services.erp_services import records_sync, spreadsheet

    school = await _known_school(school_id)
    folder = tenants.records_dir(school.id)
    return {
        "school": school.id,
        "records": school.records,
        "ready": spreadsheet.has_table(folder, "students"),
        "sync_minutes": records_sync.SYNC_MINUTES,
        "last_round_at": records_sync.last_round_at,
        "next_round_at": records_sync.next_round_at,
        "tables": spreadsheet.status(folder),
    }


class RecordsLinkRequest(BaseModel):
    url: str = Field(min_length=10, max_length=2000)


@router.put("/schools/{school_id}/records/{table}/link", dependencies=[Depends(require_super_admin)])
async def admin_link_records(school_id: str, table: str, request: RecordsLinkRequest):
    """
    Connect (or change) one table's live link - a Google Sheet tab or an
    online CSV / Excel file. It is read and checked straight away and
    kept only if it gives a usable sheet; from then on it is re-read on
    the timer.
    """
    from backend.microservices.livekit_Rag_services.services import tenants
    from backend.microservices.livekit_Rag_services.services.erp_services import records_sync, spreadsheet

    school = await _known_school(school_id)
    if school.records != "spreadsheet":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="Set this school's student records to Live spreadsheet first.")
    if table not in spreadsheet.TABLES:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such table")

    folder = tenants.records_dir(school.id)
    try:
        meta = await records_sync.connect(folder, table, request.url)
    except (records_sync.LinkError, spreadsheet.SpreadsheetError) as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error))

    if table != "students" and spreadsheet.has_table(folder, "students"):
        known = {r["student_id"].strip().lower() for r in spreadsheet.rows(folder, "students")}
        unknown = sorted({r["student_id"] for r in spreadsheet.rows(folder, table)
                          if r["student_id"].strip().lower() not in known})
        if unknown:
            meta = spreadsheet.update_meta(folder, table, warnings=meta["warnings"] + [
                f"{len(unknown)} student id(s) are not in Students (e.g. {', '.join(unknown[:3])}) - "
                "their rows are never read out."
            ])

    print(f"[Records] {school.id}: {table} linked ({meta['rows']} rows)")
    return {"table": table, "link": meta}


@router.post("/schools/{school_id}/records/sync", dependencies=[Depends(require_super_admin)])
async def admin_sync_records(school_id: str):
    """Re-read every linked table of the school now ("Sync now")."""
    from backend.microservices.livekit_Rag_services.services import tenants
    from backend.microservices.livekit_Rag_services.services.erp_services import records_sync

    school = await _known_school(school_id)
    results = await records_sync.sync_school(school.id, tenants.records_dir(school.id))
    return {"results": [r for r in results if not r.get("skipped")]}


@router.delete("/schools/{school_id}/records/{table}", dependencies=[Depends(require_super_admin)])
async def admin_remove_records(school_id: str, table: str):
    from backend.microservices.livekit_Rag_services.services import tenants
    from backend.microservices.livekit_Rag_services.services.erp_services import spreadsheet

    school = await _known_school(school_id)
    if table not in spreadsheet.TABLES or not spreadsheet.remove(tenants.records_dir(school.id), table):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such link")
    print(f"[Records] {school.id}: {table} removed")
    return {"removed": table}


# ---------------------------------------------------------
# A school's connection to its records system (ERPNext, Open School MIS, ...)
# ---------------------------------------------------------

class ConnectionRequest(BaseModel):
    kind: str = Field(max_length=30)
    settings: dict[str, str] = Field(default_factory=dict)
    # left empty: keep the secret already saved (the panel never has it)
    secrets: dict[str, str] = Field(default_factory=dict)
    capabilities: list[str] = Field(default_factory=list)
    allow_private_network: bool = False


@router.get("/connectors", dependencies=[Depends(require_super_admin)])
async def admin_connectors():
    """The records systems a school can be connected to, and what each needs."""
    from backend.microservices.livekit_Rag_services.services.erp_services import connectors

    return {"connectors": connectors.catalogue()}


async def _connectable_school(school_id: str):
    # every school - the first one too - is connected on the Schools page
    return await _known_school(school_id)


async def _checked(request: ConnectionRequest, school_id: str, for_test: bool):
    """The request's kind, settings and secrets - checked against what the kind needs."""
    from backend.microservices.livekit_Rag_services.services.erp_services import connections, connectors

    kind = connectors.KINDS.get(request.kind)
    if kind is None or kind.setup != "connection":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=f"Unknown records system '{request.kind}'.")
    saved = connections.get(school_id)
    saved_secrets = saved.secrets if saved is not None and saved.kind == request.kind else {}
    settings, secrets, missing = {}, {}, []
    for f in kind.fields:
        if f.kind == "secret":
            value = (request.secrets.get(f.key) or "").strip()
            if value:
                secrets[f.key] = value
            elif f.required and not saved_secrets.get(f.key):
                missing.append(f.label)
        else:
            value = (request.settings.get(f.key) or "").strip()
            if value:
                settings[f.key] = value
            elif f.required:
                missing.append(f.label)
    if missing:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Needed: {', '.join(missing)}.")
    unknown = [c for c in request.capabilities if c not in kind.capabilities]
    if unknown:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=f"{kind.label} cannot read: {', '.join(unknown)}.")
    if not for_test and not request.capabilities:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="Choose at least one kind of data Vocira may read.")
    try:
        await connectors.check_address(settings.get("base_url", ""), request.allow_private_network)
    except connections.ConnectionSettingsError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error))
    return kind, settings, secrets, saved_secrets


@router.get("/schools/{school_id}/connection")
async def admin_school_connection(school_id: str, admin: Annotated[object, Depends(require_super_admin)]):
    """The school's connection - its settings, which secrets are set (never the secrets), its last test and history."""
    from backend.microservices.livekit_Rag_services.services.erp_services import connections

    await _known_school(school_id)
    return {"connection": await connections.view(school_id)}


@router.post("/schools/{school_id}/connection/test")
async def admin_test_connection(school_id: str, request: ConnectionRequest,
                                admin: Annotated[object, Depends(require_super_admin)]):
    """
    Try the connection as typed in the form (secrets left empty: the saved
    ones) - sign in, count students and guardians, try each kind of data.
    Nothing is saved but the result.
    """
    from backend.microservices.livekit_Rag_services.services.erp_services import connections

    await _connectable_school(school_id)
    kind, settings, secrets, saved_secrets = await _checked(request, school_id, for_test=True)
    try:
        result = await kind.test(settings, {**saved_secrets, **secrets}, request.allow_private_network)
    except Exception as error:  # an adapter's surprise is still an answer to show
        result = {"ok": False, "steps": [{"name": "Test", "ok": False, "detail": f"{type(error).__name__}: {error}"}],
                  "capabilities": [], "counts": {}}
    summary = "; ".join(f"{'✓' if s['ok'] else '✗'} {s['name']}: {s['detail']}" for s in result["steps"])
    await connections.record_test(school_id, kind.kind, result["ok"], summary, getattr(admin, "username", None))
    return result


@router.put("/schools/{school_id}/connection")
async def admin_save_connection(school_id: str, request: ConnectionRequest,
                                admin: Annotated[object, Depends(require_super_admin)]):
    """Connect the school to its records system (or change the connection). Secrets are stored encrypted."""
    from backend.microservices.livekit_Rag_services.services import tenants
    from backend.microservices.livekit_Rag_services.services.erp_services import connections

    school = await _connectable_school(school_id)
    kind, settings, secrets, _ = await _checked(request, school_id, for_test=False)
    try:
        await connections.save(school.id, kind.kind, settings, secrets, request.capabilities,
                               request.allow_private_network, getattr(admin, "username", None))
        if school.records != kind.kind:
            await tenants.update_school(school.id, name=school.name, helpline=school.helpline,
                                        name_ur=school.name_ur, records=kind.kind, records_env_prefix=None)
    except connections.ConnectionSettingsError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error))
    except tenants.TenantError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error))
    print(f"[Connections] {school.id}: {kind.kind} saved by {getattr(admin, 'username', '?')}")
    return {"connection": await connections.view(school.id)}


@router.delete("/schools/{school_id}/connection")
async def admin_disconnect(school_id: str, admin: Annotated[object, Depends(require_super_admin)]):
    """Disconnect: the settings and secrets are deleted and the school answers general questions only."""
    from backend.microservices.livekit_Rag_services.services import tenants
    from backend.microservices.livekit_Rag_services.services.erp_services import connections

    school = await _connectable_school(school_id)
    removed = await connections.delete(school.id, getattr(admin, "username", None))
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This school has no connection.")
    if school.records not in (None, "spreadsheet"):
        await tenants.update_school(school.id, name=school.name, helpline=school.helpline,
                                    name_ur=school.name_ur, records=None, records_env_prefix=None)
    print(f"[Connections] {school.id}: disconnected by {getattr(admin, 'username', '?')}")
    return {"disconnected": school.id}


@router.get("/schools")
async def admin_schools(admin: Annotated[object, Depends(require_admin)] = None):
    """
    The schools this deployment serves - one agent, a knowledge base and
    a records connector per school. Feeds the knowledge page's picker
    and the Schools page.
    """
    from backend.microservices.livekit_Rag_services.routers.users_route import (
        rag_route,
    )
    from backend.microservices.livekit_Rag_services.services import tenants
    from backend.microservices.livekit_Rag_services.services.erp_services import connections, spreadsheet
    from backend.microservices.livekit_Rag_services.services.rag_engine.vectorstore import (
        namespace_vector_counts,
    )

    await tenants.refresh(force=True)
    connection_views = {}
    if not (caller_school(admin) if admin is not None else None):
        # the super admin sees how each school's connection is doing
        for school_id in tenants.all_schools():
            if connections.get(school_id) is not None:
                connection_views[school_id] = await connections.view(school_id)

    try:
        counts = await namespace_vector_counts()
    except Exception as exc:
        print(f"[Schools] could not read the vector counts: {exc}")
        counts = None

    # A school's admin sees only their own school; the super admin all.
    own = caller_school(admin) if admin is not None else None

    schools = []
    for school in tenants.public_list():
        if own is not None and school["id"] != own:
            continue
        last = rag_route.sync_state(school["id"])
        schools.append({
            **school,
            # a spreadsheet school answers about children only once it
            # has its Students table
            # a spreadsheet school is ready once it has its Students table; a
            # connected system once its connection is saved (the first school
            # always - its ERP is the service's own)
            "records_ready": (
                spreadsheet.has_table(tenants.records_dir(school["id"]), "students")
                if school["records"] == "spreadsheet"
                else school["records"] is None or bool(school["records_env_prefix"])
                or (connections.get(school["id"]) is not None and connections.get(school["id"]).kind == school["records"])
            ),
            "connection_test_failed": bool(
                (view := connection_views.get(school["id"])) and view.get("last_test") and view["last_test"]["ok"] is False
            ),
            # a live link's last try failed - the school still answers
            # from the last good copy, but someone should look
            "records_sync_failing": school["records"] == "spreadsheet" and any(
                (spreadsheet.read_meta(tenants.records_dir(school["id"]), table) or {}).get("last_error")
                for table in spreadsheet.TABLES
            ),
            "vectors": None if counts is None else counts.get(school["namespace"], 0),
            "last_sync": {"state": last.get("state"), "finished_at": last.get("finished_at")},
            "guest_link": f"/s/{school['id']}",
        })

    return {"schools": schools, "default": tenants.default_school_id()}


@router.get("/knowledge")
async def admin_knowledge(school: str | None = None, admin: Annotated[object, Depends(require_admin)] = None):
    """
    Knowledge base ki asli halat.

    This page used to show a fake list of "articles". The real
    knowledge base is the Pinecone index - that is where RAG answers
    come from. /rag/status returns the same thing, but it sits behind
    an internal key, hence this admin-facing copy.
    """

    from backend.microservices.livekit_Rag_services.routers.users_route import (
        rag_route,
    )
    from backend.microservices.livekit_Rag_services.services.rag_engine.vectorstore import (
        get_index_stats,
    )

    chosen, _ = await _school_kinds(school, admin)

    try:
        stats = await get_index_stats(namespace=chosen.namespace)
    except Exception as exc:
        stats = {"error": f"{type(exc).__name__}: {exc}"}

    return {
        "school": chosen.id,
        "index": stats,
        "last_sync": rag_route.sync_state(chosen.id),
    }


@router.post("/knowledge/sync", status_code=202)
async def admin_sync_knowledge(school: str | None = None, admin: Annotated[object, Depends(require_admin)] = None):
    """One school's knowledge base dobara banayein (background mein)."""

    import asyncio

    from backend.microservices.livekit_Rag_services.routers.users_route import (
        rag_route,
    )

    # One sync at a time across schools - they share the index.
    if rag_route._sync_lock.locked():
        return {"state": "running", "message": "A sync is already running."}

    chosen, _ = await _school_kinds(school, admin)
    asyncio.create_task(rag_route._run_sync(chosen.id))

    return {
        "state": "started",
        "message": "Sync started in the background.",
    }


@router.patch("/escalations/{escalation_id}/status")
async def set_escalation_status(
    escalation_id: str,
    new_status: EscalationStatus,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[object, Depends(require_admin)],
):
    """Escalation ka status badlein (Resolve / Open waghera)."""

    scope = await _scope(admin)

    escalation = (
        await db.execute(
            _in_scope(
                select(Escalation)
                .join(Message, Message.id == Escalation.message_id)
                .where(Escalation.id == escalation_id),
                scope,
            )
        )
    ).scalar_one_or_none()

    if escalation is None:
        return {"updated": False, "reason": "not found"}

    escalation.status = new_status
    await db.commit()

    return {"updated": True, "id": escalation_id, "status": new_status.value}


# =========================================================
# KNOWLEDGE BASE - DOCUMENTS
#
# There used to be exactly one way to add new data: put the file on
# the server by hand, then press sync. It can now be done from the
# panel itself.
# =========================================================

@router.get("/knowledge/documents")
async def admin_knowledge_documents(school: str | None = None, admin: Annotated[object, Depends(require_admin)] = None):
    """
    Which documents exist, and how many chunks each produced.

    The chunk counts come from the last sync. A file added after that
    has a null count - meaning "not in the index yet, run a sync".
    """

    from backend.microservices.livekit_Rag_services.routers.users_route import (
        rag_route,
    )
    from backend.microservices.livekit_Rag_services.services.rag_engine import (
        documents,
    )

    chosen, kinds = await _school_kinds(school, admin)
    sources = rag_route.sync_state(chosen.id).get("sources") or {}

    docs = documents.list_documents(chunks_by_source=sources, kinds=kinds)

    return {
        "documents": docs,
        "total": len(docs),
        "indexed": sum(1 for d in docs if d["indexed"]),
        "chunks": sum(d["chunks"] or 0 for d in docs),
    }


@router.post("/knowledge/documents", status_code=201)
async def admin_upload_document(file: UploadFile = File(...), school: str | None = None,
                                admin: Annotated[object, Depends(require_admin)] = None):
    """PDF ya TXT upload karein."""

    from backend.microservices.livekit_Rag_services.services.rag_engine import (
        documents,
    )

    content = await file.read()

    try:
        _, kinds = await _school_kinds(school, admin)
        saved = documents.save_upload(
            filename=file.filename,
            content=content,
            kinds=kinds,
        )
    except documents.DocumentError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        )

    print(f"[Knowledge] upload: {saved['name']} ({saved['size']} bytes)")

    return {**saved, "message": "Uploaded. Run a sync to index it."}


class NoteRequest(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    text: str = Field(min_length=10, max_length=20000)


@router.post("/knowledge/notes", status_code=201)
async def admin_add_note(request: NoteRequest, school: str | None = None,
                         admin: Annotated[object, Depends(require_admin)] = None):
    """
    Write a short note directly - no need to produce a PDF.

    The note lands in the same text_files folder as a .txt, so as far
    as ingestion is concerned it is no different from any other file.
    """

    from backend.microservices.livekit_Rag_services.services.rag_engine import (
        documents,
    )

    try:
        _, kinds = await _school_kinds(school, admin)
        saved = documents.save_note(
            title=request.title,
            text=request.text,
            kinds=kinds,
        )
    except documents.DocumentError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        )

    print(f"[Knowledge] note: {saved['name']}")

    return {**saved, "message": "Saved. Run a sync to index it."}


@router.delete("/knowledge/documents/{name}")
async def admin_delete_document(name: str, school: str | None = None,
                                admin: Annotated[object, Depends(require_admin)] = None):
    """Document hatayein. Index se wo agli sync par nikalta hai."""

    from backend.microservices.livekit_Rag_services.services.rag_engine import (
        documents,
    )

    try:
        _, kinds = await _school_kinds(school, admin)
        removed = documents.delete_document(name, kinds=kinds)
    except documents.DocumentError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        )

    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    print(f"[Knowledge] deleted: {name}")

    return {"deleted": True, "name": name}


# =========================================================
# ERPNEXT GUARDIANS
#
# The admin panel's Users page used to ask for a Guardian ID when
# creating an account - typed in by hand. One character out of place
# and the account reached no child at all, and the mistake only
# surfaced when the parent complained.
#
# It is now picked from a list, and the email is filled in from
# ERPNext automatically. This endpoint lives here (rather than in the
# auth service) because this service is the one with ERP access.
# =========================================================

@router.get("/guardians")
async def admin_guardians(admin: Annotated[object, Depends(require_admin)] = None):
    """
    The school's guardians from its records system - naam, email aur
    kitne bachche - for the Accounts page to link parent logins to.

    The email can be empty. We do not invent one in that case: the
    account is created against the email the parent will log in with,
    and a guessed address is of no use to them.
    """

    from backend.microservices.livekit_Rag_services.services import tenants
    from backend.microservices.livekit_Rag_services.services.erp_services import connectors

    # The guardians of the admin's own school, from whatever records system
    # it is connected to - ERPNext, Open School MIS or its live sheets. (An
    # older token without a school, and the super admin: the first school.)
    own = caller_school(admin) if admin is not None else None
    await tenants.refresh(force=bool(own) and not tenants.is_known(own))
    school = tenants.get_school(own)
    if own is not None and school.id != own:
        return []
    try:
        return await connectors.connector_for(school).guardians()
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not reach the school system: {getattr(error, 'detail', None) or error}",
        )
