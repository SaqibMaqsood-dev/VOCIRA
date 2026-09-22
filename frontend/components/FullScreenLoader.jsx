"use client";

import { motion } from "framer-motion";
import BrandLogo from "@/components/BrandLogo";

/**
 * A full-screen transition shown right after a successful login,
 * before the page.jsx redirects to /dashboard or /admin.
 *
 * Login used to jump straight from the button's small inline
 * spinner to a brand-new page with no visual continuity at all -
 * the screen just went blank for a moment and then something else
 * appeared. This gives that moment its own beat: the whole screen
 * takes over, the logo and a spinning ring confirm something is
 * happening, and only then does the redirect fire (page.jsx waits
 * ~1s before navigating away).
 */
export default function FullScreenLoader({
  label = "Signing you in…",
  subLabel = "Taking you to your dashboard",
}) {
  return (
    <motion.div
      role="status"
      aria-live="polite"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.28, ease: "easeOut" }}
      className="fixed inset-0 z-[100] grid place-items-center overflow-hidden bg-bg-primary"
    >
      {/* Same soft ambient glows the rest of the app uses, so this
          reads as a continuation of the page rather than a
          different screen entirely. */}
      <div className="pointer-events-none absolute -left-24 -top-16 size-72 rounded-full bg-accent-secondary/14 blur-3xl" />
      <div className="pointer-events-none absolute -bottom-20 -right-16 size-80 rounded-full bg-accent-primary/16 blur-3xl" />

      <motion.div
        initial={{ opacity: 0, y: 10, scale: 0.96 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.4, ease: "easeOut", delay: 0.05 }}
        className="relative flex flex-col items-center gap-6"
      >
        <div className="relative grid h-24 w-24 place-items-center">
          {/* Spinning gradient ring around the logo. A plain
              border-spinner would have worked, but the app already
              has a real brand mark - reusing it here is what makes
              this feel like Vocira loading, not a generic spinner. */}
          <motion.span
            aria-hidden="true"
            className="absolute inset-0 rounded-full"
            style={{
              background:
                "conic-gradient(from 0deg, #8BE9FD, #6C63FF, transparent 65%)",
              WebkitMask:
                "radial-gradient(farthest-side, transparent calc(100% - 3px), #000 calc(100% - 3px))",
              mask:
                "radial-gradient(farthest-side, transparent calc(100% - 3px), #000 calc(100% - 3px))",
            }}
            animate={{ rotate: 360 }}
            transition={{ duration: 1.1, repeat: Infinity, ease: "linear" }}
          />

          <span className="pointer-events-none absolute inset-2 rounded-full bg-accent-primary/15 blur-xl" />

          <div className="relative grid h-16 w-16 place-items-center rounded-2xl bg-white/[0.06] shadow-card backdrop-blur-xl">
            <BrandLogo variant="icon" className="h-9 w-9" />
          </div>
        </div>

        <div className="flex flex-col items-center gap-1.5">
          <p className="text-base font-semibold text-text-primary">
            {label}
          </p>
          <p className="text-sm text-text-secondary">
            {subLabel}
          </p>
        </div>
      </motion.div>
    </motion.div>
  );
}
