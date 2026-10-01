# Groq reasoning
import asyncio
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from openai import AsyncOpenAI
from backend.microservices.livekit_Rag_services.services.rag_engine.config import (
    GROQ_MODEL, MAX_CONTEXT_CHARS, PINECONE_NAMESPACE
)
# The same client the rest of the system uses, so the provider is
# switched from one place. There was a separate Groq client here
# before, so when gpt-oss-20b ran out of quota, ERP kept working
# while RAG answered "assistant is currently busy" every time.
from backend.microservices.livekit_Rag_services.services.groq.groq import (
    LLM_BASE_URL,
    _API_KEY,
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
# "0423-8050005", "0423 8050005", "04238050005" - or with a country
# code: "+92 300 1234567", "+44-20-7946-0958", "+923001234567".
# A full stop or comma after it ends the sentence - only one followed
# by another digit ("7,000", "3.5") makes it part of a bigger number.
_PHONE = re.compile(
    r"(?<!\d)(?<!\d[,.])"
    r"(?:\+\d{1,3}(?:[-\s]\d{2,12}){1,5}|\+\d{8,15}"
    r"|0\d{2,4}(?:[-\s]\d{3,8})+|0\d{9,11})"
    r"(?!\d|[,.]\d)"
)

_PLUS = {"en": "plus", "ur": "پلس"}

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
    return _PHONE.sub(lambda match: speak_phone_number(match.group(0), language), text)


def speak_phone_number(number: str, language: str) -> str:
    """
    One phone number, however it is written ("+92 300 1234567",
    "(042) 111-777-800", "042.111.777.800"), read out digit by digit -
    a short pause (comma) between its groups, "plus" for a leading +.
    """
    words = _DIGIT_WORDS.get(language, _DIGIT_WORDS["en"])
    sep = "، " if language == "ur" else ", "
    groups = [" ".join(words[int(d)] for d in g) for g in re.split(r"\D+", number or "") if g]
    if groups and (number or "").strip().startswith("+"):
        groups[0] = f"{_PLUS.get(language, _PLUS['en'])} {groups[0]}"
    return sep.join(groups)


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


@dataclass
class RagPrompt:
    """What an answer is written from: Vocira's rules and the school's context."""

    system_prompt: str
    phone_numbers: dict[str, str]
    language: str
    user_query: str


async def prepare_rag(
    retriever,
    user_query: str,
    language: str | None = None,
    search_query: str | None = None,
    school_name: str = "The Educators",
):
    """
    Search the school's knowledge and write the prompt an answer is made
    from - a RagPrompt, or the reply itself (a string) when nothing in the
    knowledge relates to the question.

    `search_query` is the router's plain-English restatement of the
    question (it costs no extra call - the router writes it anyway).

    `retriever` searches one school's namespace, and `school_name` is
    that school's - the same agent answers for every school.
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

    system_prompt = f"""You are Vocira, the official AI Assistant for '{school_name}'.
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

    return RagPrompt(
        system_prompt=system_prompt,
        phone_numbers=phone_numbers,
        language=language,
        user_query=user_query,
    )


async def ask_vocira(
    retriever,
    user_query: str,
    language: str | None = None,
    search_query: str | None = None,
    school_name: str = "The Educators",
):
    """
    Core RAG logic — async, non-blocking, returns a single string answer.
    (stream_vocira gives the same answer a sentence at a time.)
    """
    prepared = await prepare_rag(retriever, user_query, language, search_query, school_name)
    if isinstance(prepared, str):
        return prepared
    system_prompt, phone_numbers, language = prepared.system_prompt, prepared.phone_numbers, prepared.language

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


# ---------------------------------------------------------
# The same answer, a sentence at a time
# ---------------------------------------------------------

_async_llm: AsyncOpenAI | None = None


def _async_client() -> AsyncOpenAI:
    """Made on first use, on the loop that uses it (the voice agent's brain loop)."""
    global _async_llm
    if _async_llm is None:
        _async_llm = AsyncOpenAI(api_key=_API_KEY, base_url=LLM_BASE_URL)
    return _async_llm


# Where a sentence ends - the rule Piper's splitter uses (text_speech/
# piper_servies.py): . ! ? or Urdu's ۔ ؟, then a capital, a digit or any
# non-Latin letter, so "Mr. Ahmed" and "3.5" stay whole.
_SENTENCE_END = re.compile(r"(?<=[.!?۔؟])\s+(?=[A-Z0-9]|[^\x00-\x7F])")

# shorter pieces are joined to the next - spoken alone they sound chopped
_MIN_SPOKEN_CHARS = 24

# A sentence longer than this is spoken in parts, cut after a comma: nothing
# is heard until the first part is synthesized (~6 ms a character on this
# machine), and one 278-character sentence kept a caller waiting 1.8 s for
# it. Later parts are made while the one before plays, so only the first
# has to be short.
_FIRST_SPOKEN_MAX = 90
_SPOKEN_MAX = 220
_CLAUSE_END = re.compile(r"(?<=[,;:،؛])\s+")


def _clause_cut(text: str, start: int) -> tuple[int, int] | None:
    """Where to cut `text` after its last comma (or ; : ، ؛) past `start`."""
    cut = None
    for match in _CLAUSE_END.finditer(text):
        if match.start() >= start:
            cut = (match.start(), match.end())
    return cut


async def stream_vocira(prepared: RagPrompt):
    """
    The answer as the model writes it, one finished sentence at a time - so
    the first sentence can be spoken while the rest is still being written,
    instead of after the whole answer. Each sentence is finished exactly as
    ask_vocira finishes its whole answer: phone tags back to numbers read
    digit by digit, markdown stripped.
    """
    language = prepared.language

    def finish(text: str) -> str:
        # tags first: clean_for_tts strips underscores and would break [PHONE_1]
        text = unmask_phone_numbers(text, prepared.phone_numbers, language)
        return speak_phone_numbers(clean_for_tts(text), language)

    for attempt, model_name in enumerate(_model_chain(GROQ_MODEL)):
        extra = {"reasoning_effort": "low"} if "gpt-oss" in model_name else {}
        spoken = False
        try:
            stream = await asyncio.wait_for(
                _async_client().chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": prepared.system_prompt},
                        {"role": "user", "content": prepared.user_query},
                    ],
                    max_tokens=320,
                    temperature=0.1,
                    stream=True,
                    **extra,
                ),
                timeout=15.0,
            )
            buffer, pending = "", ""
            async for chunk in stream:
                if not chunk.choices:
                    continue
                buffer += chunk.choices[0].delta.content or ""
                *ready, buffer = _SENTENCE_END.split(buffer)
                for sentence in ready:
                    pending = f"{pending} {sentence}".strip() if pending else sentence
                    if len(pending) >= _MIN_SPOKEN_CHARS:
                        if text := finish(pending):
                            spoken = True
                            yield text
                        pending = ""
                if len(pending) + len(buffer) > (_SPOKEN_MAX if spoken else _FIRST_SPOKEN_MAX):
                    cut = _clause_cut(buffer, start=max(0, _MIN_SPOKEN_CHARS - len(pending)))
                    if cut:
                        part = f"{pending} {buffer[:cut[0]]}".strip()
                        buffer, pending = buffer[cut[1]:], ""
                        if text := finish(part):
                            spoken = True
                            yield text
            rest = f"{pending} {buffer}".strip()
            if rest and (text := finish(rest)):
                spoken = True
                yield text
            return

        except asyncio.TimeoutError:
            log.warning(f"{model_name} timed out ({attempt + 1}).")
            if spoken:
                return
            continue

        except Exception as e:
            if spoken:
                # half an answer has been spoken - another model cannot continue it
                log.error(f"Groq stream broke off ({model_name}): {e}")
                return
            if _is_rate_limited(e):
                log.warning(f"{model_name} is out of budget - trying the next model")
                continue
            log.error(f"Groq error ({model_name}): {e}")
            yield "Sorry, I'm having trouble reaching the assistant service right now — please try again in a moment."
            return

    yield "Sorry, the assistant is currently busy. Please try asking again shortly."
