"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import StatsCard from "@/components/StatsCard";
import CallTable from "@/components/CallTable";

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

        const accessToken = localStorage.getItem("access_token");

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

        const statsResponse = await fetch(
          `${API_URL}/livekit/sessions/stats`,
          {
            method: "GET",
            headers: {
              Authorization: `Bearer ${accessToken}`,
            },
          }
        );

        if (statsResponse.status === 401) {
          localStorage.removeItem("access_token");
          localStorage.removeItem("refresh_token");
          localStorage.removeItem("token_type");
          localStorage.removeItem("auth_response");

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

        const sessionsResponse = await fetch(
          `${API_URL}/livekit/sessions/?limit=20&skip=0`,
          {
            method: "GET",
            headers: {
              Authorization: `Bearer ${accessToken}`,
            },
          }
        );

        if (sessionsResponse.status === 401) {
          localStorage.removeItem("access_token");
          localStorage.removeItem("refresh_token");
          localStorage.removeItem("token_type");
          localStorage.removeItem("auth_response");

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

        setError(
          err instanceof Error
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

    let duration = "—";

    if (session.start_at && session.end_at) {
      const start = new Date(session.start_at);
      const end = new Date(session.end_at);

      if (
        !Number.isNaN(start.getTime()) &&
        !Number.isNaN(end.getTime())
      ) {
        const durationSeconds = Math.floor(
          (end.getTime() - start.getTime()) / 1000
        );

        if (durationSeconds >= 0) {
          const minutes = Math.floor(durationSeconds / 60);
          const seconds = durationSeconds % 60;

          duration = `${minutes}m ${seconds}s`;
        }
      }
    }

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

      // Backend currently doesn't provide handler
      handler: session.handler ?? "—",

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