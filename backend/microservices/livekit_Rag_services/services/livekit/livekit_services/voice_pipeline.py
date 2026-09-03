import asyncio
import json
import time
import traceback
from uuid import UUID

import webrtcvad
from livekit import rtc

from backend.helper_functions.database.session import SessionLocal

from backend.microservices.livekit_Rag_services.core.config import settings
from backend.microservices.livekit_Rag_services.core.rabitmq import RabbitMQ

from backend.microservices.livekit_Rag_services.models.escalation_model import (
    Escalation,
    EscalationStatus,
)
from backend.microservices.livekit_Rag_services.models.message_model import (
    SenderTypeEnum,
)

from backend.microservices.livekit_Rag_services.services.erp_services.auth_client import (
    AuthClient,
)
from backend.microservices.livekit_Rag_services.services.erp_services.erp_service import (
    ERPService,
)

from backend.microservices.livekit_Rag_services.services.groq import (
    human_text,
    intent_prompt,
)

from backend.microservices.livekit_Rag_services.services.groq.groq import (
    dataConverter,
    GROQ_FAST_MODEL,
)

from backend.microservices.livekit_Rag_services.services.rag_engine.config import (
    INDEX_NAME,
)

from backend.microservices.livekit_Rag_services.services.rag_engine.query import (
    ask_vocira,
)

from backend.microservices.livekit_Rag_services.services.rag_engine.vectorstore import (
    connect_existing_store,
)

from backend.microservices.livekit_Rag_services.services.router_services.message_service import (
    MessageService,
)

from backend.microservices.livekit_Rag_services.services.router_services.session_service import (
    SessionService,
)

from backend.microservices.livekit_Rag_services.services.text_speech.piper_servies import (
    split_sentences,
    tts_converter,
)


# =========================================================
# SERVICES
# =========================================================

message_service = MessageService()

auth_client = AuthClient(
    base_url=settings.AUTH_SERVICE_URL
)

erp_service = ERPService()

retriever = connect_existing_store(
    index_name=INDEX_NAME
)

rabbitmq = RabbitMQ()

session_service = SessionService()


# =========================================================
# AUTHORIZATION
# =========================================================

ERP_ALLOWED_ROLES = {
    "parent",
    "guardian",
    "admin",
}

ADMIN_HANDOFF_INTENT = "ADMIN_HANDOFF"


# =========================================================
# HELPER
# =========================================================

def normalize_role(role):
    """
    Normalize role returned from Auth Service.

    Supports:

        "parent"

    and:

        {"name": "parent"}
    """

    if isinstance(role, dict):
        role = role.get("name")

    if role is None:
        return None

    return str(role).strip().lower()


# =========================================================
# READ LIVEKIT USER INFORMATION
# =========================================================

def extract_participant_identity(participant):
    """
    Extract user_id and metadata from LiveKit participant.

    IMPORTANT:
    LiveKit metadata is used only to identify the VOCIRA user.

    It is NOT trusted as the final authorization source.

    Final authorization is performed through Auth Service.
    """

    try:
        metadata = json.loads(
            participant.metadata or "{}"
        )

        if not isinstance(metadata, dict):
            metadata = {}

    except (json.JSONDecodeError, TypeError):
        print(
            f"⚠️ Invalid metadata from participant "
            f"{participant.identity}: "
            f"{participant.metadata}"
        )

        metadata = {}

    raw_user_id = metadata.get("user_id")

    user_id = None

    if raw_user_id:

        raw_user_id = str(raw_user_id).strip()

        if raw_user_id.lower() not in {
            "",
            "guest",
            "none",
            "null",
            "anonymous",
        }:

            try:

                user_id = UUID(raw_user_id)

            except (ValueError, TypeError):

                print(
                    f"⚠️ Invalid VOCIRA user_id: "
                    f"{raw_user_id}"
                )

                user_id = None

    return metadata, user_id


# =========================================================
# AGENT KO BULWAYEIN
# =========================================================

async def speak_text(service_handle, audio_source, text: str) -> bool:
    """
    Agent se koi jumla bulwayein (greeting waghera).

    Wahi sentence-streaming aur locking use karta hai jo asli jawab
    ke liye hoti hai, taake do awaazein aapas mein na takrayein.
    """

    sentences = split_sentences(text)

    if not sentences:
        return False

    # Track ke tayyar hone ka intezaar
    try:
        await asyncio.wait_for(
            service_handle._track_ready.wait(),
            timeout=10,
        )
    except asyncio.TimeoutError:
        print("⚠️ [Speak] Agent track tayyar nahi hui.")
        return False

    async with service_handle._tts_lock:

        if not (
            audio_source
            and service_handle.room
            and service_handle.room.isconnected()
        ):
            print("⚠️ [Speak] Room ya audio source maujood nahi.")
            return False

        sample_rate = 22050
        num_channels = 1
        bytes_per_sample = 2
        samples_per_channel = int(sample_rate * 20 / 1000)
        chunk_size = samples_per_channel * num_channels * bytes_per_sample

        service_handle._is_agent_speaking = True

        try:
            for sentence in sentences:

                audio_bytes = await asyncio.to_thread(
                    tts_converter, sentence
                )

                if not audio_bytes:
                    continue

                for i in range(0, len(audio_bytes), chunk_size):

                    if not (
                        service_handle.room
                        and service_handle.room.isconnected()
                    ):
                        return False

                    frame_chunk = audio_bytes[i:i + chunk_size]

                    if len(frame_chunk) < chunk_size:
                        frame_chunk += b"\x00" * (
                            chunk_size - len(frame_chunk)
                        )

                    try:
                        await audio_source.capture_frame(
                            rtc.AudioFrame(
                                data=frame_chunk,
                                sample_rate=sample_rate,
                                num_channels=num_channels,
                                samples_per_channel=samples_per_channel,
                            )
                        )
                    except Exception as frame_error:
                        print(f"⚠️ [Speak] Frame fail: {frame_error}")
                        return False

        finally:
            service_handle._is_agent_speaking = False
            service_handle._agent_speech_ended_at = time.monotonic()

    print(f"✅ [Speak] bol diya: {text[:60]}")
    return True


# =========================================================
# CONSUME LIVEKIT AUDIO
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
    Consume LiveKit participant audio.

    Flow:

        LiveKit Audio
            ↓
        VAD
            ↓
        STT
            ↓
        process_voice_intent()
    """

    # =====================================================
    # 1. PARTICIPANT IDENTITY
    # =====================================================

    metadata, user_id = extract_participant_identity(
        participant
    )

    # -----------------------------------------------------
    # Metadata role is informational only.
    # -----------------------------------------------------

    metadata_role = normalize_role(
        metadata.get("role")
    )

    metadata_type = str(
        metadata.get("type", "guest")
    ).strip().lower()

    # =====================================================
    # 2. LOG IDENTITY
    # =====================================================

    print("=" * 70)

    print(
        f"👤 Participant Identity : "
        f"{participant.identity}"
    )

    print(
        f"👤 VOCIRA User ID       : "
        f"{user_id}"
    )

    print(
        f"👤 Metadata Role        : "
        f"{metadata_role}"
    )

    print(
        f"👤 Metadata Type        : "
        f"{metadata_type}"
    )

    print(
        f"📦 Metadata             : "
        f"{metadata}"
    )

    print(
        "🔐 Auth Source          : "
        "Auth Service"
    )

    print("=" * 70)

    # =====================================================
    # 3. VALIDATE AUDIO TRACK
    # =====================================================

    if not track:

        print(
            "⚠️ No audio track received."
        )

        return

    try:

        stream = rtc.AudioStream(track)

    except Exception as error:

        print(
            f"❌ Failed to create AudioStream: "
            f"{error}"
        )

        return

    # =====================================================
    # 4. VAD
    # =====================================================

    # Aggressiveness 0-3. 2 par background shor bhi "speech" gina ja
    # raha tha, jis se har waqt nayi generation banti rehti thi aur
    # tayyar jawab "stale" ho kar phenk diya jata tha. 3 sab se sakht
    # filter hai - non-speech ko zyada rad karta hai.
    vad = webrtcvad.Vad(3)

    audio_buffer = bytearray()

    voice_accumulation = bytearray()

    is_speaking = False

    silence_frames = 0

    # 17 frames x 30ms = ~510ms khamoshi ke baad jumla khatam mana
    # jata hai. Pehle 25 (750ms) tha - har sawal par chauthai second
    # khali intezaar hota tha.
    SILENCE_LIMIT = 17

    # Agent ke bolna khatam karne ke baad itni der aur na sunein -
    # speaker se nikalti awaaz ki dum warna agla "sawal" ban jati hai.
    AGENT_COOLDOWN_SECONDS = 0.6

    consecutive_speech_frames = 0

    barge_in_triggered = False

    MAX_ACCUMULATION_BYTES = (
        32000 * 2 * 15
    )

    sample_rate = None

    vad_frame_size = None

    # =====================================================
    # 5. AUDIO LOOP
    # =====================================================

    try:

        async for event in stream:

            # -------------------------------------------------
            # ADMIN HANDOFF CHECK
            # -------------------------------------------------

            if getattr(
                service_handle,
                "_admin_handoff_requested",
                False,
            ):

                print(
                    "📞 [Admin Handoff] "
                    "AI audio processing stopped."
                )

                break

            frame = event.frame

            # -------------------------------------------------
            # AGENT BOL RAHA HAI -> BILKUL NA SUNEIN
            #
            # Jab tak agent apni baat poori na kar le, user ka
            # audio process hi nahi hota. Pehle barge-in ki
            # koshish hoti thi, magar mic agent ki apni awaaz
            # (aur shor) utha kar use beech jumle mein chup kara
            # deta tha - "kuch bolti phir chup ho jati".
            #
            # Bolne ke baad thora sa cooldown bhi, taake echo ki
            # dum agla sawal na ban jaye.
            # -------------------------------------------------

            if (
                service_handle._is_agent_speaking
                or (
                    time.monotonic()
                    - getattr(
                        service_handle,
                        "_agent_speech_ended_at",
                        0.0,
                    )
                )
                < AGENT_COOLDOWN_SECONDS
            ):

                audio_buffer.clear()
                voice_accumulation.clear()

                is_speaking = False
                silence_frames = 0
                consecutive_speech_frames = 0
                barge_in_triggered = False

                continue

            # -------------------------------------------------
            # INITIALIZE AUDIO
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

            audio_buffer.extend(
                frame.data
            )

            # =================================================
            # PROCESS VAD FRAMES
            # =================================================

            while len(audio_buffer) >= vad_frame_size:

                if getattr(
                    service_handle,
                    "_admin_handoff_requested",
                    False,
                ):

                    print(
                        "📞 [Admin Handoff] "
                        "Stopping VAD processing."
                    )

                    return

                audio_chunk = bytes(
                    audio_buffer[
                        :vad_frame_size
                    ]
                )

                del audio_buffer[
                    :vad_frame_size
                ]

                speech_detected = (
                    await asyncio.to_thread(
                        vad.is_speech,
                        audio_chunk,
                        sample_rate,
                    )
                )

                # =================================================
                # SPEECH
                # =================================================

                if speech_detected:

                    silence_frames = 0

                    consecutive_speech_frames += 1

                    voice_accumulation.extend(
                        audio_chunk
                    )

                    if not is_speaking:

                        is_speaking = True

                        print(
                            f"🎤 [Speech Started] "
                            f"{participant.identity}"
                        )

                    # NOTE: Yahan pehle barge-in tha (user agent ko
                    # tok de to agent chup ho jaye). Wo hata diya
                    # gaya hai kyunke mic agent ki apni awaaz utha
                    # kar use beech jumle mein chup kara deta tha.
                    #
                    # Ab agent ke bolne ke dauran audio upar hi
                    # chhor diya jata hai, is liye yahan tak
                    # pohanchne ka matlab hai agent khamosh hai.

                # =================================================
                # SILENCE
                # =================================================

                elif is_speaking:

                    silence_frames += 1

                    # Khamoshi aate hi barge-in ka counter reset -
                    # warna alag alag waqton ke frames jama ho kar
                    # jhoota barge-in bana dete hain.
                    consecutive_speech_frames = 0

                    voice_accumulation.extend(
                        audio_chunk
                    )

                    if (
                        silence_frames >= SILENCE_LIMIT
                        or len(voice_accumulation)
                        > MAX_ACCUMULATION_BYTES
                    ):

                        captured_audio = bytes(
                            voice_accumulation
                        )

                        print(
                            f"🛑 [Speech Finished] "
                            f"Audio bytes: "
                            f"{len(captured_audio)}"
                        )

                        service_handle._speech_generation += 1

                        generation_id = (
                            service_handle._speech_generation
                        )

                        # -----------------------------------------
                        # CREATE BACKGROUND TASK
                        # -----------------------------------------

                        task = asyncio.create_task(
                            process_voice_intent(
                                chunk=captured_audio,
                                stt=stt,
                                user_id=user_id,
                                user_type=metadata_type,
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
                            service_handle._background_tasks.discard
                        )

                        voice_accumulation.clear()

                        silence_frames = 0

                        is_speaking = False

                        # Agli utterance dobara barge-in kar sakti hai
                        consecutive_speech_frames = 0

                        barge_in_triggered = False

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
# VOICE PROCESSING PIPELINE
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
    """
    Complete voice processing pipeline.

    Flow:

        Audio
          ↓
        STT
          ↓
        Session Validation
          ↓
        Save User Message
          ↓
        Intent Router
          ↓
        ┌─────────────────────────┐
        │ ADMIN_HANDOFF           │
        └─────────────────────────┘
          ↓
        ┌─────────────────────────┐
        │ ERP_QUERY               │
        │                         │
        │ Auth Service            │
        │      ↓                  │
        │ Role Validation         │
        │      ↓                  │
        │ ERP Account Mapping     │
        │      ↓                  │
        │ ERP Service             │
        └─────────────────────────┘
          ↓
        RAG
          ↓
        Save AI Message
          ↓
        TTS
          ↓
        LiveKit
    """

    try:

        ai_response_text = None

        # =====================================================
        # 1. STT
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
        # 2. HANDOFF CHECK
        # =====================================================

        if getattr(
            service_handle,
            "_admin_handoff_requested",
            False,
        ):

            print(
                "📞 [Admin Handoff] "
                "Ignoring AI processing."
            )

            return

        # =====================================================
        # 3. DATABASE
        # =====================================================

        async with SessionLocal() as db:

            # =================================================
            # SESSION VALIDATION
            # =================================================

            retries = 3

            for attempt in range(retries):

                try:

                    await session_service.get_session_by_id(
                        db=db,
                        user_id=user_id,
                        id_value=session_id,
                    )

                    if attempt > 0:

                        print(
                            f"✅ [Session Check] "
                            f"Session found after retry "
                            f"{attempt}"
                        )

                    break

                except Exception as e:

                    if attempt < retries - 1:

                        print(
                            f"⚠️ [Session Check Failed] "
                            f"{e} | Retrying..."
                        )

                        await asyncio.sleep(
                            0.2
                        )

                    else:

                        print(
                            f"❌ [Session Check Failed] "
                            f"{e} | Aborting."
                        )

                        return

            # =================================================
            # SAVE USER MESSAGE
            # =================================================

            user_message = (
                await message_service.create_message(
                    db=db,
                    content=user_query,
                    user_id=user_id,
                    usertype=SenderTypeEnum.user.value,
                    session_id=session_id,
                )
            )

            print(
                "💬 [Message Created]"
            )

            print(
                f"   Message ID: "
                f"{user_message.id}"
            )

            # =================================================
            # INTENT ROUTER
            # =================================================

            # Pehle yahan DO LLM calls hoti thin: ek intent ke liye,
            # phir ek aur ERP resource chunne ke liye (810-line prompt).
            # Ab ek hi chhota call dono kaam karta hai.
            router_result = await dataConverter(
                intent_prompt.ROUTER_PROMPT.format(
                    user_query=user_query
                ),
                model=GROQ_FAST_MODEL,
                max_tokens=80,
            )

            router_raw = (
                router_result
                .choices[0]
                .message
                .content
                or ""
            ).strip()

            # markdown fences hata dein
            if router_raw.startswith("```"):
                _lines = router_raw.splitlines()[1:]
                if _lines and _lines[-1].strip() == "```":
                    _lines = _lines[:-1]
                router_raw = "\n".join(_lines).strip()

            try:
                route = json.loads(router_raw)
                if not isinstance(route, dict):
                    raise ValueError("route must be an object")
            except Exception:
                # JSON na bane to RAG par gir jayein - us se
                # user ko kam az kam koi jawab to milta hai.
                print(
                    f"⚠️ [Router] JSON parse fail: "
                    f"{router_raw!r} — RAG par ja rahe hain"
                )
                route = {"intent": "RAG"}

            intent = str(
                route.get("intent", "RAG")
            ).strip().upper()

            erp_resource = route.get("resource")
            erp_student = (route.get("student") or "").strip() or None

            print(
                f"🧭 [Route]: intent={intent} "
                f"resource={erp_resource} student={erp_student}"
            )

            # =================================================
            # ADMIN HANDOFF
            # =================================================

            if ADMIN_HANDOFF_INTENT in intent:

                print(
                    "📞 [Route]: ADMIN HANDOFF"
                )

                # -------------------------------------------------
                # SECURITY
                # -------------------------------------------------

                if not user_id:

                    ai_response_text = (
                        "You must be logged in with "
                        "an authorized account to "
                        "contact an admin."
                    )

                    await message_service.create_message(
                        db=db,
                        content=ai_response_text,
                        user_id=user_id,
                        usertype=SenderTypeEnum.ai.value,
                        session_id=session_id,
                    )

                    return

                # -------------------------------------------------
                # CREATE ESCALATION
                # -------------------------------------------------

                escalation = Escalation(
                    user_id=user_id,
                    message_id=user_message.id,
                    status=EscalationStatus.pending,
                )

                db.add(escalation)

                await db.commit()

                await db.refresh(
                    escalation
                )

                print(
                    "🚨 [Escalation Created]"
                )

                print(
                    f"   Escalation ID : "
                    f"{escalation.id}"
                )

                # -------------------------------------------------
                # RABBITMQ
                # -------------------------------------------------

                rabbitmq_payload = {

                    "event": "admin.call.handoff",

                    "call_id": str(
                        session_id
                    ),

                    "session_id": str(
                        session_id
                    ),

                    "room_name":
                        f"room-{session_id}",

                    "caller_id": str(
                        user_id
                    ),

                    "escalation_id": str(
                        escalation.id
                    ),

                    "message_id": str(
                        user_message.id
                    ),

                    "message": user_query,
                }

                try:

                    await rabbitmq.publish_admin_handoff(
                        rabbitmq_payload
                    )

                    print(
                        "🔔 [RabbitMQ] "
                        "Admin handoff published."
                    )

                except Exception as notification_error:

                    print(
                        "⚠️ [RabbitMQ] "
                        "Failed to publish admin handoff."
                    )

                    print(
                        notification_error
                    )

                    traceback.print_exc()

                # -------------------------------------------------
                # LIVEKIT HANDOFF
                # -------------------------------------------------

                await service_handle.request_admin_handoff(
                    user_id=user_id,
                    user_type=user_type,
                    session_id=session_id,
                    user_query=user_query,
                    escalation_id=escalation.id,
                    message_id=user_message.id,
                )

                return

            # =================================================
            # ERP QUERY
            # =================================================

                        # =================================================
            # ERP QUERY
            # =================================================

            # Router ab "ERP" deta hai (pehle "ERP_QUERY" tha).
            # Resource na mile to ERP ka koi matlab nahi - us soorat
            # mein RAG par chala jata hai, taake user khali haath na rahe.
            elif intent == "ERP" and erp_resource:

                print(
                    "🏫 [Route]: ERP Pipeline"
                )

                # =================================================
                # SECURITY MODEL
                # =================================================
                #
                # LiveKit metadata is NOT trusted for authorization.
                #
                # LiveKit gives us:
                #
                #     VOCIRA user_id
                #
                # Then:
                #
                #     VOCIRA user_id
                #            ↓
                #       Auth Service
                #            ↓
                #       role + parent_id
                #            ↓
                #       authorization
                #            ↓
                #       ERP Service
                #
                # =================================================

                try:

                    # -------------------------------------------------
                    # 1. USER ID REQUIRED
                    # -------------------------------------------------

                    if not user_id:

                        print(
                            "🚫 [ERP Auth] "
                            "No VOCIRA user_id."
                        )

                        ai_response_text = (
                            "You are not authorized to access "
                            "ERP information. Please log in "
                            "with an authorized account."
                        )

                    else:

                        print("=" * 70)

                        print(
                            "🔎 [ERP AUTHENTICATION]"
                        )

                        print(
                            f"VOCIRA User ID : "
                            f"{user_id}"
                        )

                        print(
                            f"LiveKit Type   : "
                            f"{user_type}"
                        )

                        print(
                            "Auth Source    : "
                            "Auth Service"
                        )

                        print("=" * 70)

                        # =================================================
                        # 2. GET COMPLETE USER FROM AUTH SERVICE
                        # =================================================

                        auth_user = (
                            await auth_client.get_internal_user(
                                vocira_user_id=user_id
                            )
                        )

                        print("=" * 70)

                        print(
                            "🔎 [AUTH SERVICE RESPONSE]"
                        )

                        print(
                            f"Requested User ID : "
                            f"{user_id}"
                        )

                        print(
                            f"Auth User         : "
                            f"{auth_user}"
                        )

                        print(
                            f"Response Type     : "
                            f"{type(auth_user)}"
                        )

                        print("=" * 70)

                        # =================================================
                        # 3. VALIDATE AUTH RESPONSE
                        # =================================================

                        if not auth_user:

                            print(
                                "🚫 [ERP Auth] "
                                "Auth Service returned no user."
                            )

                            ai_response_text = (
                                "I could not verify your account. "
                                "Please log in again."
                            )

                        elif not isinstance(
                            auth_user,
                            dict,
                        ):

                            print(
                                "🚫 [ERP Auth] "
                                "Unexpected Auth Service response."
                            )

                            ai_response_text = (
                                "I could not verify your account. "
                                "Please log in again."
                            )

                        else:

                            # =================================================
                            # 4. VERIFY RETURNED USER ID
                            # =================================================

                            auth_user_id = (
                                auth_user.get("user_id")
                            )

                            if str(auth_user_id) != str(user_id):

                                print(
                                    "🚫 [ERP Auth] "
                                    "Auth Service returned a "
                                    "different user_id."
                                )

                                print(
                                    f"Requested : {user_id}"
                                )

                                print(
                                    f"Returned  : {auth_user_id}"
                                )

                                ai_response_text = (
                                    "I could not verify your account. "
                                    "Please log in again."
                                )

                            else:

                                # =================================================
                                # 5. GET AUTH ROLE
                                # =================================================

                                auth_role = normalize_role(
                                    auth_user.get("role")
                                )

                                print("=" * 70)

                                print(
                                    "🔐 [AUTHORIZATION CHECK]"
                                )

                                print(
                                    f"VOCIRA User ID : "
                                    f"{user_id}"
                                )

                                print(
                                    f"LiveKit Type   : "
                                    f"{user_type}"
                                )

                                print(
                                    f"Auth Role      : "
                                    f"{auth_role}"
                                )

                                print(
                                    f"Allowed Roles  : "
                                    f"{ERP_ALLOWED_ROLES}"
                                )

                                print(
                                    f"Role Allowed   : "
                                    f"{auth_role in ERP_ALLOWED_ROLES}"
                                )

                                print("=" * 70)

                                # =================================================
                                # 6. ROLE AUTHORIZATION
                                # =================================================

                                if (
                                    auth_role
                                    not in ERP_ALLOWED_ROLES
                                ):

                                    print(
                                        "🚫 [ERP Auth] "
                                        "User role is not authorized."
                                    )

                                    ai_response_text = (
                                        "You are not authorized "
                                        "to access ERP information."
                                    )

                                else:

                                    print(
                                        "✅ [ERP Auth] "
                                        "User role authorized."
                                    )

                                    # =================================================
                                    # 7. GET ERP PARENT / GUARDIAN ID
                                    # =================================================

                                    erp_parent_id = (
                                        auth_user.get(
                                            "parent_id"
                                        )
                                    )

                                    if not erp_parent_id:

                                        print(
                                            "🚫 [ERP Mapping] "
                                            "No parent_id found."
                                        )

                                        print(
                                            f"Auth User Keys: "
                                            f"{list(auth_user.keys())}"
                                        )

                                        ai_response_text = (
                                            "Your VOCIRA account is not "
                                            "linked to an ERP account."
                                        )

                                    else:

                                        print("=" * 70)

                                        print(
                                            "🔗 [ERP ACCOUNT MAPPING]"
                                        )

                                        print(
                                            f"VOCIRA User ID : "
                                            f"{user_id}"
                                        )

                                        print(
                                            f"Auth Role      : "
                                            f"{auth_role}"
                                        )

                                        print(
                                            f"ERP Parent ID  : "
                                            f"{erp_parent_id}"
                                        )

                                        print("=" * 70)

                                        # =================================================
                                        # 8. SEND QUERY TO ERP SERVICE
                                        # =================================================

                                        print(
                                            "🏫 [ERP QUERY]"
                                        )

                                        print(
                                            f"User Query     : "
                                            f"{user_query}"
                                        )

                                        print(
                                            f"ERP Parent ID  : "
                                            f"{erp_parent_id}"
                                        )

                                        # Resource router ke usi call se
                                        # mil chuka hai - yahan doosri
                                        # LLM call ki zaroorat nahi.
                                        erp_data = (
                                            await erp_service.fetch(
                                                resource=erp_resource,
                                                erp_parent_id=erp_parent_id,
                                                student_name=erp_student,
                                            )
                                        )

                                        print(
                                            "🏫 [ERP DATA]"
                                        )

                                        print(
                                            erp_data
                                        )

                                        # =================================================
                                        # 9. CONVERT ERP DATA TO HUMAN RESPONSE
                                        # =================================================

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

                                        print(
                                            "🤖 [ERP AI RESPONSE]"
                                        )

                                        print(
                                            ai_response_text
                                        )

                except Exception as erp_error:

                    print(
                        "❌ [ERP Pipeline Error]"
                    )

                    print(
                        f"Error: {erp_error}"
                    )

                    traceback.print_exc()

                    ai_response_text = (
                        "Sorry, I was unable to retrieve "
                        "your ERP information right now."
                    )

            # =================================================
            # RAG QUERY
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
                        ai_response_text.strip()
                    )

            # =================================================
            # HANDOFF CHECK
            # =================================================

            if getattr(
                service_handle,
                "_admin_handoff_requested",
                False,
            ):

                print(
                    "📞 [Admin Handoff] "
                    "Stopping AI response."
                )

                return

            # =================================================
            # EMPTY RESPONSE
            # =================================================

            if not ai_response_text:

                print(
                    "⚠️ [AI] Empty response."
                )

                return

            print(
                f"🤖 [AI]: "
                f"{ai_response_text}"
            )

            # =================================================
            # SAVE AI MESSAGE
            # =================================================

            await message_service.create_message(
                db=db,
                content=ai_response_text,
                user_id=user_id,
                usertype=SenderTypeEnum.ai.value,
                session_id=session_id,
            )

        # =====================================================
        # 12. FINAL HANDOFF CHECK
        # =====================================================

        if getattr(
            service_handle,
            "_admin_handoff_requested",
            False,
        ):

            print(
                "📞 [TTS] "
                "Admin handoff active."
            )

            return

        # =====================================================
        # 13. TTS
        # =====================================================

        # Pehle yahan POORE jawab ka audio banaya jata tha aur tab
        # aage barha jata tha - CPU par 1.5-2 second ki khamoshi.
        # Ab sirf jumlon mein toRte hain (ye sasta hai); audio har
        # jumle ka alag alag, bajne se theek pehle banta hai.
        sentences = split_sentences(ai_response_text)

        if not sentences:

            print(
                "⚠️ [TTS] "
                "Bolne ke liye kuch nahi mila."
            )

            return

        # =====================================================
        # 14. WAIT FOR LIVEKIT TRACK
        # =====================================================

        try:

            await asyncio.wait_for(
                service_handle._track_ready.wait(),
                timeout=5,
            )

        except asyncio.TimeoutError:

            print(
                "⚠️ [LiveKit Stream] "
                "Agent track not ready."
            )

            return

        # =====================================================
        # 15. SERIALIZED TTS
        # =====================================================

        async with service_handle._tts_lock:

            if getattr(
                service_handle,
                "_admin_handoff_requested",
                False,
            ):

                print(
                    "📞 [TTS] "
                    "Admin handoff active."
                )

                return

            # -------------------------------------------------
            # PURANA JAWAB CHHORNA
            #
            # Pehle yahan `generation != _speech_generation` tha.
            # Masla: _speech_generation HAR utterance par barhta hai,
            # chahe agent bol hi na raha ho. Agar user ne doosra
            # jumla bola (ya mic ne shor uthaya) jab tak pehla jawab
            # ban raha tha, to tayyar jawab phenk diya jata tha aur
            # user ko KUCH BHI sunayi nahi deta tha.
            #
            # Ab sirf wo jawab chhorte hain jo waqai purana ho -
            # yaani us se naya jawab pehle hi bola ja chuka ho.
            # Asli barge-in (agent bol raha ho aur user tok de)
            # neeche playback loop mein sambhala jata hai.
            # -------------------------------------------------

            if (
                generation
                <= service_handle._last_played_generation
            ):

                print(
                    "⏭️ [TTS] "
                    "Is se naya jawab pehle hi bola ja chuka hai."
                )

                return

            if not (
                audio_source
                and service_handle.room
                and service_handle.room.isconnected()
            ):

                print(
                    "⚠️ [TTS] "
                    "Audio source or room unavailable."
                )

                return

            # =================================================
            # AUDIO CONFIGURATION
            # =================================================

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

            # Ye jawab bola ja raha hai - is se purane jawab ab
            # khud-ba-khud rad ho jayenge.
            service_handle._last_played_generation = generation

            # =================================================
            # PLAY TTS
            # =================================================

            try:

                # Agla jumla pichhle ke BAJTE WAQT tayyar hota hai,
                # is liye jumlon ke darmiyan khamoshi nahi aati.
                next_audio = asyncio.create_task(
                    asyncio.to_thread(
                        tts_converter,
                        sentences[0],
                    )
                )

                for index, sentence in enumerate(sentences):

                    audio_bytes = await next_audio

                    if index + 1 < len(sentences):
                        next_audio = asyncio.create_task(
                            asyncio.to_thread(
                                tts_converter,
                                sentences[index + 1],
                            )
                        )

                    if not audio_bytes:
                        continue

                    print(
                        f"🔊 [TTS] jumla {index + 1}/{len(sentences)}"
                    )

                    stop_playback = False

                    for i in range(
                        0,
                        len(audio_bytes),
                        chunk_size,
                    ):

                        # -----------------------------------------
                        # HANDOFF
                        # -----------------------------------------

                        if getattr(
                            service_handle,
                            "_admin_handoff_requested",
                            False,
                        ):

                            print(
                                "📞 [TTS] "
                                "Admin handoff requested."
                            )

                            stop_playback = True
                            stop_playback = True
                        break

                        # -----------------------------------------
                        # GENERATION
                        # -----------------------------------------

                        # NOTE: Yahan pehle generation check tha jo
                        # playback ko beech mein kaat deta tha. Ab agent
                        # ke bolne ke dauran audio sunna hi band hai,
                        # is liye generation barh hi nahi sakti - aur
                        # jumla poora bola jata hai.

                        # -----------------------------------------
                        # ROOM
                        # -----------------------------------------

                        if not (
                            service_handle.room
                            and service_handle.room.isconnected()
                        ):

                            print(
                                "🛑 [TTS] "
                                "Room disconnected."
                            )

                            stop_playback = True
                            stop_playback = True
                        break

                        # -----------------------------------------
                        # AUDIO CHUNK
                        # -----------------------------------------

                        frame_chunk = audio_bytes[
                            i:i + chunk_size
                        ]

                        # -----------------------------------------
                        # PAD LAST FRAME
                        # -----------------------------------------

                        if len(frame_chunk) < chunk_size:

                            frame_chunk += (
                                b"\x00"
                                * (
                                    chunk_size
                                    - len(frame_chunk)
                                )
                            )

                        # -----------------------------------------
                        # LIVEKIT FRAME
                        # -----------------------------------------

                        audio_frame = rtc.AudioFrame(
                            data=frame_chunk,
                            sample_rate=sample_rate,
                            num_channels=num_channels,
                            samples_per_channel=(
                                samples_per_channel
                            ),
                        )

                        # -----------------------------------------
                        # SEND FRAME
                        # -----------------------------------------

                        try:

                            await audio_source.capture_frame(
                                audio_frame
                            )

                        except Exception as frame_error:

                            print(
                                f"⚠️ [TTS] "
                                f"Frame submission failed: "
                                f"{frame_error}"
                            )

                            stop_playback = True
                            stop_playback = True
                        break

                    if stop_playback:
                        break

            finally:

                service_handle._is_agent_speaking = False

                # Cooldown yahin se shuru hota hai - echo ki dum
                # ko agla sawal banne se rokta hai.
                service_handle._agent_speech_ended_at = (
                    time.monotonic()
                )

            print(
                "✅ [TTS] "
                "Audio generation completed."
            )

    except Exception:

        print(
            "❌ [Pipeline Error]:"
        )

        traceback.print_exc()