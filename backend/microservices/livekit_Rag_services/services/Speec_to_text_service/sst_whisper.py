"""
Speech-to-text.

Pehle ye local faster-whisper "small.en" CPU par chalata tha. Us ki
accuracy kam thi - "have the fees been paid" ko "have the face being
paired" sun leta tha, jis se poora intent ghalat chala jata tha.

Ab Groq ka Whisper API use hota hai: kaafi behtar accuracy, aur CPU
par local inference se tez bhi. Groq ki key project mein pehle se hai.

Interface wahi hai - transcribe_bytes(audio_bytes) -> str - is liye
voice_pipeline ko koi farq nahi parta.

Agar Groq kisi waqt jawab na de to local whisper fallback ke taur par
chal jata hai (model sirf zaroorat par load hota hai).
"""

import io
import os
import wave

import librosa
import numpy as np
from groq import Groq

from backend.microservices.livekit_Rag_services.core.config import settings


# LiveKit 48 kHz par audio deta hai; Whisper 16 kHz chahta hai.
TARGET_SAMPLE_RATE = 16000

# Is se chhota audio bhejne ka faida nahi - Whisper us par bakwaas
# bana deta hai. 0.35 second (48 kHz, mono, int16).
MIN_AUDIO_BYTES = int(0.35 * 48000 * 2)

# Khamoshi ka gate. int16 ki range 32768 hai; kamre ka aam shor
# 100 se neeche rehta hai, boli hui awaaz kahin zyada.
MIN_RMS = 260.0

# Whisper khamoshi/shor par ye jumle bana deta hai. Ye asli baat nahi
# hoti - is ki wajah se agent apni hi awaaz ka jawab dene lagta tha
# aur "Thank you / You're welcome" ka loop ban jata tha.
_HALLUCINATIONS = {
    "thank you", "thanks", "thank you.", "thanks for watching",
    "thank you for watching", "thanks for watching!", "bye", "bye.",
    "you", "okay", "ok", "so", "uh", "um", "hmm", "mm", "mhm",
    "subtitles by the amara.org community", "please subscribe",
    "i'm sorry", "silence", "music", "applause",
}


def _is_noise(text: str) -> bool:
    """Whisper ki jhooti transcription pakrein."""
    cleaned = "".join(
        c for c in text.lower() if c.isalnum() or c.isspace()
    ).strip()

    if not cleaned:
        return True

    # sirf ek ya do harf - matlab kuch bola hi nahi
    if len(cleaned.replace(" ", "")) < 3:
        return True

    return cleaned in _HALLUCINATIONS

# whisper-large-v3-turbo tez bhi hai aur multilingual bhi - Urdu/English
# mix bolne walon ke liye munasib. Sirf English chahiye to
# "distil-whisper-large-v3-en" is se bhi tez hai.
GROQ_STT_MODEL = os.getenv(
    "GROQ_STT_MODEL",
    "whisper-large-v3-turbo",
)

# Zaban tay kar dein. Urdu chahiye to STT_LANGUAGE=ur karein.
STT_LANGUAGE = os.getenv("STT_LANGUAGE", "en")


class STTWhisper:

    def __init__(self):
        self.client = Groq(
            api_key=settings.returning_groq_api
        )

        # Fallback model sirf zaroorat par load hoga
        self._local_model = None

    # ------------------------------------------------------------------
    # PCM -> WAV
    # ------------------------------------------------------------------

    @staticmethod
    def _pcm_to_wav(
        audio_bytes: bytes,
        source_sample_rate: int,
    ) -> bytes:
        """Raw int16 mono PCM ko 16 kHz WAV mein badlein."""

        audio = np.frombuffer(
            audio_bytes,
            dtype=np.int16,
        )

        if audio.size == 0:
            return b""

        # float32 mein normalize karein
        audio = audio.astype(np.float32) / 32768.0

        if source_sample_rate != TARGET_SAMPLE_RATE:
            audio = librosa.resample(
                audio,
                orig_sr=source_sample_rate,
                target_sr=TARGET_SAMPLE_RATE,
            )

        # wapis int16
        audio = np.clip(audio, -1.0, 1.0)
        audio = (audio * 32767.0).astype(np.int16)

        buffer = io.BytesIO()

        with wave.open(buffer, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(TARGET_SAMPLE_RATE)
            wav.writeframes(audio.tobytes())

        return buffer.getvalue()

    # ------------------------------------------------------------------
    # LOCAL FALLBACK
    # ------------------------------------------------------------------

    def _transcribe_local(
        self,
        audio_bytes: bytes,
        source_sample_rate: int,
    ) -> str:

        if self._local_model is None:

            print(
                "⬇️ [STT] Local whisper fallback load ho raha hai..."
            )

            from faster_whisper import WhisperModel

            self._local_model = WhisperModel(
                "small.en",
                device="cpu",
                compute_type="int8",
            )

        audio = np.frombuffer(
            audio_bytes,
            dtype=np.int16,
        ).astype(np.float32) / 32768.0

        if source_sample_rate != TARGET_SAMPLE_RATE:
            audio = librosa.resample(
                audio,
                orig_sr=source_sample_rate,
                target_sr=TARGET_SAMPLE_RATE,
            )

        segments, _ = self._local_model.transcribe(
            audio,
            beam_size=5,
            best_of=5,
            temperature=0.0,
            condition_on_previous_text=False,
        )

        return "".join(
            segment.text for segment in segments
        ).strip()

    # ------------------------------------------------------------------
    # MAIN
    # ------------------------------------------------------------------

    def transcribe_bytes(
        self,
        audio_bytes: bytes,
        sample_rate: int = 48000,
    ) -> str:
        """
        Raw int16 mono PCM ko text mein badlein.

        Ye sync function hai - voice_pipeline ise
        asyncio.to_thread() se chalata hai.
        """

        if not audio_bytes:
            return ""

        # ------------------------------------------------------
        # Bohat chhota ya bohat khamosh audio API tak bhejna hi
        # nahi chahiye. Whisper us par jhooti baat bana deta hai
        # ("Thank you.", "E ai") jise system asli sawal samajh
        # kar jawab dene lagta hai.
        # ------------------------------------------------------

        if len(audio_bytes) < MIN_AUDIO_BYTES:
            return ""

        samples = np.frombuffer(audio_bytes, dtype=np.int16)

        if samples.size == 0:
            return ""

        rms = float(np.sqrt(np.mean(samples.astype(np.float64) ** 2)))

        if rms < MIN_RMS:
            print(
                f"🔇 [STT] khamoshi chhori (rms={rms:.0f} < {MIN_RMS:.0f})"
            )
            return ""

        try:

            wav_bytes = self._pcm_to_wav(
                audio_bytes=audio_bytes,
                source_sample_rate=sample_rate,
            )

            if not wav_bytes:
                return ""

            result = self.client.audio.transcriptions.create(
                file=("speech.wav", wav_bytes),
                model=GROQ_STT_MODEL,
                response_format="text",
                temperature=0.0,
                # Bina iske Whisper zaban khud "andaza" lagata hai aur
                # shor par Portuguese/Spanish bana deta tha.
                language=STT_LANGUAGE,
            )

            # response_format="text" par SDK seedha string deta hai,
            # magar kuch versions object lautate hain.
            text = (
                result
                if isinstance(result, str)
                else getattr(result, "text", "")
            )

            text = (text or "").strip()

            if _is_noise(text):
                print(f"🔇 [STT] hallucination chhori: {text!r}")
                return ""

            return text

        except Exception as error:

            print(
                f"⚠️ [STT] Groq fail hua ({error}). "
                "Local whisper par ja rahe hain."
            )

            try:
                return self._transcribe_local(
                    audio_bytes=audio_bytes,
                    source_sample_rate=sample_rate,
                )

            except Exception as fallback_error:

                print(
                    f"❌ [STT] Local fallback bhi fail: "
                    f"{fallback_error}"
                )

                return ""
