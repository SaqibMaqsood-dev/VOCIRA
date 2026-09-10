"use client";

/**
 * Stat tile - a single number, which is what a dashboard is for.
 *
 * The dataviz rule: do not build a chart for one current value,
 * build a tile. These four cards used to be a small label and a
 * number; the number is now large (it is the thing being read), with
 * an icon and - wherever there is data over time - a sparkline.
 *
 * The contract: label (sentence case) - value (large) - optional
 * icon, sparkline, and a short note.
 */

import { motion, useReducedMotion } from "framer-motion";

const SERIES = "#6c63ff";

export default function StatTile({
  label,
  value,
  hint,
  icon: Icon,
  spark,
  accent = SERIES,
  loading = false,
}) {
  return (
    <div className="group relative overflow-hidden rounded-2xl border border-white/10 bg-white/[0.03] p-5 shadow-card backdrop-blur-xl transition-colors hover:border-white/20">
      {/* a soft glow - decoration only, not data */}
      <div
        className="pointer-events-none absolute -right-8 -top-10 h-28 w-28 rounded-full opacity-25 blur-2xl transition-opacity group-hover:opacity-40"
        style={{ background: accent }}
      />

      <div className="relative flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-[11px] font-medium uppercase tracking-[0.14em] text-text-secondary">
            {label}
          </p>

          <p className="mt-2 text-3xl font-semibold leading-none text-white">
            {loading ? (
              <span className="inline-block h-8 w-16 animate-pulse rounded bg-white/10" />
            ) : (
              value
            )}
          </p>

          {hint && (
            <p className="mt-2 text-[11px] text-text-secondary">{hint}</p>
          )}
        </div>

        {Icon && (
          <span
            className="grid h-9 w-9 shrink-0 place-items-center rounded-xl border border-white/10"
            style={{ background: `${accent}1f`, color: accent }}
          >
            <Icon className="h-4 w-4" />
          </span>
        )}
      </div>

      {spark && spark.length > 1 && (
        <Sparkline values={spark} color={accent} />
      )}
    </div>
  );
}

/** A small line - it shows the shape, not the numbers. */
function Sparkline({ values, color }) {
  const still = useReducedMotion();
  const W = 200;
  const H = 28;
  const max = Math.max(1, ...values);

  const pts = values.map((v, i) => ({
    x: values.length === 1 ? W / 2 : (i / (values.length - 1)) * W,
    y: H - (v / max) * (H - 4) - 2,
  }));

  const d = pts.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x} ${p.y}`).join(" ");
  const last = pts[pts.length - 1];

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="mt-4 w-full"
      style={{ height: H }}
      aria-hidden="true"
    >
      <motion.path
        d={d}
        fill="none"
        stroke={color}
        strokeWidth="2"
        strokeLinejoin="round"
        strokeLinecap="round"
        opacity="0.85"
        initial={still ? false : { pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={{ duration: 0.9, ease: "easeInOut" }}
      />
      <motion.circle
        cx={last.x}
        cy={last.y}
        r="3"
        fill={color}
        initial={still ? false : { scale: 0, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 0.3, delay: 0.85 }}
      />
    </svg>
  );
}
