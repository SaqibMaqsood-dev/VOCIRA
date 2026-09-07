"use client";

/**
 * Admin dashboard.
 *
 * Pehle yahan chaar chhote cards thay, aur do "chart" jo asal mein
 * divs thay: bars ke liye height wali div, aur ratio ke liye progress
 * bar. Na axis, na grid, na hover - kis din kitne sawal aaye, ye
 * sirf title attribute se pata chalta tha.
 *
 * Ab:
 *   KPI row        stat tiles - number bara, icon, aur jahan waqt
 *                  ka data hai wahan sparkline
 *   Trend          asli area chart - axis, grid, hover crosshair
 *   Part-to-whole  stacked bar (do slices ka pie ghalat hota hai)
 *
 * Rang dataviz validator se jaanche gaye hain - tafseel StackedBar
 * mein likhi hai.
 */

import {
  AlertTriangle,
  MessagesSquare,
  PhoneCall,
  TrendingUp,
} from "lucide-react";

import { Card, CardHeader } from "@/app/admin/_components/ui/Card";
import Badge from "@/app/admin/_components/ui/Badge";
import { Table, THead, TBody, TR, TH, TD } from "@/app/admin/_components/ui/Table";
import AreaChart from "@/app/admin/_components/charts/AreaChart";
import StackedBar from "@/app/admin/_components/charts/StackedBar";
import StatTile from "@/app/admin/_components/charts/StatTile";
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

  const spark = stats.queriesPerDay.map((d) => d.value);

  return (
    <div className="space-y-6 pb-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-white">
          Overview
        </h1>
        <p className="mt-1 text-xs text-text-secondary">
          Live metrics from Vocira&apos;s voice assistant.
        </p>
      </div>

      {statsError && (
        <Card className="border-amber-400/30">
          <p className="text-xs text-amber-200">{statsError}</p>
        </Card>
      )}

      {/* ---- KPI row ---- */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile
          label="Questions today"
          value={stats.today}
          hint="Since midnight"
          icon={MessagesSquare}
          loading={statsLoading}
        />
        <StatTile
          label="This week"
          value={stats.week}
          hint="Last 7 days"
          icon={TrendingUp}
          spark={spark}
          loading={statsLoading}
        />
        <StatTile
          label="Voice calls"
          value={stats.sessions}
          hint="Sessions started"
          icon={PhoneCall}
          accent="#199e70"
          loading={statsLoading}
        />
        <StatTile
          label="Escalated"
          value={stats.escalated}
          hint="Waiting for a human"
          icon={AlertTriangle}
          accent="#d95926"
          loading={statsLoading}
        />
      </div>

      {/* ---- charts ---- */}
      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader
            title="Questions per day"
            description="Last 7 days"
          />
          <div className="mt-2">
            <AreaChart
              data={stats.queriesPerDay}
              height={220}
              formatValue={(v) =>
                `${v} question${v === 1 ? "" : "s"}`
              }
            />
          </div>
        </Card>

        <Card>
          <CardHeader
            title="How questions end"
            description="AI answered vs handed to a person"
          />
          <div className="mt-6">
            <StackedBar data={stats.escalationRate} />
          </div>

          <div className="mt-6 border-t border-white/10 pt-4">
            <p className="text-[11px] uppercase tracking-[0.14em] text-text-secondary">
              Total questions
            </p>
            <p className="mt-1 text-2xl font-semibold text-white">
              {statsLoading ? "…" : stats.total}
            </p>
          </div>
        </Card>
      </div>

      {/* ---- recent ---- */}
      <Card>
        <CardHeader
          title="Recent questions"
          description="The last eight, newest first"
        />

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
                <TD
                  colSpan={4}
                  className="py-6 text-center text-xs text-text-secondary"
                >
                  Loading…
                </TD>
              </TR>
            )}

            {!recentLoading && recent.length === 0 && !recentError && (
              <TR>
                <TD
                  colSpan={4}
                  className="py-6 text-center text-xs text-text-secondary"
                >
                  No questions yet.
                </TD>
              </TR>
            )}

            {recent.map((q) => (
              <TR key={q.id}>
                <TD className="whitespace-nowrap text-[11px] text-text-secondary">
                  {q.user}
                </TD>
                <TD className="max-w-[420px] truncate text-xs text-white">
                  {q.question}
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
