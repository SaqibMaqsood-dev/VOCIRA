"""
LLM client — provider .env se badla ja sakta hai.

Groq aur OpenRouter dono OpenAI-compatible hain, is liye ek hi client
dono ke liye kaafi hai. Sirf base_url aur key badalti hai:

    # Groq - sab se tez, magar free tier ka daily token limit
    LLM_BASE_URL=https://api.groq.com/openai/v1
    LLM_API_KEY=gsk_...
    LLM_FAST_MODEL=qwen/qwen3.8-27b
    LLM_SMART_MODEL=openai/gpt-oss-120b

    # OpenRouter - thora slow, magar quota ki tang nahi
    LLM_BASE_URL=https://openrouter.ai/api/v1
    LLM_API_KEY=sk-or-v1-...
    LLM_FAST_MODEL=google/gemini-2.5-flash-lite
    LLM_SMART_MODEL=google/gemini-2.5-flash

Do model isliye hain:
  FAST  - intent routing jaisi chhoti classification
  SMART - jawab banana aur ERP query planning

Pehle har call "openai/gpt-oss-20b" par jati thi, jo reasoning model
hai - "RAG_QUERY" jaisa teen-lafzi jawab dene ke liye bhi sainkron
tokens ki soch likhta tha, aur daily quota chand calls mein khatam
ho jata tha.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

# Apni .env khud load karein.
#
# Pehle ye module core.config se settings import karta tha, aur wahan
# load_dotenv chalta tha - yaani env load hone ka inhesaar is baat par
# tha ke core.config PEHLE import ho. Jab is module ko akela import
# kiya jata (misal test se) to koi key hi na milti aur OpenAI client
# banate hi crash ho jata.
#
# load_dotenv pehle se set variables ko override nahi karta, is liye
# dobara chalne se koi nuqsan nahi.
_SERVICE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(_SERVICE_DIR / ".env")

# GROQ_API_KEY purani .env files ke liye fallback ke taur par
_API_KEY = (
    os.getenv("LLM_API_KEY")
    or os.getenv("GROQ_API_KEY")
    or ""
)

LLM_BASE_URL = os.getenv(
    "LLM_BASE_URL",
    "https://api.groq.com/openai/v1",
)

client = OpenAI(
    api_key=_API_KEY,
    base_url=LLM_BASE_URL,
)

GROQ_FAST_MODEL = os.getenv("LLM_FAST_MODEL") or os.getenv(
    "GROQ_FAST_MODEL", "qwen/qwen3.8-27b"
)

GROQ_SMART_MODEL = os.getenv("LLM_SMART_MODEL") or os.getenv(
    "GROQ_SMART_MODEL", "openai/gpt-oss-120b"
)

# saaf naam, purane bhi chalte rahenge
LLM_FAST_MODEL = GROQ_FAST_MODEL
LLM_SMART_MODEL = GROQ_SMART_MODEL


# =========================================================
# BACKUP MODELS
#
# Groq par har model ka APNA rozana budget hai (tokens per day aur
# requests per day). Ek model khatam ho jaye to baqi ke paas budget
# bacha hota hai - magar pehle poora system ruk jata tha aur user ko
# "assistant is currently busy" milta tha, halanke doosra model
# bilkul tayyar tha.
#
# Ab 429 (rate limit) par agla model try hota hai. Tarteeb: pehle wo
# jo mangaya gaya, phir ye.
# =========================================================

_DEFAULT_FALLBACKS = "openai/gpt-oss-20b,qwen/qwen3.8-27b,openai/gpt-oss-120b"

LLM_FALLBACK_MODELS = [
    m.strip()
    for m in os.getenv("LLM_FALLBACK_MODELS", _DEFAULT_FALLBACKS).split(",")
    if m.strip()
]


def _is_rate_limited(error: Exception) -> bool:
    """429 / quota khatam - doosre model par jane ke qabil ghalti."""

    if getattr(error, "status_code", None) == 429:
        return True

    text = str(error).lower()

    return (
        "rate_limit" in text
        or "rate limit" in text
        or "tokens per day" in text
        or "tpd" in text
    )


def _model_chain(selected: str) -> list[str]:
    """Jo model manga gaya wo pehle, phir backup - bina dohraav."""

    chain = [selected]

    for m in LLM_FALLBACK_MODELS:
        if m not in chain:
            chain.append(m)

    return chain


async def dataConverter(
    prompt: str,
    model: str | None = None,
    max_tokens: int = 1024,
):
    """
    LLM se jawab lein.

    model = None             -> SMART model
    model = LLM_FAST_MODEL   -> chhoti classification ke liye

    Model ka rozana budget khatam ho to khud backup model par
    chala jata hai.
    """

    chain = _model_chain(model or GROQ_SMART_MODEL)
    last_error: Exception | None = None

    for attempt, selected_model in enumerate(chain):

        kwargs = {
            "model": selected_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "max_tokens": max_tokens,
        }

        # gpt-oss reasoning models hain. Bina is flag ke ye jawab se kai
        # guna zyada tokens sirf "sochne" par kharch karte hain.
        if "gpt-oss" in selected_model:
            kwargs["reasoning_effort"] = "low"

        try:
            response = client.chat.completions.create(**kwargs)

        except Exception as exc:

            last_error = exc

            if _is_rate_limited(exc) and attempt + 1 < len(chain):
                print(
                    f"⚠️ [LLM] {selected_model} ka budget khatam - "
                    f"{chain[attempt + 1]} par ja rahe hain"
                )
                continue

            print("=" * 70)
            print("❌ [LLM ERROR]")
            print(f"Provider: {LLM_BASE_URL}")
            print(f"Model: {selected_model}")
            print(f"Error: {exc}")
            print("=" * 70)
            raise

        return _log_and_return(response, selected_model)

    raise last_error  # pragma: no cover - chain kabhi khali nahi hoti


def _log_and_return(response, selected_model):
    """Sirf logging - jawab waisa ka waisa wapis."""

    try:

        print("=" * 70)
        print("🤖 [LLM RESPONSE]")
        print(f"Model: {selected_model}")

        usage = getattr(response, "usage", None)
        if usage:
            print(
                f"Tokens: prompt={usage.prompt_tokens} "
                f"completion={usage.completion_tokens} "
                f"total={usage.total_tokens}"
            )

        if response.choices:
            choice = response.choices[0]
            print(f"Finish reason: {choice.finish_reason}")
            print(f"Content repr: {repr(choice.message.content)}")

        print("=" * 70)

    except Exception as log_error:
        # Logging kabhi asli jawab ke raaste mein na aaye
        print(f"⚠️ [LLM] log fail: {log_error}")

    return response
