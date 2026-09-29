"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import StatsCard from "@/components/StatsCard";
import CallTable from "@/components/CallTable";
import FullScreenLoader from "@/components/FullScreenLoader";

import { authFetch, clearSession, getAccessToken } from "@/lib/session";

const API_URL = process.env.NEXT_PUBLIC_API_URL;

// How many calls one page of the table holds. The stats card already
// says the true total; this only controls how many rows arrive per
// "Load more" click.
const PAGE_SIZE = 20;

// A native <option> ignores Tailwind classes in Chrome on Windows -
// it takes its colours from the OS unless they are set inline, which
// left the child names white on white. colorScheme on the <select>
// darkens the popup itself for the same reason.
const OPTION_STYLE = { backgroundColor: "#100944", color: "#ffffff" };

export default function DashboardPage() {
  const [sessions, setSessions] = useState([]);
  const [children, setChildren] = useState([]);

  // The child picked in the "My Children" list. It only shows that
  // child's details - the calls and stats always cover every child.
  const [selectedChild, setSelectedChild] = useState(null);

  const [stats, setStats] = useState({
    total_calls: 0,
    today_calls: 0,
    this_week_calls: 0,
  });

  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");

  // =========================================================
  // FETCH ONE PAGE OF SESSIONS
  //
  // Shared by the initial load and "Load more" - the only
  // difference is whether the results replace or extend the list,
  // and which loading flag they drive.
  // =========================================================

  const fetchSessions = async (skip) => {
    const sessionsResponse = await authFetch(
      `/livekit/sessions/?limit=${PAGE_SIZE}&skip=${skip}`,
      { method: "GET" }
    );

    if (sessionsResponse.status === 401) {
      clearSession();
      window.location.href = "/login";
      return null;
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

    return Array.isArray(sessionsData) ? sessionsData : [];
  };

  const loadMore = async () => {
    setLoadingMore(true);

    try {
      const nextPage = await fetchSessions(sessions.length);
      if (nextPage) {
        setSessions((prev) => [...prev, ...nextPage]);
      }
    } catch (err) {
      console.error("Load more failed:", err);
      setError(
        err instanceof TypeError
          ? "Could not reach the server. Please make sure the API Gateway is running."
          : err instanceof Error
            ? err.message
            : "Failed to load more calls."
      );
    } finally {
      setLoadingMore(false);
    }
  };

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

        const sessionsData = await fetchSessions(0);

        console.log("Sessions response:", sessionsData);

        // =====================================================
        // GET MY CHILDREN
        //
        // Best-effort - a guardian with no ERP link yet, or a
        // hiccup here, should never block the rest of the
        // dashboard from loading.
        // =====================================================

        try {
          const childrenResponse = await authFetch(
            "/livekit/children/",
            { method: "GET" }
          );

          if (childrenResponse.ok) {
            const childrenData = await childrenResponse.json();
            setChildren(childrenData?.children || []);
          }
        } catch (childErr) {
          console.error("Children fetch failed:", childErr);
        }

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

        setSessions(sessionsData || []);

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

  const callRows = sessions.map((session, index) => {
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

      // Most recent first, numbered in that same order - not the
      // raw UUID, which told a guardian nothing and no one ever
      // read one out loud.
      number: index + 1,

      title: session.title ?? "Voice Call",

      // What the call was actually about (e.g. "Zoya - Attendance").
      // Empty for calls made before this was tracked.
      topic: session.topic || "",

      start_at: session.start_at ?? null,

      end_at: session.end_at ?? null,

      status,

      duration,

      handler: session.handler || "—",

      time,
    };
  });

  const hasMore = sessions.length < stats.total_calls;

  if (loading) {
    return (
      <FullScreenLoader
        label="Loading your calls…"
        subLabel="Fetching your stats and call history"
      />
    );
  }

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
          MY CHILDREN
      ===================================================== */}

      {children.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{
            duration: 0.6,
            ease: "easeOut",
            delay: 0.03,
          }}
          className="mt-8"
        >
          <label
            htmlFor="child-filter"
            className="text-sm font-medium uppercase tracking-wide text-text-secondary"
          >
            My Children
          </label>

          <div className="mt-3 flex flex-wrap items-center gap-3">
            <select
              id="child-filter"
              value={selectedChild?.student_id ?? ""}
              onChange={(event) =>
                setSelectedChild(
                  children.find(
                    (child) => child.student_id === event.target.value
                  ) ?? null
                )
              }
              style={{ colorScheme: "dark" }}
              className="min-w-64 rounded-xl border border-white/10 bg-white/[0.05] px-4 py-2.5 text-sm text-text-primary outline-none transition hover:border-white/20 focus:border-primary/60"
            >
              <option value="" style={OPTION_STYLE}>
                All children ({children.length})
              </option>

              {children.map((child) => (
                <option
                  key={child.student_id}
                  value={child.student_id}
                  style={OPTION_STYLE}
                >
                  {child.name}
                  {child.class_name
                    ? ` — ${child.class_name}`
                    : child.program
                      ? ` — ${child.program}`
                      : ""}
                </option>
              ))}
            </select>

            {selectedChild && (
              <span className="text-xs text-text-secondary">
                {selectedChild.academic_year
                  ? `Academic year ${selectedChild.academic_year}`
                  : ""}
              </span>
            )}
          </div>
        </motion.div>
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
          value={stats.total_calls}
          accent="primary"
        />

        <StatsCard
          label="Today's Calls"
          value={stats.today_calls}
          accent="secondary"
        />

        <StatsCard
          label="This Week"
          value={stats.this_week_calls}
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
        <CallTable rows={callRows} />

        {hasMore && (
          <div className="mt-4 flex justify-center">
            <button
              type="button"
              onClick={loadMore}
              disabled={loadingMore}
              className="rounded-xl border border-white/10 bg-white/[0.05] px-5 py-2.5 text-sm font-medium text-text-primary transition hover:border-white/20 hover:bg-white/[0.08] disabled:cursor-not-allowed disabled:opacity-60"
            >
              {loadingMore
                ? "Loading…"
                : `Load more (${sessions.length} of ${stats.total_calls})`}
            </button>
          </div>
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
