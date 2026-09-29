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

ROUTER_TEMPLATE = """You are the router for VOCIRA, a school voice assistant.

Read the user's question and reply with ONE line of JSON. Nothing else.
No markdown, no code fences, no explanation.

Shape:
{{"intent":"ERP","items":[{{"resource":"<name>","student":"<name or empty>"}}]}}
{{"intent":"RAG","search":"<the question restated in plain English>"}}
{{"intent":"ADMIN_HANDOFF"}}

Callers rarely use the words the records use. Decide by what the
question MEANS, never by which words appear in it. The question may
be English, Urdu, Roman Urdu, casual, or slightly misheard by speech
recognition.

"items" is a LIST because a question can ask about more than one
thing at once ("how is Zoya's attendance AND has the fee been
paid?"). Put ONE entry per distinct thing asked about, in the order
asked. A plain, single-topic question still uses a list - just with
one entry in it. Do not invent extra entries for anything not
actually asked.

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
  schedule     class timetable: which classes, what time, which teacher, which room
  class        which class / section / group the child is in
  course       which subjects the child studies
  program_enrollment   program and academic year
  fee          fee amount, due date, outstanding, is fee paid
  payment      whether payment was made, how much remains
  student      child's profile: name, gender, date of birth, email
  guardian     the caller's own details
  leave        leave / absence applications the child has taken, and why
  remarks      teacher or staff comments/notes written about the child

Other words for the same thing:
  assessment   performance, progress, how the child is doing in studies,
               scores, report card, academic record, "padhai kaisi hai",
               percentage ("kitni percentage aayi", "پرسنٹیج")
  attendance   goes to school regularly, missed school, came to school,
               ATTENDANCE percentage
  fee          dues, challan, voucher, how much is owed or left to pay
  exam         next test, date sheet, paper schedule
  schedule     periods, routine, what the child has tomorrow
  remarks      teacher's feedback, complaints, behaviour
"my child", "my son", "my daughter", "my kids", "their", "his", "her"
when speaking of their own children all mean the caller's children.

"student": which ONE child the question is about - the answer then
covers only that child. An empty string covers all their children.

- The caller names a child: copy that child's name EXACTLY as it is
  written in "The caller's children" under THIS CALL below. Speech
  recognition often mishears names, so choose the child whose name
  SOUNDS closest: "سنک بال", "Sanaa Kabal" or "Sanna" for "Sana Iqbal",
  "Humza" for "Hamza Iqbal". Only when no children are
  listed, write the name in Roman English spelling as school records
  would ("زویا" -> "Zoya"), never in Urdu script.
- The question names no one but plainly goes on about ONE child -
  "her", "his", "she", "he", "uski", "uska", "iski", "us ka", "and
  the fee?", "what percentage did she get?", or it finishes a sentence
  the caller began just before: use that child from THIS CALL (the one
  named in what the caller said just before, else the child they were
  just asking about).
- A pause can cut one sentence in two. When the question starts in
  the middle of a sentence ("کہ ...", "اور ...", "that ...", "and
  ..."), read what the caller said just before and this question as
  ONE sentence - a child named there ("سنک بال کا جو" sounds like
  "Sana Iqbal's") is the child this question is about.
- The caller asks about their children in general - "my children",
  "kids", "both", "all", "بچوں", "دونوں", "سب" - or asks a fresh
  question that points at no one child: empty string.
NEVER invent a name.

=== RAG ===
General school information that is not about a specific child:
admission policy, school timings, fee structure in general, campuses,
contact details, rules, facilities, holidays, or any general knowledge
question - and questions about VOCIRA itself (what it is, what it can
do, what this system is for).

"search": the same question restated as a short, plain English
question in the school's own words, so the right document is found:
"what can this system do" -> "What is the Vocira voice assistant and
what can it help with?"; "chuttiyan kab hain" -> "When are the school
holidays?". Keep its meaning exactly - add nothing the caller did not
ask. For an ERP or ADMIN_HANDOFF answer, leave "search" out.

=== Examples ===
"Have the school fees been paid?"        -> {{"intent":"ERP","items":[{{"resource":"fee","student":""}}]}}
"How many days was Ahmed present?"       -> {{"intent":"ERP","items":[{{"resource":"attendance","student":"Ahmed"}}]}}
"زویا کی حاضری کیسی ہے؟" (Urdu: how is
 Zoya's attendance?)                     -> {{"intent":"ERP","items":[{{"resource":"attendance","student":"Zoya"}}]}}
"What marks did Alisha get?"             -> {{"intent":"ERP","items":[{{"resource":"assessment","student":"Alisha"}}]}}
"When is the next exam?"                 -> {{"intent":"ERP","items":[{{"resource":"exam","student":""}}]}}
"What are tomorrow's classes?"           -> {{"intent":"ERP","items":[{{"resource":"schedule","student":""}}]}}
"Which room is my child's class in?"     -> {{"intent":"ERP","items":[{{"resource":"schedule","student":""}}]}}
"How many leaves has Ahmed taken?"       -> {{"intent":"ERP","items":[{{"resource":"leave","student":"Ahmed"}}]}}
"What did the teacher say about my son?" -> {{"intent":"ERP","items":[{{"resource":"remarks","student":""}}]}}
"Which class is my son in?"              -> {{"intent":"ERP","items":[{{"resource":"class","student":""}}]}}
"What subjects does my child study?"     -> {{"intent":"ERP","items":[{{"resource":"course","student":""}}]}}
"Show me my children's names"            -> {{"intent":"ERP","items":[{{"resource":"student","student":""}}]}}

Compound questions - one entry per topic asked:
"How is Zoya's attendance and has     -> {{"intent":"ERP","items":[
 the fee been paid?"                        {{"resource":"attendance","student":"Zoya"}},
                                             {{"resource":"fee","student":"Zoya"}}]}}
"What are Ahmed's marks and which     -> {{"intent":"ERP","items":[
 class is he in?"                           {{"resource":"assessment","student":"Ahmed"}},
                                             {{"resource":"class","student":"Ahmed"}}]}}

"How is my children's academic performance?" -> {{"intent":"ERP","items":[{{"resource":"assessment","student":""}}]}}
"Is any challan pending for my kids?"    -> {{"intent":"ERP","items":[{{"resource":"fee","student":""}}]}}

"What is the admission policy?"          -> {{"intent":"RAG","search":"What is the admission policy?"}}
"What time does the school open?"        -> {{"intent":"RAG","search":"What are the school timings?"}}
"What does your system exactly do?"      -> {{"intent":"RAG","search":"What is the Vocira voice assistant and what can it help with?"}}
"گرمیوں کی چھٹیاں کب ہوں گی؟" (Urdu: when
 are the summer holidays?)               -> {{"intent":"RAG","search":"When are the summer holidays?"}}
"Wow."                                   -> {{"intent":"RAG","search":"Wow."}}
"Okay, all right."                       -> {{"intent":"RAG","search":"Okay, all right."}}
"I'm going to go."                       -> {{"intent":"RAG","search":"I'm going to go."}}
"I want to talk to an admin"             -> {{"intent":"ADMIN_HANDOFF"}}
"Please connect me to a real person"     -> {{"intent":"ADMIN_HANDOFF"}}

With the caller's children "Sana Iqbal, Hamza Iqbal":
"سنک بال کی فیس کتنی ہے؟"                -> {{"intent":"ERP","items":[{{"resource":"fee","student":"Sana Iqbal"}}]}}
"Humza's result?"                        -> {{"intent":"ERP","items":[{{"resource":"assessment","student":"Hamza Iqbal"}}]}}
"میرے بچوں کا رزلٹ؟"                     -> {{"intent":"ERP","items":[{{"resource":"assessment","student":""}}]}}
Having just asked about Sana Iqbal:
"اور اس کی کتنی پرسنٹیج آئی؟"            -> {{"intent":"ERP","items":[{{"resource":"assessment","student":"Sana Iqbal"}}]}}

=== THIS CALL ===
{context}

User question:
{user_query}

JSON:"""

_NO_CONTEXT = "The caller's children: not known."

# The old names still format with user_query alone - the context
# line then says nothing is known.
ROUTER_PROMPT = ROUTER_TEMPLATE.replace("{context}", _NO_CONTEXT)
INTENT_ROUTER_PROMPT = ROUTER_PROMPT


def build_router_prompt(
    user_query: str,
    children: list[str] | tuple = (),
    last_child: str | None = None,
    previous: str | None = None,
) -> str:
    """
    The router prompt with what this call already knows: the caller's
    own children as the records name them - so a misheard name can
    still be matched to the right child - and what was just asked, so
    "and her percentage?" stays about the same child.
    """
    # Empty says "not known", not "none": the list is empty also when
    # it just could not be read, and "none" made the model drop the
    # name the caller said - which answers about every child.
    lines = [
        "The caller's children: "
        + (", ".join(children) if children else "not known.")
    ]
    if last_child:
        lines.append(f"The child the caller was just asking about: {last_child}")
    if previous:
        lines.append(f'What the caller said just before this: "{previous}"')
    return ROUTER_TEMPLATE.format(user_query=user_query, context="\n".join(lines))

# Room for the "search" restatement - at 80 a long one was cut off,
# and JSON cut off mid-way does not parse.
ROUTER_MAX_TOKENS = 160


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
    # "children" / "kids" were here, mapped to the child's profile. They
    # say WHOSE record, not WHICH one - "the academic performance of my
    # children" or "is a challan pending for my kids" went to the
    # profile, and the caller heard it had nothing on performance.
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

    # "her result" means the one child just talked about - only the
    # LLM, which sees this call's context, can tell which.
    for word in ("her", "his", "she", "he", "him"):
        if _has(text, word):
            return None

    mine = any(_has(text, m) for m in _MINE)

    # General information, but only when there is no "my"
    if not mine:
        for phrase in _ALWAYS_RAG:
            if _has(text, phrase):
                return {"intent": "RAG"}

    # Collect every distinct resource this question touches, rather
    # than stopping at the first match - a compound question ("is my
    # fee paid and what is her attendance?") matches more than one of
    # these, and the fast path here has no way to work out which
    # phrase belongs to which topic. That parsing needs the LLM, so
    # more than one distinct resource here means bailing out to it
    # instead of silently answering only the first one.
    matched = []

    for phrase, resource in _ALWAYS_ERP.items():
        if _has(text, phrase) and resource not in matched:
            matched.append(resource)

    if mine:
        for phrase, resource in _ERP_IF_MINE.items():
            if _has(text, phrase) and resource not in matched:
                matched.append(resource)

    if len(matched) == 1:
        return {"intent": "ERP", "items": [{"resource": matched[0], "student": ""}]}

    return None
