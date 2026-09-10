import asyncio
import json
import os
import traceback
from typing import Optional
from uuid import UUID

from livekit import api, rtc
from livekit.rtc import Room

from backend.microservices.livekit_Rag_services.services.router_services.session_service import (
    SessionService,
)

from backend.microservices.livekit_Rag_services.core.config import (
    settings,
)

from backend.microservices.livekit_Rag_services.services.Speec_to_text_service.sst_whisper import (
    STTWhisper,
)

from backend.microservices.livekit_Rag_services.services.livekit.livekit_services import (
    voice_pipeline,
)


stt = STTWhisper()


class LivekitRoomServices:

    def __init__(
        self,
        user_role: str,
        user_id: Optional[str] = None,
    ):

        self.user_id = user_id
        self.user_role = user_role

        # =====================================================
        # ROOM STATE
        # =====================================================

        self.room: Optional[Room] = None
        self.room_name: Optional[str] = None

        # =====================================================
        # PARTICIPANT TYPE
        # =====================================================

        self.participant_type: str = (
            "user"
            if user_id
            else "guest"
        )

        # =====================================================
        # HUMAN / ADMIN STATE
        # =====================================================

        self.human_has_joined = False
        self.admin_has_joined = False

        # Greet ONCE only - otherwise it speaks again on every
        # participant event
        self._greeted = False

        self._admin_handoff_requested = False
        self._escalation_created = False

        # If no admin picks up, the AI takes over again
        self._handoff_timeout_task = None

        # =====================================================
        # HANDOFF INFORMATION
        # =====================================================

        self._admin_handoff_user_id = None
        self._admin_handoff_session_id = None
        self._admin_handoff_user_type = None
        self._admin_handoff_message_id = None
        self._escalation_id = None

        # =====================================================
        # AGENT AUDIO
        # =====================================================

        self.agent_source = None
        self.agent_track = None

        # =====================================================
        # BACKGROUND TASKS
        # =====================================================

        self._background_tasks = set()
        self._disconnect_timer = None

        # =====================================================
        # INTENTIONAL END CALL
        # =====================================================

        self._intentional_disconnect = False

        # =====================================================
        # SHUTDOWN
        # =====================================================

        self._shutdown_event = asyncio.Event()

        # =====================================================
        # TTS / SPEECH STATE
        # =====================================================

        self._track_ready = asyncio.Event()

        self._tts_lock = asyncio.Lock()

        self._speech_generation = 0

        # The last generation that was actually spoken. This is what
        # decides whether an answer is stale - judging by
        # _speech_generation alone was throwing every answer away.
        self._last_played_generation = 0

        self._is_agent_speaking = False

        # The last state published to the frontend (lk.agent.state).
        # LiveKit's visualizer shows listening / thinking / speaking
        # from this. None means nothing has been published yet.
        self._agent_state = None

        # When the agent last finished speaking. The mic is ignored
        # for a short while after that, or the tail of its own audio
        # coming out of the speaker becomes the next "question".
        self._agent_speech_ended_at = 0.0

        # =====================================================
        # SESSION SERVICE
        # =====================================================

        self.ss_service = SessionService()

    # =========================================================
    # LIVEKIT TOKEN
    # =========================================================

    def livekit_token(
        self,
        api_key,
        api_secret,
        room_name: str,
        user_name: Optional[str],
    ):

        # =====================================================
        # DETERMINE PARTICIPANT TYPE
        # =====================================================

        if user_name == "agent":

            participant_type = "agent"

        elif (
            str(self.user_role).strip().lower()
            == "admin"
        ):

            participant_type = "admin"

        elif self.user_id:

            participant_type = "user"

        else:

            participant_type = "guest"

        # =====================================================
        # USER ID
        # =====================================================

        if participant_type == "guest":

            metadata_user_id = None

        else:

            metadata_user_id = (
                str(self.user_id)
                if self.user_id
                else None
            )

        # =====================================================
        # ROLE
        # =====================================================

        if participant_type == "guest":

            role = "guest"

        elif participant_type == "admin":

            role = "admin"

        elif participant_type == "agent":

            role = "agent"

        else:

            role = "user"

        # =====================================================
        # METADATA
        # =====================================================

        metadata = {
            "user_id": metadata_user_id,
            "role": role,
            "type": participant_type,
        }

        # =====================================================
        # IDENTITY
        # =====================================================

        if participant_type == "agent":

            identity = "agent"

        elif participant_type == "guest":

            identity = (
                f"guest-{room_name}"
            )

        elif participant_type == "admin":

            identity = (
                f"admin-{self.user_id}"
            )

        else:

            identity = (
                f"user-{self.user_id}"
            )

        # =====================================================
        # TOKEN
        # =====================================================

        return (
            api.AccessToken(
                api_key,
                api_secret,
            )
            .with_identity(identity)
            .with_name(user_name or role)
            .with_grants(
                api.VideoGrants(
                    room_join=True,
                    room=room_name,
                    can_publish=True,
                    can_subscribe=True,
                    agent=(participant_type == "agent"),

                    # The agent publishes its state through the
                    # "lk.agent.state" attribute (listening /
                    # thinking / speaking) - LiveKit's UI components
                    # read exactly that. set_attributes() needs this
                    # permission; without it, it fails silently.
                    can_update_own_metadata=(
                        participant_type == "agent"
                    ),
                )
            )
            .with_room_config(
                api.RoomConfiguration(
                    departure_timeout=30,
                    empty_timeout=60,
                )
            )
            .with_metadata(
                json.dumps(metadata)
            )
        ).to_jwt()

    # =========================================================
    # GREETING
    # =========================================================

    GREETING_TEXT = (
        "Assalam o Alaikum, and welcome to The Educators. "
        "I am Vocira, your school assistant. How may I help you today?"
    )

    async def greet_once(self):
        """
        Greet once, as soon as a person joins the room.

        There was no greeting at all before - the agent just sat
        there silently and the user could not tell it had connected.
        """

        if self._greeted:
            return

        self._greeted = True

        try:
            # speak_text does not raise on every failure - if the
            # track is not ready, the room is gone, or sending a frame
            # fails, it simply returns False. This return value used
            # to be ignored, so the greeting vanished silently and
            # left no trace in the logs.
            spoken = await voice_pipeline.speak_text(
                service_handle=self,
                audio_source=self.agent_source,
                text=self.GREETING_TEXT,
            )

            if not spoken:
                print(
                    "[Greeting] boli nahi ja saki - "
                    "agent track ya room tayyar nahi tha. "
                    "(the [Speak] line above gives the real reason)"
                )

        except Exception as error:
            print(
                f"[Greeting] fail: "
                f"{type(error).__name__}: {error}"
            )

            traceback.print_exc()

    def _schedule_greeting(self):
        """
        Greet in a background task - the event handler is sync, so
        it cannot await here.
        """
        task = asyncio.create_task(self.greet_once())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    # =========================================================
    # CONNECT WORKER
    # =========================================================

    async def connect_worker(
        self,
        token: str,
        session_id: UUID,
    ):

        self.room = Room()

        self.room_name = (
            f"room-{session_id}"
        )

        # =====================================================
        # RESET STATE
        # =====================================================

        self.human_has_joined = False
        self.admin_has_joined = False

        self._admin_handoff_requested = False
        self._escalation_created = False

        self._cancel_handoff_timeout()

        self._admin_handoff_user_id = None
        self._admin_handoff_session_id = None
        self._admin_handoff_user_type = None
        self._admin_handoff_message_id = None
        self._escalation_id = None

        self._intentional_disconnect = False

        self._shutdown_event.clear()
        self._track_ready.clear()

        self._speech_generation = 0
        self._last_played_generation = 0
        self._is_agent_speaking = False
        self._agent_state = None
        self._agent_speech_ended_at = 0.0

        print(
            f"[Worker] Spin-up initialized "
            f"for room: {self.room_name}"
        )

        # =====================================================
        # CREATE AGENT AUDIO
        # =====================================================

        self.agent_source = rtc.AudioSource(
            sample_rate=22050,
            num_channels=1,
        )

        self.agent_track = (
            rtc.LocalAudioTrack.create_audio_track(
                "agent_voice",
                self.agent_source,
            )
        )

        # =====================================================
        # CONNECTED
        # =====================================================

        @self.room.on("connected")
        def on_connected():

            print(
                f"[Worker] Successfully connected "
                f"to room: {self.room.name}"
            )

        # =====================================================
        # PARTICIPANT CONNECTED
        # =====================================================

        @self.room.on("participant_connected")
        def on_participant_connected(participant):

            try:

                metadata = json.loads(
                    participant.metadata or "{}"
                )

            except (
                json.JSONDecodeError,
                TypeError,
            ):

                metadata = {}

            participant_type = str(
                metadata.get(
                    "type",
                    "",
                )
            ).strip().lower()

            participant_role = str(
                metadata.get(
                    "role",
                    "",
                )
            ).strip().lower()

            participant_user_id = metadata.get(
                "user_id"
            )

            print(
                "[Participant Joined]"
            )

            print(
                f"   Identity : "
                f"{participant.identity}"
            )

            print(
                f"   Type     : "
                f"{participant_type}"
            )

            print(
                f"   Role     : "
                f"{participant_role}"
            )

            print(
                f"   User ID  : "
                f"{participant_user_id}"
            )

            # =================================================
            # AGENT
            # =================================================

            if (
                participant.identity == "agent"
                or participant_type == "agent"
            ):

                print(
                    "[Participant] "
                    "AI agent detected."
                )

                return

            # =================================================
            # ADMIN
            # =================================================

            if (
                participant_type == "admin"
                or participant_role == "admin"
            ):

                print(
                    "[Participant] "
                    "ADMIN detected."
                )

                self.admin_has_joined = True
                self.human_has_joined = True

                # An admin arrived - the "nobody is answering"
                # watchdog should no longer fire
                self._cancel_handoff_timeout()

                if self._disconnect_timer:

                    self._disconnect_timer.cancel()

                    self._disconnect_timer = None

                if self._admin_handoff_requested:

                    print(
                        "[Admin Handoff] "
                        "Admin joined after handoff."
                    )

                    task = asyncio.create_task(
                        self._complete_admin_handoff()
                    )

                    self._background_tasks.add(task)

                    task.add_done_callback(
                        self._background_tasks.discard
                    )

                return

            # =================================================
            # GUEST
            # =================================================

            if participant_type == "guest":

                print(
                    "[Participant] "
                    "GUEST detected."
                )

                print(
                    "[Security] "
                    "Guest has no authenticated user ID."
                )

                self.human_has_joined = True

                if self._disconnect_timer:

                    self._disconnect_timer.cancel()

                    self._disconnect_timer = None

                self._schedule_greeting()

                return

            # =================================================
            # AUTHENTICATED USER / PARENT
            # =================================================

            if (
                participant_type == "user"
                or participant_role == "user"
            ):

                print(
                    "[Participant] "
                    "AUTHENTICATED USER detected."
                )

                print(
                    f"Authenticated User ID: "
                    f"{participant_user_id}"
                )

                self.human_has_joined = True

                if self._disconnect_timer:

                    self._disconnect_timer.cancel()

                    self._disconnect_timer = None

                self._schedule_greeting()

                return

            # =================================================
            # UNKNOWN PARTICIPANT
            # =================================================

            print(
                "[Participant] "
                "Unknown participant type."
            )

        # =====================================================
        # PARTICIPANT DISCONNECTED
        # =====================================================

        @self.room.on("participant_disconnected")
        def on_participant_disconnected(
            participant
        ):

            print(
                f"[User Left] "
                f"Participant left: "
                f"{participant.identity}"
            )

            try:

                metadata = json.loads(
                    participant.metadata or "{}"
                )

            except (
                json.JSONDecodeError,
                TypeError,
            ):

                metadata = {}

            participant_type = str(
                metadata.get(
                    "type",
                    "",
                )
            ).strip().lower()

            participant_role = str(
                metadata.get(
                    "role",
                    "",
                )
            ).strip().lower()

            # =================================================
            # ADMIN LEFT
            # =================================================

            if (
                participant_type == "admin"
                or participant_role == "admin"
            ):

                print(
                    "[Admin] "
                    "Admin left the room."
                )

                self.admin_has_joined = False

            # =================================================
            # INTENTIONAL DISCONNECT
            # =================================================

            if self._intentional_disconnect:

                print(
                    "[Worker] "
                    "Intentional call termination detected."
                )

                self._shutdown_event.set()

                return

            # =================================================
            # CHECK REMAINING HUMANS
            # =================================================

            if not self.room:
                return

            humans_in_room = [
                p
                for p in self.room.remote_participants.values()
                if p.identity != "agent"
            ]

            if not humans_in_room:

                print(
                    "[Worker] "
                    "Last human left. "
                    "Starting 10s grace period..."
                )

                if self._disconnect_timer:

                    self._disconnect_timer.cancel()

                self._disconnect_timer = (
                    asyncio.create_task(
                        self._delayed_teardown()
                    )
                )

        # =====================================================
        # TRACK SUBSCRIBED
        # =====================================================

        @self.room.on("track_subscribed")
        def on_track_subscribed(
            track,
            publication,
            participant,
        ):

            if (
                track.kind
                != rtc.TrackKind.KIND_AUDIO
            ):

                return

            print(
                f"[Audio Active] "
                f"Subscribed to track from "
                f"{participant.identity}"
            )

            try:

                metadata = json.loads(
                    participant.metadata or "{}"
                )

            except (
                json.JSONDecodeError,
                TypeError,
            ):

                metadata = {}

            participant_type = str(
                metadata.get(
                    "type",
                    "",
                )
            ).strip().lower()

            participant_role = str(
                metadata.get(
                    "role",
                    "",
                )
            ).strip().lower()

            # =================================================
            # ADMIN AUDIO
            # =================================================

            if (
                participant_type == "admin"
                or participant_role == "admin"
            ):

                print(
                    "[Audio] "
                    "Admin audio detected. "
                    "AI will not process admin audio."
                )

                return

            # =================================================
            # AGENT AUDIO
            # =================================================

            if participant_type == "agent":

                return

            # =================================================
            # GUEST / USER AUDIO
            # =================================================

            if participant_type not in {
                "guest",
                "user",
            }:

                print(
                    "[Audio] "
                    "Unknown participant type. "
                    "Ignoring audio."
                )

                return

            # =================================================
            # VOICE PIPELINE
            # =================================================

            task = asyncio.create_task(
                voice_pipeline.consume_audio(
                    stt=stt,
                    track=track,
                    participant=participant,
                    service_handle=self,
                    session_id=session_id,
                    audio_source=self.agent_source,
                )
            )

            self._background_tasks.add(task)

            task.add_done_callback(
                self._background_tasks.discard
            )

        # =====================================================
        # CONNECT
        # =====================================================

        try:

            # Not the browser's public address - the agent's own
            # route. On the server this is the internal
            # ws://livekit:7880; locally the two are the same thing.
            await self.room.connect(
                settings.LIVEKIT_AGENT_URL,
                token,
            )

            await self._publish_agent_voice()

            await self._shutdown_event.wait()

        except Exception as error:

            print(
                f"[Worker Error] "
                f"Loop exception occurred: "
                f"{error}"
            )

        finally:

            await self.cleanup()

            try:

                await self.ss_service.close_session_by_id(
                    session_id=session_id,
                    user_id=self.user_id

                )

            except Exception as error:

                print(
                    f"[Session Cleanup Error] "
                    f"{error}"
                )

    # =========================================================
    # EXPLICIT END CALL
    # =========================================================

    async def end_call(self):

        print(
            "[Worker] "
            "Explicit End Call requested."
        )

        self._intentional_disconnect = True

        if self._disconnect_timer:

            self._disconnect_timer.cancel()

            self._disconnect_timer = None

        self._speech_generation += 1

        self._is_agent_speaking = False

        self._shutdown_event.set()

        if (
            self.room
            and self.room.isconnected()
        ):

            await self.room.disconnect()

        print(
            "[Worker] "
            "Explicit End Call completed."
        )

    # =========================================================
    # HANDOFF STATE -> THE USER'S BROWSER
    #
    # The AI's voice was the only sign the user got that they were
    # being connected to a person. Nothing changed on screen, so
    # during the silence it felt like the call had dropped.
    #
    # The frontend reads this attribute:
    #     requested  -> "Connecting you to a human agent..."
    #     connected  -> "You are speaking with a human agent"
    #
    # NOTE: the AI's attributes go away the moment it leaves the
    # room, so the frontend also infers "connected" from the admin
    # participant joining - that signal survives the AI leaving.
    # =========================================================

    HANDOFF_ATTRIBUTE = "vocira.handoff"

    # If no admin arrives within this long, the AI takes over again.
    #
    # Without it the caller was left in silence forever: the AI has
    # stopped speaking (all the handoff TTS guards), and the admin
    # never comes. The screen just kept saying "Connecting you to a
    # human agent..." while nothing happened.
    HANDOFF_ANSWER_TIMEOUT = int(
        os.getenv("HANDOFF_ANSWER_TIMEOUT_SECONDS", "60")
    )

    HANDOFF_NO_ANSWER_TEXT = (
        "I am sorry, no one from our staff is free at the moment. "
        "Your request has been saved and someone will get back to "
        "you. In the meantime, I can keep helping you."
    )

    async def _publish_handoff_state(self, state: str) -> None:

        if not self.room or not self.room.isconnected():
            return

        try:

            await self.room.local_participant.set_attributes(
                {self.HANDOFF_ATTRIBUTE: state}
            )

            print(
                f"[Handoff State] '{state}' user ko bhej diya."
            )

        except Exception as error:

            # Only a notification - a handoff must not fail over this
            print(
                f"[Handoff State] '{state}' nahi bhej sake: {error}"
            )

    # =========================================================
    # KOI ADMIN NA UTHAYE TO
    # =========================================================

    def _cancel_handoff_timeout(self):

        task = self._handoff_timeout_task

        self._handoff_timeout_task = None

        if task and not task.done():
            task.cancel()

    async def _handoff_no_answer_watchdog(self):
        """
        Muqarrara waqt tak admin na aaye to AI dobara sambhal le.

        The escalation stays 'pending' - an admin can still see it
        later on the Escalations page. All this does is keep the
        caller from sitting in silence.
        """

        try:

            await asyncio.sleep(
                self.HANDOFF_ANSWER_TIMEOUT
            )

        except asyncio.CancelledError:

            # An admin arrived - which is the whole point
            return

        if (
            self.admin_has_joined
            or not self._admin_handoff_requested
        ):
            return

        print(
            f"[Admin Handoff] "
            f"no admin arrived within "
            f"{self.HANDOFF_ANSWER_TIMEOUT}s - the AI is taking over."
        )

        # The flag has to be cleared first: without that, the
        # handoff guards in speak_text keep the AI muted.
        self._admin_handoff_requested = False

        await self._publish_handoff_state("no_answer")

        try:

            await voice_pipeline.speak_text(
                service_handle=self,
                audio_source=self.agent_source,
                text=self.HANDOFF_NO_ANSWER_TEXT,
            )

        except Exception as error:

            print(
                f"[Admin Handoff] no-answer paighaam "
                f"nahi bola ja saka: {error}"
            )

    # =========================================================
    # REQUEST ADMIN HANDOFF
    # =========================================================

    async def request_admin_handoff(
        self,
        user_id,
        user_type,
        session_id,
        user_query,
        escalation_id=None,
        message_id=None,
    ):

        if self._admin_handoff_requested:

            print(
                "[Admin Handoff] "
                "Handoff already requested."
            )

            return

        print("=" * 60)

        print(
            "[ADMIN HANDOFF REQUESTED]"
        )

        print(
            f"User ID       : {user_id}"
        )

        print(
            f"User Type     : {user_type}"
        )

        print(
            f"Session ID    : {session_id}"
        )

        print(
            f"User Request  : {user_query}"
        )

        print(
            f"Escalation ID : {escalation_id}"
        )

        print(
            f"Message ID    : {message_id}"
        )

        print("=" * 60)

        self._admin_handoff_requested = True

        self._admin_handoff_user_id = user_id

        self._admin_handoff_session_id = session_id

        self._admin_handoff_user_type = user_type

        self._admin_handoff_message_id = message_id

        self._escalation_id = escalation_id

        self._escalation_created = (
            escalation_id is not None
        )

        self._speech_generation += 1

        self._is_agent_speaking = False

        print(
            "[Admin Handoff] "
            "Current AI generation cancelled."
        )

        await self._publish_handoff_state("requested")

        if self.admin_has_joined:

            print(
                "[Admin Handoff] "
                "Admin is already in the room."
            )

            task = asyncio.create_task(
                self._complete_admin_handoff()
            )

            self._background_tasks.add(task)

            task.add_done_callback(
                self._background_tasks.discard
            )

            return

        print(
            "[Admin Handoff] "
            f"Waiting up to {self.HANDOFF_ANSWER_TIMEOUT}s "
            "for an admin to join..."
        )

        self._cancel_handoff_timeout()

        watchdog = asyncio.create_task(
            self._handoff_no_answer_watchdog()
        )

        self._handoff_timeout_task = watchdog

        self._background_tasks.add(watchdog)

        watchdog.add_done_callback(
            self._background_tasks.discard
        )

    # =========================================================
    # COMPLETE ADMIN HANDOFF
    # =========================================================

    async def _complete_admin_handoff(self):

        if not self.room:

            print(
                "[Admin Handoff] "
                "Room unavailable."
            )

            return

        if not self.room.isconnected():

            print(
                "[Admin Handoff] "
                "Room already disconnected."
            )

            return

        print(
            "[Admin Handoff] "
            "Admin successfully joined."
        )

        self._cancel_handoff_timeout()

        self._speech_generation += 1

        self._is_agent_speaking = False

        # Publish this BEFORE the AI leaves the room - otherwise the
        # news never reaches the user at all.
        await self._publish_handoff_state("connected")

        try:

            if self.agent_track:

                publications = (
                    self.room
                    .local_participant
                    .track_publications
                )

                for track_pub in publications.values():

                    if (
                        track_pub.track
                        == self.agent_track
                    ):

                        await (
                            self.room
                            .local_participant
                            .unpublish_track(
                                track_pub.sid
                            )
                        )

                        print(
                            "[Admin Handoff] "
                            "AI voice track unpublished."
                        )

                        break

        except Exception as error:

            print(
                "[Admin Handoff] "
                "Failed to unpublish AI track:"
            )

            print(error)

        try:

            print(
                "[Admin Handoff] "
                "Disconnecting AI agent..."
            )

            await self.room.disconnect()

            print(
                "[Admin Handoff] "
                "AI disconnected."
            )

        except Exception as error:

            print(
                "[Admin Handoff] "
                "Failed to disconnect AI:"
            )

            print(error)

        finally:

            self._shutdown_event.set()

    # =========================================================
    # PUBLISH AGENT VOICE
    # =========================================================

    async def _publish_agent_voice(self):

        if not self.room:

            print(
                "[LiveKit] "
                "Cannot publish agent voice. "
                "Room is unavailable."
            )

            return

        if not self.agent_track:

            print(
                "[LiveKit] "
                "Cannot publish agent voice. "
                "Agent track is unavailable."
            )

            return

        try:

            publication = (
                await self.room
                .local_participant
                .publish_track(
                    self.agent_track,
                    options=rtc.TrackPublishOptions(
                        source=(
                            rtc.TrackSource
                            .SOURCE_MICROPHONE
                        ),
                    ),
                )
            )

            print(
                f"Published Track SID: "
                f"{publication.sid}"
            )

            if self.agent_track.muted:

                self.agent_track.unmute()

            print(
                f"Track Muted State: "
                f"{publication.muted}"
            )

            print(
                "Local Publications: "
                f"{list(
                    self.room
                    .local_participant
                    .track_publications
                    .keys()
                )}"
            )

            self._track_ready.set()

        except Exception as error:

            print(
                "[LiveKit] "
                "Failed publishing agent track:"
            )

            print(error)

    # =========================================================
    # DELAYED TEARDOWN
    # =========================================================

    async def _delayed_teardown(self):

        try:

            await asyncio.sleep(10)

            print(
                "[Worker] "
                "Grace period expired. "
                "Initiating clean room teardown..."
            )

            if (
                self.room
                and self.room.isconnected()
            ):

                await self.room.disconnect()

            self._shutdown_event.set()

        except asyncio.CancelledError:

            print(
                "[Worker] "
                "Teardown cancelled. "
                "Human returned safely."
            )

    # =========================================================
    # CLEANUP
    # =========================================================

    async def cleanup(self):

        print(
            "[Worker] "
            "Cleaning up resources and "
            "cancelling background tasks..."
        )

        self._cancel_handoff_timeout()

        if self._disconnect_timer:

            self._disconnect_timer.cancel()

            self._disconnect_timer = None

        current_task = asyncio.current_task()

        for task in list(
            self._background_tasks
        ):

            if task is not current_task:

                task.cancel()

        self._background_tasks.clear()

        try:

            if (
                self.room
                and self.room.isconnected()
            ):

                await self.room.disconnect()

        except Exception as error:

            print(
                f"[Worker Cleanup] "
                f"Room disconnect failed: "
                f"{error}"
            )

        self._shutdown_event.set()

        print(
            f"[Worker] "
            f"Disconnected from "
            f"{self.room_name}."
        )