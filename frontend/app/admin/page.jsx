"use client";

import { useCallback, useEffect, useState } from "react";
import { motion } from "framer-motion";

import { Card, CardHeader } from "@/app/admin/_components/ui/Card";
import Badge from "@/app/admin/_components/ui/Badge";
import {
  Table,
  THead,
  TBody,
  TR,
  TH,
  TD,
} from "@/app/admin/_components/ui/Table";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  "http://127.0.0.1:8001";

const EMPTY_STATS = {
  total_sessions: 0,
  active_sessions: 0,
  closed_sessions: 0,
  total_messages: 0,
  total_escalations: 0,
  pending_escalations: 0,
  resolved_escalations: 0,
};

export default function AdminDashboardPage() {
  const [stats, setStats] =
    useState(EMPTY_STATS);

  const [recentSessions, setRecentSessions] =
    useState([]);

  const [loading, setLoading] =
    useState(true);

  const [error, setError] =
    useState("");

  const [refreshing, setRefreshing] =
    useState(false);

  /* ============================================================
     FETCH DASHBOARD
  ============================================================ */

  const fetchDashboard = useCallback(
    async ({ silent = false } = {}) => {
      const accessToken =
        typeof window !== "undefined"
          ? localStorage.getItem("access_token")
          : null;

      if (!accessToken) {
        setError(
          "Admin authentication token was not found."
        );

        setLoading(false);
        return;
      }

      if (!silent) {
        setRefreshing(true);
      }

      try {
        /* ------------------------------------------------------
           DASHBOARD STATS
        ------------------------------------------------------ */

        const dashboardResponse =
          await fetch(
            `${API_BASE_URL}/admin/dashboard`,
            {
              method: "GET",

              headers: {
                Accept:
                  "application/json",
                Authorization:
                  `Bearer ${accessToken}`,
              },

              cache: "no-store",
            }
          );

        const dashboardText =
          await dashboardResponse.text();

        let dashboardData = {};

        try {
          dashboardData =
            dashboardText
              ? JSON.parse(
                  dashboardText
                )
              : {};
        } catch {
          throw new Error(
            `Invalid dashboard response (${dashboardResponse.status}).`
          );
        }

        /* ------------------------------------------------------
           AUTH
        ------------------------------------------------------ */

        if (
          dashboardResponse.status ===
          401
        ) {
          throw new Error(
            "Your admin session has expired. Please log in again."
          );
        }

        if (
          dashboardResponse.status ===
          403
        ) {
          throw new Error(
            "Admin access required."
          );
        }

        if (
          !dashboardResponse.ok
        ) {
          throw new Error(
            dashboardData?.detail ||
              `Failed to load dashboard (${dashboardResponse.status}).`
          );
        }

        setStats({
          ...EMPTY_STATS,
          ...dashboardData,
        });

        /* ------------------------------------------------------
           RECENT SESSIONS
           
           We already have the /admin/sessions endpoint.
           Use it for the recent activity table.
        ------------------------------------------------------ */

        const sessionsResponse =
          await fetch(
            `${API_BASE_URL}/admin/sessions?limit=5&skip=0`,
            {
              method: "GET",

              headers: {
                Accept:
                  "application/json",
                Authorization:
                  `Bearer ${accessToken}`,
              },

              cache: "no-store",
            }
          );

        const sessionsText =
          await sessionsResponse.text();

        let sessionsData = [];

        try {
          sessionsData =
            sessionsText
              ? JSON.parse(
                  sessionsText
                )
              : [];
        } catch {
          throw new Error(
            `Invalid sessions response (${sessionsResponse.status}).`
          );
        }

        if (
          sessionsResponse.status ===
          401
        ) {
          throw new Error(
            "Your admin session has expired. Please log in again."
          );
        }

        if (
          sessionsResponse.status ===
          403
        ) {
          throw new Error(
            "Admin access required."
          );
        }

        if (
          !sessionsResponse.ok
        ) {
          throw new Error(
            sessionsData?.detail ||
              `Failed to load sessions (${sessionsResponse.status}).`
          );
        }

        setRecentSessions(
          Array.isArray(
            sessionsData
          )
            ? sessionsData
            : []
        );

        setError("");
      } catch (requestError) {
        console.error(
          "❌ Dashboard request failed:",
          requestError
        );

        setError(
          requestError?.message ||
            "Failed to load dashboard."
        );
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    []
  );

  /* ============================================================
     INITIAL LOAD
  ============================================================ */

  useEffect(() => {
    fetchDashboard();

    const interval =
      setInterval(() => {
        fetchDashboard({
          silent: true,
        });
      }, 10000);

    return () => {
      clearInterval(interval);
    };
  }, [fetchDashboard]);

  /* ============================================================
     HELPERS
  ============================================================ */

  const formatStatus = (
    status
  ) => {
    if (!status) {
      return "Unknown";
    }

    const value =
      typeof status === "object"
        ? status.value
        : status;

    const normalized =
      String(value).toLowerCase();

    if (
      normalized ===
      "active"
    ) {
      return "Active";
    }

    if (
      normalized ===
      "closed"
    ) {
      return "Closed";
    }

    return String(value);
  };

  const getStatusVariant = (
    status
  ) => {
    const value =
      typeof status === "object"
        ? status.value
        : status;

    const normalized =
      String(
        value || ""
      ).toLowerCase();

    if (
      normalized ===
      "active"
    ) {
      return "warning";
    }

    if (
      normalized ===
      "closed"
    ) {
      return "success";
    }

    return "neutral";
  };

  const formatDateTime = (
    value
  ) => {
    if (!value) {
      return "—";
    }

    const date =
      new Date(value);

    if (
      Number.isNaN(
        date.getTime()
      )
    ) {
      return String(value);
    }

    return date.toLocaleString();
  };

  const calculatePercentage = (
    value,
    total
  ) => {
    if (!total) {
      return 0;
    }

    return Math.round(
      (value / total) * 100
    );
  };

  /* ============================================================
     LOADING
  ============================================================ */

  if (loading) {
    return (
      <div className="space-y-6">

        <div>
          <h1 className="text-xl font-semibold text-white">
            Overview
          </h1>

          <p className="mt-1 text-xs text-text-secondary">
            High-level metrics across Vocira&apos;s AI assistant.
          </p>
        </div>

        <div className="rounded-xl border border-white/10 bg-white/[0.02] px-4 py-16 text-center">

          <p className="text-sm text-text-secondary">
            Loading dashboard...
          </p>

        </div>

      </div>
    );
  }

  /* ============================================================
     DASHBOARD
  ============================================================ */

  return (
    <div className="space-y-6">

      {/* ========================================================
          HEADER
      ======================================================== */}

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">

        <div>

          <h1 className="text-xl font-semibold text-white">
            Overview
          </h1>

          <p className="mt-1 text-xs text-text-secondary">
            High-level metrics across Vocira&apos;s AI assistant.
          </p>

        </div>

        <button
          type="button"
          onClick={() =>
            fetchDashboard()
          }
          disabled={refreshing}
          className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-xs text-text-secondary transition hover:bg-white/[0.06] hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
        >
          {refreshing
            ? "Refreshing..."
            : "Refresh"}
        </button>

      </div>

      {/* ========================================================
          ERROR
      ======================================================== */}

      {error && (
        <div className="rounded-lg border border-red-400/20 bg-red-400/5 px-4 py-3 text-xs text-red-200">
          {error}
        </div>
      )}

      {/* ========================================================
          MAIN STAT CARDS
      ======================================================== */}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">

        {/* TOTAL SESSIONS */}

        <Card>
          <CardHeader
            title="Total Sessions"
          />

          <p className="text-2xl font-semibold text-white">
            {stats.total_sessions}
          </p>

          <p className="mt-1 text-[11px] text-text-secondary">
            All recorded sessions
          </p>
        </Card>

        {/* ACTIVE SESSIONS */}

        <Card>
          <CardHeader
            title="Active Sessions"
          />

          <p className="text-2xl font-semibold text-amber-200">
            {stats.active_sessions}
          </p>

          <p className="mt-1 text-[11px] text-text-secondary">
            Currently active
          </p>
        </Card>

        {/* TOTAL MESSAGES */}

        <Card>
          <CardHeader
            title="Total Messages"
          />

          <p className="text-2xl font-semibold text-white">
            {stats.total_messages}
          </p>

          <p className="mt-1 text-[11px] text-text-secondary">
            Messages processed
          </p>
        </Card>

        {/* ESCALATIONS */}

        <Card>
          <CardHeader
            title="Escalations"
          />

          <p className="text-2xl font-semibold text-amber-200">
            {stats.total_escalations}
          </p>

          <p className="mt-1 text-[11px] text-text-secondary">
            {stats.pending_escalations} pending
          </p>
        </Card>

      </div>

      {/* ========================================================
          SECONDARY STATS
      ======================================================== */}

      <div className="grid gap-4 sm:grid-cols-3">

        <Card>
          <CardHeader
            title="Closed Sessions"
          />

          <p className="text-2xl font-semibold text-emerald-200">
            {stats.closed_sessions}
          </p>

          <p className="mt-1 text-[11px] text-text-secondary">
            Completed sessions
          </p>
        </Card>

        <Card>
          <CardHeader
            title="Pending Escalations"
          />

          <p className="text-2xl font-semibold text-amber-200">
            {stats.pending_escalations}
          </p>

          <p className="mt-1 text-[11px] text-text-secondary">
            Waiting for admin
          </p>
        </Card>

        <Card>
          <CardHeader
            title="Resolved Escalations"
          />

          <p className="text-2xl font-semibold text-emerald-200">
            {stats.resolved_escalations}
          </p>

          <p className="mt-1 text-[11px] text-text-secondary">
            Successfully handled
          </p>
        </Card>

      </div>

      {/* ========================================================
          SESSION DISTRIBUTION + ESCALATION RATE
      ======================================================== */}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">

        {/* SESSION DISTRIBUTION */}

        <Card className="relative overflow-hidden">

          <CardHeader
            title="Session distribution"
            description="Current AI session lifecycle"
          />

          <div className="mt-6 space-y-4">

            {/* ACTIVE */}

            <div>

              <div className="mb-1 flex items-center justify-between text-xs">

                <span className="text-text-secondary">
                  Active
                </span>

                <span className="text-white">
                  {stats.active_sessions}
                </span>

              </div>

              <div className="h-2 overflow-hidden rounded-full bg-white/5">

                <motion.div
                  initial={{
                    width: 0,
                  }}
                  animate={{
                    width: `${calculatePercentage(
                      stats.active_sessions,
                      stats.total_sessions
                    )}%`,
                  }}
                  transition={{
                    duration: 0.7,
                    ease: "easeOut",
                  }}
                  className="h-full rounded-full bg-gradient-to-r from-accent-secondary to-accent-primary"
                />

              </div>

            </div>

            {/* CLOSED */}

            <div>

              <div className="mb-1 flex items-center justify-between text-xs">

                <span className="text-text-secondary">
                  Closed
                </span>

                <span className="text-white">
                  {stats.closed_sessions}
                </span>

              </div>

              <div className="h-2 overflow-hidden rounded-full bg-white/5">

                <motion.div
                  initial={{
                    width: 0,
                  }}
                  animate={{
                    width: `${calculatePercentage(
                      stats.closed_sessions,
                      stats.total_sessions
                    )}%`,
                  }}
                  transition={{
                    duration: 0.7,
                    ease: "easeOut",
                  }}
                  className="h-full rounded-full bg-gradient-to-r from-accent-secondary to-accent-primary"
                />

              </div>

            </div>

          </div>

          <div className="mt-6 grid grid-cols-2 gap-3">

            <div className="rounded-lg border border-white/10 bg-white/[0.02] p-3">

              <p className="text-[10px] uppercase tracking-wide text-text-secondary">
                Total
              </p>

              <p className="mt-1 text-lg font-semibold text-white">
                {stats.total_sessions}
              </p>

            </div>

            <div className="rounded-lg border border-white/10 bg-white/[0.02] p-3">

              <p className="text-[10px] uppercase tracking-wide text-text-secondary">
                Closed
              </p>

              <p className="mt-1 text-lg font-semibold text-emerald-200">
                {stats.closed_sessions}
              </p>

            </div>

          </div>

        </Card>

        {/* ESCALATION RATE */}

        <Card>

          <CardHeader
            title="Escalation rate"
            description="Share of escalations by status"
          />

          <div className="mt-4 space-y-4">

            {/* PENDING */}

            <div className="space-y-1">

              <div className="flex items-center justify-between text-xs text-text-secondary">

                <span>
                  Pending
                </span>

                <span>
                  {calculatePercentage(
                    stats.pending_escalations,
                    stats.total_escalations
                  )}
                  %
                </span>

              </div>

              <div className="h-2 rounded-full bg-white/5">

                <div
                  className="h-2 rounded-full bg-gradient-to-r from-accent-secondary to-accent-primary"
                  style={{
                    width: `${calculatePercentage(
                      stats.pending_escalations,
                      stats.total_escalations
                    )}%`,
                  }}
                />

              </div>

            </div>

            {/* RESOLVED */}

            <div className="space-y-1">

              <div className="flex items-center justify-between text-xs text-text-secondary">

                <span>
                  Resolved
                </span>

                <span>
                  {calculatePercentage(
                    stats.resolved_escalations,
                    stats.total_escalations
                  )}
                  %
                </span>

              </div>

              <div className="h-2 rounded-full bg-white/5">

                <div
                  className="h-2 rounded-full bg-gradient-to-r from-accent-secondary to-accent-primary"
                  style={{
                    width: `${calculatePercentage(
                      stats.resolved_escalations,
                      stats.total_escalations
                    )}%`,
                  }}
                />

              </div>

            </div>

          </div>

        </Card>

      </div>

      {/* ========================================================
          RECENT SESSIONS
      ======================================================== */}

      <Card>

        <CardHeader
          title="Recent sessions"
          description="Latest activity from Vocira"
        />

        {recentSessions.length === 0 ? (

          <div className="px-4 py-10 text-center">

            <p className="text-sm text-text-secondary">
              No sessions found.
            </p>

          </div>

        ) : (

          <Table>

            <THead>

              <TR>

                <TH>
                  Session
                </TH>

                <TH>
                  User
                </TH>

                <TH>
                  Title
                </TH>

                <TH>
                  Handler
                </TH>

                <TH>
                  Status
                </TH>

                <TH>
                  Started
                </TH>

              </TR>

            </THead>

            <TBody>

              {recentSessions.map(
                (session) => {

                  const handler =
                    typeof session.handler ===
                    "object"
                      ? session.handler?.value
                      : session.handler;

                  return (
                    <TR
                      key={session.id}
                    >

                      <TD className="whitespace-nowrap font-mono text-[10px] text-text-secondary">
                        {session.id}
                      </TD>

                      <TD className="whitespace-nowrap font-mono text-[10px] text-text-secondary">
                        {session.user_id ||
                          "Guest"}
                      </TD>

                      <TD className="max-w-[240px] truncate text-xs text-white">
                        {session.title ||
                          "Untitled session"}
                      </TD>

                      <TD className="text-xs text-text-secondary">
                        {handler
                          ? String(
                              handler
                            )
                              .charAt(
                                0
                              )
                              .toUpperCase() +
                            String(
                              handler
                            ).slice(
                              1
                            )
                          : "—"}
                      </TD>

                      <TD>

                        <Badge
                          label={formatStatus(
                            session.status
                          )}
                          variant={getStatusVariant(
                            session.status
                          )}
                        />

                      </TD>

                      <TD className="whitespace-nowrap text-[11px] text-text-secondary">
                        {formatDateTime(
                          session.start_at
                        )}
                      </TD>

                    </TR>
                  );
                }
              )}

            </TBody>

          </Table>

        )}

      </Card>

      {/* ========================================================
          AUTO REFRESH
      ======================================================== */}

      <div className="flex items-center justify-end gap-2 text-[10px] text-text-secondary/60">

        <span
          className={`h-1.5 w-1.5 rounded-full ${
            refreshing
              ? "animate-pulse bg-amber-300"
              : "bg-emerald-400"
          }`}
        />

        <span>
          Dashboard auto-refreshes every 10 seconds
        </span>

      </div>

    </div>
  );
}