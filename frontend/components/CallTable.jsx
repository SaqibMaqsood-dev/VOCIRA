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
      {status || "—"}
    </span>
  );
}

export default function CallTable({ rows = [] }) {
  const hasRows = Array.isArray(rows) && rows.length > 0;

  return (
    <div className="w-full overflow-hidden rounded-xl border border-white/10 bg-white/[0.05] shadow-card backdrop-blur-xl">

      {/* =====================================================
          TABLE HEADER
      ===================================================== */}

      <div className="flex items-center justify-between border-b border-white/10 px-5 py-4">
        <h2 className="text-sm font-semibold tracking-wide text-text-primary">
          Call History
        </h2>

        {/*
          This used to say "Last 30 days" - but the query behind it
          (GET /sessions/?limit=20&skip=0) has no date filter at all.
          It is just the most recent 20 calls, however old they are,
          so a caller with one call from six months ago would see
          that label next to it. This says what the page actually
          does instead.
        */}
        <p className="text-xs text-text-secondary">
          Most recent calls
        </p>
      </div>

      {/* =====================================================
          TABLE
      ===================================================== */}

      <div className="w-full overflow-x-auto">
        <table className="min-w-[700px] w-full">

          {/* -------------------------------------------------
              HEADERS
          ------------------------------------------------- */}

          <thead className="bg-white/[0.03]">
            <tr className="text-left text-xs font-semibold tracking-wider text-text-secondary">

              <th className="whitespace-nowrap px-5 py-3">
                Call ID
              </th>

              <th className="whitespace-nowrap px-5 py-3">
                Status
              </th>

              <th className="whitespace-nowrap px-5 py-3">
                Duration
              </th>

              <th className="whitespace-nowrap px-5 py-3">
                Handler
              </th>

              <th className="whitespace-nowrap px-5 py-3">
                Time
              </th>

            </tr>
          </thead>

          {/* -------------------------------------------------
              BODY
          ------------------------------------------------- */}

          <tbody className="divide-y divide-white/10">

            {hasRows ? (
              rows.map((row, index) => (
                <tr
                  key={row.id || `call-${index}`}
                  className="text-sm text-text-primary transition-colors hover:bg-white/[0.03]"
                >

                  {/* Call ID */}
                  <td className="whitespace-nowrap px-5 py-4 font-mono text-xs text-text-secondary">
                    {row.id || "—"}
                  </td>

                  {/* Status */}
                  <td className="whitespace-nowrap px-5 py-4">
                    <StatusBadge status={row.status} />
                  </td>

                  {/* Duration */}
                  <td className="whitespace-nowrap px-5 py-4 text-text-secondary">
                    {row.duration || "—"}
                  </td>

                  {/* Handler */}
                  <td className="whitespace-nowrap px-5 py-4 text-text-secondary">
                    {row.handler || "—"}
                  </td>

                  {/* Time */}
                  <td className="whitespace-nowrap px-5 py-4 text-text-secondary">
                    {row.time || "—"}
                  </td>

                </tr>
              ))
            ) : (
              /* =================================================
                 EMPTY STATE
                 Table remains visible even with no database data.
                 ================================================= */

              <tr className="text-sm text-text-secondary">

                <td className="whitespace-nowrap px-5 py-5 font-mono text-xs">
                  —
                </td>

                <td className="whitespace-nowrap px-5 py-5">
                  <StatusBadge status="—" />
                </td>

                <td className="whitespace-nowrap px-5 py-5">
                  —
                </td>

                <td className="whitespace-nowrap px-5 py-5">
                  —
                </td>

                <td className="whitespace-nowrap px-5 py-5">
                  —
                </td>

              </tr>
            )}

          </tbody>
        </table>
      </div>
    </div>
  );
}