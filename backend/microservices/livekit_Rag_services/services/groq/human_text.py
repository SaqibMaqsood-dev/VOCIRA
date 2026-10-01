import os
from datetime import date


# The same switch used by sst_whisper.py (what Whisper listens for)
# and piper_servies.py (which voice speaks the answer) also decides
# what language the LLM is told to answer in. One setting for the
# whole conversation instead of three that could drift apart - an
# Urdu voice reading an English answer, or vice versa, is exactly
# the mismatch a caller would notice immediately.
# The default, for callers whose account has not chosen a language.
# A guardian who HAS chosen gets theirs passed in per call instead.
_RESPONSE_LANGUAGE = os.getenv("STT_LANGUAGE", "ur").strip().lower()

_LANGUAGE_INSTRUCTIONS = {
    "en": "Respond in English.",
    "ur": (
        "Respond ONLY in Urdu, written in the Urdu (Nastaliq / "
        "Perso-Arabic) script - never in English, and never in Roman "
        "Urdu (Urdu spelled out with English letters). This answer is "
        "read aloud by an Urdu text-to-speech voice, which can only "
        "pronounce real Urdu script correctly. All of the RESPONSE "
        "RULES below still apply in Urdu too."
    ),
}

# How numbers are written. English: in words, the model does that
# well. Urdu: in digits - the model spells Urdu numbers wrong (76 as
# "ستائیس چھ"), so spoken_text.speak_numbers() spells them instead.
_NUMBER_RULES = {
    "en": """8. Convert ALL numbers, times, amounts and codes into spoken words.
   This is not optional - the answer is read aloud.

   "8:00 AM to 2:00 PM"  ->  "eight in the morning until two in the afternoon"
   "PKR 18,500"          ->  "eighteen thousand five hundred rupees"
   "Grades 1 to 5"       ->  "grades one to five"
   "64.8%"               ->  "sixty-four point eight percent"
   "042-111-777-800"     ->  "zero four two, one one one, seven seven seven, eight hundred"
""",
    "ur": """8. Write EVERY number with digits - marks, percentages, amounts,
   counts, day numbers and years: 76, 64.8%, 7000 روپے, 7 اگست 2026.
   Never spell a number out in words - the app turns the digits into
   correctly spoken Urdu. Write month names in Urdu (اگست, not August).
   Marks out of a total: the TOTAL first - "400 میں سے 259 نمبر"
   (259 out of 400), never "259 میں سے 400".
""",
}


# Short system messages spoken directly by voice_pipeline.py - login
# and permission refusals, "the ERP is unreachable" - none of these
# ever go through the LLM, so switching STT_LANGUAGE alone would not
# have touched them. Without their own translation an Urdu
# conversation would suddenly jump to English at exactly the moment
# something had already gone wrong for the caller, which is the worst
# possible time for it to be confusing.
SYSTEM_MESSAGES = {
    # Nobody on the staff answered a handoff in time.
    "handoff_no_answer": {
        "en": (
            "I am sorry, no one from our staff is free at the moment. "
            "Your request has been saved and someone will get back to "
            "you. In the meantime, I can keep helping you."
        ),
        "ur": (
            "معذرت، اس وقت ہمارے عملے میں سے کوئی دستیاب نہیں ہے۔ آپ کی "
            "درخواست محفوظ کر لی گئی ہے اور کوئی آپ سے رابطہ کرے گا۔ تب "
            "تک میں آپ کی مدد کرتا رہوں گا۔"
        ),
    },
    # The same, for a guest - with no account there is no way to get
    # back to them, so they are told where to reach the school instead.
    # A school with no records system connected (services/tenants.py):
    # a question about a child gets this instead of any ERP lookup.
    "records_not_available": {
        "en": (
            "I am sorry, children's records for {school} are not "
            "available on Vocira yet. For attendance, fees or results, "
            "please call the school on {helpline}. I can still help you "
            "with general questions about the school."
        ),
        "ur": (
            "معذرت، {school} کے بچوں کا ریکارڈ ابھی ووسیرا پر دستیاب نہیں ہے۔ "
            "حاضری، فیس یا نتیجے کے لیے براہ کرم اسکول کو {helpline} پر کال "
            "کریں۔ اسکول کے عام سوالات میں میں اب بھی آپ کی مدد کر سکتا ہوں۔"
        ),
    },
    "handoff_no_answer_guest": {
        "en": (
            "I am sorry, no one from our staff is free at the moment. "
            "Since you are not logged in, we have no way to call you "
            "back, so please call the school helpline on {helpline}, "
            "or send a request from the Support page. In the meantime, "
            "I can keep helping you."
        ),
        "ur": (
            "معذرت، اس وقت ہمارے عملے میں سے کوئی دستیاب نہیں ہے۔ آپ لاگ "
            "ان نہیں ہیں، اس لیے ہم آپ سے دوبارہ رابطہ نہیں کر سکتے۔ براہ "
            "کرم اسکول کی ہیلپ لائن {helpline} پر کال کریں یا سپورٹ پیج سے "
            "درخواست بھیجیں۔ تب تک میں آپ کی مدد کرتا رہوں گا۔"
        ),
    },
    "erp_not_authorized": {
        "en": "You are not authorized to access ERP information. Please log in with an authorized account.",
        "ur": "آپ کو ای آر پی کی معلومات تک رسائی کی اجازت نہیں ہے۔ براہ کرم ایک مجاز اکاؤنٹ سے لاگ ان کریں۔",
    },
    "erp_not_authorized_short": {
        "en": "You are not authorized to access ERP information.",
        "ur": "آپ کو ای آر پی کی معلومات تک رسائی کی اجازت نہیں ہے۔",
    },
    "account_not_verified": {
        "en": "I could not verify your account. Please log in again.",
        "ur": "میں آپ کے اکاؤنٹ کی تصدیق نہیں کر سکا۔ براہ کرم دوبارہ لاگ ان کریں۔",
    },
    "erp_not_linked": {
        "en": "Your VOCIRA account is not linked to an ERP account.",
        "ur": "آپ کا ووسیرا اکاؤنٹ کسی ای آر پی اکاؤنٹ سے منسلک نہیں ہے۔",
    },
    "answer_assembly_failed": {
        "en": (
            "I found your record, but I am having trouble putting "
            "the answer together right now. Please ask me again in "
            "a moment."
        ),
        "ur": (
            "مجھے آپ کا ریکارڈ مل گیا، لیکن ابھی جواب تیار کرنے میں "
            "دشواری ہو رہی ہے۔ براہ کرم تھوڑی دیر بعد دوبارہ پوچھیں۔"
        ),
    },
    "connecting_to_staff": {
        "en": "Please hold on. I am connecting you to a member of our school staff.",
        "ur": "براہ کرم انتظار کریں۔ میں آپ کو اسکول کے عملے کے ایک رکن سے ملا رہا ہوں۔",
    },
    "erp_unreachable": {
        "en": (
            "Sorry, I cannot reach the school records system right "
            "now. Please try again shortly."
        ),
        "ur": (
            "معذرت، میں ابھی اسکول کے ریکارڈ کے نظام تک نہیں پہنچ "
            "سکتا۔ براہ کرم تھوڑی دیر بعد دوبارہ کوشش کریں۔"
        ),
    },
}


def system_message(key: str, language: str | None = None, school=None) -> str:
    """
    A short, non-LLM-written spoken message, in the caller's language.

    {school} and {helpline} are the caller's school's (services/tenants.py
    - the first school when none is given); the helpline is spelled out
    digit by digit, as every phone number is.
    """

    # Imported here: tenants and query pull in the RAG config and the
    # vector store, which this small module should not load at import.
    from backend.microservices.livekit_Rag_services.services import tenants
    from backend.microservices.livekit_Rag_services.services.rag_engine.query import (
        speak_phone_number,
    )

    entry = SYSTEM_MESSAGES.get(key, {})

    language = (language or _RESPONSE_LANGUAGE).strip().lower()

    text = entry.get(language) or entry.get("en", "")

    if "{school}" in text or "{helpline}" in text:
        chosen = school if isinstance(school, tenants.School) else tenants.get_school(school)
        text = text.replace("{school}", chosen.display_name(language)).replace(
            "{helpline}", speak_phone_number(chosen.helpline, language)
        )

    return text


# ERPNext's internal IDs - "EDU-ATT-2026-00001",
# "EDU-STU-2026-00013", "ACC-SINV-2026-00007". They are not worth
# speaking aloud, and every resource already carries a readable name
# alongside them (student_name / customer / guardian_name /
# student_group_name).
#
# Two benefits:
#   - ~50 fewer characters per record, so fewer tokens (Groq's limit
#     is tokens-per-minute, so this is directly more calls)
#   - the LLM cannot read such an ID aloud. It used to say:
#     "ACC-SINV-two thousand twenty-six-zero zero zero zero seven"
_INTERNAL_ID_FIELDS = ("name", "student")


def _strip_internal_ids(response):
    """LLM ko bhejne se pehle andaroni IDs nikaal dein."""

    if isinstance(response, dict):
        return {
            k: _strip_internal_ids(v)
            for k, v in response.items()
            if k not in _INTERNAL_ID_FIELDS
        }

    if isinstance(response, list):
        return [_strip_internal_ids(v) for v in response]

    return response


def build_response_prompt(
    user_query: str,
    response: str,
    today: str | None = None,
    language: str | None = None,
    school_name: str = "The Educators",
) -> str:
    """
    Convert structured ERP/API data into a natural,
    conversational response suitable for text and TTS.

    Passing `today` lets questions like "yesterday" or "this week"
    resolve correctly.

    `response` is a single dict for an ordinary, single-topic
    question - unchanged from before. For a compound question
    ("Zoya's attendance AND has the fee been paid?") voice_pipeline.py
    passes a LIST of dicts, one per topic asked about. Left as a bare
    Python list dumped into the prompt, the model tended to notice
    only the first dict and silently drop the rest - it was never
    told there was more than one topic to cover. Numbering each
    section explicitly fixes that.
    """

    today = today or date.today().isoformat()

    response = _strip_internal_ids(response)

    multi_topic_instruction = ""
    if isinstance(response, list) and len(response) > 1:
        topic_count = len(response)
        response = "\n\n".join(
            f"--- Topic {i} of {topic_count} ---\n{part}"
            for i, part in enumerate(response, start=1)
        )
        multi_topic_instruction = (
            f"\nThis question asked about {topic_count} separate "
            "topics, numbered below. Address EVERY one of them in "
            "your answer - do not stop after the first. If one "
            "topic's information is genuinely missing, say so briefly "
            "for that topic only and still cover the rest.\n"
        )

    language_key = (language or _RESPONSE_LANGUAGE).strip().lower()
    language_instruction = _LANGUAGE_INSTRUCTIONS.get(
        language_key,
        _LANGUAGE_INSTRUCTIONS["en"],
    )
    number_rule = _NUMBER_RULES.get(language_key, _NUMBER_RULES["en"])

    return f"""
You are Vocira, a professional AI voice assistant for {school_name}.

Your task is to convert the provided information into a clear,
natural, conversational answer to the user's question.

==================================================
LANGUAGE
==================================================

{language_instruction}

==================================================
TODAY'S DATE
==================================================

{today}

Use this to work out words like "today", "tomorrow", "yesterday",
"this week", "next exam" and "upcoming".

==================================================
USER QUESTION
==================================================

{user_query}

==================================================
AVAILABLE INFORMATION
==================================================
{multi_topic_instruction}
{response}

Each "_about" line, if present, tells you what that section of
information is.

IMPORTANT CONTEXT:

- This information has ALREADY been filtered to the person asking.
  Every record belongs to their own child or children. You may
  speak about it directly as theirs.

- If a record shows a class or group, that IS the class of the
  child being asked about. Say so plainly.

- If only one child's records are present, the answer is about
  that child.

- Percentages are ALREADY worked out: "percentage" for each subject,
  "overall_result" / "overall_results" (obtained_marks out of
  total_marks, and overall_percentage) for a whole exam, and
  "attendance_percentage". Say those exact figures. NEVER calculate a
  percentage, total or average yourself. When the caller asks about
  a result or a percentage, give the overall percentage first, then
  the subjects.

==================================================
RESPONSE RULES
==================================================

1. Answer the user's question directly.

2. Use ONLY the information provided above.
   Never invent, assume, or add information.

3. Return plain natural-language text only.

4. The response will be spoken aloud using text-to-speech.
   Therefore, write it exactly as a person would naturally speak.

5. Do NOT use:
   - Markdown
   - Asterisks
   - Tables
   - Bullet points
   - Numbered lists
   - JSON
   - Emojis
   - Special formatting

6. Avoid unnecessary technical language.

7. Do not mention:
   - SQL
   - databases
   - tables
   - columns
   - APIs
   - queries
   - ERP systems
   - internal processing

{number_rule}
   Never speak a URL or file name such as "site.com/page.php" -
   say "on the school website" instead.

8b. Convert numerical information into natural spoken language when
   appropriate.

   For example:
   "8:00 AM to 4:00 PM"
   should become:
   "from eight in the morning until four in the afternoon."

   "7:55 AM"
   should become:
   "five minutes before eight in the morning."

   "11:00 AM to 11:20 AM"
   should become:
   "from eleven in the morning until twenty past eleven."

9. Prefer approximate, easy-to-understand expressions for times
   when exact precision is not important.

10. Do not read unnecessary timestamps, IDs, UUIDs, database values,
    or technical identifiers aloud.

11. If the information contains multiple related records, summarize
    them naturally instead of reading them like a table.

12. Keep the answer concise but complete.

13. Do NOT give up while any useful information is present.

    Only say that you do not have the answer when the information
    is genuinely empty or completely unrelated.

    If records exist but do not match the exact date or detail the
    user asked for, DO NOT reply with "I don't have that
    information". Instead, tell them what you DO have.

    For example, if they ask about tomorrow's timetable and the
    only classes you have are for an earlier date, say which
    classes you have and for which date, rather than refusing.

    Likewise, if they ask when the next exam is and you have
    exam records with dates, tell them those exams and dates,
    noting whether they have already passed.

==================================================
FINAL OUTPUT
==================================================

Return ONLY the final response that Vocira should speak to the user.
"""