"""
STT round-trip test.

Piper TTS se jumla bolwate hain, phir wahi audio naye STT ko dete hain.
Agar wapis wahi jumla aa jaye to STT theek kaam kar raha hai.

Piper 22050 Hz deta hai, is liye sample_rate wahi pass karte hain.
"""
import io
import contextlib

from backend.microservices.livekit_Rag_services.services.text_speech.piper_servies import (
    tts_converter,
)
from backend.microservices.livekit_Rag_services.services.Speec_to_text_service.sst_whisper import (
    STTWhisper,
)

PHRASES = [
    "Have the school fees been paid?",
    "How many days was Muhammad Ali present?",
    "What marks did Alisha Ahmed get?",
    "When is the next exam?",
    "Which class is Muhammad Ali in?",
]

print("=" * 74)
print("STT ROUND-TRIP TEST   (Piper 22050 Hz -> Groq Whisper)")
print("=" * 74)

noise = io.StringIO()
with contextlib.redirect_stdout(noise):
    stt = STTWhisper()

ok = 0

for phrase in PHRASES:
    audio = tts_converter(text=phrase)

    with contextlib.redirect_stdout(noise):
        heard = stt.transcribe_bytes(audio, sample_rate=22050)

    # narmi se compare: sirf harf aur chhote-bare ka farq nazarandaz
    def norm(s):
        return "".join(c.lower() for c in s if c.isalnum())

    match = norm(heard) == norm(phrase)
    if match:
        ok += 1

    print()
    print(f"  bola  : {phrase}")
    print(f"  suna  : {heard}")
    print(f"  {'MATCH' if match else 'FARQ HAI'}")

print()
print("=" * 74)
print(f"NATEEJA: {ok} / {len(PHRASES)} bilkul sahi")
print("=" * 74)
