"use client";

import { motion } from "framer-motion";
import { Card, CardHeader } from "@/app/admin/_components/ui/Card";
import Badge from "@/app/admin/_components/ui/Badge";
import { Table, THead, TBody, TR, TH, TD } from "@/app/admin/_components/ui/Table";
import { useAdminData, formatTime } from "@/app/admin/useAdminApi";

const EMPTY_STATS = {
  today: 0,
  week: 0,
  total: 0,
  escalated: 0,
  sessions: 0,
  queriesPerDay: [],
  escalationRate: [],
};

export default function AdminDashboardPage() {
  const {
    data: stats,
    loading: statsLoading,
    error: statsError,
  } = useAdminData("/livekit/admin/stats", EMPTY_STATS);

  const {
    data: recent,
    loading: recentLoading,
    error: recentError,
  } = useAdminData("/livekit/admin/queries?limit=8", []);

  // Pehle bar ki oonchai (value / 200) se nikalti thi - 200 hardcoded
  // tha. Asli data mein koi din 200 se ooper ja sakta hai (bar chart
  // se bahar) ya sab 200 se bohat neeche (chart khali dikhta hai).
  // Ab sab se oonche din ke hisab se scale hota hai.
  const peak = Math.max(1, ...stats.queriesPerDay.map((d) => d.value));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-white">Overview</h1>
        <p className="mt-1 text-xs text-text-secondary">
          High-level metrics across Vocira&apos;s AI assistant.
        </p>
      </div>

      {statsError && (
        <Card className="border-amber-400/30">
          <p className="text-xs text-amber-200">{statsError}</p>
        </Card>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader title="Total Queries Today" />
          <p className="text-2xl font-semibold text-white">
            {statsLoading ? "…" : stats.today}
          </p>
        </Card>
        <Card>
          <CardHeader title="Total Queries This Week" />
          <p className="text-2xl font-semibold text-white">
            {statsLoading ? "…" : stats.week}
          </p>
        </Card>
        <Card>
          <CardHeader title="Escalated Queries" />
          <p className="text-2xl font-semibold text-amber-200">
            {statsLoading ? "…" : stats.escalated}
          </p>
        </Card>
        <Card>
          <CardHeader title="Voice Sessions" />
          <p className="text-2xl font-semibold text-emerald-200">
            {statsLoading ? "…" : stats.sessions}
          </p>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <Card className="relative overflow-hidden">
          <CardHeader
            title="Queries per day"
            description="Last 7 days of activity"
          />
          <div className="mt-4 flex h-[140px] items-end gap-3">
            {stats.queriesPerDay.map((d) => (
              <motion.div
                key={d.date || d.day}
                title={`${d.day}: ${d.value}`}
                initial={{ height: 0 }}
                animate={{ height: `${Math.max(2, (d.value / peak) * 140)}px` }}
                transition={{ duration: 0.6, ease: "easeOut" }}
                className="flex-1 rounded-t-md bg-gradient-to-t from-accent-primary/10 via-accent-primary/70 to-accent-secondary/90"
              >
                <span className="sr-only">{d.value}</span>
              </motion.div>
            ))}
          </div>
          <div className="mt-2 flex justify-between text-[11px] text-text-secondary">
            {stats.queriesPerDay.map((d) => (
              <span key={d.date || d.day}>{d.day}</span>
            ))}
          </div>
        </Card>

        <Card>
          <CardHeader
            title="Escalation rate"
            description="Share of AI vs human handled"
          />
          <div className="mt-4 space-y-3">
            {stats.escalationRate.map((e) => (
              <div key={e.label} className="space-y-1">
                <div className="flex items-center justify-between text-xs text-text-secondary">
                  <span>{e.label}</span>
                  <span>{e.value}%</span>
                </div>
                <div className="h-2 rounded-full bg-white/5">
                  <div
                    className="h-2 rounded-full bg-gradient-to-r from-accent-secondary to-accent-primary"
                    style={{ width: `${e.value}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <Card>
        <CardHeader title="Recent queries" />

        {recentError && (
          <p className="py-3 text-xs text-amber-200">{recentError}</p>
        )}

        <Table>
          <THead>
            <TR>
              <TH>User</TH>
              <TH>Question</TH>
              <TH>Status</TH>
              <TH>Time</TH>
            </TR>
          </THead>
          <TBody>
            {recentLoading && (
              <TR>
                <TD colSpan={4} className="py-6 text-center text-xs text-text-secondary">
                  Loading…
                </TD>
              </TR>
            )}

            {!recentLoading && recent.length === 0 && !recentError && (
              <TR>
                <TD colSpan={4} className="py-6 text-center text-xs text-text-secondary">
                  Abhi koi sawal nahi aaya.
                </TD>
              </TR>
            )}

            {recent.map((q) => (
              <TR key={q.id}>
                <TD className="whitespace-nowrap text-[11px] text-text-secondary">
                  {q.user}
                </TD>
                <TD className="text-xs text-white">{q.question}</TD>
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
                  {formatTime(q.timestamp)}
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      </Card>
    </div>
  );
}
