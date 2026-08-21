import asyncio
import json
import traceback
from uuid import UUID

import webrtcvad
from livekit import rtc

from backend.microservices.livekit_Rag_services.services.rag_engine.vectorstore import (
    connect_existing_store,
)

from backend.microservices.livekit_Rag_services.services.groq import (
    human_text,
    intent_prompt,
)

from backend.helper_functions.database import SessionLocal

from backend.microservices.livekit_Rag_services.services.router_services.message_service import (
    MessageService,
)

from backend.microservices.livekit_Rag_services.services.text_speech.piper_servies import (
    tts_converter,
)

from backend.microservices.livekit_Rag_services.services.groq.groq import (
    dataConverter,
)

from backend.microservices.livekit_Rag_services.services.rag_engine.query import (
    ask_vocira,
)

from backend.microservices.livekit_Rag_services.services.rag_engine.config import (
    INDEX_NAME,
)

from backend.microservices.livekit_Rag_services.services.erp_services.auth_client import (
    AuthClient,
)

from backend.microservices.livekit_Rag_services.services.erp_services.erp_service import (
    ERPService,
)

from backend.microservices.livekit_Rag_services.core.config import (
    settings,
)


# =========================================================
# Service Initialization
# =========================================================

message_service = MessageService()

auth_client = AuthClient(
    base_url=settings.AUTH_SERVICE_URL,
)

erp_service = ERPService()


# =========================================================
# RAG Retriever
# =========================================================

retriever = connect_existing_store(
    index_name=INDEX_NAME,
)


# =========================================================
# ERP Authorization Roles
# =========================================================

ERP_ALLOWED_ROLES = {
    "guardian",
    "admin",
}


# =========================================================
# Consume LiveKit Audio
# =========================================================

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

    Access model:

        Guest:
            user_id = None
            RAG = allowed
            ERP = denied

        Guardian:
            user_id = VOCIRA UUID
            RAG = allowed
            ERP = allowed

        Admin:
            user_id = VOCIRA UUID
            RAG = allowed
            ERP = allowed

    Important:
        participant.identity is never used as the VOCIRA user ID.
        The authenticated user ID is obtained from participant metadata.
    """

    # =========================================================
    # 1. Read Participant Metadata
    # =========================================================

    try:
        metadata = json.loads(
            participant.metadata or "{}"
        )

    except (
        json.JSONDecodeError,
        TypeError,
    ):
        print(
            f"⚠️ Invalid metadata from participant "
            f"{participant.identity}: "
            f"{participant.metadata}"
        )

        metadata = {}

    raw_user_id = metadata.get("user_id")

    user_type = metadata.get(
        "type",
        "guest",
    )

    user_type = str(
        user_type
    ).strip().lower()

    # =========================================================
    # 2. Validate User ID
    # =========================================================

    user_id = None

    if raw_user_id is not None:

        raw_user_id = str(
            raw_user_id
        ).strip()

        if raw_user_id.lower() not in {
            "",
            "guest",
            "none",
            "null",
            "anonymous",
        }:

            try:
                user_id = UUID(
                    raw_user_id
                )

            except (
                ValueError,
                TypeError,
                AttributeError,
            ):
                print(
                    f"⚠️ Invalid user_id received: "
                    f"{raw_user_id}"
                )

                print(
                    "⚠️ Treating participant as guest."
                )

                user_id = None
                user_type = "guest"

    # =========================================================
    # 3. Guest Normalization
    # =========================================================

    if user_id is None:
        user_type = "guest"

    # =========================================================
    # 4. Participant Logging
    # =========================================================

    print("=" * 60)

    print(
        f"👤 Participant Identity : "
        f"{participant.identity}"
    )

    print(
        f"👤 VOCIRA User ID       : "
        f"{user_id}"
    )

    print(
        f"👤 User Type            : "
        f"{user_type}"
    )

    print(
        f"📦 Metadata             : "
        f"{metadata}"
    )

    print(
        f"🔐 ERP Allowed          : "
        f"{user_type in ERP_ALLOWED_ROLES and user_id is not None}"
    )

    print("=" * 60)

    # =========================================================
    # 5. Validate Audio Track
    # =========================================================

    if not track:
        print(
            "⚠️ No audio track received."
        )

        return

    try:
        stream = rtc.AudioStream(
            track
        )

    except Exception as error:
        print(
            f"❌ Failed to create AudioStream: "
            f"{error}"
        )

        return

    # =========================================================
    # 6. Voice Activity Detection Configuration
    # =========================================================

    vad = webrtcvad.Vad(2)

    audio_buffer = bytearray()

    voice_accumulation = bytearray()

    is_speaking = False

    silence_frames = 0

    SILENCE_LIMIT = 25

    MAX_ACCUMULATION_BYTES = (
        32000 * 2 * 15
    )

    sample_rate = None

    vad_frame_size = None

    # =========================================================
    # 7. Consume Audio Stream
    # =========================================================

    try:

        async for event in stream:

            frame = event.frame

            # -------------------------------------------------
            # Initialize Audio Properties
            # -------------------------------------------------

            if sample_rate is None:

                sample_rate = (
                    frame.sample_rate
                )

                vad_frame_size = (
                    int(
                        sample_rate
                        * 30
                        / 1000
                    )
                    * 2
                    * frame.num_channels
                )

                print(
                    f"🎵 Audio initialized: "
                    f"sample_rate={sample_rate}, "
                    f"channels={frame.num_channels}"
                )

            audio_buffer.extend(
                frame.data
            )

            # -------------------------------------------------
            # Process Complete VAD Frames
            # -------------------------------------------------

            while (
                len(audio_buffer)
                >= vad_frame_size
            ):

                audio_chunk = bytes(
                    audio_buffer[
                        :vad_frame_size
                    ]
                )

                del audio_buffer[
                    :vad_frame_size
                ]

                speech_detected = await asyncio.to_thread(
                    vad.is_speech,
                    audio_chunk,
                    sample_rate,
                )

                # =================================================
                # User Is Speaking
                # =================================================

                if speech_detected:

                    silence_frames = 0

                    voice_accumulation.extend(
                        audio_chunk
                    )

                    if not is_speaking:

                        is_speaking = True

                        print(
                            f"🎤 [Speech Started] "
                            f"{participant.identity}"
                        )

                        # -------------------------------------------------
                        # Barge-In
                        # -------------------------------------------------

                        if (
                            service_handle
                            ._is_agent_speaking
                        ):

                            service_handle._speech_generation += 1

                            print(
                                "✋ [Barge-In] "
                                "User interrupted agent. "
                                f"Generation: "
                                f"{service_handle._speech_generation}"
                            )

                # =================================================
                # User Stopped Speaking
                # =================================================

                elif is_speaking:

                    silence_frames += 1

                    voice_accumulation.extend(
                        audio_chunk
                    )

                    # -------------------------------------------------
                    # Speech Finished
                    # -------------------------------------------------

                    if (
                        silence_frames
                        >= SILENCE_LIMIT
                        or len(
                            voice_accumulation
                        )
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
                        # Start New Generation
                        # -------------------------------------------------

                        service_handle._speech_generation += 1

                        generation_id = (
                            service_handle
                            ._speech_generation
                        )

                        # -------------------------------------------------
                        # Process User Speech
                        # -------------------------------------------------

                        task = asyncio.create_task(
                            process_voice_intent(
                                chunk=captured_audio,
                                stt=stt,
                                user_id=user_id,
                                user_type=user_type,
                                session_id=session_id,
                                audio_source=audio_source,
                                service_handle=service_handle,
                                generation=generation_id,
                            )
                        )

                        service_handle._background_tasks.add(
                            task
                        )

                        task.add_done_callback(
                            service_handle
                            ._background_tasks
                            .discard
                        )

                        # -------------------------------------------------
                        # Reset Speech State
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

        except Exception as error:

            print(
                f"⚠️ Failed to close audio stream: "
                f"{error}"
            )




# =========================================================
# Process Voice Intent
# =========================================================
async def process_voice_intent(
    chunk: bytes,
    stt,
    user_id,
    user_type,
    session_id,
    audio_source,
    service_handle,
    generation: int,
):

    try:

        # =====================================================
        # 1. Speech -> Text
        # =====================================================

        user_query = await asyncio.to_thread(
            stt.transcribe_bytes,
            chunk,
        )

        if not user_query or not user_query.strip():
            return

        user_query = user_query.strip()

        print(
            f"🗣️ [User]: {user_query}"
        )

        # =====================================================
        # 2. Database sender type
        # =====================================================

        db_sender_type = (
            "user"
            if user_type != "agent"
            else "agent"
        )

        # =====================================================
        # 3. Database transaction
        # =====================================================

        async with SessionLocal() as db:

            # =================================================
            # Save user message
            # =================================================

            await message_service.create_message(
                db=db,
                content=user_query,
                user_id=user_id,
                usertype=db_sender_type,
                session_id=session_id,
            )

            # =================================================
            # 4. Intent Router
            # =================================================

            router_prompt = (
                intent_prompt.INTENT_ROUTER_PROMPT.format(
                    user_query=user_query
                )
            )

            router_result = await dataConverter(
                router_prompt
            )

            intent = (
                router_result
                .choices[0]
                .message
                .content
                .strip()
                .upper()
            )

            print(
                f"🧭 [Intent]: {intent}"
            )

            ai_response_text = ""

            # =================================================
            # 5. ERP QUERY
            # =================================================

            if "ERP_QUERY" in intent:

                print(
                    "🏫 [Route]: ERP Pipeline"
                )

                # =================================================
                # Security check
                # =================================================

                if (
                    not user_id
                    or user_type not in ERP_ALLOWED_ROLES
                ):

                    print(
                        f"🚫 [ERP Access Denied] "
                        f"user_type={user_type}, "
                        f"user_id={user_id}"
                    )

                    ai_response_text = (
                        "You are not authorized to access "
                        "ERP information. "
                        "Please log in with an authorized account."
                    )

                else:

                    try:

                        # =============================================
                        # Get user from Auth Service
                        # =============================================

                        user = await auth_client.get_user(
                            user_id=user_id
                        )

                        print(
                            f"👤 [Auth User]: {user}"
                        )

                        # =============================================
                        # Get actual role
                        # =============================================

                        auth_role = user.get("role")

                        if isinstance(auth_role, dict):

                            auth_role = auth_role.get("name")

                        if auth_role:

                            auth_role = str(
                                auth_role
                            ).strip().lower()

                        print(
                            f"🔐 [Auth Role]: {auth_role}"
                        )

                        # =============================================
                        # Second security check
                        # =============================================

                        if (
                            auth_role
                            not in ERP_ALLOWED_ROLES
                        ):

                            print(
                                f"🚫 [ERP Access Denied] "
                                f"Auth role={auth_role}"
                            )

                            ai_response_text = (
                                "You are not authorized "
                                "to access ERP information."
                            )

                        else:

                            # =========================================
                            # Get ERP parent ID
                            # =========================================

                            erp_parent_id = user.get(
                                "parent_id"
                            )

                            if not erp_parent_id:

                                ai_response_text = (
                                    "Your VOCIRA account is not "
                                    "linked to an ERP account."
                                )

                            else:

                                print(
                                    f"🏫 [ERP Parent ID]: "
                                    f"{erp_parent_id}"
                                )

                                # =====================================
                                # Query ERP
                                # =====================================

                                erp_data = (
                                    await erp_service.handle_query(
                                        user_query=user_query,
                                        erp_parent_id=erp_parent_id,
                                    )
                                )

                                print(
                                    f"🏫 [ERP Data]: "
                                    f"{erp_data}"
                                )

                                # =====================================
                                # ERP data -> natural language
                                # =====================================

                                response_prompt = (
                                    human_text.build_response_prompt(
                                        user_query=user_query,
                                        response=erp_data,
                                    )
                                )

                                converter_response = (
                                    await dataConverter(
                                        prompt=response_prompt
                                    )
                                )

                                ai_response_text = (
                                    converter_response
                                    .choices[0]
                                    .message
                                    .content
                                    .strip()
                                )

                    except Exception as erp_error:

                        print(
                            f"❌ [ERP Pipeline Error]: "
                            f"{erp_error}"
                        )

                        traceback.print_exc()

                        ai_response_text = (
                            "Sorry, I was unable to retrieve "
                            "your ERP information right now."
                        )

            # =================================================
            # 6. RAG QUERY
            # =================================================

            else:

                print(
                    "📚 [Route]: RAG Pipeline"
                )

                ai_response_text = await ask_vocira(
                    retriever=retriever,
                    user_query=user_query,
                )

                if ai_response_text:

                    ai_response_text = (
                        ai_response_text
                        .strip()
                    )

            # =================================================
            # 7. Save AI response
            # =================================================

            print(
                f"🤖 [AI]: {ai_response_text}"
            )

            await message_service.create_message(
                db=db,
                content=ai_response_text,
                user_id=user_id,
                usertype="agent",
                session_id=session_id,
            )

        # =====================================================
        # 8. Text -> Speech
        # =====================================================

        audio_bytes = await asyncio.to_thread(
            tts_converter,
            text=ai_response_text,
        )

        if not audio_bytes:

            print(
                "⚠️ [TTS] No audio bytes generated, "
                "skipping voice playback."
            )

            return

        # =====================================================
        # 9. Wait for LiveKit track
        # =====================================================

        try:

            await asyncio.wait_for(
                service_handle._track_ready.wait(),
                timeout=5,
            )

        except asyncio.TimeoutError:

            print(
                "⚠️ [LiveKit Stream] "
                "Agent track not ready after 5s — "
                "aborting voice send."
            )

            return

        # =====================================================
        # 10. Serialized playback
        # =====================================================

        async with service_handle._tts_lock:

            # =================================================
            # Check stale generation
            # =================================================

            if (
                generation
                != service_handle._speech_generation
            ):

                print(
                    f"⏭️ [LiveKit Stream] "
                    f"Skipping stale response "
                    f"(gen {generation} superseded by "
                    f"{service_handle._speech_generation})."
                )

                return

            # =================================================
            # Check LiveKit room
            # =================================================

            if (
                audio_source
                and service_handle.room
                and service_handle.room.isconnected()
            ):

                print(
                    "🔊 [LiveKit Stream] "
                    "Shipping audio frames down "
                    "the WebRTC track..."
                )

                sample_rate = 22050
                num_channels = 1
                bytes_per_sample = 2

                samples_per_channel = int(
                    sample_rate * 20 / 1000
                )

                chunk_size = (
                    samples_per_channel
                    * num_channels
                    * bytes_per_sample
                )

                service_handle._is_agent_speaking = True

                try:

                    for i in range(
                        0,
                        len(audio_bytes),
                        chunk_size,
                    ):

                        # =============================================
                        # Check interruption
                        # =============================================

                        if (
                            generation
                            != service_handle._speech_generation
                        ):

                            print(
                                "✋ [LiveKit Stream] "
                                "Interrupted mid-stream. "
                                "Stopping playback."
                            )

                            break

                        # =============================================
                        # Check room
                        # =============================================

                        if (
                            not service_handle.room
                            or not service_handle.room.isconnected()
                        ):

                            print(
                                "🛑 [LiveKit Stream] "
                                "Room disconnected mid-stream."
                            )

                            break

                        frame_chunk = audio_bytes[
                            i:i + chunk_size
                        ]

                        # =============================================
                        # Pad incomplete frame
                        # =============================================

                        if len(frame_chunk) < chunk_size:

                            frame_chunk += (
                                b"\x00"
                                * (
                                    chunk_size
                                    - len(frame_chunk)
                                )
                            )

                        audio_frame = rtc.AudioFrame(
                            data=frame_chunk,
                            sample_rate=sample_rate,
                            num_channels=num_channels,
                            samples_per_channel=(
                                samples_per_channel
                            ),
                        )

                        try:

                            await audio_source.capture_frame(
                                audio_frame
                            )

                        except Exception as frame_error:

                            print(
                                f"⚠️ [Stream Warning] "
                                f"Frame submission failed: "
                                f"{frame_error}"
                            )

                            break

                finally:

                    service_handle._is_agent_speaking = False

                print(
                    "✅ [LiveKit Stream] "
                    "Audio generation stream completed."
                )

            else:

                print(
                    "⚠️ [LiveKit Stream] "
                    "audio_source or room unavailable."
                )

    except Exception:

        print(
            "❌ [Pipeline Error]:"
        )

        traceback.print_exc()