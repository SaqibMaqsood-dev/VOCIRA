import asyncio
import json
from typing import Optional

from livekit import api, rtc
from livekit.rtc import Room

from core.config import settings
from services.Speec_to_text_service.sst_whisper import STTWhisper
from services.session_services.session_create import SessionCreate

from . import voice_pipeline

stt = STTWhisper()


class LivekitServices:
    def __init__(self, user_role: str, user_id: Optional[int] = None):
        self.user_id = user_id
        self.user_role = user_role
        self.human_has_joined = False
        self.room = None
        self.room_name = None
        self.agent_source = None
        self.agent_track = None
        self._background_tasks = set()
        self._disconnect_timer = None
        self._shutdown_event = asyncio.Event()
        self._track_ready = asyncio.Event()
        self._tts_lock = asyncio.Lock()        # ensures only one voice response streams at a time
        self._speech_generation = 0            # used to drop stale/superseded responses
        self._is_agent_speaking = False         # true while audio is actively streaming out

    def livekit_token(self, api_key, api_secret, room_name: str, user_name: str):
        metadata = {
            "user_id": str(self.user_id) if self.user_id else "guest",
            "role": getattr(self.user_role, "value", str(self.user_role)),
            "type": "agent" if user_name == "agent" else "participant"
        }

        return (
            api.AccessToken(api_key, api_secret)
            .with_identity(str(self.user_id) if self.user_id else "guest")
            .with_name(user_name)
            .with_grants(
                api.VideoGrants(room_join=True, room=room_name, can_publish=True, can_subscribe=True)
            )
            .with_room_config(
                api.RoomConfiguration(departure_timeout=30, empty_timeout=60)
            )
            .with_metadata(metadata=json.dumps(metadata))
        ).to_jwt()

    async def connect_worker(self, token: str, session_id: str):
        self.room = Room()
        self.room_name = f"room-{session_id}"
        self.human_has_joined = False
        self._shutdown_event.clear()
        self._track_ready.clear()
        self._speech_generation = 0
        print(f" [Worker] Spin-up initialized for room: {self.room_name}...")

        self.agent_source = rtc.AudioSource(sample_rate=22050, num_channels=1)
        self.agent_track = rtc.LocalAudioTrack.create_audio_track("agent_voice", self.agent_source)

        @self.room.on("connected")
        def on_connected():
            print(f" [Worker] Successfully connected to room: {self.room.name}")
            # NOTE: publishing happens directly after connect() below, not here,
            # to avoid a race between the connected event and the first utterance.

        @self.room.on("participant_connected")
        def on_participant_connected(participant):
            if participant.identity != "agent":
                print(f" [User Joined] Human detected: {participant.identity}")
                self.human_has_joined = True
                if self._disconnect_timer:
                    self._disconnect_timer.cancel()
                    self._disconnect_timer = None

        @self.room.on("participant_disconnected")
        def on_participant_disconnected(participant):
            print(f"[User Left] Participant left: {participant.identity}")
            if self.human_has_joined:
                humans_in_room = [p for p in self.room.remote_participants.values() if p.identity != "agent"]
                if not humans_in_room:
                    print("[Worker] Last human left. Starting 10s grace period countdown...")
                    if self._disconnect_timer:
                        self._disconnect_timer.cancel()
                    self._disconnect_timer = asyncio.create_task(self._delayed_teardown())

        @self.room.on("track_subscribed")
        def on_track_subscribed(track, publication, participant):
            if track.kind == rtc.TrackKind.KIND_AUDIO:
                print(f" [Audio Active] Subscribed to track from {participant.identity}")
                t = asyncio.create_task(
                    voice_pipeline.consume_audio(
                        stt=stt,
                        track=track,
                        participant=participant,
                        service_handle=self,
                        session_id=session_id,
                        audio_source=self.agent_source
                    )
                )
                self._background_tasks.add(t)
                t.add_done_callback(self._background_tasks.discard)

        try:
            await self.room.connect(settings.LIVEKIT_URL, token)
            # Publish directly here — no race with event ordering
            await self._publish_agent_voice()
            await self._shutdown_event.wait()
        except Exception as e:
            print(f" [Worker Error] Loop exception occurred: {e}")
        finally:
            await self.cleanup()
            await SessionCreate.close_session_by_id(session_id=session_id)

    async def _publish_agent_voice(self):
        try:
            publication = await self.room.local_participant.publish_track(
                self.agent_track,
                options=rtc.TrackPublishOptions(
                    source=rtc.TrackSource.SOURCE_MICROPHONE,
                )
            )
            print(f" Published Track SID: {publication.sid}")

            if self.agent_track.muted:
                self.agent_track.unmute()

            print(f" Track Muted State: {publication.muted}")
            print(f" Local Publications: {list(self.room.local_participant.track_publications.keys())}")

            self._track_ready.set()
        except Exception as e:
            print(f" [LiveKit] Failed publishing agent track: {e}")

    async def _delayed_teardown(self):
        try:
            await asyncio.sleep(10)
            print(" [Worker] Grace period expired. Initiating clean room teardown...")
            if self.room and self.room.isconnected():
                await self.room.disconnect()
            self._shutdown_event.set()
        except asyncio.CancelledError:
            print(" [Worker] Teardown cancelled. Human returned safely.")

    async def cleanup(self):
        print(" [Worker] Cleaning up resources and cancelling ghost tasks...")
        if self._disconnect_timer:
            self._disconnect_timer.cancel()
        for task in list(self._background_tasks):
            task.cancel()
        self._shutdown_event.set()
        print(f" [Worker] Disconnected from {self.room_name}. Releasing process channel.")
        