"use client";

import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import StatsCard from "@/components/StatsCard";
import CallTable from "@/components/CallTable";
import FullScreenLoader from "@/components/FullScreenLoader";

import { authFetch, clearSession, getAccessToken } from "@/lib/session";
import { localDateKey, parseServerTime } from "@/lib/time";

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

// A day picked on the calendar ("2026-09-30") as the two UTC instants
// that bound it on the viewer's own clock - so a call at 1am Pakistan
// time counts on that day, not the one before (UTC).
function dayRange(dateKey) {
  const [year, month, day] = dateKey.split("-").map(Number);
  return {
    start: new Date(year, month - 1, day).toISOString(),
    end: new Date(year, month - 1, day + 1).toISOString(),
  };
}

// "30 Sep 2026"
function formatDay(dateKey) {
  const [year, month, day] = dateKey.split("-").map(Number);
  return new Date(year, month - 1, day).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

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

  // The day picked on the Call History calendar ("" = every day), and
  // how many calls the last page brought - a full page means there
  // may be more for that day. The stats' total counts every day, so
  // it cannot tell.
  const [callDate, setCallDate] = useState("");
  const [lastPageSize, setLastPageSize] = useState(0);
  const [loadingDay, setLoadingDay] = useState(false);

  // Picking days quickly must not let a slower, older answer
  // overwrite the newer one.
  const dayRequest = useRef(0);

  // =========================================================
  // FETCH ONE PAGE OF SESSIONS
  //
  // Shared by the initial load and "Load more" - the only
  // difference is whether the results replace or extend the list,
  // and which loading flag they drive.
  // =========================================================

  const fetchSessions = async (skip, date = callDate) => {
    let query = `limit=${PAGE_SIZE}&skip=${skip}`;

    if (date) {
      const { start, end } = dayRange(date);
      query += `&start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`;
    }

    const sessionsResponse = await authFetch(
      `/livekit/sessions/?${query}`,
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

  // A day picked on the calendar - or "" for every day again.
  const changeDate = async (date) => {
    const request = ++dayRequest.current;

    setCallDate(date);
    setLoadingDay(true);
    setError("");

    try {
      const firstPage = await fetchSessions(0, date);
      if (firstPage && request === dayRequest.current) {
        setSessions(firstPage);
        setLastPageSize(firstPage.length);
      }
    } catch (err) {
      if (request !== dayRequest.current) return;
      console.error("Loading that day's calls failed:", err);
      setError(
        err instanceof TypeError
          ? "Could not reach the server. Please make sure the API Gateway is running."
          : err instanceof Error
            ? err.message
            : "Failed to load calls for that day."
      );
    } finally {
      if (request === dayRequest.current) setLoadingDay(false);
    }
  };

  const loadMore = async () => {
    setLoadingMore(true);

    try {
      const nextPage = await fetchSessions(sessions.length);
      if (nextPage) {
        setSessions((prev) => [...prev, ...nextPage]);
        setLastPageSize(nextPage.length);
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
        // "Today" and "this week" on the viewer's own clock - left
        // to the server they were UTC's, and in Pakistan the UTC day
        // only starts at 5am, so the card disagreed with the calendar.
        const now = new Date();
        const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        const weekStart = new Date(todayStart);
        weekStart.setDate(todayStart.getDate() - ((todayStart.getDay() + 6) % 7));

        const statsResponse = await authFetch(
          `/livekit/sessions/stats?today_start=${encodeURIComponent(todayStart.toISOString())}` +
            `&week_start=${encodeURIComponent(weekStart.toISOString())}`,
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
        setLastPageSize((sessionsData || []).length);

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
        const start = parseServerTime(session.start_at);
        const end = parseServerTime(session.end_at);

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
      const date = parseServerTime(session.start_at);

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

  const hasMore = callDate
    ? lastPageSize === PAGE_SIZE
    : sessions.length < stats.total_calls;

  const todayKey = localDateKey(new Date());

  // Where "Most recent calls" used to be: pick a day, see that day.
  const dayPicker = (
    <div className="flex flex-wrap items-center gap-2">
      <label htmlFor="call-date" className="text-xs text-text-secondary">
        {callDate ? "Calls on" : "Most recent calls · pick a day"}
      </label>

      <input
        id="call-date"
        type="date"
        value={callDate}
        max={todayKey}
        disabled={loadingDay}
        onChange={(event) => changeDate(event.target.value)}
        // Open the calendar on a click anywhere in the box, not only
        // on its small icon.
        onClick={(event) => {
          try {
            event.currentTarget.showPicker?.();
          } catch {
            /* the browser opens it on its own */
          }
        }}
        style={{ colorScheme: "dark" }}
        className="cursor-pointer rounded-lg border border-white/10 bg-white/[0.06] px-3 py-1.5 text-xs text-text-primary outline-none transition hover:border-white/20 focus:border-accent-primary/60 disabled:opacity-60"
      />

      {callDate && (
        <button
          type="button"
          onClick={() => changeDate("")}
          disabled={loadingDay}
          className="rounded-lg border border-white/10 bg-white/[0.04] px-3 py-1.5 text-xs font-medium text-text-secondary transition hover:border-white/20 hover:text-text-primary disabled:opacity-60"
        >
          All dates
        </button>
      )}
    </div>
  );

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
        <CallTable
          rows={loadingDay ? [] : callRows}
          headerRight={dayPicker}
          emptyText={
            loadingDay
              ? "Loading…"
              : callDate
                ? `No calls on ${formatDay(callDate)}.`
                : ""
          }
        />

        {hasMore && !loadingDay && (
          <div className="mt-4 flex justify-center">
            <button
              type="button"
              onClick={loadMore}
              disabled={loadingMore}
              className="rounded-xl border border-white/10 bg-white/[0.05] px-5 py-2.5 text-sm font-medium text-text-primary transition hover:border-white/20 hover:bg-white/[0.08] disabled:cursor-not-allowed disabled:opacity-60"
            >
              {loadingMore
                ? "Loading…"
                : callDate
                  ? "Load more"
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
