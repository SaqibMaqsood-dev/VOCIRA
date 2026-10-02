"use client";

/*
 * Choosing where a school's records come from. Grouped by what the school
 * has: nothing (Native Records), a sheet or an export (Excel/CSV, Google
 * Sheets), a system with an approved API or database, and the named systems
 * still waiting for their vendor's official integration - shown, but not
 * choosable, with what to use instead.
 */

import Badge from "@/app/admin/_components/ui/Badge";

import { MODE_TEXT, STATUS_BADGE } from "./shared";

const GROUPS = [
  { title: "No school software", kinds: ["native"] },
  { title: "A sheet or an export", kinds: ["excel", "spreadsheet"] },
  { title: "A system with an approved API or database", kinds: ["rest-api", "database", "erpnext", "open-school-mis"] },
];

export default function ProviderPicker({ providers, current, onPick }) {
  const byKind = Object.fromEntries(providers.map((p) => [p.kind, p]));
  const waiting = providers.filter((p) => p.mode === "unavailable");

  const card = (p) => {
    const badge = STATUS_BADGE[p.status];
    const selected = p.kind === current;
    return (
      <button
        key={p.kind}
        type="button"
        onClick={() => onPick(p)}
        className={`flex h-full flex-col items-start gap-1.5 rounded-xl border p-3 text-left transition-colors ${
          selected ? "border-accent-primary/60 bg-accent-primary/10" : "border-white/10 bg-white/[0.03] hover:border-white/25"
        }`}
      >
        <div className="flex w-full items-center justify-between gap-2">
          <span className="text-sm font-semibold text-white">{p.label}</span>
          {selected ? <Badge label="current" variant="success" /> : badge ? <Badge label={badge.label} variant={badge.variant} /> : null}
        </div>
        <span className="text-[11px] leading-4 text-text-secondary">{p.description}</span>
        <span className="text-[10px] text-text-secondary/70">{MODE_TEXT[p.mode]}</span>
      </button>
    );
  };

  return (
    <div className="space-y-5">
      {GROUPS.map((group) => (
        <div key={group.title}>
          <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-text-secondary">{group.title}</div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {group.kinds.map((k) => byKind[k]).filter(Boolean).map(card)}
          </div>
        </div>
      ))}
      {waiting.length > 0 && (
        <div>
          <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-text-secondary">
            Waiting for the vendor&apos;s official integration
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {waiting.map((p) => (
              <div key={p.kind} className="rounded-xl border border-dashed border-white/15 p-3">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-semibold text-white/80">{p.label}</span>
                  <Badge label="official integration required" variant="warning" />
                </div>
                <p className="mt-1.5 text-[11px] leading-4 text-text-secondary">{p.notes}</p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {p.instead.map((k) => byKind[k]).filter(Boolean).map((alt) => (
                    <button key={alt.kind} type="button" onClick={() => onPick(alt)}
                            className="rounded-full border border-white/15 px-2 py-0.5 text-[10px] text-white hover:bg-white/10">
                      Use {alt.label}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
