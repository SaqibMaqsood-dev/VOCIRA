"use client";

import { motion } from "framer-motion";
import { Card, CardHeader } from "@/app/admin/_components/ui/Card";
import Badge from "@/app/admin/_components/ui/Badge";
import { Table, THead, TBody, TR, TH, TD } from "@/app/admin/_components/ui/Table";
import {
  dashboardStats,
  dashboardQueriesPerDay,
  dashboardEscalationRate,
  recentQueries
} from "@/app/admin/data";

export default function AdminDashboardPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-white">Overview</h1>
        <p className="mt-1 text-xs text-text-secondary">
          High-level metrics across Vocira&apos;s AI assistant.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader title="Total Queries Today" />
          <p className="text-2xl font-semibold text-white">{dashboardStats.today}</p>
        </Card>
        <Card>
          <CardHeader title="Total Queries This Week" />
          <p className="text-2xl font-semibold text-white">{dashboardStats.week}</p>
        </Card>
        <Card>
          <CardHeader title="Escalated Queries" />
          <p className="text-2xl font-semibold text-amber-200">
            {dashboardStats.escalated}
          </p>
        </Card>
        <Card>
          <CardHeader title="Knowledge Articles" />
          <p className="text-2xl font-semibold text-emerald-200">
            {dashboardStats.articles}
          </p>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <Card className="relative overflow-hidden">
          <CardHeader title="Queries per day" description="Last 7 days of activity" />
          <div className="mt-4 flex items-end gap-3">
            {dashboardQueriesPerDay.map((d) => (
              <motion.div
                key={d.day}
                initial={{ height: 0 }}
                animate={{ height: `${(d.value / 200) * 140}px` }}
                transition={{ duration: 0.6, ease: "easeOut" }}
                className="flex-1 rounded-t-md bg-gradient-to-t from-accent-primary/10 via-accent-primary/70 to-accent-secondary/90"
              >
                <span className="sr-only">{d.value}</span>
              </motion.div>
            ))}
          </div>
          <div className="mt-2 flex justify-between text-[11px] text-text-secondary">
            {dashboardQueriesPerDay.map((d) => (
              <span key={d.day}>{d.day}</span>
            ))}
          </div>
        </Card>

        <Card>
          <CardHeader
            title="Escalation rate"
            description="Share of AI vs human handled"
          />
          <div className="mt-4 space-y-3">
            {dashboardEscalationRate.map((e) => (
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
            {recentQueries.map((q) => (
              <TR key={q.question}>
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
                  {q.time}
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      </Card>
    </div>
  );
}

