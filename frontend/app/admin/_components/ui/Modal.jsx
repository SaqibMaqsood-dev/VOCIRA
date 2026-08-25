"use client";

import { X } from "lucide-react";

export default function Modal({ open, onClose, title, children }) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 backdrop-blur">
      <div className="w-full max-w-xl rounded-xl border border-white/10 bg-[#05041c] p-5 shadow-card">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-white">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-white/5 text-text-secondary hover:bg-white/10"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="space-y-4 text-xs text-text-secondary">{children}</div>
      </div>
    </div>
  );
}

