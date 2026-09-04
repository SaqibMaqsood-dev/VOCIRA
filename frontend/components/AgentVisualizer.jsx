"use client";

/**
 * Agent ka asli audio visualizer.
 *
 * Pehle /assistant par jo daira tha wo sirf framer-motion ka jhoota
 * pulse tha - scale 1 -> 1.08 -> 1, hamesha ek jaisa. Agent bol raha
 * ho ya chup ho, dikhne mein koi farq nahi parta tha.
 *
 * Ab LiveKit ke apne components chalte hain (@livekit/components-react):
 *
 *   BarVisualizer    asli audio track se lehrein banata hai, aur
 *                    state ke hisab se andaz badalta hai
 *   useRemoteParticipants / useParticipantTracks / useParticipantAttributes
 *                    agent, us ka mic track, aur us ki haalat
 *
 * AGENT KYUN IDENTITY SE DHOONDA JATA HAI
 *
 * LiveKit ka apna useVoiceAssistant() agent ko ParticipantKind.AGENT
 * se pehchanta hai. Wo kind sirf LiveKit Agents framework ke zariye
 * milta hai - hamara worker apna hai, wo token mein agent=true hone
 * ke bawajood standard kind hi rehta hai (naapa gaya: kind 0, chahiye
 * tha 4). Is liye agent yahan apni identity "agent" se dhoonda jata
 * hai. Visualizer phir bhi LiveKit ka apna hai - sirf track chunne
 * ka tareeqa hamara hai.
 *
 * Haalat backend se aati hai: voice_pipeline har mor par
 * "lk.agent.state" attribute set karta hai - wahi key jo LiveKit
 * Agents SDK use karta hai.
 */

import {
  BarVisualizer,
  useParticipantAttributes,
  useParticipantTracks,
  useRemoteParticipants,
} from "@livekit/components-react";
import { Track } from "livekit-client";
import { Mic } from "lucide-react";

const AGENT_IDENTITY = "agent";
const STATE_KEY = "lk.agent.state";

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

export default function AgentVisualizer() {
  const participants = useRemoteParticipants();
  const agent = participants.find((p) => p.identity === AGENT_IDENTITY);

  const tracks = useParticipantTracks(
    [Track.Source.Microphone],
    agent?.identity
  );

  const { attributes } = useParticipantAttributes({ participant: agent });

  const agentTrack = tracks[0];
  const state = attributes?.[STATE_KEY] || (agent ? "connecting" : "connecting");
  const waiting = !agent || !agentTrack;

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

      {STATE_LABEL[state] && (
        <p
          className={`mt-4 text-sm tracking-wide ${
            STATE_COLOR[state] || "text-text-secondary"
          }`}
        >
          {STATE_LABEL[state]}
        </p>
      )}
    </div>
  );
}
