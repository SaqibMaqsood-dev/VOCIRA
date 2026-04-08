"use client";

import { motion } from "framer-motion";
import { Mic } from "lucide-react";

export default function AssistantPage() {
  return (
    <div className="page-shell !max-w-none !px-0 !py-0">
      <section className="relative mx-auto flex min-h-[calc(100vh-4rem-2.5rem)] w-full items-center justify-center overflow-hidden bg-transparent">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(139,233,253,0.12),transparent_55%)]" />

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, ease: "easeOut" }}
          className="relative z-10 mx-auto flex w-full max-w-6xl flex-col items-center justify-center px-4 py-0 text-center sm:px-6"
        >
          <h1 className="max-w-5xl text-3xl font-semibold leading-[1.1] tracking-[-0.02em] text-text-primary sm:text-5xl">
            Create the most realistic speech
            <br />
            with our AI audio platform
          </h1>

          <p className="mt-4 max-w-3xl text-sm text-text-secondary sm:text-base">
            Pioneering research in Text to Speech, AI Voice Generator, and more
          </p>

          <a
            href="/assistant#voice-assistant-demo"
            className="assistant-speaker-link relative mt-8 block sm:mt-10"
            aria-label="Go to voice assistant demo section"
          >
            <div id="voice-assistant-demo" className="assistant-speaker-float relative flex h-[290px] w-[290px] items-center justify-center">
              <div className="assistant-speaker-device relative flex h-[290px] w-[290px] items-center justify-center">
                <div className="assistant-speaker-outer absolute h-[250px] w-[250px] rounded-full border border-white/20 bg-white/5 shadow-[0_0_0_20px_rgba(139,233,253,0.08)] backdrop-blur-md" />
                <div className="assistant-speaker-inner absolute h-[220px] w-[220px] rounded-full bg-[radial-gradient(circle,rgba(108,99,255,0.28)_0%,rgba(108,99,255,0.12)_46%,rgba(139,233,253,0.1)_70%,transparent_100%)]" />
                <motion.div
                  className="assistant-speaker-ring absolute h-[205px] w-[205px] rounded-full"
                  animate={{ rotate: 360 }}
                  transition={{ duration: 16, repeat: Infinity, ease: "linear" }}
                  style={{
                    background:
                      "conic-gradient(from 0deg, rgba(108,99,255,0.03), rgba(108,99,255,0.2), rgba(139,233,253,0.28), rgba(108,99,255,0.03))"
                  }}
                />

                <div className="assistant-mic-pulse pointer-events-none absolute left-1/2 top-1/2 h-12 w-12 -translate-x-1/2 -translate-y-1/2 rounded-full" />
                <motion.div
                  className="assistant-mic-core relative grid h-28 w-28 place-items-center rounded-full bg-gradient-to-b from-accent-primary/80 to-accent-secondary/85 text-white shadow-[0_14px_40px_rgba(108,99,255,0.35)]"
                  animate={{ scale: [1, 1.03, 1] }}
                  transition={{ duration: 3.2, repeat: Infinity, ease: "easeInOut" }}
                >
                  <Mic className="h-9 w-9" />
                </motion.div>
              </div>
            </div>
          </a>

        </motion.div>
      </section>
    </div>
  );
}

