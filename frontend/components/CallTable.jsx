"use client";

import { cn } from "@/lib/utils";

function StatusBadge({ status }) {
  const styles =
    status === "Answered"
      ? "border-emerald-400/20 bg-emerald-400/10 text-emerald-200"
      : status === "Missed"
        ? "border-rose-400/20 bg-rose-400/10 text-rose-200"
        : "border-amber-400/20 bg-amber-400/10 text-amber-200";

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold tracking-wide",
        styles
      )}
    >
      {status}
    </span>
  );
}

export default function CallTable({ rows }) {
  return (
    <div className="overflow-hidden rounded-xl border border-white/10 bg-white/[0.05] shadow-card backdrop-blur-xl">
      <div className="flex items-center justify-between border-b border-white/10 px-5 py-4">
        <h2 className="text-sm font-semibold tracking-wide text-text-primary">
          Call History
        </h2>
        <p className="text-xs text-text-secondary">Last 30 days</p>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full">
          <thead className="bg-white/[0.03]">
            <tr className="text-left text-xs font-semibold tracking-wider text-text-secondary">
              <th className="px-5 py-3">Call ID</th>
              <th className="px-5 py-3">Status</th>
              <th className="px-5 py-3">Duration</th>
              <th className="px-5 py-3">Handler</th>
              <th className="px-5 py-3">Time</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/10">
            {rows.map((row) => (
              <tr
                key={row.id}
                className="text-sm text-text-primary transition-colors hover:bg-white/[0.03]"
              >
                <td className="whitespace-nowrap px-5 py-4 font-mono text-xs text-text-secondary">
                  {row.id}
                </td>
                <td className="whitespace-nowrap px-5 py-4">
                  <StatusBadge status={row.status} />
                </td>
                <td className="whitespace-nowrap px-5 py-4 text-text-secondary">
                  {row.duration}
                </td>
                <td className="whitespace-nowrap px-5 py-4 text-text-secondary">
                  {row.handler}
                </td>
                <td className="whitespace-nowrap px-5 py-4 text-text-secondary">
                  {row.time}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

