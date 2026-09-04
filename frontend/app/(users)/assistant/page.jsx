"use client";

import { motion } from "framer-motion";
import {
  Mic,
  Pause,
  Play,
  PhoneOff,
} from "lucide-react";
import { useState } from "react";

import {
  Room,
  RoomEvent,
  Track,
} from "livekit-client";

import { RoomContext } from "@livekit/components-react";

import AgentVisualizer from "@/components/AgentVisualizer";

export default function AssistantPage() {
  const [room, setRoom] = useState(null);
  const [sessionId, setSessionId] = useState(null);

  const [isConnecting, setIsConnecting] =
    useState(false);

  const [isConnected, setIsConnected] =
    useState(false);

  const [isPaused, setIsPaused] =
    useState(false);

  const [isEnding, setIsEnding] =
    useState(false);

  const [error, setError] = useState(null);

  // ============================================================
  // START CALL
  // ============================================================

  const handleMicClick = async () => {
    if (
      isConnecting ||
      isConnected ||
      isEnding
    ) {
      return;
    }

    setIsConnecting(true);
    setError(null);

    try {
      // ========================================================
      // 1. API BASE URL
      // ========================================================

      const API_BASE_URL =
        process.env.NEXT_PUBLIC_API_URL ||
        "http://localhost:9000";

      console.log(
        "========================================"
      );

      console.log(
        "🌐 API BASE URL:",
        API_BASE_URL
      );

      // ========================================================
      // 2. GET AUTH TOKEN
      // ========================================================

      const accessToken =
        localStorage.getItem("access_token");

      console.log(
        "🔐 Access token exists:",
        Boolean(accessToken)
      );

      const isAuthenticated =
        Boolean(accessToken);

      // ========================================================
      // 3. SELECT ENDPOINT
      // ========================================================

      let tokenEndpoint;

      if (isAuthenticated) {
        tokenEndpoint =
          `${API_BASE_URL}/livekit/live_kit/token`;

        console.log(
          "👨‍👩‍👧 Using authenticated LiveKit endpoint:"
        );

      } else {
        tokenEndpoint =
          `${API_BASE_URL}/livekit/guest/live_kit/token`;

        console.log(
          "👤 Using guest LiveKit endpoint:"
        );
      }

      console.log(
        "📡 TOKEN ENDPOINT:",
        tokenEndpoint
      );

      // ========================================================
      // 4. HEADERS
      // ========================================================

      const headers = {
        Accept: "application/json",
        "Content-Type": "application/json",
      };

      if (isAuthenticated) {
        headers.Authorization =
          `Bearer ${accessToken}`;
      }

      console.log(
        "📋 Request headers:",
        {
          Accept: headers.Accept,
          Authorization:
            isAuthenticated
              ? "Bearer ********"
              : "none",
        }
      );

      // ========================================================
      // 5. REQUEST TOKEN
      // ========================================================

      console.log(
        "📡 Requesting LiveKit token..."
      );

      const tokenResponse =
        await fetch(
          tokenEndpoint,
          {
            method: "POST",
            headers,
            body: JSON.stringify({}),
          }
        );

      // ========================================================
      // 6. HTTP STATUS
      // ========================================================

      console.log(
        "📥 HTTP STATUS:",
        tokenResponse.status
      );

      console.log(
        "📥 HTTP OK:",
        tokenResponse.ok
      );

      // ========================================================
      // 7. READ RAW RESPONSE FIRST
      // ========================================================

      const rawResponse =
        await tokenResponse.text();

      console.log(
        "========================================"
      );

      console.log(
        "📦 RAW BACKEND RESPONSE:"
      );

      console.log(
        rawResponse
      );

      console.log(
        "========================================"
      );

      // ========================================================
      // 8. HANDLE HTTP ERROR
      // ========================================================

      if (!tokenResponse.ok) {
        if (
          isAuthenticated &&
          (
            tokenResponse.status === 401 ||
            tokenResponse.status === 403
          )
        ) {
          throw new Error(
            "Your login session has expired. Please login again."
          );
        }

        if (
          tokenResponse.status === 404
        ) {
          throw new Error(
            `LiveKit endpoint not found.

Requested:
${tokenEndpoint}

Backend returned:
404`
          );
        }

        throw new Error(
          `LiveKit token request failed (${tokenResponse.status}).

Backend response:
${rawResponse}`
        );
      }

      // ========================================================
      // 9. PARSE JSON
      // ========================================================

      let data;

      try {
        data =
          JSON.parse(rawResponse);
      } catch (parseError) {
        console.error(
          "❌ Backend did not return valid JSON."
        );

        throw new Error(
          `Backend returned invalid JSON.

Raw response:
${rawResponse}`
        );
      }

      console.log(
        "🎫 PARSED BACKEND RESPONSE:",
        data
      );

      console.log(
        "🎫 Response keys:",
        Object.keys(data || {})
      );

      // ========================================================
      // 10. EXTRACT TOKEN
      // ========================================================

      /*
       * Expected backend response:
       *
       * {
       *   session_id: "...",
       *   token: "...",
       *   room: "...",
       *   url: "..."
       * }
       */

      const livekitToken =
        typeof data?.token === "string"
          ? data.token.trim()
          : "";

      const livekitUrl =
        typeof data?.url === "string"
          ? data.url.trim()
          : "";

      const backendSessionId =
        data?.session_id;

      const roomName =
        typeof data?.room === "string"
          ? data.room.trim()
          : "";

      console.log(
        "🔎 Extracted values:"
      );

      console.log(
        "token exists:",
        Boolean(livekitToken)
      );

      console.log(
        "token type:",
        typeof data?.token
      );

      console.log(
        "token length:",
        livekitToken.length
      );

      console.log(
        "url:",
        livekitUrl
      );

      console.log(
        "session_id:",
        backendSessionId
      );

      console.log(
        "room:",
        roomName
      );

      // ========================================================
      // 11. VALIDATE TOKEN
      // ========================================================

      if (!livekitToken) {
        console.error(
          "❌ BACKEND TOKEN MISSING"
        );

        console.error(
          "Full backend object:",
          data
        );

        throw new Error(
          `Backend did not return a valid 'token'.

Backend response:
${JSON.stringify(
  data,
  null,
  2
)}`
        );
      }

      // ========================================================
      // 12. VALIDATE URL
      // ========================================================

      if (!livekitUrl) {
        throw new Error(
          `Backend did not return a valid 'url'.

Backend response:
${JSON.stringify(
  data,
  null,
  2
)}`
        );
      }

      // ========================================================
      // 13. VALIDATE SESSION
      // ========================================================

      if (!backendSessionId) {
        throw new Error(
          `Backend did not return 'session_id'.

Backend response:
${JSON.stringify(
  data,
  null,
  2
)}`
        );
      }

      // ========================================================
      // 14. VALIDATE ROOM
      // ========================================================

      if (!roomName) {
        throw new Error(
          `Backend did not return a valid 'room'.

Backend response:
${JSON.stringify(
  data,
  null,
  2
)}`
        );
      }

      // ========================================================
      // 15. SAVE SESSION
      // ========================================================

      setSessionId(
        backendSessionId
      );

      console.log(
        "🆔 SESSION ID:",
        backendSessionId
      );

      console.log(
        "🏠 ROOM:",
        roomName
      );

      console.log(
        "🔗 LIVEKIT URL:",
        livekitUrl
      );

      console.log(
        "👤 SESSION TYPE:",
        isAuthenticated
          ? "AUTHENTICATED PARENT"
          : "GUEST"
      );

      // ========================================================
      // 16. CREATE LIVEKIT ROOM
      // ========================================================

      const livekitRoom =
        new Room({
          // Echo cancellation lazmi hai. Iske baghair speaker se
          // nikalti agent ki apni awaaz wapis mic mein aati hai,
          // backend use "user bol raha hai" samajh kar barge-in
          // kar deta hai, aur agent beech jumle mein chup ho jata
          // hai. Noise suppression background shor rokta hai.
          audioCaptureDefaults: {
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
          },
        });

      // ========================================================
      // 17. PARTICIPANT CONNECTED
      // ========================================================

      livekitRoom.on(
        RoomEvent.ParticipantConnected,
        (participant) => {
          console.log(
            "👤 Participant joined:",
            participant.identity
          );
        }
      );

      // ========================================================
      // 18. PARTICIPANT DISCONNECTED
      // ========================================================

      livekitRoom.on(
        RoomEvent.ParticipantDisconnected,
        (participant) => {
          console.log(
            "🚪 Participant left:",
            participant.identity
          );
        }
      );

      // ========================================================
      // 19. TRACK PUBLISHED
      // ========================================================

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

      // ========================================================
      // 20. REMOTE AUDIO
      // ========================================================

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

          audioElement
            .play()
            .then(() => {
              console.log(
                "🔊 Agent voice is playing."
              );
            })
            .catch((audioError) => {
              console.error(
                "❌ Could not play remote audio:",
                audioError
              );
            });
        }
      );

      // ========================================================
      // 21. TRACK UNSUBSCRIBED
      // ========================================================

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
            track.kind ===
            Track.Kind.Audio
          ) {
            track
              .detach()
              .forEach((element) => {
                element.pause();
                element.srcObject =
                  null;
                element.remove();
              });
          }
        }
      );

      // ========================================================
      // 22. ROOM DISCONNECTED
      // ========================================================

      livekitRoom.on(
        RoomEvent.Disconnected,
        (reason) => {
          console.log(
            "🚪 LiveKit disconnected:",
            reason
          );

          setRoom(null);
          setIsConnected(false);
          setIsPaused(false);
        }
      );

      // ========================================================
      // 23. CONNECT TO LIVEKIT
      // ========================================================

      console.log(
        "🔌 Connecting to LiveKit..."
      );

      console.log(
        "🔗 URL:",
        livekitUrl
      );

      console.log(
        "🎫 Token length:",
        livekitToken.length
      );

      await livekitRoom.connect(
        livekitUrl,
        livekitToken
      );

      console.log(
        "✅ Connected to LiveKit room:",
        livekitRoom.name
      );

      // ========================================================
      // 24. ENABLE MICROPHONE
      // ========================================================

      await livekitRoom.localParticipant.setMicrophoneEnabled(
        true
      );

      console.log(
        "🎤 Microphone enabled."
      );

      // ========================================================
      // 25. SAVE ROOM STATE
      // ========================================================

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
        "========================================"
      );

    } catch (err) {
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

  // ============================================================
  // PAUSE / RESUME
  // ============================================================

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
        if (isPaused) {
          await room.localParticipant.setMicrophoneEnabled(
            true
          );

          setIsPaused(false);

          console.log(
            "🎤 Microphone resumed."
          );
        } else {
          await room.localParticipant.setMicrophoneEnabled(
            false
          );

          setIsPaused(true);

          console.log(
            "⏸️ Microphone paused."
          );
        }

      } catch (err) {
        console.error(
          "❌ Error changing microphone state:",
          err
        );

        setError(
          err?.message ||
            "Could not change microphone state."
        );
      }
    };

  // ============================================================
  // END CALL
  // ============================================================

  const handleEndCall =
    async () => {
      if (
        !room ||
        !isConnected ||
        isEnding
      ) {
        return;
      }

      setIsEnding(true);
      setError(null);

      try {
        console.log(
          "📞 Ending call..."
        );

        // ------------------------------------------------------
        // Disable microphone
        // ------------------------------------------------------

        try {
          await room.localParticipant.setMicrophoneEnabled(
            false
          );

          console.log(
            "🎤 Microphone disabled."
          );

        } catch (micError) {
          console.warn(
            "⚠️ Could not disable microphone:",
            micError
          );
        }

        // ------------------------------------------------------
        // Disconnect
        // ------------------------------------------------------

        console.log(
          "🔌 Disconnecting frontend from LiveKit..."
        );

        await room.disconnect();

        console.log(
          "🚪 Frontend disconnected."
        );

        // ------------------------------------------------------
        // Remove audio elements
        // ------------------------------------------------------

        const audioElements =
          document.querySelectorAll(
            "audio"
          );

        audioElements.forEach(
          (audio) => {
            try {
              audio.pause();
              audio.srcObject = null;
              audio.remove();
            } catch (audioError) {
              console.warn(
                "⚠️ Could not remove audio:",
                audioError
              );
            }
          }
        );

        // ------------------------------------------------------
        // Reset state
        // ------------------------------------------------------

        setRoom(null);
        setSessionId(null);
        setIsConnected(false);
        setIsPaused(false);

        console.log(
          "✅ Call ended successfully."
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

  // ============================================================
  // UI
  // ============================================================

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

          <h1 className="max-w-5xl text-3xl font-semibold sm:text-5xl">
            Create the most realistic speech
            <br />
            with our AI audio platform
          </h1>

          <p className="mt-4 max-w-3xl text-sm text-text-secondary sm:text-base">
            Pioneering research in Text to Speech,
            AI Voice Generator, and more
          </p>

          {/* ================================================== */}
          {/* MICROPHONE */}
          {/* ================================================== */}

          {/*
            Call chal rahi ho to LiveKit ka apna visualizer - wo agent
            ki ASLI awaaz par chalta hai. Room pehle se yahan bani hui
            hai, is liye sirf RoomContext se neeche pahunchani hai;
            useVoiceAssistant() wahin se agent aur us ka track uthata
            hai.

            Pehle yahan har haal mein ek framer-motion pulse chalta tha
            (scale 1 -> 1.08 -> 1). Wo audio se juda hua nahi tha - agent
            bol raha ho ya chup ho, daira bilkul ek jaisa dikhta tha.
          */}
          {isConnected && room ? (

            <div
              id="voice-assistant-demo"
              className="assistant-speaker-float relative mt-10"
            >
              <RoomContext.Provider value={room}>
                <AgentVisualizer />
              </RoomContext.Provider>
            </div>

          ) : (

            <div
              id="voice-assistant-demo"
              className={`assistant-speaker-float relative mt-10 flex h-[290px] w-[290px] items-center justify-center ${
                isConnecting || isEnding
                  ? "cursor-default"
                  : "cursor-pointer"
              }`}
              onClick={
                !isConnecting && !isEnding
                  ? handleMicClick
                  : undefined
              }
            >

              <div className="absolute h-[250px] w-[250px] rounded-full border border-white/20 bg-white/5 shadow-[0_0_0_20px_rgba(139,233,253,0.08)] backdrop-blur-md" />

              <motion.div
                className="assistant-mic-core relative grid h-28 w-28 place-items-center rounded-full bg-gradient-to-b from-accent-primary/80 to-accent-secondary/85 text-white shadow-[0_14px_40px_rgba(108,99,255,0.35)]"
                animate={{ scale: [1, 1.03, 1] }}
                transition={{
                  duration: 3.2,
                  repeat: Infinity,
                  ease: "easeInOut",
                }}
              >
                <Mic className="h-9 w-9" />
              </motion.div>

            </div>

          )}

          {/* ================================================== */}
          {/* CONNECTING */}
          {/* ================================================== */}

          {isConnecting && (
            <p className="mt-5 text-yellow-400">
              Connecting to voice assistant...
            </p>
          )}

          {/* ================================================== */}
          {/* CONNECTED */}
          {/* ================================================== */}

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
                  {isPaused
                    ? "Voice assistant paused"
                    : "Connected to voice assistant"}
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

                  {/* PAUSE */}

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

                  {/* END CALL */}

                  <button
                    type="button"
                    disabled={isEnding}
                    onClick={
                      handleEndCall
                    }
                    className="flex h-12 items-center gap-2 rounded-full bg-red-500/90 px-5 text-sm text-white transition hover:bg-red-500 disabled:cursor-not-allowed disabled:opacity-50"
                  >

                    <PhoneOff className="h-4 w-4" />

                    {isEnding
                      ? "Ending..."
                      : "End Call"}

                  </button>

                </div>

              </div>
            )}

          {/* ================================================== */}
          {/* ERROR */}
          {/* ================================================== */}

          {error && (
            <div className="mt-5 max-w-3xl rounded-lg border border-red-500/30 bg-red-500/10 px-5 py-4 text-left">

              <p className="text-sm font-medium text-red-400">
                {error}
              </p>

            </div>
          )}

        </motion.div>

      </section>

    </div>
  );
}