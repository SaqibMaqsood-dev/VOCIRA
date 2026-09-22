"use client";

import { Suspense, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Search, Filter, RefreshCw, ChevronDown } from "lucide-react";
import Button from "@/app/admin/_components/ui/Button";
import Badge from "@/app/admin/_components/ui/Badge";
import { useAdminData, formatTime } from "@/app/admin/useAdminApi";
import FullScreenLoader from "@/components/FullScreenLoader";
import DateCalendar from "@/app/admin/_components/DateCalendar";

const statusOptions = ["All", "Resolved", "Escalated"];

// The header's search sends here with ?q=. useSearchParams requires
// Suspense, so the real page lives inside it.
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

  // Which guardian accordions are open. Collapsed by default - with
  // several guardians and dozens of questions each, showing every
  // conversation at once was just a wall of text with no way to see
  // who was who.
  const [openGroups, setOpenGroups] = useState(new Set());

  const toggleGroup = (key) => {
    setOpenGroups((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  // Which date is picked per guardian - a guardian with dozens of
  // calls across weeks used to dump every single one into view at
  // once. Undefined means "not chosen yet", which defaults to that
  // guardian's most recent day.
  const [selectedDate, setSelectedDate] = useState({});

  // A guardian's live call can add new questions to this list while
  // the admin is looking at it - a slower, 30s poll is enough here
  // since a question sitting unseen a little longer is far less
  // urgent than an escalation is.
  const { data: queries, loading, error, reload } = useAdminData(
    "/livekit/admin/queries?limit=100",
    [],
    { pollMs: 30000 }
  );

  // Status is the only thing that drops individual questions - search
  // now picks a guardian, not a question (see `groups` below).
  const filtered = useMemo(
    () =>
      queries.filter((q) =>
        statusFilter === "All" ? true : q.status === statusFilter
      ),
    [queries, statusFilter]
  );

  // ---------------------------------------------------------------
  // GROUP BY GUARDIAN
  //
  // Every question used to sit in one flat list ordered only by
  // time, so one guardian's questions were scattered between
  // everyone else's - there was no way to see "what has THIS parent
  // been asking". `userId` is the real, stable guardian identity
  // (backend now resolves it via Message.user_id -> Users, instead
  // of the generic "Parent" label every row used to share).
  // ---------------------------------------------------------------

  const groups = useMemo(() => {
    const byUser = new Map();

    for (const q of filtered) {
      const key = q.userId || q.user;
      if (!byUser.has(key)) {
        byUser.set(key, {
          key,
          name: q.user,
          email: q.userEmail || null,
          rows: [],
        });
      }
      byUser.get(key).rows.push(q);
    }

    // Each guardian's own questions, newest first
    const list = [...byUser.values()];
    for (const g of list) {
      g.rows.sort(
        (a, b) => new Date(b.timestamp) - new Date(a.timestamp)
      );
    }

    // Guardians ordered by their most recent question, so whoever
    // called most recently appears first - same feel as the flat
    // list this replaces. "Guest" is not a real, identifiable
    // guardian, so it always sinks to the bottom regardless of when
    // it last called.
    list.sort((a, b) => {
      const aGuest = a.key === "guest";
      const bGuest = b.key === "guest";
      if (aGuest !== bGuest) return aGuest ? 1 : -1;

      return new Date(b.rows[0].timestamp) - new Date(a.rows[0].timestamp);
    });

    // A chat reads top-to-bottom as it happened, oldest first - the
    // opposite of `rows`, which stays newest-first for the "last
    // asked" ordering above.
    for (const g of list) {
      g.chat = [...g.rows].reverse();

      // Split that chat into one bucket per calendar day, so a
      // guardian with weeks of history isn't shown all at once - a
      // single day picked at a time reads like the real conversation
      // that happened on it.
      const byDate = new Map();
      for (const q of g.chat) {
        const dateKey = q.timestamp.slice(0, 10); // "2026-09-15"
        if (!byDate.has(dateKey)) byDate.set(dateKey, []);
        byDate.get(dateKey).push(q);
      }

      // Most recent day first, so that is what a guardian's
      // accordion opens to by default.
      g.dates = [...byDate.keys()].sort((a, b) => (a < b ? 1 : -1));
      g.chatByDate = Object.fromEntries(byDate);
    }

    // Search picks a guardian by name or email - it is no longer a
    // question-text search, since each guardian's own questions are
    // already right there once their group is opened.
    const needle = search.trim().toLowerCase();
    if (!needle) return list;

    return list.filter(
      (g) =>
        g.name.toLowerCase().includes(needle) ||
        (g.email || "").toLowerCase().includes(needle)
    );
  }, [filtered, search]);

  if (loading) {
    return (
      <FullScreenLoader
        label="Loading queries…"
        subLabel="Fetching every question Vocira has handled"
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-white">Queries</h1>
          <p className="mt-1 text-xs text-text-secondary">
            Review and manage user conversations handled by Vocira.
            {!error && (
              <span className="ml-1 text-text-secondary/70">
                ({filtered.length} of {queries.length} questions
                {search ? `, ${groups.length} guardian${groups.length === 1 ? "" : "s"} matched` : ""})
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
              placeholder="Search guardian..."
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

      {groups.length === 0 && !error && (
        <div className="rounded-xl border border-white/10 bg-white/[0.03] py-6 text-center text-xs text-text-secondary">
          {queries.length === 0
            ? "No questions yet."
            : search
              ? "No guardian matches this search."
              : "Nothing matches this filter."}
        </div>
      )}

      <div className="space-y-3">
        {groups.map((group) => {
          const isOpen = openGroups.has(group.key);

          // Fall back to the most recent day - selectedDate only
          // holds an entry once the admin has actually clicked a
          // different one.
          const activeDate = selectedDate[group.key] || group.dates[0];
          const dayChat = group.chatByDate[activeDate] || [];

          return (
            <div
              key={group.key}
              className="overflow-hidden rounded-xl border border-white/10 bg-white/[0.03]"
            >
              {/* ---- guardian header - click to open/close ---- */}
              <button
                type="button"
                onClick={() => toggleGroup(group.key)}
                className="flex w-full flex-wrap items-center justify-between gap-2 px-4 py-3 text-left transition-colors hover:bg-white/[0.03]"
              >
                <div className="flex items-center gap-3">
                  <ChevronDown
                    className={`h-4 w-4 shrink-0 text-text-secondary transition-transform ${
                      isOpen ? "rotate-180" : ""
                    }`}
                  />
                  <div>
                    <p className="text-sm font-semibold text-white">
                      {group.name}
                    </p>
                    {group.email && (
                      <p className="text-[11px] text-text-secondary">
                        {group.email}
                      </p>
                    )}
                  </div>
                </div>
                <span className="rounded-full border border-white/10 bg-white/5 px-2.5 py-0.5 text-[11px] text-text-secondary">
                  {group.rows.length} question{group.rows.length === 1 ? "" : "s"}
                </span>
              </button>

              {/* ---- this guardian's conversation, chat-style ---- */}
              {isOpen && (
                <div className="border-t border-white/10">

                  {/* ---- pick a day ---- */}
                  <div className="flex items-center gap-2 border-b border-white/10 bg-white/[0.02] px-4 py-2.5">
                    <DateCalendar
                      availableDates={group.dates}
                      selected={activeDate}
                      onSelect={(date) =>
                        setSelectedDate((prev) => ({
                          ...prev,
                          [group.key]: date,
                        }))
                      }
                    />
                    <span className="text-[11px] text-text-secondary">
                      {dayChat.length} question{dayChat.length === 1 ? "" : "s"} on this day
                    </span>
                  </div>

                  <div className="space-y-4 px-4 py-4">
                    {dayChat.map((q) => (
                      <div key={q.id} className="space-y-1.5">

                        {/* guardian's question */}
                        <div className="flex justify-end">
                          <div className="max-w-[75%] rounded-2xl rounded-tr-sm bg-accent-primary/20 px-4 py-2">
                            <p className="text-sm text-white">{q.question}</p>
                            <p className="mt-1 text-right text-[10px] text-text-secondary">
                              {formatTime(q.timestamp)}
                            </p>
                          </div>
                        </div>

                        {/* Vocira's answer */}
                        <div className="flex justify-start">
                          <div className="max-w-[75%] rounded-2xl rounded-tl-sm bg-white/[0.06] px-4 py-2">
                            <p className="text-sm text-text-primary">
                              {q.response}
                            </p>
                            <div className="mt-1.5 flex items-center gap-2">
                              <span className="text-[10px] uppercase tracking-wide text-text-secondary">
                                {q.intent || "—"}
                              </span>
                              <Badge
                                label={q.status}
                                variant={q.status === "Escalated" ? "warning" : "success"}
                              />
                            </div>
                          </div>
                        </div>

                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
