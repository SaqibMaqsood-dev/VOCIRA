"use client";

import { Mic } from "lucide-react";
import { motion } from "framer-motion";

export default function AssistantBlob() {
  return (
    <div className="relative flex items-center justify-center">
      <motion.div
        className="pointer-events-none absolute h-[380px] w-[380px] rounded-[999px] bg-accent-primary/35 blur-3xl"
        animate={{ opacity: [0.35, 0.75, 0.35], scale: [1, 1.05, 1] }}
        transition={{ duration: 9, repeat: Infinity, ease: "easeInOut" }}
      />

      <motion.div
        className="relative h-[280px] w-[280px]"
        initial={{ scale: 0.92, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 0.7, ease: [0.22, 0.61, 0.36, 1] }}
      >
        <motion.svg viewBox="0 0 260 260" className="h-full w-full">
          <defs>
            <radialGradient id="blobCore" cx="50%" cy="10%" r="80%">
              <stop offset="0%" stopColor="#8BE9FD" stopOpacity="0.7" />
              <stop offset="45%" stopColor="#6C63FF" stopOpacity="0.98" />
              <stop offset="100%" stopColor="#03041b" stopOpacity="1" />
            </radialGradient>
            <linearGradient id="blobStroke" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#8BE9FD" stopOpacity="0.85" />
              <stop offset="50%" stopColor="#6C63FF" stopOpacity="0.9" />
              <stop offset="100%" stopColor="#8BE9FD" stopOpacity="0.85" />
            </linearGradient>
            <filter id="blobGlow" x="-40%" y="-40%" width="180%" height="180%">
              <feGaussianBlur stdDeviation="16" result="blur" />
              <feColorMatrix
                in="blur"
                type="matrix"
                values="0 0 0 0 0.54 0 0 0 0 0.57 0 0 0 0 1 0 0 0 0.9 0"
              />
            </filter>
          </defs>

          <motion.path
            d="M130 20C165 22 204 40 224 74C244 108 246 154 224 188C202 222 163 244 130 242C97 240 60 216 40 184C20 152 16 112 32 80C48 48 95 18 130 20Z"
            fill="none"
            stroke="url(#blobStroke)"
            strokeWidth="2"
            filter="url(#blobGlow)"
            animate={{ opacity: [0.7, 1, 0.7] }}
            transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}
          />

          <motion.path
            d="M130 20C165 22 204 40 224 74C244 108 246 154 224 188C202 222 163 244 130 242C97 240 60 216 40 184C20 152 16 112 32 80C48 48 95 18 130 20Z"
            fill="url(#blobCore)"
            stroke="rgba(139,233,253,0.25)"
            strokeWidth="1"
            animate={{
              d: [
                "M130 20C165 22 204 40 224 74C244 108 246 154 224 188C202 222 163 244 130 242C97 240 60 216 40 184C20 152 16 112 32 80C48 48 95 18 130 20Z",
                "M130 18C168 18 210 38 230 74C250 110 246 156 224 190C202 224 162 246 126 244C90 242 54 218 36 182C18 146 16 108 34 74C52 40 92 18 130 18Z",
                "M130 24C162 26 198 46 216 76C234 106 242 148 226 182C210 216 174 240 138 242C102 244 64 228 44 194C24 160 18 120 32 86C46 52 98 22 130 24Z",
                "M130 20C165 22 204 40 224 74C244 108 246 154 224 188C202 222 163 244 130 242C97 240 60 216 40 184C20 152 16 112 32 80C48 48 95 18 130 20Z"
              ]
            }}
            transition={{ duration: 14, repeat: Infinity, ease: "easeInOut" }}
          />
        </motion.svg>

        <motion.div
          className="pointer-events-none absolute inset-[70px] overflow-hidden rounded-full"
          animate={{ opacity: [0.5, 0.9, 0.5] }}
          transition={{ duration: 7, repeat: Infinity, ease: "easeInOut" }}
        >
          <svg
            viewBox="0 0 260 80"
            className="absolute left-1/2 top-1/2 h-16 w-[260px] -translate-x-1/2 -translate-y-1/2"
          >
            <defs>
              <linearGradient id="assistantWaveMain" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#5f5bff" stopOpacity="0.1" />
                <stop offset="50%" stopColor="#9b6bff" stopOpacity="0.85" />
                <stop offset="100%" stopColor="#5f5bff" stopOpacity="0.1" />
              </linearGradient>
              <linearGradient id="assistantWaveSoft" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#5f5bff" stopOpacity="0.05" />
                <stop offset="50%" stopColor="#9b6bff" stopOpacity="0.4" />
                <stop offset="100%" stopColor="#5f5bff" stopOpacity="0.05" />
              </linearGradient>
            </defs>

            <motion.path
              fill="none"
              stroke="url(#assistantWaveSoft)"
              strokeWidth="1.4"
              strokeLinecap="round"
              initial={false}
              animate={{
                d: [
                  "M0 34 Q 32 28 64 34 T 128 34 T 192 34 T 260 34",
                  "M0 34 Q 32 24 64 34 T 128 42 T 192 30 T 260 34",
                  "M0 34 Q 32 30 64 34 T 128 28 T 192 38 T 260 34",
                  "M0 34 Q 32 28 64 34 T 128 34 T 192 34 T 260 34"
                ]
              }}
              transition={{ duration: 11, repeat: Infinity, ease: "easeInOut" }}
            />

            <motion.path
              fill="none"
              stroke="url(#assistantWaveMain)"
              strokeWidth="2"
              strokeLinecap="round"
              initial={false}
              animate={{
                d: [
                  "M0 40 Q 32 30 64 40 T 128 40 T 192 40 T 260 40",
                  "M0 40 Q 32 25 64 40 T 128 55 T 192 30 T 260 40",
                  "M0 40 Q 32 35 64 40 T 128 30 T 192 50 T 260 40",
                  "M0 40 Q 32 30 64 40 T 128 40 T 192 40 T 260 40"
                ]
              }}
              transition={{ duration: 9.5, repeat: Infinity, ease: "easeInOut" }}
            />

            <motion.path
              fill="none"
              stroke="url(#assistantWaveSoft)"
              strokeWidth="1.4"
              strokeLinecap="round"
              initial={false}
              animate={{
                d: [
                  "M0 46 Q 32 40 64 46 T 128 46 T 192 46 T 260 46",
                  "M0 46 Q 32 36 64 46 T 128 54 T 192 42 T 260 46",
                  "M0 46 Q 32 44 64 46 T 128 38 T 192 52 T 260 46",
                  "M0 46 Q 32 40 64 46 T 128 46 T 192 46 T 260 46"
                ]
              }}
              transition={{ duration: 12, repeat: Infinity, ease: "easeInOut" }}
            />
          </svg>
        </motion.div>

        <motion.div
          className="absolute left-1/2 top-1/2 grid h-16 w-16 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full bg-black/45 shadow-[0_0_30px_rgba(0,0,0,0.85)] ring-1 ring-white/10 backdrop-blur-xl"
          initial={{ opacity: 1, scale: 1 }}
          animate={{ opacity: 1, scale: [1, 1.06, 1] }}
          transition={{ duration: 3.4, ease: "easeInOut", repeat: Infinity }}
        >
          <Mic className="h-7 w-7 text-accent-secondary" />
        </motion.div>
      </motion.div>
    </div>
  );
}

