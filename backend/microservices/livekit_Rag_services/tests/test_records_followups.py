"""
Narrowed answers about a child's records, and the questions Vocira asks
back (services/integrations/followups.py, services/agent/brain.py):

    attendance  which month - asked when the records span more than one;
                one day ("aaj", "17 September")
    results     which exam - asked when there is more than one; an exam's
                overall result, strongest and weakest subject, the exam
                before; one subject in detail; every subject
    replies     "September", "mid term", "اردو", "haan", "nahi" to what
                Vocira asked
    sharing     a school sharing only the overall result (or only the
                marks) never has the other worked out
    brain       the question back is kept per call, and the reply answers it

No services are needed: the records and the answer model are stand-ins.

Run:
    uv run --no-sync --project backend/microservices/livekit_Rag_services \
        pytest backend/microservices/livekit_Rag_services/tests/test_records_followups.py -v
"""

import json
import uuid
from datetime import date
from types import SimpleNamespace

import pytest

from backend.microservices.livekit_Rag_services.services.erp_services.compact import compact_records
from backend.microservices.livekit_Rag_services.services.erp_services.records_base import _limit_assessment
from backend.microservices.livekit_Rag_services.services.groq import human_text, intent_prompt
from backend.microservices.livekit_Rag_services.services.integrations import followups

TODAY = date(2026, 10, 5)


def _attendance(name, days):
    return [{"student": "S-1", "student_name": name, "date": d, "status": s, "student_group": "Grade 5-A"}
            for d, s in days]


AHMED_DAYS = (
    [(f"2026-09-{d:02d}", "Present") for d in (1, 2, 3, 4, 7, 8, 10, 11)]
    + [("2026-09-09", "Absent"), ("2026-09-17", "Absent")]
    + [("2026-10-01", "Present"), ("2026-10-02", "Present"), ("2026-10-05", "Present")]
)


def _result(name, exam, subject, marks, total=100, grade=None):
    row = {"student": "S-1", "student_name": name, "assessment_group": exam, "course": subject,
           "total_score": marks, "maximum_score": total, "academic_year": "2026-27"}
    if grade:
        row["grade"] = grade
    return row


AHMED_RESULTS = [
    _result("Ahmed Khan", "First Term 2026", "English", 70),
    _result("Ahmed Khan", "First Term 2026", "Urdu", 70),
    _result("Ahmed Khan", "First Term 2026", "Mathematics", 80),
    _result("Ahmed Khan", "Mid Term 2026", "English", 85, grade="A"),
    _result("Ahmed Khan", "Mid Term 2026", "Urdu", 61, grade="C"),
    _result("Ahmed Khan", "Mid Term 2026", "Mathematics", 92, grade="A+"),
]


def attendance_data(days=AHMED_DAYS, name="Ahmed Khan"):
    return compact_records("attendance", {"data": _attendance(name, days)})


def results_data(rows=AHMED_RESULTS):
    return compact_records("assessment", {"data": [dict(r) for r in rows]})


# =========================================================
# Months, days, exams and subjects as parents say them
# =========================================================

@pytest.mark.parametrize("said, month", [
    ("September", "2026-09"),
    ("Ahmed ki September ki attendance", "2026-09"),
    ("ستمبر کی حاضری", "2026-09"),
    ("sitambar", "2026-09"),
    ("is mahine ki attendance", "2026-10"),
    ("اس مہینے کی حاضری", "2026-10"),
    ("pichle mahine", "2026-09"),
    ("last month please", "2026-09"),
    ("December", "2025-12"),          # not yet this year - the last one
    ("poore saal ki attendance", "all"),
    ("2026-08", "2026-08"),
])
def test_months_said_in_english_urdu_and_roman_urdu(said, month):
    assert followups.month_said(said, TODAY) == month


def test_may_as_a_word_is_not_the_month_may():
    assert followups.month_said("may I know Ahmed's attendance", TODAY) is None
    assert followups.month_said("mai Ahmed ki attendance poochna chahta hoon", TODAY) is None
    assert followups.month_said("May", TODAY, short_reply=True) == "2026-05"


def test_a_month_with_records_wins_over_this_year():
    assert followups.month_said("December", TODAY, available=["2026-10", "2025-12"]) == "2025-12"


@pytest.mark.parametrize("said, day", [
    ("aaj school aaya?", "2026-10-05"),
    ("was he present today", "2026-10-05"),
    ("kal aaya tha?", "2026-10-04"),
    ("17 September ko", "2026-09-17"),
    ("September 9th", "2026-09-09"),
    ("ستمبر 17", "2026-09-17"),
])
def test_one_day_said(said, day):
    assert followups.day_said(said, TODAY) == day


@pytest.mark.parametrize("said, subject", [
    ("maths", "Mathematics"), ("ریاضی", "Mathematics"), ("Urdu", "Urdu"), ("اردو", "Urdu"),
    ("angrezi", "English"), ("انگلش", "English"), ("english mein kitne marks", "English"),
])
def test_subjects_as_parents_say_them(said, subject):
    assert followups.option_said(said, ["English", "Urdu", "Mathematics"]) == subject


def test_exams_told_apart_by_what_differs():
    exams = ["Mid Term 2026", "First Term 2026"]
    assert followups.option_said("mid term", exams) == "Mid Term 2026"
    assert followups.option_said("midterm ka result", exams) == "Mid Term 2026"
    assert followups.option_said("مڈ ٹرم", exams) == "Mid Term 2026"
    assert followups.option_said("term", exams) is None               # names neither
    assert followups.option_said("pehla", exams, short_reply=True) == "First Term 2026"
    # "pehle bache ka result" - the first CHILD, not the first exam; "fir" is "then"
    assert followups.option_said("pehle bache ka result", exams) is None
    assert followups.option_said("fir Ahmed ka result batao", exams) is None


def test_the_exact_name_picks_one_of_two_alike():
    assert followups.option_said("Mid Term 2025", ["Mid Term 2026", "Mid Term 2025"]) == "Mid Term 2025"


def test_exams_ordered_latest_first():
    rows = AHMED_RESULTS + [_result("Ahmed Khan", "Final 2026", "Urdu", 75), _result("Ahmed Khan", "Final 2025", "Urdu", 50)]
    assert followups.exams_newest_first(rows) == ["Final 2026", "Mid Term 2026", "First Term 2026", "Final 2025"]


# =========================================================
# Attendance
# =========================================================

def test_records_keep_their_rows_for_the_agent_only():
    data = attendance_data()
    assert len(data["_rows"]) == len(AHMED_DAYS)
    prompt = human_text.build_response_prompt("attendance?", data, language="en", school_name="Test School")
    assert "_rows" not in prompt and "2026-09-03" not in prompt  # a present day is only in the rows


def test_attendance_over_two_months_asks_which_month():
    found = followups.focus("attendance", attendance_data(), {"resource": "attendance"}, "Ahmed ki attendance", TODAY)
    assert found.ask == {"what": "month", "options": ["2026-10", "2026-09"], "labels": ["October 2026", "September 2026"]}
    assert found.student == "Ahmed Khan"
    assert "_ask" in found.data and "data" not in found.data and "_rows" not in found.data


def test_the_month_said_gets_that_months_figures():
    found = followups.focus("attendance", attendance_data(), {"resource": "attendance", "month": "2026-09"}, "x", TODAY)
    assert found.ask is None
    assert found.data["month"] == "September 2026"
    [entry] = found.data["data"]
    assert entry["total_days_recorded"] == 10
    assert entry["present_days"] == 8 and entry["absent_days"] == 2
    assert entry["attendance_percentage"] == 80
    assert entry["absent_dates"] == ["2026-09-09", "2026-09-17"]


def test_a_month_in_the_question_is_read_even_when_the_router_missed_it():
    found = followups.focus("attendance", attendance_data(), {"resource": "attendance"}, "ستمبر کی حاضری", TODAY)
    assert found.ask is None and found.data["month"] == "September 2026"


def test_one_day():
    absent = followups.focus("attendance", attendance_data(), {"resource": "attendance", "date": "2026-09-17"}, "x", TODAY)
    assert absent.data["day"] == "17 September 2026" and absent.data["data"][0]["absent_days"] == 1
    today = followups.focus("attendance", attendance_data(), {"resource": "attendance"}, "aaj school gaya?", TODAY)
    assert today.data["day"] == "5 October 2026" and today.data["data"][0]["present_days"] == 1


def test_a_day_without_attendance_says_so_and_the_last_day_recorded():
    found = followups.focus("attendance", attendance_data(), {"resource": "attendance", "date": "2026-10-04"}, "x", TODAY)
    assert "No attendance was recorded for 4 October 2026" in found.data["_note"]
    assert "5 October 2026" in found.data["_note"]


def test_a_month_without_records_names_the_months_there_are():
    found = followups.focus("attendance", attendance_data(), {"resource": "attendance", "month": "2026-07"}, "x", TODAY)
    assert found.data["data"] == [] and "October 2026, September 2026" in found.data["_note"]


def test_one_month_of_records_is_answered_without_asking():
    only_october = [d for d in AHMED_DAYS if d[0].startswith("2026-10")]
    found = followups.focus("attendance", attendance_data(only_october), {"resource": "attendance"}, "attendance?", TODAY)
    assert found.ask is None and found.data["month"] == "October 2026"


def test_a_compound_question_is_never_asked_back():
    found = followups.focus("attendance", attendance_data(), {"resource": "attendance"}, "attendance and fee", TODAY,
                            may_ask=False)
    assert found.ask is None and found.data["data"][0]["total_days_recorded"] == len(AHMED_DAYS)


def test_an_attendance_summary_without_days_is_answered_as_it_is():
    summary = {"data": [{"student_name": "Ahmed Khan", "attendance_percentage": 91}], "_about": "Attendance"}
    assert followups.focus("attendance", summary, {"resource": "attendance"}, "attendance?", TODAY).data is summary


# =========================================================
# Results
# =========================================================

def test_two_exams_ask_which_exam_latest_first():
    found = followups.focus("assessment", results_data(), {"resource": "assessment"}, "Ahmed ke marks", TODAY)
    assert found.ask["what"] == "exam" and found.ask["options"] == ["Mid Term 2026", "First Term 2026"]
    assert "_ask" in found.data


def test_an_exam_gives_overall_strongest_weakest_and_the_exam_before():
    found = followups.focus("assessment", results_data(), {"resource": "assessment", "exam": "mid term"}, "x", TODAY)
    [entry] = found.data["data"]
    assert entry["exam"] == "Mid Term 2026"
    assert entry["overall_result"] == {"obtained_marks": 238, "total_marks": 300, "overall_percentage": 79.3, "subjects": 3}
    assert entry["strongest_subject"]["subject"] == "Mathematics" and entry["strongest_subject"]["obtained_marks"] == 92
    assert entry["weakest_subject"]["subject"] == "Urdu" and entry["weakest_subject"]["grade"] == "C"
    assert entry["previous_exam"] == {"exam": "First Term 2026", "overall_percentage": 73.3}
    assert entry["change_in_percentage_points"] == 6
    assert "all_subjects" not in entry and "records" not in entry          # not every subject at once
    assert found.offer == {"what": "subject", "options": ["English", "Urdu", "Mathematics"],
                           "labels": ["English", "Urdu", "Mathematics"], "exam": "Mid Term 2026"}
    assert "_end_with" in found.data


def test_one_subject_in_detail_with_the_exam_before():
    found = followups.focus("assessment", results_data(),
                            {"resource": "assessment", "exam": "Mid Term 2026", "subject": "Urdu"}, "x", TODAY)
    [entry] = found.data["data"]
    assert entry["subject_result"] == {"subject": "Urdu", "obtained_marks": 61, "total_marks": 100, "percentage": 61, "grade": "C"}
    assert entry["previous_exam"] == {"exam": "First Term 2026", "obtained_marks": 70, "total_marks": 100, "percentage": 70}
    assert entry["change_in_percentage_points"] == -9
    assert found.offer["what"] == "subject"


def test_a_subject_asked_with_two_exams_asks_the_exam_and_keeps_the_subject():
    found = followups.focus("assessment", results_data(), {"resource": "assessment", "subject": "Urdu"}, "x", TODAY)
    assert found.ask["what"] == "exam" and found.ask["subject"] == "Urdu"


def test_every_subject_when_asked_for_all():
    found = followups.focus("assessment", results_data(),
                            {"resource": "assessment", "exam": "mid term", "subject": "all"}, "x", TODAY)
    [entry] = found.data["data"]
    assert [s["subject"] for s in entry["all_subjects"]] == ["Mathematics", "English", "Urdu"]


def test_a_subject_not_taken_names_the_ones_there_are():
    found = followups.focus("assessment", results_data(),
                            {"resource": "assessment", "exam": "mid term", "subject": "Physics"}, "x", TODAY)
    assert found.data["data"] == [] and "English, Urdu, Mathematics" in found.data["_note"]


def test_one_exam_is_answered_without_asking():
    found = followups.focus("assessment", results_data(AHMED_RESULTS[3:]), {"resource": "assessment"}, "marks?", TODAY)
    assert found.ask is None and found.data["data"][0]["exam"] == "Mid Term 2026"


def test_two_children_are_answered_together_with_no_offer():
    rows = AHMED_RESULTS[3:] + [_result("Sara Khan", "Mid Term 2026", "Urdu", 88), _result("Sara Khan", "Mid Term 2026", "English", 77)]
    found = followups.focus("assessment", results_data(rows), {"resource": "assessment"}, "results", TODAY)
    assert {e["student_name"] for e in found.data["data"]} == {"Ahmed Khan", "Sara Khan"}
    assert found.offer is None and found.student is None


# =========================================================
# What the school shares
# =========================================================

def test_only_the_overall_result_shared_offers_no_subject():
    shared = _limit_assessment(results_data(), {"results"})
    assert "_rows" not in shared
    found = followups.focus("assessment", shared, {"resource": "assessment", "exam": "mid term"}, "x", TODAY)
    assert found.data is shared and found.offer is None


def test_only_the_marks_shared_never_works_out_an_overall_result():
    shared = _limit_assessment(results_data(), {"marks"})
    found = followups.focus("assessment", shared, {"resource": "assessment", "exam": "mid term"}, "x", TODAY)
    [entry] = found.data["data"]
    assert "overall_result" not in entry and "previous_exam" not in entry
    assert entry["strongest_subject"]["subject"] == "Mathematics"


# =========================================================
# The parent's reply
# =========================================================

MONTH_ASKED = {"what": "month", "options": ["2026-10", "2026-09"], "labels": ["October 2026", "September 2026"]}
EXAM_ASKED = {"what": "exam", "options": ["Mid Term 2026", "First Term 2026"], "labels": ["Mid Term 2026", "First Term 2026"]}
SUBJECT_OFFERED = {"what": "subject", "options": ["English", "Urdu", "Mathematics"], "exam": "Mid Term 2026"}


@pytest.mark.parametrize("pending, reply, slots", [
    (MONTH_ASKED, "September", {"month": "2026-09"}),
    (MONTH_ASKED, "ستمبر", {"month": "2026-09"}),
    (MONTH_ASKED, "is mahine ki", {"month": "2026-10"}),
    (MONTH_ASKED, "aaj ki", {"date": "2026-10-05"}),
    (MONTH_ASKED, "nahi, September", {"month": "2026-09"}),
    (EXAM_ASKED, "mid term", {"exam": "Mid Term 2026"}),
    (EXAM_ASKED, "پہلا", {"exam": "First Term 2026"}),
    (EXAM_ASKED, "aakhri wala", {"exam": "Mid Term 2026"}),
    (EXAM_ASKED, "sab", {"exam": "all"}),
    ({**EXAM_ASKED, "subject": "Urdu"}, "mid term", {"exam": "Mid Term 2026", "subject": "Urdu"}),
    (SUBJECT_OFFERED, "Urdu", {"exam": "Mid Term 2026", "subject": "Urdu"}),
    (SUBJECT_OFFERED, "اردو کے", {"exam": "Mid Term 2026", "subject": "Urdu"}),
    (SUBJECT_OFFERED, "haan", {"exam": "Mid Term 2026", "subject": "?"}),
    (SUBJECT_OFFERED, "sab subjects", {"exam": "Mid Term 2026", "subject": "all"}),
])
def test_replies_answer_what_was_asked(pending, reply, slots):
    assert followups.answer_to(pending, reply, TODAY) == (slots, False)


@pytest.mark.parametrize("pending, reply, declined", [
    (SUBJECT_OFFERED, "nahi shukriya", True),
    (MONTH_ASKED, "bas", True),
    (SUBJECT_OFFERED, "okay", False),                       # "fine" - not "go on", not "no"
    (SUBJECT_OFFERED, "fee kitni reh gayi hai?", False),    # something else - the router decides
])
def test_replies_that_answer_nothing(pending, reply, declined):
    assert followups.answer_to(pending, reply, TODAY) == (None, declined)


def test_yes_to_the_offer_asks_which_subject():
    found = followups.focus("assessment", results_data(),
                            {"resource": "assessment", "exam": "Mid Term 2026", "subject": "?"}, "haan", TODAY)
    assert found.ask == {"what": "subject", "options": ["English", "Urdu", "Mathematics"],
                         "labels": ["English", "Urdu", "Mathematics"], "exam": "Mid Term 2026"}


# =========================================================
# The router's prompt
# =========================================================

def test_the_router_is_told_today_and_what_vocira_asked():
    prompt = intent_prompt.build_router_prompt("September", children=["Ahmed Khan"], today=TODAY,
                                               asked=followups.describe({**MONTH_ASKED, "student": "Ahmed Khan"}))
    assert "Today's date: 2026-10-05" in prompt
    assert "Vocira just asked the caller which month of Ahmed Khan's attendance they want (October 2026, September 2026)." in prompt


# =========================================================
# The brain: the question back is kept, and the reply answers it
# =========================================================

@pytest.fixture
def brain(monkeypatch):
    from backend.microservices.livekit_Rag_services.services.agent import brain as module

    prompts = []

    async def fake_llm(prompt, **kwargs):
        prompts.append(prompt)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="Theek hai."), finish_reason="stop")])

    async def fake_user(vocira_user_id):
        return {"user_id": str(vocira_user_id), "role": "guardian", "parent_id": "G-1"}

    lookups = []

    async def fake_lookup(school, resource, guardian_id, student_name=None, session_id=None):
        lookups.append((resource, student_name))
        return attendance_data() if resource == "attendance" else results_data()

    monkeypatch.setattr(module, "_llm", fake_llm)
    monkeypatch.setattr(module.pipeline.auth_client, "get_internal_user", fake_user)
    monkeypatch.setattr(module.records_tools, "lookup", fake_lookup)
    module._pending.clear()
    yield SimpleNamespace(module=module, prompts=prompts, lookups=lookups)
    module._pending.clear()


def _call(brain):
    return brain.module.Call(session_id=uuid.uuid4(), user_id=uuid.uuid4(), user_type="user",
                             school=SimpleNamespace(name="Test School", id="test"), language="en")


@pytest.mark.asyncio
async def test_brain_asks_the_month_then_answers_the_reply(brain):
    call = _call(brain)
    await brain.module._records_answer(call, None, [{"resource": "attendance", "student": None}], "Ahmed ki attendance")
    pending = brain.module.pending_for(call.session_id)
    assert pending["what"] == "month" and pending["student"] == "Ahmed Khan" and pending["resource"] == "attendance"
    assert "'_ask'" in brain.prompts[-1]

    slots, declined = followups.answer_to(pending, "September")
    items = [{"resource": pending["resource"], "student": pending["student"], **slots}]
    await brain.module._records_answer(call, None, items, "September")
    assert brain.lookups[-1] == ("attendance", "Ahmed Khan")              # the same child
    assert "September 2026" in brain.prompts[-1] and "'absent_days': 2" in brain.prompts[-1]
    assert brain.module.pending_for(call.session_id) is None               # nothing left to ask


@pytest.mark.asyncio
async def test_brain_offers_a_subject_after_an_exam_and_answers_it(brain):
    call = _call(brain)
    await brain.module._records_answer(call, None, [{"resource": "assessment", "student": None, "exam": "mid term"}],
                                       "mid term ke marks")
    pending = brain.module.pending_for(call.session_id)
    assert pending["what"] == "subject" and pending["exam"] == "Mid Term 2026"
    assert "_end_with" in brain.prompts[-1]

    slots, _ = followups.answer_to(pending, "Urdu")
    await brain.module._records_answer(call, None, [{"resource": "assessment", "student": pending["student"], **slots}], "Urdu")
    sent = brain.prompts[-1]
    assert "'subject_result'" in sent and "'change_in_percentage_points': -9" in sent


@pytest.mark.asyncio
async def test_brain_never_asks_back_on_a_compound_question(brain):
    call = _call(brain)
    await brain.module._records_answer(call, None, [{"resource": "attendance", "student": None},
                                                    {"resource": "assessment", "student": None}], "attendance and marks")
    assert brain.module.pending_for(call.session_id) is None


def test_router_details_reach_the_items():
    from backend.microservices.livekit_Rag_services.services.agent import brain as module

    items = module._erp_items({"intent": "ERP", "items": [
        {"resource": "assessment", "student": "Ahmed", "exam": "mid term", "subject": "Urdu", "month": ""}]})
    assert items == [{"resource": "assessment", "student": "Ahmed", "exam": "mid term", "subject": "Urdu"}]


def test_what_was_asked_is_forgotten_after_a_while(monkeypatch):
    from backend.microservices.livekit_Rag_services.services.agent import brain as module

    clock = [1000.0]
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])
    module._set_pending("s-1", {"what": "month"})
    assert module.pending_for("s-1") == {"what": "month"}
    clock[0] += module.PENDING_SECONDS + 1
    assert module.pending_for("s-1") is None


@pytest.mark.parametrize("written, spoken_order", [
    ("مجموعی نتیجہ 238 میں سے 300 نمبر", "300 میں سے 238"),     # the English way round - turned
    ("22 میں سے 20 دن حاضر", "22 میں سے 20"),                    # already right - left alone
    ("۶۱ میں سے ۱۰۰", "100 میں سے 61"),                          # Urdu digits too
])
def test_urdu_out_of_says_the_total_first(written, spoken_order):
    from backend.microservices.livekit_Rag_services.services.groq import spoken_text

    first, second = spoken_order.split(" میں سے ")
    expected = f"{spoken_text.urdu_number(int(first))} میں سے {spoken_text.urdu_number(int(second))}"
    assert expected in spoken_text.speak_numbers(written, "ur")


@pytest.mark.parametrize("written, said", [
    ("92 فیصد اور A+ گریڈ حاصل ہوا", "اے پلس گریڈ"),
    ("اس کا گریڈ C ہے", "گریڈ سی ہے"),
    ("گریڈ B- ملا", "گریڈ بی مائنس"),
    ("جماعت 5-A میں", "5-A"),          # a class, not a grade - left alone
])
def test_urdu_grades_are_written_as_said(written, said):
    from backend.microservices.livekit_Rag_services.services.groq import spoken_text

    assert said in spoken_text.speak_grades(written, "ur")
    assert spoken_text.speak_grades(written, "en") == written
