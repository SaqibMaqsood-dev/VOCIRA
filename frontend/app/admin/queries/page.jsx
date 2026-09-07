"use client";

import { Suspense, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Search, Filter, RefreshCw } from "lucide-react";
import Button from "@/app/admin/_components/ui/Button";
import Badge from "@/app/admin/_components/ui/Badge";
import { Table, THead, TBody, TR, TH, TD } from "@/app/admin/_components/ui/Table";
import { useAdminData, formatTime } from "@/app/admin/useAdminApi";

const statusOptions = ["All", "Resolved", "Escalated"];

// Header ka search ?q= ke sath yahan bhejta hai. useSearchParams
// Suspense maangta hai, is liye asal page andar hai.
export default function QueriesPage() {
  return (
    <Suspense fallback={null}>
      <QueriesPageInner />
    </Suspense>
  );
}

function QueriesPageInner() {
  const params = useSearchParams();
  const [search, setSearch] = useState(params.get("q") || "");
  const [statusFilter, setStatusFilter] = useState("All");
  const [openId, setOpenId] = useState(null);

  const { data: queries, loading, error, reload } = useAdminData(
    "/livekit/admin/queries?limit=100",
    []
  );

  const filtered = useMemo(
    () =>
      queries.filter((q) => {
        const needle = search.toLowerCase();
        const matchesSearch =
          !needle ||
          q.question.toLowerCase().includes(needle) ||
          (q.response || "").toLowerCase().includes(needle) ||
          q.user.toLowerCase().includes(needle);
        const matchesStatus =
          statusFilter === "All" ? true : q.status === statusFilter;
        return matchesSearch && matchesStatus;
      }),
    [queries, search, statusFilter]
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-white">Queries</h1>
          <p className="mt-1 text-xs text-text-secondary">
            Review and manage user conversations handled by Vocira.
            {!loading && !error && (
              <span className="ml-1 text-text-secondary/70">
                ({filtered.length} of {queries.length})
              </span>
            )}
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
              className="w-full rounded-xl border border-white/10 bg-white/[0.04] py-2.5 pl-8 pr-3 text-xs text-white placeholder:text-text-secondary/70 outline-none transition-colors focus:border-accent-primary/50 focus:bg-white/[0.07] focus:ring-2 focus:ring-accent-primary/40"
            />
          </div>

          <div className="inline-flex items-center gap-1 rounded-xl border border-white/10 bg-white/[0.04] px-2 py-1.5 text-xs">
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

          <Button variant="outline" onClick={reload}>
            <RefreshCw className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-amber-400/30 bg-amber-400/5 px-3 py-2 text-xs text-amber-200">
          {error}
        </div>
      )}

      <Table>
        <THead>
          <TR>
            <TH>User</TH>
            <TH>Question</TH>
            <TH>AI Response</TH>
            {/* Pehle yahan "Confidence" tha jis ki value data.js mein
                likhi hui thi - backend aisa koi score rakhta hi nahi.
                Intent asli hai: router har sawal par ye tay karta hai. */}
            <TH>Route</TH>
            <TH>Status</TH>
            <TH>Timestamp</TH>
            <TH className="text-right">Actions</TH>
          </TR>
        </THead>
        <TBody>
          {loading && (
            <TR>
              <TD colSpan={7} className="py-6 text-center text-xs text-text-secondary">
                Loading…
              </TD>
            </TR>
          )}

          {!loading && filtered.length === 0 && !error && (
            <TR>
              <TD colSpan={7} className="py-6 text-center text-xs text-text-secondary">
                {queries.length === 0
                  ? "No questions yet."
                  : "Nothing matches this filter."}
              </TD>
            </TR>
          )}

          {filtered.map((q) => (
            <TR key={q.id}>
              <TD className="whitespace-nowrap text-[11px] text-text-secondary">
                {q.user}
              </TD>
              <TD className="max-w-xs text-xs text-white">
                {openId === q.id ? q.question : truncate(q.question, 70)}
              </TD>
              <TD className="max-w-xs text-[11px] text-text-secondary">
                {openId === q.id ? q.response : truncate(q.response, 70)}
              </TD>
              <TD className="whitespace-nowrap text-[11px] text-text-secondary">
                {q.intent || "—"}
              </TD>
              <TD>
                <Badge
                  label={q.status}
                  variant={q.status === "Escalated" ? "warning" : "success"}
                />
              </TD>
              <TD className="whitespace-nowrap text-[11px] text-text-secondary">
                {formatTime(q.timestamp)}
              </TD>
              <TD className="whitespace-nowrap text-right">
                {/* Pehle yahan "Resolve" aur "Escalate" ke button thay
                    jo kuch karte hi nahi thay - backend mein query ka
                    koi status badalne wala concept nahi (escalations
                    ka apna status hai, wo us page par hai). */}
                <Button
                  variant="ghost"
                  onClick={() => setOpenId(openId === q.id ? null : q.id)}
                >
                  {openId === q.id ? "Collapse" : "View"}
                </Button>
              </TD>
            </TR>
          ))}
        </TBody>
      </Table>
    </div>
  );
}

function truncate(text, max) {
  if (!text) return "—";
  return text.length > max ? `${text.slice(0, max)}…` : text;
}
