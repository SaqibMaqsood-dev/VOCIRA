"use client";

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Calendar, ChevronLeft, ChevronRight } from "lucide-react";

const WEEKDAYS = ["S", "M", "T", "W", "T", "F", "S"];

function toKey(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function formatLabel(dateKey) {
  const date = new Date(`${dateKey}T00:00:00`);
  if (Number.isNaN(date.getTime())) return dateKey;

  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const diffDays = Math.round((today - date) / 86400000);

  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Yesterday";

  return date.toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

/**
 * A small calendar popover for picking one day out of the days a
 * guardian actually has calls on.
 *
 * The pill-row this replaced only fit a handful of dates before it
 * had to scroll sideways - a guardian with months of history needed
 * an actual calendar, not a longer and longer row of buttons.
 *
 * `availableDates` are "YYYY-MM-DD" strings - only those days render
 * as clickable; every other day in the month is just a greyed-out
 * number, since there is nothing to show for it anyway.
 */
export default function DateCalendar({ availableDates, selected, onSelect }) {
  const available = new Set(availableDates);

  const [open, setOpen] = useState(false);
  const [coords, setCoords] = useState(null);
  const [mounted, setMounted] = useState(false);
  const [viewDate, setViewDate] = useState(() =>
    selected ? new Date(`${selected}T00:00:00`) : new Date()
  );

  const boxRef = useRef(null);
  const popoverRef = useRef(null);

  // createPortal needs document.body, which does not exist during
  // server rendering.
  useEffect(() => setMounted(true), []);

  // The popover used to be an absolutely-positioned child of this
  // button, which put it inside whatever the caller's layout was -
  // on the Queries page that meant the chat bubbles below it (plain,
  // non-positioned content) painted over the calendar instead of
  // under it, because the accordion row in between them established
  // its own stacking context. Rendering it into a portal at
  // document.body sidesteps every ancestor's overflow and stacking
  // entirely; its position is then computed here from the button's
  // own screen position instead of coming from CSS layout.
  useEffect(() => {
    if (!open || !boxRef.current) return;

    const POPOVER_WIDTH = 256;
    const rect = boxRef.current.getBoundingClientRect();
    const alignRight = rect.left + POPOVER_WIDTH > window.innerWidth - 8;

    setCoords({
      top: rect.bottom + 8,
      left: alignRight ? rect.right - POPOVER_WIDTH : rect.left,
    });
  }, [open]);

  // Close on an outside click - the usual popover behaviour. The
  // popover now lives outside boxRef in the DOM (it's portalled), so
  // its own ref has to be checked too, or clicking inside it would
  // register as "outside" and close it immediately.
  useEffect(() => {
    if (!open) return;

    const handleClick = (event) => {
      if (
        boxRef.current &&
        !boxRef.current.contains(event.target) &&
        popoverRef.current &&
        !popoverRef.current.contains(event.target)
      ) {
        setOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  const year = viewDate.getFullYear();
  const month = viewDate.getMonth();

  const firstOfMonth = new Date(year, month, 1);
  const startOffset = firstOfMonth.getDay(); // 0 = Sunday
  const daysInMonth = new Date(year, month + 1, 0).getDate();

  const cells = [];
  for (let i = 0; i < startOffset; i++) cells.push(null);
  for (let day = 1; day <= daysInMonth; day++) cells.push(day);

  const monthLabel = viewDate.toLocaleDateString(undefined, {
    month: "long",
    year: "numeric",
  });

  const changeMonth = (delta) => {
    setViewDate(new Date(year, month + delta, 1));
  };

  const popover = open && coords && mounted && (
    <div
      ref={popoverRef}
      style={{ position: "fixed", top: coords.top, left: coords.left }}
      className="z-50 w-64 rounded-xl border border-white/10 bg-[#14122a] p-3 shadow-2xl"
    >
          <div className="flex items-center justify-between">
            <button
              type="button"
              onClick={() => changeMonth(-1)}
              className="rounded-md p-1 text-text-secondary hover:bg-white/10 hover:text-white"
              aria-label="Previous month"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <p className="text-xs font-semibold text-white">{monthLabel}</p>
            <button
              type="button"
              onClick={() => changeMonth(1)}
              className="rounded-md p-1 text-text-secondary hover:bg-white/10 hover:text-white"
              aria-label="Next month"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>

          <div className="mt-2 grid grid-cols-7 gap-1 text-center text-[10px] text-text-secondary">
            {WEEKDAYS.map((w, i) => (
              <span key={i}>{w}</span>
            ))}
          </div>

          <div className="mt-1 grid grid-cols-7 gap-1">
            {cells.map((day, i) => {
              if (day === null) return <span key={`empty-${i}`} />;

              const key = toKey(new Date(year, month, day));
              const hasCalls = available.has(key);
              const isSelected = key === selected;

              return (
                <button
                  key={key}
                  type="button"
                  disabled={!hasCalls}
                  onClick={() => {
                    onSelect(key);
                    setOpen(false);
                  }}
                  className={`aspect-square rounded-md text-[11px] transition-colors ${
                    isSelected
                      ? "bg-accent-primary font-semibold text-white"
                      : hasCalls
                        ? "bg-white/10 text-white hover:bg-accent-primary/40"
                        : "cursor-not-allowed text-text-secondary/30"
                  }`}
                >
                  {day}
                </button>
              );
            })}
          </div>
    </div>
  );

  return (
    <div ref={boxRef} className="relative inline-block">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-[11px] font-medium text-white transition-colors hover:bg-white/10"
      >
        <Calendar className="h-3.5 w-3.5 text-text-secondary" />
        {selected ? formatLabel(selected) : "Pick a date"}
      </button>

      {mounted && popover && createPortal(popover, document.body)}
    </div>
  );
}
