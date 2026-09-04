"""
Combined router prompt.

Pehle do alag LLM calls hoti thin:

    call 1  intent_prompt      (254 lines)  -> ERP_QUERY / RAG_QUERY / ADMIN_HANDOFF
    call 2  erp_services/prompt (810 lines) -> {resource, filters, fields, limit}

Doosri call ka 810-line prompt asal mein sirf DO cheezon ke liye tha:
resource ka naam, aur (kabhi kabhi) student ka naam. Kyunke:

    fields   -> app poori tarah ignore karta hai (endpoint.py se aate hain)
    filters  -> sirf student_name nikala jata hai, baqi phenk diya jata hai
    limit    -> constant

Is liye dono kaam ek hi chhote prompt mein mila diye gaye hain.
Ek LLM call kam, aur ~5,000 tokens ke bajaye ~400.
"""

import re

ROUTER_PROMPT = """You are the router for VOCIRA, a school voice assistant.

Read the user's question and reply with ONE line of JSON. Nothing else.
No markdown, no code fences, no explanation.

Shape:
{{"intent":"ERP","resource":"<name>","student":"<name or empty>"}}
{{"intent":"RAG"}}
{{"intent":"ADMIN_HANDOFF"}}

=== ADMIN_HANDOFF ===
ONLY when the user EXPLICITLY asks to speak to a human, admin, staff
member, teacher or real person - or clearly reports an emergency
involving a child ("my son is hurt", "there has been an accident").

NEVER choose ADMIN_HANDOFF for:
  - short reactions or thinking aloud: "wow", "okay", "all right",
    "hmm", "I see", "right", "bye", "I'm going to go"
  - surprise, alarm or an exclamation on its own
  - frustration, a hard question, or anything you cannot answer

Handing off ends the AI conversation, so when in doubt choose RAG.

=== ERP ===
The question is about the caller's OWN CHILDREN — private school records.
Pick exactly one "resource":

  attendance   present/absent, how many days, attendance record
  assessment   marks, grades, results of exams ALREADY TAKEN
  exam         UPCOMING exams: when is the next exam, exam schedule
  schedule     class timetable: which classes, what time, which teacher
  class        which class / section / group the child is in
  course       which subjects the child studies
  program_enrollment   program and academic year
  fee          fee amount, due date, outstanding, is fee paid
  payment      whether payment was made, how much remains
  student      child's profile: name, gender, date of birth, email
  guardian     the caller's own details

"student": if the user names a specific child, put that name.
Otherwise use an empty string — the app then covers all their children.
NEVER invent a name.

=== RAG ===
General school information that is not about a specific child:
admission policy, school timings, fee structure in general, campuses,
contact details, rules, facilities, or any general knowledge question.

=== Examples ===
"Have the school fees been paid?"        -> {{"intent":"ERP","resource":"fee","student":""}}
"How many days was Ahmed present?"       -> {{"intent":"ERP","resource":"attendance","student":"Ahmed"}}
"What marks did Alisha get?"             -> {{"intent":"ERP","resource":"assessment","student":"Alisha"}}
"When is the next exam?"                 -> {{"intent":"ERP","resource":"exam","student":""}}
"What are tomorrow's classes?"           -> {{"intent":"ERP","resource":"schedule","student":""}}
"Which class is my son in?"              -> {{"intent":"ERP","resource":"class","student":""}}
"What subjects does my child study?"     -> {{"intent":"ERP","resource":"course","student":""}}
"Show me my children's names"            -> {{"intent":"ERP","resource":"student","student":""}}
"What is the admission policy?"          -> {{"intent":"RAG"}}
"What time does the school open?"        -> {{"intent":"RAG"}}
"Wow."                                   -> {{"intent":"RAG"}}
"Okay, all right."                       -> {{"intent":"RAG"}}
"I'm going to go."                       -> {{"intent":"RAG"}}
"I want to talk to an admin"             -> {{"intent":"ADMIN_HANDOFF"}}
"Please connect me to a real person"     -> {{"intent":"ADMIN_HANDOFF"}}

User question:
{user_query}

JSON:"""


# Purana naam bhi rakha hua hai taake koi purana import na toote.
INTENT_ROUTER_PROMPT = ROUTER_PROMPT


# =========================================================
# BINA LLM KE ROUTING
#
# ROUTER_PROMPT har sawal par ~812 prompt tokens kharch karta hai.
# Groq ki hadd tokens-per-MINUTE par hai (free tier 8000), is liye
# ye seedha ye tay karta hai ke ek minute mein kitne sawal ho sakte
# hain. Aam sawal saaf pehchane ja sakte hain - un par LLM bulane
# ki zaroorat nahi.
#
# Usool: SIRF tab jawab dein jab bilkul yaqeen ho. Zara sa bhi shak
# ho to None laut ta hai aur LLM faisla karta hai. Ghalat routing
# ki qeemat (parent ko doosre bache ka data, ya "pata nahi") in
# tokens se kahin zyada hai.
# =========================================================

# "mera/mere bache ka" - is ke baghair sawal aam maloomat ka hai.
# Lafz poore milte hain, andar se nahi: "our" ko "your" ke andar
# match nahi hona chahiye.
_MINE = ("my", "our", "mine", "our's")

# Ye lafz hamesha zaati record ka pata dete hain - "attendance"
# school ki policy ka sawal nahi hota.
_ALWAYS_ERP = {
    "attendance": "attendance",
    "marks": "assessment",
    "grades": "assessment",
    "report card": "assessment",
    "result": "assessment",
    "results": "assessment",
}

# Ye lafz dono taraf ja sakte hain - "fee structure" (aam) banaam
# "my fees" (zaati). Sirf "mera/mere" ke sath ERP mante hain.
_ERP_IF_MINE = {
    "fee": "fee",
    "fees": "fee",
    "invoice": "fee",
    "bill": "fee",
    "outstanding": "fee",
    "payment": "payment",
    "present": "attendance",
    "absent": "attendance",
    "timetable": "schedule",
    "time table": "schedule",
    "exam": "exam",
    "subjects": "course",
    "courses": "course",
    "children": "student",
    "kids": "student",
}

# Ye hamesha aam maloomat hain - kabhi kisi ek bache ka record nahi
_ALWAYS_RAG = (
    "admission", "policy", "uniform", "fee structure", "syllabus",
    "school timing", "school timings", "school hour", "school hours", "what time does the school",
    "contact", "address", "principal", "about the school",
    "your name", "who are you",
)

# Sawal ke shuru mein aane wale aam lafz - bara harf hone par bhi
# ye kisi bache ka naam nahi hote.
_NOT_NAMES = {
    "what", "when", "where", "which", "who", "whose", "why", "how",
    "is", "are", "was", "were", "do", "does", "did", "can", "could",
    "has", "have", "had", "show", "tell", "give", "please", "my",
    "our", "i", "the", "a", "an", "and", "or", "if", "hello", "hi",
    "vocira", "class", "okay", "ok", "yes", "no", "sorry", "thanks",
}


def _has(text: str, phrase: str) -> bool:
    """Poora lafz mile, kisi lafz ke andar nahi."""
    return re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text) is not None


def _mentions_a_name(user_query: str) -> bool:
    """
    Kisi bache ka naam liya gaya hai? ("What marks did Alisha get?")

    Aise sawal LLM ko dene chahiye - wo naam nikaal kar sirf USI
    bache ka record mangta hai. quick_route sab bachon ka data
    le aata, jo jawab ko kharab kar deta.
    """
    words = user_query.split()

    for i, w in enumerate(words):
        clean = w.strip(".,?!'\"").strip()

        if not clean or not clean[0].isupper():
            continue

        # Pehla lafz bara harf hone se naam nahi ban jata
        if i == 0:
            continue

        if clean.lower() in _NOT_NAMES:
            continue

        return True

    return False


def quick_route(user_query: str) -> dict | None:
    """
    Aam sawal bina LLM ke pehchanein.

    Returns router jaisa dict, ya None agar zara sa bhi shak ho -
    us surat mein caller ROUTER_PROMPT wali LLM call kare.
    """

    if not user_query:
        return None

    text = user_query.lower().strip()

    # Admin handoff nadir aur ahem hai - hamesha LLM decide kare
    for word in ("admin", "human", "real person", "staff", "someone",
                 "emergency", "urgent"):
        if _has(text, word):
            return None

    # Kisi bache ka naam ho to LLM nikale
    if _mentions_a_name(user_query):
        return None

    mine = any(_has(text, m) for m in _MINE)

    # Aam maloomat, magar sirf tab jab "mera" na ho
    if not mine:
        for phrase in _ALWAYS_RAG:
            if _has(text, phrase):
                return {"intent": "RAG"}

    # Hamesha zaati
    for phrase, resource in _ALWAYS_ERP.items():
        if _has(text, phrase):
            return {"intent": "ERP", "resource": resource, "student": ""}

    # Dono taraf ja sakte hain - sirf "mera" ke sath
    if mine:
        for phrase, resource in _ERP_IF_MINE.items():
            if _has(text, phrase):
                return {"intent": "ERP", "resource": resource, "student": ""}

    return None
