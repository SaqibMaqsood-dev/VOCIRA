"use client";

import Button from "@/app/admin/_components/ui/Button";
import Badge from "@/app/admin/_components/ui/Badge";
import { Table, THead, TBody, TR, TH, TD } from "@/app/admin/_components/ui/Table";
import { escalations } from "@/app/admin/data";

export default function EscalationsPage() {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">Escalations</h1>
          <p className="mt-1 text-xs text-text-secondary">
            Queries that required human review.
          </p>
        </div>
      </div>

      <Table>
        <THead>
          <TR>
            <TH>Escalation ID</TH>
            <TH>User Question</TH>
            <TH>AI Response</TH>
            <TH>Assigned Admin</TH>
            <TH>Status</TH>
            <TH>Time</TH>
            <TH className="text-right">Actions</TH>
          </TR>
        </THead>
        <TBody>
          {escalations.map((e) => (
            <TR key={e.id}>
              <TD className="whitespace-nowrap font-mono text-[11px] text-text-secondary">
                {e.id}
              </TD>
              <TD className="max-w-xs text-xs text-white">{e.question}</TD>
              <TD className="max-w-xs text-[11px] text-text-secondary">{e.response}</TD>
              <TD className="whitespace-nowrap text-[11px] text-text-secondary">
                {e.admin}
              </TD>
              <TD>
                <Badge
                  label={e.status}
                  variant={
                    e.status === "Open"
                      ? "warning"
                      : e.status === "Resolved"
                        ? "success"
                        : "neutral"
                  }
                />
              </TD>
              <TD className="whitespace-nowrap text-[11px] text-text-secondary">
                {e.time}
              </TD>
              <TD className="whitespace-nowrap text-right">
                <div className="flex justify-end gap-1">
                  <Button variant="ghost">Assign</Button>
                  <Button variant="ghost">Reply</Button>
                  <Button variant="outline">Resolve</Button>
                </div>
              </TD>
            </TR>
          ))}
        </TBody>
      </Table>
    </div>
  );
}

