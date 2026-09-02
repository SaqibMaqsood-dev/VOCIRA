import asyncio
import json
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

from backend.microservices.livekit_Rag_services.models.session_model import (
    Session,
    SessionHandler,
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

GUEST_TYPES = {
    "",
    "guest",
    "anonymous",
    "unauthenticated",
    "none",
    "null",
}


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def normalize_role(role):
    """
    Normalize a role returned from Auth Service.

    Supported examples:

        "parent"

        {
            "name": "parent"
        }

        {
            "role": "parent"
        }
    """

    if isinstance(role, dict):

        role = (
            role.get("name")
            or role.get("role")
            or role.get("value")
        )

    if role is None:
        return None

    return str(role).strip().lower()


def extract_roles_from_auth_response(
    auth_response,
):
    """
    Extract normalized roles from an Auth Service response.

    Supported response shapes:

        {
            "role": "parent"
        }

        {
            "role": {
                "name": "parent"
            }
        }

        {
            "roles": ["parent", "guardian"]
        }

        {
            "roles": [
                {"name": "parent"}
            ]
        }
    """

    roles = set()

    if not isinstance(
        auth_response,
        dict,
    ):
        return roles

    # -----------------------------------------------------
    # SINGLE ROLE
    # -----------------------------------------------------

    single_role = auth_response.get(
        "role"
    )

    if single_role:

        normalized = normalize_role(
            single_role
        )

        if normalized:
            roles.add(normalized)

    # -----------------------------------------------------
    # MULTIPLE ROLES
    # -----------------------------------------------------

    response_roles = auth_response.get(
        "roles"
    )

    if response_roles:

        if isinstance(
            response_roles,
            (list, tuple, set),
        ):

            for role in response_roles:

                normalized = normalize_role(
                    role
                )

                if normalized:
                    roles.add(normalized)

        else:

            normalized = normalize_role(
                response_roles
            )

            if normalized:
                roles.add(normalized)

    return roles


def extract_erp_guardian_id(
    auth_response,
):
    """
    Extract ERP Guardian ID from Auth Service response.

    Supported fields:

        erp_guardian_id
        guardian_id
        erp_parent_id
    """

    erp_guardian_id = None

    if isinstance(
        auth_response,
        dict,
    ):

        erp_guardian_id = (
            auth_response.get(
                "erp_guardian_id"
            )
            or auth_response.get(
                "guardian_id"
            )
            or auth_response.get(
                "erp_parent_id"
            )
        )

    elif isinstance(
        auth_response,
        str,
    ):

        erp_guardian_id = (
            auth_response.strip()
        )

    if erp_guardian_id:

        erp_guardian_id = str(
            erp_guardian_id
        ).strip()

    return erp_guardian_id


def is_guest_type(
    user_type,
):
    """
    Determine whether LiveKit user_type represents
    a guest.

    LiveKit metadata is informational only and must
    never override Auth Service authorization.
    """

    if user_type is None:
        return True

    normalized = (
        str(user_type)
        .strip()
        .lower()
    )

    return normalized in GUEST_TYPES


# =========================================================
# ERP AUTHORIZATION
# =========================================================

async def verify_erp_authorization(
    user_id,
):
    """
    Verify that a VOCIRA user is authorized for ERP.

    Security model:

        VOCIRA user UUID
                ↓
        Auth Service
                ↓
        User authorization
                ↓
        ERP Guardian mapping
                ↓
        ERPService
                ↓
        ERPNext

    LiveKit metadata is NOT used as an authorization
    source.

    Returns:

        {
            "authorized": bool,
            "erp_guardian_id": str | None,
            "roles": set,
            "response": dict | str | None,
            "reason": str
        }
    """

    result = {
        "authorized": False,
        "erp_guardian_id": None,
        "roles": set(),
        "response": None,
        "reason": None,
    }

    # =====================================================
    # USER ID REQUIRED
    # =====================================================

    if not user_id:

        result["reason"] = (
            "Missing VOCIRA user_id."
        )

        return result

    print("=" * 70)

    print(
        "🔐 [ERP AUTHORIZATION]"
    )

    print(
        f"VOCIRA User ID : {user_id}"
    )

    print(
        "Auth Source    : Auth Service"
    )

    print("=" * 70)

    # =====================================================
    # AUTH SERVICE
    # =====================================================

    try:

        auth_response = (
            await auth_client.get_erp_guardian_id(
                vocira_user_id=user_id
            )
        )

    except Exception as error:

        print("=" * 70)

        print(
            "❌ [ERP AUTH] "
            "Auth Service request failed."
        )

        print(
            f"VOCIRA User ID : {user_id}"
        )

        print(
            f"Error          : {error}"
        )

        print("=" * 70)

        traceback.print_exc()

        result["reason"] = (
            "Auth Service unavailable."
        )

        return result

    result["response"] = auth_response

    print("=" * 70)

    print(
        f"VOCIRA User ID : {user_id}"
    )

    print(
        f"Auth Response  : {auth_response}"
    )

    print(
        f"Response Type  : {type(auth_response)}"
    )

    print("=" * 70)

    # =====================================================
    # EXTRACT ROLES
    # =====================================================

    roles = extract_roles_from_auth_response(
        auth_response
    )

    result["roles"] = roles

    print(
        f"🔐 [ERP AUTH] Auth roles: {roles}"
    )

    # =====================================================
    # ROLE AUTHORIZATION
    # =====================================================

    if roles:

        authorized_roles = (
            roles.intersection(
                ERP_ALLOWED_ROLES
            )
        )

        if not authorized_roles:

            print(
                "🚫 [ERP AUTH] "
                "User does not have an allowed ERP role."
            )

            print(
                f"User roles    : {roles}"
            )

            print(
                f"Allowed roles : {ERP_ALLOWED_ROLES}"
            )

            result["reason"] = (
                "User role is not authorized for ERP."
            )

            return result

        print(
            "✅ [ERP AUTH] "
            f"Authorized role(s): {authorized_roles}"
        )

    else:

        # -------------------------------------------------
        # Backward compatibility:
        #
        # If Auth Service returns only the ERP Guardian
        # mapping and no role, the authoritative mapping
        # from Auth Service is treated as authorization.
        #
        # LiveKit metadata is never used for this decision.
        # -------------------------------------------------

        print(
            "ℹ️ [ERP AUTH] "
            "Auth Service response did not include role."
        )

    # =====================================================
    # ERP GUARDIAN ID
    # =====================================================

    erp_guardian_id = extract_erp_guardian_id(
        auth_response
    )

    result["erp_guardian_id"] = (
        erp_guardian_id
    )

    if not erp_guardian_id:

        print("=" * 70)

        print(
            "🚫 [ERP MAPPING]"
        )

        print(
            "No ERP Guardian ID returned."
        )

        print(
            f"VOCIRA User ID : {user_id}"
        )

        print("=" * 70)

        result["reason"] = (
            "VOCIRA account is not linked to an ERP account."
        )

        return result

    # =====================================================
    # SUCCESS
    # =====================================================

    print("=" * 70)

    print(
        "✅ [ERP AUTHORIZATION SUCCESS]"
    )

    print(
        f"VOCIRA User ID  : {user_id}"
    )

    print(
        f"ERP Guardian ID : {erp_guardian_id}"
    )

    print(
        f"Roles           : {roles}"
    )

    print("=" * 70)

    result["authorized"] = True

    result["reason"] = (
        "ERP authorization successful."
    )

    return result


# =========================================================
# SESSION HANDLER
# =========================================================

async def get_session_handler(
    db,
    session_id,
):
    """
    Get the current handler of a session.

    Database is the source of truth.

    Returns:

        SessionHandler.ai
        SessionHandler.admin
        None
    """

    try:

        session = await db.get(
            Session,
            session_id,
        )

        if not session:

            print("=" * 70)

            print(
                "⚠️ [SESSION HANDLER]"
            )

            print(
                f"Session not found: {session_id}"
            )

            print("=" * 70)

            return None

        return session.handler

    except Exception as error:

        print("=" * 70)

        print(
            "❌ [SESSION HANDLER CHECK ERROR]"
        )

        print(
            f"Session ID : {session_id}"
        )

        print(
            f"Error      : {error}"
        )

        print("=" * 70)

        traceback.print_exc()

        return None


async def is_ai_handler(
    db,
    session_id,
):
    """
    Return True only when the database says
    the session is currently handled by AI.
    """

    handler = await get_session_handler(
        db=db,
        session_id=session_id,
    )

    return handler == SessionHandler.ai


async def is_admin_handler(
    db,
    session_id,
):
    """
    Return True when the database says
    the session is currently handled by Admin.
    """

    handler = await get_session_handler(
        db=db,
        session_id=session_id,
    )

    return handler == SessionHandler.admin


async def update_session_handler(
    db,
    session_id,
    handler: SessionHandler,
):
    """
    Change the handler of an existing session.

    Normal:

        AI

    Escalated:

        ADMIN

    The caller is responsible for committing the
    transaction.
    """

    try:

        session = await db.get(
            Session,
            session_id,
        )

        if not session:

            print("=" * 70)

            print(
                "⚠️ [SESSION HANDLER UPDATE]"
            )

            print(
                f"Session not found: {session_id}"
            )

            print("=" * 70)

            return False

        old_handler = session.handler

        # -------------------------------------------------
        # NOTHING TO CHANGE
        # -------------------------------------------------

        if old_handler == handler:

            print("=" * 70)

            print(
                "ℹ️ [SESSION HANDLER]"
            )

            print(
                f"Session ID : {session_id}"
            )

            print(
                f"Handler already set to: {handler}"
            )

            print("=" * 70)

            return True

        # -------------------------------------------------
        # UPDATE
        # -------------------------------------------------

        session.handler = handler

        await db.flush()

        print("=" * 70)

        print(
            "🔄 [SESSION HANDLER UPDATED]"
        )

        print(
            f"Session ID  : {session_id}"
        )

        print(
            f"Old Handler : {old_handler}"
        )

        print(
            f"New Handler : {handler}"
        )

        print("=" * 70)

        return True

    except Exception as error:

        print("=" * 70)

        print(
            "❌ [SESSION HANDLER UPDATE ERROR]"
        )

        print(
            f"Session ID : {session_id}"
        )

        print(
            f"Error      : {error}"
        )

        print("=" * 70)

        traceback.print_exc()

        return False


# =========================================================
# LIVEKIT USER INFORMATION
# =========================================================

def extract_participant_identity(
    participant,
):
    """
    Extract VOCIRA user_id and metadata from LiveKit.

    IMPORTANT:

    LiveKit metadata is used only to identify the
    VOCIRA user.

    It is NOT trusted as the final authorization source.
    """

    try:

        metadata = json.loads(
            participant.metadata or "{}"
        )

        if not isinstance(
            metadata,
            dict,
        ):

            metadata = {}

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

    raw_user_id = metadata.get(
        "user_id"
    )

    user_id = None

    if raw_user_id:

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
            ):

                print(
                    f"⚠️ Invalid VOCIRA user_id: "
                    f"{raw_user_id}"
                )

                user_id = None

    return metadata, user_id


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
    # PARTICIPANT IDENTITY
    # =====================================================

    metadata, user_id = (
        extract_participant_identity(
            participant
        )
    )

    metadata_role = normalize_role(
        metadata.get("role")
    )

    metadata_type = str(
        metadata.get(
            "type",
            "guest",
        )
    ).strip().lower()

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
    # VALIDATE TRACK
    # =====================================================

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

    # =====================================================
    # VAD
    # =====================================================

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

    # =====================================================
    # AUDIO LOOP
    # =====================================================

    try:

        async for event in stream:

            # -------------------------------------------------
            # SERVICE HANDOFF CHECK
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

            # -------------------------------------------------
            # DATABASE HANDLER CHECK
            # -------------------------------------------------

            try:

                async with SessionLocal() as handler_db:

                    current_handler = (
                        await get_session_handler(
                            db=handler_db,
                            session_id=session_id,
                        )
                    )

                if (
                    current_handler
                    == SessionHandler.admin
                ):

                    print(
                        "📞 [Session Handler] "
                        "Database handler is ADMIN. "
                        "Stopping AI audio processing."
                    )

                    break

                if (
                    current_handler
                    != SessionHandler.ai
                ):

                    print(
                        "📞 [Session Handler] "
                        "Session is not owned by AI. "
                        "Stopping audio processing."
                    )

                    break

            except Exception as handler_error:

                print(
                    "⚠️ [Session Handler] "
                    f"Unable to verify handler: "
                    f"{handler_error}"
                )

                traceback.print_exc()

                # Fail closed.
                break

            frame = event.frame

            # =================================================
            # INITIALIZE AUDIO
            # =================================================

            if sample_rate is None:

                sample_rate = frame.sample_rate

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

            # =================================================
            # PROCESS VAD FRAMES
            # =================================================

            while (
                len(audio_buffer)
                >= vad_frame_size
            ):

                # -------------------------------------------------
                # SERVICE HANDOFF CHECK
                # -------------------------------------------------

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

                # -------------------------------------------------
                # DATABASE HANDLER CHECK
                # -------------------------------------------------

                try:

                    async with SessionLocal() as handler_db:

                        current_handler = (
                            await get_session_handler(
                                db=handler_db,
                                session_id=session_id,
                            )
                        )

                    if (
                        current_handler
                        != SessionHandler.ai
                    ):

                        print(
                            "📞 [Session Handler] "
                            "AI no longer owns session. "
                            "Stopping VAD processing."
                        )

                        return

                except Exception as handler_error:

                    print(
                        "⚠️ [Session Handler] "
                        f"Handler verification failed: "
                        f"{handler_error}"
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

                # -------------------------------------------------
                # WebRTC VAD expects mono 16-bit PCM.
                #
                # Existing pipeline assumes incoming LiveKit
                # stream is already suitable for VAD.
                # -------------------------------------------------

                try:

                    speech_detected = (
                        await asyncio.to_thread(
                            vad.is_speech,
                            audio_chunk,
                            sample_rate,
                        )
                    )

                except Exception as vad_error:

                    print(
                        "⚠️ [VAD] "
                        f"VAD processing failed: "
                        f"{vad_error}"
                    )

                    continue

                # =================================================
                # SPEECH
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

                        if (
                            service_handle._is_agent_speaking
                        ):

                            service_handle._speech_generation += 1

                            print(
                                "✋ [Barge-In] "
                                "User interrupted agent. "
                                f"Generation="
                                f"{service_handle._speech_generation}"
                            )

                # =================================================
                # SILENCE
                # =================================================

                elif is_speaking:

                    silence_frames += 1

                    voice_accumulation.extend(
                        audio_chunk
                    )

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
                            f"🛑 [Speech Finished] "
                            f"Audio bytes: "
                            f"{len(captured_audio)}"
                        )

                        service_handle._speech_generation += 1

                        generation_id = (
                            service_handle._speech_generation
                        )

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

    Handler model:

        Session.handler = AI
            ↓
        AI processes voice

        Session.handler = ADMIN
            ↓
        AI processing stops

    Flow:

        Audio
          ↓
        Session Handler Check
          ↓
        STT
          ↓
        Session Handler Check
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
        Create Escalation
          ↓
        Session Handler = Admin
          ↓
        Commit
          ↓
        RabbitMQ
          ↓
        LiveKit Handoff

        OR

        ┌─────────────────────────┐
        │ ERP_QUERY               │
        └─────────────────────────┘
          ↓
        Auth Service
          ↓
        ERP Authorization
          ↓
        ERP Guardian Mapping
          ↓
        ERP Service
          ↓
        ERPNext

        OR

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
        # 1. INITIAL SESSION HANDLER CHECK
        # =====================================================

        async with SessionLocal() as handler_db:

            current_handler = (
                await get_session_handler(
                    db=handler_db,
                    session_id=session_id,
                )
            )

        if current_handler is None:

            print(
                "❌ [Handler] "
                "Unable to determine session handler."
            )

            return

        if (
            current_handler
            == SessionHandler.admin
        ):

            print(
                "📞 [Handler] "
                "Session is already handled by ADMIN. "
                "Ignoring AI request."
            )

            return

        if (
            current_handler
            != SessionHandler.ai
        ):

            print(
                "📞 [Handler] "
                "Session is not currently handled by AI. "
                "Ignoring request."
            )

            return

        # =====================================================
        # 2. STT
        # =====================================================

        try:

            user_query = await asyncio.to_thread(
                stt.transcribe_bytes,
                chunk,
            )

        except Exception as stt_error:

            print(
                "❌ [STT] "
                f"Transcription failed: "
                f"{stt_error}"
            )

            traceback.print_exc()

            return

        if (
            not user_query
            or not user_query.strip()
        ):

            return

        user_query = user_query.strip()

        print(
            f"🗣️ [User]: {user_query}"
        )

        # =====================================================
        # 3. HANDOFF CHECK AFTER STT
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
        # 4. DATABASE HANDLER CHECK
        # =====================================================

        async with SessionLocal() as handler_db:

            current_handler = (
                await get_session_handler(
                    db=handler_db,
                    session_id=session_id,
                )
            )

        if (
            current_handler
            != SessionHandler.ai
        ):

            print(
                "📞 [Handler] "
                "Session is no longer owned by AI. "
                "Stopping pipeline."
            )

            return

        # =====================================================
        # 5. DATABASE TRANSACTION
        # =====================================================

        async with SessionLocal() as db:

            # =================================================
            # SESSION VALIDATION
            # =================================================

            retries = 3

            session_valid = False

            for attempt in range(
                retries
            ):

                try:

                    await session_service.get_session_by_id(
                        db=db,
                        user_id=user_id,
                        id_value=session_id,
                    )

                    session_valid = True

                    if attempt > 0:

                        print(
                            f"✅ [Session Check] "
                            f"Session found after retry "
                            f"{attempt}"
                        )

                    break

                except Exception as error:

                    if (
                        attempt
                        < retries - 1
                    ):

                        print(
                            f"⚠️ [Session Check Failed] "
                            f"{error} | Retrying..."
                        )

                        await asyncio.sleep(
                            0.2
                        )

                    else:

                        print(
                            f"❌ [Session Check Failed] "
                            f"{error} | Aborting."
                        )

            if not session_valid:

                await db.rollback()

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

                    await db.commit()

                    return

                # -------------------------------------------------
                # RECHECK HANDLER
                # -------------------------------------------------

                current_handler = (
                    await get_session_handler(
                        db=db,
                        session_id=session_id,
                    )
                )

                if (
                    current_handler
                    != SessionHandler.ai
                ):

                    print(
                        "📞 [Admin Handoff] "
                        "Session is no longer owned by AI."
                    )

                    await db.rollback()

                    return

                # -------------------------------------------------
                # CREATE ESCALATION
                #
                # message_id points to the exact user message
                # that triggered the escalation.
                # -------------------------------------------------

                escalation = Escalation(
                    user_id=user_id,
                    message_id=user_message.id,
                    status=EscalationStatus.pending,
                )

                db.add(
                    escalation
                )

                await db.flush()

                await db.refresh(
                    escalation
                )

                print("=" * 70)

                print(
                    "🚨 [ESCALATION CREATED]"
                )

                print(
                    f"Escalation ID : "
                    f"{escalation.id}"
                )

                print(
                    f"User ID       : "
                    f"{user_id}"
                )

                print(
                    f"Session ID    : "
                    f"{session_id}"
                )

                print(
                    f"Message ID    : "
                    f"{user_message.id}"
                )

                print(
                    "Status        : pending"
                )

                print("=" * 70)

                # -------------------------------------------------
                # CHANGE SESSION HANDLER
                #
                # IMPORTANT:
                #
                # Escalation remains pending.
                #
                # Only the session handler changes:
                #
                # AI → ADMIN
                #
                # Escalation becomes resolved later when
                # admin_end_call() successfully ends the call.
                # -------------------------------------------------

                handler_updated = (
                    await update_session_handler(
                        db=db,
                        session_id=session_id,
                        handler=SessionHandler.admin,
                    )
                )

                if not handler_updated:

                    print(
                        "❌ [SESSION HANDLER] "
                        "Failed to change handler."
                    )

                    await db.rollback()

                    return

                print("=" * 70)

                print(
                    "👨‍💼 [SESSION HANDLER]"
                )

                print(
                    "Handler changed:"
                )

                print(
                    "AI → Admin"
                )

                print("=" * 70)

                # -------------------------------------------------
                # COMMIT BOTH CHANGES TOGETHER
                #
                # This guarantees that the escalation and
                # session handler change are persisted as one
                # transaction.
                # -------------------------------------------------

                try:

                    await db.commit()

                except Exception as commit_error:

                    print(
                        "❌ [DATABASE] "
                        "Failed to commit escalation "
                        "and session handler."
                    )

                    print(
                        commit_error
                    )

                    traceback.print_exc()

                    await db.rollback()

                    return

                await db.refresh(
                    escalation
                )

                print(
                    "💾 [DATABASE] "
                    "Escalation and session handler committed."
                )

                # -------------------------------------------------
                # INVALIDATE ALL PREVIOUS AI GENERATIONS
                #
                # Any already-running TTS generation becomes stale.
                # -------------------------------------------------

                service_handle._speech_generation += 1

                print(
                    "✋ [AI] "
                    "Previous AI generations invalidated."
                )

                # =================================================
                # RABBITMQ ADMIN NOTIFICATION
                # =================================================

                rabbitmq_payload = {
                    "event": "admin.call.handoff",
                    "call_id": str(session_id),
                    "session_id": str(session_id),
                    "room_name": f"room-{session_id}",
                    "caller_id": str(user_id),
                    "escalation_id": str(escalation.id),
                    "message_id": str(user_message.id),
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
                    # IMPORTANT:
                    #
                    # RabbitMQ failure does NOT roll back the database
                    # transaction because the escalation already exists.
                    #
                    # The LiveKit handoff can still continue.
                    # -------------------------------------------------

                # =================================================
                # LIVEKIT HANDOFF
                # =================================================

                try:

                    await service_handle.request_admin_handoff(
                        user_id=user_id,
                        user_type=user_type,
                        session_id=session_id,
                        user_query=user_query,
                        escalation_id=escalation.id,
                        message_id=user_message.id,
                    )

                    print(
                        "📞 [Admin Handoff] "
                        "LiveKit handoff requested."
                    )

                except Exception as handoff_error:

                    print(
                        "❌ [Admin Handoff] "
                        "LiveKit handoff failed."
                    )

                    print(
                        handoff_error
                    )

                    traceback.print_exc()

                    # -------------------------------------------------
                    # IMPORTANT:
                    #
                    # Do not mark escalation resolved here.
                    #
                    # The escalation remains pending and can still
                    # be handled by the admin flow.
                    # -------------------------------------------------

                return

            # =================================================
            # ERP QUERY
            # =================================================

            elif "ERP_QUERY" in intent:

                print(
                    "🏫 [Route]: ERP Pipeline"
                )

                # =================================================
                # SECURITY MODEL
                # =================================================
                #
                # LiveKit metadata
                #       ↓
                # only identify VOCIRA user
                #
                # VOCIRA user UUID
                #       ↓
                # Auth Service
                #       ↓
                # ERP authorization
                #       ↓
                # ERP Guardian ID
                #       ↓
                # ERPService
                #       ↓
                # ERPNext
                #
                # =================================================

                try:

                    # -------------------------------------------------
                    # USER ID REQUIRED
                    # -------------------------------------------------

                    if not user_id:

                        print(
                            "🚫 [ERP Auth] "
                            "No VOCIRA user_id."
                        )

                        ai_response_text = (
                            "You are not authorized "
                            "to access ERP information. "
                            "Please log in with an "
                            "authorized account."
                        )

                    else:

                        print("=" * 70)

                        print(
                            "🔐 [ERP AUTHENTICATION]"
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
                            "LiveKit Role   : "
                            "NOT TRUSTED"
                        )

                        print(
                            "Auth Source    : "
                            "Auth Service"
                        )

                        print("=" * 70)

                        # =================================================
                        # GUEST PROTECTION
                        # =================================================

                        if is_guest_type(
                            user_type
                        ):

                            print(
                                "🚫 [ERP Auth] "
                                "Guest user cannot access ERP."
                            )

                            ai_response_text = (
                                "You are not authorized "
                                "to access ERP information. "
                                "Please log in with an "
                                "authorized account."
                            )

                        else:

                            # =================================================
                            # AUTH SERVICE AUTHORIZATION
                            # =================================================

                            auth_result = (
                                await verify_erp_authorization(
                                    user_id=user_id
                                )
                            )

                            if not auth_result[
                                "authorized"
                            ]:

                                reason = (
                                    auth_result.get(
                                        "reason"
                                    )
                                )

                                print(
                                    "🚫 [ERP Auth] "
                                    f"Authorization failed: "
                                    f"{reason}"
                                )

                                if (
                                    reason
                                    == "VOCIRA account is not linked to an ERP account."
                                ):

                                    ai_response_text = (
                                        "Your VOCIRA account "
                                        "is not linked to an "
                                        "ERP account."
                                    )

                                else:

                                    ai_response_text = (
                                        "You are not authorized "
                                        "to access ERP information."
                                    )

                            else:

                                erp_guardian_id = (
                                    auth_result[
                                        "erp_guardian_id"
                                    ]
                                )

                                # =================================================
                                # ERP ACCOUNT MAPPING
                                # =================================================

                                print("=" * 70)

                                print(
                                    "🔗 [ERP ACCOUNT MAPPING]"
                                )

                                print(
                                    f"VOCIRA User ID  : "
                                    f"{user_id}"
                                )

                                print(
                                    f"ERP Guardian ID : "
                                    f"{erp_guardian_id}"
                                )

                                print("=" * 70)

                                # =================================================
                                # ERP SERVICE
                                # =================================================

                                print(
                                    "🏫 [ERP QUERY]"
                                )

                                print(
                                    f"User Query      : "
                                    f"{user_query}"
                                )

                                print(
                                    f"ERP Guardian ID : "
                                    f"{erp_guardian_id}"
                                )

                                erp_data = (
                                    await erp_service.handle_query(
                                        user_query=user_query,
                                        erp_parent_id=erp_guardian_id,
                                    )
                                )

                                print(
                                    "🏫 [ERP DATA]"
                                )

                                print(
                                    erp_data
                                )

                                # =================================================
                                # HUMAN RESPONSE
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

                try:

                    ai_response_text = (
                        await ask_vocira(
                            retriever=retriever,
                            user_query=user_query,
                        )
                    )

                    if ai_response_text:

                        ai_response_text = (
                            ai_response_text.strip()
                        )

                except Exception as rag_error:

                    print(
                        "❌ [RAG Pipeline Error]"
                    )

                    print(
                        f"Error: {rag_error}"
                    )

                    traceback.print_exc()

                    ai_response_text = (
                        "Sorry, I was unable to "
                        "process your request right now."
                    )

            # =================================================
            # HANDLER CHECK BEFORE AI RESPONSE
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

                await db.rollback()

                return

            # -------------------------------------------------
            # DATABASE HANDLER CHECK
            # -------------------------------------------------

            current_handler = (
                await get_session_handler(
                    db=db,
                    session_id=session_id,
                )
            )

            if (
                current_handler
                != SessionHandler.ai
            ):

                print(
                    "📞 [Handler] "
                    "Session is no longer handled by AI."
                )

                await db.rollback()

                return

            # =================================================
            # EMPTY RESPONSE
            # =================================================

            if not ai_response_text:

                print(
                    "⚠️ [AI] Empty response."
                )

                await db.rollback()

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

            # -------------------------------------------------
            # COMMIT USER + AI MESSAGE
            # -------------------------------------------------

            try:

                await db.commit()

            except Exception as commit_error:

                print(
                    "❌ [DATABASE] "
                    "Failed to commit messages."
                )

                print(
                    commit_error
                )

                traceback.print_exc()

                await db.rollback()

                return

        # =====================================================
        # 6. FINAL HANDLER CHECK BEFORE TTS
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

        try:

            async with SessionLocal() as handler_db:

                current_handler = (
                    await get_session_handler(
                        db=handler_db,
                        session_id=session_id,
                    )
                )

            if (
                current_handler
                != SessionHandler.ai
            ):

                print(
                    "📞 [TTS] "
                    "Session is no longer owned by AI."
                )

                return

        except Exception as handler_error:

            print(
                "⚠️ [TTS] "
                f"Unable to verify handler: "
                f"{handler_error}"
            )

            return

        # =====================================================
        # 7. TTS GENERATION
        # =====================================================

        try:

            audio_bytes = await asyncio.to_thread(
                tts_converter,
                text=ai_response_text,
            )

        except Exception as tts_error:

            print(
                "❌ [TTS] "
                f"TTS generation failed: "
                f"{tts_error}"
            )

            traceback.print_exc()

            return

        if not audio_bytes:

            print(
                "⚠️ [TTS] "
                "No audio bytes generated."
            )

            return

        # =====================================================
        # 8. WAIT FOR LIVEKIT TRACK
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
        # 9. SERIALIZED TTS
        # =====================================================

        async with service_handle._tts_lock:

            # -------------------------------------------------
            # SERVICE HANDOFF CHECK
            # -------------------------------------------------

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
            # DATABASE HANDLER CHECK
            # -------------------------------------------------

            try:

                async with SessionLocal() as handler_db:

                    current_handler = (
                        await get_session_handler(
                            db=handler_db,
                            session_id=session_id,
                        )
                    )

                if (
                    current_handler
                    != SessionHandler.ai
                ):

                    print(
                        "📞 [TTS] "
                        "Session is handled by ADMIN. "
                        "TTS cancelled."
                    )

                    return

            except Exception as handler_error:

                print(
                    "⚠️ [TTS] "
                    f"Unable to verify session handler: "
                    f"{handler_error}"
                )

                return

            # -------------------------------------------------
            # GENERATION CHECK
            # -------------------------------------------------

            if (
                generation
                != service_handle._speech_generation
            ):

                print(
                    "⏭️ [TTS] "
                    "Stale generation."
                )

                return

            # -------------------------------------------------
            # ROOM CHECK
            # -------------------------------------------------

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
                sample_rate
                * 20
                / 1000
            )

            chunk_size = (
                samples_per_channel
                * num_channels
                * bytes_per_sample
            )

            service_handle._is_agent_speaking = True

            # =================================================
            # PLAY TTS
            # =================================================

            try:

                for i in range(
                    0,
                    len(audio_bytes),
                    chunk_size,
                ):

                    # -----------------------------------------
                    # HANDOFF CHECK
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

                        break

                    # -----------------------------------------
                    # DATABASE HANDLER
                    # -----------------------------------------

                    try:

                        async with SessionLocal() as handler_db:

                            current_handler = (
                                await get_session_handler(
                                    db=handler_db,
                                    session_id=session_id,
                                )
                            )

                        if (
                            current_handler
                            != SessionHandler.ai
                        ):

                            print(
                                "📞 [TTS] "
                                "Session switched to ADMIN. "
                                "Stopping playback."
                            )

                            break

                    except Exception as handler_error:

                        print(
                            "⚠️ [TTS] "
                            f"Handler check failed: "
                            f"{handler_error}"
                        )

                        break

                    # -----------------------------------------
                    # GENERATION
                    # -----------------------------------------

                    if (
                        generation
                        != service_handle._speech_generation
                    ):

                        print(
                            "✋ [TTS] "
                            "Playback interrupted."
                        )

                        break

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

                        break

            finally:

                service_handle._is_agent_speaking = False

            print(
                "✅ [TTS] "
                "Audio generation completed."
            )

    except Exception:

        print(
            "❌ [Pipeline Error]:"
        )

        traceback.print_exc()
