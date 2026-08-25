ERP_RESOURCES = {
    "student": {
        "endpoint": "/api/resource/Student",
        "authorization": "student",
        "description": "Student information.",
    },

    "guardian": {
        "endpoint": "/api/resource/Guardian",
        "authorization": "guardian",
        "description": "Guardian information.",
    },

    "program_enrollment": {
        "endpoint": "/api/resource/Program Enrollment",
        "authorization": "student",
        "description": (
            "Student program enrollment including "
            "program, academic year, and enrolled courses."
        ),
    },

    "attendance": {
        "endpoint": "/api/resource/Student Attendance",
        "authorization": "student",
        "description": "Student attendance records.",
    },

    "fee": {
        "endpoint": "/api/resource/Fee",
        "authorization": "student",
        "description": "Student fee records.",
    },

    "payment": {
        "endpoint": "/api/resource/Payment Entry",
        "authorization": "student",
        "description": "Student payment records.",
    },

    "assessment": {
        "endpoint": "/api/resource/Assessment Result",
        "authorization": "student",
        "description": "Student marks and assessment results.",
    },

    "class": {
        "endpoint": "/api/resource/Student Group",
        "authorization": "student",
        "description": "Student class and group information.",
    },

    "schedule": {
        "endpoint": "/api/resource/Event",
        "authorization": "student",
        "description": "Student schedules and academic events.",
    },
}