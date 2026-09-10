import { cn } from "@/lib/utils";

/**
 * Card.
 *
 * The border used to be "border-white/8" - and Tailwind does NOT
 * generate that class. The default opacity scale runs in multiples
 * of 5 (5, 10, 15, 20...), so no CSS was produced for /8. The
 * `border` class still applies 1px solid, but the colour fell back
 * to preflight's default: #e5e7eb - a light gray. That was the ugly
 * white edge showing on the dark theme.
 *
 * It is now /10 (which does generate), and the radius matches the
 * rest of the shell - the sidebar, header and stat tiles are all
 * rounded-2xl, and only these two were left at rounded-xl.
 */
export function Card({ className, children }) {
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-2xl border border-white/10",
        "bg-white/[0.03] p-5 shadow-[0_8px_32px_rgba(0,0,0,0.28)]",
        "backdrop-blur-xl transition-colors hover:border-white/[0.18]",
        className
      )}
    >
      {/* a hairline of light along the top - it reads as glass, and
          separates the card from the background */}
      <span
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/20 to-transparent"
      />
      {children}
    </div>
  );
}

export function CardHeader({ title, description }) {
  return (
    <div className="mb-4 flex items-start justify-between gap-2">
      <div className="min-w-0">
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.18em] text-text-secondary">
          {title}
        </h2>
        {description && (
          <p className="mt-1.5 text-xs leading-5 text-text-secondary/75">
            {description}
          </p>
        )}
      </div>
    </div>
  );
}
