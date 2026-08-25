# Groq reasoning
import asyncio
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from groq import Groq
from backend.microservices.livekit_Rag_services.services.rag_engine.config import (
    GROQ_API_KEY, GROQ_MODEL, MAX_CONTEXT_CHARS, PINECONE_NAMESPACE
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


async def search_knowledge_base(retriever, query: str):
    """Fetch relevant chunks from Pinecone asynchronously with namespace isolation."""
    try:
        if not retriever:
            return "Retriever is not initialized. Please run /sync-database first.", []

        loop = asyncio.get_running_loop()
        docs = await loop.run_in_executor(_retrieval_executor, retriever.invoke, query)

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


async def ask_vocira(retriever, user_query: str):
    """Core RAG logic — async, non-blocking, returns a single string answer."""
    context, _ = await search_knowledge_base(retriever, user_query)

    if not context.strip():
        return "I'm sorry, I couldn't find any verified information about this in the school records."

    if len(context) > MAX_CONTEXT_CHARS:
        context = context[:MAX_CONTEXT_CHARS] + "\n...[truncated]"

    system_prompt = f"""You are Vocira, the official AI Assistant for 'The Educators'.
Use the following verified context to answer the user's question.

RULES:
1. Be concise, helpful, and professional.
2. If the context does not contain the answer, politely say you don't have that information.
3. Never make up facts.
4. For admission-related questions, always provide complete step-by-step details including requirements, process, and any tests or documents needed.
5. Never give a partial answer — if information exists in context, give it fully.
6. This answer will be converted to speech. Do NOT use markdown, asterisks, bold/italic markers, numbered lists (1. 2. 3.), or bullet points (-). Write in plain, natural spoken sentences only — if listing multiple items, describe them in flowing sentence form (e.g. "First... then... and finally...") instead of a numbered/bulleted list.

CONTEXT:
{context}"""

    groq_client = Groq(api_key=GROQ_API_KEY)

    for attempt in range(2):
        try:
            loop = asyncio.get_running_loop()
            response = await asyncio.wait_for(
                loop.run_in_executor(
                    _groq_executor,
                    lambda: groq_client.chat.completions.create(
                        model=GROQ_MODEL,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user",   "content": user_query}
                        ],
                        max_tokens=1000,
                        temperature=0.1
                    )
                ),
                timeout=15.0
            )
            return clean_for_tts(response.choices[0].message.content)

        except asyncio.TimeoutError:
            log.warning(f"Groq call timed out (attempt {attempt + 1}/2).")
            continue

        except Exception as e:
            status = getattr(e, "status_code", None)
            if status in (503, 429):
                log.warning(f"API rate limited (HTTP {status}). Retry {attempt + 1}/2...")
                await asyncio.sleep(2 * (attempt + 1))
                continue
            log.error(f"Groq error: {e}")
            return "Sorry, I'm having trouble reaching the assistant service right now — please try again in a moment."

    return "Sorry, the assistant is currently busy. Please try asking again shortly."