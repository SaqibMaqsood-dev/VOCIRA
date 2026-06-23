import numpy as np
import librosa
from faster_whisper import WhisperModel


class STTWhisper:
    def __init__(self):
        self.model = WhisperModel(
            "small.en",
            device="cpu",
            compute_type="int8",
        )

    def transcribe_bytes(self, audio_bytes: bytes):
        
        # 1. Convert bytes → int16 PCM
        audio = np.frombuffer(audio_bytes, dtype=np.int16)

        # 2. Normalize (VERY IMPORTANT)
        audio = audio.astype(np.float32) / 32768.0

        audio = librosa.resample(audio, orig_sr=48000, target_sr=16000 )
        
        # 4. Transcribe
        segments, info = self.model.transcribe(
            audio,
            beam_size=5,
            best_of=5,
            temperature=0.0,
            condition_on_previous_text=False,

)

        return "".join([s.text for s in segments]).strip()