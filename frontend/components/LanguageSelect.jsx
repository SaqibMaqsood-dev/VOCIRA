"use client";

import { useEffect, useRef, useState } from "react";
import { Check, ChevronDown, Languages } from "lucide-react";

// A guest has no account, so their choice lives in the browser and
// travels with the call token instead of being saved server-side.
export const GUEST_LANGUAGE_KEY = "vocira-guest-language";

export function readGuestLanguage(fallback = "ur") {
  try {
    return localStorage.getItem(GUEST_LANGUAGE_KEY) || fallback;
  } catch {
    // Private windows and blocked site data both throw here.
    return fallback;
  }
}

export function writeGuestLanguage(value) {
  try {
    localStorage.setItem(GUEST_LANGUAGE_KEY, value);
  } catch {
    // Not being able to remember it is survivable - the call still
    // runs, just in the default language next time.
  }
}

/**
 * The language picker for a guardian's own calls.
 *
 * This replaced a native <select>. A native option list is drawn by
 * Windows, not by the page: its colours had to be forced inline (they
 * came out white on white otherwise) and `cursor` on an <option> is
 * ignored outright, so the list never showed a pointer. Drawing the
 * list here instead puts all of that back under the page's control.
 */
export default function LanguageSelect({
  value,
  options,
  disabled = false,
  onChange,
  fullWidth = false,
  lockedReason = "",
}) {
  const [open, setOpen] = useState(false);
  const boxRef = useRef(null);

  const selected = options.find((option) => option.value === value);

  // A call starting while the list is open would otherwise leave it
  // hanging there, still clickable.
  useEffect(() => {
    if (disabled) setOpen(false);
  }, [disabled]);

  useEffect(() => {
    if (!open) return;

    const handleClick = (event) => {
      if (boxRef.current && !boxRef.current.contains(event.target)) {
        setOpen(false);
      }
    };

    const handleKey = (event) => {
      if (event.key === "Escape") setOpen(false);
    };

    document.addEventListener("mousedown", handleClick);
    document.addEventListener("keydown", handleKey);

    return () => {
      document.removeEventListener("mousedown", handleClick);
      document.removeEventListener("keydown", handleKey);
    };
  }, [open]);

  const pick = (option) => {
    setOpen(false);
    if (option.value !== value) onChange(option.value);
  };

  return (
    <div
      ref={boxRef}
      className={`relative shrink-0 ${fullWidth ? "w-full" : ""}`}
    >
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen((isOpen) => !isOpen)}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label="Language for your calls"
        title={
          disabled && lockedReason ? lockedReason : "Language for your calls"
        }
        className={`inline-flex cursor-pointer items-center gap-1.5 rounded-xl border border-white/10 bg-white/[0.04] px-2.5 py-2 text-sm font-semibold text-text-secondary transition-colors hover:border-white/20 hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-60 lg:px-3 ${
          fullWidth ? "w-full justify-between" : ""
        }`}
      >
        <span className="inline-flex items-center gap-1.5">
          <Languages className="h-4 w-4" />
          {selected?.label}
        </span>
        <ChevronDown
          className={`h-3.5 w-3.5 transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>

      {open && (
        <ul
          role="listbox"
          className={`absolute right-0 top-full z-50 mt-2 min-w-[9rem] overflow-hidden rounded-xl border border-white/10 bg-[#100944] py-1 shadow-2xl ${
            fullWidth ? "left-0" : ""
          }`}
        >
          {options.map((option) => {
            const isSelected = option.value === value;

            return (
              <li key={option.value}>
                <button
                  type="button"
                  role="option"
                  aria-selected={isSelected}
                  onClick={() => pick(option)}
                  className={`flex w-full cursor-pointer items-center justify-between gap-3 px-3 py-2 text-left text-sm transition-colors hover:bg-white/10 ${
                    isSelected
                      ? "font-semibold text-text-primary"
                      : "text-text-secondary hover:text-text-primary"
                  }`}
                >
                  {option.label}
                  {isSelected && <Check className="h-3.5 w-3.5" />}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
