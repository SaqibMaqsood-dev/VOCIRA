"""
Turning an LLM answer into text that is safe to speak.

Two things the model cannot be trusted with:

  Urdu numbers. Urdu has a separate word for every number up to 99,
  and the model gets them wrong - 76 came out as "ستائیس چھ" and 84
  as "اسیٹھ چار", so a parent heard the wrong marks. The model now
  writes digits and they are spelled here, from a fixed table.

  Stopping. A weaker fallback model once repeated "چالیس سے زیادہ
  نہیں" until it ran out of tokens, and the caller heard that loop.
"""

import re

_UR_0_99 = (
    "صفر ایک دو تین چار پانچ چھ سات آٹھ نو "
    "دس گیارہ بارہ تیرہ چودہ پندرہ سولہ سترہ اٹھارہ انیس "
    "بیس اکیس بائیس تئیس چوبیس پچیس چھبیس ستائیس اٹھائیس انتیس "
    "تیس اکتیس بتیس تینتیس چونتیس پینتیس چھتیس سینتیس اڑتیس انتالیس "
    "چالیس اکتالیس بیالیس تینتالیس چوالیس پینتالیس چھیالیس سینتالیس اڑتالیس انچاس "
    "پچاس اکاون باون ترپن چون پچپن چھپن ستاون اٹھاون انسٹھ "
    "ساٹھ اکسٹھ باسٹھ ترسٹھ چونسٹھ پینسٹھ چھیاسٹھ سڑسٹھ اڑسٹھ انہتر "
    "ستر اکہتر بہتر تہتر چوہتر پچھتر چھہتر ستتر اٹھہتر اناسی "
    "اسی اکیاسی بیاسی تراسی چوراسی پچاسی چھیاسی ستاسی اٹھاسی نواسی "
    "نوے اکانوے بانوے ترانوے چورانوے پچانوے چھیانوے ستانوے اٹھانوے ننانوے"
).split()

_UR_MONTHS = (
    "جنوری فروری مارچ اپریل مئی جون جولائی اگست ستمبر اکتوبر نومبر دسمبر"
).split()

# The model sometimes writes Urdu digits (۷۶) instead of 76.
_URDU_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

_ISO_DATE = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)")
_CLOCK = re.compile(r"(?<!\d)(\d{1,2}):(\d{2})(?!\d)")
_RANGE = re.compile(r"(?<![\d.,])(\d+)\s*[-–]\s*(\d+)(?![\d.,])")
_NUMBER = re.compile(r"(?<![\d.,])(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?(?![\d,]|\.\d)(?:\s?(%))?")


def urdu_number(n: int) -> str:
    """76 -> "چھہتر", 2026 -> "دو ہزار چھبیس", 10500 -> "دس ہزار پانچ سو"."""
    if n < 100:
        return _UR_0_99[n]
    for size, word in ((10_000_000, "کروڑ"), (100_000, "لاکھ"), (1000, "ہزار"), (100, "سو")):
        if n >= size:
            head, rest = divmod(n, size)
            spoken = f"{urdu_number(head)} {word}"
            return f"{spoken} {urdu_number(rest)}" if rest else spoken
    return str(n)


def _speak_number(match: re.Match) -> str:
    whole, fraction, percent = match.group(1), match.group(2), match.group(3)
    spoken = urdu_number(int(whole.replace(",", "")))
    if fraction and fraction.strip("0"):
        spoken += " اعشاریہ " + " ".join(_UR_0_99[int(d)] for d in fraction.rstrip("0"))
    if percent:
        spoken += " فیصد"
    return spoken


def _speak_date(match: re.Match) -> str:
    year, month, day = (int(g) for g in match.groups())
    if not 1 <= month <= 12:
        return match.group(0)
    return f"{urdu_number(day)} {_UR_MONTHS[month - 1]} {urdu_number(year)}"


def _speak_clock(match: re.Match) -> str:
    hour, minute = int(match.group(1)), int(match.group(2))
    if minute == 0:
        return f"{urdu_number(hour)} بجے"
    return f"{urdu_number(hour)} بج کر {urdu_number(minute)} منٹ"


def speak_numbers(text: str, language: str | None) -> str:
    """Spell every number in an Urdu answer. English answers are left alone."""
    if (language or "").strip().lower() != "ur" or not text:
        return text
    text = text.translate(_URDU_DIGITS)
    text = _ISO_DATE.sub(_speak_date, text)
    text = _CLOCK.sub(_speak_clock, text)
    text = _RANGE.sub(r"\1 سے \2", text)
    return _NUMBER.sub(_speak_number, text)


_CLAUSE = re.compile(r"[^،,؛;۔.!?؟\n]+[،,؛;۔.!?؟\n]*")
_SENTENCE_END = re.compile(r"[۔.!?؟]")


def drop_repetition(text: str) -> str:
    """
    Cut the answer where it starts going round in a loop.

    Only a loop counts - the same clause twice in a row (A, A) or two
    clauses taking turns (A, B, A, B). A clause coming back later is
    normal: "درجہ سی" follows every subject graded C.
    """
    keys, kept = [], []
    looped = False
    for clause in _CLAUSE.findall(text or ""):
        key = " ".join(clause.strip(" \n،,؛;۔.!?؟").split())
        if len(key.split()) >= 2 and keys and key == keys[-1]:
            looped = True
        elif len(keys) >= 3 and key == keys[-2] and keys[-1] == keys[-3]:
            kept.pop()
            looped = True
        if looped:
            break
        keys.append(key)
        kept.append(clause)
    if not kept:
        return (text or "").strip()
    out = "".join(kept).strip()
    if looped:
        out = out.rstrip(" ،,؛;")
        if not _SENTENCE_END.search(out[-1:]):
            out += "۔" if re.search(r"[؀-ۿ]", out) else "."
    return out


def end_at_sentence(text: str) -> str:
    """An answer cut off by the token limit ends at its last full sentence."""
    ends = list(_SENTENCE_END.finditer(text))
    return text[: ends[-1].end()].strip() if ends else text.strip()


def finish_answer(text: str, language: str | None, cut_off: bool = False) -> str:
    """Everything an ERP answer needs before it is spoken."""
    # Imported here: query.py pulls in the vector store, which this
    # small module should not load just to be imported.
    from backend.microservices.livekit_Rag_services.services.rag_engine.query import (
        clean_for_tts,
        speak_phone_numbers,
    )

    text = drop_repetition(text)
    if cut_off:
        text = end_at_sentence(text)
    # Numbers before clean_for_tts: it drops "76." at the start of a
    # line as if it were a list number.
    text = speak_phone_numbers(text, language or "en")
    text = speak_numbers(text, language)
    # A paragraph break after a finished sentence is just a space -
    # clean_for_tts would add a second full stop ("۔.").
    text = re.sub(r"([۔.!?؟])\s*\n+\s*", r"\1 ", text)
    return clean_for_tts(text)
