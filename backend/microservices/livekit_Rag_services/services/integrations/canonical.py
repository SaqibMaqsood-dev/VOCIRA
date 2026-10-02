"""
Vocira's canonical records - the one set of tables and fields every school's
records are mapped into, whatever system they came from.

Each table says:
    fields      what it holds: name, label, type, and whether an import needs it
    columns     which model column each field is stored in (models/canonical_records_model.py)
    aliases     other names a source may give a column ("Roll No" -> student_id)
    capability  which kind of data a school shares by allowing it (records_base.CAPABILITIES)

The field names are the ones the Google Sheets tables always used, so a
school's existing sheets map onto them unchanged.
"""

from backend.microservices.livekit_Rag_services.models import canonical_records_model as m

# Field types: text, longtext, number, date, status, email, tel, time, day


def _f(name, label, type_="text", required=False, **extra):
    return {"name": name, "label": label, "type": type_, "required": required, **extra}


TABLES: dict[str, dict] = {
    "students": {
        "label": "Students",
        "model": m.RecStudent,
        "key": "student_id",
        "capability": "profile",
        "fields": [
            # left empty on a Native Records form, one is given (S-0001)
            _f("student_id", "Student ID / admission no.", required=True, native_optional=True),
            _f("student_name", "Student name", required=True),
            # an import needs it - it is what ties a parent to their children
            _f("guardian_id", "Parent / guardian ID", required=True, native_optional=True),
            _f("guardian_name", "Parent name"),
            _f("guardian_email", "Parent email", "email"),
            _f("guardian_mobile", "Parent mobile", "tel"),
            _f("class", "Class"),
            _f("section", "Section"),
            _f("roll_no", "Roll no."),
            _f("gender", "Gender"),
            _f("date_of_birth", "Date of birth", "date"),
        ],
        "columns": {
            "student_id": "student_id", "student_name": "name", "class": "class_name", "section": "section",
            "roll_no": "roll_no", "gender": "gender", "date_of_birth": "date_of_birth",
        },
        "aliases": {
            "roll_number": "student_id", "admission_no": "student_id", "admission_number": "student_id",
            "adm_no": "student_id", "gr_no": "student_id", "registration_no": "student_id", "reg_no": "student_id",
            "roll_no": "student_id", "id": "student_id",
            "name": "student_name", "student": "student_name", "full_name": "student_name",
            "parent_id": "guardian_id", "father_id": "guardian_id", "family_id": "guardian_id",
            "parent_name": "guardian_name", "father_name": "guardian_name", "guardian": "guardian_name",
            "parent_email": "guardian_email", "father_email": "guardian_email", "email": "guardian_email",
            "parent_mobile": "guardian_mobile", "father_mobile": "guardian_mobile", "mobile": "guardian_mobile",
            "phone": "guardian_mobile", "contact": "guardian_mobile", "whatsapp": "guardian_mobile",
            "grade": "class", "class_name": "class", "standard": "class",
            "dob": "date_of_birth", "birth_date": "date_of_birth", "sex": "gender",
        },
    },
    "guardians": {
        "label": "Parents",
        "model": m.RecGuardian,
        "key": "guardian_id",
        "capability": "profile",
        "fields": [
            _f("guardian_id", "Parent / guardian ID", required=True, native_optional=True),
            _f("guardian_name", "Name", required=True),
            _f("guardian_email", "Email", "email"),
            _f("guardian_mobile", "Mobile", "tel"),
            _f("relation", "Relation"),
        ],
        "columns": {
            "guardian_id": "guardian_id", "guardian_name": "name", "guardian_email": "email",
            "guardian_mobile": "mobile", "relation": "relation",
        },
        "aliases": {
            "parent_id": "guardian_id", "father_id": "guardian_id", "family_id": "guardian_id", "id": "guardian_id",
            "name": "guardian_name", "parent_name": "guardian_name", "father_name": "guardian_name",
            "email": "guardian_email", "parent_email": "guardian_email",
            "mobile": "guardian_mobile", "phone": "guardian_mobile", "contact": "guardian_mobile",
            "whatsapp": "guardian_mobile", "relationship": "relation",
        },
    },
    "classes": {
        "label": "Classes",
        "model": m.RecClass,
        "key": "class_id",
        "capability": "profile",
        "fields": [
            _f("class_id", "Class ID", required=True, native_optional=True),
            _f("class_name", "Class name", required=True),
            _f("section", "Section"),
            _f("class_teacher", "Class teacher"),
        ],
        "columns": {"class_id": "class_id", "class_name": "name", "section": "section", "class_teacher": "class_teacher"},
        "aliases": {"id": "class_id", "name": "class_name", "class": "class_name", "grade": "class_name",
                    "teacher": "class_teacher", "incharge": "class_teacher"},
    },
    "teachers": {
        "label": "Teachers",
        "model": m.RecTeacher,
        "key": "teacher_id",
        "capability": "profile",
        "fields": [
            _f("teacher_id", "Teacher ID", required=True, native_optional=True),
            _f("teacher_name", "Name", required=True),
            _f("subject", "Subject"),
            _f("teacher_email", "Email", "email"),
            _f("teacher_mobile", "Mobile", "tel"),
        ],
        "columns": {"teacher_id": "teacher_id", "teacher_name": "name", "subject": "subject",
                    "teacher_email": "email", "teacher_mobile": "mobile"},
        "aliases": {"id": "teacher_id", "employee_id": "teacher_id", "staff_id": "teacher_id",
                    "name": "teacher_name", "email": "teacher_email", "mobile": "teacher_mobile",
                    "phone": "teacher_mobile", "subjects": "subject"},
    },
    "attendance": {
        "label": "Attendance",
        "model": m.RecAttendance,
        "key": None,
        "capability": "attendance",
        "fields": [
            _f("student_id", "Student ID", required=True),
            _f("date", "Date", "date", required=True),
            _f("status", "Status (Present / Absent / Leave / Late)", "status", required=True),
            _f("remarks", "Remarks"),
        ],
        "columns": {"student_id": "student_id", "date": "date", "status": "status", "remarks": "remarks"},
        "aliases": {"roll_no": "student_id", "roll_number": "student_id", "admission_no": "student_id",
                    "adm_no": "student_id", "attendance": "status", "present": "status", "day": "date",
                    "attendance_date": "date", "remark": "remarks", "note": "remarks"},
    },
    "fees": {
        "label": "Fees",
        "model": m.RecFee,
        "key": None,
        "capability": "fees",
        "fields": [
            _f("student_id", "Student ID", required=True),
            _f("amount", "Amount", "number", required=True),
            _f("description", "Description (e.g. October tuition)"),
            _f("paid", "Paid", "number"),
            _f("outstanding", "Outstanding", "number"),
            _f("due_date", "Due date", "date"),
            _f("status", "Status"),
        ],
        "columns": {"student_id": "student_id", "amount": "amount", "description": "description", "paid": "paid",
                    "outstanding": "outstanding", "due_date": "due_date", "status": "status"},
        "aliases": {"roll_no": "student_id", "roll_number": "student_id", "admission_no": "student_id",
                    "adm_no": "student_id", "fee_type": "description", "month": "description", "title": "description",
                    "challan": "description", "total": "amount", "fee": "amount", "total_fee": "amount",
                    "paid_amount": "paid", "received": "paid", "balance": "outstanding", "due_amount": "outstanding",
                    "remaining": "outstanding", "arrears": "outstanding", "due": "due_date", "last_date": "due_date"},
    },
    "results": {
        "label": "Results",
        "model": m.RecResult,
        "key": None,
        "capability": "results",
        "fields": [
            _f("student_id", "Student ID", required=True),
            _f("subject", "Subject", required=True),
            _f("marks", "Marks obtained", "number", required=True),
            _f("total", "Total marks", "number"),
            _f("grade", "Grade"),
            _f("exam", "Exam / term"),
            _f("year", "Year"),
        ],
        "columns": {"student_id": "student_id", "subject": "subject", "marks": "marks", "total": "total",
                    "grade": "grade", "exam": "exam", "year": "year"},
        "aliases": {"roll_no": "student_id", "roll_number": "student_id", "admission_no": "student_id",
                    "adm_no": "student_id", "course": "subject", "obtained": "marks", "obtained_marks": "marks",
                    "score": "marks", "max_marks": "total", "total_marks": "total", "out_of": "total",
                    "maximum": "total", "term": "exam", "assessment": "exam", "test": "exam",
                    "academic_year": "year", "session": "year"},
    },
    "timetable": {
        "label": "Timetable",
        "model": m.RecTimetable,
        "key": None,
        "capability": "timetable",
        "fields": [
            _f("class", "Class", required=True),
            _f("day", "Day", "day", required=True),
            _f("subject", "Subject", required=True),
            _f("start_time", "Starts", "time"),
            _f("end_time", "Ends", "time"),
            _f("teacher", "Teacher"),
            _f("room", "Room"),
        ],
        "columns": {"class": "class_name", "day": "day", "subject": "subject", "start_time": "start_time",
                    "end_time": "end_time", "teacher": "teacher", "room": "room"},
        "aliases": {"class_name": "class", "grade": "class", "weekday": "day", "course": "subject",
                    "start": "start_time", "from": "start_time", "time": "start_time", "end": "end_time",
                    "to": "end_time", "teacher_name": "teacher", "room_no": "room"},
    },
    "announcements": {
        "label": "Announcements",
        "model": m.RecAnnouncement,
        "key": None,
        # school-wide notices: shared with every caller, guests too
        "capability": None,
        "fields": [
            _f("title", "Title", required=True),
            _f("message", "Message", "longtext", required=True),
            _f("audience", "For (all, or one class)"),
            _f("date", "Date", "date"),
            _f("expires", "Show until", "date"),
        ],
        "columns": {"title": "title", "message": "message", "audience": "audience", "date": "date", "expires": "expires"},
        "aliases": {"subject": "title", "heading": "title", "notice": "message", "body": "message",
                    "details": "message", "description": "message", "class": "audience",
                    "published": "date", "until": "expires", "expiry": "expires"},
    },
}

# The tables a parent's question can be answered from, in the order the admin panel lists them.
TABLE_ORDER = list(TABLES)


def spec(table: str) -> dict:
    if table not in TABLES:
        raise KeyError(table)
    return TABLES[table]


def field_names(table: str) -> list[str]:
    return [f["name"] for f in spec(table)["fields"]]


def required_fields(table: str, native: bool = False) -> list[str]:
    return [f["name"] for f in spec(table)["fields"]
            if f["required"] and not (native and f.get("native_optional"))]


def public_tables() -> list[dict]:
    """What the admin panel needs to build the mapping step and the Native Records forms."""
    return [
        {
            "table": name,
            "label": t["label"],
            "capability": t["capability"],
            "fields": [{k: v for k, v in f.items()} for f in t["fields"]],
        }
        for name, t in TABLES.items()
    ]
