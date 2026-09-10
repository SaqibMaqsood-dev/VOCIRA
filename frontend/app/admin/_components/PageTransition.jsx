"use client";

/**
 * How admin pages come and go.
 *
 * The animation used to exist only on the dashboard (duration 0.4,
 * y 10) and not at all on the other three pages. So one page arrived
 * gently and the next snapped in - and returning to the dashboard
 * replayed that fade, which read as a flicker.
 *
 * Now it lives in one place, for all of them:
 *
 *   - NO exit animation. Fading the old page out leaves a moment of
 *     empty screen in between - that was the "fade in and out"
 *     jolt. The new page simply arrives gently.
 *
 *   - y of only 6px (it was 10) - a slight movement, not a jump.
 *
 *   - duration 0.45s with an ease-out curve, so it starts quickly
 *     and settles at the end. That feels softer than linear or
 *     easeOut.
 *
 * key={pathname} lets each page run its own entry.
 */

import { motion } from "framer-motion";
import { usePathname } from "next/navigation";

export default function PageTransition({ children }) {
  const pathname = usePathname();

  return (
    <motion.div
      key={pathname}
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{
        duration: 0.45,
        // easeOutQuint - speed at the start, softness at the end
        ease: [0.22, 1, 0.36, 1],
      }}
    >
      {children}
    </motion.div>
  );
}
