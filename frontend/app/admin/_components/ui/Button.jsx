"use client";

import { cn } from "@/lib/utils";

export default function Button({ className, children, variant = "primary", ...props }) {
  const base =
    "inline-flex items-center justify-center rounded-lg text-xs font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-primary/70";

  const variants = {
    primary:
      "bg-accent-primary text-white hover:bg-accent-primary/90 px-3.5 py-2 shadow-card",
    ghost:
      "bg-transparent text-text-secondary hover:bg-white/5 px-3 py-1.5 border border-transparent",
    outline:
      "border border-white/15 bg-transparent text-text-secondary hover:bg-white/5 px-3.5 py-2"
  };

  return (
    <button className={cn(base, variants[variant], className)} {...props}>
      {children}
    </button>
  );
}

