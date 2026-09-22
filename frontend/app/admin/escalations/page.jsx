"use client";

import { useMemo, useState } from "react";
import { RefreshCw } from "lucide-react";
import Button from "@/app/admin/_components/ui/Button";
import Badge from "@/app/admin/_components/ui/Badge";
import { Table, THead, TBody, TR, TH, TD } from "@/app/admin/_components/ui/Table";
import { useAdminData, adminFetch, formatTime } from "@/app/admin/useAdminApi";
import FullScreenLoader from "@/components/FullScreenLoader";
import DateCalendar from "@/app/admin/_components/DateCalendar";

// The backend's EscalationStatus enum - the same values here
const STATUS_VARIANT = {
  pending: "neutral",
  open: "warning",
  customer_waiting: "warning",
  resolved: "success",
  closed: "neutral",
};

// Escalations mean a parent is waiting on a real answer, so a stale
// list here matters more than anywhere else in the admin panel - 15s
// keeps a new one from sitting unseen for long without polling so
// often it is indistinguishable from spam.
const POLL_MS = 15000;

export default function EscalationsPage() {
  const { data: escalations, loading, error, reload } = useAdminData(
    "/livekit/admin/escalations?limit=100",
    [],
    { pollMs: POLL_MS }
  );

  const [busyId, setBusyId] = useState(null);
  const [actionError, setActionError] = useState("");

  // Which day is picked - null means "every day", the default, since
  // escalations are rare enough that seeing them all at once is
  // usually what's wanted. The calendar narrows it down to one day
  // only when that is actually useful.
  const [selectedDate, setSelectedDate] = useState(null);

  const dates = useMemo(
    () =>
      [...new Set(escalations.map((e) => e.time.slice(0, 10)))].sort(
        (a, b) => (a < b ? 1 : -1)
      ),
    [escalations]
  );

  const visibleEscalations = useMemo(
    () =>
      selectedDate
        ? escalations.filter((e) => e.time.slice(0, 10) === selectedDate)
        : escalations,
    [escalations, selectedDate]
  );

  async function setStatus(id, status) {
    try {
      setBusyId(id);
      setActionError("");
      await adminFetch(
        `/livekit/admin/escalations/${id}/status?new_status=${status}`,
        { method: "PATCH" }
      );
      await reload();
    } catch (err) {
      setActionError(err.message || "Could not change the status.");
    } finally {
      setBusyId(null);
    }
  }

  if (loading) {
    return (
      <FullScreenLoader
        label="Loading escalations…"
        subLabel="Fetching queries that needed human review"
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-white">Escalations</h1>
          <p className="mt-1 text-xs text-text-secondary">
            Queries that required human review.
            {!error && (
              <span className="ml-1 text-text-secondary/70">
                ({selectedDate
                  ? `${visibleEscalations.length} of ${escalations.length}`
                  : escalations.length})
              </span>
            )}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <DateCalendar
            availableDates={dates}
            selected={selectedDate}
            onSelect={setSelectedDate}
          />
          {selectedDate && (
            <Button variant="outline" onClick={() => setSelectedDate(null)}>
              All dates
            </Button>
          )}
          <Button variant="outline" onClick={reload}>
            <RefreshCw className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      {(error || actionError) && (
        <div className="rounded-xl border border-amber-400/30 bg-amber-400/5 px-3 py-2 text-xs text-amber-200">
          {error || actionError}
        </div>
      )}

      <Table>
        <THead>
          <TR>
            <TH>User Question</TH>
            <TH>Session</TH>
            <TH>Status</TH>
            <TH>Time</TH>
            <TH className="text-right">Actions</TH>
          </TR>
        </THead>
        <TBody>
          {visibleEscalations.length === 0 && !error && (
            <TR>
              <TD colSpan={5} className="py-6 text-center text-xs text-text-secondary">
                {escalations.length === 0
                  ? "No escalations — the AI handled every question."
                  : "No escalations on this day."}
              </TD>
            </TR>
          )}

          {visibleEscalations.map((e) => (
            <TR key={e.id}>
              <TD className="max-w-md text-xs text-white">{e.question}</TD>
              <TD className="whitespace-nowrap font-mono text-[11px] text-text-secondary">
                {e.sessionId ? e.sessionId.slice(0, 8) : "—"}
              </TD>
              <TD>
                <Badge
                  label={e.status}
                  variant={STATUS_VARIANT[e.status] || "neutral"}
                />
              </TD>
              <TD className="whitespace-nowrap text-[11px] text-text-secondary">
                {formatTime(e.time)}
              </TD>
              <TD className="whitespace-nowrap text-right">
                {/* There used to be "Assign" / "Reply" / "Resolve"
                    buttons here that did nothing. Only the ones with
                    a backend behind them are kept. */}
                <div className="flex justify-end gap-1">
                  {e.status !== "open" && e.status !== "resolved" && (
                    <Button
                      variant="ghost"
                      disabled={busyId === e.id}
                      onClick={() => setStatus(e.id, "open")}
                    >
                      Open
                    </Button>
                  )}
                  {e.status !== "resolved" && (
                    <Button
                      variant="outline"
                      disabled={busyId === e.id}
                      onClick={() => setStatus(e.id, "resolved")}
                    >
                      {busyId === e.id ? "…" : "Resolve"}
                    </Button>
                  )}
                  {e.status === "resolved" && (
                    <span className="text-[11px] text-text-secondary">
                      Done
                    </span>
                  )}
                </div>
              </TD>
            </TR>
          ))}
        </TBody>
      </Table>
    </div>
  );
}
