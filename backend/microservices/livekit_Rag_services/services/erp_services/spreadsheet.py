"""
A school's records as spreadsheets - for a school with no ERP.

The super admin gives a live link for up to four tables (a Google
Sheet tab, or any online CSV / Excel file): students, attendance,
results and fees. Only students is needed; it is also what ties a
parent to their children - each row names a child and the guardian it
belongs to, and a parent's login carries that guardian id (set on the
Accounts page, as for ERPNext).

records_sync.py re-reads every link on a timer. Each copy is checked
here and the last good one is kept as plain UTF-8 CSV under the
school's own folder (data/schools/<id>/records/), so the voice worker
reads it without Excel support or network, and keeps answering when a
link is briefly down. Column names are forgiving ("Roll No", "roll_no"
and "student_id" are the same column); extra columns are kept and
read out like any other.
"""

import csv
import io
import json
import os
import re
import shutil
from datetime import date, datetime, timezone

MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 20000
MAX_COLUMNS = 40

TABLES = {
    "students": {
        "label": "Students",
        "required": ["student_id", "student_name", "guardian_id"],
        "optional": ["guardian_name", "guardian_email", "guardian_mobile", "class"],
        "aliases": {
            "roll_no": "student_id", "roll_number": "student_id",
            "admission_no": "student_id", "admission_number": "student_id",
            "name": "student_name",
            "parent_id": "guardian_id",
            "parent_name": "guardian_name", "father_name": "guardian_name",
            "parent_email": "guardian_email", "email": "guardian_email",
            "parent_mobile": "guardian_mobile", "mobile": "guardian_mobile", "phone": "guardian_mobile",
            "grade": "class", "class_name": "class",
        },
    },
    "attendance": {
        "label": "Attendance",
        "required": ["student_id", "date", "status"],
        "optional": [],
        "aliases": {"roll_no": "student_id", "roll_number": "student_id", "admission_no": "student_id"},
    },
    "results": {
        "label": "Results",
        "required": ["student_id", "subject", "marks"],
        "optional": ["total", "grade", "exam", "year"],
        "aliases": {
            "roll_no": "student_id", "roll_number": "student_id", "admission_no": "student_id",
            "course": "subject",
            "obtained": "marks", "obtained_marks": "marks", "score": "marks",
            "max_marks": "total", "total_marks": "total", "out_of": "total", "maximum": "total",
            "term": "exam", "assessment": "exam",
            "academic_year": "year",
        },
    },
    "fees": {
        "label": "Fees",
        "required": ["student_id", "amount"],
        "optional": ["description", "paid", "outstanding", "due_date", "status"],
        "aliases": {
            "roll_no": "student_id", "roll_number": "student_id", "admission_no": "student_id",
            "fee_type": "description", "month": "description", "title": "description",
            "total": "amount", "fee": "amount",
            "paid_amount": "paid",
            "balance": "outstanding", "due_amount": "outstanding", "remaining": "outstanding",
            "due": "due_date",
        },
    },
}


class SpreadsheetError(ValueError):
    """The sheet was not usable - shown to the super admin as the reason."""


# ---------------------------------------------------------
# Where a school's tables live
# ---------------------------------------------------------

def _csv_path(records_dir: str, table: str) -> str:
    return os.path.join(records_dir, f"{table}.csv")


def _meta_path(records_dir: str, table: str) -> str:
    return os.path.join(records_dir, f"{table}.json")


def has_table(records_dir: str, table: str) -> bool:
    return os.path.isfile(_csv_path(records_dir, table))


def read_meta(records_dir: str, table: str) -> dict | None:
    """A table's link and how its syncing went - None if it has none."""
    try:
        with open(_meta_path(records_dir, table), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def update_meta(records_dir: str, table: str, **fields) -> dict | None:
    meta = read_meta(records_dir, table)
    if meta is None:
        return None
    meta.update(fields)
    _write_meta(records_dir, table, meta)
    return meta


def _write_meta(records_dir: str, table: str, meta: dict) -> None:
    path = _meta_path(records_dir, table)
    temp = path + ".tmp"
    with open(temp, "w", encoding="utf-8") as f:
        json.dump(meta, f)
    os.replace(temp, path)


def status(records_dir: str) -> list[dict]:
    """Each table, what it needs, and its link (or None)."""
    return [
        {
            "table": table,
            "label": spec["label"],
            "required": spec["required"],
            "optional": spec["optional"],
            "needed": table == "students",
            "link": read_meta(records_dir, table) if has_table(records_dir, table) else None,
        }
        for table, spec in TABLES.items()
    ]


# ---------------------------------------------------------
# Reading a sheet
# ---------------------------------------------------------

def _column(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(name or "").strip().lower()).strip("_")


def _cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat() if value.time() == datetime.min.time() else value.isoformat(sep=" ")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return " ".join(str(value).split())


def _grid(filename: str, content: bytes) -> list[list[str]]:
    name = (filename or "").lower()
    if name.endswith(".csv"):
        for encoding in ("utf-8-sig", "cp1252"):
            try:
                text = content.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise SpreadsheetError("The CSV file could not be read - save it as UTF-8 CSV.")
        return [[_cell(v) for v in row] for row in csv.reader(io.StringIO(text))]
    if name.endswith(".xlsx"):
        from openpyxl import load_workbook

        try:
            book = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        except Exception:
            raise SpreadsheetError("The Excel file could not be opened - is it a real .xlsx file?")
        try:
            sheet = book.worksheets[0]
            return [[_cell(v) for v in row] for row in sheet.iter_rows(values_only=True)]
        finally:
            book.close()
    raise SpreadsheetError("Use a .csv or .xlsx sheet (old .xls files: save as .xlsx first).")


def parse(table: str, filename: str, content: bytes) -> tuple[list[str], list[dict], list[str]]:
    """The sheet as (columns, rows, warnings) - or SpreadsheetError."""
    if table not in TABLES:
        raise SpreadsheetError(f"Unknown table '{table}'.")
    if len(content) > MAX_BYTES:
        raise SpreadsheetError("The file is larger than 5 MB.")
    spec = TABLES[table]

    grid = [row for row in _grid(filename, content) if any(cell for cell in row)]
    if not grid:
        raise SpreadsheetError("The file is empty.")

    header = [spec["aliases"].get(_column(h), _column(h)) for h in grid[0]]
    while header and not header[-1]:
        header.pop()
    if not header or any(not h for h in header):
        raise SpreadsheetError("Every column in the first row needs a name.")
    if len(header) > MAX_COLUMNS:
        raise SpreadsheetError(f"At most {MAX_COLUMNS} columns.")
    repeated = sorted({h for h in header if header.count(h) > 1})
    if repeated:
        raise SpreadsheetError(f"These columns appear twice: {', '.join(repeated)}.")
    missing = [c for c in spec["required"] if c not in header]
    if missing:
        raise SpreadsheetError(
            f"Missing column(s): {', '.join(missing)}. The first row must name the columns - "
            f"needed: {', '.join(spec['required'])}."
        )
    if len(grid) - 1 > MAX_ROWS:
        raise SpreadsheetError(f"At most {MAX_ROWS} rows.")

    rows, skipped = [], []
    for number, raw in enumerate(grid[1:], start=2):
        row = {column: (raw[i] if i < len(raw) else "") for i, column in enumerate(header)}
        if any(not row[c] for c in spec["required"]):
            skipped.append(number)
            continue
        rows.append(row)

    warnings = []
    if skipped:
        shown = ", ".join(str(n) for n in skipped[:8]) + ("…" if len(skipped) > 8 else "")
        warnings.append(f"{len(skipped)} row(s) left out - a needed value is empty (row {shown}).")
    if not rows:
        raise SpreadsheetError("No usable rows - every row is missing a needed value.")

    for column in ("marks", "total", "amount", "paid", "outstanding"):
        if column in header:
            bad = sum(1 for r in rows if r.get(column) and _number(r[column]) is None)
            if bad:
                warnings.append(f"{bad} row(s) have a '{column}' that is not a number.")

    return header, rows, warnings


# ---------------------------------------------------------
# Storing and reading back
# ---------------------------------------------------------

def now() -> str:
    """UTC without a zone - how the server's other times are stored, and
    how the admin panel reads them (it shows them in the viewer's time)."""
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")


def save(records_dir: str, table: str, source_url: str, columns: list[str], rows: list[dict],
         warnings: list[str] | None = None, digest: str | None = None) -> dict:
    """A good copy of a table, read from its link: the CSV the agent
    reads, and the link with how it went."""
    os.makedirs(records_dir, exist_ok=True)
    path = _csv_path(records_dir, table)
    temp = path + ".tmp"
    with open(temp, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temp, path)
    stamp = now()
    meta = {
        "source_url": source_url,
        "rows": len(rows),
        "columns": columns,
        "warnings": warnings or [],
        "digest": digest,
        "synced_at": stamp,       # the copy in use is from then
        "last_attempt": stamp,    # the link was last tried then
        "last_error": None,       # why that last try failed, if it did
    }
    _write_meta(records_dir, table, meta)
    _cache.pop(path, None)
    return meta


def remove(records_dir: str, table: str) -> bool:
    found = False
    for path in (_csv_path(records_dir, table), _meta_path(records_dir, table)):
        try:
            os.remove(path)
            found = True
        except FileNotFoundError:
            pass
    _cache.pop(_csv_path(records_dir, table), None)
    return found


def remove_all(records_dir: str) -> None:
    """A school removed from the platform takes its records with it."""
    shutil.rmtree(records_dir, ignore_errors=True)
    try:
        # the school's own folder too, when nothing else (documents) is left in it
        os.rmdir(os.path.dirname(records_dir))
    except OSError:
        pass


# path -> (modified time, rows): re-read only when the file changed
_cache: dict[str, tuple[int, list[dict]]] = {}


def rows(records_dir: str, table: str) -> list[dict]:
    path = _csv_path(records_dir, table)
    try:
        changed = os.stat(path).st_mtime_ns
    except FileNotFoundError:
        return []
    cached = _cache.get(path)
    if cached and cached[0] == changed:
        return cached[1]
    with open(path, encoding="utf-8", newline="") as f:
        loaded = list(csv.DictReader(f))
    _cache[path] = (changed, loaded)
    return loaded


def same_id(a, b) -> bool:
    return str(a or "").strip().lower() == str(b or "").strip().lower() != ""


def _number(value):
    text = str(value or "").replace(",", "").strip()
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return int(number) if number.is_integer() else number


_STATUS = {
    "p": "Present", "present": "Present",
    "a": "Absent", "absent": "Absent",
    "l": "Leave", "leave": "Leave", "on leave": "Leave",
    "late": "Late",
}


def shaped(table: str, row: dict, student_name: str) -> dict:
    """
    A stored row in the shape the ERPNext rows have, so the same
    compaction (counts, percentages) and the same answer prompt apply.
    Extra columns pass through as they are.
    """
    out = {"student": row.get("student_id"), "student_name": student_name}
    extra = {k: v for k, v in row.items() if v not in (None, "")}
    if table == "attendance":
        raw = str(row.get("status") or "").strip()
        out.update(date=row.get("date"), status=_STATUS.get(raw.lower(), raw.title() or "Unknown"))
        used = {"student_id", "date", "status"}
    elif table == "results":
        out.update(
            course=row.get("subject"),
            assessment_group=row.get("exam") or None,
            total_score=_number(row.get("marks")),
            maximum_score=_number(row.get("total")),
            grade=row.get("grade") or None,
            academic_year=row.get("year") or None,
        )
        used = {"student_id", "subject", "exam", "marks", "total", "grade", "year"}
    elif table == "fees":
        amount = _number(row.get("amount"))
        paid = _number(row.get("paid"))
        outstanding = _number(row.get("outstanding"))
        if outstanding is None and amount is not None and paid is not None:
            outstanding = max(amount - paid, 0)
        state = row.get("status") or (
            None if outstanding is None else ("Paid" if outstanding == 0 else "Unpaid")
        )
        out.update(
            description=row.get("description") or None,
            grand_total=amount,
            paid_amount=paid,
            outstanding_amount=outstanding,
            due_date=row.get("due_date") or None,
            status=state,
        )
        used = {"student_id", "description", "amount", "paid", "outstanding", "due_date", "status"}
    else:  # students: the child's own profile, not the guardian's contact details
        used = {"student_id", "student_name", "guardian_id", "guardian_email", "guardian_mobile"}
    out.update({k: v for k, v in extra.items() if k not in used and k not in out})
    return {k: v for k, v in out.items() if v not in (None, "")}
