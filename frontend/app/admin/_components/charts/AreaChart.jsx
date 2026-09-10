"use client";

/**
 * One series over time - a line with a soft area fill.
 *
 * This used to be a bar chart made of divs: no axes, no grid, and no
 * way to tell how many questions came on a given day (only a hover
 * title attribute). The point is to read a trend, and a line/area is
 * the right form for that - bars are for comparing magnitudes.
 *
 * There is a single series, so there is no legend - the title says
 * what this is.
 *
 * Mark specs:
 *   line          2px, round join/cap
 *   end dot       r >= 4, 2px ring in the surface colour
 *   gridlines     1px solid, faint - never dashed
 */

import { motion, useReducedMotion } from "framer-motion";
import { useMemo, useState } from "react";

const SURFACE = "#05041c";
const SERIES = "#6c63ff";

const PAD = { top: 16, right: 16, bottom: 28, left: 40 };

export default function AreaChart({
  data = [],
  height = 200,
  valueKey = "value",
  labelKey = "day",
  formatValue = (v) => String(v),
}) {
  const [hover, setHover] = useState(null);

  // For anyone who asked the system for reduced motion, the chart
  // arrives fully drawn - the movement is decoration, not
  // information.
  const still = useReducedMotion();

  const W = 640; // viewBox width - the SVG itself is responsive
  const H = height;

  const plotW = W - PAD.left - PAD.right;
  const plotH = H - PAD.top - PAD.bottom;

  const { points, ticks, max } = useMemo(() => {
    const values = data.map((d) => Number(d[valueKey]) || 0);
    const rawMax = Math.max(1, ...values);

    // Y axis ko sundar ginti par khatam karein (10, 25, 50, 100...)
    const step = niceStep(rawMax / 3);
    const top = Math.ceil(rawMax / step) * step;

    const pts = data.map((d, i) => ({
      ...d,
      x: data.length === 1 ? plotW / 2 : (i / (data.length - 1)) * plotW,
      y: plotH - ((Number(d[valueKey]) || 0) / top) * plotH,
      value: Number(d[valueKey]) || 0,
    }));

    const tk = [];
    for (let v = 0; v <= top; v += step) {
      tk.push({ v, y: plotH - (v / top) * plotH });
    }

    return { points: pts, ticks: tk, max: top };
  }, [data, valueKey, plotW, plotH]);

  if (!data.length) {
    return (
      <div
        style={{ height }}
        className="grid place-items-center text-xs text-text-secondary"
      >
        No data yet
      </div>
    );
  }

  const linePath = points
    .map((p, i) => `${i === 0 ? "M" : "L"} ${p.x} ${p.y}`)
    .join(" ");

  const areaPath =
    `${linePath} L ${points[points.length - 1].x} ${plotH} ` +
    `L ${points[0].x} ${plotH} Z`;

  // Mouse kis nuqte ke sab se qareeb hai
  const onMove = (e) => {
    const box = e.currentTarget.getBoundingClientRect();
    const x = ((e.clientX - box.left) / box.width) * W - PAD.left;
    let nearest = points[0];
    for (const p of points) {
      if (Math.abs(p.x - x) < Math.abs(nearest.x - x)) nearest = p;
    }
    setHover(nearest);
  };

  return (
    <div className="relative">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        style={{ height }}
        onMouseMove={onMove}
        onMouseLeave={() => setHover(null)}
        role="img"
        aria-label="Questions per day over the last seven days"
      >
        <defs>
          <linearGradient id="area-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={SERIES} stopOpacity="0.34" />
            <stop offset="100%" stopColor={SERIES} stopOpacity="0.02" />
          </linearGradient>
        </defs>

        <g transform={`translate(${PAD.left},${PAD.top})`}>
          {/* gridlines - hairline, solid, recessive */}
          {ticks.map((t) => (
            <g key={t.v}>
              <line
                x1={0}
                y1={t.y}
                x2={plotW}
                y2={t.y}
                stroke="rgba(255,255,255,0.07)"
                strokeWidth="1"
              />
              <text
                x={-10}
                y={t.y + 4}
                textAnchor="end"
                className="fill-[rgba(255,255,255,0.42)] text-[11px]"
              >
                {t.v}
              </text>
            </g>
          ))}

          {/* The area rises from behind the line - the stroke draws
              first, then the fill arrives. The origin sits at the
              bottom of the plot so it grows up from the baseline. */}
          <motion.path
            d={areaPath}
            fill="url(#area-fill)"
            initial={still ? false : { opacity: 0, scaleY: 0.4 }}
            animate={{ opacity: 1, scaleY: 1 }}
            transition={{ duration: 0.7, delay: 0.35, ease: "easeOut" }}
            style={{ transformOrigin: `50% ${plotH}px` }}
          />

          {/* pathLength is framer-motion's own mechanism - it
              handles stroke-dasharray itself, so we never have to
              measure the path's length. */}
          <motion.path
            d={linePath}
            fill="none"
            stroke={SERIES}
            strokeWidth="2"
            strokeLinejoin="round"
            strokeLinecap="round"
            initial={still ? false : { pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={{ duration: 1.1, ease: "easeInOut" }}
          />

          {/* hover: crosshair + dot */}
          {hover && (
            <g>
              <line
                x1={hover.x}
                y1={0}
                x2={hover.x}
                y2={plotH}
                stroke="rgba(255,255,255,0.22)"
                strokeWidth="1"
              />
              <circle
                cx={hover.x}
                cy={hover.y}
                r="5"
                fill={SERIES}
                stroke={SURFACE}
                strokeWidth="2"
              />
            </g>
          )}

          {/* x labels */}
          {points.map((p) => (
            <text
              key={p[labelKey] + p.x}
              x={p.x}
              y={plotH + 18}
              textAnchor="middle"
              className={
                hover && hover.x === p.x
                  ? "fill-white text-[11px]"
                  : "fill-[rgba(255,255,255,0.42)] text-[11px]"
              }
            >
              {p[labelKey]}
            </text>
          ))}
        </g>
      </svg>

      {/* tooltip - the text wears its own token, not the series colour */}
      {hover && (
        <div
          className="pointer-events-none absolute -translate-x-1/2 -translate-y-full rounded-lg border border-white/10 bg-[#0b0a2a]/95 px-3 py-2 shadow-xl backdrop-blur"
          style={{
            left: `${((hover.x + PAD.left) / W) * 100}%`,
            top: `${((hover.y + PAD.top) / H) * 100}%`,
          }}
        >
          <p className="whitespace-nowrap text-[11px] text-text-secondary">
            {hover.date || hover[labelKey]}
          </p>
          <p className="flex items-center gap-1.5 whitespace-nowrap text-xs font-semibold text-white">
            <span
              className="inline-block h-2 w-2 rounded-full"
              style={{ background: SERIES }}
            />
            {formatValue(hover.value)}
          </p>
        </div>
      )}
    </div>
  );
}

/** 37 -> 50, 8 -> 10, 240 -> 250 */
function niceStep(raw) {
  if (raw <= 1) return 1;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const n = raw / mag;
  const snapped = n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10;
  return snapped * mag;
}
