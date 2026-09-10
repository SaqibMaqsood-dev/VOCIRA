"""STT guards: khamoshi, chhota audio, aur hallucination rukti hai?"""
import io, contextlib
import numpy as np

from backend.microservices.livekit_Rag_services.services.text_speech.piper_servies import tts_converter
from backend.microservices.livekit_Rag_services.services.Speec_to_text_service.sst_whisper import (
    STTWhisper, MIN_AUDIO_BYTES, MIN_RMS, _is_noise,
)

noise = io.StringIO()
with contextlib.redirect_stdout(noise):
    stt = STTWhisper()

print("=" * 72)
print("STT GUARDS")
print("=" * 72)
print(f"  MIN_AUDIO_BYTES : {MIN_AUDIO_BYTES}  (~0.35s @ 48kHz)")
print(f"  MIN_RMS         : {MIN_RMS}")

pass_n = fail_n = 0
def chk(label, cond):
    global pass_n, fail_n
    if cond:
        print(f"  PASS  {label}"); pass_n += 1
    else:
        print(f"  FAIL  {label}"); fail_n += 1

print("\n--- 1. hallucination filter ---")
for junk in ["Thank you.", "you", "Bye.", "", ".", "  ", "Okay",
             "Thanks for watching!", "Music"]:
    chk(f"{junk!r} -> noise", _is_noise(junk))
for real in ["Have the school fees been paid?", "What are the school timings"]:
    chk(f"{real[:34]!r} -> asli baat", not _is_noise(real))

print("\n--- 2. khamoshi API tak nahi jani chahiye ---")
# 2 second bilkul khamoshi
silence = np.zeros(48000 * 2, dtype=np.int16).tobytes()
with contextlib.redirect_stdout(noise):
    out = stt.transcribe_bytes(silence, sample_rate=48000)
chk(f"pin-drop khamoshi -> {out!r}", out == "")

# halka kamre ka shor (rms ~60)
room = (np.random.randn(48000 * 2) * 60).astype(np.int16).tobytes()
with contextlib.redirect_stdout(noise):
    out = stt.transcribe_bytes(room, sample_rate=48000)
chk(f"kamre ka shor -> {out!r}", out == "")

print("\n--- 3. bohat chhota audio ---")
tiny = np.zeros(4000, dtype=np.int16).tobytes()
with contextlib.redirect_stdout(noise):
    out = stt.transcribe_bytes(tiny, sample_rate=48000)
chk(f"0.04s audio -> {out!r}", out == "")

print("\n--- 4. ASLI awaaz to guzarni chahiye ---")
phrase = "Have the school fees been paid?"
audio = tts_converter(phrase)          # Piper: 22050 Hz
with contextlib.redirect_stdout(noise):
    heard = stt.transcribe_bytes(audio, sample_rate=22050)
print(f"       bola : {phrase}")
print(f"       suna : {heard!r}")
chk("asli jumla guzra", "fee" in heard.lower())

print("\n" + "=" * 72)
print(f"  PASS: {pass_n}   FAIL: {fail_n}")
print("=" * 72)
