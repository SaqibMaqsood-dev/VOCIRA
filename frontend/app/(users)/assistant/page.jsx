"use client";

import { motion } from "framer-motion";
import {
  Mic,
  Pause,
  Play,
  PhoneOff,
} from "lucide-react";
import {
  useEffect,
  useRef,
  useState,
} from "react";

import {
  Room,
  RoomEvent,
  Track,
} from "livekit-client";


// ============================================================
// API CONFIGURATION
// ============================================================
//
// Frontend
//     ↓
// Gateway :9000
//     ↓
// LiveKit/RAG Service :8001
//
// The frontend MUST NOT directly call port 8001.
//
// Gateway handles:
//   POST /livekit/live_kit/token
//   POST /livekit/guest/live_kit/token
//
// Session lifecycle is handled by the backend worker.
//
// IMPORTANT:
// The frontend does NOT close PostgreSQL sessions.
// When the LiveKit room is disconnected, the worker handles
// the backend session cleanup.
// ============================================================

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  "http://127.0.0.1:9000";


// ============================================================
// ASSISTANT PAGE
// ============================================================

export default function AssistantPage() {

  // ==========================================================
  // STATE
  // ==========================================================

  const [room, setRoom] =
    useState(null);

  const [sessionId, setSessionId] =
    useState(null);

  const [isConnecting, setIsConnecting] =
    useState(false);

  const [isConnected, setIsConnected] =
    useState(false);

  const [isPaused, setIsPaused] =
    useState(false);

  const [isEnding, setIsEnding] =
    useState(false);

  const [error, setError] =
    useState(null);


  // ==========================================================
  // REFS
  // ==========================================================

  const roomRef =
    useRef(null);

  const sessionIdRef =
    useRef(null);


  // ==========================================================
  // CLEAN AUDIO ELEMENTS
  // ==========================================================

  const cleanupAudioElements =
    () => {

      if (
        typeof document ===
        "undefined"
      ) {
        return;
      }


      const audioElements =
        document.querySelectorAll(
          "audio"
        );


      audioElements.forEach(
        (audio) => {

          try {

            audio.pause();

            audio.srcObject =
              null;

            audio.remove();

          } catch (
            audioError
          ) {

            console.warn(
              "⚠️ Audio cleanup failed:",
              audioError
            );
          }
        }
      );
    };


  // ==========================================================
  // START CALL
  // ==========================================================

  const handleMicClick =
    async () => {

      if (
        isConnecting ||
        isConnected ||
        isEnding
      ) {
        return;
      }


      setIsConnecting(
        true
      );

      setError(
        null
      );


      // ======================================================
      // RESET SESSION STATE
      // ======================================================

      setSessionId(
        null
      );

      sessionIdRef.current =
        null;

      roomRef.current =
        null;


      try {

        console.log(
          "========================================"
        );

        console.log(
          "🎙️ STARTING VOICE CALL"
        );

        console.log(
          "🌐 GATEWAY:",
          API_BASE_URL
        );

        console.log(
          "========================================"
        );


        // ====================================================
        // ACCESS TOKEN
        // ====================================================

        const accessToken =
          localStorage.getItem(
            "access_token"
          );


        const isAuthenticated =
          Boolean(
            accessToken
          );


        console.log(
          "🔐 Authenticated:",
          isAuthenticated
        );


        // ====================================================
        // SELECT TOKEN ENDPOINT
        // ====================================================
        //
        // Authenticated:
        //
        // POST /livekit/live_kit/token
        //
        // Guest:
        //
        // POST /livekit/guest/live_kit/token
        //
        // Both go through Gateway :9000.
        // ====================================================

        let tokenEndpoint;


        if (
          isAuthenticated
        ) {

          tokenEndpoint =
            `${API_BASE_URL}/livekit/live_kit/token`;


          console.log(
            "👨‍👩‍👧 Using authenticated LiveKit endpoint"
          );

        } else {

          tokenEndpoint =
            `${API_BASE_URL}/livekit/guest/live_kit/token`;


          console.log(
            "👤 Using guest LiveKit endpoint"
          );
        }


        console.log(
          "📡 TOKEN ENDPOINT:",
          tokenEndpoint
        );


        // ====================================================
        // REQUEST HEADERS
        // ====================================================

        const headers = {

          Accept:
            "application/json",

          "Content-Type":
            "application/json",
        };


        if (
          isAuthenticated &&
          accessToken
        ) {

          headers.Authorization =
            `Bearer ${accessToken}`;
        }


        // ====================================================
        // REQUEST LIVEKIT TOKEN
        // ====================================================

        console.log(
          "📡 Requesting LiveKit token through Gateway..."
        );


        const tokenResponse =
          await fetch(
            tokenEndpoint,
            {
              method: "POST",

              headers,

              body:
                JSON.stringify({}),
            }
          );


        console.log(
          "📥 TOKEN STATUS:",
          tokenResponse.status
        );


        // ====================================================
        // READ RAW RESPONSE
        // ====================================================

        const rawTokenResponse =
          await tokenResponse.text();


        console.log(
          "📦 TOKEN RESPONSE:",
          rawTokenResponse
        );


        // ====================================================
        // TOKEN API ERROR
        // ====================================================

        if (
          !tokenResponse.ok
        ) {

          // --------------------------------------------------
          // AUTH FAILURE
          // --------------------------------------------------

          if (
            isAuthenticated &&
            (
              tokenResponse.status ===
              401 ||
              tokenResponse.status ===
              403
            )
          ) {

            throw new Error(
              "Your login session has expired. Please login again."
            );
          }


          // --------------------------------------------------
          // ENDPOINT NOT FOUND
          // --------------------------------------------------

          if (
            tokenResponse.status ===
            404
          ) {

            throw new Error(
              `LiveKit Gateway endpoint not found.

Requested:
${tokenEndpoint}

Gateway returned:
404`
            );
          }


          // --------------------------------------------------
          // OTHER ERROR
          // --------------------------------------------------

          throw new Error(
            `LiveKit token request failed (${tokenResponse.status}).

Gateway response:
${rawTokenResponse}`
          );
        }


        // ====================================================
        // PARSE JSON
        // ====================================================

        let data;


        try {

          data =
            JSON.parse(
              rawTokenResponse
            );

        } catch (
          parseError
        ) {

          console.error(
            "❌ Invalid JSON from Gateway:",
            parseError
          );

          throw new Error(
            `Gateway returned invalid JSON.

Response:
${rawTokenResponse}`
          );
        }


        console.log(
          "🎫 TOKEN DATA:",
          data
        );


        // ====================================================
        // EXTRACT LIVEKIT TOKEN
        // ====================================================

        const livekitToken =
          typeof data?.token ===
          "string"
            ? data.token.trim()
            : "";


        // ====================================================
        // EXTRACT LIVEKIT URL
        // ====================================================

        const livekitUrl =
          typeof data?.url ===
          "string"
            ? data.url.trim()
            : "";


        // ====================================================
        // EXTRACT SESSION ID
        // ====================================================

        const backendSessionId =
          typeof data?.session_id ===
          "string"
            ? data.session_id.trim()
            : "";


        // ====================================================
        // EXTRACT ROOM
        // ====================================================

        const roomName =
          typeof data?.room ===
          "string"
            ? data.room.trim()
            : typeof data?.room_name ===
              "string"
              ? data.room_name.trim()
              : "";


        // ====================================================
        // DEBUG EXTRACTED VALUES
        // ====================================================

        console.log(
          "🔎 Extracted values:",
          {
            tokenExists:
              Boolean(
                livekitToken
              ),

            tokenLength:
              livekitToken.length,

            url:
              livekitUrl,

            sessionId:
              backendSessionId,

            room:
              roomName,
          }
        );


        // ====================================================
        // VALIDATE TOKEN
        // ====================================================

        if (
          !livekitToken
        ) {

          throw new Error(
            `Gateway did not return a valid "token".

Response:
${JSON.stringify(
  data,
  null,
  2
)}`
          );
        }


        // ====================================================
        // VALIDATE LIVEKIT URL
        // ====================================================

        if (
          !livekitUrl
        ) {

          throw new Error(
            `Gateway did not return a valid "url".

Response:
${JSON.stringify(
  data,
  null,
  2
)}`
          );
        }


        // ====================================================
        // VALIDATE SESSION ID
        // ====================================================

        if (
          !backendSessionId
        ) {

          throw new Error(
            `Gateway did not return "session_id".

Response:
${JSON.stringify(
  data,
  null,
  2
)}`
          );
        }


        // ====================================================
        // VALIDATE ROOM
        // ====================================================

        if (
          !roomName
        ) {

          throw new Error(
            `Gateway did not return a valid "room".

Response:
${JSON.stringify(
  data,
  null,
  2
)}`
          );
        }


        // ====================================================
        // SAVE SESSION INFORMATION
        // ====================================================

        setSessionId(
          backendSessionId
        );

        sessionIdRef.current =
          backendSessionId;


        console.log(
          "🆔 SESSION:",
          backendSessionId
        );

        console.log(
          "🏠 ROOM:",
          roomName
        );


        // ====================================================
        // CREATE LIVEKIT ROOM
        // ====================================================

        const livekitRoom =
          new Room();


        roomRef.current =
          livekitRoom;


        // ====================================================
        // PARTICIPANT CONNECTED
        // ====================================================

        livekitRoom.on(
          RoomEvent.ParticipantConnected,
          (participant) => {

            console.log(
              "👤 Participant joined:",
              participant.identity
            );
          }
        );


        // ====================================================
        // PARTICIPANT DISCONNECTED
        // ====================================================

        livekitRoom.on(
          RoomEvent.ParticipantDisconnected,
          (participant) => {

            console.log(
              "🚪 Participant left:",
              participant.identity
            );
          }
        );


        // ====================================================
        // TRACK PUBLISHED
        // ====================================================

        livekitRoom.on(
          RoomEvent.TrackPublished,
          (
            publication,
            participant
          ) => {

            console.log(
              "📡 Track published:",
              publication.kind,
              publication.trackName,
              participant.identity
            );
          }
        );


        // ====================================================
        // REMOTE AUDIO
        // ====================================================

        livekitRoom.on(
          RoomEvent.TrackSubscribed,
          (
            track,
            publication,
            participant
          ) => {

            console.log(
              "🎧 Track subscribed:",
              track.kind,
              participant.identity
            );


            // ------------------------------------------------
            // ONLY HANDLE AUDIO
            // ------------------------------------------------

            if (
              track.kind !==
              Track.Kind.Audio
            ) {

              return;
            }


            console.log(
              "🔊 Agent audio received from:",
              participant.identity
            );


            // ------------------------------------------------
            // ATTACH AUDIO
            // ------------------------------------------------

            const audioElement =
              track.attach();


            audioElement.autoplay =
              true;

            audioElement.setAttribute(
              "playsinline",
              "true"
            );

            audioElement.style.display =
              "none";


            document.body.appendChild(
              audioElement
            );


            // ------------------------------------------------
            // PLAY AUDIO
            // ------------------------------------------------

            audioElement
              .play()
              .then(
                () => {

                  console.log(
                    "🔊 Agent voice playing."
                  );
                }
              )
              .catch(
                (
                  audioError
                ) => {

                  console.error(
                    "❌ Could not play agent audio:",
                    audioError
                  );
                }
              );
          }
        );


        // ====================================================
        // TRACK UNSUBSCRIBED
        // ====================================================

        livekitRoom.on(
          RoomEvent.TrackUnsubscribed,
          (
            track,
            publication,
            participant
          ) => {

            console.log(
              "🔇 Track unsubscribed:",
              track.kind,
              participant.identity
            );


            if (
              track.kind !==
              Track.Kind.Audio
            ) {

              return;
            }


            track
              .detach()
              .forEach(
                (
                  element
                ) => {

                  try {

                    element.pause();

                    element.srcObject =
                      null;

                    element.remove();

                  } catch (
                    audioError
                  ) {

                    console.warn(
                      "⚠️ Audio cleanup failed:",
                      audioError
                    );
                  }
                }
              );
          }
        );


        // ====================================================
        // LIVEKIT DISCONNECTED
        // ====================================================
        //
        // IMPORTANT:
        //
        // DO NOT CLOSE THE BACKEND SESSION HERE.
        //
        // The worker is responsible for detecting the room
        // disconnect / grace-period expiry and performing the
        // backend session cleanup.
        // ====================================================

        livekitRoom.on(
          RoomEvent.Disconnected,
          (
            reason
          ) => {

            console.log(
              "🚪 LiveKit disconnected:",
              reason
            );


            console.log(
              "ℹ️ Frontend will not close the backend session."
            );

            console.log(
              "ℹ️ Worker/backend is responsible for session cleanup."
            );


            setRoom(
              null
            );

            setIsConnected(
              false
            );

            setIsPaused(
              false
            );


            roomRef.current =
              null;


            cleanupAudioElements();
          }
        );


        // ====================================================
        // CONNECT TO LIVEKIT
        // ====================================================

        console.log(
          "🔌 Connecting to LiveKit..."
        );


        await livekitRoom.connect(
          livekitUrl,
          livekitToken
        );


        console.log(
          "✅ Connected to LiveKit:",
          livekitRoom.name
        );


        // ====================================================
        // ENABLE MICROPHONE
        // ====================================================

        await livekitRoom
          .localParticipant
          .setMicrophoneEnabled(
            true
          );


        console.log(
          "🎤 Microphone enabled."
        );


        // ====================================================
        // SAVE ROOM STATE
        // ====================================================

        setRoom(
          livekitRoom
        );

        setIsConnected(
          true
        );

        setIsPaused(
          false
        );


        console.log(
          "========================================"
        );

        console.log(
          "✅ VOICE CALL CONNECTED"
        );

        console.log(
          "🆔 SESSION:",
          backendSessionId
        );

        console.log(
          "🏠 ROOM:",
          roomName
        );

        console.log(
          "========================================"
        );


      } catch (
        err
      ) {

        console.error(
          "========================================"
        );

        console.error(
          "❌ ERROR CONNECTING TO LIVEKIT"
        );

        console.error(
          err
        );

        console.error(
          "========================================"
        );


        // ====================================================
        // CLEAN LIVEKIT ROOM
        // ====================================================
        //
        // IMPORTANT:
        //
        // We DO NOT call the backend session close endpoint.
        //
        // If a session was already created, disconnecting the
        // room allows the worker/backend to handle cleanup.
        // ====================================================

        if (
          roomRef.current
        ) {

          try {

            await roomRef.current.disconnect();

          } catch (
            disconnectError
          ) {

            console.warn(
              "⚠️ LiveKit cleanup failed:",
              disconnectError
            );
          }
        }


        cleanupAudioElements();


        // ====================================================
        // RESET STATE
        // ====================================================

        setRoom(
          null
        );

        setSessionId(
          null
        );

        sessionIdRef.current =
          null;

        roomRef.current =
          null;

        setIsConnected(
          false
        );

        setIsPaused(
          false
        );


        setError(
          err?.message ||
          "Could not connect to voice assistant."
        );

      } finally {

        setIsConnecting(
          false
        );
      }
    };


  // ==========================================================
  // PAUSE / RESUME
  // ==========================================================

  const handlePauseResume =
    async () => {

      if (
        !room ||
        !isConnected ||
        isEnding
      ) {

        return;
      }


      try {

        // ====================================================
        // RESUME MICROPHONE
        // ====================================================

        if (
          isPaused
        ) {

          await room
            .localParticipant
            .setMicrophoneEnabled(
              true
            );


          setIsPaused(
            false
          );


          console.log(
            "🎤 Microphone resumed."
          );

        }

        // ====================================================
        // PAUSE MICROPHONE
        // ====================================================

        else {

          await room
            .localParticipant
            .setMicrophoneEnabled(
              false
            );


          setIsPaused(
            true
          );


          console.log(
            "⏸️ Microphone paused."
          );
        }


      } catch (
        err
      ) {

        console.error(
          "❌ Microphone state error:",
          err
        );


        setError(
          err?.message ||
          "Could not change microphone state."
        );
      }
    };


  // ==========================================================
  // END CALL
  // ==========================================================
  //
  // IMPORTANT ARCHITECTURE:
  //
  // Frontend DOES NOT close the PostgreSQL session.
  //
  // Frontend only:
  //
  // 1. Disables microphone
  // 2. Disconnects from LiveKit
  //
  // Then:
  //
  // LiveKit disconnect
  //       ↓
  // Worker detects disconnect
  //       ↓
  // Grace period
  //       ↓
  // Worker cleanup
  //       ↓
  // Backend session closed
  //
  // ==========================================================
const handleEndCall = async () => {
  if (!room || !isConnected || isEnding) {
    return;
  }

  setIsEnding(true);
  setError(null);

  try {
    console.log("========================================");
    console.log("📞 ENDING CALL");
    console.log("🆔 SESSION:", sessionIdRef.current);
    console.log("========================================");

    // Disable microphone
    try {
      await room.localParticipant.setMicrophoneEnabled(false);
    } catch (micError) {
      console.warn(
        "⚠️ Could not disable microphone:",
        micError
      );
    }

   

    console.log(
      "🔌 Disconnecting from LiveKit..."
    );

    await room.disconnect();

    console.log(
      "🚪 LiveKit disconnected."
    );

    cleanupAudioElements();

    setRoom(null);
    setSessionId(null);

    sessionIdRef.current = null;
    roomRef.current = null;

    setIsConnected(false);
    setIsPaused(false);

    console.log(
      "✅ CALL ENDED — worker will finalize the backend session."
    );

  } catch (err) {
    console.error(
      "❌ Error ending call:",
      err
    );

    setError(
      err?.message ||
      "Could not end the call."
    );

  } finally {
    setIsEnding(false);
  }
};

  // ==========================================================
  // COMPONENT CLEANUP
  // ==========================================================

  useEffect(
    () => {

      return () => {

        cleanupAudioElements();

      };

    },
    []
  );


  // ==========================================================
  // UI
  // ==========================================================

  return (

    <div className="page-shell !max-w-none !px-0 !py-0">

      <section className="relative mx-auto flex min-h-[calc(100vh-4rem-2.5rem)] w-full items-center justify-center overflow-hidden bg-transparent">

        <motion.div
          initial={{
            opacity: 0,
            y: 16,
          }}
          animate={{
            opacity: 1,
            y: 0,
          }}
          transition={{
            duration: 0.7,
            ease: "easeOut",
          }}
          className="relative z-10 mx-auto flex w-full max-w-6xl flex-col items-center justify-center px-4 py-0 text-center sm:px-6"
        >

          {/* ==================================================
              HEADING
          ================================================== */}

          <h1 className="max-w-5xl text-3xl font-semibold sm:text-5xl">

            Create the most realistic speech

            <br />

            with our AI audio platform

          </h1>


          <p className="mt-4 max-w-3xl text-sm text-text-secondary sm:text-base">

            Pioneering research in Text to Speech,
            AI Voice Generator, and more

          </p>


          {/* ==================================================
              MICROPHONE
          ================================================== */}

          <div
            id="voice-assistant-demo"
            className={`assistant-speaker-float relative mt-10 flex h-[290px] w-[290px] items-center justify-center ${
              isConnecting ||
              isConnected ||
              isEnding
                ? "cursor-default"
                : "cursor-pointer"
            }`}
            onClick={
              !isConnected &&
              !isConnecting &&
              !isEnding
                ? handleMicClick
                : undefined
            }
          >

            <div className="absolute h-[250px] w-[250px] rounded-full border border-white/20 bg-white/5 shadow-[0_0_0_20px_rgba(139,233,253,0.08)] backdrop-blur-md" />


            <motion.div
              className="assistant-mic-core relative grid h-28 w-28 place-items-center rounded-full bg-gradient-to-b from-accent-primary/80 to-accent-secondary/85 text-white shadow-[0_14px_40px_rgba(108,99,255,0.35)]"
              animate={
                isConnected &&
                !isPaused
                  ? {
                      scale: [
                        1,
                        1.08,
                        1,
                      ],
                    }
                  : {
                      scale: [
                        1,
                        1.03,
                        1,
                      ],
                    }
              }
              transition={{
                duration:
                  isConnected &&
                  !isPaused
                    ? 1.5
                    : 3.2,

                repeat:
                  Infinity,

                ease:
                  "easeInOut",
              }}
            >

              <Mic className="h-9 w-9" />

            </motion.div>

          </div>


          {/* ==================================================
              CONNECTING
          ================================================== */}

          {isConnecting && (

            <p className="mt-5 text-yellow-400">

              Connecting to voice assistant...

            </p>

          )}


          {/* ==================================================
              CONNECTED
          ================================================== */}

          {isConnected &&
            room && (

              <div className="mt-5">

                <p
                  className={
                    isPaused
                      ? "text-yellow-400"
                      : "text-green-500"
                  }
                >

                  {
                    isPaused
                      ? "Voice assistant paused"
                      : "Connected to voice assistant"
                  }

                </p>


                <p className="mt-1 text-sm text-text-secondary">

                  Room: {room.name}

                </p>


                {sessionId && (

                  <p className="mt-1 text-xs text-text-secondary">

                    Session: {sessionId}

                  </p>

                )}


                <div className="mt-5 flex items-center justify-center gap-4">

                  {/* ==================================================
                      PAUSE / RESUME
                  ================================================== */}

                  <button
                    type="button"
                    disabled={isEnding}
                    onClick={
                      handlePauseResume
                    }
                    className="flex h-12 items-center gap-2 rounded-full border border-white/20 bg-white/10 px-5 text-sm text-white transition hover:bg-white/20 disabled:cursor-not-allowed disabled:opacity-50"
                  >

                    {isPaused ? (

                      <>

                        <Play className="h-4 w-4" />

                        Resume

                      </>

                    ) : (

                      <>

                        <Pause className="h-4 w-4" />

                        Pause

                      </>

                    )}

                  </button>


                  {/* ==================================================
                      END CALL
                  ================================================== */}

                  <button
                    type="button"
                    disabled={isEnding}
                    onClick={
                      handleEndCall
                    }
                    className="flex h-12 items-center gap-2 rounded-full bg-red-500/90 px-5 text-sm text-white transition hover:bg-red-500 disabled:cursor-not-allowed disabled:opacity-50"
                  >

                    <PhoneOff className="h-4 w-4" />

                    {
                      isEnding
                        ? "Ending..."
                        : "End Call"
                    }

                  </button>

                </div>

              </div>

            )}


          {/* ==================================================
              ERROR
          ================================================== */}

          {error && (

            <div className="mt-5 max-w-3xl rounded-lg border border-red-500/30 bg-red-500/10 px-5 py-4 text-left">

              <p className="whitespace-pre-wrap text-sm font-medium text-red-400">

                {error}

              </p>

            </div>

          )}

        </motion.div>

      </section>

    </div>
  );
}