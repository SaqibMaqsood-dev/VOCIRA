"use client";

import {
  useEffect,
  useState,
} from "react";

import { motion } from "framer-motion";

import StatsCard from "@/components/StatsCard";
import CallTable from "@/components/CallTable";


// ============================================================
// API CONFIGURATION
// ============================================================
//
// IMPORTANT:
//
// Frontend communicates ONLY with the Gateway.
//
// Gateway:
//     http://127.0.0.1:9000
//
// Gateway forwards:
//
//     /livekit/*
//             ↓
//     LiveKit_RAG service :8001
//
// Therefore DO NOT use port 8001 here.
// ============================================================

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  "http://127.0.0.1:9000";


// ============================================================
// DASHBOARD PAGE
// ============================================================

export default function DashboardPage() {

  // ==========================================================
  // STATE
  // ==========================================================

  const [sessions, setSessions] =
    useState([]);

  const [stats, setStats] =
    useState({
      total_calls: 0,
      today_calls: 0,
      this_week_calls: 0,
    });

  const [loading, setLoading] =
    useState(true);

  const [error, setError] =
    useState("");


  // ==========================================================
  // LOGOUT / AUTH FAILURE
  // ==========================================================

  const handleAuthFailure = () => {

    console.warn(
      "🔐 Authentication failed. Redirecting to login..."
    );

    localStorage.removeItem(
      "access_token"
    );

    localStorage.removeItem(
      "refresh_token"
    );

    localStorage.removeItem(
      "token_type"
    );

    localStorage.removeItem(
      "auth_response"
    );

    window.location.href =
      "/login";
  };


  // ==========================================================
  // FETCH DASHBOARD DATA
  // ==========================================================

  useEffect(() => {

    let mounted = true;

    const fetchDashboardData =
      async () => {

        try {

          setLoading(true);
          setError("");


          // ==================================================
          // ACCESS TOKEN
          // ==================================================

          const accessToken =
            localStorage.getItem(
              "access_token"
            );


          if (!accessToken) {

            window.location.href =
              "/login";

            return;
          }


          // ==================================================
          // API URL
          // ==================================================

          if (!API_BASE_URL) {

            throw new Error(
              "API URL is not configured."
            );
          }


          // ==================================================
          // HEADERS
          // ==================================================

          const headers = {

            Authorization:
              `Bearer ${accessToken}`,

            Accept:
              "application/json",

            "Content-Type":
              "application/json",
          };


          // ==================================================
          // DEBUG
          // ==================================================

          console.log(
            "========================================"
          );

          console.log(
            "📊 DASHBOARD API"
          );

          console.log(
            "🌐 Gateway:",
            API_BASE_URL
          );

          console.log(
            "========================================"
          );


          // ==================================================
          // GET DASHBOARD STATS
          // ==================================================
          //
          // Gateway:
          //
          // GET /livekit/sessions/stats
          //
          // Gateway -> LiveKit_RAG :8001
          // ==================================================

          const statsEndpoint =
            `${API_BASE_URL}/livekit/sessions/stats`;


          console.log(
            "📊 Fetching stats:",
            statsEndpoint
          );


          const statsResponse =
            await fetch(
              statsEndpoint,
              {
                method: "GET",
                headers,
              }
            );


          // ==================================================
          // AUTH FAILURE
          // ==================================================

          if (
            statsResponse.status === 401
          ) {

            handleAuthFailure();

            return;
          }


          // ==================================================
          // STATS ERROR
          // ==================================================

          if (
            !statsResponse.ok
          ) {

            const errorData =
              await statsResponse.text();

            console.error(
              "❌ Stats API failed:",
              {
                status:
                  statsResponse.status,

                statusText:
                  statsResponse.statusText,

                body:
                  errorData,

                url:
                  statsResponse.url,
              }
            );

            throw new Error(
              `Failed to load dashboard statistics (${statsResponse.status})`
            );
          }


          // ==================================================
          // PARSE STATS
          // ==================================================

          const statsData =
            await statsResponse.json();


          console.log(
            "📊 Stats response:",
            statsData
          );


          // ==================================================
          // GET USER SESSIONS
          // ==================================================
          //
          // Gateway:
          //
          // GET /livekit/sessions/?limit=20&skip=0
          //
          // Gateway -> LiveKit_RAG :8001
          // ==================================================

          const sessionsEndpoint =
            `${API_BASE_URL}/livekit/sessions/?limit=20&skip=0`;


          console.log(
            "📞 Fetching sessions:",
            sessionsEndpoint
          );


          const sessionsResponse =
            await fetch(
              sessionsEndpoint,
              {
                method: "GET",
                headers,
              }
            );


          // ==================================================
          // AUTH FAILURE
          // ==================================================

          if (
            sessionsResponse.status === 401
          ) {

            handleAuthFailure();

            return;
          }


          // ==================================================
          // SESSIONS ERROR
          // ==================================================

          if (
            !sessionsResponse.ok
          ) {

            const errorData =
              await sessionsResponse.text();

            console.error(
              "❌ Sessions API failed:",
              {
                status:
                  sessionsResponse.status,

                statusText:
                  sessionsResponse.statusText,

                body:
                  errorData,

                url:
                  sessionsResponse.url,
              }
            );

            throw new Error(
              `Failed to load call history (${sessionsResponse.status})`
            );
          }


          // ==================================================
          // PARSE SESSIONS
          // ==================================================

          const sessionsData =
            await sessionsResponse.json();


          console.log(
            "📞 Sessions response:",
            sessionsData
          );


          // ==================================================
          // UPDATE STATE
          // ==================================================

          if (!mounted) {
            return;
          }


          setStats({

            total_calls:
              Number(
                statsData?.total_calls
              ) || 0,

            today_calls:
              Number(
                statsData?.today_calls
              ) || 0,

            this_week_calls:
              Number(
                statsData?.this_week_calls
              ) || 0,
          });


          setSessions(
            Array.isArray(
              sessionsData
            )
              ? sessionsData
              : []
          );


        } catch (err) {

          console.error(
            "❌ Dashboard error:",
            err
          );


          if (!mounted) {
            return;
          }


          setError(
            err instanceof Error
              ? err.message
              : "Failed to load dashboard."
          );


          setStats({
            total_calls: 0,
            today_calls: 0,
            this_week_calls: 0,
          });


          setSessions([]);


        } finally {

          if (mounted) {

            setLoading(
              false
            );
          }
        }
      };


    fetchDashboardData();


    // ========================================================
    // CLEANUP
    // ========================================================

    return () => {

      mounted = false;
    };

  }, []);


  // ==========================================================
  // FORMAT STATUS
  // ==========================================================

  const formatStatus =
    (status) => {

      if (!status) {
        return "—";
      }


      const normalizedStatus =
        String(status)
          .trim()
          .toLowerCase();


      switch (
        normalizedStatus
      ) {

        case "active":
          return "Active";

        case "closed":
          return "Closed";

        default:
          return String(status);
      }
    };


  // ==========================================================
  // FORMAT HANDLER
  // ==========================================================

  const formatHandler =
    (handler) => {

      if (!handler) {
        return "—";
      }


      const normalizedHandler =
        String(handler)
          .trim()
          .toLowerCase();


      switch (
        normalizedHandler
      ) {

        case "ai":
          return "AI";

        case "admin":
          return "Admin";

        default:
          return String(handler);
      }
    };


  // ==========================================================
  // FORMAT DURATION
  // ==========================================================

  const formatDuration =
    (
      durationSeconds,
      status
    ) => {

      if (
        String(status)
          .trim()
          .toLowerCase() ===
        "active"
      ) {

        return "In progress";
      }


      if (
        durationSeconds === null ||
        durationSeconds === undefined
      ) {

        return "—";
      }


      const totalSeconds =
        Number(
          durationSeconds
        );


      if (
        Number.isNaN(
          totalSeconds
        ) ||
        totalSeconds < 0
      ) {

        return "—";
      }


      const hours =
        Math.floor(
          totalSeconds /
          3600
        );


      const minutes =
        Math.floor(
          (
            totalSeconds %
            3600
          ) /
          60
        );


      const seconds =
        Math.floor(
          totalSeconds %
          60
        );


      if (
        hours > 0
      ) {

        return (
          `${hours}h ${minutes}m ${seconds}s`
        );
      }


      return (
        `${minutes}m ${seconds}s`
      );
    };


  // ==========================================================
  // FORMAT TIME
  // ==========================================================

  const formatTime =
    (startAt) => {

      if (!startAt) {
        return "—";
      }


      const date =
        new Date(
          startAt
        );


      if (
        Number.isNaN(
          date.getTime()
        )
      ) {

        return "—";
      }


      return date.toLocaleString();
    };


  // ==========================================================
  // CONVERT BACKEND SESSIONS -> CALL TABLE ROWS
  // ==========================================================

  const callRows =
    sessions.map(
      (session) => {

        const status =
          formatStatus(
            session?.status
          );


        const handler =
          formatHandler(
            session?.handler
          );


        const duration =
          formatDuration(
            session?.duration_seconds,
            session?.status
          );


        const time =
          formatTime(
            session?.start_at
          );


        return {

          id:
            session?.id ??
            "—",

          title:
            session?.title ??
            "Voice Call",

          start_at:
            session?.start_at ??
            null,

          end_at:
            session?.end_at ??
            null,

          status,

          handler,

          duration,

          time,

          duration_seconds:
            session?.duration_seconds ??
            null,

          session,
        };
      }
    );


  // ==========================================================
  // RENDER
  // ==========================================================

  return (

    <div className="page-shell flex flex-col justify-center">

      {/* =====================================================
          HEADER
      ===================================================== */}

      <motion.div
        initial={{
          opacity: 0,
          y: 14,
        }}
        animate={{
          opacity: 1,
          y: 0,
        }}
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
        initial={{
          opacity: 0,
          y: 16,
        }}
        animate={{
          opacity: 1,
          y: 0,
        }}
        transition={{
          duration: 0.6,
          ease: "easeOut",
          delay: 0.06,
        }}
        className="mt-10 grid gap-4 sm:grid-cols-3"
      >

        <StatsCard
          label="Total Calls"
          value={
            loading
              ? "—"
              : stats.total_calls
          }
          accent="primary"
        />


        <StatsCard
          label="Today's Calls"
          value={
            loading
              ? "—"
              : stats.today_calls
          }
          accent="secondary"
        />


        <StatsCard
          label="This Week"
          value={
            loading
              ? "—"
              : stats.this_week_calls
          }
          accent="primary"
        />

      </motion.div>


      {/* =====================================================
          CALL HISTORY
      ===================================================== */}

      <motion.div
        initial={{
          opacity: 0,
          y: 16,
        }}
        animate={{
          opacity: 1,
          y: 0,
        }}
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

          <CallTable
            rows={callRows}
          />

        )}

      </motion.div>

    </div>
  );
}