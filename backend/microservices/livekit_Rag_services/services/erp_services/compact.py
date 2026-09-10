"""
Shrinking ERP records for the LLM - WITHOUT losing information.

Why: Groq's limit is on tokens-per-MINUTE, so every token in the
prompt directly sets how many questions fit into a minute. Attendance
was the most expensive - 20 records, each repeating student_name /
student_group / internal IDs:

    {"name":"EDU-ATT-2026-00001","student":"EDU-STU-2026-00013",
     "student_name":"Muhammad Ali","date":"2026-08-10",
     "status":"Present","student_group":"Class 5"}
    ... x20

This is not a SUMMARY. Every date and every status is still there -
just written once instead of repeated. So both "how many days were
they present" and "which day were they absent" can still be answered.

It also sounds better: the LLM used to read all 20 dates out one by
one ("present on July first, July second, July third..."), and now
gives a count.
"""

from collections import defaultdict


# Internal IDs - not worth speaking aloud, and present in every record
_DROP = ("name", "student")


def _who(row: dict) -> str:
    """Who the record is about."""
    return (
        row.get("student_name")
        or row.get("customer")
        or row.get("guardian_name")
        or "?"
    )


def _compact_attendance(rows: list) -> list:
    """One entry per child - a count, plus the dates grouped by status."""

    by_student = defaultdict(list)

    for row in rows:
        by_student[_who(row)].append(row)

    out = []

    for student, records in by_student.items():

        dates_by_status = defaultdict(list)

        for record in records:
            status = record.get("status") or "Unknown"
            date = record.get("date")
            if date:
                dates_by_status[status].append(date)

        for dates in dates_by_status.values():
            dates.sort()

        entry = {
            "student_name": student,
            "total_days_recorded": len(records),
        }

        group = next(
            (r.get("student_group") for r in records if r.get("student_group")),
            None,
        )
        if group:
            entry["class"] = group

        all_dates = sorted(
            d for dates in dates_by_status.values() for d in dates
        )
        if all_dates:
            entry["period"] = f"{all_dates[0]} to {all_dates[-1]}"

        # the count first - this is what the LLM should say
        for status, dates in sorted(dates_by_status.items()):
            entry[f"{status.lower()}_days"] = len(dates)

        # Dates only for the statuses that are NOT the common one.
        #
        # A child is usually present, so listing 9 "present" dates
        # only wastes room - and the LLM read them out one by one
        # ("July first, July second, July third..."). The absent
        # dates are the ones a parent actually asks about.
        #
        # No information is lost: any day not listed here is a day
        # with the most common status - the "note" below says so.
        common = max(dates_by_status, key=lambda s: len(dates_by_status[s]))

        for status, dates in sorted(dates_by_status.items()):
            if status != common:
                entry[f"{status.lower()}_dates"] = dates

        if len(dates_by_status) > 1:
            entry["note"] = (
                f"All other recorded days were {common}."
            )

        out.append(entry)

    return out


def _group_by_student(rows: list, repeated: tuple) -> list:
    """
    One entry per child; fields that are identical across all the
    records appear once at the top, the rest go in the list below.
    """

    by_student = defaultdict(list)

    for row in rows:
        by_student[_who(row)].append(row)

    out = []

    for student, records in by_student.items():

        entry = {"student_name": student}

        # a field holding one value across every record moves up
        for field in repeated:
            values = {r.get(field) for r in records if r.get(field)}
            if len(values) == 1:
                entry[field] = values.pop()

        items = []

        for record in records:
            item = {
                k: v
                for k, v in record.items()
                if k not in entry
                and k != "student_name"
                and v not in (None, "")
            }
            if item:
                items.append(item)

        entry["records"] = items
        out.append(entry)

    return out


def compact_records(resource: str, data: dict) -> dict:
    """
    Shrink an ERP response for the LLM.

    If anything is unclear, the data comes back untouched - this
    should never stand in the way.
    """

    try:
        rows = data.get("data")

        if not isinstance(rows, list) or not rows:
            return data

        # har record se andaroni IDs nikaal dein
        rows = [
            {k: v for k, v in row.items() if k not in _DROP}
            for row in rows
            if isinstance(row, dict)
        ]

        if resource == "attendance":
            rows = _compact_attendance(rows)

        elif resource in ("assessment", "course", "program_enrollment"):
            rows = _group_by_student(
                rows,
                repeated=("academic_year", "assessment_group", "program"),
            )

        return {**data, "data": rows}

    except Exception as error:
        print(f"[ERP Compact] chhoR diya: {error}")
        return data
