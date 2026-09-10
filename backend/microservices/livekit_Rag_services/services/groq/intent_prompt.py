"""
Combined router prompt.

There used to be two separate LLM calls:

    call 1  intent_prompt      (254 lines)  -> ERP_QUERY / RAG_QUERY / ADMIN_HANDOFF
    call 2  erp_services/prompt (810 lines) -> {resource, filters, fields, limit}

The second call's 810-line prompt really only produced TWO things:
the resource name and (sometimes) the student name. Because:

    fields   -> the app ignores them entirely (they come from endpoint.py)
    filters  -> only student_name is read out, the rest is thrown away
    limit    -> constant

So both jobs were merged into a single small prompt.
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


# The old name is kept as well so no existing import breaks.
INTENT_ROUTER_PROMPT = ROUTER_PROMPT


# =========================================================
# ROUTING WITHOUT THE LLM
#
# ROUTER_PROMPT spends ~812 prompt tokens on every question. Groq's
# limit is on tokens-per-MINUTE (8000 on the free tier), so this
# directly sets how many questions fit into a minute. Common
# questions can be recognised outright - there is no need to call
# the LLM for them.
#
# The rule: answer ONLY when it is certain. On the slightest doubt
# it returns None and the LLM decides. The cost of routing wrongly
# (another child's data reaching a parent, or an "I don't know") is
# far higher than these tokens.
# =========================================================

# "my / my child's" - without this the question is a general one.
# Words are matched whole, not inside other words: "our" must not
# match inside "your".
_MINE = ("my", "our", "mine", "our's")

# These words always point at a personal record - "attendance" is
# never a question about school policy.
_ALWAYS_ERP = {
    "attendance": "attendance",
    "marks": "assessment",
    "grades": "assessment",
    "report card": "assessment",
    "result": "assessment",
    "results": "assessment",
}

# These words can go either way - "fee structure" (general) versus
# "my fees" (personal). They count as ERP only alongside "my".
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

# These are always general information - never one child's record
_ALWAYS_RAG = (
    "admission", "policy", "uniform", "fee structure", "syllabus",
    "school timing", "school timings", "school hour", "school hours", "what time does the school",
    "contact", "address", "principal", "about the school",
    "your name", "who are you",
)

# Ordinary words that open a question - even capitalised, these
# are not a child's name.
_NOT_NAMES = {
    "what", "when", "where", "which", "who", "whose", "why", "how",
    "is", "are", "was", "were", "do", "does", "did", "can", "could",
    "has", "have", "had", "show", "tell", "give", "please", "my",
    "our", "i", "the", "a", "an", "and", "or", "if", "hello", "hi",
    "vocira", "class", "okay", "ok", "yes", "no", "sorry", "thanks",
}


def _has(text: str, phrase: str) -> bool:
    """Match a whole word, not a fragment inside another word."""
    return re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text) is not None


def _mentions_a_name(user_query: str) -> bool:
    """
    Was a child named? ("What marks did Alisha get?")

    Questions like these should go to the LLM - it pulls the name out
    and asks for THAT child's record only. quick_route would fetch
    every child's data, which spoils the answer.
    """
    words = user_query.split()

    for i, w in enumerate(words):
        clean = w.strip(".,?!'\"").strip()

        if not clean or not clean[0].isupper():
            continue

        # A capitalised first word does not make it a name
        if i == 0:
            continue

        if clean.lower() in _NOT_NAMES:
            continue

        return True

    return False


def quick_route(user_query: str) -> dict | None:
    """
    Aam sawal bina LLM ke pehchanein.

    Returns a router-shaped dict, or None on the slightest doubt -
    in which case the caller should make the ROUTER_PROMPT LLM call.
    """

    if not user_query:
        return None

    text = user_query.lower().strip()

    # Admin handoff is rare and consequential - always let the LLM decide
    for word in ("admin", "human", "real person", "staff", "someone",
                 "emergency", "urgent"):
        if _has(text, word):
            return None

    # Kisi bache ka naam ho to LLM nikale
    if _mentions_a_name(user_query):
        return None

    mine = any(_has(text, m) for m in _MINE)

    # General information, but only when there is no "my"
    if not mine:
        for phrase in _ALWAYS_RAG:
            if _has(text, phrase):
                return {"intent": "RAG"}

    # Hamesha zaati
    for phrase, resource in _ALWAYS_ERP.items():
        if _has(text, phrase):
            return {"intent": "ERP", "resource": resource, "student": ""}

    # Can go either way - only counts alongside "my"
    if mine:
        for phrase, resource in _ERP_IF_MINE.items():
            if _has(text, phrase):
                return {"intent": "ERP", "resource": resource, "student": ""}

    return None
