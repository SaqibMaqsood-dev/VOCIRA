"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import StatsCard from "@/components/StatsCard";
import CallTable from "@/components/CallTable";

import { authFetch, clearSession, getAccessToken } from "@/lib/session";

const API_URL = process.env.NEXT_PUBLIC_API_URL;

export default function DashboardPage() {
  const [sessions, setSessions] = useState([]);

  const [stats, setStats] = useState({
    total_calls: 0,
    today_calls: 0,
    this_week_calls: 0,
  });

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const fetchDashboardData = async () => {
      try {
        setLoading(true);
        setError("");

        const accessToken = getAccessToken();

        if (!accessToken) {
          window.location.href = "/login";
          return;
        }

        if (!API_URL) {
          setError("API URL is not configured.");
          return;
        }

        // =====================================================
        // GET DASHBOARD STATISTICS
        // =====================================================

        // authFetch renews an expired access token and retries, so
        // a 401 here means the refresh token is gone too.
        const statsResponse = await authFetch(
          "/livekit/sessions/stats",
          { method: "GET" }
        );

        if (statsResponse.status === 401) {
          clearSession();

          window.location.href = "/login";
          return;
        }

        if (!statsResponse.ok) {
          const errorData = await statsResponse.text();

          console.error("Stats API failed:", {
            status: statsResponse.status,
            statusText: statsResponse.statusText,
            body: errorData,
            url: statsResponse.url,
          });

          throw new Error(
            `Failed to load dashboard statistics (${statsResponse.status})`
          );
        }

        const statsData = await statsResponse.json();

        console.log("Stats response:", statsData);

        // =====================================================
        // GET USER'S SESSIONS
        // =====================================================

        const sessionsResponse = await authFetch(
          "/livekit/sessions/?limit=20&skip=0",
          { method: "GET" }
        );

        if (sessionsResponse.status === 401) {
          clearSession();

          window.location.href = "/login";
          return;
        }

        if (!sessionsResponse.ok) {
          const errorData = await sessionsResponse.text();

          console.error("Sessions API failed:", {
            status: sessionsResponse.status,
            statusText: sessionsResponse.statusText,
            body: errorData,
            url: sessionsResponse.url,
          });

          throw new Error(
            `Failed to load call history (${sessionsResponse.status})`
          );
        }

        const sessionsData = await sessionsResponse.json();

        console.log("Sessions response:", sessionsData);

        // =====================================================
        // SAVE STATS
        // =====================================================

        setStats({
          total_calls: Number(statsData?.total_calls) || 0,
          today_calls: Number(statsData?.today_calls) || 0,
          this_week_calls: Number(statsData?.this_week_calls) || 0,
        });

        // =====================================================
        // SAVE SESSIONS
        // =====================================================

        setSessions(
          Array.isArray(sessionsData)
            ? sessionsData
            : []
        );

      } catch (err) {
        console.error("Dashboard error:", err);

        // fetch() throws a TypeError on network failure, and its
        // message is "Failed to fetch" - which tells the user
        // nothing. The usual cause is simply that the backend is
        // not running.
        setError(
          err instanceof TypeError
            ? "Could not reach the server. Please make sure the API Gateway is running."
            : err instanceof Error
              ? err.message
              : "Failed to load dashboard."
        );

        // Keep dashboard usable
        setStats({
          total_calls: 0,
          today_calls: 0,
          this_week_calls: 0,
        });

        setSessions([]);
      } finally {
        setLoading(false);
      }
    };

    fetchDashboardData();
  }, []);

  // =========================================================
  // CONVERT BACKEND SESSIONS → CALL TABLE ROWS
  // =========================================================

  const callRows = sessions.map((session) => {
    // =======================================================
    // DURATION
    // =======================================================

    // The backend now returns duration_seconds directly. The old
    // calculation is kept as a fallback, in case that field is ever
    // missing.
    let seconds = session.duration_seconds;

    if (seconds === null || seconds === undefined) {
      if (session.start_at && session.end_at) {
        const start = new Date(session.start_at);
        const end = new Date(session.end_at);

        if (!Number.isNaN(start.getTime()) && !Number.isNaN(end.getTime())) {
          seconds = Math.floor((end.getTime() - start.getTime()) / 1000);
        }
      }
    }

    // A call in progress has no duration - it is still growing.
    // "—" would not say whether the data is missing or the call is
    // ongoing, so we spell it out.
    const duration =
      seconds === null || seconds === undefined || seconds < 0
        ? session.status === "active"
          ? "In progress"
          : "—"
        : formatDuration(seconds);

    // =======================================================
    // TIME
    // =======================================================

    let time = "—";

    if (session.start_at) {
      const date = new Date(session.start_at);

      if (!Number.isNaN(date.getTime())) {
        time = date.toLocaleString();
      }
    }

    // =======================================================
    // STATUS
    // =======================================================

    let status = "—";

    if (session.status) {
      status = String(session.status);

      // Handles enum responses such as:
      // "active"
      // "closed"
      status = status.toLowerCase();

      // Optional display names
      if (status === "active") {
        status = "Active";
      } else if (status === "closed") {
        status = "Closed";
      }
    }

    // =======================================================
    // RETURN ROW
    // =======================================================

    return {
      id: session.id ?? "—",

      title: session.title ?? "Voice Call",

      start_at: session.start_at ?? null,

      end_at: session.end_at ?? null,

      status,

      duration,

      handler: session.handler || "—",

      time,
    };
  });

  return (
    <div className="page-shell flex flex-col justify-center">

      {/* ==========================This problem is solved.===========================
          HEADER
      ===================================================== */}

      <motion.div
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{
          duration: 0.55,
          ease: "easeOut",
        }}
      >
        <h1 className="text-2xl font-semibold tracking-tight text-text-primary sm:text-3xl">
          My Calls
        </h1>

        <p className="mt-3 max-w-2xl text-sm leading-6 text-text-secondary sm:text-base">
          Track your voice sessions and call history.
        </p>
      </motion.div>

      {/* =====================================================
          ERROR
      ===================================================== */}

      {error && (
        <div className="mt-6 rounded-xl border border-red-400/20 bg-red-400/10 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* =====================================================
          STATS
      ===================================================== */}

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{
          duration: 0.6,
          ease: "easeOut",
          delay: 0.06,
        }}
        className="mt-10 grid gap-4 sm:grid-cols-3"
      >
        <StatsCard
          label="Total Calls"
          value={loading ? "—" : stats.total_calls}
          accent="primary"
        />

        <StatsCard
          label="Today's Calls"
          value={loading ? "—" : stats.today_calls}
          accent="secondary"
        />

        <StatsCard
          label="This Week"
          value={loading ? "—" : stats.this_week_calls}
          accent="primary"
        />
      </motion.div>

      {/* =====================================================
          CALL HISTORY
          ALWAYS SHOW TABLE AFTER LOADING
      ===================================================== */}

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{
          duration: 0.6,
          ease: "easeOut",
          delay: 0.12,
        }}
        className="mt-6"
      >
        {loading ? (
          <div className="glass p-6 text-sm text-text-secondary">
            Loading your calls...
          </div>
        ) : (
          <CallTable rows={callRows} />
        )}
      </motion.div>

    </div>
  );
}


/**
 * Make a number of seconds readable.
 *
 * It always wrote "Xm Ys" before, so a 34 second call showed as
 * "0m 34s" - awkward to read, with the "0" taking up room for
 * nothing.
 *
 *     34    ->  34s
 *     124   ->  2m 4s
 *     180   ->  3m
 *     3661  ->  1h 1m
 */
function formatDuration(total) {
  if (total < 60) return `${total}s`;

  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const seconds = total % 60;

  // Seconds are meaningless at the scale of hours - nobody reads
  // "1h 1m 7s"
  if (hours > 0) {
    return minutes > 0 ? `${hours}h ${minutes}m` : `${hours}h`;
  }

  return seconds > 0 ? `${minutes}m ${seconds}s` : `${minutes}m`;
}
