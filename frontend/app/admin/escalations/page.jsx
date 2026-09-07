"use client";

import { useState } from "react";
import { RefreshCw } from "lucide-react";
import Button from "@/app/admin/_components/ui/Button";
import Badge from "@/app/admin/_components/ui/Badge";
import { Table, THead, TBody, TR, TH, TD } from "@/app/admin/_components/ui/Table";
import { useAdminData, adminFetch, formatTime } from "@/app/admin/useAdminApi";

// Backend ka EscalationStatus enum - wahi values yahan bhi
const STATUS_VARIANT = {
  pending: "neutral",
  open: "warning",
  customer_waiting: "warning",
  resolved: "success",
  closed: "neutral",
};

export default function EscalationsPage() {
  const { data: escalations, loading, error, reload } = useAdminData(
    "/livekit/admin/escalations?limit=100",
    []
  );

  const [busyId, setBusyId] = useState(null);
  const [actionError, setActionError] = useState("");

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

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">Escalations</h1>
          <p className="mt-1 text-xs text-text-secondary">
            Queries that required human review.
            {!loading && !error && (
              <span className="ml-1 text-text-secondary/70">
                ({escalations.length})
              </span>
            )}
          </p>
        </div>
        <Button variant="outline" onClick={reload}>
          <RefreshCw className="h-3.5 w-3.5" />
        </Button>
      </div>

      {(error || actionError) && (
        <div className="rounded-lg border border-amber-400/30 bg-amber-400/5 px-3 py-2 text-xs text-amber-200">
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
          {loading && (
            <TR>
              <TD colSpan={5} className="py-6 text-center text-xs text-text-secondary">
                Loading…
              </TD>
            </TR>
          )}

          {!loading && escalations.length === 0 && !error && (
            <TR>
              <TD colSpan={5} className="py-6 text-center text-xs text-text-secondary">
                Koi escalation nahi — sab sawal AI ne hal kar diye.
              </TD>
            </TR>
          )}

          {escalations.map((e) => (
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
                {/* Pehle yahan "Assign" / "Reply" / "Resolve" ke button
                    thay jo kuch karte hi nahi thay. Ab sirf wo rakhe
                    hain jin ka backend mojood hai. */}
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
