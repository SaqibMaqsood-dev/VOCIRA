"""
ERP resource whitelist.

Har entry batati hai:

    endpoint                : Frappe REST path (sirf /api/ allowed hai)
    authorization           : filter lagane ka tareeqa -
                              "guardian"      -> guardian ke apne record
                              "student"       -> guardian ke students par
                              "student_group" -> un students ki classes par
    student_filter_field    : student ID kis field mein hai
    student_filter_doctype  : (optional) agar student link child table mein
                              ho to us child doctype ka naam
    group_filter_field      : (student_group ke liye) class field ka naam
    fields                  : ERP se kaun se fields mangwane hain
    description             : LLM ko batane ke liye

IMPORTANT - "fields" yahan kyun likhe hain:

    LLM resource to sahi chunta hai, magar field ke naam ghar se bana
    leta hai ("attendance_date", "subject", "score"), jis par Frappe
    HTTP 417 "Field not permitted in query" deta hai.

    Is liye LLM ki field list nazarandaz ki jati hai aur yahi authoritative
    list bheji jati hai. Ye naam asal ERP schema se liye gaye hain.
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
            "Student kaun kaun se subjects/courses parh raha hai."
        ),
    },

    "class": {
        # Student Group mein student ka link child table mein hota hai,
        # is liye seedha ["student","in",...] HTTP 417 deta hai.
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
        "description": "Student kis class / student group mein hai.",
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
        # Assessment Plan class ke saath juda hota hai, student ke saath nahi.
        "endpoint": "/api/resource/Assessment Plan",
        "authorization": "student_group",
        "group_filter_field": "student_group",
        # "room" shamil nahi - schedule ki tarah yahan bhi sirf ID hoti hai.
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
            "Aane wale exams / assessments: naam, subject, tareekh, "
            "waqt, room aur maximum score."
        ),
    },

    # =====================================================
    # TIMETABLE
    # =====================================================

    "schedule": {
        # Event khali hai; asli timetable Course Schedule mein hai,
        # aur wo class ke saath juda hota hai.
        "endpoint": "/api/resource/Course Schedule",
        "authorization": "student_group",
        "group_filter_field": "student_group",
        # NOTE: "room" jaan bujh kar shamil nahi hai. Course Schedule
        # sirf room ka ID rakhta hai (HTL-ROOM-2026-00002), naam nahi,
        # aur TTS us ID ko har haraf alag bolta hai. Room ka naam
        # chahiye ho to Room doctype se alag fetch karna paregi.
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
            "Class timetable: subject, teacher, tareekh aur waqt."
        ),
    },

    # =====================================================
    # FEES / PAYMENTS
    # =====================================================

    "fee": {
        # Education ka "Fees" doctype is setup mein khali hai.
        # Asli fee bills Sales Invoice mein hain, jahan student field bhi hai.
        # NOTE: Sales Invoice par "student_name" nahi hota - "customer" hota hai.
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
        # Payment Entry mein student field nahi hota (HTTP 417).
        # Sales Invoice ka status/outstanding hi payment ka jawab deta hai.
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
            "Payment ki soorat-e-haal: fee jama hui ya nahi, "
            "kitni baqi hai."
        ),
    },
}
