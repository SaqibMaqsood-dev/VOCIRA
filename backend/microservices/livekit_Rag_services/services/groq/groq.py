import os

from groq import Groq

from backend.microservices.livekit_Rag_services.core.config import settings


client = Groq(
    api_key=settings.returning_groq_api
)


# =========================================================
# MODELS
# =========================================================
#
# Pehle har call "openai/gpt-oss-20b" par jati thi. Wo ek
# reasoning model hai - sirf "RAG_QUERY" jaisa teen-lafzi
# jawab dene ke liye bhi sainkron tokens ki soch likhta hai.
# Natija: daily token limit (200k) chand calls mein khatam,
# aur poora assistant chup ho jata hai.
#
# Ab do model:
#
#   FAST  - intent routing jaisi chhoti classification ke liye
#   SMART - ERP query plan aur insani jawab ke liye
#
# Dono env se badle ja sakte hain.
# =========================================================

# Ye naam is account par asal mein available models se chune gaye
# hain (test_models.py se benchmark kiye gaye - dono 3/3 sahi).
# Account par koi llama model maujood NAHI hai.
GROQ_FAST_MODEL = os.getenv(
    "GROQ_FAST_MODEL",
    "qwen/qwen3.8-27b",
)

GROQ_SMART_MODEL = os.getenv(
    "GROQ_SMART_MODEL",
    "openai/gpt-oss-120b",
)


async def dataConverter(
    prompt: str,
    model: str | None = None,
    max_tokens: int = 1024,
):
    """
    Groq se jawab lein.

    model = None  ->  SMART model (query plan, insani jawab)
    model = GROQ_FAST_MODEL  ->  chhoti classification ke liye
    """

    selected_model = model or GROQ_SMART_MODEL

    kwargs = {
        "model": selected_model,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
        "temperature": 0,
        # Bina hadd ke reasoning models poora din ka
        # token budget kha jate hain.
        "max_tokens": max_tokens,
    }

    # gpt-oss reasoning models hain. Bina is flag ke ye sirf
    # "RAG_QUERY" lautane ke liye bhi sainkron lafzon ki soch
    # likhte hain - yahi cheez daily quota kha gayi thi.
    if "gpt-oss" in selected_model:
        kwargs["reasoning_effort"] = "low"

    try:

        response = client.chat.completions.create(**kwargs)

        # ==================================================
        # DEBUG GROQ RESPONSE
        # ==================================================

        print("=" * 70)
        print("🤖 [GROQ RESPONSE]")
        print(
            f"Model: {selected_model}"
        )

        usage = getattr(
            response,
            "usage",
            None,
        )

        if usage:
            print(
                f"Tokens: "
                f"prompt={usage.prompt_tokens} "
                f"completion={usage.completion_tokens} "
                f"total={usage.total_tokens}"
            )

        if response.choices:

            choice = response.choices[0]

            print(
                f"Finish reason: "
                f"{choice.finish_reason}"
            )

            print(
                f"Content repr: "
                f"{repr(choice.message.content)}"
            )

        print("=" * 70)

        return response

    except Exception as exc:

        print("=" * 70)
        print("❌ [GROQ ERROR]")
        print(f"Model: {selected_model}")
        print(f"Error: {exc}")
        print("=" * 70)

        raise
