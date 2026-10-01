"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { motion } from "framer-motion";
import Lottie from "lottie-react";

// bundled, not fetched: a loader has to show the moment it appears
import loadingAnimation from "@/public/lottie/vocira-loading.json";

/**
 * Set by a layout whose frame stays on screen while a page's data loads
 * (the admin panel: AdminLayout). Inside it the loader fills only the
 * content area - the sidebar and header stay where they are, instead of
 * the whole screen going blank for every page.
 */
export const LoaderInFrame = createContext(false);

// Most pages have their data in a moment. Shown at once, the loader
// flashed for a split second on every page change; it now appears only
// once loading has taken this long.
const IN_FRAME_DELAY_MS = 300;

/**
 * A full-screen transition shown right after a successful login,
 * before the page.jsx redirects to /dashboard or /admin.
 *
 * Login used to jump straight from the button's small inline
 * spinner to a brand-new page with no visual continuity at all -
 * the screen just went blank for a moment and then something else
 * appeared. This gives that moment its own beat: the whole screen
 * takes over, Vocira's loading animation confirms something is
 * happening, and only then does the redirect fire (page.jsx waits
 * ~1s before navigating away). Pages show it while their data loads -
 * inside a LoaderInFrame, in their content area only.
 */
export default function FullScreenLoader({
  label = "Signing you in…",
  subLabel = "Taking you to your dashboard",
}) {
  const inFrame = useContext(LoaderInFrame);
  const [due, setDue] = useState(!inFrame);

  useEffect(() => {
    if (due) return undefined;
    const timer = setTimeout(() => setDue(true), IN_FRAME_DELAY_MS);
    return () => clearTimeout(timer);
  }, [due]);

  const content = (
    <motion.div
      // in the frame it appears as it is - no fade, nothing dims
      initial={inFrame ? false : { opacity: 0, y: 10, scale: 0.96 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.4, ease: "easeOut", delay: 0.05 }}
      className="relative flex flex-col items-center gap-6"
    >
      {/* Vocira's own loading animation (public/lottie/vocira-loading.json) */}
      <div aria-hidden="true" className="relative grid h-32 w-32 place-items-center">
        <span className="pointer-events-none absolute inset-4 rounded-full bg-accent-primary/15 blur-xl" />
        <Lottie animationData={loadingAnimation} loop autoplay className="relative h-full w-full" />
      </div>

      <div className="flex flex-col items-center gap-1.5 text-center">
        <p className="text-base font-semibold text-text-primary">
          {label}
        </p>
        <p className="text-sm text-text-secondary">
          {subLabel}
        </p>
      </div>
    </motion.div>
  );

  if (inFrame) {
    // the content area's own height: the screen less the header and the
    // frame's padding - held even before the loader is due, so nothing jumps
    return (
      <div role="status" aria-live="polite" className="grid min-h-[calc(100dvh-8rem)] place-items-center">
        {due && content}
      </div>
    );
  }

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

      {content}
    </motion.div>
  );
}
