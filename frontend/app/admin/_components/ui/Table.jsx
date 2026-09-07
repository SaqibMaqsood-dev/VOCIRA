import { cn } from "@/lib/utils";

/**
 * Table.
 *
 * Yahan bhi wahi toota hua border tha ("border-white/8" - Tailwind
 * us ka CSS banati hi nahi, tafseel Card.jsx mein). Ab /10, aur
 * radius baqi shell jaisa.
 *
 * Sath hi rows ko saans di gayi: pehle har row divide-white/10 ki
 * lakeer se kati hui thi, jo ghani tables mein jaali jaisi lagti
 * hai. Ab lakeerein halki hain aur padding zyada.
 */
export function Table({ children, className }) {
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-2xl border border-white/10",
        "bg-white/[0.02] shadow-[0_8px_32px_rgba(0,0,0,0.28)] backdrop-blur-xl",
        className
      )}
    >
      <span
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 z-10 h-px bg-gradient-to-r from-transparent via-white/20 to-transparent"
      />
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
    <thead
      className={cn(
        "border-b border-white/10 bg-white/[0.04]",
        "text-[10px] font-semibold uppercase tracking-[0.16em] text-text-secondary/80"
      )}
    >
      {children}
    </thead>
  );
}

export function TBody({ children }) {
  // divide-white/10 se har row ek jaali mein band lagti thi -
  // /5 par lakeer nazar to aati hai magar shor nahi machati
  return <tbody className="divide-y divide-white/5">{children}</tbody>;
}

export function TR({ children }) {
  return (
    <tr className="transition-colors hover:bg-white/[0.04]">{children}</tr>
  );
}

export function TH({ children, className }) {
  return <th className={cn("px-4 py-3.5", className)}>{children}</th>;
}

export function TD({ children, className }) {
  return <td className={cn("px-4 py-3.5 align-middle", className)}>{children}</td>;
}
