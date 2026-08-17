import asyncio
import json
import traceback

import webrtcvad
from sqlalchemy import text
from livekit import rtc

from backend.microservices.livekit_Rag_services.services.groq import human_text , intent_prompt
from backend.helper_functions.database import SessionLocal

from backend.microservices.livekit_Rag_services.services.router_services.message_service import MessageService
from backend.microservices.livekit_Rag_services.services.text_speech.piper_servies import tts_converter
from backend.microservices.livekit_Rag_services.services.groq.groq import dataConverter
from backend.microservices.livekit_Rag_services.services.groq import sql_prompt
from backend.microservices.livekit_Rag_services.services.rag_engine.query import ask_vocira



from uuid import UUID
msg_serivce = MessageService()

async def consume_audio(
    track,
    stt,
    participant,
    service_handle,
    session_id,
    audio_source,
):
    """
    Consume audio from a LiveKit participant.

    Important:
    - Authenticated users -> real UUID user_id
    - Guest users -> user_id = None
    - participant.identity is NEVER used as user_id
    """

    # =========================================================
    # 1. Read participant metadata
    # =========================================================

    try:
        metadata = json.loads(participant.metadata or "{}")
    except (json.JSONDecodeError, TypeError):
        print(
            f"⚠️ Invalid metadata from participant "
            f"{participant.identity}: {participant.metadata}"
        )
        metadata = {}

    raw_user_id = metadata.get("user_id")
    user_type = metadata.get("type", "participant")

    # =========================================================
    # 2. Validate user_id
    # =========================================================

    user_id = None

    if raw_user_id is not None:
        raw_user_id = str(raw_user_id).strip()

        # Guest / empty values
        if raw_user_id.lower() not in {
            "",
            "guest",
            "none",
            "null",
            "anonymous",
        }:
            try:
                # Make sure it is REALLY a UUID
                user_id = UUID(raw_user_id)

            except (ValueError, TypeError, AttributeError):
                print(
                    f"⚠️ Invalid user_id received: {raw_user_id}"
                )
                print(
                    "⚠️ Treating participant as guest."
                )
                user_id = None

    # =========================================================
    # 3. Logging  
    # =========================================================

    print("=" * 60)
    print(f"👤 Participant Identity : {participant.identity}")
    print(f"👤 User ID              : {user_id}")
    print(f"👤 User Type            : {user_type}")
    print(f"📦 Metadata             : {metadata}")
    print("=" * 60)

    # =========================================================
    # 4. Validate audio track
    # =========================================================

    if not track:
        print("⚠️ No audio track received.")
        return

    try:
        stream = rtc.AudioStream(track)

    except Exception as e:
        print(f"❌ Failed to create AudioStream: {e}")
        return

    # =========================================================
    # 5. VAD configuration
    # =========================================================

    vad = webrtcvad.Vad(2)

    audio_buffer = bytearray()
    voice_accumulation = bytearray()

    is_speaking = False
    silence_frames = 0

    SILENCE_LIMIT = 25
    MAX_ACCUMULATION_BYTES = 32000 * 2 * 15

    sample_rate = None
    vad_frame_size = None

    # =========================================================
    # 6. Consume audio
    # =========================================================

    try:

        async for event in stream:

            frame = event.frame

            # -------------------------------------------------
            # Initialize audio properties
            # -------------------------------------------------

            if sample_rate is None:

                sample_rate = frame.sample_rate

                vad_frame_size = (
                    int(sample_rate * 30 / 1000)
                    * 2
                    * frame.num_channels
                )

                print(
                    f"🎵 Audio initialized: "
                    f"sample_rate={sample_rate}, "
                    f"channels={frame.num_channels}"
                )

            audio_buffer.extend(frame.data)

            # -------------------------------------------------
            # Process complete VAD frames
            # -------------------------------------------------

            while len(audio_buffer) >= vad_frame_size:

                chunk = bytes(
                    audio_buffer[:vad_frame_size]
                )

                del audio_buffer[:vad_frame_size]

                speech = await asyncio.to_thread(
                    vad.is_speech,
                    chunk,
                    sample_rate,
                )

                # =================================================
                # USER IS SPEAKING
                # =================================================

                if speech:

                    silence_frames = 0

                    voice_accumulation.extend(chunk)

                    if not is_speaking:

                        is_speaking = True

                        print(
                            f"🎤 [Speech Started] "
                            f"{participant.identity}"
                        )

                        # -------------------------------------------------
                        # Barge-in
                        # -------------------------------------------------

                        if service_handle._is_agent_speaking:

                            service_handle._speech_generation += 1

                            print(
                                "✋ [Barge-In] User interrupted agent. "
                                f"Generation: "
                                f"{service_handle._speech_generation}"
                            )

                # =================================================
                # USER STOPPED SPEAKING
                # =================================================

                elif is_speaking:

                    silence_frames += 1

                    voice_accumulation.extend(chunk)

                    # -------------------------------------------------
                    # Speech finished
                    # -------------------------------------------------

                    if (
                        silence_frames >= SILENCE_LIMIT
                        or len(voice_accumulation)
                        > MAX_ACCUMULATION_BYTES
                    ):

                        captured_audio = bytes(
                            voice_accumulation
                        )

                        print(
                            "🛑 [Speech Finished] "
                            f"Audio bytes: "
                            f"{len(captured_audio)}"
                        )

                        # -------------------------------------------------
                        # New generation
                        # -------------------------------------------------

                        service_handle._speech_generation += 1

                        my_generation = (
                            service_handle._speech_generation
                        )

                        # -------------------------------------------------
                        # Process speech
                        # -------------------------------------------------

                        task = asyncio.create_task(
                            process_voice_intent(
                                chunk=captured_audio,
                                stt=stt,

                                # IMPORTANT:
                                # This is None for guests
                                # and UUID for authenticated users.
                                user_id=user_id,

                                usertype=user_type,

                                session_id=session_id,

                                audio_source=audio_source,

                                service_handle=service_handle,

                                generation=my_generation,
                            )
                        )

                        service_handle._background_tasks.add(
                            task
                        )

                        task.add_done_callback(
                            service_handle._background_tasks.discard
                        )

                        # -------------------------------------------------
                        # Reset speech state
                        # -------------------------------------------------

                        voice_accumulation.clear()

                        silence_frames = 0

                        is_speaking = False

    except Exception:

        print(
            "❌ Audio Consumer Error:"
        )

        traceback.print_exc()

    finally:

        try:
            await stream.aclose()
        except Exception as e:
            print(
                f"⚠️ Failed to close audio stream: {e}"
            )


async def process_voice_intent(chunk: bytes, stt, user_id, usertype, session_id, audio_source, service_handle, generation: int):
    try:
        sql_text = await asyncio.to_thread(stt.transcribe_bytes, chunk)
        if not sql_text or not sql_text.strip():
            return

        print(f"🗣️ [User]: {sql_text}")
        db_sender_type = "user" if usertype != "agent" else "agent"

        async with SessionLocal() as db:
            await msg_serivce.create_message(db=db, content=sql_text, user_id=user_id, usertype=db_sender_type, session_id=session_id)

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

                print("👋 [Route]  :  General Conversation Pipeline")
                general_prompt     =  f"You are a helpful AI voice assistant named 'Vocira'. Respond naturally and concisely to the user's input: {sql_text}"
                converter_text     =  ask_vocira(retriever= general_prompt, user_query=general_prompt)
                ai_response_text   =  converter_text.choices[0].message.content
                                                    
            print(f"🤖 [AI]: {ai_response_text}")
            await msg_serivce.create_message(db=db, content=ai_response_text, user_id=user_id, usertype="agent", session_id=session_id)

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