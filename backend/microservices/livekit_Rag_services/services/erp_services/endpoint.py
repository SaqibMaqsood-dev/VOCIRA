"""
ERP resource whitelist.

Each entry states:

    endpoint                : Frappe REST path (only /api/ is allowed)
    authorization           : how the filter is applied -
                              "guardian"      -> the guardian's own record
                              "student"       -> the guardian's students
                              "student_group" -> those students' classes
    student_filter_field    : which field holds the student ID
    student_filter_doctype  : (optional) the child doctype name, if the
                              student link lives in a child table
    group_filter_field      : (for student_group) the class field name
    fields                  : which fields to request from ERP
    description             : what to tell the LLM

IMPORTANT - why "fields" are listed here:

    The LLM picks the right resource, but it invents field names
    ("attendance_date", "subject", "score"), and Frappe answers those
    with HTTP 417 "Field not permitted in query".

    So the LLM's field list is ignored and this authoritative list is
    sent instead. These names come from the real ERP schema.
"""

ERP_RESOURCES = {

    # =====================================================
    # STUDENT / GUARDIAN
    # =====================================================

    "student": {
        "endpoint": "/api/resource/Student",
        "authorization": "student",
        "student_filter_field": "name",
        "fields": [
            "name",
            "student_name",
            "gender",
            "date_of_birth",
            "student_email_id",
            "joining_date",
        ],
        "description": "Student profile: naam, gender, email, date of birth.",
    },

    "guardian": {
        "endpoint": "/api/resource/Guardian",
        "authorization": "guardian",
        "fields": [
            "name",
            "guardian_name",
            "email_address",
            "mobile_number",
            "occupation",
        ],
        "description": "Guardian ki apni maloomat.",
    },

    # =====================================================
    # ACADEMIC RECORD
    # =====================================================

    "program_enrollment": {
        "endpoint": "/api/resource/Program Enrollment",
        "authorization": "student",
        "student_filter_field": "student",
        "fields": [
            "name",
            "student",
            "student_name",
            "program",
            "academic_year",
            "enrollment_date",
        ],
        "description": (
            "Student ka program enrollment: program, academic year."
        ),
    },

    "course": {
        "endpoint": "/api/resource/Course Enrollment",
        "authorization": "student",
        "student_filter_field": "student",
        "fields": [
            "name",
            "student",
            "student_name",
            "course",
            "program",
            "enrollment_date",
        ],
        "description": (
            "Which subjects/courses the student is enrolled in."
        ),
    },

    "class": {
        # In Student Group the link to the student lives in a child
        # table, so a plain ["student","in",...] returns HTTP 417.
        "endpoint": "/api/resource/Student Group",
        "authorization": "student",
        "student_filter_doctype": "Student Group Student",
        "student_filter_field": "student",
        "fields": [
            "name",
            "student_group_name",
            "program",
            "academic_year",
        ],
        "description": "Which class / student group the student is in.",
    },

    # =====================================================
    # ATTENDANCE / RESULTS
    # =====================================================

    "attendance": {
        "endpoint": "/api/resource/Student Attendance",
        "authorization": "student",
        "student_filter_field": "student",
        "fields": [
            "name",
            "student",
            "student_name",
            "date",
            "status",
            "student_group",
        ],
        "description": (
            "Rozana attendance record: date aur status "
            "(Present / Absent)."
        ),
    },

    "assessment": {
        "endpoint": "/api/resource/Assessment Result",
        "authorization": "student",
        "student_filter_field": "student",
        "fields": [
            "name",
            "student",
            "student_name",
            "course",
            "assessment_group",
            "total_score",
            "maximum_score",
            "grade",
            "academic_year",
        ],
        "description": (
            "Ho chuke exams ke marks aur grades."
        ),
    },

    "exam": {
        # Assessment Plan is attached to the class, not to the student.
        "endpoint": "/api/resource/Assessment Plan",
        "authorization": "student_group",
        "group_filter_field": "student_group",
        # "room" is left out - as with the schedule, it is only an ID here.
        "fields": [
            "name",
            "assessment_name",
            "student_group",
            "course",
            "schedule_date",
            "from_time",
            "to_time",
            "maximum_assessment_score",
        ],
        "description": (
            "Upcoming exams / assessments: name, subject, date, "
            "time, room and maximum score."
        ),
    },

    # =====================================================
    # TIMETABLE
    # =====================================================

    "schedule": {
        # Event is empty; the real timetable is in Course Schedule,
        # which is attached to the class.
        "endpoint": "/api/resource/Course Schedule",
        "authorization": "student_group",
        "group_filter_field": "student_group",
        # NOTE: "room" is deliberately left out. Course Schedule only
        # holds the room's ID (HTL-ROOM-2026-00002), not its name, and
        # TTS reads that ID out one character at a time. Getting the
        # room name would need a separate fetch from the Room doctype.
        "fields": [
            "name",
            "student_group",
            "course",
            "instructor_name",
            "schedule_date",
            "from_time",
            "to_time",
        ],
        "description": (
            "Class timetable: subject, teacher, date and time."
        ),
    },

    # =====================================================
    # FEES / PAYMENTS
    # =====================================================

    "fee": {
        # Education's "Fees" doctype is empty in this setup.
        # The real fee bills are in Sales Invoice, which also has a
        # student field.
        # NOTE: Sales Invoice has no "student_name" - it has "customer".
        "endpoint": "/api/resource/Sales Invoice",
        "authorization": "student",
        "student_filter_field": "student",
        "fields": [
            "name",
            "student",
            "customer",
            "posting_date",
            "due_date",
            "grand_total",
            "outstanding_amount",
            "status",
        ],
        "description": (
            "Fee bills: kul raqam, baqi raqam, due date aur status "
            "(Paid / Unpaid / Overdue)."
        ),
    },

    "payment": {
        # Payment Entry has no student field (HTTP 417).
        # A Sales Invoice's status/outstanding answers the payment
        # question on its own.
        "endpoint": "/api/resource/Sales Invoice",
        "authorization": "student",
        "student_filter_field": "student",
        "fields": [
            "name",
            "student",
            "customer",
            "posting_date",
            "grand_total",
            "outstanding_amount",
            "status",
        ],
        "description": (
            "Payment status: whether the fee has been paid, "
            "and how much is outstanding."
        ),
    },
}
