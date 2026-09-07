import { cn } from "@/lib/utils";

/**
 * Card.
 *
 * Pehle border "border-white/8" tha - aur wo class Tailwind BANATI
 * HI NAHI. Default opacity scale 5 ke multiples par hai (5, 10, 15,
 * 20...), is liye /8 ka koi CSS nahi banta tha. `border` class phir
 * bhi 1px solid lagati hai, magar rang preflight ke default par gir
 * jata tha: #e5e7eb - halka gray. Gehre theme par wahi bhadda safaid
 * kinara nazar aa raha tha.
 *
 * Ab /10 hai (banti hai), aur radius bhi baqi shell jaisa - sidebar,
 * header aur stat tiles sab rounded-2xl hain, sirf ye do rounded-xl
 * reh gaye thay.
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
      {/* upar ek baal barabar roshni - shishe ka ehsaas deti hai,
          aur card ko background se alag karti hai */}
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
