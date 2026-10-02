"""
The records-system connection of each school, as set on the Schools page.

A connection is the system's kind (see connectors.py), its settings (the
URL, a username - nothing secret), its secrets (keys, passwords),
which data Vocira may read, and whether the system may sit on the
school's own network. Secrets are encrypted with RECORDS_SECRETS_KEY
(.env) before they reach the database and are never sent back to the
panel - it is only told whether each one is set.

The API and the voice worker are separate processes, so both keep a
copy in memory and re-read it with the schools (tenants.refresh).
Every change - connected, changed, tested, disconnected - is written
to the audit log with who did it.
"""

import json
import os
from dataclasses import dataclass, field

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select

from backend.helper_functions.database.session import SessionLocal
from backend.microservices.livekit_Rag_services.models.school_connection_model import (
    ConnectionAudit,
    SchoolConnection,
)


class ConnectionSettingsError(ValueError):
    """The connection settings were not usable - shown to the super admin."""


def _box() -> Fernet:
    key = os.getenv("RECORDS_SECRETS_KEY", "").strip()
    if not key:
        raise ConnectionSettingsError("RECORDS_SECRETS_KEY is not set on the server - connections cannot be saved.")
    return Fernet(key.encode())


def _encrypt(secrets: dict) -> str:
    return _box().encrypt(json.dumps(secrets).encode()).decode()


def _decrypt(token: str | None) -> dict:
    if not token:
        return {}
    try:
        return json.loads(_box().decrypt(token.encode()).decode())
    except (InvalidToken, ValueError):
        # a changed key: the connection has to be entered again
        print("[Connections] could not decrypt a saved connection - was RECORDS_SECRETS_KEY changed?")
        return {}


@dataclass(frozen=True)
class Connection:
    school_id: str
    kind: str
    settings: dict = field(default_factory=dict)
    secrets: dict = field(default_factory=dict)
    capabilities: tuple = ()
    allow_private_network: bool = False
    version: str = ""          # changes whenever the connection does - connectors are rebuilt
    # the Integration Hub's: {table: {canonical field: source column}}, and how often to re-read
    mapping: dict = field(default_factory=dict)
    sync_minutes: int | None = None
    status: str | None = None


_store: dict[str, Connection] = {}


def _from_row(row: SchoolConnection) -> Connection:
    return Connection(
        school_id=row.school_id,
        kind=row.kind,
        settings=json.loads(row.settings_json or "{}"),
        secrets=_decrypt(row.secrets_enc),
        capabilities=tuple(json.loads(row.capabilities_json or "[]")),
        allow_private_network=bool(row.allow_private_network),
        version=str(row.updated_at),
        mapping=json.loads(row.mapping_json or "{}"),
        sync_minutes=row.sync_minutes,
        status=row.status,
    )


async def refresh() -> None:
    async with SessionLocal() as db:
        rows = (await db.execute(select(SchoolConnection))).scalars().all()
    _store.clear()
    _store.update({row.school_id: _from_row(row) for row in rows})


def get(school_id: str) -> Connection | None:
    return _store.get(school_id)


async def _audit(db, school_id: str, action: str, kind: str | None, actor: str | None, detail: str | None = None):
    db.add(ConnectionAudit(school_id=school_id, action=action, kind=kind, actor=actor, detail=detail))


_KEEP = object()


async def save(school_id: str, kind: str, settings: dict, secrets: dict, capabilities: list[str],
               allow_private_network: bool, actor: str | None, mapping=_KEEP, sync_minutes=_KEEP) -> Connection:
    """
    Connect or change. A secret left empty keeps the one already saved
    (the panel never has it to send back); switching to another kind of
    system starts from no secrets at all.
    """
    async with SessionLocal() as db:
        row = await db.get(SchoolConnection, school_id)
        kept = _decrypt(row.secrets_enc) if row and row.kind == kind else {}
        merged = {**kept, **{k: v for k, v in secrets.items() if v}}
        action = "connected" if row is None or row.kind != kind else "changed"
        if row is None:
            row = SchoolConnection(school_id=school_id)
            db.add(row)
        row.kind = kind
        row.settings_json = json.dumps(settings)
        row.secrets_enc = _encrypt(merged) if merged else None
        row.capabilities_json = json.dumps(list(capabilities))
        row.allow_private_network = bool(allow_private_network)
        row.updated_by = actor
        if mapping is not _KEEP:
            row.mapping_json = json.dumps(mapping or {})
        elif action == "connected":
            row.mapping_json = None  # another system's columns mean nothing to this one
        if sync_minutes is not _KEEP:
            row.sync_minutes = sync_minutes
        if action == "connected":
            row.status = "connected"
            row.last_sync_at = row.last_sync_ok = row.last_sync_summary = row.record_counts_json = None
            # the usual order is Test, then Save: the test made before this
            # connection existed is its last test
            tested = (await db.execute(
                select(ConnectionAudit)
                .where(ConnectionAudit.school_id == school_id, ConnectionAudit.kind == kind, ConnectionAudit.action == "tested")
                .order_by(ConnectionAudit.id.desc()).limit(1)
            )).scalar_one_or_none()
            if tested is not None:
                row.last_test_at = tested.at
                row.last_test_ok = (tested.detail or "").startswith("ok: ")
                row.last_test_summary = (tested.detail or "").split(": ", 1)[-1]
        await _audit(db, school_id, action, kind, actor,
                     f"settings: {', '.join(sorted(settings))}; secrets set: {', '.join(sorted(merged)) or 'none'}; "
                     f"reads: {', '.join(capabilities) or 'nothing'}")
        await db.commit()
    await refresh()
    return get(school_id)


async def delete(school_id: str, actor: str | None) -> bool:
    """Disconnect: the connection and its secrets are gone from the database."""
    async with SessionLocal() as db:
        row = await db.get(SchoolConnection, school_id)
        if row is None:
            return False
        kind = row.kind
        await db.delete(row)
        await _audit(db, school_id, "disconnected", kind, actor, "settings and secrets deleted")
        await db.commit()
    await refresh()
    return True


async def ensure(school_id: str, kind: str, actor: str | None, capabilities: list[str] | None = None) -> Connection:
    """A connection row for a source with nothing secret (Excel/CSV, Google Sheets, Native Records),
    so its sync state, mapping and history have a home like every other's."""
    from backend.microservices.livekit_Rag_services.services.integrations.base import ALL_CAPABILITIES

    found = get(school_id)
    if found is not None and found.kind == kind:
        return found
    return await save(school_id, kind, {}, {}, list(capabilities or ALL_CAPABILITIES), False, actor)


async def set_mapping(school_id: str, table: str, mapping: dict, actor: str | None) -> None:
    """One table's column mapping, as chosen on the mapping step."""
    async with SessionLocal() as db:
        row = await db.get(SchoolConnection, school_id)
        if row is None:
            return
        current = json.loads(row.mapping_json or "{}")
        current[table] = {k: v for k, v in (mapping or {}).items() if v}
        row.mapping_json = json.dumps(current)
        await _audit(db, school_id, "mapped", row.kind, actor, f"{table}: {', '.join(sorted(current[table])) or 'automatic'}")
        await db.commit()
    await refresh()


# how a sync's outcome leaves the connection's status
_STATUS_AFTER_SYNC = {"success": "connected", "partial": "attention", "failed": "error"}


async def record_sync(school_id: str, kind: str, state: str, summary: str, counts: dict | None) -> None:
    """How the last sync went - success, partial (needs attention) or failed - shown on both panels."""
    from datetime import datetime, timezone

    async with SessionLocal() as db:
        row = await db.get(SchoolConnection, school_id)
        if row is None or row.kind != kind:
            return
        row.last_sync_at = datetime.now(timezone.utc).replace(tzinfo=None)
        row.last_sync_ok = state == "success"
        row.last_sync_state = state
        row.last_sync_summary = (summary or "")[:2000]
        if counts is not None:
            row.record_counts_json = json.dumps(counts)
        row.status = _STATUS_AFTER_SYNC.get(state, "error")
        await db.commit()


async def record_test(school_id: str, kind: str, ok: bool, summary: str, actor: str | None) -> None:
    from datetime import datetime, timezone

    async with SessionLocal() as db:
        row = await db.get(SchoolConnection, school_id)
        if row is not None and row.kind == kind:
            row.last_test_at = datetime.now(timezone.utc).replace(tzinfo=None)
            row.last_test_ok = ok
            row.last_test_summary = summary[:2000]
            row.status = "connected" if ok else "error"
        await _audit(db, school_id, "tested", kind, actor, ("ok: " if ok else "failed: ") + summary[:500])
        await db.commit()


# what the first school's ERPNext may read (connectors.KINDS["erpnext"])
_SERVER_ERP_READS = ["profile", "attendance", "results", "fees", "marks", "timetable"]


async def adopt_server_erp() -> bool:
    """
    Once: the first school's ERPNext keys in the server settings (.env
    ERP_*) become its encrypted connection, so it is managed on the
    Schools page like every other school. Never again once it has a
    connection, or after it was disconnected on purpose.
    """
    from sqlalchemy import update

    from backend.microservices.livekit_Rag_services.core.config import settings
    from backend.microservices.livekit_Rag_services.models.school_model import SchoolRecord
    from backend.microservices.livekit_Rag_services.services.tenants import DEFAULT_SCHOOL_ID

    base, key, secret = (getattr(settings, name, None) for name in ("ERP_BASE_URL", "ERP_API_KEY", "ERP_API_SECRET"))
    if not (base and key and secret):
        return False
    async with SessionLocal() as db:
        if await db.get(SchoolConnection, DEFAULT_SCHOOL_ID) is not None:
            return False
        disconnected = (await db.execute(
            select(ConnectionAudit.id).where(ConnectionAudit.school_id == DEFAULT_SCHOOL_ID,
                                             ConnectionAudit.action == "disconnected").limit(1)
        )).first()
        if disconnected:
            return False
        # a row of changes to the first school keeps its ERPNext
        await db.execute(update(SchoolRecord).where(SchoolRecord.id == DEFAULT_SCHOOL_ID, SchoolRecord.records.is_(None))
                         .values(records="erpnext"))
        await db.commit()
    # the service's own ERP may well be on this machine or the school's network
    await save(DEFAULT_SCHOOL_ID, "erpnext", {"base_url": base}, {"api_key": key, "api_secret": secret},
               _SERVER_ERP_READS, True, "system (moved from the server settings)")
    print(f"[Connections] {DEFAULT_SCHOOL_ID}: ERPNext keys moved from the server settings into its connection")
    return True


async def view(school_id: str) -> dict | None:
    """What the panel may see: no secret, only whether each is set."""
    async with SessionLocal() as db:
        row = await db.get(SchoolConnection, school_id)
        if row is None:
            return None
        audit = (await db.execute(
            select(ConnectionAudit).where(ConnectionAudit.school_id == school_id)
            .order_by(ConnectionAudit.id.desc()).limit(8)
        )).scalars().all()
    return {
        "kind": row.kind,
        "settings": json.loads(row.settings_json or "{}"),
        "secrets_set": sorted(_decrypt(row.secrets_enc)),
        "capabilities": json.loads(row.capabilities_json or "[]"),
        "allow_private_network": bool(row.allow_private_network),
        "last_test": None if row.last_test_at is None else {
            "at": row.last_test_at.isoformat(timespec="seconds"),
            "ok": row.last_test_ok,
            "summary": row.last_test_summary,
        },
        "updated_by": row.updated_by,
        "updated_at": row.updated_at.isoformat(timespec="seconds") if row.updated_at else None,
        "status": row.status,
        "mapping": json.loads(row.mapping_json or "{}"),
        "sync_minutes": row.sync_minutes,
        "last_sync": None if row.last_sync_at is None else {
            "at": row.last_sync_at.isoformat(timespec="seconds"),
            "ok": row.last_sync_ok,
            "state": row.last_sync_state or ("success" if row.last_sync_ok else "failed"),
            "summary": row.last_sync_summary,
        },
        "counts": json.loads(row.record_counts_json or "{}"),
        "audit": [
            {"action": a.action, "kind": a.kind, "actor": a.actor, "detail": a.detail,
             "at": a.at.isoformat(timespec="seconds") if a.at else None}
            for a in audit
        ],
    }
