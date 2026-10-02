"""
Excel / CSV upload - a copied source, for any school whose software can
export a report (nearly all can), or that keeps its records in a sheet.

Each table is one file. The admin uploads it, checks the column mapping
and a preview, and imports it: the school's copy of that table is replaced
by the file's rows. A Native Records school imports the same way, to fill
its tables in one go.
"""

from backend.microservices.livekit_Rag_services.services.erp_services import spreadsheet
from backend.microservices.livekit_Rag_services.services.integrations import canonical, normalizer, store
from backend.microservices.livekit_Rag_services.services.integrations.base import Provider, SourceError

MAX_BYTES = spreadsheet.MAX_BYTES


def _grid(filename: str, content: bytes) -> list[list]:
    if len(content) > MAX_BYTES:
        raise SourceError("The file is larger than 5 MB.")
    try:
        grid = spreadsheet._grid(filename, content)
    except spreadsheet.SpreadsheetError as error:
        raise SourceError(str(error))
    grid = [row for row in grid if any(str(cell or "").strip() for cell in row)]
    if not grid:
        raise SourceError("The file is empty.")
    return grid


def preview(table: str, filename: str, content: bytes, mapping: dict | None = None) -> dict:
    """What an import would do: the file's columns, the mapping, the first rows - nothing is saved."""
    grid = _grid(filename, content)
    columns = [normalizer.text(c) for c in grid[0]]
    out = {
        "table": table,
        "columns": columns,
        "suggested": normalizer.suggest_mapping(table, columns),
        "rows_in_file": len(grid) - 1,
    }
    try:
        result = normalizer.normalize(table, columns, grid[1:], mapping)
    except normalizer.NormalizeError as error:
        return {**out, "ok": False, "error": str(error), "preview": [], "warnings": []}
    return {
        **out,
        "ok": True,
        "mapping": result.mapping,
        "extras": result.extras,
        "rows": len(result.rows),
        "skipped": result.skipped,
        "warnings": result.warnings,
        "preview": result.rows[:10],
    }


async def import_file(school_id: str, table: str, filename: str, content: bytes, mapping: dict | None,
                      source: str = "excel") -> dict:
    """The file's rows become the school's copy of this table."""
    if table not in canonical.TABLES:
        raise SourceError(f"Unknown table '{table}'.")
    grid = _grid(filename, content)
    try:
        result = normalizer.normalize(table, [normalizer.text(c) for c in grid[0]], grid[1:], mapping)
    except normalizer.NormalizeError as error:
        raise SourceError(str(error))
    rows = await store.replace_table(school_id, table, result.rows, source)
    return {"table": table, "rows": rows, "skipped": result.skipped, "warnings": result.warnings,
            "mapping": result.mapping}


PROVIDER = Provider(
    kind="excel",
    label="Excel / CSV upload",
    description="Upload each table as an .xlsx or .csv file - exported from the school's software, or typed in a sheet.",
    category="generic",
    mode="sync",
    setup="upload",
    tables=tuple(canonical.TABLE_ORDER),
    notes="Upload a fresh file whenever the data changes - results each term, fees each month.",
)
