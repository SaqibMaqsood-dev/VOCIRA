"""
Thori der ke liye jawab yaad rakhein.

Kyun: Groq ki hadd tokens-per-MINUTE par hai. Ek hi sawal dobara
poochne par poora kharcha dobara lagta tha - router, ERP, aur jawab
banane wali LLM call. Demo ke dauran ye aam baat hai (jab jawab theek
se sunai na de, ya koi doosra bandah wahi sawal poochay).

EHTIYAT:

  - Key mein user_id shaamil hai. Ek parent ka jawab kabhi doosre ko
    nahi milta - yehi is cache ki sab se ahem shart hai.
  - TTL chhota (2 minute). Fees ya attendance itni der mein nahi
    badalti, magar agli call par taaza data mil jata hai.
  - Ghalti wale jawab ("records tak pahunch nahi") kabhi yaad nahi
    rakhe jate - warna ek waqti kharabi do minute tak chipki rehti.
"""

import re
import time


TTL_SECONDS = 120

# Bounded - warna lambi call mein memory barhti rehti hai
MAX_ENTRIES = 200

# Ye jawab yaad NAHI rakhne - waqti kharabi ki nishani hain
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
    "Have my fees been paid?" aur "have my fees been paid"
    ek hi cheez hain.
    """
    text = question.lower().strip()
    text = re.sub(r"[^\w\s]", "", text)
    return re.sub(r"\s+", " ", text)


def _key(user_id, question: str) -> tuple[str, str]:
    # user_id None (guest) apni alag bucket hai
    return (str(user_id), _normalise(question))


def get(user_id, question: str) -> str | None:
    """Yaad hai to jawab dein, warna None."""

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
    """Jawab yaad rakhein. Rakha gaya ya nahi, wo batata hai."""

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
