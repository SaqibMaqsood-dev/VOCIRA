"""
The data normalizer - any source's columns and values into Vocira's
canonical fields (canonical.py).

Every copied source passes through here: an Excel/CSV upload, a Google
Sheet, a REST API's JSON, a database query's rows, and a Native Records
form. So a school's "Adm No", "GR #" or "roll_number" all end up as
student_id, "P"/"A" as Present/Absent, and "1,500" as 1500.

Which source column fills which field, in this order:
    1. the school's own mapping, set on the mapping step
    2. a column with the field's own name (required fields first)
    3. a known alias of it - "Roll No" for student_id
Columns left over are kept as extras and read out like any other.
"""

import re
from dataclasses import dataclass, field
from datetime import date, datetime

from backend.microservices.livekit_Rag_services.services.integrations import canonical

MAX_ROWS = 20000
MAX_COLUMNS = 60


class NormalizeError(ValueError):
    """The data could not be used - the reason is shown to the admin as it is."""


@dataclass
class Normalized:
    rows: list[dict]                       # canonical fields, plus "_extra" for leftover columns
    mapping: dict[str, str]                # canonical field -> the source column it came from
    extras: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    skipped: int = 0


def column_key(name) -> str:
    """'Adm. No #' -> 'adm_no' - how columns are compared."""
    return re.sub(r"[^a-z0-9]+", "_", str(name or "").strip().lower()).strip("_")


# ---------------------------------------------------------
# Which column is which field
# ---------------------------------------------------------

def _assign(table: str, columns: list[str], mapping: dict | None) -> tuple[dict[str, int], list[str]]:
    t = canonical.spec(table)
    names = canonical.field_names(table)
    required = [f["name"] for f in t["fields"] if f["required"]]
    optional = [n for n in names if n not in required]
    keys = [column_key(c) for c in columns]
    assigned: dict[str, int] = {}
    problems: list[str] = []

    def free(i):
        return i not in assigned.values()

    # 1. the school's own mapping
    for field_name, source in (mapping or {}).items():
        if field_name not in names or not source:
            continue
        key = column_key(source)
        if key not in keys:
            problems.append(f"The column '{source}' chosen for {field_name} is not in the data.")
            continue
        i = keys.index(key)
        if free(i):
            assigned[field_name] = i

    def by_name(fields):
        for f in fields:
            if f not in assigned and f in keys and free(keys.index(f)):
                assigned[f] = keys.index(f)

    def by_alias(fields):
        for i, key in enumerate(keys):
            target = t["aliases"].get(key)
            if target in fields and target not in assigned and free(i):
                assigned[target] = i

    # 2-3 required fields first, so "Roll No" can be the student id when there is no other
    by_name(required)
    by_alias(required)
    by_name(optional)
    by_alias(optional)
    return assigned, problems


def suggest_mapping(table: str, columns: list[str]) -> dict[str, str | None]:
    """For the mapping step: the column each field would come from (None: none found)."""
    assigned, _ = _assign(table, columns, None)
    return {name: (columns[assigned[name]] if name in assigned else None) for name in canonical.field_names(table)}


# ---------------------------------------------------------
# Values
# ---------------------------------------------------------

def text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat() if value.time() == datetime.min.time() else value.isoformat(sep=" ")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return " ".join(str(value).split())


def number(value):
    """'1,500' -> 1500, '85.5' -> 85.5; None when it is not a number."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value) if float(value).is_integer() else float(value)
    cleaned = re.sub(r"(?i)^(rs\.?|pkr)\s*", "", text(value).replace(",", "")).strip()
    if not cleaned:
        return None
    try:
        n = float(cleaned)
    except ValueError:
        return None
    return int(n) if n.is_integer() else n


STATUS = {
    "p": "Present", "present": "Present", "yes": "Present", "y": "Present", "1": "Present",
    "a": "Absent", "absent": "Absent", "no": "Absent", "n": "Absent", "0": "Absent",
    "l": "Leave", "leave": "Leave", "on leave": "Leave", "on_leave": "Leave",
    "late": "Late", "lt": "Late",
    "h": "Holiday", "holiday": "Holiday",
}


def attendance_status(value) -> str:
    raw = text(value)
    return STATUS.get(raw.lower(), raw.title() or "Unknown")


_DAYS = {
    "mon": "Monday", "monday": "Monday", "pir": "Monday", "peer": "Monday",
    "tue": "Tuesday", "tues": "Tuesday", "tuesday": "Tuesday", "mangal": "Tuesday",
    "wed": "Wednesday", "wednesday": "Wednesday", "budh": "Wednesday",
    "thu": "Thursday", "thur": "Thursday", "thurs": "Thursday", "thursday": "Thursday", "jumerat": "Thursday",
    "fri": "Friday", "friday": "Friday", "juma": "Friday", "jumma": "Friday",
    "sat": "Saturday", "saturday": "Saturday", "hafta": "Saturday",
    "sun": "Sunday", "sunday": "Sunday", "itwar": "Sunday",
}


def day_name(value) -> str:
    raw = text(value)
    return _DAYS.get(raw.lower().rstrip("."), raw.title())


_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y", "%d-%b-%Y", "%d %b %Y",
                 "%d %B %Y", "%b %d, %Y", "%B %d, %Y", "%Y/%m/%d")


def iso_date(value) -> str:
    """A date as 2026-10-02. Day-first for slashes - how Pakistani records write them.
    Text that is no date stays as it is."""
    if isinstance(value, (datetime, date)):
        return text(value)[:10]
    raw = text(value)
    if not raw:
        return ""
    candidate = raw.split(" ")[0] if re.match(r"^\d{4}-\d{2}-\d{2}[ T]", raw) else raw
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(candidate, fmt).date().isoformat()
        except ValueError:
            continue
    return raw


def coerce(field_type: str, value):
    if field_type == "number":
        return number(value)
    if field_type == "date":
        return iso_date(value) or None
    if field_type == "status":
        return attendance_status(value) if text(value) else None
    if field_type == "day":
        return day_name(value) or None
    if field_type == "email":
        return text(value).lower() or None
    return text(value) or None


# ---------------------------------------------------------
# A whole table
# ---------------------------------------------------------

def normalize(table: str, columns: list[str], raw_rows: list, mapping: dict | None = None) -> Normalized:
    """
    A table's rows into canonical rows. raw_rows are dicts keyed by the
    source's column names, or lists in the order of `columns`.
    """
    t = canonical.spec(table)
    columns = [text(c) for c in columns]
    while columns and not columns[-1]:
        columns.pop()
    if not columns:
        raise NormalizeError("The data has no columns - the first row must name them.")
    if any(not c for c in columns):
        raise NormalizeError("Every column in the first row needs a name.")
    if len(columns) > MAX_COLUMNS:
        raise NormalizeError(f"At most {MAX_COLUMNS} columns.")
    keys = [column_key(c) for c in columns]
    repeated = sorted({columns[i] for i, k in enumerate(keys) if keys.count(k) > 1})
    if repeated:
        raise NormalizeError(f"These columns appear twice: {', '.join(repeated)}.")
    if len(raw_rows) > MAX_ROWS:
        raise NormalizeError(f"At most {MAX_ROWS} rows.")

    assigned, problems = _assign(table, columns, mapping)
    if problems:
        raise NormalizeError(" ".join(problems))
    labels = {f["name"]: f["label"] for f in t["fields"]}
    missing = [n for n in canonical.required_fields(table) if n not in assigned]
    if missing:
        raise NormalizeError(
            f"Missing column(s) for: {', '.join(labels[n] for n in missing)}. "
            f"Choose them on the mapping step, or name the columns {', '.join(missing)}."
        )

    types = {f["name"]: f["type"] for f in t["fields"]}
    used = set(assigned.values())
    extra_index = {i: keys[i] for i in range(len(columns)) if i not in used}
    required = canonical.required_fields(table)
    rows, skipped_rows, not_numbers = [], [], {}

    for number_in_file, raw in enumerate(raw_rows, start=2):
        if isinstance(raw, dict):
            by_key = {column_key(k): v for k, v in raw.items()}
            cells = [by_key.get(k) for k in keys]
        else:
            cells = list(raw) + [None] * (len(columns) - len(raw))
        if not any(text(c) for c in cells):
            continue  # an empty line
        row = {}
        for name, i in assigned.items():
            value = coerce(types[name], cells[i])
            if types[name] == "number" and value is None and text(cells[i]):
                not_numbers[name] = not_numbers.get(name, 0) + 1
            row[name] = value
        if any(row.get(n) in (None, "") for n in required):
            skipped_rows.append(number_in_file)
            continue
        extra = {key: text(cells[i]) for i, key in extra_index.items() if text(cells[i])}
        if extra:
            row["_extra"] = extra
        rows.append(_derive(table, row))

    warnings = []
    if skipped_rows:
        shown = ", ".join(str(n) for n in skipped_rows[:8]) + ("…" if len(skipped_rows) > 8 else "")
        warnings.append(f"{len(skipped_rows)} row(s) left out - a needed value is empty (row {shown}).")
    for name, count in not_numbers.items():
        warnings.append(f"{count} row(s) have a '{labels[name]}' that is not a number.")
    if not rows:
        raise NormalizeError("No usable rows - every row is missing a needed value.")

    return Normalized(
        rows=rows,
        mapping={name: columns[i] for name, i in assigned.items()},
        extras=[keys[i] for i in sorted(extra_index)],
        warnings=warnings,
        skipped=len(skipped_rows),
    )


def _derive(table: str, row: dict) -> dict:
    """Values a table can work out from the others."""
    if table == "fees":
        amount, paid, outstanding = row.get("amount"), row.get("paid"), row.get("outstanding")
        if outstanding is None and amount is not None and paid is not None:
            row["outstanding"] = max(amount - paid, 0)
        if not row.get("status") and row.get("outstanding") is not None:
            row["status"] = "Paid" if row["outstanding"] == 0 else "Unpaid"
    elif table == "announcements":
        row["audience"] = row.get("audience") or "all"
    return row


def normalize_record(table: str, data: dict, native: bool = True) -> dict:
    """One record typed into a Native Records form - checked like an imported row."""
    t = canonical.spec(table)
    labels = {f["name"]: f["label"] for f in t["fields"]}
    row = {}
    for f in t["fields"]:
        if f["name"] in data:
            row[f["name"]] = coerce(f["type"], data.get(f["name"]))
    bad = [labels[f["name"]] for f in t["fields"]
           if f["type"] == "number" and f["name"] in data and text(data[f["name"]]) and row.get(f["name"]) is None]
    if bad:
        raise NormalizeError(f"Not a number: {', '.join(bad)}.")
    missing = [labels[n] for n in canonical.required_fields(table, native=native) if row.get(n) in (None, "")]
    if missing:
        raise NormalizeError(f"Needed: {', '.join(missing)}.")
    return _derive(table, row)
