"""
ERP records ko LLM ke liye sikorna - BINA maloomat khoye.

Kyun: Groq ki hadd tokens-per-MINUTE par hai, is liye prompt ka har
token seedha ye tay karta hai ke ek minute mein kitne sawal ho sakte
hain. Attendance sab se mehnga tha - 20 records, aur har record mein
student_name / student_group / andaroni IDs dohraye hue:

    {"name":"EDU-ATT-2026-00001","student":"EDU-STU-2026-00013",
     "student_name":"Muhammad Ali","date":"2026-08-10",
     "status":"Present","student_group":"Class 5"}
    ... x20

Ye SUMMARY nahi hai. Har tareekh aur har status ab bhi mojood hai -
bas ek baar likha jata hai, dohra kar nahi. Is liye "kitne din hazir
raha" aur "kis din ghair-hazir tha" dono ka jawab ban sakta hai.

Sath hi jawab sunne mein behtar hota hai: pehle LLM 20 tareekhein ek
ek kar ke padhta tha ("present on July first, July second, July
third..."), ab ginti bolta hai.
"""

from collections import defaultdict


# Andaroni IDs - sunane ke qabil nahi aur har record mein hote hain
_DROP = ("name", "student")


def _who(row: dict) -> str:
    """Record kis ke baare mein hai."""
    return (
        row.get("student_name")
        or row.get("customer")
        or row.get("guardian_name")
        or "?"
    )


def _compact_attendance(rows: list) -> list:
    """Har bache ka ek entry - ginti + tareekhein status ke hisab se."""

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

        # ginti pehle - LLM ko yehi bolna chahiye
        for status, dates in sorted(dates_by_status.items()):
            entry[f"{status.lower()}_days"] = len(dates)

        # Tareekhein sirf UN statuses ki jo aam nahi hain.
        #
        # Aam tor par bacha hazir hota hai, to 9 "present" tareekhein
        # likhna sirf jagah kharab karta hai - aur LLM unhein ek ek
        # kar ke padh deta tha ("July first, July second, July
        # third..."). Ghair-hazri wali tareekhein wo hain jo parent
        # asal mein poochta hai.
        #
        # Maloomat phir bhi poori hai: jo din yahan nahi likha, wo
        # sab se aam status ka din hai - neeche "note" ye keh deta
        # hai.
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
    Har bache ka ek entry; jo fields sab records mein ek jaise hain
    wo upar ek baar, baqi neeche list mein.
    """

    by_student = defaultdict(list)

    for row in rows:
        by_student[_who(row)].append(row)

    out = []

    for student, records in by_student.items():

        entry = {"student_name": student}

        # jo field har record mein ek hi value rakhta hai, wo upar
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
    ERP jawab ko LLM ke liye chhota karein.

    Kuch samajh na aaye to data jaisa hai waisa hi wapis - ye kabhi
    raaste ka rukawat nahi banna chahiye.
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
        print(f"⚠️ [ERP Compact] chhoR diya: {error}")
        return data
