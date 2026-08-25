import { cn } from "@/lib/utils";

export function Table({ children, className }) {
  return (
    <div
      className={cn(
        "overflow-hidden rounded-xl border border-white/8 bg-white/[0.02] shadow-card backdrop-blur-xl",
        className
      )}
    >
      <div className="overflow-x-auto">
        <table className="min-w-[720px] border-collapse text-left text-xs text-text-secondary sm:min-w-full">
          {children}
        </table>
      </div>
    </div>
  );
}

export function THead({ children }) {
  return (
    <thead className="bg-white/[0.03] text-[11px] font-semibold uppercase tracking-[0.14em] text-text-secondary">
      {children}
    </thead>
  );
}

export function TBody({ children }) {
  return <tbody className="divide-y divide-white/10">{children}</tbody>;
}

export function TR({ children }) {
  return <tr className="transition-colors hover:bg-white/[0.03]">{children}</tr>;
}

export function TH({ children, className }) {
  return <th className={cn("px-4 py-3", className)}>{children}</th>;
}

export function TD({ children, className }) {
  return <td className={cn("px-4 py-3 align-top", className)}>{children}</td>;
}

