"""
Piper text-to-speech.

tts_converter() used to build the audio for the whole answer before
returning. On CPU a long answer took 1.5-2 seconds, and the user heard
nothing at all through it.

The caller (voice_pipeline.py) now splits the answer into sentences
with split_sentences() and runs tts_converter() on each one, so the
first sentence starts playing in ~400ms. Lock and generation tracking
happen in that same loop, which made this more flexible than a
generator function.
"""

import io
import os
import re

from piper import PiperVoice
from piper.config import SynthesisConfig

# The same switch that tells Whisper which language to expect
# (sst_whisper.py's STT_LANGUAGE) also picks which voice speaks the
# answer back. One setting turns the whole conversation from English
# to Urdu instead of three separate ones that could drift out of
# sync with each other.
_LANGUAGE = os.getenv("STT_LANGUAGE", "en").strip().lower()

_VOICE_FILES = {
    "en": "en_US-lessac-medium.onnx",
    "ur": "ur_PK-fasih-medium.onnx",
}

_voice_file = _VOICE_FILES.get(_LANGUAGE, _VOICE_FILES["en"])

voice = PiperVoice.load(
    f"backend/microservices/livekit_Rag_services/audio_models/{_voice_file}"
)

_CONFIG = SynthesisConfig(length_scale=1)

# Where a sentence ends. The lookbehind/lookahead keep it from
# breaking on decimals (3.5) or common abbreviations (Mr. Dr.) - but
# only for English, because that check asks "is the next character an
# UPPERCASE Latin letter or a digit?". Urdu script has no concept of
# uppercase at all, so for an Urdu answer that check never once
# matched: the whole reply came back as a single unsplit "sentence",
# and speak_text() lost the entire point of splitting it - the first
# sentence could no longer start playing before the rest of the
# answer had even finished being written by the LLM.
#
# Matching any non-ASCII character as well (Urdu, Arabic, or any
# other non-Latin script) fixes that without loosening the English
# guard - a lowercase English letter still fails both checks, so
# "Mr. Ahmed" still will not split.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?۔؟])\s+(?=[A-Z0-9]|[^\x00-\x7F])")

# Do not play fragments smaller than this on their own - the audio
# sounds chopped up.
_MIN_CHUNK_CHARS = 24


def split_sentences(text: str) -> list[str]:
    """Split an answer into sentences that can be spoken."""
    text = (text or "").strip()
    if not text:
        return []

    parts = [p.strip() for p in _SENTENCE_SPLIT.split(text) if p.strip()]

    # bohat chhote tukde agle ke saath mila dein
    merged: list[str] = []
    for part in parts:
        if merged and len(merged[-1]) < _MIN_CHUNK_CHARS:
            merged[-1] = f"{merged[-1]} {part}"
        else:
            merged.append(part)
    return merged


def _synth(text: str) -> bytes:
    buffer = io.BytesIO()
    for chunk in voice.synthesize(text, syn_config=_CONFIG):
        buffer.write(chunk.audio_int16_bytes)
    return buffer.getvalue()


def tts_converter(text: str) -> bytes:
    """Poore jawab ka audio ek saath (purana behaviour)."""
    if not text or not text.strip():
        return b""
    return _synth(text.strip())
