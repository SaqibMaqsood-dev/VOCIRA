"use client";

import { useMemo, useState } from "react";
import { Search, Filter } from "lucide-react";
import Button from "@/app/admin/_components/ui/Button";
import Badge from "@/app/admin/_components/ui/Badge";
import { Table, THead, TBody, TR, TH, TD } from "@/app/admin/_components/ui/Table";
import { queries } from "@/app/admin/data";

const statusOptions = ["All", "Resolved", "Pending", "Escalated"];

export default function QueriesPage() {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("All");

  const filtered = useMemo(
    () =>
      queries.filter((q) => {
        const matchesSearch =
          q.question.toLowerCase().includes(search.toLowerCase()) ||
          q.user.toLowerCase().includes(search.toLowerCase()) ||
          q.id.toLowerCase().includes(search.toLowerCase());
        const matchesStatus = statusFilter === "All" ? true : q.status === statusFilter;
        return matchesSearch && matchesStatus;
      }),
    [search, statusFilter]
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">Queries</h1>
          <p className="mt-1 text-xs text-text-secondary">
            Review and manage user conversations handled by Vocira.
          </p>
        </div>

        <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row sm:items-center">
          <div className="relative flex-1 sm:w-64">
            <span className="pointer-events-none absolute left-3 top-2.5 text-text-secondary">
              <Search className="h-3.5 w-3.5" />
            </span>
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search queries..."
              className="w-full rounded-lg border border-white/10 bg-white/5 py-2 pl-8 pr-3 text-xs text-white placeholder:text-text-secondary/70 outline-none focus:ring-2 focus:ring-accent-primary/60"
            />
          </div>

          <div className="inline-flex items-center gap-1 rounded-lg border border-white/10 bg-white/5 px-2 py-1.5 text-xs">
            <Filter className="mr-1 h-3.5 w-3.5 text-text-secondary" />
            {statusOptions.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => setStatusFilter(s)}
                className={`rounded-md px-2 py-0.5 ${
                  statusFilter === s
                    ? "bg-accent-primary text-white"
                    : "text-text-secondary hover:bg-white/5"
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      </div>

      <Table>
        <THead>
          <TR>
            <TH>Query ID</TH>
            <TH>User</TH>
            <TH>Question</TH>
            <TH>AI Response</TH>
            <TH>Confidence</TH>
            <TH>Status</TH>
            <TH>Timestamp</TH>
            <TH className="text-right">Actions</TH>
          </TR>
        </THead>
        <TBody>
          {filtered.map((q) => (
            <TR key={q.id}>
              <TD className="whitespace-nowrap font-mono text-[11px] text-text-secondary">
                {q.id}
              </TD>
              <TD className="whitespace-nowrap text-[11px] text-text-secondary">
                {q.user}
              </TD>
              <TD className="max-w-xs text-xs text-white">{q.question}</TD>
              <TD className="max-w-xs text-[11px] text-text-secondary">{q.response}</TD>
              <TD className="whitespace-nowrap text-[11px] text-text-secondary">
                {(q.confidence * 100).toFixed(0)}%
              </TD>
              <TD>
                <Badge
                  label={q.status}
                  variant={
                    q.status === "Escalated"
                      ? "warning"
                      : q.status === "Resolved"
                        ? "success"
                        : "neutral"
                  }
                />
              </TD>
              <TD className="whitespace-nowrap text-[11px] text-text-secondary">
                {q.timestamp}
              </TD>
              <TD className="whitespace-nowrap text-right">
                <div className="flex justify-end gap-1">
                  <Button variant="ghost">View</Button>
                  <Button variant="outline">Resolve</Button>
                  <Button variant="ghost">Escalate</Button>
                </div>
              </TD>
            </TR>
          ))}
        </TBody>
      </Table>
    </div>
  );
}

