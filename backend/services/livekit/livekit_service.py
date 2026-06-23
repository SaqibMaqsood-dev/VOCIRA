import asyncio
import json
import traceback
from sqlalchemy import text
import webrtcvad
from livekit import api, rtc
from livekit.rtc import Room
from core.config import settings
from database.database import SessionLocal
from services.Speec_to_text_service.sst_whisper import STTWhisper
from services.message_services.message_create import create_message
from services.session_services.session_create import SessionCreate
from services.text_speech.piper_servies import tts_converter
from services.groq.groq import dataConverter
from ..groq import sql_prompt, human_text, intent_prompt
from typing import Optional

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
        self._is_agent_speaking = False        # NEW: true while audio is actively streaming out

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
        print(f"🚀 [Worker] Spin-up initialized for room: {self.room_name}...")

        self.agent_source = rtc.AudioSource(sample_rate=22050, num_channels=1)
        self.agent_track = rtc.LocalAudioTrack.create_audio_track("agent_voice", self.agent_source)

        @self.room.on("connected")
        def on_connected():
            print(f"✅ [Worker] Successfully connected to room: {self.room.name}")
            # NOTE: publishing happens directly after connect() below, not here,
            # to avoid a race between the connected event and the first utterance.

        @self.room.on("participant_connected")
        def on_participant_connected(participant):
            if participant.identity != "agent":
                print(f"👤 [User Joined] Human detected: {participant.identity}")
                self.human_has_joined = True
                if self._disconnect_timer:
                    self._disconnect_timer.cancel()
                    self._disconnect_timer = None

        @self.room.on("track_subscribed")
        def on_track_subscribed(track, publication, participant):
            if track.kind == rtc.TrackKind.KIND_AUDIO:
                print(f"🎤 [Audio Active] Subscribed to track from {participant.identity}")
                t = asyncio.create_task(
                    consume_audio(
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

        @self.room.on("participant_disconnected")
        def on_participant_disconnected(participant):
            print(f"🚪 [User Left] Participant left: {participant.identity}")
            if self.human_has_joined:
                humans_in_room = [p for p in self.room.remote_participants.values() if p.identity != "agent"]
                if not humans_in_room:
                    print("🤫 [Worker] Last human left. Starting 10s grace period countdown...")
                    if self._disconnect_timer:
                        self._disconnect_timer.cancel()
                    self._disconnect_timer = asyncio.create_task(self._delayed_teardown(session_id))

        try:
            await self.room.connect(settings.LIVEKIT_URL, token)
            # Publish directly here — no race with event ordering
            await self._publish_agent_voice()
            await self._shutdown_event.wait()
        except Exception as e:
            print(f"❌ [Worker Error] Loop exception occurred: {e}")
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
            print(f"📡 Published Track SID: {publication.sid}")

            if self.agent_track.muted:
                self.agent_track.unmute()

            print(f"🎤 Track Muted State: {publication.muted}")
            print(f"📚 Local Publications: {list(self.room.local_participant.track_publications.keys())}")

            self._track_ready.set()
        except Exception as e:
            print(f"❌ [LiveKit] Failed publishing agent track: {e}")

    async def _delayed_teardown(self, session_id):
        try:
            await asyncio.sleep(10)
            print("🤫 [Worker] Grace period expired. Initiating clean room teardown...")
            if self.room and self.room.isconnected():
                await self.room.disconnect()
            self._shutdown_event.set()
        except asyncio.CancelledError:
            print("🔄 [Worker] Teardown cancelled. Human returned safely.")

    async def cleanup(self):
        print("🛑 [Worker] Cleaning up resources and cancelling ghost tasks...")
        if self._disconnect_timer:
            self._disconnect_timer.cancel()
        for task in list(self._background_tasks):
            task.cancel()
        self._shutdown_event.set()
        print(f"🛑 [Worker] Disconnected from {self.room_name}. Releasing process channel.")


async def consume_audio(track, stt, participant, service_handle, session_id, audio_source):
    metadata = json.loads(participant.metadata or "{}")
    user_id = metadata.get("user_id") or participant.identity
    user_type = metadata.get("type")

    if not track:
        return

    try:
        stream = rtc.AudioStream(track)
    except Exception as e:
        print(f"❌ Failed to create AudioStream: {e}")
        return

    vad = webrtcvad.Vad(2)
    audio_buffer = bytearray()
    voice_accumulation = bytearray()
    is_speaking = False
    silence_frames = 0
    SILENCE_LIMIT = 25
    MAX_ACCUMULATION_BYTES = 32000 * 2 * 15
    sample_rate = None
    vad_frame_size = None

    try:
        async for event in stream:
            frame = event.frame
            if sample_rate is None:
                sample_rate = frame.sample_rate
                vad_frame_size = int(sample_rate * 30 / 1000) * 2 * frame.num_channels

            audio_buffer.extend(frame.data)

            while len(audio_buffer) >= vad_frame_size:
                chunk = bytes(audio_buffer[:vad_frame_size])
                del audio_buffer[:vad_frame_size]

                speech = await asyncio.to_thread(vad.is_speech, chunk, sample_rate)

                if speech:
                    silence_frames = 0
                    voice_accumulation.extend(chunk)
                    if not is_speaking:
                        is_speaking = True
                        # Barge-in: user started talking again — interrupt agent immediately
                        if service_handle._is_agent_speaking:
                            service_handle._speech_generation += 1
                            print(f"✋ [Barge-In] User interrupted — bumping to gen {service_handle._speech_generation}, stopping agent audio.")
                elif is_speaking:
                    silence_frames += 1
                    voice_accumulation.extend(chunk)

                    if silence_frames >= SILENCE_LIMIT or len(voice_accumulation) > MAX_ACCUMULATION_BYTES:
                        captured_audio = bytes(voice_accumulation)

                        service_handle._speech_generation += 1
                        my_generation = service_handle._speech_generation

                        t = asyncio.create_task(
                            process_voice_intent(
                                chunk=captured_audio,
                                stt=stt,
                                user_id=user_id,
                                usertype=user_type,
                                session_id=session_id,
                                audio_source=audio_source,
                                service_handle=service_handle,
                                generation=my_generation,
                            )
                        )
                        service_handle._background_tasks.add(t)
                        t.add_done_callback(service_handle._background_tasks.discard)

                        voice_accumulation.clear()
                        silence_frames = 0
                        is_speaking = False
    except Exception as e:
        print(f"❌ Audio Consumer Error: {e}")
    finally:
        await stream.aclose()


async def process_voice_intent(chunk: bytes, stt, user_id, usertype, session_id, audio_source, service_handle, generation: int):
    try:
        sql_text = await asyncio.to_thread(stt.transcribe_bytes, chunk)
        if not sql_text or not sql_text.strip():
            return

        print(f"🗣️ [User]: {sql_text}")
        db_sender_type = "user" if usertype != "agent" else "agent"

        async with SessionLocal() as db:
            await create_message(db=db, content=sql_text, user_id=user_id, usertype=db_sender_type, session_id=session_id)
            
            router_prompt = intent_prompt.INTENT_ROUTER_PROMPT.format(user_query=sql_text)
            router_result = await dataConverter(router_prompt)
            intent = router_result.choices[0].message.content.strip().upper()

            ai_response_text = ""

            if "DB_QUERY" in intent:
                print("🔍 [Route]: Database Query Pipeline")
                prompt = sql_prompt.build_prompt(user_query=sql_text)
                result = await dataConverter(prompt)
                response_sql = result.choices[0].message.content
                print(f"⚙️ [Generated SQL]: {response_sql}")

                if "LIMIT" not in response_sql.upper() and "SELECT" in response_sql.upper():
                    response_sql = f"{response_sql.rstrip(';')} LIMIT 5;"

                db_response = await db.execute(text(response_sql))
                rows = db_response.fetchall()
                data = [dict(row._mapping) for row in rows][:5]
                print(f"📊 [SQL Result Windowed]: {data}")

                sql_result_prompt = human_text.build_response_prompt(user_query=sql_text, sql_result=data)
                converter_text = await dataConverter(prompt=sql_result_prompt)
                ai_response_text = converter_text.choices[0].message.content
            else:
                print("👋 [Route]: General Conversation Pipeline")
                general_prompt = f"You are a helpful AI voice assistant named 'Vocira'. Respond naturally and concisely to the user's input: {sql_text}"
                converter_text = await dataConverter(prompt=general_prompt)
                ai_response_text = converter_text.choices[0].message.content

            print(f"🤖 [AI]: {ai_response_text}")
            await create_message(db=db, content=ai_response_text, user_id=user_id, usertype="agent", session_id=session_id)

        audio_bytes = await asyncio.to_thread(tts_converter, text=ai_response_text)
        if not audio_bytes:
            print("⚠️ [TTS] No audio bytes generated, skipping voice playback.")
            return

        try:
            await asyncio.wait_for(service_handle._track_ready.wait(), timeout=5)
        except asyncio.TimeoutError:
            print("⚠️ [LiveKit Stream] Agent track not ready after 5s — aborting voice send.")
            return

        # --- Serialized playback: only one response streams audio at a time ---
        async with service_handle._tts_lock:

            if generation != service_handle._speech_generation:
                print(f"⏭️ [LiveKit Stream] Skipping stale response (gen {generation} superseded by {service_handle._speech_generation}).")
                return

            if audio_source and service_handle.room and service_handle.room.isconnected():
                print("🔊 [LiveKit Stream] Shipping audio frames down the WebRTC track...")

                sample_rate = 22050
                num_channels = 1
                bytes_per_sample = 2
                samples_per_channel = int(sample_rate * 20 / 1000)
                chunk_size = samples_per_channel * num_channels * bytes_per_sample

                service_handle._is_agent_speaking = True
                try:
                    for i in range(0, len(audio_bytes), chunk_size):
                        # Check on every frame — bail out instantly if interrupted or room dropped
                        if generation != service_handle._speech_generation:
                            print(f"✋ [LiveKit Stream] Interrupted mid-stream (gen {generation} superseded). Stopping playback.")
                            break

                        if not service_handle.room or not service_handle.room.isconnected():
                            print("🛑 [LiveKit Stream] Room disconnected mid-stream. Aborting framing.")
                            break

                        frame_chunk = audio_bytes[i:i + chunk_size]
                        if len(frame_chunk) < chunk_size:
                            frame_chunk += b'\x00' * (chunk_size - len(frame_chunk))

                        audio_frame = rtc.AudioFrame(
                            data=frame_chunk,
                            sample_rate=sample_rate,
                            num_channels=num_channels,
                            samples_per_channel=samples_per_channel
                        )

                        try:
                            await audio_source.capture_frame(audio_frame)
                        except Exception as frame_err:
                            print(f"⚠️ [Stream Warning] Core frame submission bypassed: {frame_err}")
                            break
                finally:
                    service_handle._is_agent_speaking = False

                print("✅ [LiveKit Stream] Audio generation stream completed.")
            else:
                print("⚠️ [LiveKit Stream] audio_source or room unavailable — voice response not sent.")

    except Exception as e:
        print(f"❌ [Pipeline Error]: {traceback.format_exc()}")