"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import Lottie from "lottie-react";
import { cn } from "@/lib/utils";
import animationData from "@/public/lottie/robot-bot.json";

/**
 * The animated robot on the home page, replacing the hand-drawn
 * smart-speaker illustration. Same link target and sizing as
 * VoiceOrb had, so the layout around it needed no changes.
 *
 * `src` swaps in another animation from /public, loaded when the page
 * shows it rather than bundled - Vocira's own site uses a larger one.
 */
export default function RobotBot({ className, href = "/assistant", label = "Open voice assistant demo", src = null }) {
  const [loaded, setLoaded] = useState(null);

  useEffect(() => {
    if (!src) return;
    let cancelled = false;
    fetch(src)
      .then((response) => (response.ok ? response.json() : null))
      .then((data) => !cancelled && setLoaded(data))
      .catch(() => {
        /* the space stays empty - the page works without the robot */
      });
    return () => {
      cancelled = true;
    };
  }, [src]);

  const data = src ? loaded : animationData;

  return (
    <Link
      href={href}
      aria-label={label}
      className={cn("relative grid place-items-center", className)}
    >
      <motion.div
        // Vocira's robot sits small in its canvas, so it gets more room
        className={cn("relative", src ? "w-[300px] sm:w-[420px] lg:w-[520px]" : "w-[260px] sm:w-[320px] lg:w-[380px]")}
        initial={{ scale: 0.94, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 0.8, ease: [0.22, 0.61, 0.36, 1] }}
      >
        <div className="pointer-events-none absolute inset-0 -z-10 rounded-full bg-[radial-gradient(circle_at_50%_45%,rgba(139,233,253,0.22),rgba(108,99,255,0.12)_52%,transparent_75%)] blur-2xl" />
        {data ? (
          <Lottie animationData={data} loop autoplay className="h-auto w-full" />
        ) : (
          // holds the robot's place while it loads, so nothing jumps
          <div className="aspect-square w-full" />
        )}
      </motion.div>
    </Link>
  );
}
