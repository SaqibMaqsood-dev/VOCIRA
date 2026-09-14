"use client";

/**
 * The agent's real audio visualizer.
 *
 * The circle on /assistant used to be nothing but a fake
 * framer-motion pulse - scale 1 -> 1.08 -> 1, always identical.
 * Whether the agent was speaking or silent, it looked the same.
 *
 * It now uses LiveKit's own components (@livekit/components-react):
 *
 *   BarVisualizer    builds the waveform from the real audio track,
 *                    and changes style according to the state
 *   useRemoteParticipants / useParticipantTracks / useParticipantAttributes
 *                    the agent, its mic track, and its state
 *
 * WHY THE AGENT IS FOUND BY IDENTITY
 *
 * LiveKit's own useVoiceAssistant() identifies the agent by
 * ParticipantKind.AGENT. That kind is only assigned through the
 * LiveKit Agents framework - our worker is our own, and despite
 * agent=true in the token it keeps the standard kind (measured:
 * kind 0, where 4 was needed). So the agent is found here by its
 * identity, "agent". The visualizer is still LiveKit's own - only
 * the way the track is selected is ours.
 *
 * The state comes from the backend: voice_pipeline sets the
 * "lk.agent.state" attribute at every turn - the same key the
 * LiveKit Agents SDK uses.
 */

import { useEffect, useRef } from "react";

import {
  BarVisualizer,
  useParticipantAttributes,
  useParticipantTracks,
  useRemoteParticipants,
} from "@livekit/components-react";
import { Track } from "livekit-client";
import { Mic } from "lucide-react";

import { isAdminParticipant } from "@/lib/handoff";

const AGENT_IDENTITY = "agent";
const STATE_KEY = "lk.agent.state";

/*
 * How long the circle is allowed to sit on "Connecting..." before we
 * tell the caller something is wrong.
 *
 * The agent normally joins within a second or two of the room being
 * created. Without this timer, a caller whose agent never showed up
 * (the worker was at its concurrency limit, crashed on this call, or
 * the RabbitMQ message never arrived) saw nothing but a spinning
 * circle forever - no error, no hint to hang up and try again.
 */
const STUCK_AFTER_MS = 20_000;

const STATE_LABEL = {
  connecting: "Connecting…",
  initializing: "Getting ready…",
  listening: "Listening",
  thinking: "Thinking…",
  speaking: "Speaking",
  failed: "Connection failed",
};

const STATE_COLOR = {
  listening: "text-cyan-300",
  thinking: "text-amber-300",
  speaking: "text-emerald-300",
  failed: "text-red-400",
};

/**
 * handoff  null | "requested" | "connected" | "no_answer"
 *
 * When a call passes to a person, the AI leaves the room entirely.
 * After that no participant named "agent" remains here - which is
 * why the circle used to stay stuck on "Connecting…" forever, even
 * though the line below it clearly said a person was on the call.
 *
 * During a handoff the waveform is now built from the ADMIN's audio,
 * and the line below is written by the page itself.
 */
export default function AgentVisualizer({
  handoff = null,
  onStuck,
  onRecovered,
}) {
  const participants = useRemoteParticipants();

  const agent = participants.find((p) => p.identity === AGENT_IDENTITY);
  const human = participants.find(isAdminParticipant);

  // Once a person has joined, they are the one speaking
  const speaker = human || agent;

  const tracks = useParticipantTracks(
    [Track.Source.Microphone],
    speaker?.identity
  );

  const { attributes } = useParticipantAttributes({ participant: speaker });

  const agentTrack = tracks[0];

  // Only the AI publishes "lk.agent.state". For a person the bars
  // follow their real audio, so "speaking" directly.
  const state = human
    ? "speaking"
    : attributes?.[STATE_KEY] || "connecting";

  const waiting = !speaker || !agentTrack;

  /*
   * A handoff is its own, expected kind of "waiting" - the AI has
   * left on purpose and the page already says so. Only a caller
   * stuck waiting for the AI itself, with no handoff in progress,
   * counts as stuck.
   */
  const stuckTimer = useRef(null);
  const hasFiredStuck = useRef(false);

  useEffect(() => {
    if (waiting && !handoff && onStuck) {
      stuckTimer.current = setTimeout(() => {
        hasFiredStuck.current = true;
        onStuck();
      }, STUCK_AFTER_MS);
    } else if (!waiting && hasFiredStuck.current) {
      // The agent showed up late, after we already warned the
      // caller. Let the page clear that warning instead of leaving
      // a stale "did not join" message next to a working call.
      hasFiredStuck.current = false;
      onRecovered?.();
    }

    return () => {
      if (stuckTimer.current) {
        clearTimeout(stuckTimer.current);
        stuckTimer.current = null;
      }
    };
  }, [waiting, handoff, onStuck, onRecovered]);

  // During a handoff the page states the status itself ("Connecting
  // you to a human agent…" / "You are speaking with a human agent"),
  // so do not repeat it here.
  const label = handoff ? null : STATE_LABEL[state];

  return (
    <div className="flex flex-col items-center">
      <div className="relative grid h-[290px] w-[290px] place-items-center">
        <div className="absolute h-[250px] w-[250px] rounded-full border border-white/20 bg-white/5 shadow-[0_0_0_20px_rgba(139,233,253,0.08)] backdrop-blur-md" />

        {/* Bolte waqt daire ke gird halka sa glow */}
        <div
          className={`absolute h-[250px] w-[250px] rounded-full transition-all duration-500 ${
            state === "speaking"
              ? "shadow-[0_0_60px_12px_rgba(139,233,253,0.25)]"
              : state === "listening"
                ? "shadow-[0_0_40px_6px_rgba(108,99,255,0.18)]"
                : ""
          }`}
        />

        {waiting ? (
          <div className="relative grid h-28 w-28 place-items-center rounded-full bg-gradient-to-b from-accent-primary/80 to-accent-secondary/85 text-white shadow-[0_14px_40px_rgba(108,99,255,0.35)]">
            <Mic className="h-9 w-9" />
          </div>
        ) : (
          <BarVisualizer
            state={state}
            barCount={7}
            trackRef={agentTrack}
            options={{ minHeight: 8 }}
            className="agent-visualizer relative flex h-32 w-40 items-center justify-center gap-1.5"
          />
        )}
      </div>

      {label && (
        <p
          className={`mt-4 text-sm tracking-wide ${
            STATE_COLOR[state] || "text-text-secondary"
          }`}
        >
          {label}
        </p>
      )}
    </div>
  );
}
