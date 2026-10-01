"""
Piper as a LiveKit Agents TTS - the same local voices the older worker
speaks with (text_speech/piper_servies.py), one per call language.

Piper makes a whole sentence at once rather than streaming, so the
framework feeds it a sentence at a time and plays each as soon as it is
ready; the next one is made while the first plays.
"""

import asyncio
import json
import time
from collections.abc import Callable

from livekit.agents import APIConnectOptions, tts, utils
from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS

from backend.microservices.livekit_Rag_services.services.agent import piper_proc
from backend.microservices.livekit_Rag_services.services.agent.piper_proc import piper_pool
from backend.microservices.livekit_Rag_services.services.text_speech import piper_servies


def _sample_rate(language: str) -> int:
    """From the voice's own config - the voice itself is only loaded in the Piper process."""
    voice = piper_servies._VOICE_FILES.get(language, piper_servies._VOICE_FILES["en"])
    with open(f"{piper_servies._MODEL_DIR}/{voice}.json", encoding="utf-8") as f:
        return int(json.load(f)["audio"]["sample_rate"])


def warm_up() -> None:
    """Start the Piper process and load its voices before the first call needs them."""
    piper_pool().submit(piper_proc.synthesize, "Hello.", "en").result(timeout=120)


class PiperTTS(tts.TTS):
    def __init__(self, language: str, on_spoken: Callable[[str, list[float], float], None] | None = None) -> None:
        self._language = language
        # told of every sentence as its audio is ready: its text, when each
        # word starts, and how long it lasts (the captions, captions.py)
        self.on_spoken = on_spoken
        sample_rate = _sample_rate(language)
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=False),
            sample_rate=sample_rate,
            num_channels=1,
        )

    @property
    def model(self) -> str:
        return f"piper-{self._language}"

    @property
    def provider(self) -> str:
        return "piper"

    def synthesize(
        self, text: str, *, conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS
    ) -> "_PiperStream":
        return _PiperStream(tts=self, input_text=text, conn_options=conn_options)


class _PiperStream(tts.ChunkedStream):
    def __init__(self, *, tts: PiperTTS, input_text: str, conn_options: APIConnectOptions) -> None:
        super().__init__(tts=tts, input_text=input_text, conn_options=conn_options)
        self._piper = tts

    async def _run(self, output_emitter: tts.AudioEmitter) -> None:
        output_emitter.initialize(
            request_id=utils.shortuuid(),
            sample_rate=self._piper.sample_rate,
            num_channels=1,
            mime_type="audio/pcm",
        )
        # Piper is CPU work - in its own process (piper_proc.py), off this
        # call's loop and away from its audio handling
        started = time.perf_counter()
        pcm, synth_seconds, starts = await asyncio.get_running_loop().run_in_executor(
            piper_pool(), piper_proc.synthesize, self._input_text, self._piper._language
        )
        duration = len(pcm) / 2 / self._piper.sample_rate
        print(f"[Piper] {(time.perf_counter() - started) * 1000:.0f}ms "
              f"(synthesis {synth_seconds * 1000:.0f}ms) at {time.strftime('%H:%M:%S')} "
              f"for {len(self._input_text)} chars -> {duration:.1f}s of audio")
        if pcm:
            if self._piper.on_spoken is not None:
                self._piper.on_spoken(self._input_text.strip(), starts, duration)
            output_emitter.push(pcm)
        output_emitter.flush()
