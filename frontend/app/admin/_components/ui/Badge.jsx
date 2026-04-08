import { cn } from "@/lib/utils";

export default function Badge({ label, variant = "neutral", className }) {
  const variants = {
    success:
      "border-emerald-400/25 bg-emerald-400/10 text-emerald-200 shadow-[0_0_30px_rgba(16,185,129,0.35)]",
    danger:
      "border-rose-400/25 bg-rose-400/10 text-rose-200 shadow-[0_0_30px_rgba(244,63,94,0.35)]",
    warning:
      "border-amber-400/25 bg-amber-400/10 text-amber-100 shadow-[0_0_30px_rgba(245,158,11,0.35)]",
    neutral: "border-white/15 bg-white/[0.04] text-text-secondary"
  };

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-[10px] font-semibold tracking-wide",
        variants[variant],
        className
      )}
    >
      {label}
    </span>
  );
}

