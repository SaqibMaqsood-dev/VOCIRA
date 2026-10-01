"""
The agent's words on the caller's screen, each word shown as it is spoken -
the older worker's captions (voice_pipeline.AgentCaption), for the LiveKit
Agents worker.

One line per reply. As each sentence's audio is ready (PiperTTS) its words
go to the page with when each starts, counted from the moment the line's
audio begins; the page starts that clock when it actually hears the voice
begin, so however slow the network, the text never runs ahead of the voice.
The line ends when the agent stops speaking - cut where the voice stopped
if the caller interrupted it.

    {"role": "agent", "id": ..., "words": [...], "starts": [...]}   per sentence
    {"role": "agent", "id": ..., "end": seconds}                     at the end
"""

import asyncio
import json
import time
from uuid import uuid4

from livekit import rtc
from livekit.agents import AgentSession

from backend.microservices.livekit_Rag_services.services.livekit.livekit_services.voice_pipeline import (
    TRANSCRIPT_TOPIC,
)

# ending this long before its audio would have, a line was cut off
_CUT_MARGIN = 0.25


class _Line:
    def __init__(self) -> None:
        self.id = uuid4().hex[:12]
        self.first_plays_at: float | None = None
        self.plays_until: float | None = None
        self.heard = False  # the agent's voice played while this line was open


class Captions:
    def __init__(self, session: AgentSession, room: rtc.Room) -> None:
        self._room = room
        self._line: _Line | None = None
        self._tasks: set[asyncio.Task] = set()
        session.on("agent_state_changed", self._agent_state)

    def spoken(self, text: str, starts: list[float], duration: float) -> None:
        """A sentence's audio is ready to play."""
        line = self._line = self._line or _Line()
        now = time.monotonic()
        # sentences play back to back; one not ready in time starts when it is
        plays_at = max(line.plays_until or now, now)
        line.plays_until = plays_at + duration
        if line.first_plays_at is None:
            line.first_plays_at = plays_at
        offset = plays_at - line.first_plays_at
        self._send(line, {"words": text.split(), "starts": [round(offset + s, 3) for s in starts]})

    def new_reply(self) -> None:
        """
        A new question is being answered. A line still open but not playing
        (made, then interrupted before a word was heard) is over - or the
        new reply's sentences would join it.
        """
        line = self._line
        if line and (not line.heard or time.monotonic() >= (line.plays_until or 0)):
            self._close(cut=True)

    def _agent_state(self, ev) -> None:
        if ev.new_state == "speaking" and self._line is not None:
            self._line.heard = True
        elif ev.old_state == "speaking":
            line = self._line
            cut = bool(line and line.plays_until and time.monotonic() < line.plays_until - _CUT_MARGIN)
            self._close(cut=cut)

    def _close(self, cut: bool) -> None:
        line, self._line = self._line, None
        if line is None or line.plays_until is None:
            return
        if not line.heard:
            end = -1.0  # never played: nothing of it is shown
        elif cut:
            end = min(line.plays_until, time.monotonic()) - line.first_plays_at
        else:
            end = line.plays_until - line.first_plays_at
        self._send(line, {"end": round(end, 3)})

    def _send(self, line: _Line, payload: dict) -> None:
        # in order, without holding up the audio
        task = asyncio.ensure_future(self._publish({"role": "agent", "id": line.id, **payload}))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _publish(self, payload: dict) -> None:
        if not self._room.isconnected():
            return
        try:
            await self._room.local_participant.publish_data(
                json.dumps(payload, ensure_ascii=False), reliable=True, topic=TRANSCRIPT_TOPIC
            )
        except Exception as error:
            print(f"[Transcript] could not send: {error}")
