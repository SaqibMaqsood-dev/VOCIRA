"""
Piper in a process of its own.

Inside the agent's process Piper ran 2-3 times slower than on its own
(1.1-2.3 s for a sentence it makes in 0.6-0.9 s): it was competing with
the call's audio handling and voice detection for the same CPU and
Python lock. One separate process, with both voices loaded once, gives
it the machine to itself. Only this small module is imported there.
"""

import multiprocessing
from concurrent.futures import ProcessPoolExecutor

_pool: ProcessPoolExecutor | None = None


def _load_voices() -> None:
    from backend.microservices.livekit_Rag_services.services.text_speech.piper_servies import _voice_for

    for language in ("en", "ur"):
        _voice_for(language)


def synthesize(text: str, language: str) -> tuple[bytes, float, list[float]]:
    """
    16-bit mono PCM for one sentence, the seconds it took, and when each of
    its words starts - for the captions (runs in the Piper process).
    """
    import time

    from backend.microservices.livekit_Rag_services.services.text_speech.piper_servies import (
        synthesize_with_timing,
    )

    started = time.perf_counter()
    pcm, starts = synthesize_with_timing(text, language)
    return pcm, time.perf_counter() - started, starts


def piper_pool() -> ProcessPoolExecutor:
    global _pool
    if _pool is None:
        _pool = ProcessPoolExecutor(
            max_workers=1,
            mp_context=multiprocessing.get_context("spawn"),
            initializer=_load_voices,
        )
    return _pool
