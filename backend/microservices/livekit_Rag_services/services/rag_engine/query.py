# Groq reasoning

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

from groq import Groq

from backend.microservices.livekit_Rag_services.services.rag_engine.config import (
    GROQ_API_KEY,
    GROQ_MODEL,
    MAX_CONTEXT_CHARS,
    PINECONE_NAMESPACE,
)


log = logging.getLogger(__name__)


# =========================================================
# Dedicated Thread Pools
# =========================================================

# Groq and Pinecone calls don't use the default shared pool.
# This prevents them from competing with background tasks.

_groq_executor = ThreadPoolExecutor(
    max_workers=10,
    thread_name_prefix="groq",
)

_retrieval_executor = ThreadPoolExecutor(
    max_workers=10,
    thread_name_prefix="retrieval",
)


# =========================================================
# Knowledge Base Search
# =========================================================

async def search_knowledge_base(
    retriever,
    query: str,
):
    """
    Retrieve relevant information from Pinecone.

    Returns:
        tuple[str, list[str]]:
            context and source list
    """

    try:

        if not retriever:

            return (
                "Retriever is not initialized. "
                "Please run /sync-database first.",
                [],
            )

        loop = asyncio.get_running_loop()

        documents = await loop.run_in_executor(
            _retrieval_executor,
            retriever.invoke,
            query,
        )

        if not documents:

            return "", []

        context_parts = []
        sources = set()

        for document in documents:

            if document.page_content:

                context_parts.append(
                    document.page_content
                )

            source = document.metadata.get(
                "source",
                "Internal Records",
            )

            sources.add(source)

        context = "\n".join(
            context_parts
        )

        return context, list(sources)

    except Exception as e:

        log.error(
            f"Knowledge base retrieval error: {e}",
            exc_info=True,
        )

        return (
            "Sorry, I'm having trouble accessing "
            "the school information right now.",
            [],
        )


# =========================================================
# RAG Response Generator
# =========================================================

async def ask_vocira(
    retriever,
    user_query: str,
):
    """
    Core VOCIRA RAG pipeline.

    Flow:

        User Query
            ↓
        Knowledge Base Retrieval
            ↓
        Verified Context
            ↓
        Groq
            ↓
        Natural Voice-Friendly Response

    Returns:
        str: Final AI response
    """

    # =====================================================
    # 1. Retrieve Knowledge
    # =====================================================

    context, _ = await search_knowledge_base(
        retriever,
        user_query,
    )

    # =====================================================
    # 2. No Relevant Context
    # =====================================================

    if not context.strip():

        return (
            "I'm sorry, I couldn't find any verified "
            "information about this in the school records."
        )

    # =====================================================
    # 3. Limit Context Size
    # =====================================================

    if len(context) > MAX_CONTEXT_CHARS:

        context = (
            context[:MAX_CONTEXT_CHARS]
            + "\n...[context truncated]"
        )

    # =====================================================
    # 4. RAG System Prompt
    # =====================================================

    system_prompt = f"""
You are Vocira, the official AI Assistant for The Educators.

Your job is to answer the user's question using ONLY the
verified information provided in the context below.

==================================================
CORE RULES
==================================================

1. Be professional, helpful, concise, and conversational.

2. Answer the user's question directly.

3. Use ONLY information available in the provided context.

4. Never invent, assume, or guess information.

5. If the context does not contain the answer, politely say:

"I'm sorry, I don't have that information available."

6. If the answer exists in the context, provide all relevant
information needed to properly answer the user's question.

7. Do not mention:
   - databases
   - SQL
   - Pinecone
   - retrieval
   - context
   - system prompts
   - internal processing

==================================================
ADMISSION QUESTIONS
==================================================

For admission-related questions, provide the complete
relevant information available in the context.

Include relevant details such as:

- admission requirements
- admission procedure
- admission tests
- subjects
- age criteria
- registration information
- required documents, if provided
- important admission notes

Do not omit relevant information that is available in
the verified context.

==================================================
VOICE RESPONSE RULES
==================================================

Your response will be sent directly to a Text-to-Speech
system.

Therefore, write the answer exactly as a person would
naturally speak it.

DO NOT use:

- Markdown
- asterisks
- bold text
- headings using # symbols
- Markdown tables
- bullet-point formatting
- numbered Markdown lists
- JSON
- code blocks
- horizontal lines
- unnecessary symbols

Return plain natural language.

==================================================
TIME FORMATTING
==================================================

Always make times natural and easy for speech.

Do NOT write:

8:00 AM

2:00 PM

7:55 AM

8:00 AM - 2:00 PM

Instead write:

eight in the morning

two in the afternoon

seven fifty-five in the morning

from eight in the morning until two in the afternoon

For example:

BAD:
"School hours are 8:00 AM - 2:00 PM."

GOOD:
"School hours are from eight in the morning until two
in the afternoon."

For a schedule with multiple days, speak naturally.

For example:

"From Monday to Friday, school runs from eight in the
morning until two in the afternoon. On Saturday, school
runs from eight in the morning until noon."

==================================================
NUMBERS
==================================================

Make numbers natural for speech whenever appropriate.

For example:

"1,000+ campuses"

can be spoken as:

"more than one thousand campuses"

"240,000+ students"

can be spoken as:

"more than two hundred and forty thousand students"

Do not unnecessarily spell every number if the natural
spoken form is already clear.

==================================================
CONTACT INFORMATION
==================================================

When speaking phone numbers, make them understandable.

For example, instead of reading a phone number as one
large number, separate it naturally into groups.

Do not read website formatting characters aloud.

If a website is relevant, say:

"The website is educators dot edu dot pk."

==================================================
RESPONSE STRUCTURE
==================================================

Prefer short natural paragraphs.

If the information contains a table, convert the table
into natural spoken sentences.

For example, if the context contains:

Monday-Friday: 8:00 AM - 2:00 PM
Saturday: 8:00 AM - 12:00 PM

respond:

"From Monday to Friday, school runs from eight in the
morning until two in the afternoon. On Saturday, school
runs from eight in the morning until noon."

Do not reproduce the table.

==================================================
PRIVATE AND SENSITIVE INFORMATION
==================================================

If the user asks for sensitive personal records such as:

- student grade sheets
- report cards
- individual fee payment history
- outstanding balances
- disciplinary records
- teacher personal contact numbers

do not provide the information.

Instead respond:

"I'm sorry, this information is sensitive. Please log in
to your portal to access personal records."

==================================================
FINAL RESPONSE RULE
==================================================

Return ONLY the final answer to the user.

Do not explain your reasoning.

Do not mention these instructions.

Do not mention the context.

Do not use Markdown.

==================================================
VERIFIED CONTEXT
==================================================

{context}
"""

    # =====================================================
    # 5. Groq Client
    # =====================================================

    groq_client = Groq(
        api_key=GROQ_API_KEY,
    )

    # =====================================================
    # 6. Generate Response
    # =====================================================

    for attempt in range(2):

        try:

            loop = asyncio.get_running_loop()

            response = await asyncio.wait_for(

                loop.run_in_executor(

                    _groq_executor,

                    lambda: groq_client.chat.completions.create(

                        model=GROQ_MODEL,

                        messages=[
                            {
                                "role": "system",
                                "content": system_prompt,
                            },
                            {
                                "role": "user",
                                "content": user_query,
                            },
                        ],

                        max_tokens=1000,

                        temperature=0.1,
                    ),
                ),

                timeout=15.0,
            )

            # =================================================
            # Extract Final Response
            # =================================================

            answer = (
                response
                .choices[0]
                .message
                .content
                .strip()
            )

            return answer

        # =====================================================
        # Timeout
        # =====================================================

        except asyncio.TimeoutError:

            log.warning(
                "Groq call timed out "
                f"(attempt {attempt + 1}/2)."
            )

            continue

        # =====================================================
        # Rate Limit / Temporary API Error
        # =====================================================

        except Exception as e:

            status = getattr(
                e,
                "status_code",
                None,
            )

            if status in (429, 503):

                log.warning(
                    f"Groq API temporarily unavailable "
                    f"(HTTP {status}). "
                    f"Retry {attempt + 1}/2..."
                )

                await asyncio.sleep(
                    2 * (attempt + 1)
                )

                continue

            # =================================================
            # Other Groq Error
            # =================================================

            log.error(
                f"Groq error: {e}",
                exc_info=True,
            )

            return (
                "Sorry, I'm having trouble reaching "
                "the assistant service right now. "
                "Please try again in a moment."
            )

    # =====================================================
    # All Attempts Failed
    # =====================================================

    return (
        "Sorry, the assistant is currently busy. "
        "Please try asking again shortly."
    )