"use client";

import { Bell, Search, ChevronDown, PanelLeftOpen } from "lucide-react";

export default function Header({ onMenuClick }) {
  return (
    <header className="sticky top-0 z-30 border-b border-white/10 bg-[#05041c]/90 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4">
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-white/10 bg-white/5 text-text-secondary hover:bg-white/10 md:hidden"
            onClick={onMenuClick}
          >
            <PanelLeftOpen className="h-4 w-4" />
          </button>

          <div className="relative hidden w-72 items-center md:flex">
            <span className="pointer-events-none absolute left-3 text-text-secondary">
              <Search className="h-4 w-4" />
            </span>
            <input
              placeholder="Search queries, users, knowledge..."
              className="w-full rounded-lg border border-white/10 bg-white/5 py-2 pl-9 pr-3 text-xs text-white placeholder:text-text-secondary/70 outline-none focus:ring-2 focus:ring-accent-primary/60"
            />
          </div>
        </div>

        <div className="ml-auto flex items-center gap-3">
          <button
            type="button"
            className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-white/10 bg-white/5 text-text-secondary hover:bg-white/10"
          >
            <Bell className="h-4 w-4" />
          </button>
          <button
            type="button"
            className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-medium text-text-secondary hover:bg-white/10"
          >
            <span className="grid h-7 w-7 place-items-center rounded-full bg-gradient-to-br from-accent-primary to-accent-secondary text-[11px] font-semibold text-[#05041c]">
              AD
            </span>
            <span className="hidden sm:inline">Admin</span>
            <ChevronDown className="h-3 w-3" />
          </button>
        </div>
      </div>
    </header>
  );
}

