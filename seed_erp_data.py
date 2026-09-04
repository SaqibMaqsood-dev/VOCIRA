"""
ERPNext mein test data: 2 guardian, 4 student, aur har student ka
poora academic + financial record.

    python seed_erp_data.py            # banayein
    python seed_erp_data.py --check    # sirf dekhein, banayein nahi

Dobara chalane par kuch kharab nahi hota - jo pehle se mojood hai
wo chhora ja jata hai (naam se dhoonda jata hai).

Dhaancha wahi rakha gaya hai jo mojooda data mein hai, taake
endpoint.py ki queries bina kisi tabdeeli ke chalti rahein.
"""

import json
import sys
from datetime import date, timedelta

import httpx

from backend.microservices.livekit_Rag_services.core.config import settings

BASE = settings.ERP_BASE_URL.rstrip("/")
HEADERS = {
    "Authorization": (
        f"token {settings.ERP_API_KEY}:{settings.ERP_API_SECRET}"
    ),
    "Accept": "application/json",
    "Content-Type": "application/json",
}

CHECK_ONLY = "--check" in sys.argv

# ---- mojooda setup se ----
PROGRAM = "Primary Education"
YEAR = "2026-2027"
COURSES = ["English", "Urdu", "Mathematics", "Islamiyat"]
COMPANY = "vocira (Demo)"
INCOME_ACCOUNT = "Service - vocira_voiD"
COST_CENTER = "Main - vocira_voiD"
FEE_ITEM = "Tuition fee"
GRADING = "Standard Grading Scale"

# Course Schedule mein room lazmi hai (ERPNext MandatoryError).
# Har class ka apna kamra.
ROOMS = {"Class 4": "HTL-ROOM-2026-00002", "Class 5": "HTL-ROOM-2026-00003"}

client = httpx.Client(headers=HEADERS, timeout=60)

created = []
skipped = []
failed = []


def log(kind, what, extra=""):
    bucket = {"+": created, "=": skipped, "!": failed}[kind]
    bucket.append(what)
    print(f"  {kind} {what}{('  ' + extra) if extra else ''}")


def find(doctype, filters, field="name"):
    r = client.get(
        f"{BASE}/api/resource/{doctype}",
        params={"filters": json.dumps(filters), "limit_page_length": 1},
    )
    if r.status_code != 200:
        return None
    rows = r.json().get("data", [])
    return rows[0][field] if rows else None


def create(doctype, payload, label, submit=False):
    r = client.post(f"{BASE}/api/resource/{doctype}", json=payload)

    if r.status_code not in (200, 201):
        log("!", label, f"HTTP {r.status_code} {r.text[:150]}")
        return None

    name = r.json()["data"]["name"]

    if submit:
        s = client.put(
            f"{BASE}/api/resource/{doctype}/{name}",
            json={"docstatus": 1},
        )
        if s.status_code not in (200, 201):
            log("!", f"{label} (submit)", f"HTTP {s.status_code} {s.text[:120]}")
            return name

    log("+", label, name)
    return name


# =========================================================
# KAUN KAUN
# =========================================================

FAMILIES = [
    {
        "guardian": {
            "guardian_name": "Bilal Hussain",
            "email_address": "bilal.hussain@edu.com",
            "mobile_number": "03001234567",
            "occupation": "Bank Manager",
        },
        "students": [
            {
                "first_name": "Ayesha Bilal",
                "gender": "Female",
                "date_of_birth": "2016-03-14",
                "email": "ayesha.bilal@school.edu",
                "group": "Class 4",
                # fee: ek bachche ki bharri hui, doosre ki baqi
                "fee_paid": True,
                "marks": {"English": 82, "Urdu": 75, "Mathematics": 91, "Islamiyat": 88},
                "absent_days": ["2026-08-05"],
            },
            {
                "first_name": "Usman Bilal",
                "gender": "Male",
                "date_of_birth": "2014-11-02",
                "email": "usman.bilal@school.edu",
                "group": "Class 5",
                "fee_paid": False,
                "marks": {"English": 64, "Urdu": 71, "Mathematics": 58, "Islamiyat": 79},
                "absent_days": ["2026-08-04", "2026-08-11"],
            },
        ],
    },
    {
        "guardian": {
            "guardian_name": "Sana Tariq",
            "email_address": "sana.tariq@edu.com",
            "mobile_number": "03219876543",
            "occupation": "Doctor",
        },
        "students": [
            {
                "first_name": "Hina Tariq",
                "gender": "Female",
                "date_of_birth": "2016-07-21",
                "email": "hina.tariq@school.edu",
                "group": "Class 4",
                "fee_paid": True,
                "marks": {"English": 95, "Urdu": 89, "Mathematics": 84, "Islamiyat": 92},
                "absent_days": [],
            },
            {
                "first_name": "Saad Tariq",
                "gender": "Male",
                "date_of_birth": "2015-01-09",
                "email": "saad.tariq@school.edu",
                "group": "Class 5",
                "fee_paid": False,
                "marks": {"English": 70, "Urdu": 66, "Mathematics": 73, "Islamiyat": 61},
                "absent_days": ["2026-08-06"],
            },
        ],
    },
]

# Attendance ke din (school ke din)
TERM_DAYS = [date(2026, 8, 3) + timedelta(days=i) for i in range(10)]
TERM_DAYS = [d for d in TERM_DAYS if d.weekday() < 5]


def grade_for(score):
    if score >= 90: return "A+"
    if score >= 80: return "A"
    if score >= 70: return "B"
    if score >= 60: return "C"
    return "D"


# =========================================================
# 1. STUDENTS + GUARDIANS
# =========================================================

def seed_people():
    print("\n--- 1. Guardians aur Students ---")

    for family in FAMILIES:

        g = family["guardian"]
        gname = find("Guardian", {"guardian_name": g["guardian_name"]})

        if gname:
            log("=", f"guardian {g['guardian_name']}", gname)
        elif not CHECK_ONLY:
            gname = create("Guardian", g, f"guardian {g['guardian_name']}")

        family["guardian_id"] = gname

        for s in family["students"]:
            sname = find("Student", {"student_name": s["first_name"]})

            if sname:
                log("=", f"student {s['first_name']}", sname)
            elif not CHECK_ONLY:
                sname = create(
                    "Student",
                    {
                        "first_name": s["first_name"],
                        "student_email_id": s["email"],
                        "gender": s["gender"],
                        "date_of_birth": s["date_of_birth"],
                        "joining_date": "2026-05-25",
                        "country": "Pakistan",
                        # Guardian ke through hi rishta banta hai
                        "guardians": [{"guardian": gname}] if gname else [],
                    },
                    f"student {s['first_name']}",
                )

            s["id"] = sname

        # Guardian ke students table mein bhi daalein - endpoint.py
        # isi rishte se parent ke bachche dhoondti hai.
        if gname and not CHECK_ONLY:
            kids = [
                {"student": s["id"], "student_name": s["first_name"]}
                for s in family["students"] if s.get("id")
            ]
            r = client.put(
                f"{BASE}/api/resource/Guardian/{gname}",
                json={"students": kids},
            )
            if r.status_code in (200, 201):
                log("+", f"{g['guardian_name']} ke {len(kids)} bachche jode")
            else:
                log("!", f"{g['guardian_name']} ke bachche", f"HTTP {r.status_code}")


# =========================================================
# 2. CUSTOMER  (Sales Invoice ke liye zaroori)
# =========================================================

def seed_customers():
    print("\n--- 2. Customers (fee bill ke liye) ---")

    for family in FAMILIES:
        for s in family["students"]:
            if not s.get("id"):
                continue
            name = s["first_name"]
            if find("Customer", {"customer_name": name}):
                log("=", f"customer {name}")
            elif not CHECK_ONLY:
                create(
                    "Customer",
                    {
                        "customer_name": name,
                        "customer_group": "Student",
                        "territory": "All Territories",
                    },
                    f"customer {name}",
                )


# =========================================================
# 3. ENROLLMENT  (program + courses)
# =========================================================

def seed_enrollment():
    print("\n--- 3. Program aur Course enrollment ---")

    for family in FAMILIES:
        for s in family["students"]:
            sid = s.get("id")
            if not sid:
                continue

            enr = find("Program Enrollment", {"student": sid})

            if enr:
                log("=", f"enrollment {s['first_name']}", enr)
            elif not CHECK_ONLY:
                enr = create(
                    "Program Enrollment",
                    {
                        "student": sid,
                        "student_name": s["first_name"],
                        "program": PROGRAM,
                        "academic_year": YEAR,
                        "enrollment_date": "2026-05-25",
                        "courses": [{"course": c} for c in COURSES],
                    },
                    f"enrollment {s['first_name']}",
                    submit=True,
                )

            s["enrollment"] = enr

            if not enr or CHECK_ONLY:
                continue

            for course in COURSES:
                if find("Course Enrollment", {"student": sid, "course": course}):
                    continue
                create(
                    "Course Enrollment",
                    {
                        "student": sid,
                        "student_name": s["first_name"],
                        "program_enrollment": enr,
                        "program": PROGRAM,
                        "course": course,
                        "enrollment_date": "2026-05-25",
                    },
                    f"  course {course} -> {s['first_name']}",
                )


# =========================================================
# 4. CLASS  (Student Group ka member banayein)
# =========================================================

def seed_groups():
    print("\n--- 4. Class (Student Group) ---")

    by_group = {}
    for family in FAMILIES:
        for s in family["students"]:
            if s.get("id"):
                by_group.setdefault(s["group"], []).append(s)

    for group, students in by_group.items():
        r = client.get(f"{BASE}/api/resource/Student Group/{group}")
        if r.status_code != 200:
            log("!", f"group {group}", f"HTTP {r.status_code}")
            continue

        existing = r.json()["data"].get("students", [])
        have = {row.get("student") for row in existing}

        rows = [
            {
                "student": row.get("student"),
                "student_name": row.get("student_name"),
                "group_roll_number": row.get("group_roll_number") or (i + 1),
                "active": 1,
            }
            for i, row in enumerate(existing)
        ]

        added = 0
        for s in students:
            if s["id"] in have:
                log("=", f"{s['first_name']} pehle se {group} mein")
                continue
            rows.append(
                {
                    "student": s["id"],
                    "student_name": s["first_name"],
                    "group_roll_number": len(rows) + 1,
                    "active": 1,
                }
            )
            added += 1

        if added and not CHECK_ONLY:
            u = client.put(
                f"{BASE}/api/resource/Student Group/{group}",
                json={"students": rows},
            )
            if u.status_code in (200, 201):
                log("+", f"{group} mein {added} student jode")
            else:
                log("!", f"{group}", f"HTTP {u.status_code} {u.text[:120]}")


# =========================================================
# 5. ATTENDANCE
# =========================================================

def seed_attendance():
    print("\n--- 5. Attendance ---")

    for family in FAMILIES:
        for s in family["students"]:
            sid = s.get("id")
            if not sid or CHECK_ONLY:
                continue

            made = 0
            for day in TERM_DAYS:
                iso = day.isoformat()

                if find("Student Attendance", {"student": sid, "date": iso}):
                    continue

                status = "Absent" if iso in s["absent_days"] else "Present"

                r = client.post(
                    f"{BASE}/api/resource/Student Attendance",
                    json={
                        "student": sid,
                        "student_name": s["first_name"],
                        "student_group": s["group"],
                        "date": iso,
                        "status": status,
                    },
                )
                if r.status_code in (200, 201):
                    client.put(
                        f"{BASE}/api/resource/Student Attendance/"
                        f"{r.json()['data']['name']}",
                        json={"docstatus": 1},
                    )
                    made += 1
                else:
                    log("!", f"attendance {s['first_name']} {iso}",
                        f"HTTP {r.status_code} {r.text[:110]}")
                    break

            if made:
                log("+", f"{s['first_name']}: {made} din ki attendance",
                    f"({len(s['absent_days'])} absent)")
            else:
                log("=", f"{s['first_name']} ki attendance pehle se")


# =========================================================
# 6. EXAM  (Assessment Plan) - har class ke har subject ka
# =========================================================

EXAM_TIMES = {
    "English":     ("2026-09-14", "09:00:00", "11:00:00"),
    "Urdu":        ("2026-09-15", "09:00:00", "11:00:00"),
    "Mathematics": ("2026-09-16", "09:00:00", "11:30:00"),
    "Islamiyat":   ("2026-09-17", "09:00:00", "10:30:00"),
}


def seed_exams():
    print("\n--- 6. Exams (Assessment Plan) ---")

    groups = sorted({s["group"] for f in FAMILIES for s in f["students"]})
    plans = {}

    for group in groups:
        for course in COURSES:
            existing = find(
                "Assessment Plan",
                {
                    "student_group": group,
                    "course": course,
                    "assessment_group": "Mid term",
                },
            )
            if existing:
                plans[(group, course)] = existing
                log("=", f"exam {group} {course}", existing)
                continue

            if CHECK_ONLY:
                continue

            when, start, end = EXAM_TIMES[course]

            name = create(
                "Assessment Plan",
                {
                    "student_group": group,
                    "assessment_group": "Mid term",
                    "grading_scale": GRADING,
                    "program": PROGRAM,
                    "course": course,
                    "academic_year": YEAR,
                    "schedule_date": when,
                    "from_time": start,
                    "to_time": end,
                    "maximum_assessment_score": 100,
                    "assessment_criteria": [
                        {"assessment_criteria": "Midterm", "maximum_score": 100}
                    ],
                },
                f"exam {group} {course}",
                submit=True,
            )
            if name:
                plans[(group, course)] = name

    return plans


# =========================================================
# 7. MARKS  (Assessment Result)
# =========================================================

def seed_results(plans):
    print("\n--- 7. Marks (Assessment Result) ---")

    for family in FAMILIES:
        for s in family["students"]:
            sid = s.get("id")
            if not sid or CHECK_ONLY:
                continue

            made = 0
            for course, score in s["marks"].items():
                plan = plans.get((s["group"], course))
                if not plan:
                    continue

                if find("Assessment Result",
                        {"student": sid, "assessment_plan": plan}):
                    continue

                grade = grade_for(score)

                r = client.post(
                    f"{BASE}/api/resource/Assessment Result",
                    json={
                        "assessment_plan": plan,
                        "student": sid,
                        "student_name": s["first_name"],
                        "student_group": s["group"],
                        "program": PROGRAM,
                        "course": course,
                        "academic_year": YEAR,
                        "assessment_group": "Mid term",
                        "grading_scale": GRADING,
                        "maximum_score": 100,
                        "details": [
                            {
                                "assessment_criteria": "Midterm",
                                "maximum_score": 100,
                                "score": score,
                                "grade": grade,
                            }
                        ],
                    },
                )
                if r.status_code in (200, 201):
                    client.put(
                        f"{BASE}/api/resource/Assessment Result/"
                        f"{r.json()['data']['name']}",
                        json={"docstatus": 1},
                    )
                    made += 1
                else:
                    log("!", f"marks {s['first_name']} {course}",
                        f"HTTP {r.status_code} {r.text[:110]}")
                    break

            if made:
                log("+", f"{s['first_name']}: {made} subject ke marks",
                    str(s["marks"]))
            else:
                log("=", f"{s['first_name']} ke marks pehle se")


# =========================================================
# 8. TIMETABLE  (Course Schedule) - class ka, student ka nahi
# =========================================================

PERIODS = [
    ("English",     "08:00:00", "09:00:00", "Ayesha Malik"),
    ("Urdu",        "09:00:00", "10:00:00", "Nida Hassan"),
    ("Mathematics", "10:30:00", "11:30:00", "Tariq Mehmood"),
    ("Islamiyat",   "11:30:00", "12:30:00", "Usman Ghani"),
]


def seed_schedule():
    print("\n--- 8. Timetable (Course Schedule) ---")

    groups = sorted({s["group"] for f in FAMILIES for s in f["students"]})
    days = TERM_DAYS[:5]

    for group in groups:

        # Jis class ka timetable pehle se bana hua hai us ko haath
        # na lagayein - ERPNext ek hi waqt par do period nahi
        # banane deta (OverlapError), aur zaroorat bhi nahi.
        if find("Course Schedule", {"student_group": group}):
            log("=", f"{group} ka timetable pehle se mojood")
            continue

        made = 0
        for day in days:
            iso = day.isoformat()
            for course, start, end, teacher in PERIODS:

                if find("Course Schedule",
                        {"student_group": group, "course": course,
                         "schedule_date": iso}):
                    continue

                if CHECK_ONLY:
                    continue

                r = client.post(
                    f"{BASE}/api/resource/Course Schedule",
                    json={
                        "student_group": group,
                        "program": PROGRAM,
                        "course": course,
                        "instructor": teacher,
                        "instructor_name": teacher,
                        "schedule_date": iso,
                        "from_time": start,
                        "to_time": end,
                        "title": f"{course} by {teacher}",
                        "room": ROOMS.get(group, "HTL-ROOM-2026-00002"),
                    },
                )
                if r.status_code in (200, 201):
                    made += 1
                else:
                    log("!", f"schedule {group} {course} {iso}",
                        f"HTTP {r.status_code} {r.text[:110]}")
                    break

        if made:
            log("+", f"{group}: {made} periods",
                f"({len(days)} din x {len(PERIODS)} subject)")
        else:
            log("=", f"{group} ka timetable pehle se")


# =========================================================
# 9. FEE / PAYMENT  (Sales Invoice)
# =========================================================

def seed_fees():
    print("\n--- 9. Fee bills (Sales Invoice) ---")

    for family in FAMILIES:
        for s in family["students"]:
            sid = s.get("id")
            if not sid or CHECK_ONLY:
                continue

            if find("Sales Invoice", {"student": sid}):
                log("=", f"fee bill {s['first_name']}")
                continue

            r = client.post(
                f"{BASE}/api/resource/Sales Invoice",
                json={
                    "customer": s["first_name"],
                    "student": sid,
                    "company": COMPANY,
                    "currency": "PKR",
                    # Is ke baghair ERPNext posting_date nazarandaz
                    # kar ke AAJ ki tareekh lagata hai, aur phir
                    # due_date us se pehle ho jati hai:
                    #   "Due Date cannot be before Posting Date"
                    "set_posting_time": 1,
                    "posting_date": "2026-08-02",
                    "due_date": "2026-08-10",
                    "items": [
                        {
                            "item_code": FEE_ITEM,
                            "qty": 1,
                            "rate": 5000,
                            "income_account": INCOME_ACCOUNT,
                            "cost_center": COST_CENTER,
                        }
                    ],
                },
            )

            if r.status_code not in (200, 201):
                log("!", f"fee bill {s['first_name']}",
                    f"HTTP {r.status_code} {r.text[:170]}")
                continue

            inv = r.json()["data"]["name"]

            sub = client.put(
                f"{BASE}/api/resource/Sales Invoice/{inv}",
                json={"docstatus": 1},
            )
            if sub.status_code not in (200, 201):
                log("!", f"fee bill {s['first_name']} (submit)",
                    f"HTTP {sub.status_code} {sub.text[:130]}")
                continue

            state = "baqi hai" if not s["fee_paid"] else "bhari hui (payment banegi)"
            log("+", f"fee bill {s['first_name']}", f"{inv}  5000 PKR - {state}")

            s["invoice"] = inv


def seed_payments():
    """Jin ki fee 'paid' honi chahiye, un ka payment banayein."""
    print("\n--- 10. Payments ---")

    for family in FAMILIES:
        for s in family["students"]:
            if CHECK_ONLY or not s.get("invoice") or not s["fee_paid"]:
                continue

            r = client.post(
                f"{BASE}/api/method/erpnext.accounts.doctype.payment_entry"
                f".payment_entry.get_payment_entry",
                json={"dt": "Sales Invoice", "dn": s["invoice"]},
            )
            if r.status_code != 200:
                log("!", f"payment {s['first_name']}",
                    f"HTTP {r.status_code} {r.text[:130]}")
                continue

            pe = r.json()["message"]
            pe["reference_no"] = f"FEE-{s['first_name'].split()[0].upper()}"
            pe["reference_date"] = "2026-08-08"
            pe["posting_date"] = "2026-08-08"

            c = client.post(f"{BASE}/api/resource/Payment Entry", json=pe)
            if c.status_code not in (200, 201):
                log("!", f"payment {s['first_name']}",
                    f"HTTP {c.status_code} {c.text[:130]}")
                continue

            name = c.json()["data"]["name"]
            sub = client.put(
                f"{BASE}/api/resource/Payment Entry/{name}",
                json={"docstatus": 1},
            )
            if sub.status_code in (200, 201):
                log("+", f"payment {s['first_name']}", f"{name}  5000 PKR")
            else:
                log("!", f"payment {s['first_name']} (submit)",
                    f"HTTP {sub.status_code} {sub.text[:130]}")


# =========================================================

def main():
    print("=" * 76)
    print("ERPNEXT TEST DATA" + ("  (sirf dekh rahe hain)" if CHECK_ONLY else ""))
    print("=" * 76)

    seed_people()
    seed_customers()
    seed_enrollment()
    seed_groups()
    seed_attendance()
    plans = seed_exams()
    seed_results(plans)
    seed_schedule()
    seed_fees()
    seed_payments()

    print("\n" + "=" * 76)
    print(f"  naye: {len(created)}   pehle se: {len(skipped)}   nakaam: {len(failed)}")
    if failed:
        print("\n  NAKAAM:")
        for x in failed[:12]:
            print(f"    - {x}")
    print("=" * 76)


main()
