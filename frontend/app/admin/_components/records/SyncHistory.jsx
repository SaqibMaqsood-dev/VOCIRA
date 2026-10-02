"use client";

/* The school's recent syncs - what started each, how it went, what it read, and why it failed. */

import Badge from "@/app/admin/_components/ui/Badge";
import { Table, THead, TBody, TR, TH, TD } from "@/app/admin/_components/ui/Table";
import { formatTime } from "@/app/admin/useAdminApi";

import { RUN_BADGE, RUN_LABEL, TRIGGER_TEXT, countsText } from "./shared";

export default function SyncHistory({ runs, tables }) {
  return (
    <Table>
      <THead>
        <TR>
          <TH>When</TH>
          <TH>Started by</TH>
          <TH>Result</TH>
          <TH>Records</TH>
          <TH>Problem</TH>
        </TR>
      </THead>
      <TBody>
        {(runs || []).length === 0 ? (
          <TR>
            <TD colSpan={5} className="py-6 text-center text-text-secondary">
              No syncs yet.
            </TD>
          </TR>
        ) : (
          runs.map((run) => (
            <TR key={run.id}>
              <TD className="whitespace-nowrap">{formatTime(run.started_at)}</TD>
              <TD>
                <div className="text-white">{TRIGGER_TEXT[run.trigger] || run.trigger}</div>
                {run.actor && <div className="text-[10px] text-text-secondary/70">{run.actor}</div>}
              </TD>
              <TD>
                <Badge label={RUN_LABEL[run.status] || run.status} variant={RUN_BADGE[run.status] || "neutral"} />
                {run.attempts > 1 && (
                  <div className="mt-1 text-[10px] text-text-secondary/70">{run.attempts} attempts</div>
                )}
              </TD>
              <TD className="max-w-[260px] text-[11px]">{countsText(run.counts, tables)}</TD>
              <TD className="max-w-[320px] text-[11px] text-rose-200/90">{run.error || "—"}</TD>
            </TR>
          ))
        )}
      </TBody>
    </Table>
  );
}
