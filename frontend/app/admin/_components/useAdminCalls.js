"use client";

/**
 * Calls arriving for the admin.
 *
 * When a parent tells the AI "I want to speak to a person", the
 * backend creates an escalation and puts admin.call.handoff onto
 * RabbitMQ. From there it reaches the admin's WebSocket. This hook
 * manages that WebSocket.
 *
 * There are two routes, and both are needed:
 *
 *   WebSocket  - a call arriving NOW, rings immediately
 *   REST       - a call that arrived while the admin had not opened
 *                the panel at all (fetched once on page load)
 *
 * The REST list also contains older pending escalations - from
 * yesterday, from last week. Their callers left long ago. So only
 * those within RING_MAX_AGE_MS ring; the rest stay on the
 * Escalations page.
 *
 * The token goes in the URL's query string because a browser
 * WebSocket cannot send headers. That route is verified on the
 * server and lets nobody but an admin in.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { adminFetch } from "@/app/admin/useAdminApi";
import { getAccessToken } from "@/lib/session";

// The gateway proxies WebSockets now, so the realtime channel goes
// through the same address as every other call. It used to point
// straight at the livekit service, defaulting to localhost:8001 -
// which meant that on any deployed build the browser tried to open
// a socket to the visitor's own machine, and no call ever rang.
//
// NEXT_PUBLIC_REALTIME_URL still overrides it, for a setup that
// really does want to bypass the gateway.
const REALTIME_URL =
  process.env.NEXT_PUBLIC_REALTIME_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:9000";

// Is se purani pending escalation par ring nahi bajti.
const RING_MAX_AGE_MS = 5 * 60 * 1000;

// Reconnect if the connection drops - waiting a little longer each
// time, never more than 15 seconds.
const RECONNECT_MIN_MS = 1000;
const RECONNECT_MAX_MS = 15000;

function wsUrl(token) {
  const base = REALTIME_URL.replace(/^http/, "ws").replace(/\/+$/, "");
  return `${base}/livekit/notifications/ws/admin?token=${encodeURIComponent(
    token
  )}`;
}

/**
 * Two shapes arrive - the RabbitMQ event and the REST row.
 * The UI needs a single shape.
 */
function fromEvent(data) {
  const sessionId = data.session_id || data.call_id || null;
  return {
    escalationId: data.escalation_id,
    sessionId,
    room: data.room_name || (sessionId ? `room-${sessionId}` : null),
    question: data.message || "The caller asked to speak with a person.",
    caller: data.caller_id && data.caller_id !== "None" ? "Parent" : "Guest",
    at: Date.now(),
  };
}

function fromEscalation(row) {
  return {
    escalationId: row.id,
    sessionId: row.sessionId,
    room: row.sessionId ? `room-${row.sessionId}` : null,
    question: row.question || "The caller asked to speak with a person.",
    caller: row.userId ? "Parent" : "Guest",
    at: new Date(row.time).getTime() || Date.now(),
  };
}

export default function useAdminCalls() {
  const [calls, setCalls] = useState([]);
  const [connected, setConnected] = useState(false);

  const socketRef = useRef(null);
  const timerRef = useRef(null);
  const backoffRef = useRef(RECONNECT_MIN_MS);
  const closedRef = useRef(false);

  /** Remove one call from the list (claimed, or dismissed). */
  const remove = useCallback((escalationId) => {
    setCalls((list) => list.filter((c) => c.escalationId !== escalationId));
  }, []);

  const add = useCallback((call) => {
    if (!call.escalationId || !call.sessionId) return;
    setCalls((list) =>
      list.some((c) => c.escalationId === call.escalationId)
        ? list
        : [...list, call]
    );
  }, []);

  // ----------------------------------------------------------
  // On page open: the calls that were already waiting
  // ----------------------------------------------------------

  useEffect(() => {
    let alive = true;

    adminFetch("/livekit/admin/escalations?limit=100")
      .then((rows) => {
        if (!alive || !Array.isArray(rows)) return;
        const fresh = rows
          .filter((r) => r.status === "pending")
          .map(fromEscalation)
          .filter((c) => Date.now() - c.at < RING_MAX_AGE_MS);
        fresh.forEach(add);
      })
      .catch(() => {
        /* if it cannot ring, the panel still keeps working */
      });

    return () => {
      alive = false;
    };
  }, [add]);

  // ----------------------------------------------------------
  // Realtime channel
  // ----------------------------------------------------------

  useEffect(() => {
    closedRef.current = false;

    const open = () => {
      if (closedRef.current) return;

      const token = getAccessToken();
      if (!token) return;

      let socket;
      try {
        socket = new WebSocket(wsUrl(token));
      } catch {
        schedule();
        return;
      }

      socketRef.current = socket;

      socket.onopen = () => {
        backoffRef.current = RECONNECT_MIN_MS;
        setConnected(true);
      };

      socket.onmessage = (event) => {
        let data;
        try {
          data = JSON.parse(event.data);
        } catch {
          return;
        }

        if (data.event === "admin.call.handoff") {
          add(fromEvent(data));
          return;
        }

        // Another admin got there first - stop ringing here.
        if (data.event === "escalation.claimed") {
          remove(data.escalation_id);
        }
      };

      socket.onclose = () => {
        setConnected(false);
        socketRef.current = null;
        schedule();
      };

      // onclose runs in every case, so all that is needed here is
      // to close the socket.
      socket.onerror = () => socket.close();
    };

    const schedule = () => {
      if (closedRef.current || timerRef.current) return;
      const wait = backoffRef.current;
      backoffRef.current = Math.min(wait * 2, RECONNECT_MAX_MS);
      timerRef.current = setTimeout(() => {
        timerRef.current = null;
        open();
      }, wait);
    };

    open();

    return () => {
      closedRef.current = true;
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = null;

      const socket = socketRef.current;
      socketRef.current = null;
      if (!socket) return;

      socket.onclose = null;
      socket.onerror = null;
      socket.onmessage = null;

      // React StrictMode runs every effect twice in dev: open ->
      // close -> open again. Calling close() on a socket still
      // CONNECTING makes the browser warn "closed before the
      // connection is established" and leaves a half-open entry on
      // the server. So we wait for it to connect before closing.
      if (socket.readyState === WebSocket.CONNECTING) {
        socket.onopen = () => socket.close();
      } else {
        socket.close();
      }
    };
  }, [add, remove]);

  return { calls, connected, remove };
}
