"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

import {
  Room,
  RoomEvent,
  Track,
} from "livekit-client";

import Button from "@/app/admin/_components/ui/Button";
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
  "http://127.0.0.1:9000";

const POLL_INTERVAL = 5000;

/* ============================================================
   HELPERS
============================================================ */

function getStatusValue(status) {
  if (!status) {
    return "";
  }

  if (typeof status === "string") {
    return status.toLowerCase();
  }

  if (
    typeof status === "object" &&
    status.value
  ) {
    return String(status.value).toLowerCase();
  }

  return String(status).toLowerCase();
}

function formatStatus(status) {
  const value = getStatusValue(status);

  if (value === "pending") {
    return "Pending";
  }

  if (value === "resolved") {
    return "Resolved";
  }

  return value || "Unknown";
}

function getBadgeVariant(status) {
  const value = getStatusValue(status);

  if (value === "pending") {
    return "warning";
  }

  if (value === "resolved") {
    return "success";
  }

  return "neutral";
}

function formatDateTime(value) {
  if (!value) {
    return "—";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return String(value);
  }

  return date.toLocaleString();
}

function getMessageId(escalation) {
  return escalation?.message_id || null;
}

/* ============================================================
   PAGE
============================================================ */

export default function EscalationsPage() {
  /* ==========================================================
     ESCALATION STATE
  ========================================================== */

  const [escalations, setEscalations] =
    useState([]);

  const [loading, setLoading] =
    useState(true);

  const [refreshing, setRefreshing] =
    useState(false);

  const [error, setError] =
    useState("");

  const [acceptingId, setAcceptingId] =
    useState(null);

  const [endingId, setEndingId] =
    useState(null);

  /* ==========================================================
     ACTIVE CALL STATE
  ========================================================== */

  const [activeCall, setActiveCall] =
    useState(null);

  const [isLiveKitConnected, setIsLiveKitConnected] =
    useState(false);

  const [isMicrophoneEnabled, setIsMicrophoneEnabled] =
    useState(false);

  /* ==========================================================
     LIVEKIT REFS
  ========================================================== */

  const adminRoomRef =
    useRef(null);

  const audioElementsRef =
    useRef([]);

  /* ==========================================================
     POLLING REFS
  ========================================================== */

  const previousPendingIds =
    useRef(new Set());

  /* ==========================================================
     ACCESS TOKEN
  ========================================================== */

  const getAccessToken = useCallback(() => {
    if (
      typeof window === "undefined"
    ) {
      return null;
    }

    return localStorage.getItem(
      "access_token"
    );
  }, []);

  /* ==========================================================
     AUDIO CLEANUP
  ========================================================== */

  const cleanupAudioElements =
    useCallback(() => {
      const elements =
        audioElementsRef.current;

      elements.forEach((element) => {
        try {
          element.pause();
          element.srcObject = null;
          element.remove();
        } catch (audioError) {
          console.warn(
            "⚠️ Audio cleanup failed:",
            audioError
          );
        }
      });

      audioElementsRef.current = [];
    }, []);

  /* ==========================================================
     DISCONNECT LIVEKIT
  ========================================================== */

  const disconnectAdminRoom =
    useCallback(async () => {
      const room =
        adminRoomRef.current;

      if (!room) {
        cleanupAudioElements();

        setIsLiveKitConnected(false);
        setIsMicrophoneEnabled(false);

        return;
      }

      try {
        console.log(
          "🔌 Disconnecting admin from LiveKit..."
        );

        await room.disconnect();

        console.log(
          "✅ Admin disconnected from LiveKit."
        );
      } catch (disconnectError) {
        console.error(
          "❌ LiveKit disconnect failed:",
          disconnectError
        );
      } finally {
        adminRoomRef.current = null;

        cleanupAudioElements();

        setIsLiveKitConnected(false);
        setIsMicrophoneEnabled(false);
      }
    }, [cleanupAudioElements]);

  /* ============================================================
     FETCH ESCALATIONS
  ============================================================ */

  const fetchEscalations = useCallback(
    async ({ silent = false } = {}) => {
      const accessToken =
        getAccessToken();

      if (!accessToken) {
        setError(
          "Admin authentication token was not found."
        );

        setLoading(false);
        setRefreshing(false);

        return;
      }

      if (!silent) {
        setRefreshing(true);
      }

      try {
        const response =
          await fetch(
            `${API_BASE_URL}/admin/escalations?limit=100&skip=0`,
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

        const responseText =
          await response.text();

        let data = [];

        try {
          data = responseText
            ? JSON.parse(responseText)
            : [];
        } catch {
          throw new Error(
            `Invalid response received from admin API (${response.status}).`
          );
        }

        /* ------------------------------------------------------
           AUTH
        ------------------------------------------------------ */

        if (
          response.status === 401
        ) {
          throw new Error(
            "Your admin session has expired. Please log in again."
          );
        }

        if (
          response.status === 403
        ) {
          throw new Error(
            "Admin access required. This account is not authorized to access the admin panel."
          );
        }

        /* ------------------------------------------------------
           OTHER API ERRORS
        ------------------------------------------------------ */

        if (!response.ok) {
          throw new Error(
            data?.detail ||
              `Failed to load escalations (${response.status}).`
          );
        }

        /* ------------------------------------------------------
           VALIDATE RESPONSE
        ------------------------------------------------------ */

        if (!Array.isArray(data)) {
          throw new Error(
            "Admin API returned an unexpected escalation response."
          );
        }

        /* ------------------------------------------------------
           DETECT NEW PENDING ESCALATIONS
        ------------------------------------------------------ */

        const pendingIds =
          new Set(
            data
              .filter(
                (item) =>
                  getStatusValue(
                    item?.status
                  ) === "pending"
              )
              .map((item) =>
                String(item.id)
              )
          );

        if (
          previousPendingIds.current
            .size > 0
        ) {
          const newEscalationFound =
            [
              ...pendingIds,
            ].some(
              (id) =>
                !previousPendingIds.current.has(
                  id
                )
            );

          if (
            newEscalationFound
          ) {
            console.log(
              "🔔 New pending escalation detected."
            );
          }
        }

        previousPendingIds.current =
          pendingIds;

        /* ------------------------------------------------------
           UPDATE STATE
        ------------------------------------------------------ */

        setEscalations(data);
        setError("");
      } catch (fetchError) {
        console.error(
          "❌ Failed to fetch escalations:",
          fetchError
        );

        setError(
          fetchError?.message ||
            "Failed to load escalations."
        );
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [getAccessToken]
  );

  /* ============================================================
     ACCEPT ESCALATION
  ============================================================ */

  const acceptCall =
    useCallback(
      async (escalation) => {
        const escalationId =
          escalation?.id;

        if (!escalationId) {
          setError(
            "Escalation ID is missing."
          );

          return;
        }

        if (
          activeCall &&
          activeCall.escalationId
        ) {
          setError(
            "You already have an active admin call."
          );

          return;
        }

        const accessToken =
          getAccessToken();

        if (!accessToken) {
          setError(
            "Admin authentication token was not found."
          );

          return;
        }

        setAcceptingId(
          escalationId
        );

        setError("");

        try {
          /* ----------------------------------------------------
             ACCEPT CALL API
          ---------------------------------------------------- */

          const response =
            await fetch(
              `${API_BASE_URL}/admin/calls/accept`,
              {
                method: "POST",

                headers: {
                  Accept:
                    "application/json",

                  "Content-Type":
                    "application/json",

                  Authorization:
                    `Bearer ${accessToken}`,
                },

                body: JSON.stringify({
                  escalation_id:
                    escalationId,
                }),
              }
            );

          const responseText =
            await response.text();

          let data = {};

          try {
            data = responseText
              ? JSON.parse(responseText)
              : {};
          } catch {
            throw new Error(
              `Invalid response received from accept-call API (${response.status}).`
            );
          }

          /* ----------------------------------------------------
             AUTH
          ---------------------------------------------------- */

          if (
            response.status === 401
          ) {
            throw new Error(
              "Your admin session has expired. Please log in again."
            );
          }

          if (
            response.status === 403
          ) {
            throw new Error(
              "Admin access required."
            );
          }

          /* ----------------------------------------------------
             API ERROR
          ---------------------------------------------------- */

          if (!response.ok) {
            throw new Error(
              data?.detail ||
                data?.message ||
                `Failed to accept call (${response.status}).`
            );
          }

          /* ----------------------------------------------------
             VALIDATE LIVEKIT RESPONSE
          ---------------------------------------------------- */

          const livekitToken =
            data?.token;

          const livekitUrl =
            data?.url;

          const roomName =
            data?.room_name;

          const sessionId =
            data?.session_id;

          if (
            !livekitToken ||
            !livekitUrl ||
            !roomName
          ) {
            throw new Error(
              "Admin call was accepted, but LiveKit connection information is incomplete."
            );
          }

          /* ----------------------------------------------------
             CLEANUP EXISTING ROOM
          ---------------------------------------------------- */

          if (
            adminRoomRef.current
          ) {
            await disconnectAdminRoom();
          }

          cleanupAudioElements();

          /* ----------------------------------------------------
             CREATE LIVEKIT ROOM
          ---------------------------------------------------- */

          const room =
            new Room();

          adminRoomRef.current =
            room;

          /* ----------------------------------------------------
             REMOTE TRACK SUBSCRIBED
          ---------------------------------------------------- */

          room.on(
            RoomEvent.TrackSubscribed,
            (
              track,
              publication,
              participant
            ) => {
              console.log(
                "🎧 Remote track subscribed:",
                {
                  trackKind:
                    track.kind,
                  participant:
                    participant.identity,
                }
              );

              if (
                track.kind !==
                Track.Kind.Audio
              ) {
                return;
              }

              try {
                const audioElement =
                  track.attach();

                audioElement.autoplay =
                  true;

                audioElement.setAttribute(
                  "playsinline",
                  "true"
                );

                audioElement.style.display =
                  "none";

                document.body.appendChild(
                  audioElement
                );

                audioElementsRef.current.push(
                  audioElement
                );

                audioElement
                  .play()
                  .catch(
                    (playError) => {
                      console.warn(
                        "⚠️ Browser blocked audio playback:",
                        playError
                      );
                    }
                  );
              } catch (
                audioError
              ) {
                console.error(
                  "❌ Failed to attach remote audio:",
                  audioError
                );
              }
            }
          );

          /* ----------------------------------------------------
             REMOTE TRACK UNSUBSCRIBED
          ---------------------------------------------------- */

          room.on(
            RoomEvent.TrackUnsubscribed,
            (
              track
            ) => {
              console.log(
                "🔇 Remote track unsubscribed."
              );

              try {
                track.detach().forEach(
                  (element) => {
                    try {
                      element.pause();
                      element.srcObject =
                        null;
                      element.remove();
                    } catch (
                      cleanupError
                    ) {
                      console.warn(
                        "⚠️ Track cleanup failed:",
                        cleanupError
                      );
                    }

                    audioElementsRef.current =
                      audioElementsRef.current.filter(
                        (item) =>
                          item !==
                          element
                      );
                  }
                );
              } catch (
                detachError
              ) {
                console.warn(
                  "⚠️ Failed to detach remote track:",
                  detachError
                );
              }
            }
          );

          /* ----------------------------------------------------
             LIVEKIT DISCONNECTED
          ---------------------------------------------------- */

          room.on(
            RoomEvent.Disconnected,
            (
              reason
            ) => {
              console.log(
                "🔌 LiveKit disconnected:",
                reason
              );

              adminRoomRef.current =
                null;

              cleanupAudioElements();

              setIsLiveKitConnected(
                false
              );

              setIsMicrophoneEnabled(
                false
              );
            }
          );

          /* ----------------------------------------------------
             CONNECT ADMIN TO ROOM
          ---------------------------------------------------- */

          console.log(
            "🔗 Connecting admin to LiveKit:",
            {
              roomName,
              livekitUrl,
            }
          );

          await room.connect(
            livekitUrl,
            livekitToken
          );

          console.log(
            "✅ Admin connected to LiveKit."
          );

          setIsLiveKitConnected(
            true
          );

          /* ----------------------------------------------------
             ENABLE ADMIN MICROPHONE
          ---------------------------------------------------- */

          await room.localParticipant.setMicrophoneEnabled(
            true
          );

          setIsMicrophoneEnabled(
            true
          );

          /* ----------------------------------------------------
             ACTIVE CALL STATE
          ---------------------------------------------------- */

          setActiveCall({
            escalationId,
            sessionId,
            roomName,
            participantIdentity:
              data?.participant_identity ||
              null,
          });

          /* ----------------------------------------------------
             REFRESH ESCALATIONS
          ---------------------------------------------------- */

          await fetchEscalations({
            silent: true,
          });
        } catch (
          acceptError
        ) {
          console.error(
            "❌ Failed to accept admin call:",
            acceptError
          );

          /*
           * IMPORTANT:
           * If LiveKit connection failed after backend
           * accepted the escalation, we do not automatically
           * call /admin/calls/end here.
           *
           * Backend state should be inspected instead of
           * accidentally resolving a call.
           */

          await disconnectAdminRoom();

          setActiveCall(null);

          setError(
            acceptError?.message ||
              "Failed to accept call."
          );
        } finally {
          setAcceptingId(null);
        }
      },
      [
        activeCall,
        cleanupAudioElements,
        disconnectAdminRoom,
        fetchEscalations,
        getAccessToken,
      ]
    );

  /* ============================================================
     TOGGLE MICROPHONE
  ============================================================ */

  const toggleMicrophone =
    useCallback(
      async () => {
        const room =
          adminRoomRef.current;

        if (!room) {
          setError(
            "Admin is not connected to a LiveKit call."
          );

          return;
        }

        try {
          const nextState =
            !isMicrophoneEnabled;

          await room.localParticipant.setMicrophoneEnabled(
            nextState
          );

          setIsMicrophoneEnabled(
            nextState
          );
        } catch (
          microphoneError
        ) {
          console.error(
            "❌ Microphone toggle failed:",
            microphoneError
          );

          setError(
            "Failed to change microphone state."
          );
        }
      },
      [isMicrophoneEnabled]
    );

  /* ============================================================
     END CALL
  ============================================================ */

  const endCall =
    useCallback(
      async (escalation) => {
        const escalationId =
          activeCall?.escalationId ||
          escalation?.id;

        if (!escalationId) {
          setError(
            "Escalation ID is missing."
          );

          return;
        }

        const accessToken =
          getAccessToken();

        if (!accessToken) {
          setError(
            "Admin authentication token was not found."
          );

          return;
        }

        setEndingId(
          escalationId
        );

        setError("");

        try {
          /* ----------------------------------------------------
             END CALL API
          ---------------------------------------------------- */

          const response =
            await fetch(
              `${API_BASE_URL}/admin/calls/end`,
              {
                method: "POST",

                headers: {
                  Accept:
                    "application/json",

                  "Content-Type":
                    "application/json",

                  Authorization:
                    `Bearer ${accessToken}`,
                },

                body: JSON.stringify({
                  escalation_id:
                    escalationId,
                }),
              }
            );

          const responseText =
            await response.text();

          let data = {};

          try {
            data = responseText
              ? JSON.parse(responseText)
              : {};
          } catch {
            throw new Error(
              `Invalid response received from end-call API (${response.status}).`
            );
          }

          /* ----------------------------------------------------
             AUTH
          ---------------------------------------------------- */

          if (
            response.status === 401
          ) {
            throw new Error(
              "Your admin session has expired. Please log in again."
            );
          }

          if (
            response.status === 403
          ) {
            throw new Error(
              "Admin access required."
            );
          }

          /* ----------------------------------------------------
             API ERROR
          ---------------------------------------------------- */

          if (!response.ok) {
            throw new Error(
              data?.detail ||
                data?.message ||
                `Failed to end call (${response.status}).`
            );
          }

          console.log(
            "✅ Admin call ended successfully."
          );

          /* ----------------------------------------------------
             DISCONNECT BROWSER LIVEKIT
          ---------------------------------------------------- */

          await disconnectAdminRoom();

          setActiveCall(null);

          /* ----------------------------------------------------
             REFRESH ESCALATIONS
          ---------------------------------------------------- */

          await fetchEscalations({
            silent: true,
          });
        } catch (
          endError
        ) {
          console.error(
            "❌ Failed to end admin call:",
            endError
          );

          setError(
            endError?.message ||
              "Failed to end call."
          );
        } finally {
          setEndingId(null);
        }
      },
      [
        activeCall,
        disconnectAdminRoom,
        fetchEscalations,
        getAccessToken,
      ]
    );

  /* ============================================================
     INITIAL FETCH
  ============================================================ */

  useEffect(() => {
    fetchEscalations({
      silent: false,
    });
  }, [fetchEscalations]);

  /* ============================================================
     POLLING
  ============================================================ */

  useEffect(() => {
    const interval =
      setInterval(() => {
        fetchEscalations({
          silent: true,
        });
      }, POLL_INTERVAL);

    return () => {
      clearInterval(interval);
    };
  }, [fetchEscalations]);

  /* ============================================================
     PAGE CLEANUP
  ============================================================ */

  useEffect(() => {
    return () => {
      /*
       * IMPORTANT:
       *
       * Page unmount only disconnects the browser's
       * LiveKit connection.
       *
       * It does NOT call /admin/calls/end because
       * navigation/reload should not resolve the
       * backend escalation automatically.
       */

      const room =
        adminRoomRef.current;

      if (room) {
        try {
          room.disconnect();
        } catch (
          cleanupError
        ) {
          console.warn(
            "⚠️ LiveKit page cleanup failed:",
            cleanupError
          );
        }
      }

      adminRoomRef.current =
        null;

      cleanupAudioElements();
    };
  }, [cleanupAudioElements]);

  /* ============================================================
     RENDER
  ============================================================ */

  const pendingCount =
    escalations.filter(
      (item) =>
        getStatusValue(
          item?.status
        ) === "pending"
    ).length;

  const resolvedCount =
    escalations.filter(
      (item) =>
        getStatusValue(
          item?.status
        ) === "resolved"
    ).length;

  return (
    <div className="space-y-6">
      {/* ======================================================
          HEADER
      ====================================================== */}

      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">
            Escalations
          </h1>

          <p className="mt-1 text-xs text-text-secondary">
            Monitor escalated AI conversations and
            handle live calls.
          </p>
        </div>

        <Button
          onClick={() =>
            fetchEscalations({
              silent: false,
            })
          }
          disabled={refreshing}
        >
          {refreshing
            ? "Refreshing..."
            : "Refresh"}
        </Button>
      </div>

      {/* ======================================================
          ERROR
      ====================================================== */}

      {error && (
        <div className="rounded-lg border border-red-400/20 bg-red-400/10 px-4 py-3 text-sm text-red-200">
          {error}
        </div>
      )}

      {/* ======================================================
          SUMMARY
      ====================================================== */}

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
          <p className="text-xs text-text-secondary">
            Total Escalations
          </p>

          <p className="mt-2 text-2xl font-semibold text-white">
            {escalations.length}
          </p>
        </div>

        <div className="rounded-xl border border-amber-400/10 bg-amber-400/[0.04] p-4">
          <p className="text-xs text-text-secondary">
            Pending
          </p>

          <p className="mt-2 text-2xl font-semibold text-amber-200">
            {pendingCount}
          </p>
        </div>

        <div className="rounded-xl border border-emerald-400/10 bg-emerald-400/[0.04] p-4">
          <p className="text-xs text-text-secondary">
            Resolved
          </p>

          <p className="mt-2 text-2xl font-semibold text-emerald-200">
            {resolvedCount}
          </p>
        </div>
      </div>

      {/* ======================================================
          ACTIVE CALL PANEL
      ====================================================== */}

      {activeCall && (
        <div className="rounded-xl border border-emerald-400/20 bg-emerald-400/[0.05] p-5">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <div className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-emerald-400" />

                <h2 className="font-semibold text-white">
                  Active Admin Call
                </h2>
              </div>

              <div className="mt-3 space-y-1 text-xs text-text-secondary">
                <p>
                  <span className="text-white/60">
                    Escalation:
                  </span>{" "}
                  {activeCall.escalationId}
                </p>

                <p>
                  <span className="text-white/60">
                    Session:
                  </span>{" "}
                  {activeCall.sessionId ||
                    "—"}
                </p>

                <p>
                  <span className="text-white/60">
                    Room:
                  </span>{" "}
                  {activeCall.roomName}
                </p>

                <p>
                  <span className="text-white/60">
                    LiveKit:
                  </span>{" "}
                  {isLiveKitConnected
                    ? "Connected"
                    : "Disconnected"}
                </p>

                <p>
                  <span className="text-white/60">
                    Microphone:
                  </span>{" "}
                  {isMicrophoneEnabled
                    ? "Enabled"
                    : "Disabled"}
                </p>
              </div>
            </div>

            <div className="flex flex-wrap gap-2">
              <Button
                onClick={
                  toggleMicrophone
                }
                disabled={
                  !isLiveKitConnected
                }
              >
                {isMicrophoneEnabled
                  ? "Mute Microphone"
                  : "Enable Microphone"}
              </Button>

              <Button
                onClick={() =>
                  endCall(
                    {
                      id:
                        activeCall.escalationId,
                    }
                  )
                }
                disabled={
                  endingId ===
                  activeCall.escalationId
                }
              >
                {endingId ===
                activeCall.escalationId
                  ? "Ending..."
                  : "End Call"}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* ======================================================
          ESCALATIONS TABLE
      ====================================================== */}

      <div className="rounded-xl border border-white/10 bg-white/[0.02]">
        <div className="border-b border-white/10 px-5 py-4">
          <h2 className="text-sm font-semibold text-white">
            Escalation Requests
          </h2>

          <p className="mt-1 text-xs text-text-secondary">
            Pending requests can be accepted for live
            admin assistance.
          </p>
        </div>

        {loading ? (
          <div className="px-5 py-10 text-center text-sm text-text-secondary">
            Loading escalations...
          </div>
        ) : escalations.length === 0 ? (
          <div className="px-5 py-10 text-center text-sm text-text-secondary">
            No escalations found.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <THead>
                <TR>
                  <TH>Status</TH>
                  <TH>User ID</TH>
                  <TH>Message ID</TH>
                  <TH>Created</TH>
                  <TH>Action</TH>
                </TR>
              </THead>

              <TBody>
                {escalations.map(
                  (escalation) => {
                    const status =
                      getStatusValue(
                        escalation?.status
                      );

                    const isPending =
                      status ===
                      "pending";

                    const isActiveCall =
                      activeCall?.escalationId ===
                      escalation?.id;

                    return (
                      <TR
                        key={
                          escalation.id
                        }
                      >
                        {/* STATUS */}
                        <TD>
                          <Badge
                            label={formatStatus(
                              escalation.status
                            )}
                            variant={getBadgeVariant(
                              escalation.status
                            )}
                          />
                        </TD>

                        {/* USER */}
                        <TD className="max-w-[220px]">
                          <span className="block truncate text-xs text-text-secondary">
                            {escalation.user_id ||
                              "Guest"}
                          </span>
                        </TD>

                        {/* MESSAGE */}
                        <TD className="max-w-[220px]">
                          <span className="block truncate text-xs text-text-secondary">
                            {getMessageId(
                              escalation
                            ) ||
                              "—"}
                          </span>
                        </TD>

                        {/* CREATED */}
                        <TD className="whitespace-nowrap text-xs text-text-secondary">
                          {formatDateTime(
                            escalation.created_at
                          )}
                        </TD>

                        {/* ACTION */}
                        <TD>
                          <div className="flex flex-wrap gap-2">
                            {isPending && (
                              <Button
                                onClick={() =>
                                  acceptCall(
                                    escalation
                                  )
                                }
                                disabled={
                                  acceptingId ===
                                    escalation.id ||
                                  Boolean(
                                    activeCall
                                  )
                                }
                              >
                                {acceptingId ===
                                escalation.id
                                  ? "Accepting..."
                                  : "Accept Call"}
                              </Button>
                            )}

                            {isActiveCall && (
                              <Button
                                onClick={() =>
                                  endCall(
                                    escalation
                                  )
                                }
                                disabled={
                                  endingId ===
                                  escalation.id
                                }
                              >
                                {endingId ===
                                escalation.id
                                  ? "Ending..."
                                  : "End Call"}
                              </Button>
                            )}

                            {!isPending &&
                              !isActiveCall && (
                                <span className="text-xs text-text-secondary">
                                  No action
                                </span>
                              )}
                          </div>
                        </TD>
                      </TR>
                    );
                  }
                )}
              </TBody>
            </Table>
          </div>
        )}
      </div>
    </div>
  );
}