"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import VoiceOrb from "@/components/VoiceOrb";

export default function HomeHero() {
  return (
    <div className="page-shell flex items-center">
      <div className="grid w-full items-center gap-10 lg:grid-cols-2 lg:gap-12">
        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, ease: "easeOut" }}
        >
          <h1 className="text-balance text-3xl font-semibold tracking-tight text-text-primary sm:text-4xl lg:text-5xl">
            Get instant answers through real-time voice conversation.
          </h1>
          <p className="mt-5 max-w-xl text-pretty text-base leading-7 text-text-secondary sm:text-lg">
            Vocira AI assistant helps students and parents get school information
            instantly.
          </p>

          <div className="mt-8 space-y-3">
            <motion.div whileHover={{ y: -2 }} whileTap={{ scale: 0.98 }}>
              <Link href="/assistant" className="gradient-btn">
                <span className="relative">Go to Assistant</span>
              </Link>
            </motion.div>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: "easeOut", delay: 0.06 }}
          className="relative"
        >
          <VoiceOrb className="mx-auto" />
        </motion.div>
      </div>
    </div>
  );
}

