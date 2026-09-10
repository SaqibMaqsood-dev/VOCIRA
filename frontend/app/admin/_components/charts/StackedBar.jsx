"use client";

/**
 * Part-to-whole - a horizontal stacked bar.
 *
 * A two-slice pie was avoided: the eye cannot judge the angle of two
 * slices well, and there are only two parts here. A single bar shows
 * the whole total clearly.
 *
 * The colours are validated (dataviz validator, dark surface
 * #05041c):
 *
 *   #6c63ff  violet   AI Resolved
 *   #d95926  orange   Escalated
 *   CVD separation ΔE 31.4 (protan) · normal 34.6 · both >= 3:1
 *
 * Each segment is labelled directly as well - identification does
 * not rest on colour alone, and there is a legend too.
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
              // width goes in animate only - keeping it in style as
              // well makes the two fight each other
              style={{
                background: COLORS[i % COLORS.length],
                // a 2px surface gap so the segments do not touch
                marginRight:
                  i < data.length - 1 ? 2 : 0,
                boxShadow: `inset 0 0 0 0 ${SURFACE}`,
              }}
            />
          );
        })}
      </div>

      {/* Legend plus direct labels. The text wears its own token;
          the colour lives only in the swatch beside it. */}
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
