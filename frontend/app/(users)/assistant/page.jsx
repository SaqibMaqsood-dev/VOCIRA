"use client";

import { motion } from "framer-motion";
import {
  Mic,
  Pause,
  Play,
  PhoneOff,
} from "lucide-react";
import { useCallback, useState } from "react";

import {
  Room,
  RoomEvent,
  Track,
} from "livekit-client";

import { RoomContext } from "@livekit/components-react";

import AgentVisualizer from "@/components/AgentVisualizer";

import {
  HANDOFF_ATTRIBUTE,
  isAdminParticipant,
} from "@/lib/handoff";
import { getAccessToken } from "@/lib/session";

// ============================================================
// HUMAN HANDOFF
//
// When the user says "I want to speak to a person", the AI sets
// this attribute on its own participant:
//
//     requested  -> an admin has been called and is on the way
//     connected  -> the admin has joined, the AI is leaving
//
// The AI's attributes disappear the moment it leaves the room, so
// the second - and stronger - proof of "connected" is that the
// admin is present in the room. Both routes are checked here.
// ============================================================

const HANDOFF_TEXT = {
  requested: {
    text: "Connecting you to a human agent…",
    className: "text-yellow-400",
  },
  connected: {
    text: "You are speaking with a human agent",
    className: "text-green-500",
  },
  agent_left: {
    text: "The human agent has ended the call.",
    className: "text-text-secondary",
  },
  no_answer: {
    text: "No one was free to take the call. The assistant is helping you again.",
    className: "text-yellow-400",
  },
};

/**
 * Remove the <audio> tags for remote audio.
 *
 * They are created hidden on the page (track.attach()). If they are
 * not removed when the call ends, every call leaves another dead
 * element behind.
 */
function removeAudioElements() {
  document.querySelectorAll("audio").forEach((audio) => {
    try {
      audio.pause();
      audio.srcObject = null;
      audio.remove();
    } catch (error) {
      console.warn(
        "Could not remove audio:",
        error
      );
    }
  });
}

const AGENT_STUCK_MESSAGE =
  "The voice assistant did not join the call. Please tap " +
  "\"End Call\" and try again.";

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

  // null | "requested" | "connected" | "agent_left"
  const [handoff, setHandoff] =
    useState(null);

  /*
   * Why the call ended - this stays on screen AFTER the call has
   * closed.
   *
   * When an admin hung up, the user used to be left sitting there:
   * "Connecting..." spinning at the top, the long Room and Session
   * ids listed, and Pause / End Call still present - even though
   * nobody was in the room any more, neither the AI nor a person.
   * The call now closes immediately, the screen returns to its
   * starting state, and this says what happened.
   */
  const [endedNotice, setEndedNotice] =
    useState("");

  /*
   * Never move backwards.
   *
   * "connected" arrives when the admin joins the room. After that
   * the AI's older "requested" attribute can still turn up again
   * (an attribute sync, for instance). Showing "Connecting..." at
   * that point would be wrong - the user is already talking.
   */
  const markHandoff = (next) => {
    setHandoff((current) => {
      if (current === "agent_left") return current;
      if (current === "connected" && next === "requested") {
        return current;
      }
      return next;
    });
  };

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

    // Nayi call - pichhli call ka natija ab bemani hai
    setEndedNotice("");

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
        "API BASE URL:",
        API_BASE_URL
      );

      // ========================================================
      // 2. GET AUTH TOKEN
      // ========================================================

      const accessToken = getAccessToken();

      console.log(
        "Access token exists:",
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
          "Using authenticated LiveKit endpoint:"
        );

      } else {
        tokenEndpoint =
          `${API_BASE_URL}/livekit/guest/live_kit/token`;

        console.log(
          "Using guest LiveKit endpoint:"
        );
      }

      console.log(
        "TOKEN ENDPOINT:",
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
        "Request headers:",
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
        "Requesting LiveKit token..."
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
        "HTTP STATUS:",
        tokenResponse.status
      );

      console.log(
        "HTTP OK:",
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
        "RAW BACKEND RESPONSE:"
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
          "Backend did not return valid JSON."
        );

        throw new Error(
          `Backend returned invalid JSON.

Raw response:
${rawResponse}`
        );
      }

      console.log(
        "PARSED BACKEND RESPONSE:",
        data
      );

      console.log(
        "Response keys:",
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
        "Extracted values:"
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
          "BACKEND TOKEN MISSING"
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
        "SESSION ID:",
        backendSessionId
      );

      console.log(
        "ROOM:",
        roomName
      );

      console.log(
        "LIVEKIT URL:",
        livekitUrl
      );

      console.log(
        "SESSION TYPE:",
        isAuthenticated
          ? "AUTHENTICATED PARENT"
          : "GUEST"
      );

      // ========================================================
      // 16. CREATE LIVEKIT ROOM
      // ========================================================

      const livekitRoom =
        new Room({
          // Echo cancellation is essential. Without it the agent's
          // own voice comes back out of the speaker and into the
          // mic, the backend reads that as "the user is speaking"
          // and barges in, and the agent falls silent mid-sentence.
          // Noise suppression keeps background noise out.
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
            "Participant joined:",
            participant.identity
          );

          // The admin joining the room is the strongest signal
          // that a person is now on the line.
          if (isAdminParticipant(participant)) {
            console.log(
              "A human agent joined the call."
            );

            markHandoff("connected");
          }

          const state =
            participant.attributes?.[
              HANDOFF_ATTRIBUTE
            ];

          if (state) {
            markHandoff(state);
          }
        }
      );

      // ========================================================
      // 17b. HANDOFF ATTRIBUTE
      // ========================================================

      livekitRoom.on(
        RoomEvent.ParticipantAttributesChanged,
        (
          changed,
          participant
        ) => {
          const state =
            changed?.[HANDOFF_ATTRIBUTE];

          if (!state) return;

          console.log(
            "Handoff state:",
            state,
            "from",
            participant.identity
          );

          markHandoff(state);
        }
      );

      // ========================================================
      // 18. PARTICIPANT DISCONNECTED
      // ========================================================

      livekitRoom.on(
        RoomEvent.ParticipantDisconnected,
        (participant) => {
          console.log(
            "Participant left:",
            participant.identity
          );

          // The admin hung up. The AI does not come back - it left
          // the room at handoff. So the room is now completely
          // empty; there is no point keeping it open. Close the
          // call at once and put the reason on screen.
          if (isAdminParticipant(participant)) {
            console.log(
              "The human agent left the call."
            );

            setHandoff("agent_left");

            setEndedNotice(
              "The staff member ended the call."
            );

            livekitRoom
              .disconnect()
              .catch(() => {
                /* pehle hi nikal chuke */
              });
          }
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
            "Track published:",
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
            "Track subscribed:",
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
            "Agent audio received from:",
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
                "Agent voice is playing."
              );
            })
            .catch((audioError) => {
              console.error(
                "Could not play remote audio:",
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
            "Track unsubscribed:",
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
            "LiveKit disconnected:",
            reason
          );

          // The audio elements go too - otherwise dead <audio> tags
          // pile up on the page.
          removeAudioElements();

          setRoom(null);
          setSessionId(null);
          setIsConnected(false);
          setIsPaused(false);
          setHandoff(null);

          // Whatever ended the call - server, network or admin -
          // the user must at least know that it is over.
          setEndedNotice(
            (current) =>
              current || "The call has ended."
          );
        }
      );

      // ========================================================
      // 23. CONNECT TO LIVEKIT
      // ========================================================

      console.log(
        "Connecting to LiveKit..."
      );

      console.log(
        "URL:",
        livekitUrl
      );

      console.log(
        "Token length:",
        livekitToken.length
      );

      await livekitRoom.connect(
        livekitUrl,
        livekitToken
      );

      console.log(
        "Connected to LiveKit room:",
        livekitRoom.name
      );

      // Check whoever is already inside as well - events only fire
      // for what happens after we join.
      livekitRoom.remoteParticipants.forEach(
        (participant) => {
          if (isAdminParticipant(participant)) {
            markHandoff("connected");
          }

          const state =
            participant.attributes?.[
              HANDOFF_ATTRIBUTE
            ];

          if (state) {
            markHandoff(state);
          }
        }
      );

      // ========================================================
      // 24. ENABLE MICROPHONE
      // ========================================================

      await livekitRoom.localParticipant.setMicrophoneEnabled(
        true
      );

      console.log(
        "Microphone enabled."
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
        "VOICE CALL CONNECTED"
      );

      console.log(
        "========================================"
      );

    } catch (err) {
      console.error(
        "========================================"
      );

      console.error(
        "ERROR CONNECTING TO LIVEKIT"
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
            "Microphone resumed."
          );
        } else {
          await room.localParticipant.setMicrophoneEnabled(
            false
          );

          setIsPaused(true);

          console.log(
            "Microphone paused."
          );
        }

      } catch (err) {
        console.error(
          "Error changing microphone state:",
          err
        );

        setError(
          err?.message ||
            "Could not change microphone state."
        );
      }
    };

  // ============================================================
  // AGENT NEVER SHOWED UP
  // ============================================================
  //
  // The room connected fine (the green "Connected" text above is
  // about that), but AgentVisualizer waited STUCK_AFTER_MS for the
  // AI to publish a track and it never did - the worker was likely
  // at its call limit, crashed on this session, or never received
  // it. Before this there was no feedback at all: the circle just
  // spun on "Connecting..." forever and the caller had no way to
  // know the call was actually going nowhere.
  //
  // useCallback keeps this function's identity stable across
  // renders - AgentVisualizer's effect depends on it, and without
  // this it would re-run (and restart the timer) on every render,
  // so the timeout would never actually fire.
  const handleAgentStuck = useCallback(() => {
    setError(AGENT_STUCK_MESSAGE);
  }, []);

  // The agent joined after all, just later than expected - drop the
  // warning above rather than leaving it next to a call that is now
  // actually working. Only clears OUR OWN message, so an unrelated
  // error (a microphone failure, say) is never wiped out from under
  // it.
  const handleAgentRecovered = useCallback(() => {
    setError((current) =>
      current === AGENT_STUCK_MESSAGE ? null : current
    );
  }, []);

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
          "Ending call..."
        );

        // ------------------------------------------------------
        // Disable microphone
        // ------------------------------------------------------

        try {
          await room.localParticipant.setMicrophoneEnabled(
            false
          );

          console.log(
            "Microphone disabled."
          );

        } catch (micError) {
          console.warn(
            "Could not disable microphone:",
            micError
          );
        }

        // ------------------------------------------------------
        // Disconnect
        // ------------------------------------------------------

        console.log(
          "Disconnecting frontend from LiveKit..."
        );

        await room.disconnect();

        console.log(
          "Frontend disconnected."
        );

        // ------------------------------------------------------
        // Tell the backend this session is over
        // ------------------------------------------------------
        //
        // Leaving the LiveKit room only ends the audio - it does not
        // touch the session row in the database. Without this the
        // worker was the only thing that could close it, and only
        // after its own 10-second grace period, so "My Calls" kept
        // showing "active" for a while after a call the user had
        // already ended. This closes it the moment the button is
        // pressed instead of waiting on the worker.
        //
        // Best-effort: if this fails (a dropped connection, say),
        // the worker's own teardown still closes the session a few
        // seconds later, so the call does not hang open forever
        // either way.
        if (sessionId) {
          try {
            const API_BASE_URL =
              process.env.NEXT_PUBLIC_API_URL ||
              "http://localhost:9000";

            const accessToken = getAccessToken();

            await fetch(
              `${API_BASE_URL}/livekit/sessions/${sessionId}/close`,
              {
                method: "PATCH",
                headers: accessToken
                  ? { Authorization: `Bearer ${accessToken}` }
                  : {},
              }
            );

            console.log(
              "Session closed on the server."
            );
          } catch (closeError) {
            console.warn(
              "Could not close the session on the server - the worker will close it shortly:",
              closeError
            );
          }
        }

        // ------------------------------------------------------
        // Remove audio elements
        // ------------------------------------------------------

        removeAudioElements();

        // ------------------------------------------------------
        // Reset state
        // ------------------------------------------------------

        setRoom(null);
        setSessionId(null);
        setIsConnected(false);
        setIsPaused(false);
        setHandoff(null);

        setEndedNotice(
          "You ended the call."
        );

        console.log(
          "Call ended successfully."
        );

      } catch (err) {
        console.error(
          "Error ending call:",
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
            While a call is running, LiveKit's own visualizer - it
            moves to the agent's REAL audio. The room already exists
            here, so it only has to be passed down through
            RoomContext; useVoiceAssistant() picks the agent and its
            track up from there.

            A framer-motion pulse used to run here unconditionally
            (scale 1 -> 1.08 -> 1). It was not tied to the audio at
            all - the circle looked exactly the same whether the
            agent was speaking or silent.
          */}
          {isConnected && room ? (

            <div
              id="voice-assistant-demo"
              className="assistant-speaker-float relative mt-10"
            >
              <RoomContext.Provider value={room}>
                <AgentVisualizer
                  handoff={handoff}
                  onStuck={handleAgentStuck}
                  onRecovered={handleAgentRecovered}
                />
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
          {/* CALL KHATAM                                        */}
          {/* ================================================== */}

          {/*
            The call has ended. The screen is back to its starting
            state - the mic circle, no Pause/End Call, no Room or
            Session id. Just this one line saying what happened, and
            the mic can be pressed again.
          */}
          {!isConnected &&
            !isConnecting &&
            endedNotice && (
              <div className="mt-5 flex flex-col items-center gap-1">

                <p className="text-sm text-text-secondary">
                  {endedNotice}
                </p>

                <p className="text-xs text-text-secondary/70">
                  Tap the microphone to start a new call.
                </p>

              </div>
            )}

          {/* ================================================== */}
          {/* CONNECTED */}
          {/* ================================================== */}

          {isConnected &&
            room && (
              <div className="mt-5">

                {/*
                  The state has to be visible during a handoff. The
                  AI has gone quiet and the admin has not arrived
                  yet - with nothing on screen the user assumes the
                  call has dropped and hangs up.
                */}
                {HANDOFF_TEXT[handoff] ? (
                  <p
                    className={
                      HANDOFF_TEXT[handoff]
                        .className
                    }
                  >
                    {
                      HANDOFF_TEXT[handoff]
                        .text
                    }
                  </p>
                ) : (
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
                )}

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