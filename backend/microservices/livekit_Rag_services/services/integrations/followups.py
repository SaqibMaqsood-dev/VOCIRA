"""
A child's records narrowed to what the parent asked - and what to ask back
when they did not say.

    attendance  which month ("September", "is mahine", "پچھلے مہینے") or which
                day ("aaj", "15 September"). Records in more than one month
                and no month said: the parent is asked which month.
    results     which exam, then which subject. More than one exam and none
                said: the parent is asked which. An exam's answer is its
                overall result with the strongest and the weakest subject,
                and an offer to go into one subject; a subject's answer has
                its grade and how it went in the exam before.

The figures come from the rows behind compact_records' summaries ("_rows")
and are worked out here; the answer model only says them. A school that
shares only the overall result has no rows here (records_base
._limit_assessment), so nothing per subject is offered; a system that gives
only an attendance summary (Open School MIS) is answered as before.

The agent (services/agent/brain.py) keeps what was asked, so the parent's
one-word reply - "September", "Urdu" - is matched here by answer_to().
"""

import re
from dataclasses import dataclass
from datetime import date, timedelta

from backend.microservices.livekit_Rag_services.services.erp_services.compact import (
    _percent,
    _plain_number,
    attendance_summary,
    results_summary,
)


@dataclass
class Focused:
    """What the answer model is given, and what Vocira asks or offers next."""

    data: dict
    # Vocira asks this before answering: {"what": "month" | "exam" | "subject",
    # "options": [...], "labels": [...]} - plus "exam" / "subject" already known
    ask: dict | None = None
    # the next step offered after the answer (same shape) - "Urdu" then answers it
    offer: dict | None = None
    # the one child it is about, as the records name them (None: several)
    student: str | None = None


# ---------------------------------------------------------
# Words
# ---------------------------------------------------------

_PUNCTUATION = re.compile(r"[^\w\s-]|_", re.UNICODE)


def _norm(text) -> str:
    return " ".join(_PUNCTUATION.sub(" ", str(text or "").lower()).split())


def _words(text) -> list[str]:
    return _norm(text).split()


def _has_phrase(text: str, phrases) -> bool:
    padded = f" {text} "
    return any(f" {p} " in padded for p in phrases)


_MONTH_WORDS = {
    1: ("january", "jan", "janwari", "januari", "جنوری"),
    2: ("february", "feb", "farwari", "fabruary", "febuary", "فروری"),
    3: ("march", "mar", "maarch", "مارچ"),
    4: ("april", "apr", "aprail", "aprel", "اپریل"),
    5: ("may", "mai", "mayi", "مئی", "مئ"),
    6: ("june", "jun", "joon", "جون"),
    7: ("july", "jul", "julai", "jolai", "جولائی", "جولائ"),
    8: ("august", "aug", "agast", "agust", "اگست"),
    9: ("september", "sep", "sept", "sitambar", "stambar", "septembar", "ستمبر"),
    10: ("october", "oct", "aktubar", "oktobar", "aktobar", "اکتوبر"),
    11: ("november", "nov", "navambar", "nawambar", "novembar", "نومبر"),
    12: ("december", "dec", "disambar", "dasambar", "decembar", "دسمبر"),
}
_MONTH_OF = {word: number for number, words in _MONTH_WORDS.items() for word in words}

# Month names that are everyday words too ("may I know", Roman Urdu "mai" -
# "I"): counted only in a reply of a few words ("May." to "which month?").
_EVERYDAY = {"may", "mai", "mar", "jan"}

_MONTH_NAMES = ("January", "February", "March", "April", "May", "June", "July",
                "August", "September", "October", "November", "December")

_THIS_MONTH = ("this month", "current month", "is mahine", "is mahinay", "is maheene", "iss mahine",
               "is month", "اس مہینے", "اس مہینہ", "اس ماہ", "رواں ماہ", "رواں مہینے")
_LAST_MONTH = ("last month", "previous month", "pichle mahine", "pichhle mahine", "pichlay mahinay",
               "pichle mahinay", "pichla mahina", "guzishta mahine", "پچھلے مہینے", "پچھلا مہینہ",
               "گزشتہ ماہ", "گذشتہ ماہ", "پچھلے ماہ", "گزشتہ مہینے")
_WHOLE_YEAR = ("whole year", "full year", "entire year", "overall", "all months", "every month",
               "poore saal", "pure saal", "poora saal", "pura saal", "sare mahine", "saare mahine",
               "sab mahine", "kul", "پورے سال", "پورا سال", "مجموعی", "تمام مہینوں", "سارے مہینے",
               "سب مہینے")
_TODAY = ("today", "aaj", "aj", "آج")
_YESTERDAY = ("yesterday", "kal", "گزشتہ روز")


def month_label(month: str) -> str:
    """'2026-09' -> 'September 2026'."""
    try:
        year, number = month.split("-")[:2]
        return f"{_MONTH_NAMES[int(number) - 1]} {int(year)}"
    except (ValueError, IndexError):
        return month


def day_label(day: str) -> str:
    """'2026-10-05' -> '5 October 2026'."""
    try:
        d = date.fromisoformat(day[:10])
        return f"{d.day} {_MONTH_NAMES[d.month - 1]} {d.year}"
    except ValueError:
        return day


def _year_for(number: int, today: date, available=()) -> str:
    """A month named without a year: the latest one with records, else the latest one so far."""
    for month in sorted(available, reverse=True):
        if month[5:7] == f"{number:02d}":
            return month
    year = today.year if number <= today.month else today.year - 1
    return f"{year}-{number:02d}"


def _months_named(words: list[str], short: bool) -> list[int]:
    return [_MONTH_OF[w] for w in words if w in _MONTH_OF and (short or w not in _EVERYDAY)]


def month_said(text, today: date, available=(), short_reply: bool = False) -> str | None:
    """The month a question or reply names: 'YYYY-MM', 'all' (the whole year), or None."""
    norm = _norm(text)
    if re.fullmatch(r"\d{4}-\d{2}", norm.strip()):
        return norm.strip()
    if _has_phrase(norm, _WHOLE_YEAR):
        return "all"
    if _has_phrase(norm, _THIS_MONTH):
        return f"{today.year}-{today.month:02d}"
    if _has_phrase(norm, _LAST_MONTH):
        first = today.replace(day=1) - timedelta(days=1)
        return f"{first.year}-{first.month:02d}"
    named = _months_named(norm.split(), short_reply)
    if len(set(named)) == 1:
        return _year_for(named[0], today, available)
    return None


def day_said(text, today: date) -> str | None:
    """One day a question names: today, yesterday, or '15 September' -> 'YYYY-MM-DD'."""
    norm = _norm(text)
    words = norm.split()
    for i, word in enumerate(words):
        number = _MONTH_OF.get(word)
        if number is None or word in _EVERYDAY:
            continue
        for neighbour in (words[i - 1] if i else "", words[i + 1] if i + 1 < len(words) else ""):
            digits = re.sub(r"(st|nd|rd|th)$", "", neighbour)
            if digits.isdigit() and 1 <= int(digits) <= 31:
                year = int(_year_for(number, today)[:4])
                try:
                    return date(year, number, int(digits)).isoformat()
                except ValueError:
                    return None
    if _has_phrase(norm, _TODAY):
        return today.isoformat()
    if _has_phrase(norm, _YESTERDAY):
        return (today - timedelta(days=1)).isoformat()
    return None


# Subjects and exams as parents say them -> the words school records use
_PHRASE_ALIASES = {
    "مطالعہ پاکستان": "pakistan studies", "pak studies": "pakistan studies",
    "معاشرتی علوم": "social studies", "general knowledge": "general knowledge",
    "computer science": "computer", "midterm": "mid term",
}
_WORD_ALIASES = {
    "maths": "mathematics", "math": "mathematics", "riyazi": "mathematics", "ریاضی": "mathematics",
    "حساب": "mathematics", "hisab": "mathematics",
    "angrezi": "english", "انگریزی": "english", "انگلش": "english", "inglish": "english",
    "اردو": "urdu",
    "سائنس": "science", "saains": "science", "sains": "science",
    "islamiyat": "islamiat", "islamiyaat": "islamiat", "اسلامیات": "islamiat",
    "sst": "social", "معاشرتی": "social", "muashrati": "social",
    "کمپیوٹر": "computer", "computing": "computer",
    "فزکس": "physics", "کیمسٹری": "chemistry", "بیالوجی": "biology", "بائیولوجی": "biology",
    "عربی": "arabic", "ڈرائنگ": "drawing", "آرٹ": "art", "pak": "pakistan",
    "مڈ": "mid", "وسط": "mid",
    "فائنل": "final", "annual": "final", "سالانہ": "final", "salana": "final",
    "ماہانہ": "monthly", "ٹیسٹ": "test", "ٹرم": "term",
}
# Ordinals mean "the first exam" only as a reply to "which exam?" - in a
# question "pehle bache" is the first CHILD.
_ORDINALS = {
    "pehla": "first", "pehli": "first", "پہلا": "first", "پہلی": "first", "1st": "first",
    "doosra": "second", "dusra": "second", "doosri": "second", "dusri": "second", "دوسرا": "second",
    "دوسری": "second", "2nd": "second", "teesra": "third", "teesri": "third", "تیسرا": "third",
    "تیسری": "third", "3rd": "third",
}
_ALL_WORDS = ("all", "every", "sab", "sare", "saare", "tamam", "har", "سب", "سارے", "تمام", "ہر")
_LATEST_WORDS = ("latest", "last", "recent", "akhri", "aakhri", "akhiri", "آخری", "تازہ", "نیا")
_NO_WORDS = ("no", "nahi", "nahin", "nai", "bas", "rehne do", "nope", "نہیں", "بس", "نہ")
# "okay" is not here: after an answer it means "fine", not "go on"
_YES_WORDS = ("yes", "haan", "han", "ha", "ji", "jee", "zaroor", "zarur", "sure", "ہاں", "جی", "ضرور")


def _canonical_words(text, short_reply: bool = False) -> list[str]:
    norm = _norm(text)
    for phrase, alias in _PHRASE_ALIASES.items():
        norm = f" {norm} ".replace(f" {phrase} ", f" {alias} ").strip()
    out = []
    for word in norm.split():
        word = _WORD_ALIASES.get(word, word)
        if short_reply:
            word = _ORDINALS.get(word, word)
        out.extend(word.split())
    return out


def _keywords(option: str) -> set[str]:
    return {w for w in _canonical_words(option) if not w.isdigit() and w not in ("exam", "examination", "result", "results")}


def _hits(keyword: str, words: list[str]) -> bool:
    # a cut-short word counts from four letters ("engl", "scie") - at three,
    # Roman Urdu "fir" (then) read as "first"
    return any(w == keyword or (len(w) >= 4 and keyword.startswith(w)) or (len(keyword) >= 4 and w.startswith(keyword))
               for w in words)


def option_said(text, options, short_reply: bool = False) -> str | None:
    """Which one of `options` (exams, subjects) the text names - None when none, or not one clearly."""
    options = [o for o in options if o]
    if not options or not _norm(text):
        return None
    exact = [o for o in options if _norm(o) == _norm(text)]
    if len(exact) == 1:
        return exact[0]
    words = _canonical_words(text, short_reply)
    keywords = {o: _keywords(o) for o in options}
    if len(options) > 1:
        # words every option shares ("term" in "Mid Term" / "Final Term") tell none of them apart
        shared = set.intersection(*keywords.values()) if all(keywords.values()) else set()
        keywords = {o: (k - shared) or k for o, k in keywords.items()}
    scores = {o: sum(_hits(k, words) for k in ks) for o, ks in keywords.items()}
    best = max(scores.values())
    if best == 0:
        return None
    top = [o for o, s in scores.items() if s == best]
    return top[0] if len(top) == 1 else None


def _says_all(text) -> bool:
    return _has_phrase(_norm(text), _ALL_WORDS)


def _says_latest(text) -> bool:
    return _has_phrase(_norm(text), _LATEST_WORDS)


def _short(text) -> bool:
    return len(_words(text)) <= 4


# ---------------------------------------------------------
# Exams in order
# ---------------------------------------------------------

_TERM_RANK = (
    (("first", "1st", "term 1", "term i"), 1), (("monthly",), 1.5), (("mid", "half"), 2),
    (("second", "2nd", "term 2", "term ii"), 3), (("third", "3rd", "term 3"), 4),
    (("pre", "send up", "sendup", "mock"), 5), (("final", "annual"), 6),
)


def _exam_key(name: str, year: str | None, first_seen: int):
    text = f" {_norm(name)} "
    found = re.search(r"(20\d{2})", f"{name} {year or ''}")
    rank = next((r for words, r in _TERM_RANK if any(f" {w}" in text for w in words)), 3.5)
    return (int(found.group(1)) if found else 0, rank, first_seen)


def exams_newest_first(rows: list) -> list[str]:
    """The exams in the rows, the latest first (by year, then first term .. final)."""
    seen = {}
    for i, row in enumerate(rows):
        name = row.get("assessment_group") or ""
        if name not in seen:
            seen[name] = (i, row.get("academic_year"))
    return sorted(seen, key=lambda n: _exam_key(n, seen[n][1], seen[n][0]), reverse=True)


# ---------------------------------------------------------
# Attendance
# ---------------------------------------------------------

def _one_child(rows: list) -> str | None:
    names = {r.get("student_name") for r in rows if r.get("student_name")}
    return names.pop() if len(names) == 1 else None


def _valid_month(value) -> str | None:
    value = str(value or "").strip().lower()
    return value if value == "all" or re.fullmatch(r"\d{4}-\d{2}", value) else None


def _valid_day(value) -> str | None:
    value = str(value or "").strip()
    try:
        return date.fromisoformat(value[:10]).isoformat() if value else None
    except ValueError:
        return None


def _about(source: dict, **extra) -> dict:
    """The lookup's own notes ("_about", "_note"), with what is given now."""
    out = {k: v for k, v in source.items() if k in ("_about", "_note", "_tool")}
    out.update(extra)
    return out


def focus_attendance(data: dict, item: dict, question: str, today: date, may_ask: bool = True) -> Focused:
    rows = data.get("_rows")
    if not isinstance(rows, list) or not rows:
        return Focused(data)
    dated = [r for r in rows if _valid_day(r.get("date"))]
    if not dated:
        return Focused(data)
    student = _one_child(dated)
    months = sorted({r["date"][:7] for r in dated}, reverse=True)

    day = _valid_day(item.get("date")) or day_said(question, today)
    if day:
        picked = [r for r in dated if r["date"][:10] == day]
        if picked:
            return Focused(_about(data, day=day_label(day), data=attendance_summary(picked)), student=student)
        last = max(r["date"][:10] for r in dated)
        note = (f"No attendance was recorded for {day_label(day)}. "
                f"The last day with attendance recorded is {day_label(last)}.")
        latest = [r for r in dated if r["date"].startswith(last[:7])]
        return Focused(_about(data, _note=note, month=month_label(last[:7]), data=attendance_summary(latest)),
                       student=student)

    month = _valid_month(item.get("month")) or month_said(question, today, months)
    if month == "all" or (month is None and not may_ask):
        return Focused(_about(data, data=attendance_summary(dated)), student=student)
    if month:
        picked = [r for r in dated if r["date"].startswith(month)]
        if picked:
            return Focused(_about(data, month=month_label(month), data=attendance_summary(picked)), student=student)
        note = (f"No attendance was recorded in {month_label(month)}. "
                f"Months with attendance: {', '.join(month_label(m) for m in months)}.")
        return Focused(_about(data, _note=note, data=[]), student=student)
    if len(months) == 1:
        return Focused(_about(data, month=month_label(months[0]), data=attendance_summary(dated)), student=student)

    options = months[:3]
    labels = [month_label(m) for m in options]
    ask = {"what": "month", "options": options, "labels": labels}
    asking = _about(
        data,
        about_child=student or "all of the parent's children",
        months_with_attendance=labels,
        _ask=f"Ask which month's attendance they want: {', '.join(labels)} - or another month.",
    )
    asking.pop("_note", None)
    return Focused(asking, ask=ask, student=student)


# ---------------------------------------------------------
# Results
# ---------------------------------------------------------

def _subject_line(row: dict) -> dict:
    marks, total = row.get("total_score"), row.get("maximum_score")
    # named as in "overall_result", which the answer prompt's rules speak of
    line = {"subject": row.get("course") or "?", "obtained_marks": _plain_number(marks),
            "total_marks": _plain_number(total)}
    if isinstance(marks, (int, float)) and isinstance(total, (int, float)) and total > 0:
        line["percentage"] = _percent(marks, total)
    if row.get("grade"):
        line["grade"] = row["grade"]
    return {k: v for k, v in line.items() if v is not None}


def _overall(rows: list) -> dict | None:
    scored = [r for r in rows if isinstance(r.get("total_score"), (int, float))
              and isinstance(r.get("maximum_score"), (int, float)) and r["maximum_score"] > 0]
    if not scored:
        return None
    obtained = sum(r["total_score"] for r in scored)
    total = sum(r["maximum_score"] for r in scored)
    return {"obtained_marks": _plain_number(float(obtained)), "total_marks": _plain_number(float(total)),
            "overall_percentage": _percent(obtained, total), "subjects": len(scored)}


def _change(now, before):
    if now is None or before is None:
        return None
    value = round(now - before, 1)
    return int(value) if value == int(value) else value


def _subjects_of(rows: list) -> list[str]:
    seen = []
    for row in rows:
        if row.get("course") and row["course"] not in seen:
            seen.append(row["course"])
    return seen


def _by_child(rows: list) -> dict[str, list]:
    out = {}
    for row in rows:
        out.setdefault(row.get("student_name") or "?", []).append(row)
    return out


def _previous_exam(exams: list[str], exam: str, rows: list, subject: str | None = None) -> str | None:
    """The exam before `exam` with marks in it (in `subject`, when given)."""
    older = exams[exams.index(exam) + 1:] if exam in exams else []
    for name in older:
        if any((r.get("assessment_group") or "") == name and (subject is None or r.get("course") == subject)
               for r in rows):
            return name
    return None


def _exam_entry(child: str, rows: list, exams: list[str], exam: str, no_overall: bool) -> dict:
    exam_rows = [r for r in rows if (r.get("assessment_group") or "") == exam]
    entry = {"student_name": child, "exam": exam or None}
    if not no_overall:
        overall = _overall(exam_rows)
        if overall:
            entry["overall_result"] = overall
            before = _previous_exam(exams, exam, rows)
            previous = _overall([r for r in rows if (r.get("assessment_group") or "") == before]) if before else None
            if previous:
                entry["previous_exam"] = {"exam": before, "overall_percentage": previous["overall_percentage"]}
                entry["change_in_percentage_points"] = _change(overall["overall_percentage"],
                                                               previous["overall_percentage"])
    lines = [_subject_line(r) for r in exam_rows]
    scored = sorted((l for l in lines if "percentage" in l), key=lambda l: l["percentage"], reverse=True)
    if len(scored) >= 2:
        entry["strongest_subject"] = scored[0]
        entry["weakest_subject"] = scored[-1]
    elif len(lines) == 1:
        entry["subject"] = lines[0]
    return {k: v for k, v in entry.items() if v is not None}


def _subject_entry(child: str, rows: list, exams: list[str], exam: str, subject: str) -> dict:
    row = next((r for r in rows if (r.get("assessment_group") or "") == exam and r.get("course") == subject), None)
    entry = {"student_name": child, "exam": exam or None}
    if row is None:
        entry["note"] = f"No marks in {subject} for this exam."
        return {k: v for k, v in entry.items() if v is not None}
    entry["subject_result"] = _subject_line(row)
    before = _previous_exam(exams, exam, rows, subject)
    if before:
        old = next(r for r in rows if (r.get("assessment_group") or "") == before and r.get("course") == subject)
        old_line = _subject_line(old)
        entry["previous_exam"] = {"exam": before, **{k: v for k, v in old_line.items() if k != "subject"}}
        change = _change(entry["subject_result"].get("percentage"), old_line.get("percentage"))
        if change is not None:
            entry["change_in_percentage_points"] = change
    return {k: v for k, v in entry.items() if v is not None}


def focus_results(data: dict, item: dict, question: str, may_ask: bool = True) -> Focused:
    rows = data.get("_rows")
    if not isinstance(rows, list) or not rows:
        return Focused(data)
    no_overall = bool(data.get("_no_overall"))
    student = _one_child(rows)
    exams = exams_newest_first(rows)
    wanted_subject = str(item.get("subject") or "").strip()

    # which exam
    said_exam = str(item.get("exam") or "").strip()
    if said_exam.lower() == "all" or (not said_exam and _says_all(question) and "exam" in _norm(question)):
        exam = "all"
    else:
        exam = option_said(said_exam, exams) if said_exam else None
        exam = exam or option_said(question, exams)
        if exam is None and said_exam and _says_latest(said_exam):
            exam = exams[0]
    if exam is None:
        if len(exams) == 1:
            exam = exams[0]
        elif not may_ask:
            return Focused(data, student=student)
        else:
            options = exams[:4]
            ask = {"what": "exam", "options": options, "labels": options}
            if wanted_subject:
                ask["subject"] = wanted_subject
            asking = _about(data, about_child=student or "all of the parent's children", exams=options,
                            _ask=f"Ask which exam's result they want: {', '.join(o for o in options if o)}.")
            asking.pop("_note", None)
            return Focused(asking, ask=ask, student=student)

    if exam == "all":
        return Focused(_about(data, data=results_summary(rows)), student=student)

    exam_rows = [r for r in rows if (r.get("assessment_group") or "") == exam]
    subjects = _subjects_of(exam_rows)
    children = _by_child(rows)

    # which subject
    if wanted_subject == "?":
        ask = {"what": "subject", "options": subjects, "labels": subjects, "exam": exam}
        return Focused(_about(data, about_child=student or "the child", exam=exam or None, subjects=subjects,
                              _ask=f"Ask which subject they want: {', '.join(subjects)}."),
                       ask=ask, student=student)
    if wanted_subject.lower() == "all" or (not wanted_subject and _says_all(question)
                                            and any(w in _norm(question) for w in ("subject", "مضامین", "مضمون", "mazameen"))):
        entries = []
        for child, child_rows in children.items():
            mine = [r for r in child_rows if (r.get("assessment_group") or "") == exam]
            entry = {"student_name": child, "exam": exam or None}
            if not no_overall and _overall(mine):
                entry["overall_result"] = _overall(mine)
            entry["all_subjects"] = sorted((_subject_line(r) for r in mine),
                                           key=lambda l: l.get("percentage", -1), reverse=True)
            entries.append({k: v for k, v in entry.items() if v is not None})
        return Focused(_about(data, data=entries), student=student)

    subject = None
    if wanted_subject:
        subject = option_said(wanted_subject, subjects) or option_said(wanted_subject, _subjects_of(rows))
        if subject is None:
            note = f"No marks for '{wanted_subject}' were found. Subjects in {exam or 'this exam'}: {', '.join(subjects)}."
            return Focused(_about(data, _note=note, data=[]), student=student)
    else:
        subject = option_said(question, subjects)

    offer = None
    if student and len(subjects) >= 2:
        offer = {"what": "subject", "options": subjects, "labels": subjects, "exam": exam}

    if subject:
        entries = [_subject_entry(child, child_rows, exams, exam, subject) for child, child_rows in children.items()]
        out = _about(data, data=entries)
        if offer:
            out["_end_with"] = "Ask whether they want the marks of another subject."
        return Focused(out, offer=offer, student=student)

    entries = [_exam_entry(child, child_rows, exams, exam, no_overall) for child, child_rows in children.items()]
    out = _about(data, data=entries)
    if offer:
        out["_end_with"] = "Ask whether they want any one subject's marks in detail."
    return Focused(out, offer=offer, student=student)


def focus(resource: str, data, item: dict, question: str, today: date | None = None, may_ask: bool = True) -> Focused:
    """One record lookup narrowed to what was asked (other resources: as they are)."""
    if not isinstance(data, dict):
        return Focused(data)
    try:
        if resource == "attendance":
            return focus_attendance(data, item, question, today or date.today(), may_ask)
        if resource == "assessment":
            return focus_results(data, item, question, may_ask)
    except Exception as error:  # never stand in the way of an answer
        print(f"[Followups] answered without narrowing: {type(error).__name__}: {error}")
    return Focused(data)


# ---------------------------------------------------------
# The parent's reply to what Vocira asked
# ---------------------------------------------------------

def answer_to(pending: dict, question: str, today: date | None = None) -> tuple[dict | None, bool]:
    """
    (slots, declined) for a reply to `pending` (what Focused.ask / .offer
    asked): slots to look the same record up again with, or None when the
    reply is not an answer to it (it then goes through the router as usual);
    declined when the parent said no.
    """
    today = today or date.today()
    short = _short(question)
    norm = _norm(question)
    options = pending.get("options") or []

    slots = _slots_from_reply(pending, question, today, short, norm, options)
    if slots is not None:
        return slots, False
    # "no", "bas" - only when the reply answers nothing ("nahi, September" does)
    return None, short and _has_phrase(norm, _NO_WORDS)


def _slots_from_reply(pending: dict, question: str, today: date, short: bool, norm: str, options: list) -> dict | None:
    what = pending.get("what")
    if what == "month":
        day = day_said(question, today)
        if day and short:
            return {"date": day}
        month = month_said(question, today, options, short_reply=short)
        return {"month": month} if month else None

    if what == "exam":
        if short and _says_all(question):
            exam = "all"
        else:
            exam = option_said(question, options, short_reply=short)
            if exam is None and short and _says_latest(question):
                exam = options[0] if options else None
        if not exam:
            return None
        slots = {"exam": exam}
        if pending.get("subject"):
            slots["subject"] = pending["subject"]
        return slots

    if what == "subject":
        subject = option_said(question, options, short_reply=short)
        if subject is None and short and _says_all(question):
            subject = "all"
        if subject is None and short and _has_phrase(norm, _YES_WORDS):
            subject = "?"
        if not subject:
            return None
        return {"exam": pending.get("exam") or "", "subject": subject}

    return None


def describe(pending: dict) -> str:
    """What Vocira just asked, for the router's prompt."""
    child = pending.get("student") or "the children"
    labels = ", ".join(str(l) for l in (pending.get("labels") or []) if l)
    what = pending.get("what")
    if what == "month":
        return f"which month of {child}'s attendance they want ({labels})."
    if what == "exam":
        return f"which exam's result of {child} they want ({labels})."
    return f"whether they want one subject of {child}'s {pending.get('exam') or 'exam'} result ({labels})."
