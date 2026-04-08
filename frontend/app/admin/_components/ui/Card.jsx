import { cn } from "@/lib/utils";

export function Card({ className, children }) {
  return (
    <div
      className={cn(
        "rounded-xl border border-white/8 bg-white/[0.03] p-4 shadow-card backdrop-blur-xl",
        className
      )}
    >
      {children}
    </div>
  );
}

export function CardHeader({ title, description }) {
  return (
    <div className="mb-3 flex items-center justify-between gap-2">
      <div>
        <h2 className="text-xs font-semibold uppercase tracking-[0.18em] text-text-secondary">
          {title}
        </h2>
        {description && (
          <p className="mt-1 text-xs text-text-secondary/80">{description}</p>
        )}
      </div>
    </div>
  );
}

