"""
Remember answers for a short while.

Why: Groq's limit is on tokens-per-MINUTE. Asking the same question
twice used to cost the full round trip again - router, ERP, and the
LLM call that writes the answer. During a demo that happens often
(when an answer was not heard clearly, or someone else asks the same
thing).

CARE TAKEN:

  - The key includes user_id. One parent's answer never reaches
    another - the most important condition on this cache.
  - The TTL is short (2 minutes). Fees and attendance do not change
    in that time, and the next call gets fresh data anyway.
  - Error answers ("cannot reach the records") are never remembered -
    otherwise one temporary fault would stick around for two
    minutes.
"""

import re
import time


TTL_SECONDS = 120

# Bounded - otherwise memory grows through a long call
MAX_ENTRIES = 200

# Answers NOT to remember - they signal a temporary fault
_DO_NOT_CACHE = (
    "cannot reach",
    "having trouble",
    "try again",
    "unable",
    "currently busy",
    "connecting you to",
)

_store: dict[tuple[str, str], tuple[float, str]] = {}


def _normalise(question: str) -> str:
    """
    "Have my fees been paid?" and "have my fees been paid"
    are the same thing.
    """
    text = question.lower().strip()
    text = re.sub(r"[^\w\s]", "", text)
    return re.sub(r"\s+", " ", text)


def _key(user_id, question: str) -> tuple[str, str]:
    # a user_id of None (guest) gets its own bucket
    return (str(user_id), _normalise(question))


def get(user_id, question: str) -> str | None:
    """Return the remembered answer, or None."""

    if not question:
        return None

    key = _key(user_id, question)
    found = _store.get(key)

    if not found:
        return None

    stored_at, answer = found

    if time.monotonic() - stored_at > TTL_SECONDS:
        _store.pop(key, None)
        return None

    return answer


def put(user_id, question: str, answer: str) -> bool:
    """Remember an answer. Reports whether it was stored."""

    if not question or not answer:
        return False

    low = answer.lower()

    for phrase in _DO_NOT_CACHE:
        if phrase in low:
            return False

    if len(_store) >= MAX_ENTRIES:
        # sab se purana nikaal dein
        oldest = min(_store, key=lambda k: _store[k][0])
        _store.pop(oldest, None)

    _store[_key(user_id, question)] = (time.monotonic(), answer)
    return True


def clear() -> None:
    """Tests ke liye."""
    _store.clear()
