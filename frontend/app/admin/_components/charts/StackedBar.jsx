"use client";

/**
 * Part-to-whole - ek ufqi stacked bar.
 *
 * Do hisson ka pie nahi banaya: aankh do slices ka zaawiya theek se
 * nahi naap sakti, aur ye to do hi hisse hain. Ek bar mein poora
 * kul saaf nazar aata hai.
 *
 * Rang jaanche hue hain (dataviz validator, dark surface #05041c):
 *
 *   #6c63ff  violet   AI Resolved
 *   #d95926  orange   Escalated
 *   CVD separation ΔE 31.4 (protan) · normal 34.6 · dono >= 3:1
 *
 * Har hisse par seedha label bhi hai - pehchan sirf rang par nahi
 * chhori, aur legend bhi mojood hai.
 */

import { motion, useReducedMotion } from "framer-motion";

const SURFACE = "#05041c";

const COLORS = ["#6c63ff", "#d95926"];

export default function StackedBar({ data = [], height = 14 }) {
  const still = useReducedMotion();
  const total = data.reduce((sum, d) => sum + (Number(d.value) || 0), 0);

  if (!total) {
    return (
      <p className="py-6 text-center text-xs text-text-secondary">
        No data yet
      </p>
    );
  }

  return (
    <div>
      <div
        className="flex overflow-hidden rounded-full"
        style={{ height, background: "rgba(255,255,255,0.05)" }}
      >
        {data.map((d, i) => {
          const pct = ((Number(d.value) || 0) / total) * 100;
          if (pct <= 0) return null;
          return (
            <motion.div
              key={d.label}
              title={`${d.label}: ${d.value}%`}
              initial={still ? false : { width: 0 }}
              animate={{ width: `${pct}%` }}
              transition={{
                duration: 0.8,
                delay: 0.15 + i * 0.1,
                ease: [0.22, 1, 0.36, 1],
              }}
              // width sirf animate mein - style mein bhi rakhne se
              // dono takrate hain
              style={{
                background: COLORS[i % COLORS.length],
                // 2px surface gap - hisse aapas mein chipke na lagein
                marginRight:
                  i < data.length - 1 ? 2 : 0,
                boxShadow: `inset 0 0 0 0 ${SURFACE}`,
              }}
            />
          );
        })}
      </div>

      {/* Legend + seedhe labels. Text apne token pehnta hai; rang
          sirf us ke bagal wale nishaan mein hai. */}
      <div className="mt-4 space-y-2.5">
        {data.map((d, i) => (
          <div
            key={d.label}
            className="flex items-center justify-between gap-3"
          >
            <span className="flex items-center gap-2 text-xs text-text-secondary">
              <span
                className="inline-block h-2.5 w-2.5 rounded-sm"
                style={{ background: COLORS[i % COLORS.length] }}
              />
              {d.label}
            </span>
            <span className="text-xs font-semibold tabular-nums text-white">
              {d.value}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
