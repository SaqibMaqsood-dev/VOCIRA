"use client";

/**
 * A handoff call to a person - the admin's side.
 *
 * The story: a parent was talking to the AI and says "put me
 * through to a person". The AI's voice stops, but the parent stays
 * in the same LiveKit room. It rings here for the admin; pressing
 * JOIN puts the admin into THAT SAME room and the AI slips quietly
 * away. The parent's call is never cut - only the voice in their ear
 * changes.
 *
 * On JOIN the browser sends nothing but escalation_id. The room
 * name, the session and the admin's identity are all decided by the
 * server from its own token. Sending an id from here would mean:
 * "walk into any room whose name you happen to know".
 *
 * If two admins press JOIN at once the server admits only one; the
 * other gets a 409 and their ringing stops on its own
 * (escalation.claimed).
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { Loader2, Mic, MicOff, PhoneCall, PhoneOff, X } from "lucide-react";

import { Room, RoomEvent, Track } from "livekit-client";

import { adminFetch } from "@/app/admin/useAdminApi";
import useAdminCalls from "@/app/admin/_components/useAdminCalls";

export default function IncomingCall() {
  const { calls, remove } = useAdminCalls();

  // Chal rahi call
  const [active, setActive] = useState(null);
  const [joiningId, setJoiningId] = useState(null);
  const [muted, setMuted] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [error, setError] = useState("");

  const audioRef = useRef(null);
  const roomRef = useRef(null);

  // ----------------------------------------------------------
  // Ring
  // ----------------------------------------------------------

  useEffect(() => {
    if (active || calls.length === 0) return;

    // A small beep - no audio file, the browser generates it. If
    // autoplay policy blocks it, we move on silently.
    const beep = () => {
      try {
        const Ctx = window.AudioContext || window.webkitAudioContext;
        if (!Ctx) return;
        const ctx = new Ctx();
        const now = ctx.currentTime;
        [0, 0.28].forEach((offset) => {
          const osc = ctx.createOscillator();
          const gain = ctx.createGain();
          osc.type = "sine";
          osc.frequency.value = 660;
          gain.gain.setValueAtTime(0.0001, now + offset);
          gain.gain.exponentialRampToValueAtTime(0.08, now + offset + 0.02);
          gain.gain.exponentialRampToValueAtTime(0.0001, now + offset + 0.2);
          osc.connect(gain).connect(ctx.destination);
          osc.start(now + offset);
          osc.stop(now + offset + 0.22);
        });
        setTimeout(() => ctx.close().catch(() => {}), 900);
      } catch {
        /* even with no sound, the card is still visible */
      }
    };

    beep();
    const id = setInterval(beep, 3200);
    return () => clearInterval(id);
  }, [calls.length, active]);

  // ----------------------------------------------------------
  // Call ka waqt
  // ----------------------------------------------------------

  useEffect(() => {
    if (!active) {
      setSeconds(0);
      return;
    }
    const id = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(id);
  }, [active]);

  // ----------------------------------------------------------
  // Safai
  // ----------------------------------------------------------

  const cleanupAudio = useCallback(() => {
    const element = audioRef.current;
    if (!element) return;
    try {
      element.pause();
      element.srcObject = null;
      element.remove();
    } catch {
      /* pehle hi ja chuka */
    }
    audioRef.current = null;
  }, []);

  const teardown = useCallback(async () => {
    const room = roomRef.current;
    roomRef.current = null;

    if (room) {
      try {
        await room.localParticipant.setMicrophoneEnabled(false);
      } catch {
        /* mic pehle hi band */
      }
      try {
        await room.disconnect();
      } catch {
        /* pehle hi nikal chuke */
      }
    }

    cleanupAudio();
    setActive(null);
    setMuted(false);
  }, [cleanupAudio]);

  // Whether the tab closes or the admin leaves the panel - do not
  // leave the mic open
  useEffect(
    () => () => {
      const room = roomRef.current;
      roomRef.current = null;
      if (room) room.disconnect().catch(() => {});
    },
    []
  );

  // ----------------------------------------------------------
  // JOIN
  // ----------------------------------------------------------

  async function join(call) {
    if (joiningId || active) return;

    setJoiningId(call.escalationId);
    setError("");

    try {
      // Mic permission FIRST. Discovering there is no mic after
      // joining the room leaves the parent in silence - and by then
      // the AI has already gone.
      try {
        const probe = await navigator.mediaDevices.getUserMedia({
          audio: true,
        });
        probe.getTracks().forEach((t) => t.stop());
      } catch {
        throw new Error(
          "Microphone access is blocked. Allow the microphone and try again."
        );
      }

      // escalation_id only - the server decides everything else.
      const data = await adminFetch("/livekit/admin/accept-call", {
        method: "POST",
        body: JSON.stringify({ escalation_id: call.escalationId }),
      });

      const livekitRoom = new Room({
        audioCaptureDefaults: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      livekitRoom.on(RoomEvent.TrackSubscribed, (track) => {
        if (track.kind !== Track.Kind.Audio) return;
        const element = track.attach();
        element.autoplay = true;
        element.setAttribute("playsinline", "true");
        element.style.display = "none";
        document.body.appendChild(element);
        audioRef.current = element;
        element.play().catch(() => {
          /* the browser blocked it - the admin will have to click
             on the page */
        });
      });

      livekitRoom.on(RoomEvent.ParticipantDisconnected, (participant) => {
        // The AI leaves by design - that is what a handoff is.
        // If the parent leaves, the call is over.
        const identity = String(participant.identity || "");
        if (identity.startsWith("agent")) return;

        setError("The caller hung up.");
        teardown();

        // The conversation happened - otherwise this escalation sits
        // 'open' forever because the admin never pressed END CALL.
        resolveEscalation(call.escalationId);
      });

      livekitRoom.on(RoomEvent.Disconnected, () => {
        cleanupAudio();
        roomRef.current = null;
        setActive(null);
      });

      await livekitRoom.connect(data.url, data.token);
      await livekitRoom.localParticipant.setMicrophoneEnabled(true);

      roomRef.current = livekitRoom;

      setActive({
        escalationId: call.escalationId,
        sessionId: data.session_id,
        room: data.room,
        question: call.question,
        caller: call.caller,
      });

      remove(call.escalationId);
    } catch (err) {
      // 409 = another admin got there first. There is no point
      // keeping this one ringing.
      if (err.status === 409) {
        remove(call.escalationId);
      }
      setError(err.message || "Could not join the call.");
    } finally {
      setJoiningId(null);
    }
  }

  // ----------------------------------------------------------
  // END
  // ----------------------------------------------------------

  async function hangUp() {
    const escalationId = active?.escalationId;
    await teardown();
    await resolveEscalation(escalationId);
  }

  async function toggleMute() {
    const room = roomRef.current;
    if (!room) return;
    const next = !muted;
    try {
      await room.localParticipant.setMicrophoneEnabled(!next);
      setMuted(next);
    } catch {
      setError("Could not change the microphone.");
    }
  }

  const onScreen = Boolean(active) || calls.length > 0;

  // The PWA's "Install Vocira" card also appears in the bottom right
  // corner (z-60). It and this one were printing over each other. It
  // hides itself during a call - this is what tells it to.
  useEffect(() => {
    window.dispatchEvent(
      new CustomEvent("vocira-call", { detail: onScreen })
    );
    return () => {
      window.dispatchEvent(
        new CustomEvent("vocira-call", { detail: false })
      );
    };
  }, [onScreen]);

  if (!onScreen && !error) return null;

  return (
    <div
      data-testid="admin-calls"
      className="pointer-events-none fixed bottom-4 right-4 z-[70] flex w-[min(22rem,calc(100vw-2rem))] flex-col gap-3"
    >
      {error && (
        <div className="pointer-events-auto flex items-start gap-2 rounded-2xl border border-amber-400/30 bg-[#0b0a2a]/95 px-3 py-2.5 text-[11px] text-amber-200 shadow-2xl backdrop-blur-xl">
          <span className="flex-1">{error}</span>
          <button
            type="button"
            onClick={() => setError("")}
            className="text-amber-200/70 hover:text-amber-100"
            aria-label="Dismiss message"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {active ? (
        <div
          data-testid="active-call"
          className="pointer-events-auto rounded-2xl border border-emerald-400/30 bg-[#0b0a2a]/95 p-4 shadow-2xl backdrop-blur-xl"
        >
          <div className="flex items-center gap-2">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400/70" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-400" />
            </span>
            <p className="text-xs font-semibold text-white">
              On a call with {active.caller}
            </p>
            <span className="ml-auto font-mono text-[11px] tabular-nums text-text-secondary">
              {formatDuration(seconds)}
            </span>
          </div>

          <p className="mt-2 line-clamp-3 text-[11px] leading-relaxed text-text-secondary">
            {active.question}
          </p>

          <div className="mt-3 flex items-center gap-2">
            <button
              type="button"
              onClick={toggleMute}
              className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-xl border border-white/10 bg-white/[0.06] px-3 py-2 text-xs font-semibold text-text-secondary transition-colors hover:bg-white/[0.12] hover:text-white"
            >
              {muted ? (
                <>
                  <MicOff className="h-3.5 w-3.5" /> Unmute
                </>
              ) : (
                <>
                  <Mic className="h-3.5 w-3.5" /> Mute
                </>
              )}
            </button>

            <button
              type="button"
              data-testid="end-call"
              onClick={hangUp}
              className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-xl bg-red-500/90 px-3 py-2 text-xs font-semibold text-white transition-colors hover:bg-red-500"
            >
              <PhoneOff className="h-3.5 w-3.5" /> End call
            </button>
          </div>
        </div>
      ) : (
        calls.map((call) => (
          <div
            key={call.escalationId}
            data-testid="incoming-call"
            data-escalation={call.escalationId}
            className="pointer-events-auto rounded-2xl border border-accent-primary/40 bg-[#0b0a2a]/95 p-4 shadow-2xl backdrop-blur-xl"
          >
            <div className="flex items-center gap-2">
              <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-accent-primary/20 text-accent-secondary">
                <PhoneCall className="h-4 w-4 animate-pulse" />
              </span>
              <div className="min-w-0">
                <p className="truncate text-xs font-semibold text-white">
                  {call.caller} wants a human
                </p>
                <p className="text-[10px] text-text-secondary">
                  Session {String(call.sessionId).slice(0, 8)}
                </p>
              </div>
              <button
                type="button"
                onClick={() => remove(call.escalationId)}
                className="ml-auto shrink-0 text-text-secondary/70 hover:text-white"
                aria-label="Dismiss call"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>

            <p className="mt-2 line-clamp-3 text-[11px] leading-relaxed text-text-secondary">
              {call.question}
            </p>

            <button
              type="button"
              data-testid="join-call"
              disabled={Boolean(joiningId)}
              onClick={() => join(call)}
              className="mt-3 inline-flex w-full items-center justify-center gap-1.5 rounded-xl bg-emerald-500 px-3 py-2 text-xs font-semibold text-[#05041c] transition-colors hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {joiningId === call.escalationId ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" /> Joining
                </>
              ) : (
                <>
                  <PhoneCall className="h-3.5 w-3.5" /> Join call
                </>
              )}
            </button>
          </div>
        ))
      )}
    </div>
  );
}

/**
 * The conversation happened - do not leave the escalation open.
 *
 * A call ends in two ways: the admin presses END CALL, or the caller
 * hangs up. The status has to change either way, or it sits 'open'
 * forever on the Escalations page.
 */
async function resolveEscalation(escalationId) {
  if (!escalationId) return;

  try {
    await adminFetch(
      `/livekit/admin/escalations/${escalationId}/status?new_status=resolved`,
      { method: "PATCH" }
    );
  } catch {
    // The call did happen; the status can be changed from the
    // Escalations page
  }
}

/** 95 -> "1:35" */
function formatDuration(total) {
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}
