"""
LLM client — the provider is switched from .env.

Groq and OpenRouter are both OpenAI-compatible, so one client covers
both. Only the base_url and the key change:

    # Groq - fastest, but the free tier has a daily token limit
    LLM_BASE_URL=https://api.groq.com/openai/v1
    LLM_API_KEY=gsk_...
    LLM_FAST_MODEL=qwen/qwen3.8-27b
    LLM_SMART_MODEL=openai/gpt-oss-120b

    # OpenRouter - a little slower, but no quota pressure
    LLM_BASE_URL=https://openrouter.ai/api/v1
    LLM_API_KEY=sk-or-v1-...
    LLM_FAST_MODEL=google/gemini-2.5-flash-lite
    LLM_SMART_MODEL=google/gemini-2.5-flash

There are two models because:
  FAST  - small classification such as intent routing
  SMART - writing answers and planning ERP queries

Every call used to go to "openai/gpt-oss-20b", a reasoning model - it
wrote hundreds of tokens of thinking even to produce a three-word
answer like "RAG_QUERY", and burned through the daily quota in a
handful of calls.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

# Load our own .env.
#
# This module used to import settings from core.config, where
# load_dotenv ran - meaning the env only loaded if core.config was
# imported FIRST. Importing this module on its own (from a test, for
# instance) found no key at all and crashed while building the
# OpenAI client.
#
# load_dotenv does not override variables that are already set, so
# running it again does no harm.
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

# clearer names; the old ones keep working
LLM_FAST_MODEL = GROQ_FAST_MODEL
LLM_SMART_MODEL = GROQ_SMART_MODEL


# =========================================================
# BACKUP MODELS
#
# On Groq every model has its OWN daily budget (tokens per day and
# requests per day). When one runs out the others still have budget
# left - but the whole system used to stop and hand the user
# "assistant is currently busy", while another model sat ready.
#
# On a 429 (rate limit) the next model is tried. Order: the one that
# was asked for first, then these.
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
    """The requested model first, then the backups - no duplicates."""

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
    model = LLM_FAST_MODEL   -> for small classification

    If a model's daily budget runs out, it falls through to a backup
    model on its own.
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

        # The gpt-oss models are reasoning models. Without this flag
        # they spend many times the answer's tokens just "thinking".
        if "gpt-oss" in selected_model:
            kwargs["reasoning_effort"] = "low"

        try:
            response = client.chat.completions.create(**kwargs)

        except Exception as exc:

            last_error = exc

            if _is_rate_limited(exc) and attempt + 1 < len(chain):
                print(
                    f"[LLM] {selected_model} is out of budget - "
                    f"moving to {chain[attempt + 1]}"
                )
                continue

            print("=" * 70)
            print("[LLM ERROR]")
            print(f"Provider: {LLM_BASE_URL}")
            print(f"Model: {selected_model}")
            print(f"Error: {exc}")
            print("=" * 70)
            raise

        return _log_and_return(response, selected_model)

    raise last_error  # pragma: no cover - the chain is never empty


def _log_and_return(response, selected_model):
    """Logging only - the response is returned untouched."""

    try:

        print("=" * 70)
        print("[LLM RESPONSE]")
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
        # Logging must never get in the way of the real answer
        print(f"[LLM] log fail: {log_error}")

    return response
