"""
Speech-to-text.

This used to run a local faster-whisper "small.en" on CPU. Its
accuracy was poor - it heard "have the fees been paid" as "have the
face being paired", which sent the whole intent the wrong way.

It now uses Groq's Whisper API: much better accuracy, and faster than
local inference on CPU. The project already has a Groq key.

The interface is unchanged - transcribe_bytes(audio_bytes) -> str -
so nothing changes for voice_pipeline.

If Groq ever fails to answer, the local whisper runs as a fallback
(the model is only loaded when it is actually needed).
"""

import io
import os
import wave

import librosa
import numpy as np
from groq import Groq

from backend.microservices.livekit_Rag_services.core.config import settings


# LiveKit delivers audio at 48 kHz; Whisper wants 16 kHz.
TARGET_SAMPLE_RATE = 16000

# Sending audio shorter than this is pointless - Whisper invents
# nonsense for it. 0.35 seconds (48 kHz, mono, int16).
MIN_AUDIO_BYTES = int(0.35 * 48000 * 2)

# The silence gate. int16 ranges to 32768; ordinary room noise stays
# below 100, while speech is far louder.
MIN_RMS = 260.0

# Whisper produces these phrases for silence and noise. They are not
# real speech - they made the agent answer its own voice and fall into
# a "Thank you / You're welcome" loop.
#
# Both languages are kept here rather than switched on STT_LANGUAGE.
# Setting STT_LANGUAGE=ur did not make Whisper stop hallucinating on
# silence - it just made it hallucinate IN URDU instead of English.
# Caught live: the exact same "background noise" case that used to
# come back as "music" started coming back as "موسیقی" (the Urdu
# word for music), which this list did not recognise at all because
# it only ever held the English spelling - so it went straight
# through as if it were a real question, and the agent answered
# noise. A multilingual model can drift into either script no matter
# which one it was told to expect, so checking for only one language's
# hallucinations was never going to be enough.
# NOTE: every entry must be written the way _is_noise() normalises -
# lower case, letters/digits/spaces only. Entries carrying their own
# punctuation ("thank you.", "i'm sorry", "thanks for watching!")
# could never match anything, because the text being checked has had
# that punctuation stripped before it arrives. "I'm sorry." was
# reaching the assistant as a real question for exactly that reason.
_HALLUCINATIONS = {
    # English
    "thank you", "thanks", "thanks for watching",
    "thank you for watching", "bye",
    "you", "okay", "ok", "so", "uh", "um", "hmm", "mm", "mhm",
    "subtitles by the amaraorg community", "please subscribe",
    "im sorry", "silence", "music", "applause",
    # Urdu - direct equivalents of the same phrases, plus موسیقی
    # (music), which is the one actually observed live
    "شکریہ", "بہت شکریہ", "خدا حافظ", "اللہ حافظ", "ٹھیک ہے",
    "ہاں", "ام", "ہوں", "خاموشی", "موسیقی", "تالیاں", "معذرت",
    "سبسکرائب کریں", "ترجمہ",
}


# A real question is this many words, OR this many characters if it
# is a short one ("حاضری بتائیں" is two words but 12 characters).
# Room noise came back as "اللہ" (1 word, 4 chars) and "ملتا ہے"
# (2 words, 7 chars) - both fall short of either bar.
MIN_QUERY_WORDS = 3
MIN_QUERY_CHARS = 10


def _is_noise(text: str) -> bool:
    """Whisper ki jhooti transcription pakrein."""
    cleaned = "".join(
        c for c in text.lower() if c.isalnum() or c.isspace()
    ).strip()

    if not cleaned:
        return True

    # only one or two characters - nothing was really said
    if len(cleaned.replace(" ", "")) < 3:
        return True

    if cleaned in _HALLUCINATIONS:
        return True

    # ------------------------------------------------------------
    # Not a phrase we recognise - but is it a question at all?
    #
    # The list above can only ever catch hallucinations already seen.
    # Whisper invents something different every time: a call logged
    # live produced "اللہ", "لانا" and "ملتا ہے" from room noise -
    # three disconnected words, none of them in any list, each one
    # answered with "I don't have information about that".
    #
    # Rather than chase every invention, require the opposite: a real
    # question here is several words, or at least a long one. Noise
    # comes back as one or two short fragments. This catches
    # inventions nobody has seen yet, which a blacklist cannot.
    # ------------------------------------------------------------

    words = cleaned.split()

    # A single word is never a question here, however long it is -
    # "production." is ten characters and still just noise.
    if len(words) < 2:
        return True

    if len(words) < MIN_QUERY_WORDS and len(cleaned) < MIN_QUERY_CHARS:
        return True

    return False

# whisper-large-v3-turbo is both fast and multilingual, which suits
# speakers who mix Urdu and English. For English only,
# "distil-whisper-large-v3-en" is faster still.
GROQ_STT_MODEL = os.getenv(
    "GROQ_STT_MODEL",
    "whisper-large-v3-turbo",
)

# The default language, for callers whose account has not chosen one
# (and for the /ask style paths that have no caller at all). A
# guardian who HAS chosen gets theirs passed in per call instead -
# see transcribe_bytes(language=...).
STT_LANGUAGE = os.getenv("STT_LANGUAGE", "ur")


class STTWhisper:

    def __init__(self):
        self.client = Groq(
            api_key=settings.returning_groq_api
        )

        # The fallback model is loaded only when it is needed
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
                "[STT] Loading the local whisper fallback..."
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
        language: str | None = None,
    ) -> str:
        """
        Raw int16 mono PCM ko text mein badlein.

        Ye sync function hai - voice_pipeline ise
        asyncio.to_thread() se chalata hai.

        `language` is the caller's own choice ("en" / "ur"), read
        from their account once when the call starts. Left out, the
        STT_LANGUAGE default applies - which is what every call used
        to do.
        """

        language = (language or STT_LANGUAGE).strip().lower()

        if not audio_bytes:
            return ""

        # ------------------------------------------------------
        # Audio this short or this quiet should never reach the
        # API at all. Whisper invents speech for it ("Thank you.",
        # "E ai") which the system then treats as a real question
        # and answers.
        # ------------------------------------------------------

        if len(audio_bytes) < MIN_AUDIO_BYTES:
            return ""

        samples = np.frombuffer(audio_bytes, dtype=np.int16)

        if samples.size == 0:
            return ""

        rms = float(np.sqrt(np.mean(samples.astype(np.float64) ** 2)))

        if rms < MIN_RMS:
            print(
                f"[STT] khamoshi chhori (rms={rms:.0f} < {MIN_RMS:.0f})"
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
                # Without this Whisper guesses the language itself,
                # and turned noise into Portuguese/Spanish.
                language=language,
            )

            # With response_format="text" the SDK returns a plain
            # string, but some versions return an object.
            text = (
                result
                if isinstance(result, str)
                else getattr(result, "text", "")
            )

            text = (text or "").strip()

            if _is_noise(text):
                print(f"[STT] hallucination chhori: {text!r}")
                return ""

            return text

        except Exception as error:

            print(
                f"[STT] Groq failed ({error}). "
                "Falling back to local whisper."
            )

            try:
                return self._transcribe_local(
                    audio_bytes=audio_bytes,
                    source_sample_rate=sample_rate,
                )

            except Exception as fallback_error:

                print(
                    f"[STT] Local fallback bhi fail: "
                    f"{fallback_error}"
                )

                return ""
