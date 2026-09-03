"""
Piper text-to-speech.

Pehle tts_converter() poore jawab ka audio banata tha aur tab lautata tha.
CPU par ek lambe jawab mein 1.5-2 second lag jate the, jis dauran user
ko bilkul khamoshi sunayi deti thi.

Ab tts_sentences() jawab ko jumlon mein tod kar EK EK karke audio deta
hai, is liye pehla jumla ~400ms mein bajna shuru ho jata hai. Kul waqt
utna hi rehta hai, magar mehsoos kaafi tez hota hai.

tts_converter() waisa hi rakha hua hai taake purane callers na tooten.
"""

import io
import re

from piper import PiperVoice
from piper.config import SynthesisConfig

voice = PiperVoice.load(
    "backend/microservices/livekit_Rag_services/audio_models/en_US-lessac-medium.onnx"
)

_CONFIG = SynthesisConfig(length_scale=1)

# Jumla khatam hone ki nishani. Decimal numbers (3.5) aur aam
# ikhtisaraat (Mr. Dr.) par na toote, is liye lookbehind/lookahead.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")

# Itne se chhote tukde alag na bajayein - warna awaaz katti hui lagti hai.
_MIN_CHUNK_CHARS = 24


def split_sentences(text: str) -> list[str]:
    """Jawab ko bajane laiq jumlon mein toRein."""
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


def tts_sentences(text: str):
    """
    Har jumle ka audio alag alag deta hai (generator).

    Caller pehla tukda milte hi bajana shuru kar sakta hai, aur agla
    jumla us dauran ban raha hota hai.
    """
    for sentence in split_sentences(text):
        audio = _synth(sentence)
        if audio:
            yield sentence, audio


def tts_converter(text: str) -> bytes:
    """Poore jawab ka audio ek saath (purana behaviour)."""
    if not text or not text.strip():
        return b""
    return _synth(text.strip())
