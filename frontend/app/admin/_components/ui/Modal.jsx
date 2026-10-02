"use client";

import { useEffect } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";

/**
 * A form over the page, in the panel's own glass style - the QR code's
 * popup (superadmin/schools/SchoolQr.jsx) made general.
 *
 * Escape or the X closes it. A click beside it does not: half a form
 * typed in should not vanish over a stray click. The page behind does not
 * scroll while it is open; a long form scrolls inside it.
 */
/**
 * Drawn straight into <body>, not where the page renders it. Inside the
 * page it took on the page's layout: a list's spacing (space-y-*) gave it
 * a top margin, and the dark cover stopped 20px short of the window's top.
 */
export function OverPage({ children }) {
  return typeof document === "undefined" ? null : createPortal(children, document.body);
}

export default function Modal({ id, title, description, onClose, size = "md", children }) {
  useEffect(() => {
    const onKey = (event) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = overflow;
    };
  }, [onClose]);

  const width = { md: "max-w-xl", lg: "max-w-3xl", xl: "max-w-5xl" }[size] || "max-w-xl";

  return (
    <OverPage>
      <div className="fixed inset-0 z-[90] flex items-center justify-center bg-black/60 px-4 py-6 backdrop-blur-sm">
        <div
          id={id}
          role="dialog"
          aria-modal="true"
          aria-label={title}
          className={`relative flex max-h-full w-full ${width} flex-col overflow-hidden rounded-2xl border border-white/10 bg-bg-secondary shadow-card`}
        >
          <span
            aria-hidden="true"
            className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/20 to-transparent"
          />
          <div className="flex items-start justify-between gap-4 border-b border-white/10 px-5 py-4">
            <div className="min-w-0">
              <h2 className="text-base font-semibold text-white">{title}</h2>
              {description && <p className="mt-1 text-xs leading-5 text-text-secondary">{description}</p>}
            </div>
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg p-1 text-text-secondary hover:text-white"
              title="Close"
              aria-label="Close"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
          <div className="overflow-y-auto px-5 py-4">{children}</div>
        </div>
      </div>
    </OverPage>
  );
}
