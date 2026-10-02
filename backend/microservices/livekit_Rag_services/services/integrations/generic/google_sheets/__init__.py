"""
Google Sheets / online CSV - a copied source.

A link per table (a Google Sheet tab, or any online CSV / Excel file), read
by the sheet syncing Vocira always had (erp_services/records_sync.py): the
last good copy kept on disk, a broken edit never replacing it. From there
each table is copied into the school's canonical records, which is what
the agent reads.
"""

from backend.microservices.livekit_Rag_services.services import tenants
from backend.microservices.livekit_Rag_services.services.erp_services import records_sync, spreadsheet
from backend.microservices.livekit_Rag_services.services.integrations import normalizer, store
from backend.microservices.livekit_Rag_services.services.integrations.base import Provider

SOURCE = "sheets"


async def import_table(school_id: str, table: str) -> int:
    """A table's sheet copy (on disk) into the school's canonical records."""
    folder = tenants.records_dir(school_id)
    rows = spreadsheet.rows(folder, table)
    if not rows:
        return 0
    columns = list(rows[0].keys())
    result = normalizer.normalize(table, columns, rows)
    return await store.replace_table(school_id, table, result.rows, SOURCE)


async def import_all(school_id: str) -> dict[str, int]:
    """Every linked table - for a school whose sheets were linked before the canonical records existed."""
    folder = tenants.records_dir(school_id)
    counts = {}
    for table in spreadsheet.SHEET_TABLES:
        if spreadsheet.has_table(folder, table):
            counts[table] = await import_table(school_id, table)
    return counts


async def sync(school, connection, force: bool = False) -> dict:
    """Re-read every link; copy each changed table (every table, when forced) into the canonical records."""
    folder = tenants.records_dir(school.id)
    mappings = connection.mapping if connection is not None else {}
    results = await records_sync.sync_school(school.id, folder, mappings)
    stored = await store.counts(school.id)
    counts, errors, warnings, changed = {}, {}, {}, False
    for result in results:
        table = result["table"]
        if result.get("skipped"):
            continue
        if not result["ok"]:
            errors[table] = result.get("error") or "could not be read"
            continue
        meta = spreadsheet.read_meta(folder, table) or {}
        if meta.get("warnings"):
            warnings[table] = meta["warnings"]
        if force or result.get("changed") or not stored.get(table):
            counts[table] = await import_table(school.id, table)
            changed = True
        else:
            counts[table] = stored.get(table, 0)
    if not any(not r.get("skipped") for r in results):
        errors["students"] = "No sheet is linked yet - link the Students tab first."
    return {"counts": counts, "errors": errors, "warnings": warnings, "changed": changed}


PROVIDER = Provider(
    kind="spreadsheet",
    label="Google Sheets / online CSV",
    description="A live link per table - a Google Sheet tab or an online CSV / Excel file - re-read every few minutes.",
    category="generic",
    mode="sync",
    setup="links",
    tables=spreadsheet.SHEET_TABLES,
    sync=sync,
    notes="Share each tab as 'Anyone with the link - Viewer'. A broken edit never replaces the last good copy.",
    extra={"sync_minutes": records_sync.SYNC_MINUTES},
)
