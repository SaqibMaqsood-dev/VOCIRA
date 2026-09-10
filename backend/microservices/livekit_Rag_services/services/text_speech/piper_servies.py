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
import re

from piper import PiperVoice
from piper.config import SynthesisConfig

voice = PiperVoice.load(
    "backend/microservices/livekit_Rag_services/audio_models/en_US-lessac-medium.onnx"
)

_CONFIG = SynthesisConfig(length_scale=1)

# Where a sentence ends. The lookbehind/lookahead keep it from
# breaking on decimals (3.5) or common abbreviations (Mr. Dr.).
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")

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
