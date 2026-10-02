"""
The sync engine - keeping each school's canonical records current, and
saying how it went.

    run(school_id, trigger)    one sync now - initial, manual, upload or scheduled
    start(school_id, trigger)  the same in the background; returns the run's id at once
    scheduled_round()          every copied source that is due (records_sync's timer calls it)
    history(school_id)         the school's recent runs
    overview()                 every school at a glance, for the super admin

What a sync does depends on the provider:
    copied (Google Sheets, REST API, database)  read it, map it, replace the copy
    live (ERPNext, Open School MIS)             nothing to copy: the connection is tested
    Excel/CSV and Native Records                nothing to pull: the tables are counted

A passing failure (a timeout, a dropped connection) is tried again, twice,
after a pause. Every run is written to integration_sync_runs - except a
scheduled one that changed nothing - and its error is scrubbed of
credentials first (security.scrub).
"""

import asyncio
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from backend.helper_functions.database.session import SessionLocal
from backend.microservices.livekit_Rag_services.models.canonical_records_model import IntegrationSyncRun
from backend.microservices.livekit_Rag_services.services import tenants
from backend.microservices.livekit_Rag_services.services.erp_services import connections, records_sync, spreadsheet
from backend.microservices.livekit_Rag_services.services.integrations import registry, security, store
from backend.microservices.livekit_Rag_services.services.integrations.base import SourceError

MAX_ATTEMPTS = 3
BACKOFF_SECONDS = (5, 20)
DEFAULT_MINUTES = {"spreadsheet": records_sync.SYNC_MINUTES, "rest-api": 60, "database": 60}

_locks: dict[str, asyncio.Lock] = {}
_tasks: set[asyncio.Task] = set()


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Busy(Exception):
    """A sync of this school is already running."""


async def _school(school_id: str):
    await tenants.refresh(force=not tenants.is_known(school_id))
    if not tenants.is_known(school_id):
        raise LookupError(school_id)
    return tenants.get_school(school_id)


def _connection_for(school):
    found = connections.get(school.id)
    return found if found is not None and found.kind == school.records else None


async def _new_run(school_id: str, kind: str, trigger: str, actor: str | None) -> int:
    async with SessionLocal() as db:
        run = IntegrationSyncRun(school_id=school_id, kind=kind or "none", trigger=trigger, status="running", actor=actor)
        db.add(run)
        await db.commit()
        await db.refresh(run)
        return run.id


async def _finish_run(run_id: int | None, school_id: str, kind: str, trigger: str, actor: str | None, outcome: dict) -> int:
    async with SessionLocal() as db:
        run = await db.get(IntegrationSyncRun, run_id) if run_id else None
        if run is None:
            run = IntegrationSyncRun(school_id=school_id, kind=kind or "none", trigger=trigger, actor=actor)
            db.add(run)
        run.status = outcome["status"]
        run.attempts = outcome["attempts"]
        run.counts_json = json.dumps(outcome["counts"])
        run.summary = outcome["summary"][:2000]
        run.error = outcome["error"]
        run.finished_at = _now()
        await db.commit()
        await db.refresh(run)
        return run.id


async def record_run(school_id: str, kind: str, trigger: str, actor: str | None, outcome: dict) -> int:
    """A run that happened outside the engine - an upload - written to the history like the others."""
    return await _finish_run(None, school_id, kind, trigger, actor, outcome)


async def _execute(school, trigger: str) -> dict:
    """The sync itself: (status, counts, summary, error, attempts, changed)."""
    provider = registry.get(school.records)
    connection = _connection_for(school)
    secrets = connection.secrets if connection else {}
    attempts, result, error = 0, {}, None

    try:
        if provider is None:
            raise SourceError("This school has no records system - it answers general questions only.")
        if provider.mode == "unavailable":
            raise SourceError(f"{provider.label} needs its official integration first. {provider.notes}")
        if provider.mode == "live":
            if connection is None:
                raise SourceError(f"{provider.label} is not connected yet.")
            attempts = 1
            tested = await provider.test(connection.settings, connection.secrets, connection.allow_private_network)
            failed = [s for s in tested.get("steps", []) if not s["ok"]]
            result = {"counts": tested.get("counts") or {}, "changed": False,
                      "errors": {s["name"]: s["detail"] for s in failed}}
            if not tested.get("ok"):
                raise SourceError("; ".join(f"{s['name']}: {s['detail']}" for s in failed) or "The connection test failed.")
        elif provider.sync is not None:
            if provider.setup in ("rest", "database") and connection is None:
                raise SourceError(f"{provider.label} is not set up yet.")
            for attempts in range(1, MAX_ATTEMPTS + 1):
                try:
                    result = await provider.sync(school, connection, force=trigger in ("manual", "initial"))
                    break
                except SourceError as failure:
                    if failure.transient and attempts < MAX_ATTEMPTS:
                        print(f"[Sync] {school.id}: attempt {attempts} failed ({security.scrub(failure, secrets)}) - trying again")
                        await asyncio.sleep(BACKOFF_SECONDS[attempts - 1])
                        continue
                    raise
        else:
            attempts = 1
            result = {"counts": await store.counts(school.id), "changed": False}
    except Exception as failure:  # an adapter's surprise is still an outcome to show
        error = security.scrub(failure if isinstance(failure, SourceError) else f"{type(failure).__name__}: {failure}",
                               secrets)

    counts = result.get("counts") or {}
    if provider is not None and provider.mode in ("sync", "native"):
        counts = {k: v for k, v in (await store.counts(school.id)).items() if v}
    table_errors = {t: security.scrub(e, secrets) for t, e in (result.get("errors") or {}).items()}
    status = "failed" if error else ("partial" if table_errors else "success")
    if error:
        summary = error
    else:
        parts = [f"{t}: {n}" for t, n in counts.items()]
        if table_errors:
            parts += [f"{t} failed - {e}" for t, e in table_errors.items()]
        summary = "; ".join(parts) or "Nothing to read yet."
    return {"status": status, "counts": counts, "summary": summary, "error": error or (
        "; ".join(f"{t}: {e}" for t, e in table_errors.items()) if table_errors else None),
        "attempts": max(attempts, 1), "changed": bool(result.get("changed")), "warnings": result.get("warnings") or {}}


async def run(school_id: str, trigger: str = "manual", actor: str | None = None, run_id: int | None = None) -> dict:
    """One sync of a school, now. Raises Busy if one is already running, LookupError for an unknown school."""
    school = await _school(school_id)
    lock = _locks.setdefault(school.id, asyncio.Lock())
    if lock.locked():
        raise Busy(school.id)
    async with lock:
        if run_id is None and trigger != "scheduled":
            run_id = await _new_run(school.id, school.records, trigger, actor)
        outcome = await _execute(school, trigger)
        # A scheduled sync is written to the history only when it changed something,
        # or hit a problem that is not already the last one written - the same
        # "nothing linked yet" every few minutes would bury every other run.
        record = trigger != "scheduled" or outcome["changed"] or (
            outcome["status"] != "success" and outcome["error"] != await _last_written_problem(school.id))
        if record:
            run_id = await _finish_run(run_id, school.id, school.records, trigger, actor, outcome)
        provider = registry.get(school.records)
        if provider is not None and provider.mode != "unavailable":
            if provider.mode != "live" and _connection_for(school) is None:
                await connections.ensure(school.id, school.records, actor or "system")
            await connections.record_sync(school.id, school.records, outcome["status"],
                                          outcome["summary"], outcome["counts"])
        print(f"[Sync] {school.id} ({school.records}, {trigger}): {outcome['status']} - {outcome['summary'][:160]}")
        return {"run_id": run_id if record else None, **{k: v for k, v in outcome.items() if k != "changed"}}


async def _last_written_problem(school_id: str) -> str | None:
    """The problem of the school's latest written run - None when that run went fine."""
    async with SessionLocal() as db:
        last = (await db.execute(
            select(IntegrationSyncRun).where(IntegrationSyncRun.school_id == school_id,
                                             IntegrationSyncRun.status != "running")
            .order_by(IntegrationSyncRun.id.desc()).limit(1)
        )).scalar()
    return last.error if last is not None and last.status in ("failed", "partial") else None


async def start(school_id: str, trigger: str = "manual", actor: str | None = None) -> int:
    """A sync in the background - the run's id comes back at once, its outcome in history()."""
    school = await _school(school_id)
    if _locks.setdefault(school.id, asyncio.Lock()).locked():
        raise Busy(school.id)
    run_id = await _new_run(school.id, school.records, trigger, actor)

    async def work():
        try:
            await run(school.id, trigger, actor, run_id=run_id)
        except Busy:
            await _finish_run(run_id, school.id, school.records, trigger, actor, {
                "status": "failed", "attempts": 0, "counts": {}, "summary": "Another sync was already running.",
                "error": "Another sync was already running."})
        except Exception as error:
            print(f"[Sync] {school.id}: background sync failed: {type(error).__name__}: {error}")

    task = asyncio.create_task(work())
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return run_id


async def scheduled_round() -> None:
    """Every copied source that is due: Google Sheets every few minutes, a REST API or database by its schedule."""
    await tenants.refresh(force=True)
    for school_id in list(tenants.all_schools()):
        school = tenants.get_school(school_id)
        provider = registry.get(school.records)
        if provider is None or provider.mode != "sync" or provider.sync is None:
            continue
        connection = _connection_for(school)
        if provider.setup in ("rest", "database") and connection is None:
            continue
        if provider.setup == "links" and not any(
                t["link"] for t in spreadsheet.status(tenants.records_dir(school.id))):
            continue  # no sheet linked yet: nothing to read until one is
        minutes = (connection.sync_minutes if connection and connection.sync_minutes else None) \
            or DEFAULT_MINUTES.get(school.records, 60)
        view = await connections.view(school.id) if connection else None
        last = (view or {}).get("last_sync") or {}
        if last.get("at"):
            due = datetime.fromisoformat(last["at"]) + timedelta(minutes=minutes) - timedelta(seconds=30)
            if _now() < due:
                continue
        try:
            await run(school.id, "scheduled", "schedule")
        except Busy:
            continue
        except Exception as error:  # one school's trouble never stops the others
            print(f"[Sync] {school.id}: scheduled sync failed: {type(error).__name__}: {error}")


def _run_view(r: IntegrationSyncRun) -> dict:
    return {
        "id": r.id, "kind": r.kind, "trigger": r.trigger, "status": r.status, "attempts": r.attempts,
        "counts": json.loads(r.counts_json or "{}"), "summary": r.summary, "error": r.error, "actor": r.actor,
        "started_at": r.started_at.isoformat(timespec="seconds") if r.started_at else None,
        "finished_at": r.finished_at.isoformat(timespec="seconds") if r.finished_at else None,
    }


async def history(school_id: str, limit: int = 20) -> list[dict]:
    async with SessionLocal() as db:
        rows = (await db.execute(
            select(IntegrationSyncRun).where(IntegrationSyncRun.school_id == school_id)
            .order_by(IntegrationSyncRun.id.desc()).limit(limit)
        )).scalars().all()
    return [_run_view(r) for r in rows]


async def last_error(school_id: str) -> dict | None:
    async with SessionLocal() as db:
        r = (await db.execute(
            select(IntegrationSyncRun).where(IntegrationSyncRun.school_id == school_id,
                                             IntegrationSyncRun.status.in_(("failed", "partial")))
            .order_by(IntegrationSyncRun.id.desc()).limit(1)
        )).scalar()
    return _run_view(r) if r else None


async def forget(school_id: str) -> None:
    """A removed school's sync history goes with it."""
    from sqlalchemy import delete

    async with SessionLocal() as db:
        await db.execute(delete(IntegrationSyncRun).where(IntegrationSyncRun.school_id == school_id))
        await db.commit()


def is_running(school_id: str) -> bool:
    lock = _locks.get(school_id)
    return bool(lock and lock.locked())


async def school_status(school) -> dict:
    """One school's records integration at a glance - the panels' status card."""
    provider = registry.get(school.records)
    connection = _connection_for(school)
    view = await connections.view(school.id) if connection else None
    counts = (view or {}).get("counts") or {}
    if provider is not None and provider.mode in ("sync", "native"):
        counts = {k: v for k, v in (await store.counts(school.id)).items() if v}
    return {
        "school": school.id,
        "kind": school.records,
        "provider": provider.public() if provider else None,
        "connected": provider is not None and provider.mode != "unavailable"
                     and (provider.mode != "live" or connection is not None),
        "status": (view or {}).get("status") or ("connected" if provider and provider.mode in ("native",) else None),
        "last_sync": (view or {}).get("last_sync"),
        "last_test": (view or {}).get("last_test"),
        "sync_minutes": ((view or {}).get("sync_minutes") or DEFAULT_MINUTES.get(school.records))
                        if provider and provider.mode == "sync" and provider.sync else None,
        "counts": counts,
        "running": is_running(school.id),
        "last_error": await last_error(school.id),
    }


async def overview() -> list[dict]:
    """Every school's records integration - the super admin's Integrations page."""
    await tenants.refresh(force=True)
    out = []
    for school_id in tenants.all_schools():
        school = tenants.get_school(school_id)
        out.append({"name": school.name, "subdomain": tenants.address_of(school), **await school_status(school)})
    return out
