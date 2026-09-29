# Groq reasoning
import asyncio
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from backend.microservices.livekit_Rag_services.services.rag_engine.config import (
    GROQ_MODEL, MAX_CONTEXT_CHARS, PINECONE_NAMESPACE
)
# The same client the rest of the system uses, so the provider is
# switched from one place. There was a separate Groq client here
# before, so when gpt-oss-20b ran out of quota, ERP kept working
# while RAG answered "assistant is currently busy" every time.
from backend.microservices.livekit_Rag_services.services.groq.groq import (
    client as llm_client,
    _is_rate_limited,
    _model_chain,
)

# Same language switch used everywhere else in the pipeline (STT,
# TTS voice, and the ERP answer prompt in human_text.py) - imported
# rather than redefined here, so there is exactly one place that
# decides what "ur" means in a prompt instead of two copies that
# could say different things.
from backend.microservices.livekit_Rag_services.services.groq.human_text import (
    _RESPONSE_LANGUAGE,
    _LANGUAGE_INSTRUCTIONS,
)

log = logging.getLogger(__name__)

# Dedicated thread pools —Groq and Pinecone calls don't use the default shared pool, so they won't compete with the background sync.
_groq_executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="groq")
_retrieval_executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="retrieval")


def clean_for_tts(text: str) -> str:
    """Strip markdown formatting so TTS doesn't speak symbols/numbers literally."""
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'__(.*?)__', r'\1', text)
    text = re.sub(r'_(.*?)_', r'\1', text)
    text = re.sub(r'^#{1,6}\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\d+[\.\)]\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*[-\*•]\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'[\*_`#]', '', text)
    text = re.sub(r'\n{2,}', '. ', text)
    text = re.sub(r'\n', ' ', text)
    text = re.sub(r'\s{2,}', ' ', text)
    return text.strip()


# A phone number as the context writes it: "042-111-777-800",
# "0423-8050005", "0423 8050005", "04238050005".
# A full stop or comma after it ends the sentence - only one followed
# by another digit ("7,000", "3.5") makes it part of a bigger number.
_PHONE = re.compile(
    r"(?<!\d)(?<!\d[,.])"
    r"(?:0\d{2,4}(?:[-\s]\d{3,8})+|0\d{9,11})"
    r"(?!\d|[,.]\d)"
)

_DIGIT_WORDS = {
    "en": ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"],
    "ur": ["صفر", "ایک", "دو", "تین", "چار", "پانچ", "چھ", "سات", "آٹھ", "نو"],
}


# "[PHONE_1]", or the same without its brackets. Upper-case only, so a
# sentence that happens to say "phone 2" is left alone.
_PLACEHOLDER = re.compile(r"\[\s*PHONE[_\s]?(\d+)\s*\]|\bPHONE_(\d+)\b")


def mask_phone_numbers(context: str) -> tuple[str, dict[str, str]]:
    """
    Swap every phone number in the context for [PHONE_1], [PHONE_2]...

    Told to copy the digits, the backup model still spelled numbers
    itself and dropped repeats ("one one" for "one one one"). A short
    tag is copied reliably; unmask_phone_numbers() puts the real number
    back, spelled by code.
    """
    numbers: dict[str, str] = {}

    def tag(match: re.Match) -> str:
        number = match.group(0)
        for key, value in numbers.items():
            if value == number:
                return f"[{key}]"
        key = f"PHONE_{len(numbers) + 1}"
        numbers[key] = number
        return f"[{key}]"

    return _PHONE.sub(tag, context), numbers


def unmask_phone_numbers(text: str, numbers: dict[str, str], language: str) -> str:
    """Replace the tags with the numbers, read out digit by digit."""

    def restore(match: re.Match) -> str:
        number = numbers.get(f"PHONE_{match.group(1) or match.group(2)}")
        return speak_phone_numbers(number, language) if number else ""

    return _PLACEHOLDER.sub(restore, text)


def speak_phone_numbers(text: str, language: str) -> str:
    """
    Read every phone number out digit by digit.

    The model used to spell numbers itself and dropped digits from the
    runs of zeros - the service desk's 0423-8050005 came out as
    "eight zero five, zero zero five". Here each group is spelled
    exactly, a short pause (comma) between groups.
    """
    words = _DIGIT_WORDS.get(language, _DIGIT_WORDS["en"])
    sep = "، " if language == "ur" else ", "

    def spell(match: re.Match) -> str:
        groups = re.split(r"[-\s]+", match.group(0))
        return sep.join(" ".join(words[int(d)] for d in g) for g in groups)

    return _PHONE.sub(spell, text)


async def search_knowledge_base(retriever, query: str, also: str | None = None):
    """
    Fetch relevant chunks from Pinecone asynchronously with namespace isolation.

    `also` is the router's plain restatement of the question. Callers
    rarely use the records' own words - "what does your system do"
    found nothing about Vocira, while "what is the Vocira voice
    assistant" finds it at once. Both are searched together, and the
    results are interleaved so the best of each survive the context cap.
    """
    try:
        if not retriever:
            return "Retriever is not initialized. Please run /sync-database first.", []

        loop = asyncio.get_running_loop()
        queries = [query]
        if isinstance(also, str) and also.strip() and also.strip().lower() != query.strip().lower():
            queries.append(also)

        results = await asyncio.gather(*[
            loop.run_in_executor(_retrieval_executor, retriever.invoke, q)
            for q in queries
        ])

        docs, seen = [], set()
        for rank in range(max(len(r) for r in results)):
            for found in results:
                if rank < len(found) and found[rank].page_content not in seen:
                    seen.add(found[rank].page_content)
                    docs.append(found[rank])

        if not docs:
            return "", []

        context_parts = []
        sources = set()

        for doc in docs:
            context_parts.append(doc.page_content)
            sources.add(doc.metadata.get("source", "Internal Records"))

        return "\n".join(context_parts), list(sources)

    except Exception as e:
        log.error(f"Retrieval error: {e}")
        return "Sorry, I'm having trouble accessing the school records right now.", []


_NO_CONTEXT_MESSAGE = {
    "en": "I'm sorry, I couldn't find any verified information about this in the school records.",
    "ur": "معذرت، مجھے اسکول کے ریکارڈ میں اس بارے میں کوئی تصدیق شدہ معلومات نہیں ملی۔",
}


async def ask_vocira(
    retriever,
    user_query: str,
    language: str | None = None,
    search_query: str | None = None,
):
    """
    Core RAG logic — async, non-blocking, returns a single string answer.

    `search_query` is the router's plain-English restatement of the
    question (it costs no extra call - the router writes it anyway).
    """
    # The caller's own language, not the deployment default - an
    # English guest was getting Urdu answers read out by the English
    # voice.
    language = (language or _RESPONSE_LANGUAGE).strip().lower()

    context, _ = await search_knowledge_base(retriever, user_query, also=search_query)

    if not context.strip():
        return _NO_CONTEXT_MESSAGE.get(
            language, _NO_CONTEXT_MESSAGE["en"]
        )

    if len(context) > MAX_CONTEXT_CHARS:
        context = context[:MAX_CONTEXT_CHARS] + "\n...[truncated]"

    context, phone_numbers = mask_phone_numbers(context)

    language_instruction = _LANGUAGE_INSTRUCTIONS.get(
        language, _LANGUAGE_INSTRUCTIONS["en"]
    )

    system_prompt = f"""You are Vocira, the official AI Assistant for 'The Educators'.
Use the following verified context to answer the user's question.

LANGUAGE:
{language_instruction}

RULES:
1. Be concise, helpful, and professional.
2. If the context does not contain the exact answer, do NOT just say you
   don't have the information, and do not open with an apology - on a
   call, a first word of "sorry" sounds like the assistant failed.
   Instead, in two or three sentences: FIRST give what the context does
   say that is closest to the question (for example the academic year
   and term months when asked about vacations), THEN say plainly that the
   exact detail is not in the school's records, THEN tell the caller
   where to get it - their campus office, the school website, or the
   helpline number if it appears in the context.
   Only if nothing in the context is related at all, say you don't have
   that information and suggest the campus office or school website.
   Repeat what the context states and nothing more: never work a date or
   period out from it. Knowing the term months does NOT tell you when a
   vacation falls - do not say or suggest when it might be, in ANY
   language. If a question asks WHEN something happens and the context
   gives no date for that exact thing, name no month and no date for it,
   and do not hint at one either ("holidays would fall between the
   terms" is a guess - leave it out).
2a. The caller may use different words from the context: "holidays" or
   "chuttiyan" for vacations, "joining" for admission, "cost" for fee,
   "runs" for owns, "your system" or "you" for Vocira. Match by meaning,
   and answer from the context whenever it covers what they mean.
   Questions about Vocira itself - what it is, what it can do, what
   this system is for - ARE about the school's service: answer them
   from the context.
2b. If the question is not about the school or Vocira at all, or does
   not make sense (it may be a sentence that was misheard), say briefly
   that you did not catch that, and ask the caller to repeat their
   question about the school.
3. Never make up facts - no dates, times, numbers or names that are not
   in the context.
4. For admission-related questions, always provide complete step-by-step details including requirements, process, and any tests or documents needed.
5. Never give a partial answer — if information exists in context, give it fully.
6. THIS ANSWER IS SPOKEN ALOUD. Write exactly how a person would SAY it.
   No markdown, no asterisks, no bullet points, no numbered lists.

7. Write every number, time, amount and code in WORDS, not digits, IN THE
   ANSWER LANGUAGE ABOVE. English examples of the idea:
   "8:00 AM to 2:00 PM"   -> "eight in the morning until two in the afternoon"
   "PKR 18,500"           -> "eighteen thousand five hundred rupees"
   "7:55 AM"              -> "five minutes before eight in the morning"
   "Grades 1 to 5"        -> "grades one to five"
   EXCEPT phone numbers: in the context they appear as tags like
   [PHONE_1] and [PHONE_2]. Each tag IS the number - the caller hears the
   real digits in its place. So whenever a number helps the caller (how
   to reach or call the school), DO give it, by writing its tag exactly:
   "call the UAN on [PHONE_1] or the online service desk on [PHONE_2]".
   Never leave a number out, and never spell one yourself.

8. Never speak a URL, file name or web address such as
   "www.example.com/contact-us.php". Say "on the school website" instead.

9. If listing several things, join them in flowing sentences
   ("First... then... and finally..."), never as a list.

CONTEXT:
{context}"""

    # On Groq every model has its own daily budget. When one runs
    # out the others still have theirs - only that single model was
    # tried here before, so the moment its budget was gone every RAG
    # question answered "assistant is currently busy".
    chain = _model_chain(GROQ_MODEL)

    for attempt, model_name in enumerate(chain):

        # The gpt-oss models are reasoning models - without this flag
        # they spend many times the answer's tokens just "thinking".
        extra = {}
        if "gpt-oss" in model_name:
            extra["reasoning_effort"] = "low"
        try:
            loop = asyncio.get_running_loop()
            response = await asyncio.wait_for(
                loop.run_in_executor(
                    _groq_executor,
                    lambda: llm_client.chat.completions.create(
                        model=model_name,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user",   "content": user_query}
                        ],
                        # max_tokens is not just a cap - the provider
                        # RESERVES that many tokens and they come out
                        # of the per-minute budget. This was 1000,
                        # while the answers actually spoken were
                        # 29-182 tokens. One question consumed ~2400
                        # tokens, so only ~2.6 questions fit into
                        # Groq's 8000/min limit - after that every
                        # call was throttled, hit the 15s timeout,
                        # and the user got "assistant is currently
                        # busy". 320 is twice the longest answer
                        # measured.
                        max_tokens=320,
                        temperature=0.1,
                        **extra
                    )
                ),
                timeout=15.0
            )
            # Tags first: clean_for_tts strips underscores and would
            # turn [PHONE_1] into something no longer recognised.
            answer = unmask_phone_numbers(
                response.choices[0].message.content or "",
                phone_numbers,
                language,
            )
            return speak_phone_numbers(clean_for_tts(answer), language)

        except asyncio.TimeoutError:
            log.warning(f"{model_name} timed out ({attempt + 1}/{len(chain)}).")
            continue

        except Exception as e:
            if _is_rate_limited(e):
                log.warning(
                    f"{model_name} is out of budget - trying the next model"
                )
                continue
            log.error(f"Groq error ({model_name}): {e}")
            return "Sorry, I'm having trouble reaching the assistant service right now — please try again in a moment."

    return "Sorry, the assistant is currently busy. Please try asking again shortly."