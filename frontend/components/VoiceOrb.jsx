"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

export default function VoiceOrb({ className }) {
  return (
    <Link
      href="/assistant"
      aria-label="Open voice assistant demo"
      className={cn("ai-speaker-link relative grid place-items-center", className)}
    >
      <motion.div
        className="ai-speaker-visual relative w-[260px] sm:w-[320px] lg:w-[380px]"
        initial={{ scale: 0.94, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 0.8, ease: [0.22, 0.61, 0.36, 1] }}
      >
        <motion.svg
          viewBox="0 0 620 620"
          className="h-auto w-full drop-shadow-[0_18px_50px_rgba(108,99,255,0.28)]"
        >
          <defs>
            <radialGradient id="bgGlow" cx="52%" cy="38%" r="62%">
              <stop offset="0%" stopColor="#8BE9FD" stopOpacity="0.35" />
              <stop offset="46%" stopColor="#6C63FF" stopOpacity="0.26" />
              <stop offset="100%" stopColor="#100944" stopOpacity="0" />
            </radialGradient>
            <linearGradient id="speakerBody" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#6C63FF" stopOpacity="0.92" />
              <stop offset="45%" stopColor="#8f74ff" stopOpacity="0.9" />
              <stop offset="72%" stopColor="#8BE9FD" stopOpacity="0.85" />
              <stop offset="100%" stopColor="#5b4ed6" stopOpacity="0.96" />
            </linearGradient>
            <linearGradient id="topFace" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#0f1f4b" />
              <stop offset="100%" stopColor="#051129" />
            </linearGradient>
            <linearGradient id="grille" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#11143d" />
              <stop offset="60%" stopColor="#1a2352" />
              <stop offset="100%" stopColor="#0b1539" />
            </linearGradient>
            <radialGradient id="micCore" cx="50%" cy="45%" r="60%">
              <stop offset="0%" stopColor="#ffffff" stopOpacity="0.98" />
              <stop offset="72%" stopColor="#8BE9FD" stopOpacity="0.88" />
              <stop offset="100%" stopColor="#6C63FF" stopOpacity="0.7" />
            </radialGradient>
            <pattern id="grillePattern" width="8" height="8" patternUnits="userSpaceOnUse">
              <circle cx="2" cy="2" r="1.2" fill="#26316b" />
            </pattern>
          </defs>

          <circle cx="310" cy="280" r="250" fill="url(#bgGlow)" />

          <g opacity="0.45">
            <rect x="120" y="130" width="3" height="190" rx="2" fill="#8BE9FD" />
            <rect x="175" y="215" width="3" height="105" rx="2" fill="#8BE9FD" />
            <rect x="520" y="145" width="3" height="165" rx="2" fill="#8BE9FD" />
            <rect x="460" y="195" width="3" height="120" rx="2" fill="#8BE9FD" />
          </g>

          <ellipse cx="310" cy="500" rx="165" ry="38" fill="none" stroke="#8BE9FD" strokeOpacity="0.36" strokeWidth="4" />
          <ellipse cx="310" cy="500" rx="205" ry="52" fill="none" stroke="#6C63FF" strokeOpacity="0.26" strokeWidth="4" />
          <ellipse cx="310" cy="500" rx="245" ry="66" fill="none" stroke="#8BE9FD" strokeOpacity="0.16" strokeWidth="4" />

          <ellipse cx="310" cy="195" rx="110" ry="40" fill="url(#topFace)" />
          <rect x="200" y="195" width="220" height="265" rx="24" fill="url(#speakerBody)" />
          <ellipse cx="310" cy="460" rx="110" ry="36" fill="#091131" />
          <ellipse cx="310" cy="195" rx="110" ry="40" fill="none" stroke="#8BE9FD" strokeOpacity="0.3" strokeWidth="3" />

          <rect x="200" y="330" width="220" height="85" rx="16" fill="url(#grille)" />
          <rect x="210" y="340" width="200" height="65" rx="12" fill="url(#grillePattern)" opacity="0.8" />
          <line x1="205" y1="410" x2="415" y2="410" stroke="#6C63FF" strokeOpacity="0.8" strokeWidth="3" />
          <line x1="205" y1="455" x2="415" y2="455" stroke="#8BE9FD" strokeOpacity="0.85" strokeWidth="3" />

          <g>
            <circle cx="310" cy="285" r="38" fill="url(#micCore)" opacity="0.96" />
            <path
              d="M310 267c-7 0-13 6-13 13v16c0 7 6 13 13 13s13-6 13-13v-16c0-7-6-13-13-13Zm-20 26a2 2 0 0 1 4 0c0 9 7 16 16 16s16-7 16-16a2 2 0 1 1 4 0c0 10-7 18-17 20v7h9a2 2 0 1 1 0 4h-24a2 2 0 1 1 0-4h9v-7c-10-2-17-10-17-20Z"
              fill="#ffffff"
              fillOpacity="0.94"
            />
            <path d="M276 286q-9 10 0 20" fill="none" stroke="#8BE9FD" strokeOpacity="0.8" strokeWidth="3" strokeLinecap="round" />
            <path d="M344 286q9 10 0 20" fill="none" stroke="#8BE9FD" strokeOpacity="0.8" strokeWidth="3" strokeLinecap="round" />
          </g>

          <circle cx="250" cy="183" r="11" fill="#77c8ff" fillOpacity="0.65" />
          <circle cx="310" cy="176" r="11" fill="#8BE9FD" fillOpacity="0.42" />
          <circle cx="370" cy="183" r="11" fill="#77c8ff" fillOpacity="0.65" />
        </motion.svg>

        <motion.div
          className="ai-speaker-ambient pointer-events-none absolute inset-0 rounded-full"
          animate={{ opacity: [0.24, 0.4, 0.24] }}
          transition={{ duration: 3.8, repeat: Infinity, ease: "easeInOut" }}
          style={{
            background:
              "radial-gradient(circle at 50% 45%, rgba(139,233,253,0.16), rgba(108,99,255,0.08) 52%, transparent 75%)"
          }}
        />
        <span className="ai-mic-pulse pointer-events-none absolute left-1/2 top-[46%] h-12 w-12 -translate-x-1/2 -translate-y-1/2 rounded-full" />
      </motion.div>
    </Link>
  );
}

