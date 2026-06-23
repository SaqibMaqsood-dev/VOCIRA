#Groq reasoning

import time
import logging

from groq import Groq
from rag.config import GROQ_API_KEY, GROQ_MODEL, MAX_CONTEXT_CHARS

log = logging.getLogger(__name__)


def search_knowledge_base(retriever, query: str):
    """Fetch relevant chunks from Pinecone."""
    try:
        if not retriever:
            return "Retriever is not initialized. Please run /sync-database first.", []

        docs = retriever.invoke(query)
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
        return f"Database Error: {str(e)}", []


def ask_vocira(retriever, user_query: str):
    """Core RAG logic — retrieve context and generate answer via Groq."""
    context, _ = search_knowledge_base(retriever, user_query)

    # No context found — clean rejection
    if not context.strip():
        return "I'm sorry, I couldn't find any verified information about this in the school records."

    # Context window guard
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

CONTEXT:
{context}"""

    groq_client = Groq(api_key=GROQ_API_KEY)

    for attempt in range(3):
        try:
            response = groq_client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_query}
                ],
                max_tokens=1000,
                temperature=0.1
            )
            return response.choices[0].message.content

        except Exception as e:
            status = getattr(e, "status_code", None)
            if status in (503, 429):
                log.warning(f"API rate limited. Retry {attempt + 1}/3...")
                time.sleep(3 * (attempt + 1))
                continue
            log.error(f"Groq error: {e}")
            return f"Unexpected Error: {str(e)}"

    return "Service unavailable after 3 attempts. Please try again later."