from piper import PiperVoice
from piper.config import SynthesisConfig
import io

# Load the voice model
voice = PiperVoice.load("backend/microservices/livekit_Rag_services/audio_models/en_US-lessac-medium.onnx")

def tts_converter(text: str) -> bytes:
    config = SynthesisConfig(length_scale=1)

    buffer = io.BytesIO()
    
    audio = voice.synthesize(text, syn_config=config)
    
    for chunk in audio:
        buffer.write(chunk.audio_int16_bytes)
        
    buffer.seek(0)
    return buffer.read()