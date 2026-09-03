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

# whisper-large-v3-turbo tez bhi hai aur multilingual bhi - Urdu/English
# mix bolne walon ke liye munasib. Sirf English chahiye to
# "distil-whisper-large-v3-en" is se bhi tez hai.
GROQ_STT_MODEL = os.getenv(
    "GROQ_STT_MODEL",
    "whisper-large-v3-turbo",
)


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
            )

            # response_format="text" par SDK seedha string deta hai,
            # magar kuch versions object lautate hain.
            text = (
                result
                if isinstance(result, str)
                else getattr(result, "text", "")
            )

            return (text or "").strip()

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
