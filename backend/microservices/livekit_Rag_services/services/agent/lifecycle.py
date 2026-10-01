"""
A call's life around the conversation, for the LiveKit Agents worker: staff
taking over, a caller who drops or never arrives, the session closed at
the end. The rules are the older worker's (livekit_room_service.py).

Staff handoff:
    the brain asks for staff (brain.py) -> the caller hears "connecting you"
    -> "vocira.handoff" = "requested" (the page shows it) -> a staff member
    joins -> "connected", and the AI leaves the room; the room stays, so
    the caller and the staff member go on talking. Nobody comes within
    HANDOFF_ANSWER_TIMEOUT -> "no_answer", and the AI takes the call back.
"""

import asyncio
import json

from livekit import rtc
from livekit.agents import AgentSession, JobContext
from livekit.agents.voice.room_io.types import DEFAULT_CLOSE_ON_DISCONNECT_REASONS

from backend.microservices.livekit_Rag_services.core.rabitmq import MAX_CALL_SECONDS
from backend.microservices.livekit_Rag_services.services.agent import brain
from backend.microservices.livekit_Rag_services.services.agent.brain_loop import on_brain
from backend.microservices.livekit_Rag_services.services.groq import human_text
from backend.microservices.livekit_Rag_services.services.livekit.livekit_services import (
    voice_pipeline as pipeline,
)
from backend.microservices.livekit_Rag_services.services.livekit.livekit_services.livekit_room_service import (
    LivekitRoomServices,
)

HANDOFF_ATTRIBUTE = LivekitRoomServices.HANDOFF_ATTRIBUTE
HANDOFF_ANSWER_TIMEOUT = LivekitRoomServices.HANDOFF_ANSWER_TIMEOUT
# a weak link needs several seconds to get back in
LEFT_GRACE_SECONDS = LivekitRoomServices.LEFT_GRACE_SECONDS
NO_SHOW_SECONDS = LivekitRoomServices.NO_SHOW_SECONDS
# the "connecting you" sentence never finished playing (it failed, say)
_HANDOFF_SPEECH_LIMIT = 20.0


def is_staff(participant: rtc.RemoteParticipant) -> bool:
    """A staff member's token says so - metadata LiveKit signed, not the browser's word."""
    try:
        meta = json.loads(participant.metadata or "{}")
    except (json.JSONDecodeError, TypeError):
        return False
    if not isinstance(meta, dict):
        return False
    return "admin" in {str(meta.get("type", "")).strip().lower(), str(meta.get("role", "")).strip().lower()}


class CallLife:
    def __init__(self, ctx: JobContext, session: AgentSession, call: brain.Call, caller: str) -> None:
        self._ctx = ctx
        self._session = session
        self._call = call
        self._caller = caller
        # True from the moment staff are asked for: the AI says nothing more
        self.handoff_requested = False
        self._pending: dict | None = None  # asked for; "connecting you" still playing
        self._watchdog: asyncio.Task | None = None
        self._grace: asyncio.Task | None = None
        self._tasks: set[asyncio.Task] = set()

        ctx.room.on("participant_connected", self._joined)
        ctx.room.on("participant_disconnected", self._left)
        session.on("agent_state_changed", self._agent_state)
        ctx.add_shutdown_callback(self._close_session)

    def start(self) -> None:
        self._spawn(self._no_show())
        self._spawn(self._max_length())

    async def _max_length(self) -> None:
        """An abandoned call must not hold a worker slot for ever (MAX_CALL_SECONDS)."""
        await asyncio.sleep(MAX_CALL_SECONDS)
        print(f"[Worker] the call ran longer than {MAX_CALL_SECONDS}s - ending it")
        self._ctx.shutdown("call too long")

    # -- staff ---------------------------------------------------------

    def ask_for_staff(self, handoff: dict) -> None:
        """Called as the "connecting you to staff" reply is written."""
        if self.handoff_requested:
            return
        self.handoff_requested = True
        self._pending = handoff
        print(f"[ADMIN HANDOFF REQUESTED] escalation {handoff.get('escalation_id')} "
              f"session {self._call.session_id} ({self._call.user_type})")
        asyncio.get_running_loop().call_later(_HANDOFF_SPEECH_LIMIT, self._begin_handoff)

    def _agent_state(self, ev) -> None:
        # the caller has heard "connecting you" - only now does the page say so
        if self._pending and ev.old_state == "speaking" and ev.new_state != "speaking":
            self._begin_handoff()

    def _begin_handoff(self) -> None:
        if self._pending is None:
            return
        self._pending = None
        self._spawn(self._wait_for_staff())

    async def _wait_for_staff(self) -> None:
        await self._publish("requested")
        if self._staff_in_room():
            await self._staff_took_over()
            return
        print(f"[Admin Handoff] waiting up to {HANDOFF_ANSWER_TIMEOUT}s for staff to join...")
        self._watchdog = self._spawn(self._no_answer())

    async def _no_answer(self) -> None:
        await asyncio.sleep(HANDOFF_ANSWER_TIMEOUT)
        if not self.handoff_requested or self._staff_in_room():
            return
        print(f"[Admin Handoff] no staff within {HANDOFF_ANSWER_TIMEOUT}s - the AI takes the call back")
        # the escalation stays pending: it is still on the panel for later
        self.handoff_requested = False
        await self._publish("no_answer")
        # a guest has no account to be called back on
        key = "handoff_no_answer" if self._call.user_id else "handoff_no_answer_guest"
        self._session.say(human_text.system_message(key, self._call.language, school=self._call.school))

    async def _staff_took_over(self) -> None:
        if self._watchdog:
            self._watchdog.cancel()
        print("[Admin Handoff] staff joined - the AI leaves the call to them")
        self._session.interrupt()
        # before leaving: the AI's attributes go with it
        await self._publish("connected")
        self._ctx.shutdown("staff took over the call")

    def _staff_in_room(self) -> bool:
        return any(is_staff(p) for p in self._ctx.room.remote_participants.values())

    async def _publish(self, state: str) -> None:
        try:
            await self._ctx.room.local_participant.set_attributes({HANDOFF_ATTRIBUTE: state})
            print(f"[Handoff State] '{state}'")
        except Exception as error:  # only a notice - the handoff goes on
            print(f"[Handoff State] could not send '{state}': {error}")

    # -- the caller ----------------------------------------------------

    def _joined(self, participant: rtc.RemoteParticipant) -> None:
        if is_staff(participant):
            print("[Participant] staff member joined")
            if self.handoff_requested and self._pending is None:
                self._spawn(self._staff_took_over())
            return
        if participant.identity == self._caller and self._grace:
            print("[Worker] the caller is back")
            self._grace.cancel()
            self._grace = None

    def _left(self, participant: rtc.RemoteParticipant) -> None:
        if is_staff(participant):
            print("[Participant] staff member left")
            return
        if participant.identity != self._caller:
            return
        if participant.disconnect_reason in DEFAULT_CLOSE_ON_DISCONNECT_REASONS:
            return  # hung up: the framework ends the call itself
        print(f"[Worker] the caller dropped ({rtc.DisconnectReason.Name(participant.disconnect_reason or 0)}) "
              f"- waiting {LEFT_GRACE_SECONDS}s for them to come back")
        if self._grace:
            self._grace.cancel()
        self._grace = self._spawn(self._end_if_gone())

    async def _end_if_gone(self) -> None:
        await asyncio.sleep(LEFT_GRACE_SECONDS)
        print("[Worker] the caller did not come back - ending the call")
        self._ctx.shutdown("caller did not come back")

    async def _no_show(self) -> None:
        """A tab closed during "Connecting..." must not hold a worker slot for ever."""
        await asyncio.sleep(NO_SHOW_SECONDS)
        if self._caller not in {p.identity for p in self._ctx.room.remote_participants.values()} and not self._grace:
            print(f"[Worker] the caller never joined within {NO_SHOW_SECONDS}s - releasing this slot")
            self._ctx.shutdown("caller never joined")

    # -- the end -------------------------------------------------------

    async def _close_session(self, reason: str = "") -> None:
        for task in list(self._tasks):
            task.cancel()
        if self._call.session_id is None:
            return
        try:
            await on_brain(pipeline.session_service.close_session_internal(session_id=self._call.session_id))
            print(f"[Session] {self._call.session_id} closed ({reason})")
        except Exception as error:
            print(f"[Session Cleanup Error] {error}")

    def _spawn(self, work) -> asyncio.Task:
        task = asyncio.create_task(work)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task
