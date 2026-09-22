"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import Lottie from "lottie-react";
import { cn } from "@/lib/utils";
import animationData from "@/public/lottie/robot-bot.json";

/**
 * The animated robot on the home page, replacing the hand-drawn
 * smart-speaker illustration. Same link target and sizing as
 * VoiceOrb had, so the layout around it needed no changes.
 */
export default function RobotBot({ className }) {
  return (
    <Link
      href="/assistant"
      aria-label="Open voice assistant demo"
      className={cn("relative grid place-items-center", className)}
    >
      <motion.div
        className="relative w-[260px] sm:w-[320px] lg:w-[380px]"
        initial={{ scale: 0.94, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 0.8, ease: [0.22, 0.61, 0.36, 1] }}
      >
        <div className="pointer-events-none absolute inset-0 -z-10 rounded-full bg-[radial-gradient(circle_at_50%_45%,rgba(139,233,253,0.22),rgba(108,99,255,0.12)_52%,transparent_75%)] blur-2xl" />
        <Lottie animationData={animationData} loop autoplay className="h-auto w-full" />
      </motion.div>
    </Link>
  );
}
