import os
import io
from piper import PiperVoice
from piper.config import SynthesisConfig

# 1. Dynamically absolute path setup karein
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
model_path = os.path.join(BASE_DIR, "audio_models", "en_US-lessac-medium.onnx")

# 2. Load the voice model using the absolute path
voice = PiperVoice.load(model_path)

def tts_converter(text: str) -> bytes:
    config = SynthesisConfig(length_scale=1)

    buffer = io.BytesIO()
    
    audio = voice.synthesize(text, syn_config=config)
    
    for chunk in audio:
        buffer.write(chunk.audio_int16_bytes)
        
    buffer.seek(0)
    return buffer.read()